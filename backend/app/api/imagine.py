"""Grok Imagine endpoints: generate (paid, budgeted) and serve cached street illustrations."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import get_bundle
from app.api.envelope import AppError, Envelope, ok
from app.repositories.artifacts import Bundle
from app.services.imagine import IMAGINE_LABEL, ImagineService, plan_for_segment

imagine = APIRouter()
BundleDep = Annotated[Bundle, Depends(get_bundle)]
IMAGE_CACHE_CONTROL = "public, max-age=86400"


class ImagineRequest(BaseModel):
    """Only a segment id: the prompt is always written by the server."""

    model_config = ConfigDict(extra="forbid")
    seg_id: int = Field(ge=0)


class ImagineData(BaseModel):
    seg_id: int
    image_url: str
    prompt_summary: str
    fixes: list[str]
    label: str
    cached: bool


def _service(request: Request) -> ImagineService:
    service: ImagineService = request.app.state.imagine
    return service


def _image_url(seg_id: int) -> str:
    return f"/imagine/segment/{seg_id}.png"


@imagine.post("/imagine/segment", response_model=Envelope[ImagineData])
async def imagine_segment(
    req: ImagineRequest, request: Request, bundle: BundleDep
) -> Envelope[ImagineData]:
    plan = plan_for_segment(bundle, req.seg_id)
    cached = await _service(request).ensure(req.seg_id, plan.prompt)
    data = ImagineData(
        seg_id=req.seg_id,
        image_url=_image_url(req.seg_id),
        prompt_summary=plan.summary,
        fixes=list(plan.fixes),
        label=IMAGINE_LABEL,
        cached=cached,
    )
    return ok(data, bundle.model_version)


@imagine.get("/imagine/segment/{seg_id}.png", response_class=Response)
async def imagine_image(
    seg_id: Annotated[int, Path(ge=0)], request: Request, bundle: BundleDep
) -> Response:
    """Serve an already-generated illustration; this route never calls xAI."""
    if seg_id >= bundle.n_segments:
        raise AppError("NOT_FOUND", "That street segment is not in PathPro coverage.", 404)
    image = await _service(request).cached(seg_id)
    if image is None:
        raise AppError("IMAGINE_NOT_FOUND", "No illustration for this street yet.", 404)
    return Response(
        content=image.content,
        media_type=image.media_type,
        headers={"Cache-Control": IMAGE_CACHE_CONTROL, "X-Content-Type-Options": "nosniff"},
    )
