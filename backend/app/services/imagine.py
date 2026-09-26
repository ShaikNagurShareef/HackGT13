"""Grok Imagine: an AI illustration of a street redesigned with evidence-based fixes.

The prompt is built only on the server, only from the segment's modeled risk factors and road
class (never user text, never street names). Images are cached on disk per segment and model,
and new generations are capped per day. The picture is an illustration, not a risk claim: it
never changes a score.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import httpx
from cachetools import TTLCache

from app.api.envelope import AppError
from app.api.schemas import SegmentDetail
from app.domain.timeutil import ATLANTA
from app.repositories.artifacts import Bundle
from app.services.explain.service import DailyBudget
from app.services.segments import segment_detail
from app.services.weather import Resolved

log = logging.getLogger(__name__)

XAI_IMAGES_URL = "https://api.x.ai/v1/images/generations"
IMAGINE_LABEL = "AI illustration of evidence-based street fixes by Grok Imagine — not a real photo"
UNAVAILABLE_MESSAGE = "Street redesign illustrations are unavailable right now."
BUDGET_MESSAGE = "Today's street illustrations are used up. Please try again tomorrow."
CLIENT_LIMIT_MESSAGE = "You've reached today's limit for new street illustrations."
MAX_TRACKED_CLIENTS = 50_000
DAY_S = 86_400
TIMEOUT_S = 60.0
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_FIXES = 4
MAX_NAMED_FACTORS = 3
DARK_SHARE_FOR_LIGHTING = 0.4  # most recorded crashes after dark: show street lighting

# Fixed reference hour (a weekday evening, dry) so a segment always gets the same plan and the
# cached image always matches the summary shown next to it.
REFERENCE_AT = datetime(2026, 9, 23, 21, 0, tzinfo=ATLANTA)
REFERENCE_WEATHER = Resolved(wet=False, source="assumed", label="Dry")

CROSSWALKS = "high-visibility continental crosswalks with curb extensions at the corners"
REFUGE_ISLAND = "a pedestrian refuge island in the median"
LIGHTING = "pedestrian-scale street lighting"
FIX_BY_FACTOR: dict[str, str] = {
    "speed": "a slower design speed with narrower travel lanes and raised crosswalks",
    "lanes": "a road diet that turns one travel lane into a protected bike lane",
    "road_type": "a road diet with a planted center median",
    "traffic_volume": REFUGE_ISLAND,
    "intersection": CROSSWALKS,
    "history": CROSSWALKS,
    "nearby_history": CROSSWALKS,
    "vehicle_crashes": REFUGE_ISLAND,
    "ped_activity": "wider sidewalks with curb extensions where people cross",
    "destinations": "wider sidewalks with curb extensions where people cross",
    "transit": "a bus stop on a curb extension with a marked crosswalk",
    "sidewalk": "a continuous wide sidewalk behind a planted buffer",
    "school": "a raised school crosswalk with flashing beacons",
    "lighting": LIGHTING,
    "light": LIGHTING,
    "length": "a mid-block crosswalk with a refuge island",
}
DEFAULT_FIXES = (CROSSWALKS, REFUGE_ISLAND)
ROAD_SCENES = {
    "arterial": "a multi-lane urban arterial street",
    "collector": "a two-lane urban collector street",
    "local": "a local neighborhood street",
}
IMAGE_SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
)


@dataclass(frozen=True)
class ImaginePlan:
    prompt: str
    summary: str
    fixes: tuple[str, ...]


@dataclass(frozen=True)
class CachedImage:
    content: bytes
    media_type: str


def _unique(items: list[str], limit: int) -> tuple[str, ...]:
    return tuple(dict.fromkeys(items))[:limit]


def plan_for(detail: SegmentDetail) -> ImaginePlan:
    """Map the factors that raise this street's traffic risk to street-design fixes."""
    raising = [f for f in detail.factors if f.points > 0 and f.key in FIX_BY_FACTOR]
    candidates = [FIX_BY_FACTOR[f.key] for f in raising]
    if detail.history.dark_share >= DARK_SHARE_FOR_LIGHTING:
        candidates.append(LIGHTING)
    fixes = _unique(candidates, MAX_FIXES) or DEFAULT_FIXES
    road = detail.road_group if detail.road_group in ROAD_SCENES else "urban"
    scene = ROAD_SCENES.get(detail.road_group, "an urban street")
    light = "Early evening, the new street lights on." if LIGHTING in fixes else "Daytime."
    prompt = (
        f"Photorealistic eye-level street photo of {scene} in Atlanta, Georgia, redesigned "
        f"with evidence-based Vision Zero street fixes: {'; '.join(fixes)}. {light} "
        "People walking and crossing, one person on a bike, cars moving slowly. Natural "
        "colors and realistic materials. No text, no words, no logos, no lettered signs."
    )
    named = _unique([f.label for f in raising], MAX_NAMED_FACTORS)
    because = f", drawn from its top traffic-risk factors ({', '.join(named)})" if named else ""
    summary = f"Redesign ideas for this {road} street{because}: {'; '.join(fixes)}."
    return ImaginePlan(prompt=prompt, summary=summary, fixes=fixes)


def plan_for_segment(bundle: Bundle, seg_id: int) -> ImaginePlan:
    """Plan at the fixed reference hour; unknown segments raise NOT_FOUND (404)."""
    return plan_for(segment_detail(bundle, seg_id, REFERENCE_AT, REFERENCE_WEATHER))


def media_type_of(content: bytes) -> str | None:
    return next((t for sig, t in IMAGE_SIGNATURES if content.startswith(sig)), None)


def _decode_image(payload: Any) -> bytes:
    try:
        content = base64.b64decode(payload["data"][0]["b64_json"], validate=True)
    except (KeyError, IndexError, TypeError, ValueError, binascii.Error) as exc:
        raise ValueError("no image in response") from exc
    if len(content) > MAX_IMAGE_BYTES or media_type_of(content) is None:
        raise ValueError("not an image")
    return content


class ClientDailyLimit:
    """Caps new (paid) illustrations per client per day so one client cannot spend the budget."""

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._used: TTLCache[tuple[date, str], int] = TTLCache(
            maxsize=MAX_TRACKED_CLIENTS, ttl=DAY_S
        )

    def take(self, client: str, today: date | None = None) -> bool:
        key = (today or date.today(), client)
        used = self._used.get(key, 0)
        if used >= self._limit:
            return False
        self._used[key] = used + 1
        return True


class ImagineService:
    def __init__(
        self,
        client: httpx.AsyncClient,
        api_key: str | None,
        model: str,
        cache_dir: Path,
        daily_budget: int,
        per_client_daily: int,
    ) -> None:
        self._client = client
        self._key = api_key
        self._model = model
        self._cache_dir = cache_dir
        self._budget = DailyBudget(daily_budget)
        self._per_client = ClientDailyLimit(per_client_daily)
        self._inflight: dict[int, asyncio.Lock] = {}

    @property
    def enabled(self) -> bool:
        return bool(self._key)

    def _path(self, seg_id: int) -> Path:
        """Integer ids and a slugged model name only: no caller text reaches the file system."""
        model = re.sub(r"[^a-z0-9]+", "-", self._model.lower()).strip("-")
        return self._cache_dir / f"seg-{int(seg_id)}-{model}.img"

    def _read(self, seg_id: int) -> CachedImage | None:
        path = self._path(seg_id)
        if not path.is_file():
            return None
        content = path.read_bytes()
        media_type = media_type_of(content)
        return CachedImage(content, media_type) if media_type else None

    async def cached(self, seg_id: int) -> CachedImage | None:
        """The stored illustration, read off the event loop; None when not generated yet."""
        return await asyncio.to_thread(self._read, seg_id)

    async def ensure(self, seg_id: int, prompt: str, client: str) -> bool:
        """Make sure an image exists for this segment; True when it was already cached."""
        if self._path(seg_id).is_file():
            return True
        if not self.enabled:
            raise AppError("IMAGINE_UNAVAILABLE", UNAVAILABLE_MESSAGE, 503)
        lock = self._inflight.setdefault(seg_id, asyncio.Lock())
        try:
            async with lock:  # single-flight: repeated taps on one street make one paid call
                if self._path(seg_id).is_file():
                    return True
                if not self._per_client.take(client):
                    raise AppError("IMAGINE_CLIENT_LIMIT", CLIENT_LIMIT_MESSAGE, 429)
                if not self._budget.take():
                    raise AppError("IMAGINE_BUDGET", BUDGET_MESSAGE, 429)
                content = await self._generate(prompt)
                await asyncio.to_thread(self._store, seg_id, content)
                return False
        finally:
            self._inflight.pop(seg_id, None)

    async def _generate(self, prompt: str) -> bytes:
        body = {
            "model": self._model,
            "prompt": prompt,
            "n": 1,
            "aspect_ratio": "16:9",
            "resolution": "1k",
            "response_format": "b64_json",
        }
        try:
            resp = await self._client.post(
                XAI_IMAGES_URL,
                json=body,
                headers={"Authorization": f"Bearer {self._key}"},
                timeout=TIMEOUT_S,
            )
            resp.raise_for_status()
            return _decode_image(resp.json())
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("imagine failed: %s", type(exc).__name__)
            raise AppError(
                "IMAGINE_FAILED", "Could not draw this street right now. Please try again.", 502
            ) from exc

    def _store(self, seg_id: int, content: bytes) -> None:
        path = self._path(seg_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(content)
        tmp.replace(path)  # atomic: readers never see a half-written image
