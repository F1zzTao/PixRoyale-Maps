from aiogram import Router


def get_handlers_router() -> Router:
    from . import canvas, map

    router = Router()
    router.include_router(canvas.router)
    router.include_router(map.router)

    return router