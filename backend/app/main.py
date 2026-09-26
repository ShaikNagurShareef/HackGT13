"""FastAPI app factory: loads the artifact bundle once, wires routers and middleware."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from cachetools import LRUCache
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.core import api
from app.api.envelope import AppError, app_error_handler, unexpected_error_handler
from app.api.extras import extras
from app.config import Settings, get_settings
from app.domain.router import Router
from app.middleware import RateLimitMiddleware
from app.repositories.artifacts import load_bundle
from app.repositories.history import HistoryRepository
from app.services.explain.providers import GeminiProvider, GroqProvider, Provider
from app.services.explain.service import ExplainService
from app.services.geocode import GeocodeService
from app.services.weather import WeatherService

ROUTES_CACHE_SIZE = 512


def build_providers(cfg: Settings, client: httpx.AsyncClient) -> list[Provider]:
    """Groq first (fast), Gemini second; missing keys simply drop a provider."""
    providers: list[Provider] = []
    if cfg.groq_api_key:
        providers.append(GroqProvider(client, cfg.groq_api_key.get_secret_value(), cfg.groq_model))
    if cfg.gemini_api_key:
        key = cfg.gemini_api_key.get_secret_value()
        providers.append(GeminiProvider(client, key, cfg.gemini_model))
    return providers


log = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or get_settings()
    bundle = load_bundle(cfg.artifacts_dir)  # fail fast: no bundle, no app (EC-36)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with httpx.AsyncClient() as client:
            app.state.weather = WeatherService(client)
            app.state.http = client
            app.state.explainer = ExplainService(
                build_providers(cfg, client), cfg.explain_budget_s, cfg.groq_budget_s
            )
            geo_key = cfg.geoapify_api_key.get_secret_value() if cfg.geoapify_api_key else None
            app.state.geocoder = GeocodeService(client, geo_key)
            yield

    app = FastAPI(title="PathPulse API", version=bundle.model_version, lifespan=lifespan)
    app.state.bundle = bundle
    app.state.router = Router(bundle)
    app.state.settings = cfg
    app.state.routes_cache = LRUCache(maxsize=ROUTES_CACHE_SIZE)
    db_url = cfg.database_url.get_secret_value() if cfg.database_url else None
    app.state.history = HistoryRepository(db_url)
    app.add_middleware(RateLimitMiddleware, per_minute=cfg.rate_limit_per_minute)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        allow_credentials=False,
    )
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
    app.include_router(api)
    app.include_router(extras)
    app.mount(
        f"/static/{bundle.model_version}",
        StaticFiles(directory=bundle.root),
        name="static",
    )
    log.info("PathPulse API ready: model %s, %d segments", bundle.model_version, bundle.n_segments)
    return app
