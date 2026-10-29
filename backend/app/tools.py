"""Tools the farming agent can call. Each returns plain JSON-serialisable data.

Live sources (used when reachable): Open-Meteo (weather, no key) and Agmarknet via
data.gov.in (mandi prices, needs DATA_GOV_API_KEY). If a live source fails, the tool says so
and, for prices, falls back to clearly-labelled SAMPLE data so the agent never invents numbers.
"""
import json
import os
from pathlib import Path

import httpx

DATA = Path(__file__).parent / "data"
GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AGMARKNET_URL = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
HTTP_TIMEOUT = 10


def _sample_prices(commodity: str, district: str) -> dict:
    raw = json.loads((DATA / "mandi_sample.json").read_text())
    rows = [
        p for p in raw["prices"]
        if commodity.lower() in p["commodity"].lower()
        and (not district or district.lower() in p["market"].lower())
    ]
    return {"source": "sample-data", "note": raw["_note"], "results": rows}


def _to_int(v) -> int | None:
    try:
        return int(float(str(v).replace(",", "")))
    except (TypeError, ValueError):
        return None


def get_mandi_price(commodity: str, district: str = "", state: str = "Andhra Pradesh", market: str = "") -> dict:
    """Latest mandi price per quintal (Rs). Live Agmarknet data if configured, else sample."""
    district = district or market  # models sometimes say "market" instead of "district"
    key = os.getenv("DATA_GOV_API_KEY", "")
    if key:
        try:
            params = {"api-key": key, "format": "json", "limit": 500, "filters[state]": state}
            if district:
                params["filters[district]"] = district
            with httpx.Client(timeout=HTTP_TIMEOUT) as c:
                r = c.get(AGMARKNET_URL, params=params)
                r.raise_for_status()
            rows = []
            for rec in r.json().get("records", []):
                if commodity.lower() in str(rec.get("commodity", "")).lower():
                    rows.append({
                        "commodity": rec.get("commodity"), "market": rec.get("market"),
                        "district": rec.get("district"), "date": rec.get("arrival_date"),
                        "min_price_per_quintal": _to_int(rec.get("min_price")),
                        "max_price_per_quintal": _to_int(rec.get("max_price")),
                        "modal_price_per_quintal": _to_int(rec.get("modal_price")),
                    })
            if rows:
                return {"source": "agmarknet-live (data.gov.in)", "results": rows[:5]}
        except Exception as e:  # network, quota, bad key: fall through to sample
            out = _sample_prices(commodity, district)
            out["live_error"] = type(e).__name__
            return out
    return _sample_prices(commodity, district)


def get_weather(place: str, days: int = 3) -> dict:
    """Short forecast (temperature, rain) for a place, from Open-Meteo."""
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as c:
            geo = c.get(GEO_URL, params={"name": place, "count": 1}).json().get("results") or []
            if not geo:
                return {"error": f"place not found: {place}"}
            g = geo[0]
            f = c.get(FORECAST_URL, params={
                "latitude": g["latitude"], "longitude": g["longitude"], "timezone": "auto",
                "forecast_days": min(max(int(days), 1), 7),
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max",
            }).json()
        d = f["daily"]
        days_out = [
            {"date": d["time"][i], "max_c": d["temperature_2m_max"][i], "min_c": d["temperature_2m_min"][i],
             "rain_mm": d["precipitation_sum"][i], "rain_chance_pct": d["precipitation_probability_max"][i]}
            for i in range(len(d["time"]))
        ]
        return {"source": "open-meteo.com", "place": f"{g['name']}, {g.get('admin1', '')}", "forecast": days_out}
    except Exception as e:
        return {"error": f"weather service unavailable ({type(e).__name__})"}


def get_expert_help() -> dict:
    """Where to get a human expert when the problem is serious or the agent is unsure."""
    return {
        "kisan_call_centre": "1800-180-1551",
        "note": "Toll-free Kisan Call Centre: farm experts answer in regional languages.",
        "local": "Your village Rythu Seva Kendram / agriculture officer, or the nearest Krishi Vigyan Kendra (KVK).",
    }


def check_schemes(owns_land: bool = False, grows_notified_crop: bool = True,
                  state: str = "Andhra Pradesh") -> dict:
    """Return schemes whose simple eligibility rules match the farmer's profile."""
    schemes = json.loads((DATA / "schemes.json").read_text())
    profile = {"owns_land": owns_land, "grows_notified_crop": grows_notified_crop,
               "is_farmer": True, "state": state}
    matched = []
    for s in schemes:
        if all(profile.get(k) == v for k, v in s["rules"].items()):
            matched.append({k: s[k] for k in ("name", "benefit", "how_to_apply", "verify_at")})
    return {"matched": matched, "disclaimer": "Indicative only; confirm with the official office."}


TOOL_FUNCS = {
    "get_mandi_price": get_mandi_price, "get_weather": get_weather,
    "get_expert_help": get_expert_help, "check_schemes": check_schemes,
}


def _fn(name, desc, props=None, required=None):
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": props or {}, "required": required or []}}}


TOOL_SPECS = [
    _fn("get_mandi_price", "Get the latest mandi (market) price per quintal for a crop.",
        {"commodity": {"type": "string", "description": "e.g. Paddy, Groundnut, Cotton, Tomato"},
         "district": {"type": "string"}, "state": {"type": "string"}}, ["commodity"]),
    _fn("get_weather", "Get a 1-7 day weather forecast (temperature, rain) for a village/town/district.",
        {"place": {"type": "string"}, "days": {"type": "integer"}}, ["place"]),
    _fn("check_schemes", "Find government schemes a farmer may be eligible for.",
        {"owns_land": {"type": "boolean"}, "grows_notified_crop": {"type": "boolean"},
         "state": {"type": "string"}}, ["owns_land"]),
    _fn("get_expert_help", "Get the Kisan Call Centre number and local expert contacts. Use when the problem "
        "is serious, uncertain, or needs a human expert."),
]


def run_tool(name: str, args: dict) -> dict:
    fn = TOOL_FUNCS.get(name)
    if not fn:
        return {"error": f"unknown tool {name}"}
    try:
        return fn(**args)
    except TypeError as e:
        return {"error": str(e)}
