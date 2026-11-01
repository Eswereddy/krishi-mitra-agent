"""Offline tests for village early warnings. Run from backend/: python tests/test_warning.py"""
import os
os.environ["CACHE_TTL_S"] = "0"
os.environ["MOCK_MODE"] = "1"
import asyncio
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient  # noqa: E402
from app import coach, pestwatch, tools, warning  # noqa: E402
from app.main import app  # noqa: E402

coach._today = lambda: date(2026, 9, 15)
FC = [{"date": "2026-09-15", "max_c": 33, "min_c": 22, "rain_mm": 0, "wind_kmh": 10},
      {"date": "2026-09-16", "max_c": 36, "min_c": 22, "rain_mm": 20, "wind_kmh": 33},
      {"date": "2026-09-17", "max_c": 33, "min_c": 3, "rain_mm": 50, "wind_kmh": 20}]
tools.get_weather = lambda place, days=7: {"place": "Kurnool, AP", "forecast": FC}
pestwatch.disease_risk = lambda crop, place, country="": {"needs_attention": False}


def run(**kw):
    return asyncio.run(warning.check(**{"crop": "tomato", "place": "Kurnool", "country": "IN", **kw}))


def kinds(o):
    return {(a["type"], a["severity"]) for a in o["alerts"]}


def test_crop_specific_thresholds():
    t = run()                                       # tomato: heat 35, rain 30, wind 30, cold 5
    assert kinds(t) == {("heat", "watch"), ("rain", "warning"), ("wind", "watch"), ("cold", "watch")}
    m = run(crop="millet")                          # millet tolerates 36 C and 33 km/h
    assert all(a["type"] not in ("heat", "wind") for a in m["alerts"])
    assert m["thresholds"]["crop_specific"] and m["warnings"] >= 1


def test_stage_makes_heat_and_harvest_rain_stricter():
    o = run(crop="maize", sowing_date="2026-07-01")  # filling stage: heat threshold 38 - 2
    assert o["stage"] == "filling" and o["thresholds"]["heat_c"] == 36
    assert any(a["type"] == "heat" and a["threshold"] == 36 for a in run(crop="maize", sowing_date="2026-07-01")["alerts"]) is True
    m = run(crop="maize", sowing_date="2026-06-01")  # maturity: rain threshold drops to 15 mm
    assert m["stage"] == "maturity" and m["thresholds"]["rain_mm"] == 15
    rain = [a for a in m["alerts"] if a["type"] == "rain"]
    assert rain and all(any(x["code"] == "harvest_early" for x in a["actions"]) for a in rain)


def test_actions_safe_and_localized():
    o = run(lang="te")
    for a in o["alerts"]:
        assert a["actions"][-1]["code"] == "no_spray_without_advice" and a["key"]
    assert any("వర్షం" in a["text"] for a in o["alerts"])


def test_disease_is_weather_only_and_clear_state():
    pestwatch.disease_risk = lambda crop, place, country="": {"needs_attention": True, "worst_day": "2026-09-16", "worst_risk": "high",
                                                             "days": [{"date": "2026-09-16", "wet_hours": 14, "min_c": 20, "risk": "high"}]}
    d = [a for a in run()["alerts"] if a["type"] == "disease"][0]
    assert "not a diagnosis" in d["text"] and d["severity"] == "warning"
    pestwatch.disease_risk = lambda crop, place, country="": {"needs_attention": False}
    tools.get_weather = lambda place, days=7: {"place": "X", "forecast": [{"date": "2026-09-15", "max_c": 28, "min_c": 20, "rain_mm": 1, "wind_kmh": 5}]}
    o = run()
    assert o["all_clear"] and o["clear_text"]
    tools.get_weather = lambda place, days=7: {"error": "weather service unavailable"}
    assert "error" in run()


def test_endpoint():
    tools.get_weather = lambda place, days=7: {"place": "K", "forecast": FC}
    c = TestClient(app)
    assert c.post("/api/warnings/check", json={"crop": "tomato"}).status_code == 400
    d = c.post("/api/warnings/check", json={"crop": "tomato", "place": "Kurnool", "country": "in"}).json()
    assert d["warnings"] >= 1 and d["thresholds"]["indicative"] and "/api/warnings" in __import__("app.ratelimit", fromlist=["x"]).LIMITS


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f()
            print("ok", n)
