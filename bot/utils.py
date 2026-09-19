import asyncio
import io

import aiohttp
import numpy as np
from PIL import Image

from bot.core.config import Region, settings

# ============================================================
# CONSTANTS
# ============================================================

# Luminance weights (ITU-R Rec. 601 standard)
LUMINANCE_R: float = 0.299
LUMINANCE_G: float = 0.587
LUMINANCE_B: float = 0.114

# Terrain overlay parameters
LIGHT_THRESHOLD: float = 150.0       # Brightness above this → lit
LIGHT_RANGE: float = 105.0           # Softness of the light mask edge
SHADOW_THRESHOLD: float = 130.0      # Brightness below this → shadowed
SHADOW_RANGE: float = 130.0          # Softness of the shadow mask edge
RELIEF_MULTIPLIER: float = 2.0       # Amplify the gradient for more visible relief
LIGHT_OVERLAY_STRENGTH: float = 0.12 # Subtle white highlight on steep lit faces
MAX_ALPHA: float = 0.75              # Clamp for the composite alpha
EPSILON: float = 0.0001              # Avoid division by zero in normalisation

# Canvas / snapshot decoding
WHITE_THRESHOLD: int = 245           # Pixels above this are considered background
FULL_WHITE: float = 255.0            # Scalar white for screen-blend math

# Gold separator colour (in BGR byte order, as stored in the raw buffer)
_SEP_B: int = 0
_SEP_G: int = 215
_SEP_R: int = 255
_SEP_A: int = 255

# HTTP defaults
HTTP_TIMEOUT: int = 30
USER_AGENT: str = "Mozilla/5.0"


# ============================================================
# ASYNC RESOURCE LOADING
# ============================================================
async def fetch_bytes(session: aiohttp.ClientSession, url: str) -> bytes:
    """HTTP GET → raw bytes (raises on HTTP error)."""
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.read()


async def load_terrain(session: aiohttp.ClientSession) -> np.ndarray:
    """Fetch the terrain base-map and return it as a float32 RGB array."""
    terrain_bytes = await fetch_bytes(session, settings.TERRAIN_URL)
    terrain_image = Image.open(io.BytesIO(terrain_bytes)).convert("RGB")
    if terrain_image.size != (settings.WIDTH, settings.HEIGHT):
        terrain_image = terrain_image.resize(
            (settings.WIDTH, settings.HEIGHT), Image.Resampling.LANCZOS,
        )
    return np.array(terrain_image).astype(np.float32)


# ============================================================
# TERRAIN OVERLAY — shaded-relief water-colour effect
# ============================================================

def _luminance(image: np.ndarray) -> np.ndarray:
    """Perceived brightness from an RGB image (Rec. 601 weighted sum)."""
    return (
        LUMINANCE_R * image[:, :, 0]
        + LUMINANCE_G * image[:, :, 1]
        + LUMINANCE_B * image[:, :, 2]
    )


def _relief_strength(brightness: np.ndarray) -> np.ndarray:
    """Gradient magnitude normalised to [0, 1] — acts as a pseudo-height map."""
    gradient_y, gradient_x = np.gradient(brightness)
    magnitude = np.sqrt(gradient_x**2 + gradient_y**2)
    return magnitude / (magnitude.max() + EPSILON)


def _light_mask(brightness: np.ndarray) -> np.ndarray:
    """Soft mask for brightly lit areas (brightness ≥ LIGHT_THRESHOLD)."""
    return np.clip((brightness - LIGHT_THRESHOLD) / LIGHT_RANGE, 0, 1)


def _shadow_mask(brightness: np.ndarray) -> np.ndarray:
    """Soft mask for shadowed areas (brightness ≤ SHADOW_THRESHOLD)."""
    return np.clip((SHADOW_THRESHOLD - brightness) / SHADOW_RANGE, 0, 1)


def _composite_alpha(shadow: np.ndarray, relief: np.ndarray) -> np.ndarray:
    """Combine shadow and relief into a single opacity mask (clamped)."""
    alpha = relief * settings.TERRAIN_OPACITY + shadow * relief
    return np.clip(alpha, 0, MAX_ALPHA)


def _screen_blend(base: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    """
    Screen-blend *base* with white using per-pixel *alpha*.
    Equivalent to: base * (1 - α) + 255 * α
    """
    return base * (1 - alpha[:, :, None]) + FULL_WHITE * alpha[:, :, None]


def create_terrain_overlay(terrain: np.ndarray) -> np.ndarray:
    """
    Produce a shaded-relief water-colour overlay from the terrain image.

    Steps:
      1. Luminance → brightness map.
      2. Gradient magnitude → relief strength.
      3. Light / shadow masks from brightness thresholds.
      4. Composite alpha = relief × opacity + shadow × relief.
      5. Base layer: WATER_COLOR darkened by the alpha mask.
      6. Light highlight: screen-blend with white on steep, lit terrain.
    """
    brightness = _luminance(terrain)
    relief = np.clip(_relief_strength(brightness) * RELIEF_MULTIPLIER, 0, 1)
    light = _light_mask(brightness)
    shadow = _shadow_mask(brightness)
    alpha = _composite_alpha(shadow, relief)

    # Base: water colour dimmed where the mask is opaque
    base = settings.WATER_COLOR * (1 - alpha[:, :, None])

    # Overlay: white highlight on steep, sun-facing slopes
    light_alpha = light * relief * LIGHT_OVERLAY_STRENGTH
    result = _screen_blend(base, light_alpha)

    return np.clip(result, 0, 255)


def create_player_layer(
    snapshot_bytes: bytes,
    width: int = settings.WIDTH,
    height: int = settings.HEIGHT,
    is_canvas: bool = False,
) -> Image.Image:
    """
    Decode a game snapshot into a Pillow image.

    *Map mode* (``is_canvas=False``) — returns RGBA; zero-valued pixels are
    transparent (un-surveyed terrain).
    *Canvas mode* (``is_canvas=True``) — returns RGB; near-white pixels are
    treated as transparent background, then pasted onto solid white.
    """
    if is_canvas:
        expected_min_size = settings.CANVAS_MAIN_WIDTH * height * settings.CHANNELS
    else:
        expected_min_size = width * height * settings.CHANNELS

    if len(snapshot_bytes) < expected_min_size:
        raise ValueError(
            f"Invalid snapshot size: {len(snapshot_bytes)} bytes "
            f"(expected at least {expected_min_size}).",
        )

    # Choose widths according to mode
    if is_canvas:
        main_width = settings.CANVAS_MAIN_WIDTH   # 1357
        vip_width = settings.VIP_WIDTH             # 340
    else:
        main_width = settings.MAIN_MAP_WIDTH       # 2714
        vip_width = 0

    main = _decode_main_area(snapshot_bytes, height, main_width)
    vip_main_offset = main_width * height * settings.CHANNELS
    vip = _decode_vip_area(snapshot_bytes, height, vip_main_offset, vip_width)

    pixels = _assemble_pixels(main, vip, width)
    r, g, b = _bgr_to_rgb(pixels)

    if is_canvas:
        # Canvas: near-white → transparent, then flatten onto white
        is_opaque = ~((r > WHITE_THRESHOLD) & (g > WHITE_THRESHOLD) & (b > WHITE_THRESHOLD))
        alpha = np.where(is_opaque, 255, 0).astype(np.uint8)
        rgba = np.dstack((r, g, b, alpha))
        img = Image.fromarray(rgba, mode="RGBA")
        bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        bg.paste(img, (0, 0), img)
        return bg.convert("RGB")

    # Map: fully black pixels → transparent (un-surveyed water / void)
    is_void = (r == 0) & (g == 0) & (b == 0)
    alpha = np.where(is_void, 0, 255).astype(np.uint8)
    rgba = np.dstack((r, g, b, alpha))
    return Image.fromarray(rgba, mode="RGBA")


# ============================================================
# SNAPSHOT DECODING HELPERS
# ============================================================

def _decode_main_area(
    snapshot_bytes: bytes, height: int, main_width: int,
) -> np.ndarray:
    """Extract the main drawing area from the raw snapshot buffer."""
    byte_count = main_width * height * settings.CHANNELS
    return np.frombuffer(snapshot_bytes[:byte_count], dtype=np.uint8).reshape(
        (height, main_width, settings.CHANNELS),
    )


def _decode_vip_area(
    snapshot_bytes: bytes, height: int, offset: int, vip_width: int,
) -> np.ndarray | None:
    """Extract the VIP drawing area if the buffer is large enough."""
    byte_count = vip_width * height * settings.CHANNELS
    if len(snapshot_bytes) < offset + byte_count or vip_width == 0:
        return None
    return np.frombuffer(
        snapshot_bytes[offset : offset + byte_count], dtype=np.uint8,
    ).reshape((height, vip_width, settings.CHANNELS))


def _build_separator(height: int, width: int) -> np.ndarray:
    """Create a gold-coloured column (RGBA) to separate main and VIP areas."""
    separator = np.zeros((height, width, settings.CHANNELS), dtype=np.uint8)
    separator[:, :, 0] = _SEP_B
    separator[:, :, 1] = _SEP_G
    separator[:, :, 2] = _SEP_R
    separator[:, :, 3] = _SEP_A
    return separator


def _assemble_pixels(
    main: np.ndarray, vip: np.ndarray | None, total_width: int,
) -> np.ndarray:
    """
    Concatenate main, optional gold separator, and VIP along the width axis.

    Returns *main* unchanged when there is no VIP area (map mode).
    """
    if vip is None:
        return main

    sep_width = total_width - main.shape[1] - vip.shape[1]
    if sep_width > 0:
        separator = _build_separator(main.shape[0], sep_width)
        return np.concatenate((main, separator, vip), axis=1)
    return np.concatenate((main, vip), axis=1)


def _bgr_to_rgb(pixels: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    # noinspection PyShadowingNames
    """Swap BGR(A) → (R, G, B). Raw snapshot colour order is Blue-Green-Red."""
    return pixels[:, :, 2], pixels[:, :, 1], pixels[:, :, 0]


# ============================================================
# RENDERING — composite, crop, scale, encode
# ============================================================

def _scale_and_encode(
    image: Image.Image,
    scale: int,
    fmt: str,
    **save_kwargs: object,
) -> bytes:
    """Upscale with nearest-neighbour then encode to *fmt*."""
    w, h = image.size
    resized = image.resize((w * scale, h * scale), Image.Resampling.NEAREST)
    buf = io.BytesIO()
    resized.save(buf, format=fmt, **save_kwargs)
    return buf.getvalue()


def render_region_map(
    terrain: np.ndarray, snapshot_bytes: bytes, region: Region,
) -> bytes:
    """Composite player layer over the terrain overlay, crop to *region*, JPEG."""
    world = create_terrain_overlay(terrain)
    player_layer = create_player_layer(snapshot_bytes, settings.WIDTH, settings.HEIGHT)
    world_image = Image.fromarray(world.astype(np.uint8), mode="RGB").convert("RGBA")

    composite = Image.alpha_composite(world_image, player_layer).convert("RGB")

    x_min, y_min, x_max, y_max = region.coords
    cropped = composite.crop((x_min, y_min, x_max, y_max))

    return _scale_and_encode(
        cropped, settings.SCALE_FACTOR, fmt="JPEG", quality=100, subsampling=0,
    )


def render_canvas_map(snapshot_bytes: bytes) -> bytes:
    """Render the pure canvas (no terrain backdrop) as PNG."""
    canvas = create_player_layer(
        snapshot_bytes, settings.CANVAS_WIDTH, settings.CANVAS_HEIGHT, is_canvas=True,
    )
    return _scale_and_encode(canvas, settings.SCALE_FACTOR, fmt="PNG")


# ============================================================
# PUBLIC ASYNC ENTRY POINTS
# ============================================================

async def _create_session() -> aiohttp.ClientSession:
    """Build a standardised aiohttp session."""
    timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
    headers = {"User-Agent": USER_AGENT}
    return aiohttp.ClientSession(timeout=timeout, headers=headers)


async def get_map_region_jpeg(region: Region) -> bytes:
    """Concurrently fetch terrain + snapshot, render region, return JPEG bytes."""
    session = await _create_session()
    async with session:
        terrain_task = load_terrain(session)
        snapshot_task = fetch_bytes(session, settings.SNAPSHOT_URL)
        terrain, snapshot_bytes = await asyncio.gather(terrain_task, snapshot_task)

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, render_region_map, terrain, snapshot_bytes, region,
    )


async def get_canvas_png() -> bytes:
    """Fetch the canvas snapshot and return PNG bytes."""
    session = await _create_session()
    async with session:
        snapshot_bytes = await fetch_bytes(session, settings.CANVAS_SNAPSHOT_URL)

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, render_canvas_map, snapshot_bytes)
