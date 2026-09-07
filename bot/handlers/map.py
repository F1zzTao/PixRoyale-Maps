import os

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, or_f
from aiogram.types import (
    BufferedInputFile,
    FSInputFile,
    InputMediaPhoto,
    Message,
)
from loguru import logger

from bot.core.config import REGION_ALIASES, REGIONS
from bot.keyboards.play import play_button
from bot.utils import NEPE_MAP_PATH, get_map_region_jpeg

router = Router(name="map")


def find_region(text: str, aliases: dict) -> str | None:
    for alias, region_id in aliases.items():
        if alias in text:
            return region_id
    return None


@router.message(
    or_f(Command("maps", "карты"), F.text.lower().in_(["карты", "список карт"]))
)
async def list_maps_handler(message: Message):
    """Показывает список доступных карт"""
    maps_list = "\n".join([f"• {region.name}" for region in REGIONS.values()])
    text = f"🗺 **Доступные карты:**\n{maps_list}\n\n🎨 **Холст** (`/canvas`)"
    await message.answer(text, parse_mode="Markdown")


@router.message(
    or_f(Command(commands=["map", "карта"]), F.text.lower().startswith("карта"))
)
async def view_map_handler(message: Message, command: CommandObject | None = None):
    if not message.text:
        return

    if command and command.args:
        text = command.args
    else:
        text = " ".join(message.text.split()[1:])

    text = text.lower().strip()

    # Easter egg regions
    if "ои" in text:
        await message.answer("Нет территорий!")
        return
    elif "непе" in text:
        if not os.path.exists(NEPE_MAP_PATH):
            logger.error("Nepe image was not found")
            return

        photo = FSInputFile(NEPE_MAP_PATH)
        await message.answer_photo(
            photo=photo,
            caption="🗺 Карта: **Непе**",
            parse_mode="Markdown",
            reply_markup=play_button(),
        )
        return

    region_key_name = find_region(text, REGION_ALIASES) or "world"
    region = REGIONS.get(region_key_name)
    if not region:
        logger.error(f'Fallback region "{region_key_name}" was not found')
        await message.answer("Не удалось получить карту.")
        return

    status_message = await message.answer(
        f"Рендерю регион: **{region.name}**...", parse_mode="Markdown"
    )
    try:
        jpeg_data = await get_map_region_jpeg(region)
        file = BufferedInputFile(jpeg_data, filename=f"{region_key_name}.jpg")

        await status_message.edit_media(
            media=InputMediaPhoto(
                media=file,
                caption=f"🗺 Карта региона: **{region.name}**",
                parse_mode="Markdown",
            ),
            reply_markup=play_button(),
        )
    except Exception as e:  # noqa: BLE001
        logger.exception(f"Failed to get map: {e}")
        await status_message.edit_text("Не удалось получить карту.")
