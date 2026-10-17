from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aiogram import BaseMiddleware
from aiogram.types import Message
from loguru import logger

from bot.services.users import add_user, get_user_status

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from aiogram.types import TelegramObject
    from sqlalchemy.ext.asyncio import AsyncSession


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)

        session: AsyncSession = data["session"]
        message: Message = event
        user = message.from_user

        if not user:
            return await handler(event, data)

        user_status = await get_user_status(session, user.id)

        if user_status.is_banned:
            return await event.answer(f"banned, reason: {user_status.ban_reason}")

        if user_status.exists:
            return await handler(event, data)

        logger.info(f"new user registration | user_id: {user.id} | message: {message.text}")

        await add_user(session=session, user_id=user.id)

        return await handler(event, data)