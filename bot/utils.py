import asyncio
import io

import aiohttp
import numpy as np
from PIL import Image

from bot.core.config import Region

# ============================================================
# НАСТРОЙКИ КАРТЫ
# ============================================================
WIDTH = 2714
HEIGHT = 1256
CHANNELS = 4

# Размеры холста
CANVAS_WIDTH = 1701  # 1357 + 4 + 340
CANVAS_HEIGHT = 628

SNAPSHOT_URL = "https://pr.altarus.top/world/snapshot"
CANVAS_SNAPSHOT_URL = "https://pr.altarus.top/canvas/snapshot"
TERRAIN_URL = "https://pr.altarus.top/realistic-map.jpg"
NEPE_MAP_PATH = "./bot/assets/map_nepe.jpg"
WATER_COLOR = np.array([91, 155, 213], dtype=np.float32)
TERRAIN_OPACITY = 0.80
DARK_RELIEF_OPACITY = 0.50
SCALE_FACTOR = 2


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
        0.299 * terrain[:, :, 0] + 0.587 * terrain[:, :, 1] + 0.114 * terrain[:, :, 2]
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
    result = (
        result * (1 - light_alpha[:, :, None]) + light_overlay * light_alpha[:, :, None]
    )
    return np.clip(result, 0, 255)


def create_player_layer(
    snapshot_bytes: bytes,
    width: int = WIDTH,
    height: int = HEIGHT,
    is_canvas: bool = False,
) -> Image.Image:
    MAIN_WIDTH = 2714
    if is_canvas:
        MAIN_WIDTH = 1357

    VIP_WIDTH = 340

    main_size = MAIN_WIDTH * height * CHANNELS
    vip_size = VIP_WIDTH * height * CHANNELS

    if len(snapshot_bytes) < main_size:
        raise ValueError(f"Неверный размер snapshot: {len(snapshot_bytes)} байт.")

    # ---------- Основной холст ----------
    main = np.frombuffer(snapshot_bytes[:main_size], dtype=np.uint8).reshape(
        (height, MAIN_WIDTH, CHANNELS)
    )

    # ---------- VIP холст ----------
    vip = None
    if len(snapshot_bytes) >= main_size + vip_size and width > MAIN_WIDTH:
        vip = np.frombuffer(
            snapshot_bytes[main_size : main_size + vip_size], dtype=np.uint8
        ).reshape((height, VIP_WIDTH, CHANNELS))

    # ---------- Сборка пикселей с точным расчетом разделителя ----------
    if vip is not None and width > MAIN_WIDTH:
        separator_width = width - MAIN_WIDTH - VIP_WIDTH
        if separator_width > 0:
            separator = np.zeros((height, separator_width, CHANNELS), dtype=np.uint8)
            separator[:, :, 0] = 0  # Blue
            separator[:, :, 1] = 215  # Green
            separator[:, :, 2] = 255  # Red (Золотая полоса)
            separator[:, :, 3] = 255  # Alpha
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


def render_region_map(
    terrain: np.ndarray, snapshot_bytes: bytes, region: Region
) -> bytes:
    world = create_terrain_overlay(terrain)
    player_layer = create_player_layer(snapshot_bytes, WIDTH, HEIGHT)
    world_image = Image.fromarray(world.astype(np.uint8), mode="RGB").convert("RGBA")

    # Прямое альфа-наложение слоя игроков на текстуру голубой воды с рельефом
    final_image = Image.alpha_composite(world_image, player_layer).convert("RGB")

    x_min, y_min, x_max, y_max = region.coords
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
    canvas_image = create_player_layer(
        snapshot_bytes, CANVAS_WIDTH, CANVAS_HEIGHT, is_canvas=True
    )

    resized_image = canvas_image.resize(
        (CANVAS_WIDTH * SCALE_FACTOR, CANVAS_HEIGHT * SCALE_FACTOR),
        Image.Resampling.NEAREST,
    )

    output = io.BytesIO()
    resized_image.save(output, format="PNG")
    return output.getvalue()


async def get_map_region_jpeg(region: Region) -> bytes:
    timeout = aiohttp.ClientTimeout(total=30)
    headers = {"User-Agent": "Mozilla/5.0"}
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        terrain_task = load_terrain(session)
        snapshot_task = fetch_bytes(session, SNAPSHOT_URL)
        terrain, snapshot_bytes = await asyncio.gather(terrain_task, snapshot_task)

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, render_region_map, terrain, snapshot_bytes, region
    )


async def get_canvas_png() -> bytes:
    timeout = aiohttp.ClientTimeout(total=30)
    headers = {"User-Agent": "Mozilla/5.0"}
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        snapshot_bytes = await fetch_bytes(session, CANVAS_SNAPSHOT_URL)

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, render_canvas_map, snapshot_bytes)
