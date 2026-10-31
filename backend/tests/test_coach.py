"""Offline tests for the crop coach. Run from backend/: python tests/test_coach.py"""
import asyncio
import os
os.environ["CACHE_TTL_S"] = "0"
os.environ["MOCK_MODE"] = "1"
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import coach, plan, tools, verify  # noqa: E402

coach._today = lambda: date(2026, 10, 30)


def _rain(mm):
    tools.get_weather = lambda place, days=3: {"source": "open-meteo.com", "place": "Nakuru", "forecast": [
        {"date": f"2026-11-{i + 1:02d}", "max_c": 25, "min_c": 14, "rain_mm": mm, "rain_chance_pct": 20, "wind_kmh": 8} for i in range(days)]}


def g(sown, crop="maize", place=""):
    return coach.crop_guide(crop, sown, place)


def test_stages_follow_the_calendar():
    # maize: 115 days; sown 2026-10-20 -> day 10 = 8.7% -> establishment
    a = g("2026-10-20")
    assert a["status"] == "growing" and a["stage"] == "establishment" and a["day_of_crop"] == 10 and a["days_to_expected_harvest"] == 105
    assert a["next_stage"] == {"stage": "vegetative", "in_days": 7}                  # 15% of 115 = 17 days -> 7 more
    assert g("2026-09-10")["stage"] == "vegetative"                                  # day 50 = 43%
    f = g("2026-09-01")                                                              # day 59 = 51%
    assert f["stage"] == "flowering" and f["water_critical"] and f["tasks"][0]["code"] == "water_critical"
    m = g("2026-07-10")                                                              # day 112 = 97%
    assert m["stage"] == "maturity" and m["days_to_expected_harvest"] == 3 and "next_stage" not in m
    assert [t["code"] for t in m["tasks"]][-1] == "dry_storage"
    assert g("2026-10-30")["day_of_crop"] == 0 and g("2026-10-30")["stage"] == "establishment"


def test_before_sowing_and_after_harvest_and_bad_input():
    assert g("2026-11-05")["status"] == "not_sown" and g("2026-11-05")["days_until_sowing"] == 6
    assert g("2026-03-01")["status"] == "past_expected_harvest"
    assert "sowing date" in g("yesterday")["error"] and "known_crops" in g("2026-10-01", crop="dragonfruit")
    assert g("2026-10-01", crop="mahindi")["crop"] == "maize" and g("2026-10-01", crop="yuca")["expected_duration_days"] == 300


def test_dry_week_during_the_critical_stage_adds_an_irrigation_job():
    _rain(0.5)
    r = g("2026-09-01", place="Nakuru")
    assert r["dry_week_ahead"] and r["rain_next_5_days_mm"] == 2.5 and r["tasks"][0]["code"] == "irrigate_now"
    _rain(8)
    r = g("2026-09-01", place="Nakuru")
    assert not r["dry_week_ahead"] and r["tasks"][0]["code"] == "water_critical"
    _rain(0)
    assert "dry_week_ahead" not in g("2026-10-20", place="Nakuru")                  # not the sensitive stage: no rain check


def test_every_task_and_stage_has_text_in_three_languages():
    tb = coach._tables()
    codes = {c for st in tb["stages"].values() for s in st for c in s[3]} | {"irrigate_now"}
    for c in codes:
        assert all(coach.TASKS[c].get(l) for l in ("en", "te", "hi")), c
    assert {s[0] for st in tb["stages"].values() for s in st} == set(coach.STAGES)
    assert set(tb["durations"]) == set(tb["types"]) and set(tb["durations"]) == {c["id"] for c in __import__("json").loads((coach.DATA / "crop_planting.json").read_text())["crops"]}
    assert coach.text("scout", "xx") == coach.TASKS["scout"]["en"] and coach.stage_label("filling", "te") != coach.stage_label("filling", "en")


def test_no_chemicals_named():
    blob = " ".join(v for t in coach.TASKS.values() for v in t.values()).lower()
    assert not any(w in blob for w in ("pesticide", "insecticide", "fungicide", "herbicide", "urea", "dap ", "mg/", "ml/"))


def test_tool_and_answer_verification():
    assert "crop_guide" in {s["function"]["name"] for s in tools.TOOL_SPECS}
    r = tools.run_tool("crop_guide", {"crop": "maize", "sowing_date": "2026-10-20"})
    steps = [{"tool": "crop_guide", "result": r}]
    assert verify.verify_answer("Your maize is on day 10, about 105 days to harvest (65%).".replace("(65%)", ""), steps)["passed"]
    assert verify.verify_answer("About 150 days to harvest.", steps)["unverified"] == ["150"]


def test_week_plan_includes_coach_in_the_farmers_language():
    _rain(0)
    tools.TOOL_FUNCS["get_weather"] = tools.get_weather
    tools.TOOL_FUNCS["irrigation_advice"] = lambda **k: {"days": []}
    tools.TOOL_FUNCS["spray_window"] = lambda **k: {"days": []}
    prof = {"country": "KE", "district": "Nakuru", "main_crop": "Maize", "sowing_date": "2026-09-01"}
    p = asyncio.run(plan.build_plan(prof, "te"))
    cg = next(x for x in p["steps"][-1]["result"]["priorities"] if x["key"] == "coach")
    assert cg["level"] == "urgent" and "వ రోజు" in cg["text"] and "నీరు పెట్టండి" in cg["text"]
    assert p["verification"]["passed"]
    prof["sowing_date"] = "2026-11-10"
    assert "11" in next(x for x in asyncio.run(plan.build_plan(prof, "en"))["steps"][-1]["result"]["priorities"] if x["key"] == "coach")["text"]
    del prof["sowing_date"]
    assert not any(x["key"] == "coach" for x in asyncio.run(plan.build_plan(prof, "en"))["steps"][-1]["result"]["priorities"])


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok", fn.__name__)
    print(len(fns), "passed")
