import base64
import hashlib
import io
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
import structlog
from aiogram.types import Message, User
from PIL import Image

from skye.config import Settings
from skye.conversations import ConversationService
from skye.db import Database
from skye.memory import MemoryService
from skye.models import ChatSettings, RequestContext, Scope
from skye.moderation import (
    BLOCKED,
    FULL_CONTEXT_WINDOW_BYTES,
    POLICY,
    UNAVAILABLE,
    ModerationService,
    chunks,
)
from skye.runtime import AgentRuntime, RunOutput
from skye.telegram import TelegramApp
from skye.ui import MODEL_PROVIDER_ICONS, Icon, decorate_keyboard


def config(**extra: Any) -> Settings:
    return Settings(
        telegram_bot_token="test",
        openrouter_api_key="sk-or-test",
        skye_owner_ids="1",
        _env_file=None,
        **extra,
    )


def test_requested_defaults() -> None:
    settings = config()
    assert settings.skye_default_model == "deepseek/deepseek-v4.1-flash-1017"
    assert len(settings.skye_text_models) == 8
    assert len(settings.skye_image_models) == 2
    assert settings.skye_transcription_model == "mistralai/voxtral-small-transcribe-3-0"
    assert settings.skye_speech_model == "mistralai/voxtral-mini-tts-3-0"
    assert not settings.images_on_fal and not settings.audio_on_local


async def test_per_user_models_keep_chat_context(tmp_path: Path) -> None:
    settings = config()
    db = Database(tmp_path / "test.db", settings.skye_default_model, "medium")
    await db.open()
    try:
        conversations = ConversationService(db)
        runtime = AgentRuntime(settings, conversations, MemoryService(db), "Skye")
        run_stream = AsyncMock(return_value=RunOutput("ok", ()))
        runtime._run_stream = run_stream
        await db.set_model_preference(1, "text", "openai/gpt-6.1-sol")
        await db.set_model_preference(1, "image", "openai/gpt-image-2.6-sunburst")
        await db.set_model_preference(2, "text", "anthropic/claude-haiku-5.5")
        # Obsolete shared model settings must not override personal choices.
        await db.set_model(Scope("chat", -100), "obsolete")
        shared = ChatSettings("obsolete", "medium", memory_enabled=False)
        for user in (1, 2, 3):
            await runtime.run(
                RequestContext(-100, "supergroup", user), shared, "hello", AsyncMock()
            )
        assert [call.args[0].model for call in run_stream.call_args_list] == [
            "openai/gpt-6.1-sol",
            "anthropic/claude-haiku-5.5",
            settings.skye_default_model,
        ]
        assert len({call.args[2] for call in run_stream.call_args_list}) == 1
        assert (await db.model_preferences(1))[1] == "openai/gpt-image-2.6-sunburst"
        assert (await db.model_preferences(2))[1] is None
        await db.set_model_preference(1, "text", "removed/model")
        await runtime.run(RequestContext(-100, "supergroup", 1), shared, "hi", AsyncMock())
        assert run_stream.call_args.args[0].model == settings.skye_default_model
    finally:
        await db.close()


@pytest.mark.parametrize(
    "mode", ["allow", "block", "refusal", "missing", "nan", "http", "truncated"]
)
async def test_moderation_contract(mode: str) -> None:
    calls: list[dict[str, Any]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        if request.url.path.endswith("extractions"):
            return httpx.Response(
                200,
                json={
                    "answers": {"requested_action": {"type": "text", "value": None}},
                    "truncated": mode == "truncated",
                },
            )
        if mode == "http":
            return httpx.Response(503)
        answers = {key: {"type": "noul", "noul": 0.01} for key in POLICY}
        if mode == "block":
            answers["violence"]["noul"] = 0.9
        if mode == "refusal":
            answers["violence"] = {"type": "refusal"}
        if mode == "missing":
            del answers["violence"]
        if mode == "nan":
            answers["violence"]["noul"] = "NaN"
        return httpx.Response(200, json={"answers": answers})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        result = await ModerationService(config(), client).check("the original request")
    assert result == (None if mode == "allow" else BLOCKED if mode == "block" else UNAVAILABLE)
    if mode != "truncated":
        assert "the original request" in calls[-1]["state"][0]
        assert calls[-1]["model"] == "cloudflare/clef"
    assert calls[0]["model"] == "cloudflare/clairic"


def test_moderation_windows_cover_multilingual_tail() -> None:
    text = "привет 🌍 " * 700 + "UNSAFE TAIL"
    windows = chunks(text, max_bytes=1200)
    assert all(len(window.encode()) <= 1800 for window in windows)
    assert windows[-1].endswith("UNSAFE TAIL")
    assert all(text[index : index + 20] in "\n".join(windows) for index in range(0, len(text), 20))


@pytest.mark.parametrize("repeats", [150, 750])
async def test_moderation_uses_provider_sized_windows_without_dropping_context(
    repeats: int,
) -> None:
    text = (
        '<recent_group_context format="json" trust="untrusted">\n'
        + "Новости и история группы 🌍. " * repeats
        + "\n</recent_group_context>\n<current_message>Check the tail.</current_message>"
    )
    calls: list[dict[str, Any]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        answers = (
            {"requested_action": {"type": "text", "value": None}}
            if request.url.path.endswith("extractions")
            else {key: {"type": "noul", "noul": 0.01} for key in POLICY}
        )
        return httpx.Response(200, json={"answers": answers})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with structlog.contextvars.bound_contextvars(run_id="test-moderation-turn"):
            result = await ModerationService(config(), client).check(text)

    windows = chunks(text, max_bytes=FULL_CONTEXT_WINDOW_BYTES)
    assert result is None
    assert len(calls) == 2 * len(windows)
    assert [body["state"] for body in calls[::2]] == windows
    for window, body in zip(windows, calls[1::2], strict=True):
        assert window in body["state"][0]
        assert "provider" not in body
    assert "Check the tail." in calls[-1]["state"][0]
    assert all(body["session_id"] == "skye:test-moderation-turn" for body in calls)
    if repeats == 150:
        assert len(chunks(text, max_bytes=1200)) > 5
        assert len(calls) == 2


@pytest.mark.parametrize(("repeats", "image_count"), [(0, 1), (200, 5), (900, 5)])
async def test_moderation_groups_images_without_multiplying_extractions(
    repeats: int, image_count: int
) -> None:
    text = "Describe this blue square. " + "История группы 🌍. " * repeats
    image = Image.new("RGB", (128, 128), "blue")
    data = io.BytesIO()
    image.save(data, "PNG")
    url = "data:image/png;base64," + base64.b64encode(data.getvalue()).decode()
    calls: list[dict[str, Any]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        answers = (
            {"requested_action": {"type": "text", "value": None}}
            if request.url.path.endswith("extractions")
            else {key: {"type": "noul", "noul": 0.01} for key in POLICY}
        )
        return httpx.Response(200, json={"answers": answers})

    value = [
        {
            "content": [
                {"type": "input_text", "text": text},
                *[{"type": "input_image", "image_url": url} for _ in range(image_count)],
            ]
        }
    ]
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        assert await ModerationService(config(), client).check(value) is None
    vision = [body for body in calls if isinstance(body["state"], list) and len(body["state"]) > 1]
    windows = chunks(text)
    assert len(vision) == len(windows) * ((image_count + 3) // 4)
    assert sum(len(body["state"]) - 1 for body in vision) == len(windows) * image_count
    for body in vision:
        assert "provider" not in body
        assert len(body["state"][0].encode()) <= FULL_CONTEXT_WINDOW_BYTES + 1000
    if repeats == 0:
        assert len(calls) == 2
    else:
        extractions = [body for body in calls if "fields" in body]
        assert [body["state"] for body in extractions] == windows
        assert len(calls) == len(windows) + len(vision)


async def test_block_stops_before_model_and_history_write(tmp_path: Path) -> None:
    settings = config()
    db = Database(tmp_path / "blocked.db", settings.skye_default_model, "medium")
    await db.open()
    try:
        moderation = AsyncMock()
        moderation.check.return_value = BLOCKED
        runtime = AgentRuntime(
            settings, ConversationService(db), MemoryService(db), "Skye", moderation=moderation
        )
        stream = AsyncMock()
        runtime._run_stream = stream
        reply = AsyncMock()
        output = await runtime.run(
            RequestContext(1, "private", 1),
            ChatSettings(settings.skye_default_model, "medium"),
            "unsafe request",
            AsyncMock(),
            on_reply=reply,
        )
        assert output.text == BLOCKED and output.usage_tokens == 0
        stream.assert_not_called()
        reply.assert_awaited_once_with(BLOCKED, None)
        assert await db.session_items("telegram:1:0") == []
    finally:
        await db.close()


async def test_picker_is_bound_to_the_user_not_group_administrators() -> None:
    app = object.__new__(TelegramApp)
    app.config = config()
    app.database = AsyncMock()
    app.access = AsyncMock()
    app.access.allowed.return_value = True
    app._show_models = AsyncMock()
    message = Message.model_validate(
        {
            "message_id": 7,
            "date": 1,
            "chat": {"id": -100, "type": "supergroup"},
            "from": {"id": 42, "is_bot": True, "first_name": "Skye"},
        }
    )
    token = hashlib.sha256(b"openai/gpt-6.1-sol").hexdigest()[:12]
    callback = AsyncMock()
    callback.message = message
    callback.from_user = User(id=2, is_bot=False, first_name="Second member")
    callback.data = f"pick:1:text:{token}"
    await app.models_callback(callback)
    app.database.set_model_preference.assert_not_called()
    callback.answer.assert_awaited_once_with(
        "Open /models to choose your own model.", show_alert=True
    )
    callback.answer.reset_mock()
    callback.data = f"pick:2:text:{token}"
    await app.models_callback(callback)
    app.database.set_model_preference.assert_awaited_once_with(2, "text", "openai/gpt-6.1-sol")


@pytest.mark.parametrize("kind", ["image", "text"])
async def test_picker_has_brief_copy_persistent_tabs_and_logo_buttons(kind: str) -> None:
    app = object.__new__(TelegramApp)
    app.config = config()
    app.database = AsyncMock()
    app.database.model_preferences.return_value = (None, None)
    app.rich = AsyncMock()
    app.picker_prices = AsyncMock()
    models = app.config.skye_image_models if kind == "image" else app.config.skye_text_models
    app.picker_prices.labels.return_value = ["$1/1M tokens"] * len(models)
    message = Message.model_validate(
        {
            "message_id": 7,
            "date": 1,
            "chat": {"id": -100, "type": "supergroup"},
        }
    )
    await app._show_models(message, RequestContext(-100, "supergroup", 2), kind, edit=True)

    call = app.rich.edit.call_args
    body = call.args[1]
    assert [block.text for block in body.blocks] == [
        "Models",
        "Choose a model for text or images.",
    ]
    keyboard = decorate_keyboard(call.kwargs["reply_markup"])
    rows = keyboard.inline_keyboard
    assert [button.text for button in rows[0]] == ["Image", "Text"]
    assert [button.style for button in rows[0]] == (
        ["success", None] if kind == "image" else [None, "success"]
    )
    assert [button.callback_data for button in rows[0]] == [
        "pick:2:image:open",
        "pick:2:text:open",
    ]
    assert [(button.text, button.icon_custom_emoji_id) for button in rows[1]] == [
        ("Back", Icon.BACK)
    ]
    assert rows[1][0].callback_data == "settings:back"
    assert len(rows) == 2 + len(models)
    for model, row in zip(models, rows[2:], strict=True):
        button = row[0]
        assert model.name in button.text
        assert model.tier in button.text
        assert "$1/1M tokens" in button.text
        assert button.icon_custom_emoji_id == MODEL_PROVIDER_ICONS.get(model.id.partition("/")[0])
        assert len(button.callback_data.encode()) <= 64


@pytest.mark.parametrize(
    "overrides",
    [
        {"skye_provider_base_url": "https://api.openai.com/v1"},
        {"skye_audio_provider": "local"},
        {"skye_image_provider": "fal", "skye_fal_key": "test"},
    ],
)
def test_production_rejects_other_model_backends(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        config(**overrides).require_openrouter()
