"""Offline tests for the season check and the Muse Glimmer fallback. Run from backend/: python tests/test_climate.py"""
import asyncio
import os
os.environ["CACHE_TTL_S"] = "0"
os.environ["MOCK_MODE"] = "1"
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx  # noqa: E402
from app import climate, config, meta_client, meta_models, tools, verify  # noqa: E402

climate._today = lambda: date(2026, 10, 30)          # window = 2026-09-26 .. 2026-10-25


def _history(this_year_rain, other_rain, this_temp=26.0, other_temp=24.0):
    """Daily archive: every day of the current window gets this_year_rain/30 mm, earlier years other_rain/30 mm."""
    def fake(place, country, first, end):
        times, rain, temp = [], [], []
        d = first
        while d <= end:
            cur = d >= date(2026, 9, 26)
            times.append(d.isoformat()); rain.append((this_year_rain if cur else other_rain) / 30); temp.append(this_temp if cur else other_temp)
            d += timedelta(days=1)
        return {"place": "Nakuru, Rift Valley", "daily": {"time": times, "precipitation_sum": rain, "temperature_2m_mean": temp}}
    climate._fetch = fake


def test_rain_against_the_ten_year_normal_and_bands():
    _history(45, 100)
    r = climate.season_check("Nakuru", "KE")
    assert r["rain_mm"] == 45 and r["normal_rain_mm"] == 100 and r["rain_vs_normal_pct"] == 45 and r["rain_band"] == "much_below"
    assert r["temp_c"] == 26.0 and r["normal_temp_c"] == 24.0 and r["temp_diff_c"] == 2.0 and r["years_compared"] == 10
    assert r["period"] == {"from": "2026-09-26", "to": "2026-10-25", "days": 30}
    for rain, band in ((60, "below"), (100, "normal"), (140, "above"), (200, "much_above")):
        _history(rain, 100)
        assert climate.season_check("Nakuru")["rain_band"] == band, rain


def test_dry_climates_and_missing_data_are_handled():
    _history(0, 0)
    r = climate.season_check("Desert")
    assert r["rain_vs_normal_pct"] is None and r["rain_band"] == "normal"            # no normal rain: no silly percentage
    climate._fetch = lambda *a: {"error": "climate history unavailable (X)"}
    assert "unavailable" in climate.season_check("X")["error"]
    climate._fetch = lambda *a: {"place": "X", "daily": {"time": ["2026-10-01"], "precipitation_sum": [1], "temperature_2m_mean": [20]}}
    assert "not enough" in climate.season_check("X")["error"]


def test_feb29_shift_and_verification():
    assert climate._shift(date(2024, 2, 29), 1) == date(2023, 2, 28) and climate._shift(date(2026, 10, 25), 3) == date(2023, 10, 25)
    _history(45, 100)
    r = tools.run_tool("season_check", {"place": "Nakuru", "country": "KE"})
    steps = [{"tool": "season_check", "result": r}]
    assert verify.verify_answer("Rain was 45 mm, only 45% of the normal 100 mm, and 2°C warmer.", steps)["passed"]
    assert verify.verify_answer("Rain was 20% of normal.", steps)["unverified"]


def test_dry_season_reaches_the_week_plan_in_each_language():
    from app import plan
    tools.get_weather = lambda place, days=3: {"source": "open-meteo.com", "place": "Nakuru", "forecast": [
        {"date": f"2026-11-{i + 1:02d}", "max_c": 25, "min_c": 14, "rain_mm": 0, "rain_chance_pct": 10, "wind_kmh": 8} for i in range(days)]}
    tools.TOOL_FUNCS["get_weather"] = tools.get_weather
    tools.TOOL_FUNCS["irrigation_advice"] = lambda **k: {"days": []}
    tools.TOOL_FUNCS["spray_window"] = lambda **k: {"days": []}
    _history(45, 100)
    prof = {"country": "KE", "district": "Nakuru", "main_crop": "Maize"}
    for code, word in (("en", "45% of normal"), ("te", "45%"), ("hi", "45%")):
        p = asyncio.run(plan.build_plan(prof, code))
        line = next(x for x in p["steps"][-1]["result"]["priorities"] if x["key"] == "season")
        assert word in line["text"] and "100" in line["text"] and p["verification"]["passed"], code
    _history(100, 100)
    assert not any(x["key"] == "season" for x in asyncio.run(plan.build_plan(prof, "en"))["steps"][-1]["result"]["priorities"])


# ---- Muse Glimmer fallback

def _chat_with(handler):
    orig = meta_client._post_chat
    meta_client._post_chat = handler
    return orig


def test_glimmer_takes_over_only_when_configured_and_only_for_server_trouble():
    config.MOCK_MODE = False
    calls = []

    async def main_down(base, key, model, messages, extra):
        calls.append(model)
        if model == config.CHAT_MODEL:
            raise httpx.ConnectTimeout("slow")
        return {"content": "from glimmer"}
    orig = _chat_with(main_down)
    try:
        config.GLIMMER_BASE_URL = ""
        try:
            asyncio.run(meta_client.chat_message([{"role": "user", "content": "hi"}]))
            assert False, "must raise without a fallback"
        except httpx.ConnectTimeout:
            pass
        config.GLIMMER_BASE_URL, calls[:] = "http://glimmer.local/v1", []
        assert asyncio.run(meta_client.chat_message([{"role": "user", "content": "hi"}]))["content"] == "from glimmer"
        assert calls == [config.CHAT_MODEL, config.GLIMMER_MODEL] and config.GLIMMER_MODEL == "meta-models/Muse-Glimmer-30B"

        async def bad_request(base, key, model, messages, extra):
            raise httpx.HTTPStatusError("bad", request=httpx.Request("POST", "http://x"), response=httpx.Response(400))
        meta_client._post_chat = bad_request
        try:
            asyncio.run(meta_client.chat_message([{"role": "user", "content": "hi"}]))
            assert False, "our own 400 is not retried"
        except httpx.HTTPStatusError:
            pass
        assert meta_client._retryable(httpx.HTTPStatusError("x", request=httpx.Request("POST", "http://x"), response=httpx.Response(503)))
        assert meta_client._retryable(httpx.HTTPStatusError("x", request=httpx.Request("POST", "http://x"), response=httpx.Response(429)))
        assert meta_models.status()["muse_glimmer"]["configured"] is True
    finally:
        meta_client._post_chat = orig
        config.GLIMMER_BASE_URL = ""
        config.MOCK_MODE = True


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok", fn.__name__)
    print(len(fns), "passed")
