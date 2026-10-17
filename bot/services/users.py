from typing import NamedTuple

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import BanModel, UserModel


async def add_user(
    session: AsyncSession, user_id: int, is_owner: bool | None = False
) -> None:
    """Add a new user to the database."""
    new_user = UserModel(id=user_id, is_owner=is_owner)

    session.add(new_user)
    await session.commit()


async def get_user(session: AsyncSession, user_id: int) -> UserModel | None:
    """Returns user's object from the database."""
    query = select(UserModel).filter_by(id=user_id).limit(1)

    result = await session.execute(query)

    user = result.scalar_one_or_none()
    return user


class UserStatus(NamedTuple):
    exists: bool
    is_banned: bool
    ban_reason: str | None


async def get_user_status(session: AsyncSession, user_id: int) -> UserStatus:
    """
    Checks if the user is in the database or is banned (returns reason if so).
    """
    stmt = (
        select(
            UserModel.id.is_not(None).label("exists"),
            BanModel.user_id.is_not(None).label("is_banned"),
            BanModel.reason,
        )
        .select_from(BanModel)
        .outerjoin(
            UserModel,
            UserModel.id == BanModel.user_id,
        )
        .where(BanModel.user_id == user_id)
    )

    row = (await session.execute(stmt)).one_or_none()

    if row is not None:
        return UserStatus(
            exists=row.exists,
            is_banned=row.is_banned,
            ban_reason=row.reason
        )

    user = await session.get(UserModel, user_id)
    return UserStatus(
        exists=user is not None,
        is_banned=False,
        ban_reason=None
    )


async def ban_user(
    session: AsyncSession, user_id: int, reason: str | None = None
) -> None:
    new_ban = BanModel(user_id=user_id, reason=reason)

    session.add(new_ban)
    await session.commit()


async def unban_user(
    session: AsyncSession,
    user_id: int,
) -> None:
    stmt = delete(BanModel).where(
        BanModel.user_id == user_id,
    )
    await session.execute(stmt)
    await session.commit()


async def remove_user(session: AsyncSession, user_id: int) -> None:
    """Removes user from the database."""
    query = delete(UserModel).where(UserModel.id == user_id)
    await session.execute(query)
    await session.commit()
