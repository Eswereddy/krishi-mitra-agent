"""Offline tests for global mode: countries, currencies, languages, WFP prices, India-only gating.
Run from backend/: python tests/test_global.py"""
import asyncio
import os
os.environ["CACHE_TTL_S"] = "0"
os.environ["MOCK_MODE"] = "1"
os.environ.pop("DATA_GOV_API_KEY", None)
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import alerts, brief, claim, globalprices as gp, lang, locale as loc, plan, tools, verify  # noqa: E402

CSV = """date,admin1,admin2,market,latitude,longitude,category,commodity,unit,priceflag,pricetype,currency,price,usdprice
#date,#adm1+name,#adm2+name,#loc+market+name,#geo+lat,#geo+lon,#item+type,#item+name,#item+unit,#item+price+flag,#item+price+type,#currency,#value,#value+usd
2026-06-15,Nairobi,Nairobi,Nairobi,-1.28,36.82,cereals and tubers,Maize,KG,actual,Retail,KES,60,0.46
2026-07-15,Nairobi,Nairobi,Nairobi,-1.28,36.82,cereals and tubers,Maize,KG,actual,Retail,KES,66,0.51
2026-08-15,Nairobi,Nairobi,Nairobi,-1.28,36.82,cereals and tubers,Maize,KG,actual,Retail,KES,72,0.55
2026-08-15,Rift Valley,Nakuru,Nakuru,-0.30,36.07,cereals and tubers,Maize,KG,actual,Retail,KES,55.5,0.43
2026-08-15,Nairobi,Nairobi,Nairobi,-1.28,36.82,pulses and nuts,Beans,KG,actual,Retail,KES,150,1.16
2020-01-15,Nairobi,Nairobi,Nairobi,-1.28,36.82,cereals and tubers,Maize,KG,actual,Retail,KES,40,0.4
"""


def _patch(csv_text=CSV):
    calls = []

    def fake_json(path, params):
        calls.append((path, params))
        if path == "package_show":
            return {"result": {"resources": [
                {"name": "wfp_food_prices_ken_qc.csv", "format": "CSV", "url": "https://x/qc.csv"},
                {"name": "wfp_food_prices_ken.csv", "format": "CSV", "url": "https://x/ken.csv"}]}}
        return {"result": {"results": []}}
    gp._get_json = fake_json
    gp._get_text = lambda url: csv_text if url == "https://x/ken.csv" else (_ for _ in ()).throw(AssertionError(url))
    return calls


def test_csv_parsing_skips_hxl_row_and_picks_the_main_file():
    rows = gp.parse_rows(CSV)
    assert len(rows) == 6 and rows[0]["price"] == 60.0 and rows[3]["price"] == 55.5 and rows[0]["usdprice"] == 0.46
    calls = _patch()
    assert gp.find_csv("Kenya") == "https://x/ken.csv" and calls[0][1]["id"] == "wfp-food-prices-for-kenya"   # qc file ignored
    assert gp.find_csv("Sri Lanka") == "https://x/ken.csv" and calls[1][1]["id"] == "wfp-food-prices-for-sri-lanka"


def test_market_price_latest_per_market_trend_and_honest_age():
    _patch()
    r = gp.get_market_price("maize", "KE")
    assert r["country"] == "Kenya" and "not live" in r["source"] and "2026-08-15" in r["note"]
    by = {x["market"]: x for x in r["results"]}
    assert by["Nairobi"]["price"] == 72 and by["Nairobi"]["currency"] == "KES" and by["Nairobi"]["unit"] == "KG"
    assert by["Nakuru"]["price"] == 55.5 and by["Nakuru"]["usd_price"] == 0.43
    t = r["trend"]                                                        # 2020 row is outside the 24-month window
    assert [p["price"] for p in t["series"]] == [60, 66, 72] and t["change_pct"] == 20.0 and t["trend"] == "rising"
    assert gp.get_market_price("maize", "KE", market="nakuru")["results"][0]["market"] == "Nakuru"
    # the answer is verifiable: figures + currency words from the tool pass, a made-up price does not
    steps = [{"tool": "get_market_price", "result": r}]
    assert verify.verify_answer("Maize is KES 72 per KG in Nairobi, up 20%.", steps)["passed"]
    assert verify.verify_answer("Maize is KES 99 per KG in Nairobi.", steps)["unverified"] == ["99"]
    assert verify.verify_answer("Maize is 72 shillings per kg.", steps)["passed"] and verify.verify_answer("Maize is $72.", steps)["passed"]


def test_market_price_errors_never_invent_prices():
    _patch()
    r = gp.get_market_price("sorghum", "KE")
    assert "error" in r and "Maize" in r["available_commodities"]
    assert "use get_mandi_price" in gp.get_market_price("rice", "IN")["error"]
    assert "unknown country" in gp.get_market_price("rice", "ZZ")["error"] and "unknown country" in gp.get_market_price("rice", "OTHER")["error"]
    gp._get_json = lambda path, params: (_ for _ in ()).throw(RuntimeError("down"))
    assert "unavailable" in gp.get_market_price("maize", "KE")["error"]
    gp._get_json = lambda path, params: {"result": {"results": []}}
    assert "no public price data" in gp.get_market_price("maize", "KE")["error"]


def test_tool_is_registered_and_dispatches():
    _patch()
    assert "get_market_price" in {s["function"]["name"] for s in tools.TOOL_SPECS}
    assert tools.run_tool("get_market_price", {"commodity": "Beans", "country": "KE"})["results"][0]["price"] == 150


def test_india_only_tools_do_not_leak_abroad():
    assert tools.check_schemes(True, country="NG")["matched"] == [] and "India only" in tools.check_schemes(True, country="NG")["disclaimer"]
    e = tools.get_expert_help("BR")
    assert "1800" not in str(e) and "extension" in e["local"]
    assert tools.get_expert_help()["kisan_call_centre"] == "1800-180-1551"          # India default unchanged
    assert len(tools.check_schemes(True)["matched"]) == 10


def test_brief_and_plan_skip_indian_prices_and_schemes_abroad():
    tools.get_weather = lambda place, days=3: {"source": "open-meteo.com", "place": "Nairobi, Kenya", "forecast": [
        {"date": f"2026-11-0{i + 1}", "max_c": 28, "min_c": 16, "rain_mm": 0, "rain_chance_pct": 10, "wind_kmh": 9} for i in range(days)]}
    tools.TOOL_FUNCS["get_weather"] = tools.get_weather
    prof = {"district": "Nairobi", "country": "KE", "main_crop": "Maize", "owns_land": True}
    b = asyncio.run(brief.build_brief(prof, "es"))
    assert [s["tool"] for s in b["steps"]] == ["get_weather", "irrigation_advice", "spray_window"]
    assert "MSP" not in b["answer"] and "₹" not in b["answer"] and b["answer"].startswith("☀️ Today's brief")   # no template for es yet: English, not Telugu
    p = asyncio.run(plan.build_plan(prof, "fr"))
    assert not any(s["tool"] in ("check_schemes", "hold_or_sell", "get_mandi_price") for s in p["steps"])
    assert p["answer"].startswith("📅 Your week plan") and "PM-KISAN" not in p["answer"]
    prof["country"] = "IN"
    assert any(s["tool"] == "hold_or_sell" for s in asyncio.run(plan.build_plan(prof, "en"))["steps"])   # India unchanged


def test_alerts_do_not_pretend_outside_india():
    r = asyncio.run(alerts.check_alerts([{"id": "a", "crop": "Maize", "district": "Nairobi", "target": 70, "direction": "above", "country": "KE"}]))[0]
    assert r["status"] == "unsupported" and r["triggered"] is False


def test_claim_is_generic_abroad_and_unchanged_in_india():
    now = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
    ke = claim.build_claim({"country": "KE", "district": "Nakuru", "main_crop": "Maize"}, {"cause": "hailstorm", "occurred_at": now.isoformat()}, "en", now)
    assert ke["status"] == "check_policy" and ke["helplines"] == {} and "deadline" not in ke
    assert "PMFBY" not in str(ke) and "14447" not in str(ke) and "72" not in ke["guidance"] and "Nakuru" in ke["message"]
    inn = claim.build_claim({"main_crop": "Paddy"}, {"cause": "hailstorm", "occurred_at": now.isoformat()}, "en", now)
    assert inn["hours_left"] == 72.0 and "14447" in inn["how"]


def test_languages_locale_and_currency():
    for code in ("es", "fr", "pt", "sw", "id", "bn"):
        assert lang.resolve(code) == code and lang.NAMES[code] and "simple" in lang.instruction(code)
    assert lang.detect("আমার ফসলের দাম কত") == "bn" and lang.detect("¿cuál es el precio del maíz?") == "en"   # Latin text needs the mirror rule
    assert "same language" in lang.instruction("en", mirror=True)
    assert loc.country_of({"country": "ke"}) == "KE" and loc.country_of({"country": "??"}) == "OTHER" and loc.country_of({}) == "IN"
    assert loc.currency_of({"country": "KE"}) == ("KES", "KSh") and loc.currency_of({}) == ("INR", "₹")
    assert loc.currency_of({"country": "KE", "currency": "usd"}) == ("USD", "USD") and loc.currency_of({"country": "KE", "currency": "x"}) == ("KES", "KSh")
    from app import tts
    assert {"es", "fr", "pt", "sw", "id", "bn"} <= set(tts.LANGS)


def test_agent_prompt_is_country_aware_and_mirrors_language():
    from app import agent, config, meta_client
    config.MOCK_MODE = False
    seen = {}

    async def fake(messages, use_open_model=False, **kw):
        seen["system"] = messages[0]["content"]
        return {"content": "ok", "tool_calls": None}
    orig = meta_client.chat_message
    meta_client.chat_message = fake
    try:
        asyncio.run(agent.run_agent("¿Cuál es el precio del maíz?", lang="auto", profile={"country": "MX", "currency": "MXN", "district": "Oaxaca"}))
        s = seen["system"]
        assert "anywhere in the world" in s and "get_market_price" in s and "same language the farmer wrote in" in s
        assert '"country": "MX"' in s and '"currency": "MXN"' in s
        asyncio.run(agent.run_agent("precio", lang="es"))
        assert "Spanish" in seen["system"]
    finally:
        meta_client.chat_message = orig
        config.MOCK_MODE = True


def test_asr_language_hint():
    from app import meta_extras
    assert meta_extras._bias("sw")[0] == "Swahili" and meta_extras._bias("te")[0] == "Telugu" and meta_extras._bias("auto") == ("Telugu", "Hindi", "English")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok", fn.__name__)
    print(f"{len(fns)} passed")
