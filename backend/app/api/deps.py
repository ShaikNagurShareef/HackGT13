"""Dependencies: long-lived objects are created once in the lifespan and read from app.state."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from app.api.envelope import AppError
from app.domain.modes import TravelMode, mode_for
from app.domain.router import Router
from app.repositories.artifacts import Bundle
from app.services.weather import WeatherService


@dataclass(frozen=True)
class ModeContext:
    """The model bundle and router a travel mode plans on."""

    mode: TravelMode
    bundle: Bundle
    router: Router


def get_bundle(request: Request) -> Bundle:
    bundle: Bundle = request.app.state.bundle
    return bundle


def get_router(request: Request) -> Router:
    router: Router = request.app.state.router
    return router


def get_weather(request: Request) -> WeatherService:
    weather: WeatherService = request.app.state.weather
    return weather


def ride_available(request: Request) -> bool:
    return getattr(request.app.state, "ride_router", None) is not None


def mode_context(request: Request, key: str) -> ModeContext:
    """Walk always resolves; ride modes need the optional ride model (else 503)."""
    mode = mode_for(key)
    if not mode.is_ride:
        return ModeContext(mode, get_bundle(request), get_router(request))
    bundle: Bundle | None = getattr(request.app.state, "ride_bundle", None)
    router: Router | None = getattr(request.app.state, "ride_router", None)
    if bundle is None or router is None:
        raise AppError(
            "MODE_UNAVAILABLE",
            "Bike and scooter routes are unavailable right now. Try walking.",
            status=503,
        )
    return ModeContext(mode, bundle, router)
