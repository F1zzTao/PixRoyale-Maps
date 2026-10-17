from aiogram import F, Router
from aiogram.types import (
    Message,
)

from bot.database.database import sessionmaker
from bot.services.users import ban_user, get_user, unban_user

router = Router(name="admin")


async def resolve_target(
    message: Message,
) -> tuple[int | None, str | None]:
    text = message.text or ""
    parts_newline = text.split("\n", maxsplit=1)

    parts = parts_newline[0].split(maxsplit=1)
    user_id_raw = parts[1].strip() if len(parts) > 1 else ""

    reason = parts_newline[1].strip() if len(parts_newline) > 1 else None

    # Reply to a user's message
    if message.reply_to_message:
        target = message.reply_to_message.from_user
        if target is not None:
            return target.id, reason

    # Explicit Telegram user id
    if user_id_raw.isdigit():
        return int(user_id_raw), reason

    return None, reason


@router.message(F.text.lower().startswith("бан"))
async def ban_handler(message: Message):
    if not message.from_user:
        return

    async with sessionmaker() as session:
        user = await get_user(session, message.from_user.id)
        if not user or not user.is_owner:
            return

        target_id, reason = await resolve_target(message)

        if target_id is None:
            await message.reply(
                "Не удалось определить пользователя. "
                "Ответьте на его сообщение или укажите @username "
                "пользователя, который есть в базе."
            )
            return

        if message.from_user and target_id == message.from_user.id:
            await message.reply("Нельзя забанить самого себя.")
            return

        await ban_user(session, target_id, reason=reason)

    await message.reply(
        f"Пользователь {target_id} забанен."
        + (f"\nПричина: {reason}" if reason else "")
    )


@router.message(F.text.lower().startswith("разбан"))
async def unban_handler(message: Message):
    if not message.from_user:
        return

    async with sessionmaker() as session:
        user = await get_user(session, message.from_user.id)
        if not user or not user.is_owner:
            return

        target_id, _ = await resolve_target(message)

        if target_id is None:
            await message.reply(
                "Не удалось определить пользователя. "
                "Ответьте на его сообщение или укажите @username "
                "пользователя, который есть в базе."
            )
            return

        await unban_user(session, target_id)

    await message.reply(
        f"Если пользователь {target_id} был забанен, теперь он разбанен."
    )
