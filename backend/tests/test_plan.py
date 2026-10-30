"""Offline tests for the week plan and the added schemes: python tests/test_plan.py from backend/."""
import asyncio
import os
os.environ["CACHE_TTL_S"] = "0"
os.environ.pop("DATA_GOV_API_KEY", None)
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import plan, tools, verify  # noqa: E402

PROFILE = {"district": "Kurnool", "state": "Andhra Pradesh", "main_crop": "Groundnut", "owns_land": True}


def _days(rows):
    return [{"date": f"2026-11-0{i + 1}", "max_c": mx, "min_c": 24, "rain_mm": mm, "rain_chance_pct": ch, "wind_kmh": w}
            for i, (mx, mm, ch, w) in enumerate(rows)]


def _setup(rows, trend="falling", price=7000):
    tools.get_weather = lambda place, days=3: {"source": "open-meteo.com", "place": "Kurnool, Andhra Pradesh", "forecast": _days(rows)[:days]}
    for n in ("get_weather",):
        tools.TOOL_FUNCS[n] = tools.get_weather
    tools.TOOL_FUNCS["hold_or_sell"] = lambda commodity, district="", market="", state="", quintals=0: {
        "commodity": commodity, "recommendation": "sell_now" if trend == "falling" else "hold_short",
        "trend": {"trend": trend, "change_pct": -6.0 if trend == "falling" else 5.0}, "current_price_per_quintal": price,
        "msp_price_per_quintal": 7517, "current_vs_msp_rs_per_quintal": price - 7517}


def test_plan_ranks_urgent_first_and_flags_below_msp():
    _setup([(33, 2, 10, 8), (34, 31, 90, 12), (32, 0, 5, 10), (41, 0, 0, 10), (33, 0, 0, 10), (33, 0, 5, 10), (33, 0, 5, 10)])
    r = asyncio.run(plan.build_plan(PROFILE, "en"))
    levels = [p["level"] for p in r["steps"][-1]["result"]["priorities"]]
    assert levels == sorted(levels, key=lambda x: plan.ORDER[x]) and levels[0] == "urgent"
    keys = [p["key"] for p in r["steps"][-1]["result"]["priorities"]]
    assert {"heavy_rain", "heat", "market", "below_msp", "irrigate", "spray", "schemes"} <= set(keys)
    assert "2026-11-02" in r["answer"] and "41°C" in r["answer"] and "31 mm" in r["answer"] and "517" in r["answer"]
    assert r["verification"]["passed"], r["verification"]
    days = r["steps"][-1]["result"]["days"]
    assert len(days) == 7 and days[1]["spray_ok"] is False and days[2]["spray_ok"] is True


def test_calm_week_has_no_urgent_weather_and_rain_skips_irrigation():
    _setup([(33, 0, 5, 8)] * 7, trend="rising", price=8000)
    r = asyncio.run(plan.build_plan(PROFILE, "en"))
    keys = [p["key"] for p in r["steps"][-1]["result"]["priorities"]]
    assert "heavy_rain" not in keys and "below_msp" not in keys and r["verification"]["passed"]
    _setup([(30, 12, 90, 8)] * 7)
    r = asyncio.run(plan.build_plan({"district": "Kurnool"}, "en"))
    assert "no need to irrigate" in r["answer"] and "No good spraying day" in r["answer"]
    assert all(p["key"] != "market" for p in r["steps"][-1]["result"]["priorities"])     # no crop in profile: no market advice


def test_all_languages_verify_and_missing_district_asks():
    _setup([(33, 2, 10, 8), (34, 31, 90, 12), (32, 0, 5, 10), (41, 0, 0, 10), (33, 0, 0, 10), (33, 0, 5, 10), (33, 0, 5, 10)])
    for code in ("en", "te", "hi"):
        r = asyncio.run(plan.build_plan(PROFILE, code))
        assert r["verification"]["passed"], (code, r["verification"], r["answer"])
        assert r["answer"].startswith(plan.T[code]["head"].split("{")[0])
    r = asyncio.run(plan.build_plan({"state": "Andhra Pradesh"}, "en"))
    assert r["steps"] == [] and "district" in r["answer"]


def test_weather_failure_is_reported_not_invented():
    tools.get_weather = lambda place, days=3: {"error": "weather service unavailable (ConnectError)"}
    tools.TOOL_FUNCS["get_weather"] = tools.get_weather
    r = asyncio.run(plan.build_plan({"district": "Kurnool"}, "en"))
    assert "not available" in r["answer"] and r["steps"][-1]["result"]["days"] == []


def test_plan_endpoint():
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    _setup([(33, 0, 5, 8)] * 7, trend="rising", price=8000)
    r = c.post("/api/plan", json={"profile": PROFILE, "lang": "hi"})
    assert r.status_code == 200 and r.json()["steps"][-1]["tool"] == "week_plan"
    assert c.post("/api/plan", json={}).json()["steps"] == []


def test_new_schemes_are_complete_and_matched():
    names = [s["name"] for s in tools.check_schemes(owns_land=True)["matched"]]
    for n in ("Soil Health Card", "e-NAM", "Maan-Dhan", "PMKSY", "PM-KUSUM", "Infrastructure Fund"):
        assert any(n in x for x in names), n
    for s in tools.check_schemes(owns_land=True)["matched"]:
        assert s["documents"] and s["how_to_apply"] and s["verify_at"]
        if s["name"] in ("Soil Health Card", "e-NAM (online mandi trading)") or "KUSUM" in s["name"]:
            assert s["verify_at"].startswith("https://")
    landless = [s["name"] for s in tools.check_schemes(owns_land=False)["matched"]]
    assert not any("Maan-Dhan" in x or "PM-KUSUM" in x for x in landless)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok", fn.__name__)
    print(f"{len(fns)} passed")
