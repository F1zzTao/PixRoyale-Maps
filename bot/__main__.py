import asyncio
import io
import logging
import os

import aiohttp
import numpy as np
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, or_f
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
    BufferedInputFile,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
)
from dotenv import load_dotenv
from PIL import Image

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ============================================================
# НАСТРОЙКИ КАРТЫ
# ============================================================
WIDTH = 2714
HEIGHT = 1256
CHANNELS = 4

# Размеры холста
CANVAS_WIDTH = 1701      # 1357 + 4 + 340
CANVAS_HEIGHT = 628

SNAPSHOT_URL = "https://pr.altarus.top/world/snapshot"
CANVAS_SNAPSHOT_URL = "https://pr.altarus.top/canvas/snapshot"
TERRAIN_URL = "https://pr.altarus.top/realistic-map.jpg"
ANARCHY_MAP_PATH = "anarchy.png"
WATER_COLOR = np.array([91, 155, 213], dtype=np.float32)
TERRAIN_OPACITY = 0.80
DARK_RELIEF_OPACITY = 0.50
SCALE_FACTOR = 2

# ============================================================
# КООРДИНАТЫ РЕГИОНОВ
# ============================================================
REGIONS = {
    "world": (0, 0, 2714, 1256),
    "sa": (0, 0, 1040, 860),
    "ya": (280, 560, 960, 1256),
    "eurasia": (760, 0, 2714, 860),
    "europe": (1030, 40, 1540, 440),
    "asia": (1440, 40, 2332, 760),
    "africa": (960, 300, 1720, 1090),
    "aus": (1860, 700, 2714, 1220),
    "kishka": (1120, 626, 1150, 700),
    "canada": (186, 90, 780, 380),
    "usa": (8, 120, 642, 502),
    "russia": (1280, 64, 2332, 348),
    "kazakhstan": (1458, 242, 1776, 364),
    "shri-lanka": (1784, 640, 1810, 690),
    "ukraine": (1294, 258, 1436, 330),
    "bangladesh": (1842, 490, 1892, 544),
    "china": (1696, 256, 2134, 550),
    "india": (1666, 408, 1930, 666),
    "brasil": (502, 670, 860, 1050),
    "israel": (1390, 414, 1434, 484),
}

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

router = Router()

# ============================================================
# КНОПКА ИГРЫ
# ============================================================
def get_play_button():
    """Кнопка для запуска игры"""
    button = InlineKeyboardButton(
        text="🎮 Играть в PixRoyale",
        url="https://t.me/PixRoyaleBot?startapp"
    )
    return InlineKeyboardMarkup(inline_keyboard=[[button]])


# ============================================================
# АСИНХРОННАЯ ЗАГРУЗКА РЕСУРСОВ
# ============================================================
async def fetch_bytes(session: aiohttp.ClientSession, url: str) -> bytes:
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.read()


async def load_terrain(session: aiohttp.ClientSession) -> np.ndarray:
    terrain_bytes = await fetch_bytes(session, TERRAIN_URL)
    terrain_image = Image.open(io.BytesIO(terrain_bytes)).convert("RGB")
    if terrain_image.size != (WIDTH, HEIGHT):
        terrain_image = terrain_image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    return np.array(terrain_image).astype(np.float32)


# ============================================================
# ОБРАБОТКА ИЗОБРАЖЕНИЯ
# ============================================================
def create_terrain_overlay(terrain: np.ndarray) -> np.ndarray:
    brightness = (
        0.299 * terrain[:, :, 0]
        + 0.587 * terrain[:, :, 1]
        + 0.114 * terrain[:, :, 2]
    )
    gradient_y, gradient_x = np.gradient(brightness)
    relief_strength = np.sqrt(gradient_x**2 + gradient_y**2)
    relief_strength = relief_strength / (relief_strength.max() + 0.0001)
    light = np.clip((brightness - 150) / 105, 0, 1)
    shadow = np.clip((130 - brightness) / 130, 0, 1)
    relief = np.clip(relief_strength * 2.0, 0, 1)
    alpha = relief * TERRAIN_OPACITY + shadow * DARK_RELIEF_OPACITY * relief
    alpha = np.clip(alpha, 0, 0.75)
    light_overlay = np.ones_like(terrain) * 255.0
    light_alpha = light * relief * 0.12
    dark_layer = np.zeros_like(terrain)
    result = WATER_COLOR * (1 - alpha[:, :, None]) + dark_layer * alpha[:, :, None]
    result = result * (1 - light_alpha[:, :, None]) + light_overlay * light_alpha[:, :, None]
    return np.clip(result, 0, 255)


def create_player_layer(snapshot_bytes: bytes, width: int = WIDTH, height: int = HEIGHT, is_canvas: bool = False) -> Image.Image:
    MAIN_WIDTH = 2714
    if is_canvas:
        MAIN_WIDTH = 1357

    VIP_WIDTH = 340

    main_size = MAIN_WIDTH * HEIGHT * CHANNELS
    vip_size = VIP_WIDTH * HEIGHT * CHANNELS

    if len(snapshot_bytes) < main_size:
        raise ValueError(
            f"Неверный размер snapshot: {len(snapshot_bytes)} байт."
        )

    # ---------- Основной холст ----------
    main = np.frombuffer(
        snapshot_bytes[:main_size],
        dtype=np.uint8
    ).reshape((HEIGHT, MAIN_WIDTH, CHANNELS))

    # ---------- VIP холст ----------
    vip = None
    if len(snapshot_bytes) >= main_size + vip_size and width > MAIN_WIDTH:
        vip = np.frombuffer(
            snapshot_bytes[main_size:main_size + vip_size],
            dtype=np.uint8
        ).reshape((HEIGHT, VIP_WIDTH, CHANNELS))

    # ---------- Сборка пикселей с точным расчетом разделителя ----------
    if vip is not None and width > MAIN_WIDTH:
        separator_width = width - MAIN_WIDTH - VIP_WIDTH
        if separator_width > 0:
            separator = np.zeros((HEIGHT, separator_width, CHANNELS), dtype=np.uint8)
            separator[:, :, 0] = 0     # Blue
            separator[:, :, 1] = 215   # Green
            separator[:, :, 2] = 255   # Red (Золотая полоса)
            separator[:, :, 3] = 255   # Alpha
            pixels = np.concatenate((main, separator, vip), axis=1)
        else:
            pixels = np.concatenate((main, vip), axis=1)
    else:
        pixels = main

    # ---------- Обработка каналов RGBA ----------
    r = pixels[:, :, 2]
    g = pixels[:, :, 1]
    b = pixels[:, :, 0]
    
    if width == CANVAS_WIDTH:
        is_not_white = ~((r > 245) & (g > 245) & (b > 245))
        a = np.where(is_not_white, 255, 0).astype(np.uint8)
        rgba_array = np.dstack((r, g, b, a))
        img = Image.fromarray(rgba_array, mode="RGBA")
        background = Image.new("RGBA", img.size, (255, 255, 255, 255))
        background.paste(img, (0, 0), img)
        return background.convert("RGB")
    else:
        empty = (r == 0) & (g == 0) & (b == 0)
        alpha = np.where(empty, 0, 255).astype(np.uint8)
        rgba = np.dstack((r, g, b, alpha))
        return Image.fromarray(rgba, mode="RGBA")


def render_region_map(terrain: np.ndarray, snapshot_bytes: bytes, region_key: str = "world") -> bytes:
    world = create_terrain_overlay(terrain)
    player_layer = create_player_layer(snapshot_bytes, WIDTH, HEIGHT)
    world_image = Image.fromarray(world.astype(np.uint8), mode="RGB").convert("RGBA")
    
    # Прямое альфа-наложение слоя игроков на текстуру голубой воды с рельефом
    final_image = Image.alpha_composite(world_image, player_layer).convert("RGB")

    x_min, y_min, x_max, y_max = REGIONS.get(region_key, REGIONS["world"])
    cropped_image = final_image.crop((x_min, y_min, x_max, y_max))

    crop_w, crop_h = cropped_image.size
    resized_image = cropped_image.resize(
        (crop_w * SCALE_FACTOR, crop_h * SCALE_FACTOR),
        Image.Resampling.NEAREST,
    )

    output = io.BytesIO()
    resized_image.save(output, format="JPEG", quality=100, subsampling=0)
    return output.getvalue()


def render_canvas_map(snapshot_bytes: bytes) -> bytes:
    """Рендеринг чистого холста без подложки реалистичной карты"""
    canvas_image = create_player_layer(snapshot_bytes, CANVAS_WIDTH, CANVAS_HEIGHT, is_canvas=True)

    resized_image = canvas_image.resize(
        (CANVAS_WIDTH * SCALE_FACTOR, CANVAS_HEIGHT * SCALE_FACTOR),
        Image.Resampling.NEAREST,
    )

    output = io.BytesIO()
    resized_image.save(output, format="PNG")
    return output.getvalue()


async def get_map_region_jpeg(region_key: str = "world") -> bytes:
    timeout = aiohttp.ClientTimeout(total=30)
    headers = {"User-Agent": "Mozilla/5.0"}
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        terrain_task = load_terrain(session)
        snapshot_task = fetch_bytes(session, SNAPSHOT_URL)
        terrain, snapshot_bytes = await asyncio.gather(terrain_task, snapshot_task)

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, render_region_map, terrain, snapshot_bytes, region_key)


async def get_canvas_png() -> bytes:
    timeout = aiohttp.ClientTimeout(total=30)
    headers = {"User-Agent": "Mozilla/5.0"}
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        snapshot_bytes = await fetch_bytes(session, CANVAS_SNAPSHOT_URL)

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, render_canvas_map, snapshot_bytes)


# ============================================================
# ХЕНДЛЕРЫ
# ============================================================
@router.message(or_f(Command("maps", "карты"), F.text.lower().in_(["карты", "список карт"])))
async def list_maps_handler(message: Message):
    """Показывает список доступных карт"""
    maps_list = "\n".join([f"• {name}" for name in REGION_NAMES.values()])
    text = f"🗺 **Доступные карты:**\n\n{maps_list}\n• Холст (`/canvas`)"
    await message.answer(text, parse_mode="Markdown")


@router.message(or_f(Command("map_oi", "oi", "ои"), F.text.lower() == "карта ои"))
async def oi_map_handler(message: Message):
    await message.answer("Нет территорий!")


@router.message(or_f(Command("map_anarchy", "anarchy", "анархия"), F.text.lower() == "карта анархия"))
async def anarchy_map_handler(message: Message):
    if not os.path.exists(ANARCHY_MAP_PATH):
        await message.answer("❌ Файл `anarchy.png` не найден на сервере.", parse_mode="Markdown")
        return
    
    photo = FSInputFile(ANARCHY_MAP_PATH)
    await message.answer_photo(
        photo=photo,
        caption="🗺 Карта: **Анархия**",
        parse_mode="Markdown",
        reply_markup=get_play_button()
    )

@router.message(or_f(Command("canvas", "холст"), F.text.lower() == "холст"))
async def canvas_map_handler(message: Message):
    """Хендлер для отображения холста"""
    status_message = await message.answer("Рендерю **Холст**...", parse_mode="Markdown")
    try:
        png_data = await get_canvas_png()
        file = BufferedInputFile(png_data, filename="canvas.png")
        
        await status_message.edit_media(
            media=InputMediaPhoto(
                media=file,
                caption="🎨 **Холст**",
                parse_mode="Markdown"
            ),
            reply_markup=get_play_button()
        )
    except Exception as e:
        logging.exception("Failed to get canvas")
        await status_message.edit_text(f"Не удалось получить холст.", parse_mode="Markdown")

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
    status_message = await message.answer(f"Рендерю регион: **{region_title}**...", parse_mode="Markdown")
    try:
        jpeg_data = await get_map_region_jpeg(region)
        file = BufferedInputFile(jpeg_data, filename=f"{region}.jpg")
        
        await status_message.edit_media(
            media=InputMediaPhoto(
                media=file,
                caption=f"🗺 Карта региона: **{region_title}**",
                parse_mode="Markdown"
            ),
            reply_markup=get_play_button()
        )
    except Exception as e:
        logging.exception("Failed to get map")
        await status_message.edit_text(f"Не удалось получить карту.\n", parse_mode="Markdown")
# ============================================================
# НАСТРОЙКА КОМАНД И ЗАПУСК
# ============================================================
async def setup_commands(bot: Bot):
    commands = [
        BotCommand(command="maps", description="Список всех доступных карт"),
        BotCommand(command="canvas", description="Холст"),
        BotCommand(command="view_map", description="Вся карта мира"),
    ]
    await bot.set_my_commands(commands=commands, scope=BotCommandScopeAllPrivateChats())
    await bot.set_my_commands(commands=commands, scope=BotCommandScopeAllGroupChats())


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("Не задана переменная окружения BOT_TOKEN")
    
    logging.basicConfig(level=logging.INFO)
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    
    await setup_commands(bot)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
