"""Isolated interactive web preview. Never imported by production bootstrap.

Uses the production API/stores/turn lifecycle with a deterministic local runtime.
No Telegram polling, provider clients, connectors, Docker or real billing services.
"""

from __future__ import annotations

import asyncio
import io
import json
import math
import os
import struct
import wave
import zlib
from pathlib import Path
from typing import Any
from uuid import uuid4

from aiohttp import web

from skye.config import Settings
from skye.db import Database
from skye.library import MediaLibrary
from skye.models import Scope, TelegramProject
from skye.runtime import RunEvent, RunOutput
from skye.threads import MediaReceipt, ThreadStore
from skye.turns import TurnService
from skye.web_api import create_app
from skye.web_auth import AuthStore
from skye.web_contracts import SendRequest
from skye.web_events import WebEventStore
from skye.web_media import WebMediaStore
from skye.web_turns import WebTurnRunner


class DemoAccess:
    async def allowed(self, context: object) -> bool:
        return True

    async def banned(self, user_id: int) -> bool:
        return False


class DemoQuota:
    async def complimentary(self, context: object, *, billed_user_id: int) -> bool:
        return True

    async def exhausted(self, context: object, *, billed_user_id: int) -> bool:
        return False


class DemoSparks:
    async def payer(self, context: object) -> int:
        return 1

    async def can_afford(self, user_id: int) -> bool:
        return True

    def cost_milli(self, usage: object, provider_cost_rub: float | None = None) -> int:
        return 0


class DemoAudio:
    async def transcribe(self, filename: str, data: bytes, mime: str = "") -> str:
        return "This is a local demo transcription. Can you help me plan the week?"


class DemoRuntime:
    audio = DemoAudio()

    async def run(
        self,
        context: object,
        settings: object,
        user_input: object,
        on_text: object,
        **kwargs: Any,
    ) -> RunOutput:
        text = str(user_input).lower()
        event, reply = kwargs.get("on_event"), kwargs.get("on_reply")
        tools = [("web_search", "Searching the web", "Searched the web")]
        if any(word in text for word in ("code", "python", "calculate")):
            tools.append(("execute_code", "Running code", "Ran code"))
        for name, working, done in tools:
            tool_id = uuid4().hex
            if event:
                await event(
                    RunEvent(
                        kind="tool",
                        tool_id=tool_id,
                        tool_name=name,
                        tool_label=working,
                        tool_status="running",
                    )
                )
            await asyncio.sleep(1.2)
            if event:
                await event(
                    RunEvent(
                        kind="tool",
                        tool_id=tool_id,
                        tool_name=name,
                        tool_label=done,
                        tool_status="done",
                    )
                )
        if "demo error" in text:
            raise RuntimeError("Simulated preview failure")
        if reply:
            await reply("I’ve got it. Here’s a simple place to start.")
            await asyncio.sleep(0.5)
            await reply(
                "Pick one thing for today, leave room for a break, and keep the rest for later.\n\n"
                "- Choose the next small step\n- Keep your notes in this project\n"
                "- Send me a picture or file when you need it\n\n"
                "*Local demo reply — no model or external tools were called.*"
            )
        return RunOutput("", (), sent=2)


def demo_picture(index: int) -> bytes:
    """Small deterministic PNG artwork for exercising thumbnails and image previews."""
    palettes = [
        ((30, 75, 107), (222, 180, 112), (40, 110, 115)),
        ((110, 145, 157), (245, 220, 160), (45, 75, 90)),
        ((163, 109, 85), (241, 218, 183), (78, 87, 69)),
        ((62, 78, 71), (210, 199, 157), (115, 137, 112)),
    ]
    sky, sun, hill = palettes[index % len(palettes)]
    width, height = 640, 480
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            color = sky
            if (x - 440) ** 2 + (y - 135) ** 2 < 65**2:
                color = sun
            if y > 320 - 95 * math.sin(x / 135 + index):
                color = hill
            rows.extend(color)

    def chunk(name: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(rows)))
        + chunk(b"IEND", b"")
    )


async def seed(
    database: Database,
    threads: ThreadStore,
    files: MediaLibrary,
    turns: TurnService,
    events: WebEventStore,
) -> None:
    if await database.fetch_one("SELECT id FROM threads LIMIT 1", ()):
        return
    projects = []
    for name, emoji, instructions in [
        ("Everyday", "☁️", "Keep things calm and concise. Help me focus on the next small step."),
        ("Studio", "🎨", "Help me explore ideas, references and creative work."),
        ("Learning", "🎓", "Explain clearly, with practical examples."),
    ]:
        project = await database.create_telegram_project(
            TelegramProject(
                id=uuid4().hex[:16],
                user_id=1,
                kind="custom",
                name=name,
                emoji=emoji,
                instructions=instructions,
                openai_conversation_id=None,
                created_at="",
                updated_at="",
            )
        )
        projects.append(project)
    media = WebMediaStore(database, files)
    pictures = []
    for i, name in enumerate(["Coast", "Morning", "Terrace", "Forest", "Islands", "Hills"]):
        pictures.append(await media.save(1, f"{name}.png", "image/png", demo_picture(i)))
    await media.save(1, "Weekend notes.txt", "text/plain", b"Walk by the coast. Bring a camera.")
    audio = io.BytesIO()
    with wave.open(audio, "wb") as recording:
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(8000)
        recording.writeframes(b"\0\0" * 8000)
    await media.save(1, "Voice note.wav", "audio/wav", audio.getvalue())
    for i, (title, project) in enumerate(
        [
            ("A quieter week", projects[0]),
            ("Visual references", projects[1]),
            ("Learning Python", projects[2]),
            ("Weekend plans", projects[0]),
        ]
    ):
        thread = await threads.create(1, project.id, title)
        await threads.append(
            Scope("user", 1),
            thread.record.id,
            role="user",
            origin="web",
            text="Here’s a reference I’d like to keep.",
            receipt=f"demo-user-{i}",
            media=[
                MediaReceipt(
                    source_file_id=pictures[i].record.id,
                    name=pictures[i].record.name,
                    media_type="image/png",
                    size=pictures[i].record.size,
                    availability="available",
                )
            ],
        )
        await threads.append(
            Scope("user", 1),
            thread.record.id,
            role="assistant",
            origin="web",
            text="Saved. We can come back to it whenever you like.",
            receipt=f"demo-reply-{i}",
        )
        if i == 0:
            runner = WebTurnRunner(
                database,
                DemoRuntime(),
                threads,
                turns,
                media,
                max_attachment_bytes=25 * 1024 * 1024,
            )  # type: ignore[arg-type]
            await runner.send(
                1,
                thread.record.id,
                SendRequest(request_id=uuid4().hex, text="Help me plan this week"),
            )
            await asyncio.sleep(2.2)


async def main() -> None:
    internal = os.environ["SKYE_DEV_INTERNAL_TOKEN"]
    data = Path(
        os.environ.get(
            "SKYE_DEV_DATA_DIR", str(Path(__file__).resolve().parents[1] / "web" / ".dev-data")
        )
    )
    data.mkdir(parents=True, exist_ok=True)
    database = Database(data / "preview.db", "demo-local", "low")
    await database.open()
    events = WebEventStore(database)
    threads = ThreadStore(database, events=events)
    await threads.migrate()
    files = MediaLibrary(data / "files")
    turns = TurnService(database, DemoAccess(), DemoQuota(), DemoSparks(), events=events)  # type: ignore[arg-type]
    await seed(database, threads, files, turns, events)
    config = Settings(
        _env_file=None,
        telegram_bot_token="local-demo",
        skye_owner_ids={1},
        skye_web_origin="https://skye-preview.invalid",
        skye_web_internal_token=internal,
        skye_oidc_client_id="local-demo",
        skye_oidc_client_secret="local-demo",
        skye_files_dir=data / "files",
    )
    app = create_app(
        config,
        database,
        threads,
        DemoAccess(),
        turns=turns,  # type: ignore[arg-type]
        runtime=DemoRuntime(),
        files=files,
        events=events,
    )  # type: ignore[arg-type]
    session = await AuthStore(database).issue(1)
    runner = web.AppRunner(app)
    await runner.setup()
    server = await asyncio.get_running_loop().create_server(runner.server, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    print(
        "SKYE_DEV_READY " + json.dumps({"origin": f"http://127.0.0.1:{port}", "session": session}),
        flush=True,
    )
    try:
        await asyncio.Event().wait()
    finally:
        server.close()
        await server.wait_closed()
        await runner.cleanup()
        await database.close()


if __name__ == "__main__":
    asyncio.run(main())
