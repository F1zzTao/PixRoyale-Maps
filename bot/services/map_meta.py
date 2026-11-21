from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from urllib.parse import urljoin

import aiohttp
from loguru import logger

from bot.core.config import settings

META_CACHE_TTL_MS: int = 10 * 60 * 1000  # 10 minutes
HTTP_TIMEOUT: int = 30
USER_AGENT: str = "Mozilla/5.0"


@dataclass(frozen=True)
class MapMeta:
    map_id: str
    width: int
    height: int
    name_ru: str
    terrain_url: str
    next_wipe_at: int | None = None


_cached_meta: MapMeta | None = None
_cached_at_ms: int = 0
_meta_lock = asyncio.Lock()


def _is_cache_valid(now_ms: int) -> bool:
    if _cached_meta is None or _cached_at_ms == 0:
        return False
    if now_ms - _cached_at_ms >= META_CACHE_TTL_MS:
        return False
    return not (_cached_meta.next_wipe_at is not None and _cached_at_ms < _cached_meta.next_wipe_at <= now_ms)


def invalidate_map_meta_cache() -> None:
    """Mark the cached metadata as stale so the next lookup refreshes it."""
    global _cached_at_ms
    _cached_at_ms = 0


def _parse_map_meta(data: dict) -> MapMeta:
    map_id = str(data["mapId"])
    width = int(data["width"])
    height = int(data["height"])
    names = data.get("names") or {}
    name_ru = str(names.get("ru") or names.get("en") or map_id)
    realistic_path = data["assets"]["realistic"]
    terrain_url = urljoin(settings.BASE_URL, realistic_path)
    raw_wipe = data.get("nextWipeAt")
    next_wipe_at = int(raw_wipe) if raw_wipe is not None else None

    return MapMeta(
        map_id=map_id,
        width=width,
        height=height,
        name_ru=name_ru,
        terrain_url=terrain_url,
        next_wipe_at=next_wipe_at,
    )


async def _fetch_meta_json(session: aiohttp.ClientSession) -> dict:
    async with session.get(settings.META_URL) as response:
        response.raise_for_status()
        return await response.json(content_type=None)


async def get_map_meta(
    session: aiohttp.ClientSession | None = None,
    *,
    force_refresh: bool = False,
) -> MapMeta:
    """Fetch active map metadata with in-memory TTL caching and fallback."""
    global _cached_meta, _cached_at_ms

    now_ms = int(time.time() * 1000)
    if not force_refresh and _is_cache_valid(now_ms):
        assert _cached_meta is not None
        return _cached_meta

    async with _meta_lock:
        now_ms = int(time.time() * 1000)
        if not force_refresh and _is_cache_valid(now_ms):
            assert _cached_meta is not None
            return _cached_meta

        try:
            if session is not None:
                data = await _fetch_meta_json(session)
            else:
                timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
                headers = {"User-Agent": USER_AGENT}
                async with aiohttp.ClientSession(timeout=timeout, headers=headers) as own_session:
                    data = await _fetch_meta_json(own_session)

            meta = _parse_map_meta(data)
            _cached_meta = meta
            _cached_at_ms = int(time.time() * 1000)
            return meta
        except Exception as exc:
            if _cached_meta is not None and not force_refresh:
                logger.warning(f"Failed to refresh map metadata, using cached value: {exc}")
                return _cached_meta
            raise
