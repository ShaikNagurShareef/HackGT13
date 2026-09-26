"""Dependencies: long-lived objects are created once in the lifespan and read from app.state."""

from __future__ import annotations

from fastapi import Request

from app.domain.router import Router
from app.repositories.artifacts import Bundle
from app.services.weather import WeatherService


def get_bundle(request: Request) -> Bundle:
    bundle: Bundle = request.app.state.bundle
    return bundle


def get_router(request: Request) -> Router:
    router: Router = request.app.state.router
    return router


def get_weather(request: Request) -> WeatherService:
    weather: WeatherService = request.app.state.weather
    return weather
