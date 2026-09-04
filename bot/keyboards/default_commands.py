from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram.types import BotCommand, BotCommandScopeDefault

if TYPE_CHECKING:
    from aiogram import Bot

users_commands: dict[str, dict[str, str]] = {
    "en": {
        "maps": "Full map list",
        "canvas": "Canvas",
        "view_map": "World map",
    },
    "uk": {
        "maps": "Full map list",
        "canvas": "Canvas",
        "view_map": "World map",
    },
    "ru": {
        "maps": "Список всех доступных карт",
        "canvas": "Холст",
        "view_map": "Вся карта мира",
    },
}

async def set_default_commands(bot: Bot) -> None:
    await remove_default_commands(bot)

    for language_code, commands in users_commands.items():
        await bot.set_my_commands(
            [BotCommand(command=command, description=description) for command, description in commands.items()],
            scope=BotCommandScopeDefault(),
            language_code=language_code,
        )


async def remove_default_commands(bot: Bot) -> None:
    await bot.delete_my_commands(scope=BotCommandScopeDefault())
