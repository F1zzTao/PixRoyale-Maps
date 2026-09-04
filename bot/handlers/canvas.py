from aiogram import F, Router
from aiogram.filters import Command, or_f
from aiogram.types import (
    BufferedInputFile,
    InputMediaPhoto,
    Message,
)
from loguru import logger

from bot.keyboards.play import play_button
from bot.utils import get_canvas_png

router = Router(name="canvas")

@router.message(or_f(Command("canvas", "холст"), F.text.lower() == "холст"))
async def canvas_map_handler(message: Message):
    """Хендлер для отображения холста"""
    status_message = await message.answer("Рендерю **Холст**...", parse_mode="Markdown")
    try:
        png_data = await get_canvas_png()
        file = BufferedInputFile(png_data, filename="canvas.png")

        await status_message.edit_media(
            media=InputMediaPhoto(
                media=file, caption="🎨 **Холст**", parse_mode="Markdown"
            ),
            reply_markup=play_button(),
        )
    except Exception as e:  # noqa: BLE001
        logger.error(f"Failed to get canvas: {e}")
        await status_message.edit_text("Не удалось получить холст.")