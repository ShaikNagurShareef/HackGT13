"""Verify every configured sponsor key with one minimal live call. Never prints key values.

Usage: cd backend && uv run python -m app.tools.check_keys
"""

from __future__ import annotations

import asyncio
import sys

import httpx
import psycopg

from app.config import get_settings
from app.repositories.reports import ReportsRepository

OK, MISSING, FAIL = "OK     ", "MISSING", "FAIL   "


async def _get(client: httpx.AsyncClient, url: str, **kw: object) -> int:
    resp = await client.get(url, timeout=10.0, **kw)  # type: ignore[arg-type]
    return resp.status_code


async def check_groq(client: httpx.AsyncClient, key: str | None, model: str) -> tuple[str, str]:
    if not key:
        return MISSING, "GROQ_API_KEY"
    code = await _get(
        client, "https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {key}"}
    )
    return (OK, f"models reachable, using {model}") if code == 200 else (FAIL, f"HTTP {code}")


async def check_xai(client: httpx.AsyncClient, key: str | None, model: str) -> tuple[str, str]:
    """xAI (Grok explanations, voice, Imagine): list models, never a paid call."""
    if not key:
        return MISSING, "XAI_API_KEY (Grok off; Groq/Gemini explain, ElevenLabs/device voice)"
    code = await _get(
        client, "https://api.x.ai/v1/models", headers={"Authorization": f"Bearer {key}"}
    )
    return (OK, f"models reachable, using {model}") if code == 200 else (FAIL, f"HTTP {code}")


async def check_gemini(client: httpx.AsyncClient, key: str | None, model: str) -> tuple[str, str]:
    if not key:
        return MISSING, "GEMINI_API_KEY"
    code = await _get(
        client,
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}",
        headers={"x-goog-api-key": key},
    )
    return (OK, f"{model} available") if code == 200 else (FAIL, f"HTTP {code} for {model}")


async def check_geoapify(client: httpx.AsyncClient, key: str | None) -> tuple[str, str]:
    if not key:
        return MISSING, "GEOAPIFY_API_KEY (search falls back to curated places)"
    code = await _get(
        client,
        "https://api.geoapify.com/v1/geocode/autocomplete",
        params={"text": "Tech Square Atlanta", "limit": 1, "apiKey": key},
    )
    return (OK, "autocomplete works") if code == 200 else (FAIL, f"HTTP {code}")


async def check_elevenlabs(
    client: httpx.AsyncClient, key: str | None, voice: str | None
) -> tuple[str, str]:
    if not key or not voice:
        return MISSING, "ELEVENLABS_API_KEY / ELEVENLABS_VOICE_ID (device voice fallback)"
    code = await _get(
        client, f"https://api.elevenlabs.io/v1/voices/{voice}", headers={"xi-api-key": key}
    )
    return (OK, "voice found") if code == 200 else (FAIL, f"HTTP {code} for voice id")


def check_tiger(url: str | None) -> tuple[str, str]:
    if not url:
        return MISSING, "DATABASE_URL (history chart hidden)"
    try:
        with psycopg.connect(url, connect_timeout=8) as conn:
            rows = conn.execute(
                "SELECT name FROM pg_available_extensions WHERE name IN ('timescaledb','postgis')"
            ).fetchall()
    except psycopg.Error as exc:
        return FAIL, type(exc).__name__
    have = {r[0] for r in rows}
    missing = {"timescaledb", "postgis"} - have
    return (OK, "timescaledb + postgis available") if not missing else (FAIL, f"missing {missing}")


async def check_mongo(repo: ReportsRepository) -> tuple[str, str]:
    """MongoDB Atlas: ping, then confirm the geo, TTL, and unique indexes exist."""
    if not repo.configured:
        return MISSING, "MONGODB_URI (community reports hidden)"
    if await repo.ping() != "ok":
        return FAIL, "ping failed (check the URI and Atlas network access list)"
    if not await repo.indexes_ok():
        return FAIL, "ping ok, indexes MISSING (start the API once to create them)"
    return OK, "ping ok, indexes OK"


def secret(value: object) -> str | None:
    return value.get_secret_value() if value else None  # type: ignore[attr-defined]


async def main() -> int:
    cfg = get_settings()
    async with httpx.AsyncClient() as client:
        results = {
            "xAI Grok": await check_xai(client, secret(cfg.xai_api_key), cfg.xai_model),
            "Groq": await check_groq(client, secret(cfg.groq_api_key), cfg.groq_model),
            "Gemini": await check_gemini(client, secret(cfg.gemini_api_key), cfg.gemini_model),
            "Geoapify": await check_geoapify(client, secret(cfg.geoapify_api_key)),
            "ElevenLabs": await check_elevenlabs(
                client, secret(cfg.elevenlabs_api_key), cfg.elevenlabs_voice_id
            ),
        }
    results["Tiger Data"] = check_tiger(secret(cfg.database_url))
    mongo = ReportsRepository(secret(cfg.mongodb_uri), cfg.mongodb_db)
    results["MongoDB"] = await check_mongo(mongo)
    await mongo.close()
    for name, (status, note) in results.items():
        print(f"{status} {name:<11} {note}")
    return 1 if any(s == FAIL for s, _ in results.values()) else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
