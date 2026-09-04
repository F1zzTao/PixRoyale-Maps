import asyncio

from aiogram import Router
from loguru import logger

from bot.core.loader import bot, dp
from bot.handlers import get_handlers_router
from bot.keyboards.default_commands import remove_default_commands, set_default_commands

router = Router()

async def on_startup() -> None:
    logger.info("Bot starting...")

    dp.include_router(get_handlers_router())

    await set_default_commands(bot)

    bot_info = await bot.get_me()

    logger.info(f"Name     - {bot_info.full_name}")
    logger.info(f"Username - @{bot_info.username}")
    logger.info(f"ID       - {bot_info.id}")

    logger.info("Bot started")


async def on_shutdown() -> None:
    logger.info("Bot stopping...")

    await remove_default_commands(bot)

    await bot.session.close()

    logger.info("Bot stopped")


async def main():
    logger.add(
        "logs/telegram_bot.log",
        level="DEBUG",
        format="{time} | {level} | {module}:{function}:{line} | {message}",
        rotation="100 KB",
        compression="zip",
    )

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
