"""Grok draws, Gemini checks: every Grok Imagine illustration is reviewed before it is shown."""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from app.config import Settings
from app.main import create_app
from app.services.imagine import XAI_IMAGES_URL
from app.services.imagine_check import CheckResult, GeminiImageCheck
from app.services.weather import FORECAST_URL
from fastapi.testclient import TestClient

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
GEMINI_HOST = "generativelanguage.googleapis.com"
GEMINI_MODEL = "gemini-test-vision"
FIXES = (
    "high-visibility continental crosswalks with curb extensions at the corners",
    "a pedestrian refuge island in the median",
    "pedestrian-scale street lighting",
)
BANNED = re.compile(r"\b(safe|safer|safest|unsafe|dangerous|bad area|guaranteed)\b", re.IGNORECASE)
HOT_SEG = 2


def _image(data: bytes = PNG) -> httpx.Response:
    return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(data).decode()}]})


def _gemini(payload: Any, finish: str = "STOP") -> httpx.Response:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return httpx.Response(
        200,
        json={"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": finish}]},
    )


def _verdict(
    shown: list[Any] | None = None, text: bool = False, faces: bool = False
) -> dict[str, Any]:
    return {"fixes_shown": shown or [], "has_text_or_logos": text, "has_identifiable_faces": faces}


# --- GeminiImageCheck (unit) ---------------------------------------------------------------


@pytest.fixture
def gemini_mock() -> Iterator[respx.Route]:
    with respx.mock(assert_all_called=False) as mock:
        yield mock.post(host=GEMINI_HOST)


async def _check(route: respx.Route, key: str | None = "gm-test", **kw: Any) -> CheckResult | None:
    async with httpx.AsyncClient() as client:
        checker = GeminiImageCheck(client, key, GEMINI_MODEL)
        return await checker.check(PNG, "image/png", kw.get("fixes", FIXES))


@pytest.mark.unit
async def test_check_sends_the_image_and_asks_for_structured_json(
    gemini_mock: respx.Route,
) -> None:
    gemini_mock.mock(return_value=_gemini(_verdict([FIXES[0]])))

    result = await _check(gemini_mock)

    assert result == CheckResult(
        fixes_shown=(FIXES[0],), has_text_or_logos=False, has_identifiable_faces=False
    )
    assert result is not None and result.passed
    sent = gemini_mock.calls[0].request
    assert sent.headers["x-goog-api-key"] == "gm-test"
    assert f"/models/{GEMINI_MODEL}:generateContent" in str(sent.url)
    assert "key=" not in str(sent.url)  # the key never rides in the URL
    body = json.loads(sent.content)
    parts = body["contents"][0]["parts"]
    inline = next(p["inline_data"] for p in parts if "inline_data" in p)
    assert inline == {"mime_type": "image/png", "data": base64.b64encode(PNG).decode()}
    prompt = json.dumps(body)
    assert all(fix in prompt for fix in FIXES)
    config = body["generationConfig"]
    assert config["responseMimeType"] == "application/json"
    schema = config["responseSchema"]
    assert set(schema["properties"]) == {
        "fixes_shown",
        "has_text_or_logos",
        "has_identifiable_faces",
    }
    assert not BANNED.search(prompt)


@pytest.mark.unit
async def test_check_keeps_only_planned_fixes(gemini_mock: respx.Route) -> None:
    shown = [
        f"  {FIXES[1].upper()}  ",  # case and whitespace are forgiven
        "a gold-plated monorail",  # hallucinated
        FIXES[1],  # duplicate
        "crosswalks",  # partial, not exact
        "x" * 5000,  # oversized
    ]
    gemini_mock.mock(return_value=_gemini(_verdict(shown)))

    result = await _check(gemini_mock)

    assert result is not None
    assert result.fixes_shown == (FIXES[1],)


@pytest.mark.unit
async def test_check_reports_text_logos_and_faces(gemini_mock: respx.Route) -> None:
    gemini_mock.mock(return_value=_gemini(_verdict([FIXES[0]], text=True, faces=True)))

    result = await _check(gemini_mock)

    assert result is not None
    assert result.has_text_or_logos and result.has_identifiable_faces
    assert not result.passed


@pytest.mark.unit
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500),
        httpx.Response(200, json={"candidates": []}),
        httpx.Response(200, text="not json"),
        _gemini("not json at all"),
        _gemini(["a", "list"]),
        _gemini({"fixes_shown": [], "has_text_or_logos": False}),  # missing key
        _gemini({"fixes_shown": "all", "has_text_or_logos": False, "has_identifiable_faces": 0}),
        _gemini(_verdict([42])),  # non-string entry
        _gemini({**_verdict(), "has_text_or_logos": "no"}),  # not a boolean
        _gemini(_verdict([FIXES[0]]), finish="MAX_TOKENS"),
        _gemini(_verdict([FIXES[0]]), finish="SAFETY"),
    ],
)
async def test_check_returns_none_for_bad_output(
    gemini_mock: respx.Route, response: httpx.Response
) -> None:
    gemini_mock.mock(return_value=response)

    assert await _check(gemini_mock) is None


@pytest.mark.unit
async def test_check_timeout_is_unchecked_and_logs_only_the_error_type(
    gemini_mock: respx.Route, caplog: pytest.LogCaptureFixture
) -> None:
    gemini_mock.mock(side_effect=httpx.ReadTimeout("secret detail gm-test"))

    assert await _check(gemini_mock) is None
    assert "ReadTimeout" in caplog.text
    assert "secret detail" not in caplog.text and "gm-test" not in caplog.text


@pytest.mark.unit
async def test_check_without_key_is_unchecked_and_makes_no_call(
    gemini_mock: respx.Route,
) -> None:
    assert await _check(gemini_mock, key=None) is None
    assert gemini_mock.call_count == 0


@pytest.mark.unit
def test_checker_repr_hides_the_key() -> None:
    checker = GeminiImageCheck(httpx.AsyncClient(), "gm-secret-key", GEMINI_MODEL)

    assert "gm-secret-key" not in repr(checker)


# --- ImagineService + API (integration) ----------------------------------------------------


@dataclass
class Harness:
    client: TestClient
    images: respx.Route
    gemini: respx.Route
    cache_dir: Path


def _harness(bundle_dir: Path, cache_dir: Path, **overrides: object) -> Iterator[Harness]:
    settings = Settings(
        artifacts_dir=bundle_dir,
        rate_limit_per_minute=1000,
        paid_rate_limit_per_minute=1000,
        imagine_cache_dir=cache_dir,
        xai_api_key="xai-test",
        gemini_model="gemini-explain-only",
        gemini_check_model=GEMINI_MODEL,
        _env_file=None,
        **overrides,  # type: ignore[arg-type]
    )
    with respx.mock(assert_all_called=False) as mock:
        mock.get(FORECAST_URL).mock(return_value=httpx.Response(503))
        images = mock.post(XAI_IMAGES_URL).mock(return_value=_image())
        gemini = mock.post(host=GEMINI_HOST).mock(return_value=_gemini(_verdict()))
        mock.route(host="testserver").pass_through()
        with TestClient(create_app(settings)) as client:
            yield Harness(client, images, gemini, cache_dir)


@pytest.fixture
def checked(bundle_dir: Path, tmp_path: Path) -> Iterator[Harness]:
    yield from _harness(bundle_dir, tmp_path / "imagine", gemini_api_key="gm-test")


@pytest.fixture
def checked_budget_one(bundle_dir: Path, tmp_path: Path) -> Iterator[Harness]:
    yield from _harness(
        bundle_dir, tmp_path / "imagine", gemini_api_key="gm-test", imagine_daily_budget=1
    )


@pytest.fixture
def unchecked(bundle_dir: Path, tmp_path: Path) -> Iterator[Harness]:
    yield from _harness(bundle_dir, tmp_path / "imagine")


def _post(h: Harness, seg_id: int = HOT_SEG) -> httpx.Response:
    return h.client.post("/imagine/segment", json={"seg_id": seg_id})


def _planned_fixes(h: Harness) -> list[str]:
    """The server's planned fixes, as sent to Gemini in the check prompt."""
    body = json.loads(h.gemini.calls[0].request.content)
    text = json.dumps(body["contents"])
    return [fix for fix in _all_fix_phrases() if fix in text]


def _all_fix_phrases() -> list[str]:
    from app.services.imagine import FIX_BY_FACTOR, LIGHTING

    return sorted({*FIX_BY_FACTOR.values(), LIGHTING})


def _sidecars(h: Harness) -> list[Path]:
    return sorted(h.cache_dir.glob("*.check.json"))


def _images(h: Harness) -> list[Path]:
    return sorted(h.cache_dir.glob("*.img"))


def _echo_first_fix(request: httpx.Request) -> httpx.Response:
    """Gemini 'sees' the first planned fix and invents one more that was never planned."""
    text = json.dumps(json.loads(request.content)["contents"])
    planned = [fix for fix in _all_fix_phrases() if fix in text]
    return _gemini(_verdict([planned[0].upper(), "a hallucinated tram"]))


@pytest.mark.integration
def test_passing_check_caches_the_image_with_a_sidecar(checked: Harness) -> None:
    checked.gemini.side_effect = _echo_first_fix

    resp = _post(checked)

    assert resp.status_code == 200
    data = resp.json()["data"]
    shown = data["check"]["fixes_shown"]
    assert data["check"] == {
        "by": "gemini",
        "fixes_shown": shown,
        "fixes_total": len(data["fixes"]),
    }
    assert len(shown) == 1 and shown[0] in data["fixes"]
    assert set(_planned_fixes(checked)) == set(data["fixes"])
    assert len(_images(checked)) == 1
    sidecar = json.loads(
        (checked.cache_dir / f"seg-{HOT_SEG}-grok-imagine-image-2-0.check.json").read_text()
    )
    assert sidecar == {
        "by": "gemini",
        "model": GEMINI_MODEL,
        "fixes_shown": shown,
        "fixes_total": len(data["fixes"]),
        "passed": True,
    }
    assert not list(checked.cache_dir.glob("*.tmp"))


@pytest.mark.integration
def test_cached_hit_returns_the_stored_check_without_calling_gemini(checked: Harness) -> None:
    first = _post(checked)
    planned = first.json()["data"]["fixes"]
    (checked.cache_dir / f"seg-{HOT_SEG}-grok-imagine-image-2-0.check.json").write_text(
        json.dumps(
            {
                "by": "gemini",
                "model": GEMINI_MODEL,
                "fixes_shown": [planned[0]],
                "fixes_total": len(planned),
                "passed": True,
            }
        )
    )

    again = _post(checked)

    data = again.json()["data"]
    assert data["cached"] is True
    assert data["check"] == {
        "by": "gemini",
        "fixes_shown": [planned[0]],
        "fixes_total": len(planned),
    }
    assert checked.images.call_count == 1
    assert checked.gemini.call_count == 1


@pytest.mark.integration
@pytest.mark.parametrize("flag", ["text", "faces"])
def test_flagged_image_is_retried_once_then_rejected_and_not_cached(
    checked: Harness, flag: str
) -> None:
    checked.gemini.mock(return_value=_gemini(_verdict(**{flag: True})))

    resp = _post(checked)
    image = checked.client.get(f"/imagine/segment/{HOT_SEG}.png")

    assert resp.status_code == 502
    body = resp.json()
    assert body["error"]["code"] == "IMAGINE_REJECTED"
    assert body["error"]["message"] and not BANNED.search(body["error"]["message"])
    assert checked.images.call_count == 2
    assert checked.gemini.call_count == 2
    assert image.status_code == 404
    assert not _images(checked) and not _sidecars(checked)


@pytest.mark.integration
def test_flagged_image_then_clean_retry_is_cached(checked: Harness) -> None:
    checked.gemini.side_effect = [_gemini(_verdict(text=True)), _gemini(_verdict())]

    resp = _post(checked)

    assert resp.status_code == 200
    assert resp.json()["data"]["check"]["by"] == "gemini"
    assert checked.images.call_count == 2
    assert len(_images(checked)) == 1


@pytest.mark.integration
def test_no_retry_when_the_daily_budget_is_spent(checked_budget_one: Harness) -> None:
    checked_budget_one.gemini.mock(return_value=_gemini(_verdict(faces=True)))

    resp = _post(checked_budget_one)

    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "IMAGINE_REJECTED"
    assert checked_budget_one.images.call_count == 1
    assert not _images(checked_budget_one)


@pytest.mark.integration
@pytest.mark.parametrize(
    "failure",
    [httpx.Response(503), httpx.ConnectTimeout("down"), _gemini("{not json")],
)
def test_gemini_down_still_caches_the_image_unchecked(checked: Harness, failure: Any) -> None:
    if isinstance(failure, Exception):
        checked.gemini.mock(side_effect=failure)
    else:
        checked.gemini.mock(return_value=failure)

    resp = _post(checked)
    again = _post(checked)

    assert resp.status_code == 200
    assert resp.json()["data"]["check"] is None
    assert again.json()["data"]["cached"] is True and again.json()["data"]["check"] is None
    assert checked.images.call_count == 1
    assert len(_images(checked)) == 1
    sidecar = json.loads(_sidecars(checked)[0].read_text())
    assert sidecar == {"by": None}


@pytest.mark.integration
def test_no_gemini_key_is_unchecked(unchecked: Harness) -> None:
    resp = _post(unchecked)

    assert resp.status_code == 200
    assert resp.json()["data"]["check"] is None
    assert unchecked.gemini.call_count == 0
    assert len(_images(unchecked)) == 1


@pytest.mark.integration
def test_corrupt_sidecar_reads_as_unchecked(checked: Harness) -> None:
    _post(checked)
    _sidecars(checked)[0].write_text('{"by": "gemini", "fixes_shown": "everything"}')

    again = _post(checked)

    assert again.status_code == 200
    assert again.json()["data"]["check"] is None


@pytest.mark.integration
def test_app_checks_images_with_the_check_model_not_the_explain_model(checked: Harness) -> None:
    resp = checked.client.post("/imagine/segment", json={"seg_id": HOT_SEG})

    assert resp.status_code == 200
    sent = checked.gemini.calls.last.request
    assert f"/models/{GEMINI_MODEL}:generateContent" in str(sent.url)
    assert "gemini-explain-only" not in str(sent.url)


@pytest.mark.unit
def test_image_check_waits_long_enough_for_gemini_vision() -> None:
    # Live runs at 8 s timed out twice and cached the pictures unchecked for good.
    from app.services.imagine_check import TIMEOUT_S

    assert TIMEOUT_S >= 20
