from aiogram import Dispatcher

from .auth import AuthMiddleware
from .database import DatabaseMiddleware


def register_middlewares(dp: Dispatcher) -> None:
    dp.update.outer_middleware(DatabaseMiddleware())

    dp.message.middleware(AuthMiddleware())
