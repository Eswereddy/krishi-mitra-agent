"""Water plan: how much water does my crop really need this week, and how much of it will the rain provide?

FAO-56 method, computed in code: crop water use per day = reference evapotranspiration (ET0, from the Open-Meteo
forecast) x crop coefficient (Kc, which follows the growth stage from the sowing date). Subtract the rain that
the soil can actually use, and the rest is what irrigation must supply. Irrigating only that, instead of by habit,
saves water, pumping energy and money, and avoids waterlogging. Works anywhere. Kc values are typical FAO-56 numbers
(indicative); the farmer's soil is not known, so the result says to check the soil by hand.
It also tells how much rain could be caught: litres from each 100 square metres of roof or pond catchment.
"""
import json
from datetime import timedelta

import httpx

from . import coach

EFFECTIVE_RAIN = 0.8        # share of rainfall the soil can use (rest runs off or drains): rule-of-thumb
RUNOFF_COEFF = 0.8          # share of rain a roof or lined pond catchment collects
IRRIGATE_AT_MM = 20         # assumed allowable soil-water deficit before irrigating (small plots, loamy soil)
L_PER_MM_ACRE = 4046.86
L_PER_MM_HA = 10000


def _tools():
    from . import tools
    return tools


def kc_at(kcs, pct: float) -> float:
    """Crop coefficient at a point in the season (0-100% of the duration): flat initial, ramp up, flat mid, ramp down, end."""
    ini, mid, end = kcs
    if pct < 15:
        return ini
    if pct < 45:
        return ini + (mid - ini) * (pct - 15) / 30
    if pct < 70:
        return mid
    if pct < 90:
        return mid + (end - mid) * (pct - 70) / 20
    return end


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
            f = c.get(t.FORECAST_URL, params={"latitude": g["latitude"], "longitude": g["longitude"], "timezone": "auto",
                                              "forecast_days": 7, "daily": "et0_fao_evapotranspiration,precipitation_sum"}).json()
        return {"place": f"{g['name']}, {g.get('admin1', '')}".strip(", "), "daily": f["daily"]}
    except Exception as e:
        return {"error": f"weather service unavailable ({type(e).__name__})"}


def water_plan(crop: str, place: str, sowing_date: str = "", country: str = "", acres: float = 1) -> dict:
    from . import agro
    c = agro._crop(crop)
    kcs = json.loads((coach.DATA / "crop_kc.json").read_text())["kc"]
    dur = coach._tables()["durations"]
    if not c or c["id"] not in kcs:
        return {"error": f"no water guide for '{crop}' yet", "known_crops": sorted(kcs)}
    a = float(acres or 0)
    if a <= 0 or a > 1000:
        return {"error": "acres must be a sensible number above zero"}
    raw = _tools()._cached("water", (str(place).strip().lower(), str(country).upper()), lambda: _fetch(place, country),
                           ok=lambda v: "error" not in v)
    if "error" in raw:
        return raw
    d = raw["daily"]
    et0, rain, dates = d.get("et0_fao_evapotranspiration") or [], d.get("precipitation_sum") or [], d.get("time") or []
    if not et0 or not dates:
        return {"error": "evapotranspiration data not available for this place right now"}
    sown = coach._parse(sowing_date) if sowing_date else None
    if sowing_date and not sown:
        return {"error": "sowing date must look like 2026-07-15"}
    today = coach._today()
    rows, total_need, total_rain, cum, irrigate_by = [], 0.0, 0.0, 0.0, None
    for i, day in enumerate(dates[:7]):
        pct = ((today - sown).days + i) / dur[c["id"]] * 100 if sown else 55.0    # no sowing date: assume mid-season
        pct = max(pct, 0.0)
        kc = round(kc_at(kcs[c["id"]], min(pct, 100)), 2)
        use = round((et0[i] or 0) * kc, 1)
        eff = round((rain[i] or 0) * EFFECTIVE_RAIN, 1)
        cum = max(cum + use - eff, 0.0)
        if irrigate_by is None and cum >= IRRIGATE_AT_MM:
            irrigate_by = day
        total_need += use
        total_rain += rain[i] or 0
        rows.append({"date": day, "et0_mm": et0[i], "kc": kc, "crop_use_mm": use, "rain_mm": rain[i], "effective_rain_mm": eff})
    eff_total = round(sum(r["effective_rain_mm"] for r in rows), 1)
    need = round(max(total_need - eff_total, 0), 1)
    return {"source": "open-meteo.com forecast (FAO-56 method)", "place": raw["place"], "crop": c["id"], "acres": a,
            "stage_known": bool(sown), "days": rows, "crop_use_week_mm": round(total_need, 1),
            "effective_rain_week_mm": eff_total, "irrigation_need_week_mm": need,
            "irrigation_need_litres": round(need * L_PER_MM_ACRE * a), "irrigation_need_litres_per_hectare": round(need * L_PER_MM_HA),
            "irrigate_by": irrigate_by, "irrigate_at_deficit_mm": IRRIGATE_AT_MM,
            "rain_week_mm": round(total_rain, 1), "rain_harvest_litres_per_100m2": round(total_rain * 100 * RUNOFF_COEFF),
            "note": ("FAO-56 estimate with typical crop coefficients (indicative). Your soil, mulch and crop variety change it. "
                     "Check the soil by hand and irrigate only the shortfall: over-irrigation wastes water, pumping energy and "
                     "money. " + ("" if sown else "No sowing date given: mid-season water use assumed."))}


FUNCS = {"water_plan": water_plan}
SPECS = [{"type": "function", "function": {
    "name": "water_plan",
    "description": ("How much water the crop needs this week after rain (FAO-56: evapotranspiration x crop coefficient), litres for the "
                    "farmer's acres, the day to irrigate by, and rainwater that can be harvested. Works in any country. Use for 'how much "
                    "water', 'how can I save water', 'when to irrigate', 'rainwater harvesting'. Pass the profile sowing_date if known."),
    "parameters": {"type": "object", "properties": {
        "crop": {"type": "string"}, "place": {"type": "string"}, "sowing_date": {"type": "string", "description": "YYYY-MM-DD, optional"},
        "country": {"type": "string"}, "acres": {"type": "number"}}, "required": ["crop", "place"]}}}]
