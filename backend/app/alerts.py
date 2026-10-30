"""Price alerts: "tell me when groundnut goes above Rs 7,500".

The farmer's alert list lives on the device (no accounts, no stored personal data). The app sends it here
now and then; this module looks up the latest price for each and says which targets are reached. No model call.

Honesty rule: only LIVE market data can trigger an alert. Sample or saved (old) data never does, because a
"your price is reached" message built on a stale or made-up number could make a farmer sell at the wrong time.
"""
import asyncio

from . import tools

MAX_ALERTS = 5


def _clean(a) -> dict | None:
    if not isinstance(a, dict):
        return None
    crop, district = str(a.get("crop") or "").strip()[:40], str(a.get("district") or "").strip()[:40]
    try:
        target = float(a.get("target"))
    except (TypeError, ValueError):
        return None
    direction = "below" if a.get("direction") == "below" else "above"
    if not crop or not district or not (0 < target < 10_000_000):
        return None
    return {"id": str(a.get("id") or "")[:20], "crop": crop, "district": district, "target": round(target),
            "direction": direction, "state": str(a.get("state") or "Andhra Pradesh").strip()[:40]}


def _check_one(a: dict) -> dict:
    res = tools.get_mandi_price(a["crop"], a["district"], a["state"])
    src = str(res.get("source", ""))
    row = next((r for r in (res.get("results") or []) if r.get("modal_price_per_quintal")), None)
    out = {"id": a["id"], "crop": a["crop"], "district": a["district"], "target": a["target"],
           "direction": a["direction"], "triggered": False, "live": "live" in src, "source": src}
    if not row:
        out["status"] = "no_price"
        return out
    price = row["modal_price_per_quintal"]
    out.update({"current": price, "market": row.get("market"), "date": row.get("date")})
    if "live" not in src:
        out["status"] = "not_live"            # sample or saved data: never trigger
        return out
    hit = price >= a["target"] if a["direction"] == "above" else price <= a["target"]
    out["triggered"] = hit
    out["status"] = "reached" if hit else "waiting"
    return out


async def check_alerts(alerts) -> list[dict]:
    clean = [c for c in (_clean(a) for a in (alerts if isinstance(alerts, list) else [])[:MAX_ALERTS]) if c]
    return list(await asyncio.gather(*(asyncio.to_thread(_check_one, c) for c in clean)))
