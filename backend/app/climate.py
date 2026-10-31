"""Season check: is this season unusual here? Rain and temperature of the last 30 days against the same 30 days
in each of the previous 10 years (Open-Meteo historical archive, free, worldwide). Computed in code.

This turns "it feels dry" into "rain is 45% of normal": the signal a farmer needs to adjust sowing, irrigation and
loan decisions early, and the evidence for a drought or flood relief request. Archive data lags a few days.
"""
from datetime import date, timedelta

import httpx

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
LAG_DAYS, WINDOW, YEARS = 5, 30, 10
BANDS = ((50, "much_below"), (75, "below"), (125, "normal"), (150, "above"), (10**9, "much_above"))
_today = date.today                     # tests replace this


def _tools():
    from . import tools
    return tools


def _fetch(place: str, country: str, start: date, end: date) -> dict:
    t = _tools()
    try:
        with httpx.Client(timeout=max(t.HTTP_TIMEOUT, 20)) as c:
            params = {"name": place, "count": 1}
            if country and country.upper() not in ("", "OTHER"):
                params["country_code"] = country.upper()
            geo = c.get(t.GEO_URL, params=params).json().get("results") or []
            if not geo:
                return {"error": f"place not found: {place}"}
            g = geo[0]
            a = c.get(ARCHIVE_URL, params={"latitude": g["latitude"], "longitude": g["longitude"], "timezone": "auto",
                                           "start_date": start.isoformat(), "end_date": end.isoformat(),
                                           "daily": "precipitation_sum,temperature_2m_mean"}).json()
        return {"place": f"{g['name']}, {g.get('admin1', '')}".strip(", "), "daily": a["daily"]}
    except Exception as e:
        return {"error": f"climate history unavailable ({type(e).__name__})"}


def _shift(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year - years)
    except ValueError:                  # 29 February
        return d.replace(year=d.year - years, day=28)


def season_check(place: str, country: str = "") -> dict:
    end = _today() - timedelta(days=LAG_DAYS)
    start = end - timedelta(days=WINDOW - 1)
    first = _shift(start, YEARS)
    raw = _tools()._cached("climate", (str(place).strip().lower(), str(country).upper(), end.isoformat()),
                           lambda: _fetch(place, country, first, end), ok=lambda v: "error" not in v)
    if "error" in raw:
        return raw
    days = raw["daily"]
    by = {t: (p, m) for t, p, m in zip(days["time"], days["precipitation_sum"], days["temperature_2m_mean"])}

    def window(s: date):
        rain = temp = n = 0
        for i in range(WINDOW):
            p, m = by.get((s + timedelta(days=i)).isoformat(), (None, None))
            if p is None or m is None:
                return None
            rain += p; temp += m; n += 1
        return rain, temp / n

    now = window(start)
    past = [w for w in (window(_shift(start, y)) for y in range(1, YEARS + 1)) if w]
    if not now or len(past) < 5:
        return {"error": "not enough climate history for this place"}
    normal_rain = sum(w[0] for w in past) / len(past)
    normal_temp = sum(w[1] for w in past) / len(past)
    pct = None if normal_rain < 1 else round(now[0] / normal_rain * 100)
    band = "normal" if pct is None else next(b for lim, b in BANDS if pct < lim)
    return {"source": "open-meteo.com historical archive", "place": raw["place"],
            "period": {"from": start.isoformat(), "to": end.isoformat(), "days": WINDOW},
            "rain_mm": round(now[0]), "normal_rain_mm": round(normal_rain), "rain_vs_normal_pct": pct, "rain_band": band,
            "temp_c": round(now[1], 1), "normal_temp_c": round(normal_temp, 1), "temp_diff_c": round(now[1] - normal_temp, 1),
            "years_compared": len(past),
            "note": ("Compared with the same 30 days in each of the last 10 years at this place. Archive data lags about 5 days "
                     "and covers a grid cell, so a single farm can differ. A signal to plan with, not a forecast.")}


FUNCS = {"season_check": season_check}
SPECS = [{"type": "function", "function": {
    "name": "season_check",
    "description": ("Is this season unusual? Rain and temperature of the last 30 days against the last 10 years at the same place "
                    "(works in any country). Use for 'is it drier than normal', 'is this a drought year', 'is it hotter than usual'."),
    "parameters": {"type": "object", "properties": {"place": {"type": "string"}, "country": {"type": "string"}}, "required": ["place"]}}}]
