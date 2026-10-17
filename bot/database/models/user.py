from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Mapped, mapped_column

from bot.database.models.base import Base, big_int_pk, created_at


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[big_int_pk]

    is_owner: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[created_at]


class BanModel(Base):
    __tablename__ = "bans"

    user_id: Mapped[big_int_pk]

    reason: Mapped[Optional[str]] = mapped_column(default=None)
    banned_at: Mapped[created_at]