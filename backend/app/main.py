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
from pydantic import SecretStr

from app.api.areas import areas
from app.api.ask import ask as ask_routes
from app.api.core import api
from app.api.envelope import (
    AppError,
    app_error_handler,
    unexpected_error_handler,
    validation_error_handler,
)
from app.api.extras import extras
from app.api.imagine import imagine as imagine_routes
from app.api.reports import reports
from app.api.safety import safety as safety_routes
from app.api.transit import transit
from app.api.walks import walks
from app.config import BACKEND_DIR, Settings, get_settings
from app.domain.router import Router
from app.middleware import RateLimitMiddleware
from app.repositories.artifacts import load_bundle, load_ride_bundle
from app.repositories.hexes import load_hexes
from app.repositories.history import HistoryRepository
from app.repositories.reports import ReportsRepository
from app.repositories.safety import load_safety
from app.repositories.walks import WalksRepository
from app.services.ask import AskService
from app.services.ask_corpus import load_allowed_numbers
from app.services.ask_memory import AskMemory
from app.services.ask_threads import MemoryTokens, ThreadTokens, random_secret
from app.services.backboard import Backboard
from app.services.explain.providers import (
    GeminiProvider,
    GrokProvider,
    GroqProvider,
    Provider,
)
from app.services.explain.service import ExplainService
from app.services.geocode import GeocodeService
from app.services.imagine import ImagineService
from app.services.imagine_check import GeminiImageCheck
from app.services.tts import GrokTtsService, TtsService, VoiceChain
from app.services.walks import RecentUpdates
from app.services.weather import WeatherService

ROUTES_CACHE_SIZE = 512


def secret(value: SecretStr | None) -> str | None:
    """The plain key, or None when unset or blank."""
    return (value.get_secret_value() or None) if value else None


def build_providers(cfg: Settings, client: httpx.AsyncClient) -> list[Provider]:
    """Grok, Groq gpt-oss-120b, Gemini, then Groq gpt-oss-20b; missing keys drop a provider."""
    providers: list[Provider] = []
    xai_key = secret(cfg.xai_api_key)
    if xai_key:
        providers.append(GrokProvider(client, xai_key, cfg.xai_model))
    groq_key = secret(cfg.groq_api_key)
    if groq_key:
        providers.append(GroqProvider(client, groq_key, cfg.groq_model))
    if cfg.gemini_api_key:
        key = cfg.gemini_api_key.get_secret_value()
        providers.append(GeminiProvider(client, key, cfg.gemini_model))
    if groq_key:
        providers.append(GroqProvider(client, groq_key, cfg.groq_fallback_model, name="groq-20b"))
    return providers


def build_voices(cfg: Settings, client: httpx.AsyncClient) -> VoiceChain:
    """Grok voice, then ElevenLabs; the browser's device voice covers the rest (VOX-04)."""
    grok = GrokTtsService(client, secret(cfg.xai_api_key), cfg.xai_tts_voice, cfg.tts_daily_budget)
    eleven = TtsService(
        client,
        secret(cfg.elevenlabs_api_key),
        cfg.elevenlabs_voice_id,
        cfg.elevenlabs_model,
        cfg.tts_daily_budget,
    )
    return VoiceChain((grok, eleven))


def build_ask(cfg: Settings, client: httpx.AsyncClient) -> tuple[AskService, AskMemory]:
    """Ask PathPro (Backboard) and its opt-in memory; 503 without a key and an assistant id.

    Thread and memory tokens share one secret under separate purposes; without a configured
    secret it is random per process (conversations and memory tokens reset on restart).
    """
    key = secret(cfg.backboard_api_key)
    token_secret = secret(cfg.ask_thread_secret)
    secret_bytes = token_secret.encode() if token_secret else random_secret()
    backboard = Backboard(client, key) if key else None
    assistant_id = cfg.backboard_assistant_id or None
    memory_tokens = MemoryTokens(secret_bytes)
    service = AskService(
        backboard,
        assistant_id,
        load_allowed_numbers(BACKEND_DIR.parent),
        llm_provider=cfg.backboard_llm_provider,
        model_name=cfg.backboard_model,
        daily_budget=cfg.ask_daily_budget,
        per_client_daily=cfg.ask_per_client_daily,
        thread_tokens=ThreadTokens(secret_bytes),
        memory_tokens=memory_tokens,
    )
    memory = AskMemory(backboard, assistant_id, memory_tokens, daily_budget=cfg.ask_memory_daily)
    return service, memory


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
            app.state.tts = build_voices(cfg, client)
            app.state.ask, app.state.ask_memory = build_ask(cfg, client)
            app.state.imagine = ImagineService(
                client,
                secret(cfg.xai_api_key),
                cfg.xai_image_model,
                cfg.imagine_cache_dir,
                cfg.imagine_daily_budget,
                cfg.imagine_per_client_daily,
                checker=GeminiImageCheck(
                    client, secret(cfg.gemini_api_key), cfg.gemini_check_model
                ),
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
    # Personal-safety layer is optional; only lighting/foot-traffic signals reach the router.
    app.state.safety = load_safety(bundle.root, bundle.n_segments, len(bundle.graph.edge_u))
    app.state.router = Router(bundle, app.state.safety.edges if app.state.safety else None)
    # Ride model (bike / e-bike / scooter) is optional: None disables ride modes, never walk.
    app.state.ride_bundle = load_ride_bundle(bundle.root)
    app.state.ride_router = Router(app.state.ride_bundle) if app.state.ride_bundle else None
    app.state.hexes = load_hexes(bundle.root)  # City Pulse is optional (P1)
    app.state.settings = cfg
    app.state.routes_cache = LRUCache(maxsize=ROUTES_CACHE_SIZE)
    db_url = cfg.database_url.get_secret_value() if cfg.database_url else None
    app.state.history = HistoryRepository(db_url)
    mongo_uri = cfg.mongodb_uri.get_secret_value() if cfg.mongodb_uri else None
    app.state.reports = ReportsRepository(mongo_uri, cfg.mongodb_db)  # no I/O until first use
    app.state.walks = WalksRepository(mongo_uri, cfg.mongodb_db)
    app.state.walk_gate = RecentUpdates()
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
    app.include_router(safety_routes)
    app.include_router(transit)
    app.include_router(imagine_routes)
    app.include_router(ask_routes)
    app.mount(
        f"/static/{bundle.model_version}",
        StaticFiles(directory=bundle.root),
        name="static",
    )
    log.info(
        "PathPro API ready: model %s, %d walk segments, ride %s",
        bundle.model_version,
        bundle.n_segments,
        app.state.ride_bundle.n_segments if app.state.ride_bundle else "unavailable",
    )
    return app
