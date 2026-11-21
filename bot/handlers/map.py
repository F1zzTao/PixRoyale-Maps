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

from bot.core.config import Region, settings
from bot.keyboards.play import play_button
from bot.services.map_meta import MapMeta, get_map_meta
from bot.utils import get_map_region_jpeg

router = Router(name="map")


def find_region(text: str, aliases: dict) -> str | None:
    for alias, region_id in aliases.items():
        if alias in text:
            return region_id
    return None


def resolve_map_region(text: str, meta: MapMeta) -> tuple[str, Region]:
    """Resolve user query to a (filename_stem, Region) pair for the active map."""
    if meta.map_id != "world":
        return meta.map_id, Region(meta.name_ru, (0, 0, meta.width, meta.height))

    region_key_name = find_region(text, settings.REGION_ALIASES) or "world"
    if region_key_name == "world":
        return "world", Region("Весь мир", (0, 0, meta.width, meta.height))

    region = settings.REGIONS.get(region_key_name)
    if region is None:
        return "world", Region("Весь мир", (0, 0, meta.width, meta.height))
    return region_key_name, region


@router.message(
    or_f(Command("maps", "карты"), F.text.lower().in_(["карты", "список карт"]))
)
async def list_maps_handler(message: Message):
    """Показывает список доступных карт"""
    try:
        meta = await get_map_meta()
    except Exception as e:  # noqa: BLE001
        logger.exception(f"Failed to fetch map metadata: {e}")
        await message.answer("Не удалось получить список карт.")
        return

    maps_list = "\n".join([f"• {region.name}" for region in settings.REGIONS.values()])

    if meta.map_id == "world":
        text = f"🗺 **Доступные карты:**\n{maps_list}\n\n🎨 **Холст** (`/canvas`)"
    else:
        text = (
            f"🗺 **Текущая карта:** {meta.name_ru} (`/map`)\n"
            "Регионы _(будут доступны только на карте мира)_:\n"
            f"{maps_list}\n\n"
            "🎨 **Холст** (`/canvas`)"
        )
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
        if not os.path.exists(settings.NEPE_MAP_PATH):
            logger.error("Nepe image was not found")
            return

        photo = FSInputFile(settings.NEPE_MAP_PATH)
        await message.answer_photo(
            photo=photo,
            caption="🗺 Карта: **Непе**",
            parse_mode="Markdown",
            reply_markup=play_button(),
        )
        return

    try:
        meta = await get_map_meta()
    except Exception as e:  # noqa: BLE001
        logger.exception(f"Failed to fetch map metadata: {e}")
        await message.answer("Не удалось получить карту.")
        return

    region_key_name, region = resolve_map_region(text, meta)
    is_world = meta.map_id == "world"
    status_label = f"Рендерю регион: **{region.name}**..." if is_world else f"Рендерю карту: **{region.name}**..."
    caption_label = f"🗺 Карта региона: **{region.name}**" if is_world else f"🗺 Карта: **{region.name}**"

    status_message = await message.answer(status_label, parse_mode="Markdown")
    try:
        jpeg_data = await get_map_region_jpeg(region, meta)
        current_meta = await get_map_meta()
        if current_meta.map_id != meta.map_id:
            region_key_name, region = resolve_map_region(text, current_meta)
            caption_label = (
                f"🗺 Карта региона: **{region.name}**"
                if current_meta.map_id == "world"
                else f"🗺 Карта: **{region.name}**"
            )
        file = BufferedInputFile(jpeg_data, filename=f"{region_key_name}.jpg")

        await status_message.edit_media(
            media=InputMediaPhoto(
                media=file,
                caption=caption_label,
                parse_mode="Markdown",
            ),
            reply_markup=play_button(),
        )
    except Exception as e:  # noqa: BLE001
        logger.exception(f"Failed to get map: {e}")
        await status_message.edit_text("Не удалось получить карту.")


@router.message(
    or_f(
        Command("play", "game", "игра", "ссылка", "link"),
        F.text.lower().in_(["игра", "играть", "play", "game", "ссылка", "link"]),
    )
)
async def play_handler(message: Message):
    """Показывает кнопку для запуска игры"""
    await message.answer("Игра:", reply_markup=play_button())

