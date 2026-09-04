import os

from aiogram import F, Router
from aiogram.filters import Command, or_f
from aiogram.types import (
    BufferedInputFile,
    FSInputFile,
    InputMediaPhoto,
    Message,
)
from loguru import logger

from bot.keyboards.play import play_button
from bot.utils import NEPE_MAP_PATH, get_map_region_jpeg

router = Router(name="map")

REGION_NAMES = {
    "world": "Весь мир",
    "sa": "Северная Америка",
    "ya": "Южная Америка",
    "eurasia": "Евразия",
    "africa": "Африка",
    "aus": "Австралия и Океания",
    "kishka": "Того (кишка)",
    "canada": "Канада",
    "usa": "США",
    "russia": "Россия",
    "kazakhstan": "Казахстан",
    "shri-lanka": "Шри-Ланка",
    "ukraine": "Украина",
    "bangladesh": "Бангладеш",
    "china": "Китай",
    "india": "Индия",
    "brasil": "Бразилия",
    "europe": "Европа",
    "asia": "Азия",
    "israel": "Израиль",
}

@router.message(
    or_f(Command("maps", "карты"), F.text.lower().in_(["карты", "список карт"]))
)
async def list_maps_handler(message: Message):
    """Показывает список доступных карт"""
    maps_list = "\n".join([f"• {name}" for name in REGION_NAMES.values()])
    text = f"🗺 **Доступные карты:**\n\n{maps_list}\n• Холст (`/canvas`)"
    await message.answer(text, parse_mode="Markdown")

@router.message(
    or_f(
        Command("view_map", "map", "карта"),
        Command("map_sa", "са"),
        Command("map_ya", "юа"),
        Command("map_eurasia", "евразия"),
        Command("map_africa", "африка"),
        Command("map_aus", "австралия"),
        Command("кишка", "кишки"),
        Command("канада", "canada"),
        Command("сша", "usa"),
        Command("россия", "рф", "russia"),
        Command("казахстан", "kazakhstan"),
        Command("шри-ланка", "shri-lanka"),
        Command("украина", "ukraine"),
        Command("бангладеш", "bangladesh"),
        Command("китай", "china"),
        Command("индия", "india"),
        Command("бразилия", "brasil"),
        Command("израиль", "israel"),
        F.text.lower().startswith("карта"),
    )
)
async def view_map_handler(message: Message):
    if not message.text:
        return

    text = message.text.lower().strip()

    if any(k in text for k in ["са", "северная америка"]):
        region = "sa"
    elif any(k in text for k in ["юа", "южная америка"]):
        region = "ya"
    elif "еврази" in text:
        region = "eurasia"
    elif "европ" in text:
        region = "europe"
    elif "ази" in text:
        region = "asia"
    elif "африк" in text:
        region = "africa"
    elif any(k in text for k in ["австралия", "австралии", "океания"]):
        region = "aus"
    elif any(k in text for k in ["кишк", "того"]):
        region = "kishka"
    elif "канад" in text:
        region = "canada"
    elif any(k in text for k in ["сша", "usa", "штаты", "америка"]):
        region = "usa"
    elif any(k in text for k in ["росси", "рф", "рашка"]):
        region = "russia"
    elif any(k in text for k in ["казахстан", "каз"]):
        region = "kazakhstan"
    elif any(k in text for k in ["шри-ланк", "шри ланк"]):
        region = "shri-lanka"
    elif any(k in text for k in ["украин", "укр"]):
        region = "ukraine"
    elif "бангладеш" in text:
        region = "bangladesh"
    elif any(k in text for k in ["кита", "кнр"]):
        region = "china"
    elif "инди" in text:
        region = "india"
    elif "бразили" in text:
        region = "brasil"
    elif "израил" in text:
        region = "israel"
    else:
        region = "world"

    region_title = REGION_NAMES.get(region, "Карта")
    status_message = await message.answer(
        f"Рендерю регион: **{region_title}**...", parse_mode="Markdown"
    )
    try:
        jpeg_data = await get_map_region_jpeg(region)
        file = BufferedInputFile(jpeg_data, filename=f"{region}.jpg")

        await status_message.edit_media(
            media=InputMediaPhoto(
                media=file,
                caption=f"🗺 Карта региона: **{region_title}**",
                parse_mode="Markdown",
            ),
            reply_markup=play_button(),
        )
    except Exception as e:  # noqa: BLE001
        logger.exception(f"Failed to get map: {e}")
        await status_message.edit_text("Не удалось получить карту.")


@router.message(or_f(Command("map_oi", "oi", "ои"), F.text.lower() == "карта ои"))
async def oi_map_handler(message: Message):
    await message.answer("Нет территорий!")


@router.message(
    or_f(
        Command("map_nepe", "nepe", "непе"), F.text.lower() == "карта непе"
    )
)
async def nepe_map_handler(message: Message):
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