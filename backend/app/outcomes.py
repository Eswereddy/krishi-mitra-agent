"""Outcome tracking: did the advice get followed, did it help, and how far were the predictions from what happened?
The records live on the farmer's phone; the server only does the arithmetic (stateless). Everything is computed in code from
what the farmer entered. Nothing is inferred: a comparison appears only when BOTH a prediction and an actual were entered.
"""
KINDS = ("irrigate", "sow", "fertilise", "protect", "harvest", "sell", "store", "other")
METRICS = ("expense", "yield_kg", "price_per_kg")
MAX_RECORDS = 300

T = {
    "en": {"head": "Season outcome report", "followed": "Followed {d} of {n} recommendations ({p}%)", "useful": "{u} of {r} rated useful ({p}%)",
           "acc": "{m}: predicted {a}, actual {b} ({e:+.0f}%)", "m": {"expense": "Expense", "yield_kg": "Yield (kg)", "price_per_kg": "Price per kg"},
           "totals": "Actual spend {s}, harvest value {v}, net {n} {c}", "none": "No recommendations logged yet.", "nocmp": "No predicted-vs-actual pairs yet: add a prediction and the actual result to see accuracy.",
           "note": "Based only on what you entered. Predictions are estimates; seasons differ."},
    "te": {"head": "సీజన్ ఫలితాల నివేదిక", "followed": "{n} సూచనల్లో {d} పాటించారు ({p}%)", "useful": "{r} లో {u} ఉపయోగకరం ({p}%)",
           "acc": "{m}: అంచనా {a}, వాస్తవం {b} ({e:+.0f}%)", "m": {"expense": "ఖర్చు", "yield_kg": "దిగుబడి (కిలో)", "price_per_kg": "కిలో ధర"},
           "totals": "వాస్తవ ఖర్చు {s}, పంట విలువ {v}, నికరం {n} {c}", "none": "ఇంకా సూచనలు నమోదు కాలేదు.", "nocmp": "అంచనా-వాస్తవం జతలు లేవు: అంచనా, వాస్తవ ఫలితం రెండూ నమోదు చేయండి.",
           "note": "మీరు నమోదు చేసినదాని ఆధారంగా మాత్రమే. అంచనాలు సుమారు మాత్రమే; సీజన్లు మారతాయి."},
    "hi": {"head": "सीज़न परिणाम रिपोर्ट", "followed": "{n} सुझावों में से {d} अपनाए ({p}%)", "useful": "{r} में से {u} उपयोगी ({p}%)",
           "acc": "{m}: अनुमान {a}, वास्तविक {b} ({e:+.0f}%)", "m": {"expense": "खर्च", "yield_kg": "उपज (किलो)", "price_per_kg": "कीमत प्रति किलो"},
           "totals": "वास्तविक खर्च {s}, फसल मूल्य {v}, शुद्ध {n} {c}", "none": "अभी कोई सुझाव दर्ज नहीं।", "nocmp": "अनुमान-वास्तविक जोड़ी नहीं: अनुमान और असली नतीजा दोनों दर्ज करें।",
           "note": "केवल आपके दर्ज किए आँकड़ों पर आधारित। अनुमान मोटे होते हैं; सीज़न अलग होते हैं।"},
}


def _num(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if 0 <= x < 1e9 else None


def _vals(d) -> dict:
    d = d if isinstance(d, dict) else {}
    return {m: n for m in METRICS if (n := _num(d.get(m))) is not None}


def clean(rec) -> dict | None:
    if not isinstance(rec, dict) or not str(rec.get("text") or "").strip():
        return None
    useful = rec.get("useful")
    return {"id": str(rec.get("id") or "")[:20], "kind": rec.get("kind") if rec.get("kind") in KINDS else "other",
            "crop": str(rec.get("crop") or "")[:40], "text": str(rec["text"]).strip()[:300], "date": str(rec.get("date") or "")[:10],
            "done": bool(rec.get("done")), "useful": useful if isinstance(useful, bool) else None,
            "predicted": _vals(rec.get("predicted")), "actual": _vals(rec.get("actual"))}


def report(records, lang: str = "en", currency: str = "") -> dict:
    L = T.get(lang, T["en"])
    recs = [c for r in (records if isinstance(records, list) else [])[:MAX_RECORDS] if (c := clean(r))]
    n, done = len(recs), sum(r["done"] for r in recs)
    rated = [r for r in recs if r["useful"] is not None]
    useful = sum(r["useful"] for r in rated)
    by_kind = {}
    for r in recs:
        k = by_kind.setdefault(r["kind"], {"total": 0, "done": 0})
        k["total"] += 1
        k["done"] += r["done"]
    pairs = {}
    for r in recs:
        for m in METRICS:
            p, a = r["predicted"].get(m), r["actual"].get(m)
            if p is not None and a is not None:
                pairs.setdefault(m, []).append((p, a))
    acc = []
    for m, ps in pairs.items():
        sp, sa = sum(p for p, _ in ps), sum(a for _, a in ps)
        row = {"metric": m, "pairs": len(ps), "predicted": round(sp / len(ps), 2), "actual": round(sa / len(ps), 2)}
        row["error_pct"] = round((sa - sp) / sp * 100, 1) if sp else None
        acc.append(row)
    spend = sum(r["actual"].get("expense", 0) for r in recs)
    value = sum(r["actual"]["yield_kg"] * r["actual"]["price_per_kg"] for r in recs if "yield_kg" in r["actual"] and "price_per_kg" in r["actual"])
    out = {"recommendations": n, "done": done, "followed_pct": round(done / n * 100) if n else None, "rated": len(rated),
           "useful": useful, "useful_pct": round(useful / len(rated) * 100) if rated else None, "by_kind": by_kind,
           "accuracy": acc, "actual_spend": round(spend, 2), "harvest_value": round(value, 2), "net": round(value - spend, 2)}
    lines = [L["head"]]
    if not n:
        lines.append(L["none"])
    else:
        lines.append(L["followed"].format(d=done, n=n, p=out["followed_pct"]))
        if rated:
            lines.append(L["useful"].format(u=useful, r=len(rated), p=out["useful_pct"]))
        lines += [L["acc"].format(m=L["m"][a["metric"]], a=a["predicted"], b=a["actual"], e=a["error_pct"]) for a in acc if a["error_pct"] is not None]
        if not acc:
            lines.append(L["nocmp"])
        if spend or value:
            lines.append(L["totals"].format(s=out["actual_spend"], v=out["harvest_value"], n=out["net"], c=currency))
    lines.append(L["note"])
    out["text"] = "\n".join(lines)
    out["note"] = L["note"]
    return out
