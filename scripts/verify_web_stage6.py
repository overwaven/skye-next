"""Stage 6 real HTTP/SQLite E2E; deterministic provider, no paid calls."""

from __future__ import annotations

import asyncio
import io
import json
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import aiohttp
from aiohttp import web
from cryptography.fernet import Fernet

from skye.config import Settings
from skye.connectors import ConnectorService
from skye.db import Database
from skye.memory import MemoryService
from skye.models import AppConnector, CustomConnector, Scope
from skye.skills import SkillService
from skye.threads import ThreadStore
from skye.web_api import create_app
from skye.web_auth import AuthStore
from skye.web_events import WebEventStore


class Access:
    async def banned(self, user_id: int) -> bool:
        return False


class Provider:
    """Deterministic external-auth boundary; never calls a real app."""

    def __init__(self) -> None:
        self.state = "pending"
        self.fail = False
        self.callback: str | None = None

    async def list_accounts(self, user_key: str) -> list[AppConnector]:
        from skye.connectors import ConnectorError

        if self.fail:
            raise ConnectorError("Provider unavailable")
        return (
            [AppConnector(slug="gmail", name="Gmail", status=self.state, account_id="fake-account")]
            if user_key == "tg:1"
            else []
        )

    async def get_toolkit(self, slug: str) -> AppConnector:
        return AppConnector(slug=slug, name="Gmail", status="available")

    async def create_link(
        self, user_key: str, slug: str, *, callback_url: str | None = None
    ) -> str:
        self.callback = callback_url
        return "https://consent.example/authorize"

    async def delete_account(self, user_key: str, account_id: str) -> None:
        self.state = "reconnect"

    async def complete_auth(self, user_key: str, session_uri: str) -> str:
        if user_key != "tg:1" or session_uri != "single-use":
            from skye.connectors import ConnectorError

            raise ConnectorError("Authorization could not be verified.")
        self.state = "connected"
        return "gmail"


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="skye-stage6-") as directory:
        db = Database(Path(directory) / "db", "model", "low")
        await db.open()
        events = WebEventStore(db)
        threads = ThreadStore(db, events)
        await threads.migrate()
        encryption_key = Fernet.generate_key().decode()
        await db.configure_connector_encryption(encryption_key)
        config = Settings(
            skye_owner_ids={1},
            telegram_bot_token="test",
            skye_web_origin="https://chat.example",
            skye_oidc_client_id="client",
            skye_oidc_client_secret="secret",
            skye_composio_verifier_enabled=True,
        )
        connectors = ConnectorService(db, None)
        app = create_app(config, db, threads, Access(), connectors=connectors)  # type: ignore[arg-type]
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        assert site._server is not None
        base = f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}/api/v1"
        steps: list[str] = []
        async with aiohttp.ClientSession() as client:
            headers: dict[int, dict[str, str]] = {}
            for owner in (1, 2):
                token = await AuthStore(db).issue(owner)
                h = {"Host": "chat.example", "Cookie": f"__Host-skye_session={token}"}
                r = await client.get(f"{base}/session", headers=h)
                headers[owner] = {
                    **h,
                    "Origin": "https://chat.example",
                    "X-CSRF-Token": (await r.json())["csrf_token"],
                }

            async def call(
                method: str, path: str, status: int = 200, owner: int = 1, **kwargs: Any
            ) -> Any:
                r = await client.request(method, base + path, headers=headers[owner], **kwargs)
                assert r.status == status, (path, r.status, await r.text())
                return await r.json()

            m = await call(
                "POST",
                "/memories",
                201,
                json={"content": "Prefers quiet mornings", "category": "preference"},
            )
            assert (await db.memories(Scope("user", 1)))[0].id == m["id"]
            await call(
                "PATCH",
                f"/memories/{m['id']}",
                404,
                owner=2,
                json={"content": "stolen", "category": "other", "revision": m["revision"]},
            )
            changed = await call(
                "PATCH",
                f"/memories/{m['id']}",
                json={
                    "content": "Prefers tea",
                    "category": "preference",
                    "revision": m["revision"],
                },
            )
            await call(
                "PATCH",
                f"/memories/{m['id']}",
                409,
                json={"content": "stale", "category": "other", "revision": m["revision"]},
            )
            assert changed["id"] == m["id"]
            await call("POST", "/memories", 400, json={"content": "x" * 501, "category": "other"})
            await call("PATCH", "/resources/preferences", json={"memory_enabled": False})
            assert not (await db.get_settings(Scope("user", 1))).memory_enabled
            await MemoryService(db).remember(Scope("user", 1), "Telegram memory")
            assert len((await call("GET", "/resources/memory"))["memories"]) == 2
            assert not (await call("GET", "/resources/memory", owner=2))["memories"]
            steps.append("memory cross-channel CRUD, conflict, scope, limit and preference")

            skill = b"---\nname: tea-guide\ndescription: Make a cup of tea\n---\nBoil water."
            preview = await call(
                "POST", "/skills/preview", json={"filename": "SKILL.md", "content": skill.decode()}
            )
            assert preview["name"] == "tea-guide" and not await db.list_skills(Scope("user", 1))
            installed = await call(
                "POST", "/skills", 201, json={"filename": "SKILL.md", "content": skill.decode()}
            )
            assert (await SkillService(db, 25_000_000).mounted(Scope("user", 1)))[
                0
            ].name == "tea-guide"
            await call(
                "POST", "/skills", 400, json={"filename": "SKILL.md", "content": skill.decode()}
            )
            await call("GET", f"/resources/skills/{installed['id']}", 404, owner=2)
            r = await client.get(f"{base}/skills/{installed['id']}/download", headers=headers[1])
            assert r.status == 200 and zipfile.is_zipfile(io.BytesIO(await r.read()))
            for name in ("../SKILL.md", "/SKILL.md"):
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "w") as z:
                    z.writestr(name, skill)
                import base64

                await call(
                    "POST",
                    "/skills/preview",
                    400,
                    json={
                        "filename": "bad.zip",
                        "base64": base64.b64encode(buf.getvalue()).decode(),
                    },
                )
            await call("DELETE", f"/skills/{installed['id']}")
            steps.append("skill preview/install/runtime/download/duplicate/IDOR/malicious archive")

            for url in (
                "https://127.0.0.1/mcp",
                "https://169.254.169.254/mcp",
                "https://100.64.0.1/mcp",
                "https://[::1]/mcp",
                "https://localhost/mcp",
            ):
                await call(
                    "POST",
                    "/connectors/custom",
                    400,
                    json={"name": "Unsafe", "url": url, "headers": ""},
                )
            await call("POST", "/connectors/apps/gmail/connect", 503, json={})
            provider = Provider()
            connectors.client = provider  # type: ignore[assignment]
            link = await call("POST", "/connectors/apps/gmail/connect", json={})
            assert link["status"] == "pending"
            assert provider.callback == "https://chat.example/library/connectors"
            snapshot = await call("GET", "/resources/connectors?success=true")
            assert snapshot["connectors"][0]["status"] == "pending"
            await call(
                "POST", "/connectors/verify", 400, owner=2, json={"session_uri": "single-use"}
            )
            await call("POST", "/connectors/verify", json={"session_uri": "single-use"})
            assert (await call("GET", "/resources/connectors"))["connectors"][0][
                "status"
            ] == "connected"
            assert not (await call("GET", "/resources/connectors", owner=2))["connectors"]
            provider.fail = True
            assert not (await call("GET", "/resources/connectors"))["provider_verified"]
            provider.fail = False
            await call("DELETE", "/connectors/apps/gmail")
            assert (await call("GET", "/resources/connectors"))["connectors"][0][
                "status"
            ] == "reconnect"
            await db.save_custom_connector(
                CustomConnector(
                    id="private-fixture",
                    user_id=1,
                    name="Stored server",
                    url="https://127.0.0.1/mcp",
                    headers={"Authorization": "Bearer fake-stage6-secret"},
                    enabled=True,
                    created_at="",
                    updated_at="",
                )
            )
            raw = await db.fetch_one(
                "SELECT headers FROM custom_connectors WHERE id=?", ("private-fixture",)
            )
            assert (
                raw
                and str(raw[0]).startswith("fernet:")
                and "fake-stage6-secret" not in str(raw[0])
            )
            await db.configure_connector_encryption(encryption_key)
            restored = await db.get_custom_connector(1, "private-fixture")
            assert restored and restored.headers["Authorization"] == "Bearer fake-stage6-secret"
            snapshot = await call("GET", "/resources/connectors")
            assert "fake-stage6-secret" not in json.dumps(snapshot)
            await call("DELETE", "/connectors/custom/private-fixture", 404, owner=2)
            moved = await call("PATCH", "/connectors/custom/private-fixture", 400, json={
                "name": "Stored server", "url": "https://public.example/mcp"})
            assert "credentials" in moved["message"].lower()
            await call("POST", "/connectors/custom/private-fixture/test", 503, json={})
            await call("DELETE", "/connectors/custom/private-fixture")
            steps.append(
                "provider-authoritative pending/connected/revoked/outage; consent return; "
                "encrypted credential roundtrip and runtime SSRF"
            )
            r = await client.post(
                f"{base}/memories",
                headers={"Host": "chat.example", "Cookie": headers[1]["Cookie"]},
                json={},
            )
            assert r.status == 403
            await call("DELETE", f"/memories/{m['id']}", 404, owner=2)
            await call("DELETE", f"/memories/{m['id']}")
            steps.append("SSRF targets, unavailable provider, CSRF and owner-only deletion")
        await runner.cleanup()
        await db.close()
        result = {"status": "passed", "steps": steps}
        Path("docs/web-stage6-e2e.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
