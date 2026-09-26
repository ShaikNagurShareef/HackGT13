"""FastAPI app factory: loads the artifact bundle once, wires routers and middleware."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from cachetools import LRUCache
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.areas import areas
from app.api.core import api
from app.api.envelope import (
    AppError,
    app_error_handler,
    unexpected_error_handler,
    validation_error_handler,
)
from app.api.extras import extras
from app.api.reports import reports
from app.api.walks import walks
from app.config import Settings, get_settings
from app.domain.router import Router
from app.middleware import RateLimitMiddleware
from app.repositories.artifacts import load_bundle
from app.repositories.hexes import load_hexes
from app.repositories.history import HistoryRepository
from app.repositories.reports import ReportsRepository
from app.repositories.walks import WalksRepository
from app.services.explain.providers import GeminiProvider, GroqProvider, Provider
from app.services.explain.service import ExplainService
from app.services.geocode import GeocodeService
from app.services.tts import TtsService
from app.services.weather import WeatherService

ROUTES_CACHE_SIZE = 512


def build_providers(cfg: Settings, client: httpx.AsyncClient) -> list[Provider]:
    """Groq gpt-oss-120b, then Gemini, then Groq gpt-oss-20b; missing keys drop a provider."""
    providers: list[Provider] = []
    groq_key = cfg.groq_api_key.get_secret_value() if cfg.groq_api_key else None
    if groq_key:
        providers.append(GroqProvider(client, groq_key, cfg.groq_model))
    if cfg.gemini_api_key:
        key = cfg.gemini_api_key.get_secret_value()
        providers.append(GeminiProvider(client, key, cfg.gemini_model))
    if groq_key:
        providers.append(GroqProvider(client, groq_key, cfg.groq_fallback_model, name="groq-20b"))
    return providers


log = logging.getLogger(__name__)
# httpx logs full URLs at INFO; Geoapify requires its key in the query string.
logging.getLogger("httpx").setLevel(logging.WARNING)


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or get_settings()
    bundle = load_bundle(cfg.artifacts_dir)  # fail fast: no bundle, no app (EC-36)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with httpx.AsyncClient() as client:
            app.state.weather = WeatherService(client)
            app.state.http = client
            app.state.explainer = ExplainService(
                build_providers(cfg, client),
                cfg.explain_budget_s,
                cfg.groq_budget_s,
                daily_budget=cfg.llm_daily_budget,
            )
            geo_key = cfg.geoapify_api_key.get_secret_value() if cfg.geoapify_api_key else None
            app.state.geocoder = GeocodeService(client, geo_key, cfg.geocode_daily_budget)
            eleven = cfg.elevenlabs_api_key.get_secret_value() if cfg.elevenlabs_api_key else None
            app.state.tts = TtsService(
                client, eleven, cfg.elevenlabs_voice_id, cfg.elevenlabs_model, cfg.tts_daily_budget
            )
            street_reports: ReportsRepository = app.state.reports
            if street_reports.configured and not await street_reports.ensure_indexes():
                log.warning("street report indexes not ensured; community reports may be hidden")
            shared_walks: WalksRepository = app.state.walks
            if shared_walks.configured and not await shared_walks.ensure_indexes():
                log.warning("shared walk indexes not ensured; live sharing may be unavailable")
            yield
            await street_reports.close()
            await shared_walks.close()

    app = FastAPI(title="PathPro API", version=bundle.model_version, lifespan=lifespan)
    app.state.bundle = bundle
    app.state.router = Router(bundle)
    app.state.hexes = load_hexes(bundle.root)  # City Pulse is optional (P1)
    app.state.settings = cfg
    app.state.routes_cache = LRUCache(maxsize=ROUTES_CACHE_SIZE)
    db_url = cfg.database_url.get_secret_value() if cfg.database_url else None
    app.state.history = HistoryRepository(db_url)
    mongo_uri = cfg.mongodb_uri.get_secret_value() if cfg.mongodb_uri else None
    app.state.reports = ReportsRepository(mongo_uri, cfg.mongodb_db)  # no I/O until first use
    app.state.walks = WalksRepository(mongo_uri, cfg.mongodb_db)
    app.add_middleware(
        RateLimitMiddleware,
        per_minute=cfg.rate_limit_per_minute,
        paid_per_minute=cfg.paid_rate_limit_per_minute,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.origins,
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Content-Type"],
        allow_credentials=False,
    )
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
    app.include_router(api)
    app.include_router(extras)
    app.include_router(areas)
    app.include_router(reports)
    app.include_router(walks)
    app.mount(
        f"/static/{bundle.model_version}",
        StaticFiles(directory=bundle.root),
        name="static",
    )
    log.info("PathPro API ready: model %s, %d segments", bundle.model_version, bundle.n_segments)
    return app
