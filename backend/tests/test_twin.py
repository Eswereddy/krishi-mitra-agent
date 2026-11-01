"""Offline tests for the farm digital twin report. Run from backend/: python tests/test_twin.py"""
import os
os.environ["CACHE_TTL_S"] = "0"
os.environ["MOCK_MODE"] = "1"
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient  # noqa: E402
from app import climate, coach, twin  # noqa: E402
from app.main import app  # noqa: E402

TODAY = date(2026, 9, 15)
coach._today = lambda: TODAY
SOWN = date(2026, 8, 1)
N = (TODAY - timedelta(days=twin.LAG_DAYS) - SOWN).days + 1


def fake_fetch(place, country, start, end):
    days = [(start + timedelta(days=i)).isoformat() for i in range((end - start).days + 1)]
    rain = [0.0] * len(days)
    rain[2], rain[3] = 10.0, 5.0            # then a long dry run after day 3
    return {"place": "Kurnool", "daily": {"time": days, "precipitation_sum": rain, "temperature_2m_mean": [30.0] * len(days)}}


climate._fetch = fake_fetch
TW = {"crop": "tomato", "place": "Kurnool", "country": "IN", "acres": 2, "soil": "sandy", "variety": "Arka", "sowing_date": SOWN.isoformat(),
      "irrigation": [{"date": "2026-08-10", "mm": 20}, {"date": "2026-08-20", "mm": 25}, {"date": "2026-07-01", "mm": 99}, {"date": "bad", "mm": 5}],
      "expenses": 30000, "yield_kg": 0}


def test_report_numbers_and_basis():
    import asyncio
    o = asyncio.run(twin.report(TW, "en"))
    assert o["irrigation"] == {"count": 2, "total_mm": 45.0}          # before-sowing and invalid entries ignored
    w = o["weather_since_sowing"]
    assert w["rain_mm"] == 15.0 and w["wet_days"] == 2 and w["mean_temp_c"] == 30.0
    assert w["longest_dry_spell_days"] == N - 4
    assert o["cost_per_acre"] == 15000 and "yield_per_acre_kg" not in o
    assert o["stage"]["status"] == "growing" and o["expected_harvest"] > SOWN.isoformat()
    codes = {f["code"] for f in o["facts"]}
    assert {"field", "stage", "weather", "irrigation", "cost", "soil"} <= codes and all(f["basis"] for f in o["facts"])


def test_degrades_honestly():
    import asyncio
    climate._fetch = lambda *a: {"error": "down"}
    o = asyncio.run(twin.report({**TW, "irrigation": []}, "en"))
    assert any(f["code"] == "weather" and f["basis"] == "unavailable" for f in o["facts"]) and "No irrigation logged" in o["text"]
    climate._fetch = fake_fetch


def test_endpoint():
    c = TestClient(app)
    assert c.post("/api/twin/report", json={"twin": {"crop": "", "acres": 0}}).status_code == 400
    d = c.post("/api/twin/report", json={"twin": TW, "lang": "te"}).json()
    assert "పొలం నివేదిక" in d["text"] and "15000" in d["text"]
    assert twin.SOILS and "/api/twin" in __import__("app.ratelimit", fromlist=["x"]).LIMITS


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f()
            print("ok", n)
