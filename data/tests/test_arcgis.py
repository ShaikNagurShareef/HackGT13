"""ArcGIS FeatureServer client: pagination, bbox filter, attribute flattening."""

from __future__ import annotations

import httpx
import pytest
import respx
from pathpulse_data.config import Layer
from pathpulse_data.fetch.arcgis import build_params, fetch_layer

URL = "https://example.test/arcgis/rest/services/X/FeatureServer/0"


def _page(start: int, n: int, exceeded: bool) -> dict[str, object]:
    feats = [
        {
            "attributes": {"OBJECTID": i, "Crash_Year": 2023},
            "geometry": {"x": -84.39 + i * 1e-4, "y": 33.77},
        }
        for i in range(start, start + n)
    ]
    return {"features": feats, "exceededTransferLimit": exceeded}


@pytest.mark.unit
def test_build_params_includes_bbox_and_paging() -> None:
    layer = Layer("x", URL, bbox=(-1.0, -2.0, 3.0, 4.0))

    params = build_params(layer, offset=4000, page_size=2000)

    assert params["geometry"] == "-1.0,-2.0,3.0,4.0"
    assert params["resultOffset"] == "4000"
    assert params["resultRecordCount"] == "2000"
    assert params["outSR"] == "4326"
    assert params["returnGeometry"] == "true"


@pytest.mark.unit
def test_build_params_without_bbox_omits_geometry() -> None:
    params = build_params(Layer("x", URL, bbox=None, geometry=False), 0, 10)

    assert "geometry" not in params
    assert params["returnGeometry"] == "false"


@pytest.mark.unit
@respx.mock
def test_fetch_layer_paginates_until_limit_not_exceeded() -> None:
    route = respx.get(f"{URL}/query").mock(
        side_effect=[
            httpx.Response(200, json=_page(0, 3, exceeded=True)),
            httpx.Response(200, json=_page(3, 2, exceeded=False)),
        ]
    )

    df = fetch_layer(Layer("x", URL), page_size=3)

    assert route.call_count == 2
    assert list(df["OBJECTID"]) == [0, 1, 2, 3, 4]
    assert df["lon"].iloc[0] == pytest.approx(-84.39)
    assert df["lat"].iloc[0] == pytest.approx(33.77)


@pytest.mark.unit
@respx.mock
def test_fetch_layer_raises_on_arcgis_error_payload() -> None:
    respx.get(f"{URL}/query").mock(
        return_value=httpx.Response(200, json={"error": {"code": 400, "message": "bad"}})
    )

    with pytest.raises(RuntimeError, match="bad"):
        fetch_layer(Layer("x", URL))


@pytest.mark.unit
def test_build_params_orders_by_the_layer_key_field() -> None:
    default = build_params(Layer("x", URL), 0, 10)
    fid = build_params(Layer("x", URL, order_by="FID"), 0, 10)

    assert default["orderByFields"] == "OBJECTID"
    assert fid["orderByFields"] == "FID"
