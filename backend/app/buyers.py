"""Buyer offer comparison. The farmer enters the offers he actually received; this computes the NET income of each one
(price x quantity, minus commission, transport and other costs) so the best-looking price is not mistaken for the best deal.
A buyer is labelled 'verified' ONLY if the offer names an id from data/buyers.json that is marked verified there (with who
verified it and when); everything else is 'unverified', never softened. Risky terms (advance asked, long payment delay,
price far above the reference) are flagged by rules. Pure arithmetic, no model, nothing stored on the server.
"""
import json
from pathlib import Path

DATA = Path(__file__).parent / "data"
UNITS = {"kg": 1.0, "quintal": 100.0, "tonne": 1000.0}
MAX_OFFERS = 10
PAY_DELAY_WARN_DAYS = 7
TOO_GOOD_PCT = 25

T = {
    "en": {"ver": "Verified: {by} ({on})", "unver": "Unverified buyer: meet in person, never pay or hand over produce before checking, and prefer a mandi or cooperative receipt.",
           "advance": "Buyer asks you for an advance or deposit: do not pay anything first.", "delay": "Payment is promised after {n} days: ask for part payment on delivery and a written receipt.",
           "toogood": "Price is {p}% above your reference price: check carefully, offers like this are often not real.", "below": "Price is {p}% below your reference price.",
           "net": "Net {n} {c} ({k} per kg)", "best": "Best net offer: {b}, {n} {c}.", "none": "Add at least one offer with a price.",
           "note": "Net income is computed from the numbers you entered. Verification means only what is written in the registry; Krishi Mitra does not vouch for any buyer."},
    "te": {"ver": "ధృవీకరించబడింది: {by} ({on})", "unver": "ధృవీకరించని కొనుగోలుదారు: ప్రత్యక్షంగా కలవండి, తనిఖీ చేయకుండా డబ్బు ఇవ్వవద్దు, సరుకు అప్పగించవద్దు; మండీ లేదా సహకార సంఘం రసీదు తీసుకోండి.",
           "advance": "కొనుగోలుదారు అడ్వాన్స్ / డిపాజిట్ అడుగుతున్నారు: ముందుగా ఏమీ చెల్లించవద్దు.", "delay": "{n} రోజుల తర్వాత చెల్లింపు అంటున్నారు: డెలివరీ సమయంలో కొంత చెల్లింపు, రాతపూర్వక రసీదు అడగండి.",
           "toogood": "ధర మీ రిఫరెన్స్ ధర కంటే {p}% ఎక్కువ: జాగ్రత్తగా చూడండి, ఇలాంటి ఆఫర్లు తరచూ నిజం కావు.", "below": "ధర మీ రిఫరెన్స్ ధర కంటే {p}% తక్కువ.",
           "net": "నికరం {n} {c} (కిలోకు {k})", "best": "ఉత్తమ నికర ఆఫర్: {b}, {n} {c}.", "none": "ధరతో కనీసం ఒక ఆఫర్ చేర్చండి.",
           "note": "మీరు నమోదు చేసిన సంఖ్యల నుండి నికర ఆదాయం లెక్కించబడింది. ధృవీకరణ అంటే రిజిస్ట్రీలో రాసినదే; కృషి మిత్ర ఏ కొనుగోలుదారుకూ హామీ ఇవ్వదు."},
    "hi": {"ver": "सत्यापित: {by} ({on})", "unver": "असत्यापित खरीदार: आमने-सामने मिलें, जाँच से पहले पैसा या उपज न दें, और मंडी या सहकारी समिति की रसीद लें।",
           "advance": "खरीदार अग्रिम / जमा माँग रहा है: पहले कुछ भी न दें।", "delay": "भुगतान {n} दिन बाद का वादा है: डिलीवरी पर आंशिक भुगतान और लिखित रसीद माँगें।",
           "toogood": "कीमत आपके संदर्भ भाव से {p}% ज़्यादा है: सावधानी से जाँचें, ऐसे ऑफ़र अक्सर असली नहीं होते।", "below": "कीमत आपके संदर्भ भाव से {p}% कम है।",
           "net": "शुद्ध {n} {c} (प्रति किलो {k})", "best": "सबसे अच्छा शुद्ध ऑफ़र: {b}, {n} {c}।", "none": "कीमत के साथ कम से कम एक ऑफ़र जोड़ें।",
           "note": "शुद्ध आय आपके दर्ज किए आँकड़ों से निकली है। सत्यापन का मतलब सिर्फ़ रजिस्ट्री में लिखा है; कृषि मित्र किसी खरीदार की गारंटी नहीं देता।"},
}


def _n(v, hi=1e9):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if 0 <= x <= hi else None


def registry() -> dict:
    try:
        return {b["id"]: b for b in json.loads((DATA / "buyers.json").read_text())["buyers"] if b.get("id")}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def verified_list() -> list[dict]:
    return [{k: b.get(k) for k in ("id", "name", "type", "region", "verified_by", "verified_on")} for b in registry().values() if b.get("verified") is True]


def compare(offers, quantity, unit="quintal", reference_price=None, lang="en", currency="") -> dict:
    L = T.get(lang, T["en"])
    q, u = _n(quantity), unit if unit in UNITS else "quintal"
    if not q or q <= 0 or not isinstance(offers, list):
        return {"error": "quantity must be a number above zero"}
    kg = q * UNITS[u]
    ref = _n(reference_price)
    reg = registry()
    rows = []
    for o in offers[:MAX_OFFERS]:
        if not isinstance(o, dict):
            continue
        price = _n(o.get("price"))                      # per unit chosen above
        if not price:
            continue
        gross = price * q
        comm = gross * (_n(o.get("commission_pct"), 100) or 0) / 100
        trans = _n(o.get("transport_cost")) or 0
        other = _n(o.get("other_costs")) or 0
        net = gross - comm - trans - other
        entry = reg.get(str(o.get("buyer_id") or ""))
        ok = bool(entry and entry.get("verified") is True)
        flags, texts = [], []
        if ok:
            texts.append(L["ver"].format(by=entry.get("verified_by") or "-", on=entry.get("verified_on") or "-"))
        else:
            flags.append("unverified")
            texts.append(L["unver"])
        if o.get("asks_advance"):
            flags.append("advance")
            texts.append(L["advance"])
        delay = _n(o.get("payment_days"), 365)
        if delay is not None and delay > PAY_DELAY_WARN_DAYS:
            flags.append("slow_payment")
            texts.append(L["delay"].format(n=round(delay)))
        diff = None
        if ref:
            diff = round((price - ref) / ref * 100, 1)
            if diff >= TOO_GOOD_PCT:
                flags.append("too_good")
                texts.append(L["toogood"].format(p=round(diff)))
            elif diff <= -10:
                texts.append(L["below"].format(p=round(-diff)))
        rows.append({"buyer": str(o.get("buyer") or (entry or {}).get("name") or "?")[:60], "buyer_id": str(o.get("buyer_id") or "") or None,
                     "status": "verified" if ok else "unverified", "price": price, "gross": round(gross, 2), "commission": round(comm, 2),
                     "transport": round(trans, 2), "other_costs": round(other, 2), "net": round(net, 2), "net_per_kg": round(net / kg, 2),
                     "vs_reference_pct": diff, "payment_days": delay, "flags": flags, "notes": texts,
                     "net_text": L["net"].format(n=round(net), c=currency, k=round(net / kg, 2))})
    if not rows:
        return {"error": L["none"]}
    rows.sort(key=lambda r: -r["net"])
    risky = lambda r: any(f in r["flags"] for f in ("advance", "too_good"))
    out = {"quantity_kg": kg, "unit": u, "offers": rows, "best": rows[0]["buyer"], "currency": currency, "note": L["note"],
           "best_is_risky": risky(rows[0]) or rows[0]["status"] == "unverified"}
    out["text"] = L["best"].format(b=rows[0]["buyer"], n=round(rows[0]["net"]), c=currency) + "\n" + "\n".join(
        f"{i + 1}. {r['buyer']} ({r['status']}): {r['net_text']}" for i, r in enumerate(rows)) + "\n" + L["note"]
    return out
