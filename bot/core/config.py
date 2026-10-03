from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from pydantic_settings import BaseSettings, SettingsConfigDict

DIR = Path(__file__).absolute().parent.parent.parent
BOT_DIR = Path(__file__).absolute().parent.parent

class EnvBaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=f"{DIR}/.env", env_file_encoding="utf-8", extra="ignore")


class BotSettings(EnvBaseSettings):
    BOT_TOKEN: str


@dataclass(frozen=True)
class Region:
    name: str
    coords: tuple[int, int, int, int]
    aliases: tuple[str, ...] = ()


class GameSettings(EnvBaseSettings):
    REGIONS: dict = {
        "world": Region(
            "Весь мир",
            (0, 0, 1357, 628),
            aliases=("мир",),
        ),
        "sa": Region(
            "Северная Америка",
            (0, 0, 1040, 860),
            aliases=("са",),
        ),
        "ya": Region(
            "Южная Америка",
            (280, 560, 960, 1256),
            aliases=("юа",),
        ),
        "eurasia": Region(
            "Евразия",
            (760, 0, 2714, 860),
            aliases=(),
        ),
        "europe": Region(
            "Европа",
            (1030, 40, 1540, 440),
            aliases=(),
        ),
        "baltics": Region(
            "Балтия",
            (1276, 197, 1340, 255),
            aliases=("прибалтика", "латвия", "литва", "эстония"),
        ),
        "asia": Region(
            "Азия",
            (1440, 40, 2332, 760),
            aliases=(),
        ),
        "africa": Region(
            "Африка",
            (960, 300, 1720, 1090),
            aliases=(),
        ),
        "aus": Region(
            "Австралия и Океания",
            (1860, 700, 2714, 1220),
            aliases=("австралия", "океания"),
        ),
        "kishka": Region(
            "Того (кишка)",
            (1120, 626, 1150, 700),
            aliases=("кишка", "того"),
        ),
        "canada": Region(
            "Канада",
            (190, 20, 848, 360),
            aliases=(),
        ),
        "usa": Region(
            "США",
            (0, 100, 645, 510),
            aliases=("штаты",),
        ),
        "russia": Region(
            "Россия",
            (1280, 64, 2332, 348),
            aliases=("рф", "рашка"),
        ),
        "kazakhstan": Region(
            "Казахстан",
            (1458, 242, 1776, 364),
            aliases=("рк",),
        ),
        "shri-lanka": Region(
            "Шри-Ланка",
            (1784, 640, 1810, 690),
            aliases=(),
        ),
        "ukraine": Region(
            "Украина",
            (1296, 258, 1436, 334),
            aliases=("укр",),
        ),
        "bangladesh": Region(
            "Бангладеш",
            (1842, 490, 1892, 544),
            aliases=(),
        ),
        "china": Region(
            "Китай",
            (1696, 256, 2134, 550),
            aliases=("кнр",),
        ),
        "india": Region(
            "Индия",
            (1666, 408, 1930, 666),
            aliases=("инд",),
        ),
        "brasil": Region(
            "Бразилия",
            (502, 670, 860, 1050),
            aliases=("браз",),
        ),
        "israel": Region(
            "Израиль",
            (1390, 414, 1434, 484),
            aliases=(),
        ),
    }
    REGION_ALIASES: dict = {
        alias: region_id
        for region_id, region in REGIONS.items()
        for alias in list(region.aliases) + [region.name.lower()]
    }

    # Map
    WIDTH: int = 1357
    HEIGHT: int = 628
    CHANNELS: int = 4

    CANVAS_WIDTH: int = 1701  # 1357 + 4 + 340
    CANVAS_HEIGHT: int = 628

    # Snapshot layout (widths of the main and VIP drawing areas)
    MAIN_MAP_WIDTH: int = 1357
    CANVAS_MAIN_WIDTH: int = 1357
    VIP_WIDTH: int = 340

    SNAPSHOT_URL: str = "https://pr.pixroyale.fun/world/snapshot?revision=0&v=map-0"
    CANVAS_SNAPSHOT_URL: str = "https://pr.pixroyale.fun/canvas/snapshot"
    TERRAIN_URL: str = "https://pr.pixroyale.fun/world/asset/europe/realistic-map.jpg"

    # Easter egg
    NEPE_MAP_PATH: str = "./bot/assets/map_nepe.jpg"

    # Map settings
    WATER_COLOR: NDArray = np.array([90, 150, 220], dtype=np.float32)
    TERRAIN_OPACITY: float = 0.80

    SCALE_FACTOR: int = 2


class Settings(BotSettings, GameSettings):
    DEBUG: bool = False


settings = Settings()
