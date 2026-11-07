"""Feature-gated, private-account API in the bot's process, using its sole writer."""

from __future__ import annotations

import asyncio
import hmac
import json
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from typing import Any, cast
from urllib.parse import urlsplit
from uuid import uuid4

import structlog
from aiohttp import web
from pydantic import ValidationError

from .access import AccessService
from .config import Settings
from .db import Database
from .library import MediaLibrary
from .models import Scope, TelegramProject
from .quota import AllowanceError
from .runtime import AgentRuntime
from .telegram_projects import (
    DEFAULT_EMOJI,
    MAX_PROJECTS,
    new_id,
    parse_standalone_emoji,
)
from .threads import ThreadStore
from .turns import BusyTurn, TurnService
from .web_auth import (
    ABSOLUTE_TTL,
    LOGIN_COOKIE,
    SESSION_COOKIE,
    AuthStore,
    OIDCClient,
    Session,
)
from .web_contracts import (
    ActivityRecord,
    APIError,
    Capabilities,
    MediaList,
    PreferencesRecord,
    ProjectCreate,
    ProjectRecord,
    RunDetails,
    SendRequest,
    Snapshot,
    ThreadCreate,
    ThreadUpdate,
)
from .web_events import WebEventStore, activity_record, run_status
from .web_media import WebMediaStore
from .web_turns import WebTurnRunner

Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]
TURN_SERVICE = web.AppKey("turn_service", TurnService)


class LoginLimiter:
    """Bounded process-local rate limit; ingress must also limit public traffic."""

    def __init__(self) -> None:
        self._buckets: OrderedDict[str, tuple[float, int]] = OrderedDict()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        began, count = self._buckets.pop(key, (now, 0))
        if now - began >= 60:
            began, count = now, 0
        self._buckets[key] = began, count + 1
        while len(self._buckets) > 2000:
            self._buckets.popitem(last=False)
        return count < 10


async def _sse(
    response: web.StreamResponse, event: str, cursor: str, data: dict[str, Any]
) -> None:
    payload = json.dumps(data, separators=(",", ":"))
    await response.write(
        f"id: {cursor}\nevent: {event}\ndata: {payload}\n\n".encode()
    )


def create_app(
    config: Settings,
    database: Database,
    threads: ThreadStore,
    access: AccessService,
    *,
    oidc: OIDCClient | None = None,
    turns: TurnService | None = None,
    runtime: AgentRuntime | None = None,
    files: MediaLibrary | None = None,
    events: WebEventStore | None = None,
) -> web.Application:
    origin = config.skye_web_origin or ""
    parsed = urlsplit(origin)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Production web requires an exact HTTPS origin without a path")
    if not config.skye_oidc_client_id or not config.skye_oidc_client_secret:
        raise ValueError("Configure Telegram OIDC credentials before enabling web")
    auth = AuthStore(database)
    provider = oidc or OIDCClient(
        config.skye_oidc_client_id,
        config.skye_oidc_client_secret,
        origin,
        config.skye_oidc_callback_path,
    )
    limiter = LoginLimiter()
    audio_limiter = LoginLimiter()
    upload_limiter = LoginLimiter()
    media = WebMediaStore(database, files) if files is not None else None
    runner = (
        WebTurnRunner(
            database,
            runtime,
            threads,
            turns,
            media,
            max_attachment_bytes=config.skye_max_attachment_bytes,
            native_media=config.skye_native_media,
        )
        if runtime is not None and turns is not None and media is not None
        else None
    )

    def require_runner() -> WebTurnRunner:
        if runner is None:
            raise web.HTTPServiceUnavailable()
        return runner

    def session(request: web.Request) -> Session:
        return cast(Session, request["session"])

    @web.middleware
    async def security(request: web.Request, handler: Handler) -> web.StreamResponse:
        request_id = uuid4().hex
        try:
            # Ingress must preserve the configured Host. Never trust arbitrary
            # forwarded identity, owner or proxy headers supplied by a browser.
            internal = bool(config.skye_web_internal_token) and hmac.compare_digest(
                request.headers.get("X-Skye-Internal-Token", ""),
                config.skye_web_internal_token or "",
            )
            if request.headers.get("Host") != parsed.netloc and not internal:
                raise web.HTTPForbidden()
            # Top-level OIDC callback navigations are intentionally cross-site.
            if (
                request.headers.get("Sec-Fetch-Site") == "cross-site"
                and request.path != config.skye_oidc_callback_path
            ):
                raise web.HTTPForbidden()
            public = request.path in {"/api/v1/auth/start", config.skye_oidc_callback_path}
            if public:
                # Use socket address, never untrusted X-Forwarded-For. Reverse
                # proxies need a separate per-client limiter at their public edge.
                if not limiter.allow(request.remote or "unknown"):
                    raise web.HTTPTooManyRequests()
            else:
                current = await auth.session(request.cookies.get(SESSION_COOKIE, ""))
                if current is None:
                    raise web.HTTPUnauthorized()
                if await access.banned(current.user_id):
                    raise web.HTTPForbidden()
                request["session"] = current
                if request.method not in {"GET", "HEAD", "OPTIONS"} and (
                    request.headers.get("Origin") != origin
                    or not hmac.compare_digest(
                        request.headers.get("X-CSRF-Token", ""), current.csrf
                    )
                ):
                    raise web.HTTPForbidden()
            response = await handler(request)
        except web.HTTPException as error:
            if 300 <= error.status < 400:
                response = error
            else:
                codes: dict[int, Any] = {
                    400: "validation",
                    401: "unauthenticated",
                    402: "quota",
                    403: "forbidden",
                    404: "not_found",
                    409: "busy",
                    429: "busy",
                    503: "unavailable",
                }
                payload = APIError(
                    code=codes.get(error.status, "unavailable"),
                    message={
                        401: "Sign in with Telegram to continue.",
                        402: "Your allowance is used and your Sparks balance is empty.",
                        403: "This request is not allowed.",
                        404: "This item is unavailable.",
                        409: "This thread is already working. Stop it or wait.",
                        429: "Too many requests. Wait a minute.",
                    }.get(error.status, "The request could not be completed."),
                    recovery="Return to Skye and try again. Do not repeat uncertain actions.",
                    request_id=request_id,
                    retriable=error.status == 429,
                )
                response = web.json_response(payload.model_dump(), status=error.status)
        except LookupError, ValueError, ValidationError:
            payload = APIError(
                code="validation",
                message="Check the request and try again.",
                recovery="Reload Skye before retrying.",
                request_id=request_id,
            )
            response = web.json_response(payload.model_dump(), status=400)
        except Exception:
            # Do not serialize/log provider errors, callback parameters or DB data.
            payload = APIError(
                code="unavailable",
                message="Skye is temporarily unavailable.",
                recovery="Try again later.",
                request_id=request_id,
            )
            response = web.json_response(payload.model_dump(), status=503)
        if not response.prepared:
            response.headers.update(
                {
                    "Cache-Control": "no-store",
                    "Vary": "Cookie, Sec-Fetch-Dest, Sec-Fetch-Mode, Sec-Fetch-Site",
                    "X-Content-Type-Options": "nosniff",
                    "Referrer-Policy": "no-referrer",
                    "X-Request-ID": request_id,
                    "Cross-Origin-Resource-Policy": "same-origin",
                }
            )
        resource = request.match_info.route.resource
        structlog.get_logger().info(
            "web_request",
            kind="http",
            request_id=request_id,
            method=request.method,
            route=resource.canonical if resource is not None else "unmatched",
            status=response.status,
        )
        return response

    async def start(request: web.Request) -> web.StreamResponse:
        state, binding, verifier, nonce = await auth.begin()
        url = provider.authorization_url(state, nonce, verifier)
        response = web.Response(status=302, headers={"Location": url})
        response.set_cookie(
            LOGIN_COOKIE, binding, secure=True, httponly=True, samesite="Lax", path="/", max_age=300
        )
        return response

    async def callback(request: web.Request) -> web.StreamResponse:
        try:
            stage = "state_validation"
            verifier, nonce = await auth.consume(
                request.query.get("state", ""), request.cookies.get(LOGIN_COOKIE, "")
            )
            stage = "provider_response"
            if request.query.get("error") or not request.query.get("code"):
                raise ValueError("Cancelled login")
            stage = "token_exchange"
            identity = await provider.exchange(request.query["code"], verifier, nonce)
            stage = "account_link"
            if await access.banned(identity.user_id):
                raise PermissionError("Account unavailable")
            owner = await auth.link(identity)
            stage = "session_issue"
            token = await auth.issue(owner, request.cookies.get(SESSION_COOKIE, ""))
        except Exception as error:
            # Safe stage/type only: no query, token, claim, account ID or provider body.
            structlog.get_logger().warning(
                "oidc_callback_failed", stage=stage, error=type(error).__name__
            )
            response = web.Response(status=302, headers={"Location": "/login?error=verification"})
            response.del_cookie(LOGIN_COOKIE, path="/", secure=True, httponly=True, samesite="Lax")
            return response
        response = web.Response(status=302, headers={"Location": "/chat"})
        response.set_cookie(
            SESSION_COOKIE,
            token,
            secure=True,
            httponly=True,
            samesite="Lax",
            path="/",
            max_age=ABSOLUTE_TTL,
        )
        response.del_cookie(LOGIN_COOKIE, path="/", secure=True, httponly=True, samesite="Lax")
        return response

    async def account(request: web.Request) -> web.Response:
        current = session(request)
        return web.json_response({"user_id": current.user_id, "csrf_token": current.csrf})

    async def logout(request: web.Request) -> web.Response:
        await auth.revoke(session(request), all_devices=request.path.endswith("/all"))
        response = web.json_response({"signed_out": True})
        response.headers["Clear-Site-Data"] = '"cookies", "storage", "cache"'
        response.del_cookie(SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="Lax")
        return response

    async def capabilities(request: web.Request) -> web.Response:
        return web.json_response(Capabilities().model_dump())

    async def preferences(request: web.Request) -> web.Response:
        current = await database.get_settings(Scope("user", session(request).user_id))
        text_model, image_model = await database.model_preferences(session(request).user_id)
        record = PreferencesRecord(
            model=text_model
            if text_model is not None and text_model in {m.id for m in config.skye_text_models}
            else config.skye_default_model,
            image_model=image_model
            if image_model is not None and image_model in {m.id for m in config.skye_image_models}
            else config.skye_image_model,
            reasoning=current.reasoning,
            memory_enabled=current.memory_enabled,
            sparks_display=current.sparks_display,
        )
        return web.json_response(record.model_dump())

    async def projects(request: web.Request) -> web.Response:
        rows = await database.fetch_all(
            "SELECT id,name,emoji,instructions,revision FROM telegram_projects "
            "WHERE user_id=? AND kind='custom' ORDER BY updated_at DESC,id",
            (session(request).user_id,),
        )
        return web.json_response(
            {"projects": [ProjectRecord(**dict(row)).model_dump() for row in rows]}
        )

    async def create_project(request: web.Request) -> web.Response:
        payload = ProjectCreate.model_validate(await request.json())
        owner = session(request).user_id
        emoji = parse_standalone_emoji(payload.emoji)
        if emoji is None:
            raise ValueError("Send a single emoji for the project icon")
        existing = await database.list_telegram_projects(owner)
        if len([item for item in existing if item.kind == "custom"]) >= MAX_PROJECTS:
            raise ValueError(f"You can keep up to {MAX_PROJECTS} projects")
        name = " ".join(payload.name.split())
        if not 1 <= len(name) <= 64:
            raise ValueError("Project names must be 1–64 characters")
        project = await database.create_telegram_project(
            TelegramProject(
                id=new_id(),
                user_id=owner,
                kind="custom",
                name=name,
                emoji=emoji or DEFAULT_EMOJI,
                instructions=payload.instructions.strip(),
                openai_conversation_id=None,
                created_at="",
                updated_at="",
            )
        )
        await threads.create(owner, project.id, "New thread")
        await threads.publish_resource(Scope("user", owner), "project", project.id)
        return web.json_response(
            ProjectRecord(
                id=project.id,
                name=project.name,
                emoji=project.emoji,
                instructions=project.instructions,
                revision=1,
            ).model_dump(),
            status=201,
        )

    async def delete_thread(request: web.Request) -> web.Response:
        await threads.delete(session(request).user_id, request.match_info["thread_id"])
        return web.json_response({"deleted": True})

    async def list_threads(request: web.Request) -> web.Response:
        records = await threads.list_threads(session(request).user_id)
        return web.json_response({"threads": [record.model_dump() for record in records]})

    async def get_thread(request: web.Request) -> web.Response:
        try:
            thread = await threads.require(
                Scope("user", session(request).user_id), request.match_info["thread_id"]
            )
        except LookupError:
            raise web.HTTPNotFound() from None
        return web.json_response(thread.record.model_dump())

    async def history(request: web.Request) -> web.Response:
        try:
            before = int(request.query.get("before", str(2**63 - 1)))
            limit = int(request.query.get("limit", "50"))
            if not 1 <= limit <= 100 or not 1 <= before <= 2**63 - 1:
                raise ValueError("Invalid page")
            records = await threads.history(
                session(request).user_id,
                request.match_info["thread_id"],
                before=before,
                limit=limit,
            )
        except LookupError:
            raise web.HTTPNotFound() from None
        coverage = await database.fetch_one(
            "SELECT coverage FROM history_imports WHERE thread_id=?",
            (request.match_info["thread_id"],),
        )
        return web.json_response(
            {
                "messages": [record.model_dump() for record in records],
                "older_than": records[0].sequence if len(records) == limit else None,
                "legacy_history": coverage[0] if coverage else "not_backfilled",
            }
        )

    async def create_thread(request: web.Request) -> web.Response:
        payload = ThreadCreate.model_validate(await request.json())
        thread = await threads.create(
            session(request).user_id, payload.project_id, payload.title
        )
        return web.json_response(thread.record.model_dump(), status=201)

    async def update_thread(request: web.Request) -> web.Response:
        payload = ThreadUpdate.model_validate(await request.json())
        kwargs: dict[str, Any] = {}
        if "title" in payload.model_fields_set:
            kwargs["title"] = payload.title
        if "project_id" in payload.model_fields_set:
            kwargs["project_id"] = payload.project_id
        if "archived" in payload.model_fields_set:
            kwargs["archived"] = payload.archived
        if not kwargs:
            raise ValueError("No thread changes were provided")
        thread = await threads.update(
            session(request).user_id, request.match_info["thread_id"], **kwargs
        )
        return web.json_response(thread.record.model_dump())

    async def send_message(request: web.Request) -> web.Response:
        payload = SendRequest.model_validate(await request.json())
        try:
            receipt = await require_runner().send(
                session(request).user_id, request.match_info["thread_id"], payload
            )
        except AllowanceError as error:
            raise web.HTTPPaymentRequired() from error
        except BusyTurn as error:
            raise web.HTTPConflict() from error
        except LookupError as error:
            raise web.HTTPNotFound() from error
        return web.json_response(receipt.model_dump(), status=202)

    async def stop_thread(request: web.Request) -> web.Response:
        try:
            receipt = await require_runner().stop(
                session(request).user_id, request.match_info["thread_id"]
            )
        except LookupError as error:
            raise web.HTTPNotFound() from error
        return web.json_response(receipt.model_dump())

    async def snapshot_for(user_id: int, thread_id: str) -> Snapshot:
        scope = Scope("user", user_id)
        thread = await threads.require(scope, thread_id)
        records = await threads.history(user_id, thread_id, limit=50)
        run_row = await database.fetch_one(
            "SELECT r.* FROM canonical_runs r WHERE r.thread_id=? ORDER BY r.rowid DESC LIMIT 1",
            (thread_id,),
        )
        activities: list[ActivityRecord] = []
        if run_row is not None:
            rows = await database.fetch_all(
                "SELECT id AS sequence,category,status,label,tool_id FROM run_activity "
                "WHERE run_id=? AND created>=? ORDER BY id DESC LIMIT 200",
                (run_row["id"], time.time() - 86400),
            )
            activities = [activity_record(row) for row in reversed(rows)]
        cursor = str(await events.latest(scope)) if events is not None else "0"
        return Snapshot(
            thread=thread.record,
            messages=records,
            older_than=records[0].sequence if len(records) == 50 else None,
            run=run_status(run_row) if run_row is not None else None,
            activities=activities,
            cursor=cursor,
        )

    async def thread_state(request: web.Request) -> web.Response:
        snapshot = await snapshot_for(
            session(request).user_id, request.match_info["thread_id"]
        )
        return web.json_response(snapshot.model_dump())

    async def media_list(request: web.Request) -> web.Response:
        records = await require_runner().list_media(session(request).user_id)
        return web.json_response(MediaList(media=records).model_dump())

    async def upload_media(request: web.Request) -> web.Response:
        user_id = session(request).user_id
        if not upload_limiter.allow(str(user_id)):
            raise web.HTTPTooManyRequests()
        if media is None:
            raise web.HTTPServiceUnavailable()
        data = await request.read()
        if not data or len(data) > config.skye_max_attachment_bytes:
            raise ValueError("The file is empty or too large")
        name = request.headers.get("X-Skye-File-Name", "File")
        ref = await media.save(
            user_id, name, request.headers.get("Content-Type", ""), data
        )
        return web.json_response(ref.record.model_dump(), status=201)

    async def download_media(request: web.Request) -> web.Response:
        if media is None:
            raise web.HTTPServiceUnavailable()
        user_id = session(request).user_id
        try:
            try:
                ref, data = await media.read_canonical(
                    user_id, request.match_info["media_id"]
                )
            except LookupError:
                ref, data = await media.read(user_id, request.match_info["media_id"])
        except LookupError as error:
            raise web.HTTPNotFound() from error
        disposition = media.disposition(ref.record)
        response = web.Response(body=data)
        response.headers.update(
            {
                "Content-Type": ref.record.media_type,
                "Content-Disposition": (
                    f'{disposition}; filename="{ref.record.name.replace(chr(34), "")}"'
                ),
                "Content-Security-Policy": "default-src 'none'; sandbox",
                "Cross-Origin-Resource-Policy": "same-origin",
            }
        )
        return response

    async def delete_media(request: web.Request) -> web.Response:
        if media is None:
            raise web.HTTPServiceUnavailable()
        removed = await media.delete(
            session(request).user_id, request.match_info["media_id"]
        )
        if not removed:
            raise web.HTTPNotFound()
        return web.json_response({"deleted": True})

    async def transcribe(request: web.Request) -> web.Response:
        user_id = session(request).user_id
        if not audio_limiter.allow(str(user_id)):
            raise web.HTTPTooManyRequests()
        data = await request.read()
        filename = request.headers.get("X-Skye-File-Name", "recording.webm")
        mime = request.headers.get("Content-Type", "audio/webm")
        record = await require_runner().transcribe(user_id, filename, mime, data)
        return web.json_response(record.model_dump())

    async def events_stream(request: web.Request) -> web.StreamResponse:
        if events is None:
            raise web.HTTPServiceUnavailable()
        user_id = session(request).user_id
        scope = Scope("user", user_id)
        thread_id = request.match_info["thread_id"]
        await threads.require(scope, thread_id)
        response = web.StreamResponse(
            headers={
                "Content-Type": "text/event-stream; charset=utf-8",
                "Cache-Control": "no-store",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            }
        )
        await response.prepare(request)
        await response.write(b"retry: 2000\n\n")
        snapshot = await snapshot_for(user_id, thread_id)
        await _sse(response, "snapshot", str(snapshot.cursor), snapshot.model_dump())
        cursor = int(snapshot.cursor)
        queue = events.subscribe(scope)
        try:
            while True:
                try:
                    await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    await response.write(b": ping\n\n")
                    continue
                for stored in await events.replay(scope, cursor):
                    if stored.type != "resource.changed" and stored.thread_id not in {
                        None,
                        thread_id,
                    }:
                        continue
                    cursor = stored.id
                    await _sse(response, stored.type, str(stored.id), {
                        "version": 1,
                        "cursor": str(stored.id),
                        "data": stored.payload,
                    })
        except (asyncio.CancelledError, ConnectionResetError):
            pass
        finally:
            events.unsubscribe(scope, queue)
        return response


        row = await database.fetch_one(
            "SELECT r.* FROM canonical_runs r JOIN threads t "
            "ON t.id=r.thread_id WHERE r.id=? AND t.scope_kind='user' AND t.scope_id=?",
            (request.match_info["run_id"], session(request).user_id),
        )
        if row is None:
            raise web.HTTPNotFound()
        activities = await database.fetch_all(
            "SELECT id AS sequence,category,status FROM run_activity WHERE run_id=? AND created>=? "
            "ORDER BY id DESC LIMIT 200",
            (row["id"], time.time() - 86400),
        )
        record = RunDetails.model_validate(
            {
                "run": {
                    "id": row["id"],
                    "thread_id": row["thread_id"],
                    "state": row["state"],
                    "label": {
                        "accepted": "Queued",
                        "running": "Working",
                        "completed": "Finished",
                        "failed": "Failed",
                        "cancelling": "Stopping",
                        "cancelled": "Stopped",
                        "interrupted": "Interrupted",
                    }[row["state"]],
                    "cost_milli": row["cost_milli"],
                    "cost_state": row["cost_state"],
                },
                "delivery_state": row["delivery_state"],
                "activities": [dict(item) for item in reversed(activities)],
            }
        )
        return web.json_response(record.model_dump())

    async def run_details(request: web.Request) -> web.Response:
        row = await database.fetch_one(
            "SELECT r.* FROM canonical_runs r JOIN threads t "
            "ON t.id=r.thread_id WHERE r.id=? AND t.scope_kind='user' AND t.scope_id=?",
            (request.match_info["run_id"], session(request).user_id),
        )
        if row is None:
            raise web.HTTPNotFound()
        activities = await database.fetch_all(
            "SELECT id AS sequence,category,status,label,tool_id FROM run_activity "
            "WHERE run_id=? AND created>=? ORDER BY id DESC LIMIT 200",
            (row["id"], time.time() - 86400),
        )
        record = RunDetails(
            run=run_status(row),
            delivery_state=row["delivery_state"],
            activities=[activity_record(item) for item in reversed(activities)],
        )
        return web.json_response(record.model_dump())

    app = web.Application(
        middlewares=[security],
        client_max_size=max(32_768, config.skye_max_attachment_bytes + 1_048_576),
    )
    if turns is not None:
        # Stage 4 will expose sending; use the *same instance* as Telegram so
        # payer/thread admission cannot race between transport adapters.
        app[TURN_SERVICE] = turns
    app.router.add_get("/api/v1/auth/start", start)
    app.router.add_get(config.skye_oidc_callback_path, callback)
    app.router.add_get("/api/v1/session", account)
    app.router.add_post("/api/v1/auth/logout", logout)
    app.router.add_post("/api/v1/auth/logout/all", logout)
    app.router.add_get("/api/v1/capabilities", capabilities)
    app.router.add_get("/api/v1/preferences", preferences)
    app.router.add_get("/api/v1/projects", projects)
    app.router.add_post("/api/v1/projects", create_project)
    app.router.add_get("/api/v1/threads", list_threads)
    app.router.add_post("/api/v1/threads", create_thread)
    app.router.add_get("/api/v1/threads/{thread_id}", get_thread)
    app.router.add_patch("/api/v1/threads/{thread_id}", update_thread)
    app.router.add_delete("/api/v1/threads/{thread_id}", delete_thread)
    app.router.add_get("/api/v1/threads/{thread_id}/messages", history)
    app.router.add_get("/api/v1/threads/{thread_id}/state", thread_state)
    app.router.add_get("/api/v1/threads/{thread_id}/events", events_stream)
    app.router.add_post("/api/v1/threads/{thread_id}/messages", send_message)
    app.router.add_post("/api/v1/threads/{thread_id}/stop", stop_thread)
    app.router.add_get("/api/v1/runs/{run_id}", run_details)
    app.router.add_get("/api/v1/media", media_list)
    app.router.add_post("/api/v1/media", upload_media)
    app.router.add_get("/api/v1/media/{media_id}", download_media)
    app.router.add_delete("/api/v1/media/{media_id}", delete_media)
    app.router.add_post("/api/v1/audio/transcribe", transcribe)
    return app
