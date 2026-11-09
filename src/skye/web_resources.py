"""Owner-scoped views over the same personal services used by Telegram."""

from __future__ import annotations

import asyncio
import base64
import binascii
import io
import zipfile
from collections.abc import Callable

from agents.mcp import MCPServerStreamableHttp
from aiohttp import web

from .connectors import (
    ConnectorError,
    ConnectorService,
    composio_user_key,
    parse_headers,
    public_mcp_client,
    resolve_public_https,
)
from .db import Database
from .memory import MemoryService
from .models import Scope, Skill
from .skills import SkillService, bundle_from_upload, skill_paths
from .threads import ThreadStore
from .web_auth import Session
from .web_contracts import (
    ConnectorRecord,
    ConnectorVerification,
    ConnectorWrite,
    MemoryPreference,
    MemoryRecord,
    MemoryWrite,
    ResourceSnapshot,
    SkillRecord,
    SkillUpload,
)


def mount_resources(
    app: web.Application,
    database: Database,
    threads: ThreadStore,
    session: Callable[[web.Request], Session],
    connectors: ConnectorService,
    max_bytes: int,
    origin: str,
    consent_verified: bool,
) -> None:
    skills = SkillService(database, max_bytes)
    memory = MemoryService(database)
    locks: dict[int, asyncio.Lock] = {}

    def scope(request: web.Request) -> Scope:
        return Scope("user", session(request).user_id)

    async def changed(request: web.Request, resource: str, ident: str = "") -> None:
        await threads.publish_resource(scope(request), resource, ident)

    async def memory_records(request: web.Request) -> list[MemoryRecord]:
        rows = await database.fetch_all(
            "SELECT * FROM memories WHERE scope_kind='user' AND scope_id=? "
            "ORDER BY updated_at DESC,id DESC",
            (scope(request).id,),
        )
        return [
            MemoryRecord(
                id=r["id"], content=r["content"], category=r["category"], revision=r["revision"]
            )
            for r in rows
        ]

    def skill_record(skill: Skill, *, detail: bool = False) -> SkillRecord:
        paths = list(skill_paths(skill.archive)) if detail else []
        instructions = ""
        if detail:
            with zipfile.ZipFile(io.BytesIO(skill.archive)) as archive:
                for path in paths:
                    if path.lower().endswith("/skill.md"):
                        instructions = archive.read(path).decode("utf-8")[:100_000]
        return SkillRecord(
            id=skill.id,
            name=skill.name,
            description=skill.description,
            files=paths,
            instructions=instructions,
        )

    async def resources(request: web.Request) -> web.Response:
        owner = scope(request).id
        section = request.match_info.get("section", "context")
        setting = await database.get_settings(scope(request))
        result = ResourceSnapshot(
            memory_enabled=setting.memory_enabled,
            apps_configured=connectors.configured,
            app_consent_enabled=consent_verified and connectors.configured,
            credentials_configured=database.connector_credentials_configured,
        )
        data = result.model_dump()
        if section in {"context", "memory"}:
            data["memories"] = [m.model_dump() for m in await memory_records(request)]
        if section in {"context", "skills"}:
            data["skills"] = [
                skill_record(s).model_dump() for s in await skills.list(scope(request))
            ]
        if section in {"context", "connectors"}:
            try:
                snapshot = await connectors.snapshot(owner, strict=True)
                data["provider_verified"] = connectors.configured
                data["connectors"] = [
                    ConnectorRecord(
                        id=a.slug, name=a.name, kind="app", status=a.status
                    ).model_dump()
                    for a in snapshot.apps
                ]
            except ConnectorError:
                # Availability remains explicitly unverified, not fabricated as disconnected.
                data["provider_verified"] = False
            data["connectors"] += [
                ConnectorRecord(
                    id=c.id,
                    name=c.name,
                    kind="custom",
                    status="available" if c.enabled else "disabled",
                    url=c.url,
                    credential_names=list(c.headers),
                ).model_dump()
                for c in await database.list_custom_connectors(owner)
            ]
        return web.json_response(ResourceSnapshot.model_validate(data).model_dump())

    async def save_memory(request: web.Request) -> web.Response:
        payload = MemoryWrite.model_validate(await request.json())
        content = " ".join(payload.content.split())
        if not content:
            raise ValueError("Memory cannot be empty")
        ident = request.match_info.get("id")
        if ident is None:
            record = await memory.remember(scope(request), content, payload.category)
            rows = await memory_records(request)
            result = next(m for m in rows if m.id == record.id)
        else:
            async with database.transaction() as conn:
                row = await (
                    await conn.execute(
                        "SELECT revision FROM memories WHERE id=? "
                        "AND scope_kind='user' AND scope_id=?",
                        (ident, scope(request).id),
                    )
                ).fetchone()
                if row is None:
                    raise web.HTTPNotFound()
                if payload.revision != row["revision"]:
                    raise web.HTTPConflict(text="Memory changed. Reload and review before saving.")
                await conn.execute(
                    "UPDATE memories SET content=?,category=?,revision=revision+1,"
                    "updated_at=CURRENT_TIMESTAMP WHERE id=? AND scope_kind='user' AND scope_id=?",
                    (content, payload.category, ident, scope(request).id),
                )
            result = MemoryRecord(
                id=int(ident),
                content=content,
                category=payload.category,
                revision=int(row["revision"]) + 1,
            )
        await changed(request, "memory", str(result.id))
        return web.json_response(result.model_dump(), status=200 if ident else 201)

    async def delete_memory(request: web.Request) -> web.Response:
        if not await database.forget_memory(scope(request), int(request.match_info["id"])):
            raise web.HTTPNotFound()
        await changed(request, "memory", request.match_info["id"])
        return web.json_response({"deleted": True})

    async def preference(request: web.Request) -> web.Response:
        payload = MemoryPreference.model_validate(await request.json())
        await database.set_memory_enabled(scope(request), payload.memory_enabled)
        await changed(request, "account")
        return web.json_response(payload.model_dump())

    async def skill_bytes(request: web.Request) -> tuple[str, bytes]:
        payload = SkillUpload.model_validate(await request.json())
        if (payload.content is None) == (payload.base64 is None):
            raise ValueError("Supply exactly one file")
        try:
            data = (
                payload.content.encode()
                if payload.content is not None
                else base64.b64decode(payload.base64 or "", validate=True)
            )
        except binascii.Error as error:
            raise ValueError("Invalid file encoding") from error
        return payload.filename, data

    async def preview_skill(request: web.Request) -> web.Response:
        filename, data = await skill_bytes(request)
        bundle = bundle_from_upload(filename, data, max_bytes=max_bytes)
        text = next(b.decode("utf-8") for p, b in bundle.files if p.lower().endswith("/skill.md"))
        return web.json_response(
            SkillRecord(
                name=bundle.name,
                description=bundle.description,
                files=[p for p, _ in bundle.files],
                instructions=text[:100_000],
            ).model_dump()
        )

    async def install_skill(request: web.Request) -> web.Response:
        filename, data = await skill_bytes(request)
        async with locks.setdefault(scope(request).id, asyncio.Lock()):
            skill = await skills.upload(scope(request), scope(request).id, filename, data)
        await changed(request, "skill", skill.id)
        return web.json_response(skill_record(skill, detail=True).model_dump(), status=201)

    async def require_skill(request: web.Request) -> Skill:
        skill = await database.get_skill(scope(request), request.match_info["id"])
        if skill is None:
            raise web.HTTPNotFound()
        return skill

    async def detail_skill(request: web.Request) -> web.Response:
        return web.json_response(
            skill_record(await require_skill(request), detail=True).model_dump()
        )

    async def download_skill(request: web.Request) -> web.Response:
        skill = await require_skill(request)
        return web.Response(
            body=skill.archive,
            content_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{skill.name}.zip"',
                "Content-Security-Policy": "sandbox; default-src 'none'",
            },
        )

    async def delete_skill(request: web.Request) -> web.Response:
        skill = await require_skill(request)
        await skills.delete(scope(request), skill.id)
        await changed(request, "skill", skill.id)
        return web.json_response({"deleted": True})

    async def catalog(request: web.Request) -> web.Response:
        if not connectors.configured:
            raise web.HTTPServiceUnavailable()
        items = await connectors.catalog(request.query.get("q", "")[:100])
        return web.json_response(
            {
                "connectors": [
                    ConnectorRecord(
                        id=a.slug, name=a.name, kind="app", status=a.status
                    ).model_dump()
                    for a in items
                ]
            }
        )

    async def app_action(request: web.Request) -> web.Response:
        if not connectors.configured:
            raise web.HTTPServiceUnavailable()
        if request.method != "DELETE" and not consent_verified:
            raise web.HTTPServiceUnavailable()
        slug = request.match_info["id"]
        if request.method == "DELETE":
            await connectors.disconnect_app(scope(request).id, slug)
            url = None
        else:
            url = await connectors.connect_link(
                scope(request).id, slug, callback_url=origin + "/library/connectors"
            )
            if url and not url.startswith("https://"):
                raise web.HTTPServiceUnavailable()
        await changed(request, "connector", slug)
        return web.json_response({"url": url, "status": "pending" if url else "updated"})

    async def verify_connector(request: web.Request) -> web.Response:
        if not consent_verified or connectors.client is None:
            raise web.HTTPServiceUnavailable()
        payload = ConnectorVerification.model_validate(await request.json())
        slug = await connectors.client.complete_auth(
            composio_user_key(scope(request).id), payload.session_uri
        )
        # Trust only the provider's owner-bound single-use result, not query flags.
        snapshot = await connectors.snapshot(scope(request).id, strict=True)
        if not any(item.slug == slug and item.status == "connected" for item in snapshot.apps):
            raise web.HTTPServiceUnavailable()
        await database.delete_composio_sessions(scope(request).id)
        await changed(request, "connector", slug)
        return web.json_response({"status": "connected", "slug": slug})

    async def custom_action(request: web.Request) -> web.Response:
        owner = scope(request).id
        ident = request.match_info.get("id")
        if ident and await database.get_custom_connector(owner, ident) is None:
            raise web.HTTPNotFound()
        if request.method == "DELETE":
            await connectors.delete_custom(owner, ident or "")
            await changed(request, "connector", ident or "")
            return web.json_response({"deleted": True})
        payload = ConnectorWrite.model_validate(await request.json())
        headers = parse_headers(payload.headers) if payload.headers is not None else None
        if headers and not database.connector_credentials_configured:
            raise web.HTTPServiceUnavailable(text="Credential encryption is not configured.")
        async with locks.setdefault(owner, asyncio.Lock()):
            if ident:
                c = await connectors.update_custom(
                    owner, ident, name=payload.name, url=payload.url, headers=headers
                )
            else:
                c = await connectors.add_custom(owner, payload.name, payload.url, headers or {})
        await changed(request, "connector", c.id)
        return web.json_response(
            ConnectorRecord(
                id=c.id,
                name=c.name,
                kind="custom",
                status="available",
                url=c.url,
                credential_names=list(c.headers),
            ).model_dump(),
            status=200 if ident else 201,
        )

    async def test_custom(request: web.Request) -> web.Response:
        c = await database.get_custom_connector(scope(request).id, request.match_info["id"])
        if c is None:
            raise web.HTTPNotFound()
        try:
            await resolve_public_https(c.url)
            async with (
                asyncio.timeout(15),
                MCPServerStreamableHttp(
                    params={
                        "url": c.url,
                        "headers": dict(c.headers),
                        "timeout": 10,
                        "httpx_client_factory": public_mcp_client,
                    },
                    name="Connection test",
                    client_session_timeout_seconds=10,
                ) as server,
            ):
                tools = await server.list_tools()
            return web.json_response({"status": "reachable", "tools": len(tools)})
        except Exception as error:
            raise web.HTTPServiceUnavailable(
                text="Connection test failed. Check the URL and credentials."
            ) from error

    app.router.add_get("/api/v1/resources/{section}", resources)
    app.router.add_patch("/api/v1/resources/preferences", preference)
    app.router.add_post("/api/v1/memories", save_memory)
    app.router.add_patch("/api/v1/memories/{id}", save_memory)
    app.router.add_delete("/api/v1/memories/{id}", delete_memory)
    app.router.add_post("/api/v1/skills/preview", preview_skill)
    app.router.add_post("/api/v1/skills", install_skill)
    app.router.add_get("/api/v1/resources/skills/{id}", detail_skill)
    app.router.add_get("/api/v1/skills/{id}/download", download_skill)
    app.router.add_delete("/api/v1/skills/{id}", delete_skill)
    app.router.add_get("/api/v1/connectors/catalog", catalog)
    app.router.add_post("/api/v1/connectors/verify", verify_connector)
    app.router.add_post("/api/v1/connectors/apps/{id}/connect", app_action)
    app.router.add_delete("/api/v1/connectors/apps/{id}", app_action)
    app.router.add_post("/api/v1/connectors/custom", custom_action)
    app.router.add_patch("/api/v1/connectors/custom/{id}", custom_action)
    app.router.add_delete("/api/v1/connectors/custom/{id}", custom_action)
    app.router.add_post("/api/v1/connectors/custom/{id}/test", test_custom)
