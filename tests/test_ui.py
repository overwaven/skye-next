from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputRichBlockParagraph,
    InputRichBlockThinking,
    RichTextCustomEmoji,
)

from skye.ui import ACTIVITIES, Icon, activity_message, decorate_keyboard


def test_decoration_preserves_model_logos_and_selected_tab_color() -> None:
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Text",
                    callback_data="pick:1:text:open",
                    style="success",
                    icon_custom_emoji_id=Icon.MESSAGE,
                )
            ],
            [
                InlineKeyboardButton(
                    text="GPT-6.1 Sol",
                    callback_data="pick:1:text:model",
                    icon_custom_emoji_id=Icon.OPENAI,
                )
            ],
        ]
    )

    decorated = decorate_keyboard(markup)
    assert decorated.inline_keyboard[0][0].style == "success"
    assert decorated.inline_keyboard[1][0].icon_custom_emoji_id == Icon.OPENAI


def test_button_actions_override_their_feature_icon() -> None:
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Connect", callback_data="conn:link:gmail")],
            [InlineKeyboardButton(text="Disconnect", callback_data="conn:off:gmail")],
            [InlineKeyboardButton(text="Add agent", callback_data="agents:add")],
            [InlineKeyboardButton(text="Share", callback_data="agents:share:abc")],
        ]
    )

    decorated = decorate_keyboard(markup)
    icons = [button.icon_custom_emoji_id for row in decorated.inline_keyboard for button in row]

    assert icons == [Icon.UNLOCKED, Icon.LOCKED, Icon.APPS_ADD, Icon.LINK]


def test_activity_messages_use_matching_custom_emoji(monkeypatch: object) -> None:
    activity = ACTIVITIES[1]
    monkeypatch.setattr("skye.ui.secrets.choice", lambda _items: activity)  # type: ignore[attr-defined]

    draft = activity_message(draft=True)
    placeholder = activity_message(draft=False)

    assert isinstance(draft.blocks[0], InputRichBlockThinking)
    assert isinstance(placeholder.blocks[0], InputRichBlockParagraph)
    for block in (draft.blocks[0], placeholder.blocks[0]):
        assert isinstance(block.text, list)
        assert isinstance(block.text[0], RichTextCustomEmoji)
        assert block.text[0].custom_emoji_id == Icon.IMAGE
        assert block.text[1] == " Mixing colors…"


def test_project_and_emoji_rows_do_not_duplicate_their_own_icons() -> None:
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✓ ☁️ Skye", callback_data="proj:open:skye")],
            [InlineKeyboardButton(text="☁️", callback_data="proj:emo:0")],
            [InlineKeyboardButton(text="💬", callback_data="proj:icon:abc:1")],
            [InlineKeyboardButton(text="Send any emoji", callback_data="proj:any")],
        ]
    )

    decorated = decorate_keyboard(markup)
    icons = [button.icon_custom_emoji_id for row in decorated.inline_keyboard for button in row]

    assert icons == [None, None, None, Icon.IMAGE]
