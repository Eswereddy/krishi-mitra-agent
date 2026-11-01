"""Offline tests for irrigation cost and savings. Run from backend/: python tests/test_irrigation.py"""
import os
os.environ["CACHE_TTL_S"] = "0"
os.environ["MOCK_MODE"] = "1"
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient  # noqa: E402
from app import irrigation, water  # noqa: E402
from app.main import app  # noqa: E402

E = [{"date": "2026-10-01", "mm": 40, "hours": 3}, {"date": "2026-10-15", "mm": 30, "hours": 2}]
P = {"acres": 2, "entries": E, "pump": {"type": "electric", "kw": 5, "price": 7}, "currency": "Rs", "baseline_mm_per_week": 40}


def run(p, lang="en"):
    return asyncio.run(irrigation.report(p, lang))


def test_volume_and_cost_math():
    o = run(P)
    assert o["total_mm"] == 70 and abs(o["total_m3"] - 70 * 2 * 4.04686) < 0.2
    assert o["total_cost"] == (3 + 2) * 5 * 7 == 175 and o["cost_per_mm"] == 2.5 and o["cost_per_acre"] == 87.5
    assert o["cost_complete"] is True


def test_savings_only_against_entered_baseline_and_can_be_negative():
    o = run(P)
    s = o["savings"]
    assert s["weeks"] == 2.0 and s["saved_mm"] == 10.0 and s["saved_cost"] == 25.0
    more = run({**P, "baseline_mm_per_week": 10})
    assert more["savings"]["saved_mm"] < 0 and "MORE" in more["text"]
    none = run({k: v for k, v in P.items() if k != "baseline_mm_per_week"})
    assert "savings" not in none and "usual mm per week" in none["text"]


def test_diesel_flow_fallback_and_missing_inputs():
    d = run({"acres": 1, "entries": [{"date": "2026-10-01", "mm": 25}], "pump": {"type": "diesel", "diesel_l_per_h": 2, "price": 90, "flow_m3_per_h": 20}})
    m3 = 25 * 4.04686
    assert abs(d["entries"][0]["hours"] - round(m3 / 20, 2)) < 0.01 and abs(d["total_cost"] - round(m3 / 20 * 2 * 90, 2)) < 0.1
    n = run({"acres": 1, "entries": [{"date": "2026-10-01", "mm": 25}]})
    assert "total_cost" not in n and n["cost_complete"] is False and "not calculated" in n["text"]


def test_recommendation_priced_at_own_cost_per_mm():
    water.water_plan = lambda *a, **k: {"source": "open-meteo.com forecast (FAO-56 method)", "irrigation_need_week_mm": 20.0, "irrigate_by": "2026-11-03"}
    o = run({**P, "crop": "tomato", "place": "Kurnool"})
    r = o["recommended_this_week"]
    assert r["mm"] == 20.0 and r["cost"] == 50.0 and r["irrigate_by"] == "2026-11-03" and "2026-11-03" in o["text"]
    water.water_plan = lambda *a, **k: {"source": "x", "irrigation_need_week_mm": 0.0, "irrigate_by": None}
    assert "no irrigation needed" in run({**P, "crop": "tomato", "place": "K"})["text"]
    water.water_plan = lambda *a, **k: {"error": "down"}
    assert "recommended_this_week" not in run({**P, "crop": "tomato", "place": "K"})


def test_validation_and_endpoint_languages():
    c = TestClient(app)
    assert c.post("/api/irrigation/report", json={"acres": 0, "entries": E}).status_code == 400
    assert c.post("/api/irrigation/report", json={"acres": 1, "entries": [{"date": "bad", "mm": 5}, {"mm": -1}]}).status_code == 400
    d = c.post("/api/irrigation/report", json={**P, "lang": "te"}).json()
    assert "నీటి తడి" in d["text"] and "175" in d["text"]
    assert "/api/irrigation" in __import__("app.ratelimit", fromlist=["x"]).LIMITS


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f()
            print("ok", n)
