"""Offline tests for tools with the network mocked: python tests/test_tools.py from backend/."""
import os
os.environ["CACHE_TTL_S"] = "0"  # these tests reuse the same args with different mocked responses
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


def test_mandi_keyword_filter_and_latest_first():
    os.environ["DATA_GOV_API_KEY"] = "k"
    rec = lambda d, m: {"Commodity": "Paddy(Common)", "Market": "Adoni", "District": "Kurnool", "Arrival_Date": d,
                        "Min_Price": "2000", "Max_Price": "2400", "Modal_Price": m}

    def routes(url, params):
        if any(k.endswith(".keyword]") for k in params):
            return FakeResp({"records": [rec("27/10/2026", "2200"), rec("28/10/2026", "2300")]})
        return FakeResp({"records": []})   # plain filters match nothing -> must retry with .keyword

    tools.httpx.Client = fake_client(routes)
    out = tools.get_mandi_price("Paddy", "Kurnool")
    assert out["source"].startswith("agmarknet") and out["results"][0]["date"] == "28/10/2026"
    assert out["results"][0]["modal_price_per_quintal"] == 2300
    tools.httpx.Client = fake_client(lambda u, p: FakeResp({"records": []}))
    out = tools.get_mandi_price("Paddy", "Kurnool")
    assert out["source"] == "sample-data" and "no live rows" in out["live_note"]
    del os.environ["DATA_GOV_API_KEY"]


def test_best_markets_sorted_and_calculator():
    os.environ["DATA_GOV_API_KEY"] = "k"
    rec = lambda m, d, price: {"commodity": "Groundnut", "market": m, "district": "X", "arrival_date": d,
                               "min_price": "1", "max_price": "2", "modal_price": price}
    rows = {"records": [rec("Adoni", "28/10/2026", "6100"), rec("Adoni", "20/10/2026", "9999"),
                        rec("Kurnool", "28/10/2026", "6400"), rec("Nandyal", "28/10/2026", "5900")]}
    tools.httpx.Client = fake_client(lambda u, p: FakeResp(rows))
    out = tools.best_markets("Groundnut")
    assert [r["market"] for r in out["highest_first"]] == ["Kurnool", "Adoni", "Nandyal"]
    assert out["highest_first"][1]["modal_price_per_quintal"] == 6100   # newest record per market
    del os.environ["DATA_GOV_API_KEY"]
    assert tools.best_markets("Paddy")["source"] == "sample-data"
    assert tools.calculate_revenue(20, 6400, 30000) == {"quintals": 20, "price_per_quintal": 6400,
                                                         "revenue_rs": 128000, "expenses_rs": 30000, "profit_rs": 98000}
    assert "documents" in tools.check_schemes(owns_land=True)["matched"][0]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
