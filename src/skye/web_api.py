"""Feature-gated, private-account API in the bot's process, using its sole writer."""

from __future__ import annotations

import hmac
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
from .models import Scope
from .threads import ThreadStore
from .turns import TurnService
from .web_auth import (
    ABSOLUTE_TTL,
    LOGIN_COOKIE,
    SESSION_COOKIE,
    AuthStore,
    OIDCClient,
    Session,
)
from .web_contracts import APIError, Capabilities, PreferencesRecord, ProjectRecord

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


def create_app(
    config: Settings,
    database: Database,
    threads: ThreadStore,
    access: AccessService,
    *,
    oidc: OIDCClient | None = None,
    turns: TurnService | None = None,
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
        config.skye_oidc_client_id, config.skye_oidc_client_secret, origin
    )
    limiter = LoginLimiter()

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
                and request.path != "/api/v1/auth/callback"
            ):
                raise web.HTTPForbidden()
            public = request.path in {"/api/v1/auth/start", "/api/v1/auth/callback"}
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
                    403: "forbidden",
                    404: "not_found",
                    409: "conflict",
                    429: "busy",
                    503: "unavailable",
                }
                payload = APIError(
                    code=codes.get(error.status, "unavailable"),
                    message={
                        401: "Sign in with Telegram to continue.",
                        403: "This request is not allowed.",
                        404: "This item is unavailable.",
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
            verifier, nonce = await auth.consume(
                request.query.get("state", ""), request.cookies.get(LOGIN_COOKIE, "")
            )
            if request.query.get("error") or not request.query.get("code"):
                raise ValueError("Cancelled login")
            identity = await provider.exchange(request.query["code"], verifier, nonce)
            if await access.banned(identity.user_id):
                raise PermissionError("Account unavailable")
            owner = await auth.link(identity)
            token = await auth.issue(owner, request.cookies.get(SESSION_COOKIE, ""))
        except Exception:
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
            "SELECT id,name,instructions,revision FROM telegram_projects "
            "WHERE user_id=? AND kind='custom' ORDER BY updated_at DESC,id",
            (session(request).user_id,),
        )
        return web.json_response(
            {"projects": [ProjectRecord(**dict(row)).model_dump() for row in rows]}
        )

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
        return web.json_response(
            {
                "messages": [record.model_dump() for record in records],
                "older_than": records[0].sequence if len(records) == limit else None,
                "legacy_history": "not_backfilled",
            }
        )

    app = web.Application(middlewares=[security], client_max_size=32_768)
    if turns is not None:
        # Stage 4 will expose sending; use the *same instance* as Telegram so
        # payer/thread admission cannot race between transport adapters.
        app[TURN_SERVICE] = turns
    app.router.add_get("/api/v1/auth/start", start)
    app.router.add_get("/api/v1/auth/callback", callback)
    app.router.add_get("/api/v1/session", account)
    app.router.add_post("/api/v1/auth/logout", logout)
    app.router.add_post("/api/v1/auth/logout/all", logout)
    app.router.add_get("/api/v1/capabilities", capabilities)
    app.router.add_get("/api/v1/preferences", preferences)
    app.router.add_get("/api/v1/projects", projects)
    app.router.add_get("/api/v1/threads", list_threads)
    app.router.add_get("/api/v1/threads/{thread_id}", get_thread)
    app.router.add_get("/api/v1/threads/{thread_id}/messages", history)
    return app
