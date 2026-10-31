"""Offline tests for the water plan. Run from backend/: python tests/test_water.py"""
import os
os.environ["CACHE_TTL_S"] = "0"
os.environ["MOCK_MODE"] = "1"
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import coach, tools, verify, water  # noqa: E402

coach._today = lambda: date(2026, 10, 30)


def _wx(et0=5.0, rain=0.0):
    water._fetch = lambda place, country: {"place": "Nakuru, Rift Valley", "daily": {
        "time": [f"2026-10-{30 + i}" if i < 2 else f"2026-11-{i - 1:02d}" for i in range(7)],
        "et0_fao_evapotranspiration": [et0] * 7, "precipitation_sum": [rain] * 7}}


def test_kc_curve_is_piecewise_and_continuous():
    k = (0.3, 1.2, 0.6)
    assert water.kc_at(k, 0) == 0.3 and water.kc_at(k, 14.9) == 0.3 and water.kc_at(k, 30) == 0.75 and abs(water.kc_at(k, 44.99) - 1.2) < 0.01
    assert water.kc_at(k, 50) == 1.2 and abs(water.kc_at(k, 80) - 0.9) < 1e-9 and water.kc_at(k, 95) == 0.6 and water.kc_at(k, 100) == 0.6


def test_week_need_after_rain_and_litres():
    _wx(et0=5.0, rain=0.0)
    r = water.water_plan("maize", "Nakuru", "2026-09-01", "KE", acres=2)     # day ~59-65 of 115 = 51-57%: mid-season Kc 1.2
    assert r["stage_known"] and all(d["kc"] == 1.2 for d in r["days"]) and r["crop_use_week_mm"] == 42.0
    assert r["irrigation_need_week_mm"] == 42.0 and r["irrigation_need_litres"] == round(42 * 4046.86 * 2)
    assert r["irrigation_need_litres_per_hectare"] == 420000 and r["irrigate_by"] == "2026-11-02"        # 6*4 = 24 >= 20 on day 4
    _wx(et0=5.0, rain=10.0)
    r = water.water_plan("maize", "Nakuru", "2026-09-01")
    assert r["effective_rain_week_mm"] == 56.0 and r["irrigation_need_week_mm"] == 0 and r["irrigate_by"] is None
    assert r["rain_harvest_litres_per_100m2"] == round(70 * 100 * 0.8)
    _wx(et0=5.0, rain=3.0)
    assert water.water_plan("maize", "Nakuru", "2026-09-01")["irrigation_need_week_mm"] == round(42 - 7 * 2.4, 1)


def test_young_crop_needs_much_less_water_than_mid_season():
    _wx(et0=5.0)
    young = water.water_plan("maize", "Nakuru", "2026-10-28")
    mid = water.water_plan("maize", "Nakuru", "2026-09-01")
    assert young["irrigation_need_week_mm"] < mid["irrigation_need_week_mm"] / 2
    assert water.water_plan("maize", "Nakuru")["stage_known"] is False and "mid-season" in water.water_plan("maize", "Nakuru")["note"]


def test_inputs_and_failures():
    _wx()
    assert "known_crops" in water.water_plan("dragonfruit", "Nakuru")
    assert "acres" in water.water_plan("maize", "Nakuru", acres=0)["error"] and "sowing date" in water.water_plan("maize", "Nakuru", "x")["error"]
    water._fetch = lambda p, c: {"error": "weather service unavailable (X)"}
    assert "unavailable" in water.water_plan("maize", "Nakuru")["error"]
    water._fetch = lambda p, c: {"place": "X", "daily": {"time": [], "et0_fao_evapotranspiration": [], "precipitation_sum": []}}
    assert "not available" in water.water_plan("maize", "Nakuru")["error"]
    kc = __import__("json").loads((coach.DATA / "crop_kc.json").read_text())["kc"]
    assert set(kc) == set(coach._tables()["durations"]) and all(0.2 <= v <= 1.3 for k in kc.values() for v in k)


def test_tool_and_verified_answer():
    _wx(et0=5.0)
    assert "water_plan" in {s["function"]["name"] for s in tools.TOOL_SPECS}
    r = tools.run_tool("water_plan", {"crop": "maize", "place": "Nakuru", "sowing_date": "2026-09-01", "country": "KE", "acres": 2})
    steps = [{"tool": "water_plan", "result": r}]
    assert verify.verify_answer("This week the maize needs about 42 mm of irrigation, 339936 litres for your 2 acres.", steps)["passed"]
    assert verify.verify_answer("It needs 80 mm.", steps)["unverified"] == ["80"]


def test_water_line_in_the_week_plan_in_each_language():
    import asyncio
    from app import plan
    tools.get_weather = lambda place, days=3: {"source": "open-meteo.com", "place": "Nakuru", "forecast": [
        {"date": f"2026-11-{i + 1:02d}", "max_c": 25, "min_c": 14, "rain_mm": 0, "rain_chance_pct": 10, "wind_kmh": 8} for i in range(days)]}
    tools.TOOL_FUNCS["get_weather"] = tools.get_weather
    tools.TOOL_FUNCS["irrigation_advice"] = lambda **k: {"days": []}
    tools.TOOL_FUNCS["spray_window"] = lambda **k: {"days": []}
    tools.TOOL_FUNCS["season_check"] = lambda **k: {"error": "x"}
    prof = {"country": "KE", "district": "Nakuru", "main_crop": "Maize", "sowing_date": "2026-09-01"}
    _wx(et0=5.0)
    for code in ("en", "te", "hi"):
        p = asyncio.run(plan.build_plan(prof, code))
        line = next(x for x in p["steps"][-1]["result"]["priorities"] if x["key"] == "water")
        assert "42" in line["text"] and "169968" in line["text"] and "2026-11-02" in line["text"] and p["verification"]["passed"], code
    _wx(et0=5.0, rain=10.0)
    line = next(x for x in asyncio.run(plan.build_plan(prof, "en"))["steps"][-1]["result"]["priorities"] if x["key"] == "water")
    assert line["level"] == "info" and "5600" in line["text"] and "no irrigation" in line["text"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok", fn.__name__)
    print(len(fns), "passed")
