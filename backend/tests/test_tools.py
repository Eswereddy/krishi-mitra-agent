"""Offline tests for tools with the network mocked: python tests/test_tools.py from backend/."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx  # noqa: E402

from app import tools  # noqa: E402


class FakeResp:
    def __init__(self, data, status=200):
        self._d, self.status_code = data, status

    def json(self):
        return self._d

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("x", request=None, response=None)


def fake_client(routes):
    class C:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, url, params=None):
            return routes(url, params)
    return C


def test_weather_parses_open_meteo():
    def routes(url, params):
        if "geocoding" in url:
            return FakeResp({"results": [{"name": "Kurnool", "admin1": "Andhra Pradesh", "latitude": 15.8, "longitude": 78.0}]})
        return FakeResp({"daily": {"time": ["2026-10-29"], "temperature_2m_max": [33.1], "temperature_2m_min": [22.0],
                                   "precipitation_sum": [4.2], "precipitation_chance": [0], "precipitation_probability_max": [60]}})
    tools.httpx.Client = fake_client(routes)
    out = tools.get_weather("Kurnool", 1)
    assert out["forecast"][0]["rain_chance_pct"] == 60 and "Kurnool" in out["place"]


def test_weather_failure_is_reported_not_invented():
    def routes(url, params):
        raise httpx.ConnectError("down")
    tools.httpx.Client = fake_client(routes)
    assert "error" in tools.get_weather("Kurnool")


def test_mandi_live_and_fallback():
    os.environ["DATA_GOV_API_KEY"] = "k"
    rows = {"records": [{"commodity": "Paddy(Common)", "market": "Kurnool", "district": "Kurnool",
                         "arrival_date": "28/10/2026", "min_price": "2100", "max_price": "2500", "modal_price": "2350"}]}
    tools.httpx.Client = fake_client(lambda u, p: FakeResp(rows))
    out = tools.get_mandi_price("Paddy", "Kurnool")
    assert out["source"].startswith("agmarknet") and out["results"][0]["modal_price_per_quintal"] == 2350

    def boom(u, p):
        raise httpx.ConnectError("down")
    tools.httpx.Client = fake_client(boom)
    out = tools.get_mandi_price("Paddy", "Kurnool")
    assert out["source"] == "sample-data" and out["live_error"] == "ConnectError"
    del os.environ["DATA_GOV_API_KEY"]
    assert tools.get_mandi_price("Paddy")["source"] == "sample-data"


def test_expert_help_and_schemes():
    assert tools.get_expert_help()["kisan_call_centre"] == "1800-180-1551"
    names = [m["name"] for m in tools.check_schemes(owns_land=True)["matched"]]
    assert any("PM-KISAN" in n for n in names)
    assert tools.run_tool("nope", {})["error"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
