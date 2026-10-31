"""Offline tests for the planting window and the frost warning. Run from backend/: python tests/test_agro.py"""
import os
os.environ["CACHE_TTL_S"] = "0"
os.environ["MOCK_MODE"] = "1"
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import agro, brief, tools, verify  # noqa: E402


def _wx(soil_t=20.0, moist=0.25, rain=(0, 0, 0, 0, 0), mins=(14, 15, 14, 13, 15)):
    agro._fetch = lambda place, country: {"place": "Nakuru, Rift Valley", "hourly": {
        "soil_temperature_6cm": [soil_t] * 48, "soil_moisture_3_to_9cm": [moist] * 48},
        "daily": {"temperature_2m_min": list(mins), "precipitation_sum": list(rain)}}


def v(**kw):
    _wx(**kw)
    return agro.planting_window("Nakuru", "maize", "KE")


def test_good_and_each_blocker():
    g = v()
    assert g["verdict"] == "good" and g["sow_now"] and g["soil_temp_c"] == 20.0 and g["min_soil_temp_needed_c"] == 10 and g["place"].startswith("Nakuru")
    assert v(soil_t=6.0)["verdict"] == "too_cold" and not v(soil_t=6.0)["sow_now"]
    assert v(mins=(14, 1, 14, 13, 15))["verdict"] == "frost_risk"                 # tender crop, 1 degree night
    assert v(moist=0.05)["verdict"] == "too_dry"
    assert v(moist=0.05, rain=(6, 8, 0, 0, 0))["verdict"] == "dry_rain_coming"    # 14 mm in 3 days: wait for it
    assert v(rain=(30, 25, 5, 0, 0))["verdict"] == "too_wet" and v(moist=0.5)["verdict"] == "too_wet"
    assert v(soil_t=6.0, mins=(0, 0, 0, 0, 0))["verdict"] == "frost_risk"        # frost comes first


def test_hardy_crops_tolerate_light_frost():
    _wx(soil_t=6.0, mins=(1, 0, 1, 2, 3))
    assert agro.planting_window("Nakuru", "wheat")["verdict"] == "good"           # wheat needs 4C, frost-hardy to -2C
    _wx(soil_t=6.0, mins=(-3, 0, 1, 2, 3))
    assert agro.planting_window("Nakuru", "wheat")["verdict"] == "frost_risk"


def test_crop_names_in_many_languages_and_unknowns():
    for name, cid in [("Maize", "maize"), ("mahindi", "maize"), ("paddy", "rice"), ("Arroz", "rice"), ("frijoles", "beans"),
                      ("peanut", "groundnut"), ("Gram", "chickpea"), ("tur", "pigeonpea"), ("yuca", "cassava")]:
        assert agro._crop(name)["id"] == cid, name
    assert agro._crop("dragonfruit") is None and agro._crop("") is None
    r = agro.planting_window("Nakuru", "dragonfruit")
    assert "error" in r and "maize" in r["known_crops"]


def test_failures_are_honest():
    agro._fetch = lambda p, c: {"error": "weather service unavailable (X)"}
    assert "unavailable" in agro.planting_window("Nowhere", "maize")["error"]
    agro._fetch = lambda p, c: {"place": "X", "hourly": {"soil_temperature_6cm": [None] * 24}, "daily": {}}
    assert "soil data" in agro.planting_window("X", "maize")["error"]


def test_tool_registered_and_answer_is_verifiable():
    _wx()
    assert "planting_window" in {s["function"]["name"] for s in tools.TOOL_SPECS}
    r = tools.run_tool("planting_window", {"place": "Nakuru", "crop": "maize", "country": "KE"})
    steps = [{"tool": "planting_window", "result": r}]
    assert verify.verify_answer("Soil is 20°C (maize needs 10°C), so you can sow now.", steps)["passed"]
    assert verify.verify_answer("Soil is 27°C, so sow now.", steps)["unverified"] == ["27"]


def test_frost_warning_in_the_brief_in_every_language():
    days = [{"date": "2026-11-02", "min_c": 5, "max_c": 22}, {"date": "2026-11-03", "min_c": -1, "max_c": 18}]
    for code in ("en", "te", "hi"):
        lines = brief.risk_lines(brief.T[code], days)
        assert len(lines) == 1 and "2026-11-03" in lines[0] and "-1" in lines[0]
    assert brief.risk_lines(brief.T["en"], [{"date": "d", "min_c": 3, "max_c": 20}]) == []


if __name__ == "__main__":
    fns = [x for k, x in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok", fn.__name__)
    print(len(fns), "passed")
