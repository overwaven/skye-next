"""End-to-end API proof for Stage 4/5: send, SSE, stop, media and voice.

Runs the real aiohttp app, canonical stores, TurnService, WebTurnRunner and
MediaLibrary against a temporary SQLite database, with a deterministic runtime
that never calls a provider. Writes docs/web-stage45-e2e.json as the artifact.

    uv run python scripts/verify_web_stage45.py
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any

import aiohttp
from aiohttp import web

from skye.config import Settings
from skye.db import Database
from skye.library import MediaLibrary
from skye.runtime import RunEvent, RunOutput
from skye.threads import ThreadStore
from skye.turns import TurnService
from skye.web_api import create_app
from skye.web_auth import AuthStore
from skye.web_events import WebEventStore

ORIGIN = "https://chat.example"
COOKIE = "__Host-skye_session"
PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class FakeAccess:
    async def allowed(self, context: object) -> bool:
        return True

    async def banned(self, user_id: int) -> bool:
        return False


class FakeQuota:
    async def complimentary(self, context: object, *, billed_user_id: int) -> bool:
        return False

    async def exhausted(self, context: object, *, billed_user_id: int) -> bool:
        return False


class FakeSparks:
    async def payer(self, context: object) -> int:
        return 1

    async def can_afford(self, user_id: int) -> bool:
        return True

    def cost_milli(self, usage: object, provider_cost_rub: float | None = None) -> int:
        return 1


class FakeAudio:
    async def transcribe(self, filename: str, data: bytes, mime: str = "") -> str:
        return "Hello from a recording"


class FakeRuntime:
    audio = FakeAudio()

    def __init__(self) -> None:
        self.block = False
        self.release = asyncio.Event()
        self.inputs: list[object] = []

    async def run(
        self,
        context: object,
        settings: object,
        user_input: object,
        on_text: object,
        **kwargs: Any,
    ) -> RunOutput:
        self.inputs.append(user_input)
        on_event = kwargs.get("on_event")
        on_reply = kwargs.get("on_reply")
        if on_event is not None:
            await on_event(
                RunEvent(
                    kind="tool",
                    tool_id="search-1",
                    tool_name="web_search",
                    tool_label="Searched the web",
                    tool_status="running",
                )
            )
        if self.block:
            await self.release.wait()
        if on_event is not None:
            await on_event(
                RunEvent(
                    kind="tool",
                    tool_id="search-1",
                    tool_name="web_search",
                    tool_label="Searched the web",
                    tool_status="done",
                )
            )
        if on_reply is not None:
            await on_reply("Hello from the web.")
        return RunOutput("", (), sent=1)


async def next_event(response: aiohttp.ClientResponse) -> dict[str, str] | None:
    event, data = "", ""
    while True:
        line = await response.content.readline()
        if not line:
            return None
        text = line.decode().rstrip("\n")
        if not text:
            if event or data:
                return {"event": event, "data": data}
            continue
        if text.startswith("event: "):
            event = text[7:]
        elif text.startswith("data: "):
            data = text[6:]


async def main() -> None:
    temp = Path(tempfile.mkdtemp(prefix="skye-stage45-"))
    database = Database(temp / "test.db", "deepseek/deepseek-v4", "low")
    await database.open()
    events = WebEventStore(database)
    threads = ThreadStore(database, events=events)
    await threads.migrate()
    files = MediaLibrary(temp / "files")
    config = Settings(
        telegram_bot_token="test",
        skye_owner_ids={1},
        skye_web_origin=ORIGIN,
        skye_oidc_client_id="client",
        skye_oidc_client_secret="secret",
        skye_files_dir=temp / "files",
    )
    turns = TurnService(
        database,
        FakeAccess(),  # type: ignore[arg-type]
        FakeQuota(),  # type: ignore[arg-type]
        FakeSparks(),  # type: ignore[arg-type]
        events=events,
    )
    runtime = FakeRuntime()
    token = await AuthStore(database).issue(1)
    app = create_app(
        config,
        database,
        threads,
        FakeAccess(),  # type: ignore[arg-type]
        turns=turns,
        runtime=runtime,  # type: ignore[arg-type]
        files=files,
        events=events,
    )
    app_runner = web.AppRunner(app)
    await app_runner.setup()
    site = web.TCPSite(app_runner, "127.0.0.1", 0)
    await site.start()
    assert site._server is not None
    port = site._server.sockets[0].getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    headers = {"Host": "chat.example", "Cookie": f"{COOKIE}={token}"}
    steps: list[dict[str, Any]] = []

    def report(name: str, **detail: Any) -> None:
        steps.append({"step": name, "ok": True, **detail})

    async with aiohttp.ClientSession() as client:
        async with client.get(f"{base}/api/v1/session", headers=headers) as response:
            assert response.status == 200, await response.text()
            csrf = (await response.json())["csrf_token"]

        def write_headers() -> dict[str, str]:
            return {
                **headers,
                "Origin": ORIGIN,
                "X-CSRF-Token": csrf,
                "Content-Type": "application/json",
            }

        async with client.post(
            f"{base}/api/v1/threads",
            headers=write_headers(),
            json={"title": "Stage four", "project_id": None},
        ) as response:
            assert response.status == 201, await response.text()
            thread = await response.json()
        report("thread.created", thread_id=thread["id"])

        async with client.get(
            f"{base}/api/v1/threads/{thread['id']}/state", headers=headers
        ) as response:
            snapshot = await response.json()
        assert snapshot["messages"] == []
        report("state.empty")

        stream = await client.get(f"{base}/api/v1/threads/{thread['id']}/events", headers=headers)
        first = await asyncio.wait_for(next_event(stream), timeout=3)
        assert first is not None and first["event"] == "snapshot"
        report("sse.snapshot")
        sent = await client.post(
            f"{base}/api/v1/threads/{thread['id']}/messages",
            headers=write_headers(),
            json={
                "request_id": "e2e-stage45-0001",
                "text": "Show me the steps",
                "file_ids": [],
                "transcripts": {},
            },
        )
        assert sent.status == 202, await sent.text()
        receipt = await sent.json()
        seen: list[str] = []
        deadline = asyncio.get_running_loop().time() + 8
        while asyncio.get_running_loop().time() < deadline:
            event = await asyncio.wait_for(next_event(stream), timeout=4)
            if event is None:
                break
            seen.append(event["event"])
            if event["event"] == "run.changed":
                data = json.loads(event["data"])["data"]["run"]
                if data["state"] == "completed":
                    break
        stream.close()
        assert "message.created" in seen and "run.activity" in seen
        async with client.get(
            f"{base}/api/v1/threads/{thread['id']}/state", headers=headers
        ) as response:
            snapshot = await response.json()
        assert [item["role"] for item in snapshot["messages"]] == ["user", "assistant"]
        assert snapshot["run"]["state"] == "completed"
        assert snapshot["run"]["delivery_state"] == "complete"
        assert any(item["label"] == "Searched the web" for item in snapshot["activities"])
        assert isinstance(runtime.inputs[0], list)
        assert runtime.inputs[0][0]["role"] == "user"
        assert runtime.inputs[0][0]["content"][0] == {
            "type": "input_text",
            "text": "Show me the steps",
        }
        report(
            "send.sse",
            run=receipt["run_id"],
            events=seen,
            messages=len(snapshot["messages"]),
        )

        upload = await client.post(
            f"{base}/api/v1/media",
            headers={
                **headers,
                "Origin": ORIGIN,
                "X-CSRF-Token": csrf,
                "Content-Type": "image/png",
                "X-Skye-File-Name": "tiny.png",
            },
            data=PNG,
        )
        assert upload.status == 201, await upload.text()
        media = await upload.json()
        async with client.get(f"{base}/api/v1/media/{media['id']}", headers=headers) as response:
            assert response.status == 200 and await response.read() == PNG
        report("media.upload", media_id=media["id"])

        sent = await client.post(
            f"{base}/api/v1/threads/{thread['id']}/messages",
            headers=write_headers(),
            json={
                "request_id": "e2e-stage45-0002",
                "text": "Use this picture",
                "file_ids": [media["id"]],
                "transcripts": {},
            },
        )
        assert sent.status == 202, await sent.text()
        await asyncio.sleep(0.4)
        async with client.get(
            f"{base}/api/v1/threads/{thread['id']}/state", headers=headers
        ) as response:
            snapshot = await response.json()
        file_parts = [
            part
            for message in snapshot["messages"]
            for part in message["parts"]
            if part["type"] == "file"
        ]
        assert file_parts and file_parts[0]["availability"] == "available"
        async with client.get(
            f"{base}/api/v1/media/{file_parts[0]['file_id']}", headers=headers
        ) as response:
            assert response.status == 200 and await response.read() == PNG
        report("media.sent", part=file_parts[0]["file_id"])

        audio = await client.post(
            f"{base}/api/v1/audio/transcribe",
            headers={
                **headers,
                "Origin": ORIGIN,
                "X-CSRF-Token": csrf,
                "Content-Type": "audio/webm",
                "X-Skye-File-Name": "recording.webm",
            },
            data=b"fake-webm-bytes",
        )
        assert audio.status == 200, await audio.text()
        transcript = await audio.json()
        assert transcript["text"] == "Hello from a recording"
        report("voice.transcribed", media_id=transcript["media"]["id"])

        rename = await client.patch(
            f"{base}/api/v1/threads/{thread['id']}",
            headers=write_headers(),
            json={"title": "Renamed thread"},
        )
        assert rename.status == 200, await rename.text()
        assert (await rename.json())["title"] == "Renamed thread"
        report("thread.renamed")

        runtime.block = True
        runtime.release.clear()
        slow = await client.post(
            f"{base}/api/v1/threads/{thread['id']}/messages",
            headers=write_headers(),
            json={
                "request_id": "e2e-stage45-0003",
                "text": "Wait",
                "file_ids": [],
                "transcripts": {},
            },
        )
        assert slow.status == 202, await slow.text()
        await asyncio.sleep(0.2)
        stop = await client.post(
            f"{base}/api/v1/threads/{thread['id']}/stop",
            headers=write_headers(),
            json={},
        )
        assert stop.status == 200 and (await stop.json())["stopped"] is True
        await asyncio.sleep(0.4)
        async with client.get(
            f"{base}/api/v1/threads/{thread['id']}/state", headers=headers
        ) as response:
            snapshot = await response.json()
        assert snapshot["run"]["state"] == "cancelled"
        report("run.stopped", run=snapshot["run"]["id"])

        archive = await client.patch(
            f"{base}/api/v1/threads/{thread['id']}",
            headers=write_headers(),
            json={"archived": True},
        )
        assert archive.status == 200 and (await archive.json())["archived"] is True
        blocked = await client.post(
            f"{base}/api/v1/threads/{thread['id']}/messages",
            headers=write_headers(),
            json={
                "request_id": "e2e-stage45-0004",
                "text": "Nope",
                "file_ids": [],
                "transcripts": {},
            },
        )
        assert blocked.status == 400
        report("thread.archived", send_status=blocked.status)

        extra = await client.post(
            f"{base}/api/v1/threads",
            headers=write_headers(),
            json={"title": "Delete me", "project_id": None},
        )
        assert extra.status == 201
        extra_thread = await extra.json()
        deleted = await client.delete(
            f"{base}/api/v1/threads/{extra_thread['id']}", headers=write_headers()
        )
        assert deleted.status == 200, await deleted.text()
        missing = await client.get(f"{base}/api/v1/threads/{extra_thread['id']}", headers=headers)
        assert missing.status == 404
        report("thread.deleted")

        project = await client.post(
            f"{base}/api/v1/projects",
            headers=write_headers(),
            json={"name": "Web project", "emoji": "🌿", "instructions": "Keep it short"},
        )
        assert project.status == 201, await project.text()
        created_project = await project.json()
        assert created_project["emoji"] == "🌿"
        assert created_project["name"] == "Web project"
        listed = await client.get(f"{base}/api/v1/threads", headers=headers)
        assert any(
            item["project_id"] == created_project["id"] for item in (await listed.json())["threads"]
        )
        report("project.created", project_id=created_project["id"])

        project_url = f"{base}/api/v1/projects/{created_project['id']}"
        edited = await client.patch(
            project_url,
            headers=write_headers(),
            json={
                "name": "Edited project",
                "emoji": "💻",
                "instructions": "New instructions",
                "revision": created_project["revision"],
            },
        )
        assert edited.status == 200, await edited.text()
        saved = await edited.json()
        assert saved["name"] == "Edited project" and saved["emoji"] == "💻"
        assert saved["instructions"] == "New instructions"
        stale = await client.patch(
            project_url,
            headers=write_headers(),
            json={
                "name": "Stale overwrite",
                "emoji": "☁️",
                "instructions": "",
                "revision": created_project["revision"],
            },
        )
        assert stale.status == 409
        hidden = await client.patch(
            f"{base}/api/v1/projects/missing",
            headers=write_headers(),
            json={"name": "No access", "emoji": "☁️", "instructions": "", "revision": 1},
        )
        assert hidden.status == 404
        report("project.edited", stale_status=stale.status, missing_status=hidden.status)

    artifact = {
        "version": 1,
        "status": "passed",
        "steps": steps,
        "counts": {"steps": len(steps), "sse_events": len(seen)},
    }
    Path("docs/web-stage45-e2e.json").write_text(json.dumps(artifact, indent=2) + "\n")
    print(json.dumps(artifact, indent=2))
    await app_runner.cleanup()
    await database.close()


if __name__ == "__main__":
    asyncio.run(main())
