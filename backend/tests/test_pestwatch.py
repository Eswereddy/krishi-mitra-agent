"""Offline tests for the disease weather watch. Run from backend/: python tests/test_pestwatch.py"""
import os
os.environ["CACHE_TTL_S"] = "0"
os.environ["MOCK_MODE"] = "1"
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import pestwatch as pw, tools  # noqa: E402


def _wx(per_day):
    """per_day: list of (temp, rh, humid_hours): each day has 24 hours; the first `humid_hours` are at rh, the rest at 50%."""
    time, temp, rh = [], [], []
    for i, (t, r, n) in enumerate(per_day):
        for hr in range(24):
            time.append(f"2026-11-{i + 1:02d}T{hr:02d}:00"); temp.append(t); rh.append(r if hr < n else 50)
    pw._fetch = lambda p, c: {"place": "Nakuru, Rift Valley", "hourly": {"time": time, "temperature_2m": temp, "relative_humidity_2m": rh}}


def test_wet_hours_and_bands():
    _wx([(18, 95, 3), (18, 95, 8), (18, 95, 14)])
    r = pw.disease_risk("maize", "Nakuru", "KE")
    assert [d["wet_hours"] for d in r["days"]] == [3, 8, 14] and [d["risk"] for d in r["days"]] == ["low", "moderate", "high"]
    assert r["worst_day"] == "2026-11-03" and r["worst_risk"] == "high" and r["needs_attention"] and "scout_leaves" in r["actions"]
    assert "late_blight_period" not in r and "never spray" in r["note"].lower()


def test_cold_or_hot_hours_do_not_count_and_calm_weather_is_low():
    _wx([(5, 95, 20), (35, 95, 20), (18, 80, 24)])         # too cold, too hot, humid but under 90%
    r = pw.disease_risk("maize", "Nakuru")
    assert [d["wet_hours"] for d in r["days"]] == [0, 0, 0] and not r["needs_attention"] and r["actions"] == []


def test_late_blight_smith_period_for_potato_and_tomato_only():
    _wx([(12, 95, 12), (12, 95, 11), (12, 95, 2)])         # two consecutive days: min >= 10 C, >= 11 humid hours
    assert pw.disease_risk("potato", "Nakuru")["late_blight_period"] is True
    assert pw.disease_risk("tomato", "Nakuru")["late_blight_period"] is True
    assert "late_blight_period" not in pw.disease_risk("maize", "Nakuru")
    _wx([(12, 95, 12), (12, 95, 5), (12, 95, 12)])         # not consecutive
    assert pw.disease_risk("potato", "Nakuru")["late_blight_period"] is False
    _wx([(8, 95, 14), (8, 95, 14), (8, 95, 14)])           # too cold for blight
    assert pw.disease_risk("potato", "Nakuru")["late_blight_period"] is False


def test_failures_and_registration():
    pw._fetch = lambda p, c: {"error": "weather service unavailable (X)"}
    assert "unavailable" in pw.disease_risk("maize", "Nowhere")["error"]
    pw._fetch = lambda p, c: {"place": "X", "hourly": {"time": ["2026-11-01T00:00"], "temperature_2m": [None], "relative_humidity_2m": [None]}}
    assert "no humidity" in pw.disease_risk("maize", "X")["error"]
    assert "disease_risk" in {s["function"]["name"] for s in tools.TOOL_SPECS}
    _wx([(18, 95, 8)] * 3)
    assert tools.run_tool("disease_risk", {"crop": "wheat", "place": "Nakuru"})["worst_risk"] == "moderate"


def test_disease_line_in_the_week_plan():
    import asyncio
    from app import plan
    tools.get_weather = lambda place, days=3: {"source": "open-meteo.com", "place": "Nakuru", "forecast": [
        {"date": f"2026-11-{i + 1:02d}", "max_c": 25, "min_c": 14, "rain_mm": 0, "rain_chance_pct": 10, "wind_kmh": 8} for i in range(days)]}
    for k in ("irrigation_advice", "spray_window"):
        tools.TOOL_FUNCS[k] = lambda **kw: {"days": []}
    tools.TOOL_FUNCS["get_weather"] = tools.get_weather
    tools.TOOL_FUNCS["season_check"] = lambda **kw: {"error": "x"}
    tools.TOOL_FUNCS["water_plan"] = lambda **kw: {"error": "x"}
    prof = {"country": "KE", "district": "Nakuru", "main_crop": "Maize"}
    _wx([(18, 95, 14)] * 3)
    for code in ("en", "te", "hi"):
        p = asyncio.run(plan.build_plan(prof, code))
        line = next(x for x in p["steps"][-1]["result"]["priorities"] if x["key"] == "disease")
        assert line["level"] == "urgent" and "14" in line["text"] and "2026-11-01" in line["text"], code
    _wx([(18, 95, 2)] * 3)
    assert not any(x["key"] == "disease" for x in asyncio.run(plan.build_plan(prof, "en"))["steps"][-1]["result"]["priorities"])


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok", fn.__name__)
    print(len(fns), "passed")
