from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    BufferedInputFile,
    Chat,
    InputRichBlockTable,
    InputRichMessage,
    Message,
    ReplyParameters,
    User,
)

from skye.artifacts import GeneratedFile
from skye.models import (
    AppConnector,
    ChatSettings,
    ConnectorSnapshot,
    CustomConnector,
    Scope,
)
from skye.rich import RichMessages


def test_output_and_content_strip_citation_tokens() -> None:
    token = "\ue200cite\ue202turn0view0\ue201"
    text = f"Paris is the capital. {token} See https://example.com/report"

    output = RichMessages.output(text)
    wrapped = RichMessages._content(text)
    already = RichMessages._content(InputRichMessage(markdown=text))

    assert output == InputRichMessage(
        markdown="Paris is the capital. See https://example.com/report"
    )
    assert wrapped == output
    assert already == output
    assert RichMessages.output(token) == InputRichMessage(markdown="Done.")
    settings = RichMessages.settings(ChatSettings(model="gpt-5.6-luna", reasoning="medium"))
    assert RichMessages._content(settings) is settings


def test_settings_menus_send_native_blocks_instead_of_markdown() -> None:
    screens = [
        RichMessages.settings(ChatSettings(model="gpt-5.6-luna", reasoning="medium")),
        RichMessages.choose_reasoning("medium"),
        RichMessages.agents((), None),
        RichMessages.access(
            (), notice=RichMessages.access_change("Allowed", Scope("chat", -1002206813481))
        ),
        RichMessages.memory([], enabled=True),
        RichMessages.memory_clear_confirm(),
        RichMessages.skill_upload_prompt(),
        RichMessages.skill_delete_confirm("basic-math"),
        RichMessages.connector_share_confirm("Gmail", "Skye Lab", sensitive=False),
        RichMessages.connector_remove_confirm("Work CRM"),
        RichMessages.connector_search_prompt(),
        RichMessages.connector_edit_prompt("name", "Work CRM"),
        RichMessages.admin_prompt("allow"),
        RichMessages.agent_name_prompt("Helper"),
        RichMessages.agent_share_link("https://t.me/bot?start=agent_1"),
        RichMessages.agent_installed("Helper", 1, hint=True),
    ]
    for message in screens:
        assert message.blocks
        assert message.markdown is None
        for block in message.blocks:
            text = getattr(block, "text", None)
            if isinstance(text, str):
                assert "**" not in text
                assert "`" not in text


def test_connectors_screen_lists_apps_and_custom_servers() -> None:
    snapshot = ConnectorSnapshot(
        (AppConnector("gmail", "Gmail", "connected", account_id="ca_1"),),
        (
            CustomConnector(
                "abc",
                1,
                "Work CRM",
                "https://user:secret@example.com/mcp?token=1",
                {"Authorization": "Bearer x"},
                True,
                "now",
                "now",
            ),
        ),
    )

    message = RichMessages.connectors(snapshot, configured=True)
    custom = RichMessages.connector_custom(snapshot.custom[0])

    assert message.blocks
    table = message.blocks[2]
    assert isinstance(table, InputRichBlockTable)
    assert table.cells[1][0].text == "Gmail"
    assert table.cells[2][0].text == "Work CRM"
    assert custom.blocks
    custom_table = custom.blocks[2]
    assert isinstance(custom_table, InputRichBlockTable)
    assert custom_table.cells[1][1].text == "https://example.com/mcp"
    assert "secret" not in custom_table.cells[1][1].text


async def test_send_documents_uploads_container_files() -> None:
    bot = AsyncMock()
    incoming = Message(
        message_id=17,
        date=0,
        chat=Chat(id=42, type="private", first_name="Alice"),
        from_user=User(id=42, is_bot=False, first_name="Alice"),
        text="Hello",
    )

    await RichMessages(bot).send_documents(
        incoming, (GeneratedFile("Архитектура.md", b"# architecture"),)
    )

    kwargs = bot.send_document.await_args.kwargs
    assert kwargs["chat_id"] == 42
    assert kwargs["disable_content_type_detection"] is True
    assert kwargs["reply_parameters"] == ReplyParameters(
        message_id=17,
        allow_sending_without_reply=True,
    )
    document = kwargs["document"]
    assert isinstance(document, BufferedInputFile)
    assert document.filename == "Архитектура.md"


async def test_send_images_uploads_each_image_as_a_photo() -> None:
    bot = AsyncMock()
    incoming = Message(
        message_id=17,
        date=0,
        chat=Chat(id=42, type="private", first_name="Alice"),
        from_user=User(id=42, is_bot=False, first_name="Alice"),
        text="Hello",
    )

    await RichMessages(bot).send_images(incoming, (b"first", b"second"))

    assert bot.send_photo.await_count == 2
    first = bot.send_photo.await_args_list[0].kwargs
    second = bot.send_photo.await_args_list[1].kwargs
    assert isinstance(first["photo"], BufferedInputFile)
    assert first["photo"].filename == "skye-1.png"
    assert second["photo"].filename == "skye-2.png"
    assert first["reply_parameters"] == ReplyParameters(
        message_id=17,
        allow_sending_without_reply=True,
    )


async def test_send_voice_uses_native_voice_and_optional_quote() -> None:
    bot = AsyncMock()
    incoming = Message(
        message_id=17,
        date=0,
        chat=Chat(id=42, type="private", first_name="Alice"),
        from_user=User(id=42, is_bot=False, first_name="Alice"),
        text="Hello",
    )

    await RichMessages(bot).send_voice(incoming, b"opus", reply_to=123)

    kwargs = bot.send_voice.await_args.kwargs
    assert kwargs["chat_id"] == 42
    assert kwargs["message_thread_id"] is None
    assert kwargs["reply_parameters"] == ReplyParameters(
        message_id=123,
        allow_sending_without_reply=True,
    )
    voice = kwargs["voice"]
    assert isinstance(voice, BufferedInputFile)
    assert voice.filename == "voice.ogg"

    await RichMessages(bot).send_voice(incoming, b"ID3mp3")
    assert bot.send_voice.await_args.kwargs["voice"].filename == "voice.mp3"


async def test_send_keeps_forum_topic_without_quoting() -> None:
    bot = AsyncMock()
    incoming = Message(
        message_id=20,
        date=0,
        chat=Chat(id=-100, type="supergroup", title="Skye Lab"),
        from_user=User(id=42, is_bot=False, first_name="Alice"),
        text="Hello",
        message_thread_id=9,
        is_topic_message=True,
    )

    await RichMessages(bot).send(incoming, "Hi.")

    kwargs = bot.send_rich_message.await_args.kwargs
    assert kwargs["message_thread_id"] == 9
    assert kwargs["reply_parameters"] is None


async def test_send_ignores_reply_only_thread_id_without_quoting() -> None:
    bot = AsyncMock()
    incoming = Message(
        message_id=21,
        date=0,
        chat=Chat(id=-100, type="supergroup", title="Skye Lab"),
        from_user=User(id=42, is_bot=False, first_name="Alice"),
        text="Hello",
        message_thread_id=19,
    )

    await RichMessages(bot).send(incoming, "Hi.")

    kwargs = bot.send_rich_message.await_args.kwargs
    assert kwargs["message_thread_id"] is None
    assert kwargs["reply_parameters"] is None


async def test_edit_ignores_unchanged_content() -> None:
    bot = AsyncMock()
    bot.edit_message_text.side_effect = TelegramBadRequest(
        method=AsyncMock(),
        message=(
            "Bad Request: message is not modified: specified new message content "
            "and reply markup are exactly the same as a current content and reply "
            "markup of the message"
        ),
    )
    incoming = Message(
        message_id=8,
        date=0,
        chat=Chat(id=-100, type="supergroup", title="Skye Lab"),
        from_user=User(id=42, is_bot=False, first_name="Alice"),
        text="Thinking…",
    )

    await RichMessages(bot).edit(incoming, "Thinking…")


async def test_edit_still_raises_other_bad_requests() -> None:
    bot = AsyncMock()
    bot.edit_message_text.side_effect = TelegramBadRequest(
        method=AsyncMock(),
        message="Bad Request: message to edit not found",
    )
    incoming = Message(
        message_id=8,
        date=0,
        chat=Chat(id=-100, type="supergroup", title="Skye Lab"),
        from_user=User(id=42, is_bot=False, first_name="Alice"),
        text="Thinking…",
    )

    with pytest.raises(TelegramBadRequest):
        await RichMessages(bot).edit(incoming, "Done.")
