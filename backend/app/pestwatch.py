"""Disease weather watch: when does the weather favour fungal disease in the next 3 days? Works anywhere.

Most leaf and fruit fungi need a long spell of very humid, mild weather to infect. From the hourly forecast we count,
for each day, the hours with relative humidity of 90% or more and air temperature between 10 and 30 C (a standard
proxy for leaf wetness). For potato and tomato we also apply the classic late-blight "Smith period" rule: two
consecutive days with a minimum temperature of at least 10 C and at least 11 hours of 90% or more humidity.
Computed in code from the forecast: it warns when to look closely at the crop, it never diagnoses a disease and never
names a chemical.
"""
import httpx

HUMID_RH, WARM_MIN, WARM_MAX = 90, 10, 30
BANDS = ((6, "low"), (12, "moderate"), (10**9, "high"))     # hours of leaf-wetness proxy per day
SMITH_HOURS, SMITH_MIN_C = 11, 10


def _tools():
    from . import tools
    return tools


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
                                              "forecast_days": 3, "hourly": "temperature_2m,relative_humidity_2m"}).json()
        return {"place": f"{g['name']}, {g.get('admin1', '')}".strip(", "), "hourly": f["hourly"]}
    except Exception as e:
        return {"error": f"weather service unavailable ({type(e).__name__})"}


def disease_risk(crop: str, place: str, country: str = "") -> dict:
    from . import agro
    raw = _tools()._cached("pestwatch", (str(place).strip().lower(), str(country).upper()), lambda: _fetch(place, country),
                           ok=lambda v: "error" not in v)
    if "error" in raw:
        return raw
    h = raw["hourly"]
    by: dict[str, dict] = {}
    for ts, temp, rh in zip(h["time"], h["temperature_2m"], h["relative_humidity_2m"]):
        if temp is None or rh is None:
            continue
        d = by.setdefault(ts[:10], {"wet": 0, "min_c": temp, "hours": 0, "humid_all": 0})
        d["hours"] += 1
        d["min_c"] = min(d["min_c"], temp)
        d["humid_all"] += rh >= HUMID_RH
        d["wet"] += rh >= HUMID_RH and WARM_MIN <= temp <= WARM_MAX
    days = [{"date": k, "wet_hours": v["wet"], "min_c": v["min_c"], "risk": next(b for lim, b in BANDS if v["wet"] < lim)}
            for k, v in sorted(by.items()) if v["hours"] >= 12]
    if not days:
        return {"error": "no humidity forecast available right now"}
    c = agro._crop(crop)
    out = {"source": "open-meteo.com forecast", "place": raw["place"], "crop": c["id"] if c else str(crop)[:30], "days": days}
    order = [b for _l, b in BANDS]
    worst = max(days, key=lambda d: (order.index(d["risk"]), d["wet_hours"]))
    out.update(worst_day=worst["date"], worst_risk=worst["risk"], needs_attention=worst["risk"] != "low")
    if c and c["id"] in ("potato", "tomato"):
        ok = [d["wet_hours"] >= SMITH_HOURS and d["min_c"] >= SMITH_MIN_C for d in days]
        out["late_blight_period"] = any(a and b for a, b in zip(ok, ok[1:]))
    out["actions"] = ["scout_leaves", "avoid_overhead_irrigation_evening", "improve_airflow", "ask_officer_if_spots"] if out["needs_attention"] else []
    out["note"] = ("Estimated from the hourly forecast: hours with humidity of 90% or more at 10 to 30 C favour fungal disease. This is "
                   "a warning to inspect the crop, not a diagnosis. If you see spots, mould or wilting, send a photo or ask the "
                   "agriculture extension officer what to do. Never spray without advice on the product and dose.")
    return out


FUNCS = {"disease_risk": disease_risk}
SPECS = [{"type": "function", "function": {
    "name": "disease_risk",
    "description": ("Will the weather favour fungal crop disease in the next 3 days (humid, mild hours), incl. the potato/tomato late-blight "
                    "rule? Works in any country. Use for 'will disease come', 'it has been humid, should I worry', early warning. Not a diagnosis."),
    "parameters": {"type": "object", "properties": {"crop": {"type": "string"}, "place": {"type": "string"}, "country": {"type": "string"}},
                   "required": ["crop", "place"]}}}]
