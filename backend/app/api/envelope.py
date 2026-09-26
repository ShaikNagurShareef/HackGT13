"""Consistent response envelope: {success, data, error, model_version}."""

from __future__ import annotations

from typing import Generic, TypeVar

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

T = TypeVar("T")


class ApiError(BaseModel):
    code: str
    message: str


class Envelope(BaseModel, Generic[T]):
    success: bool
    data: T | None = None
    error: ApiError | None = None
    model_version: str | None = None


class AppError(Exception):
    """Raised by services; rendered as an envelope with a stable error code."""

    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def ok(data: T, model_version: str | None) -> Envelope[T]:
    return Envelope[T](success=True, data=data, model_version=model_version)


def _version(request: Request) -> str | None:
    bundle = getattr(request.app.state, "bundle", None)
    return bundle.model_version if bundle is not None else None


async def app_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    body = Envelope[None](
        success=False,
        error=ApiError(code=exc.code, message=exc.message),
        model_version=_version(request),
    )
    return JSONResponse(status_code=exc.status, content=body.model_dump())


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Never leak stack traces or internals ."""
    body = Envelope[None](
        success=False,
        error=ApiError(code="INTERNAL", message="Something went wrong. Please retry."),
        model_version=_version(request),
    )
    return JSONResponse(status_code=500, content=body.model_dump())


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Malformed requests get the same envelope as every other error (no raw 422 bodies)."""
    body = Envelope[None](
        success=False,
        error=ApiError(code="BAD_REQUEST", message="That request was not valid."),
        model_version=_version(request),
    )
    return JSONResponse(status_code=422, content=body.model_dump())
