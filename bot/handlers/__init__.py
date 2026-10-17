from aiogram import Router


def get_handlers_router() -> Router:
    from . import admin, canvas, map

    router = Router()
    router.include_router(admin.router)
    router.include_router(canvas.router)
    router.include_router(map.router)

    return router