from unittest.mock import AsyncMock

from aiogram.exceptions import TelegramBadRequest

from skye.telegram_activity import TelegramActivity


async def test_activity_failure_does_not_break_the_turn() -> None:
    bot = AsyncMock()
    bot.send_chat_action.side_effect = TelegramBadRequest(method="sendChatAction", message="no")

    async with TelegramActivity(bot, 7) as activity:
        await activity.show("record_voice")
