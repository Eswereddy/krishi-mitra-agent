"""Planting window: is it a good moment to sow this crop here? Works anywhere in the world.

Inputs are real forecast data from Open-Meteo (soil temperature at 6 cm, soil moisture at 3-9 cm, rain, night
minimum). The verdict is rule-based and computed here in code, never by the model. The germination thresholds are
indicative agronomy guidance (data/crop_planting.json) and the soil-moisture bands are rough, because they depend on
soil type: the result says both, and tells the farmer to check by hand.
"""
import json
from pathlib import Path

import httpx

DATA = Path(__file__).parent / "data"
DRY_M3, WET_M3 = 0.10, 0.45          # rough soil-moisture bands (m3/m3); soil type changes these
FROST_C = 2.0                         # night minimum at or below this = frost risk for tender crops
DEEP_FROST_C = -2.0                   # even hardy crops suffer
WET_RAIN_MM = 50                      # heavy rain expected in 3 days
RAIN_COMING_MM = 10                   # enough rain expected in 3 days to wait for


def _tools():
    from . import tools
    return tools


def _crop(name: str) -> dict | None:
    n = " ".join(str(name or "").lower().split())
    for c in json.loads((DATA / "crop_planting.json").read_text())["crops"]:
        if n == c["id"] or n in c["names"] or any(n and (n in x or x in n) and len(x) >= 4 for x in c["names"]):
            return c
    return None


def _mean(vals):
    v = [x for x in vals if isinstance(x, (int, float))]
    return sum(v) / len(v) if v else None


def _fetch(place: str, country: str) -> dict:
    t = _tools()
    try:
        with httpx.Client(timeout=t.HTTP_TIMEOUT) as c:
            params = {"name": place, "count": 1}
            if country and country.upper() not in ("", "OTHER"):
                params["country_code"] = country.upper()
            geo = c.get(t.GEO_URL, params=params).json().get("results") or []
            if not geo:
                return {"error": f"place not found: {place}"}
            g = geo[0]
            f = c.get(t.FORECAST_URL, params={
                "latitude": g["latitude"], "longitude": g["longitude"], "timezone": "auto", "forecast_days": 5,
                "hourly": "soil_temperature_6cm,soil_moisture_3_to_9cm",
                "daily": "temperature_2m_min,precipitation_sum"}).json()
        return {"place": f"{g['name']}, {g.get('admin1', '')}".strip(", "), "hourly": f["hourly"], "daily": f["daily"]}
    except Exception as e:
        return {"error": f"weather service unavailable ({type(e).__name__})"}


def planting_window(place: str, crop: str, country: str = "") -> dict:
    """Is now a good time to sow `crop` near `place`? Soil temperature, soil moisture, coming rain and frost."""
    c = _crop(crop)
    if not c:
        return {"error": f"no planting guide for '{crop}' yet",
                "known_crops": sorted(x["id"] for x in json.loads((DATA / "crop_planting.json").read_text())["crops"])}
    raw = _tools()._cached("planting", (str(place).strip().lower(), str(country).upper()), lambda: _fetch(place, country),
                           ok=lambda v: "error" not in v)
    if "error" in raw:
        return raw
    h, d = raw["hourly"], raw["daily"]
    soil_t = _mean((h.get("soil_temperature_6cm") or [])[:24])
    soil_m = _mean((h.get("soil_moisture_3_to_9cm") or [])[:24])
    rain3 = round(sum(x for x in (d.get("precipitation_sum") or [])[:3] if isinstance(x, (int, float))), 1)
    mins = [x for x in (d.get("temperature_2m_min") or [])[:5] if isinstance(x, (int, float))]
    night_min = min(mins) if mins else None
    if soil_t is None:
        return {"error": "soil data not available for this place right now"}
    soil_t = round(soil_t, 1)
    soil_m = None if soil_m is None else round(soil_m, 2)
    frost_limit = DEEP_FROST_C if c["frost_hardy"] else FROST_C
    reasons = []
    if night_min is not None and night_min <= frost_limit:
        code = "frost_risk"; reasons.append("frost")
    elif soil_t < c["min_soil_c"]:
        code = "too_cold"; reasons.append("soil_cold")
    elif rain3 >= WET_RAIN_MM or (soil_m is not None and soil_m > WET_M3):
        code = "too_wet"; reasons.append("wet")
    elif soil_m is not None and soil_m < DRY_M3:
        code = "dry_rain_coming" if rain3 >= RAIN_COMING_MM else "too_dry"; reasons.append("dry")
    else:
        code = "good"
    return {"source": "open-meteo.com", "place": raw["place"], "crop": c["id"], "verdict": code, "sow_now": code == "good",
            "soil_temp_c": soil_t, "min_soil_temp_needed_c": c["min_soil_c"], "soil_moisture_m3m3": soil_m,
            "rain_next_3_days_mm": rain3, "coldest_night_next_5_days_c": night_min, "reasons": reasons,
            "note": ("Germination temperatures are indicative guidance and the soil-moisture bands are rough (soil type changes "
                     "them). Push a finger into the soil to check moisture, and confirm sowing dates with your agriculture "
                     "extension officer.")}


FUNCS = {"planting_window": planting_window}
SPECS = [{"type": "function", "function": {
    "name": "planting_window",
    "description": ("Is it a good time to sow a crop here? Uses soil temperature, soil moisture, coming rain and frost from the "
                    "forecast. Works in any country. Use for 'should I plant now', 'can I sow maize this week'. Never judge this yourself."),
    "parameters": {"type": "object", "properties": {
        "place": {"type": "string", "description": "village, town or district"},
        "crop": {"type": "string"},
        "country": {"type": "string", "description": "ISO 2-letter code from the farmer's profile, e.g. KE, IN"}},
        "required": ["place", "crop"]}}}]
