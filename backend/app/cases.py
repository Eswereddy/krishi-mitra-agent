"""Expert escalation: turns a photo scan + symptoms + weather + crop profile into ONE structured case an agriculture
expert can act on, in te/hi/en. Nothing is stored on the server (the case history lives on the farmer's device) and
the farmer's details go in only if they consented. Urgency is computed by rules, never by a model, and the summary
always says it is an automated measurement, not a diagnosis.
"""
import asyncio
import json
import os
import secrets
import urllib.parse
from datetime import datetime, timezone

from . import coach

SYMPTOMS = ("spots_on_leaves", "yellowing", "wilting", "holes_or_chewed", "spreading_fast", "whole_field",
            "after_rain", "insects_seen", "mould_or_powder", "stunted")
RED_FLAGS = ("spreading_fast", "whole_field")
NOTE_MAX = 500

L = {
    "en": {"spots_on_leaves": "Spots on leaves", "yellowing": "Yellowing leaves", "wilting": "Wilting", "holes_or_chewed": "Holes or chewed leaves",
           "spreading_fast": "Spreading fast", "whole_field": "Whole field affected", "after_rain": "Started after rain",
           "insects_seen": "Insects seen", "mould_or_powder": "Mould or powder on leaves", "stunted": "Stunted growth",
           "urgency": {"high": "HIGH", "medium": "MEDIUM", "low": "LOW"},
           "head": "Crop problem, help needed", "case": "Case", "urg": "Urgency", "crop": "Crop", "place": "Place", "day": "Crop day",
           "sym": "Symptoms", "scan": "Photo scan", "scanline": "{pct}% of leaf area affected ({band}), photo reliability: {rel}",
           "wx": "Weather", "wxline": "max {t} C, rain next days {r} mm, disease-weather risk: {k}", "note": "Farmer's note",
           "photo": "Photo: available, will be sent separately", "disc": "This is an automated measurement from a phone photo, not a diagnosis. Please advise safe next steps and any treatment."},
    "te": {"spots_on_leaves": "ఆకులపై మచ్చలు", "yellowing": "ఆకులు పసుపు రంగు", "wilting": "వాడిపోవడం", "holes_or_chewed": "ఆకులకు రంధ్రాలు / తిన్న గుర్తులు",
           "spreading_fast": "వేగంగా వ్యాపిస్తోంది", "whole_field": "పొలం మొత్తం ప్రభావితం", "after_rain": "వర్షం తర్వాత మొదలైంది",
           "insects_seen": "పురుగులు కనిపిస్తున్నాయి", "mould_or_powder": "ఆకులపై బూజు / పొడి", "stunted": "ఎదుగుదల తక్కువ",
           "urgency": {"high": "ఎక్కువ", "medium": "మధ్యస్థం", "low": "తక్కువ"},
           "head": "పంట సమస్య, సలహా కావాలి", "case": "కేసు", "urg": "అత్యవసరం", "crop": "పంట", "place": "ప్రదేశం", "day": "పంట రోజు",
           "sym": "లక్షణాలు", "scan": "ఫోటో స్కాన్", "scanline": "ఆకు విస్తీర్ణంలో {pct}% దెబ్బతింది ({band}), ఫోటో నమ్మకం: {rel}",
           "wx": "వాతావరణం", "wxline": "max {t} C, రాబోయే రోజుల వర్షం {r} మి.మీ, తెగులు వాతావరణ ప్రమాదం: {k}", "note": "రైతు గమనిక",
           "photo": "ఫోటో ఉంది, విడిగా పంపుతాను", "disc": "ఇది ఫోన్ ఫోటో నుండి యంత్ర కొలత మాత్రమే, నిర్ధారణ కాదు. దయచేసి సురక్షిత చర్యలు, చికిత్స సలహా ఇవ్వండి."},
    "hi": {"spots_on_leaves": "पत्तों पर धब्बे", "yellowing": "पत्ते पीले", "wilting": "मुरझाना", "holes_or_chewed": "पत्तों में छेद / कुतरे निशान",
           "spreading_fast": "तेज़ी से फैल रहा है", "whole_field": "पूरा खेत प्रभावित", "after_rain": "बारिश के बाद शुरू हुआ",
           "insects_seen": "कीट दिख रहे हैं", "mould_or_powder": "पत्तों पर फफूँद / पाउडर", "stunted": "बढ़वार रुकी",
           "urgency": {"high": "ज़्यादा", "medium": "मध्यम", "low": "कम"},
           "head": "फसल की समस्या, सलाह चाहिए", "case": "केस", "urg": "तात्कालिकता", "crop": "फसल", "place": "स्थान", "day": "फसल का दिन",
           "sym": "लक्षण", "scan": "फ़ोटो स्कैन", "scanline": "पत्ती का {pct}% हिस्सा प्रभावित ({band}), फ़ोटो भरोसा: {rel}",
           "wx": "मौसम", "wxline": "max {t} C, अगले दिनों बारिश {r} मिमी, रोग-मौसम जोखिम: {k}", "note": "किसान का नोट",
           "photo": "फ़ोटो उपलब्ध है, अलग से भेजूँगा", "disc": "यह फ़ोन की फ़ोटो से मशीन द्वारा माप है, निदान नहीं। कृपया सुरक्षित कदम और उपचार की सलाह दें।"},
}


def _s(v, n=60) -> str:
    return str(v or "").strip()[:n]


def urgency(symptoms: list[str], scan: dict) -> tuple[str, list[str]]:
    reasons = []
    if (scan.get("escalation") or {}).get("needed") and "severe_damage" in (scan["escalation"].get("reasons") or []):
        reasons.append("severe_damage")
    reasons += [s for s in symptoms if s in RED_FLAGS]
    if reasons:
        return "high", reasons
    if (scan.get("escalation") or {}).get("needed") or scan.get("reliability") in ("uncertain", "retake"):
        return "medium", ["scan_not_reliable"]
    return "low", []


def _weather(place: str, crop: str, country: str) -> dict:
    from . import pestwatch, tools
    out = {}
    if not place:
        return out
    wx = tools.get_weather(place, 5)
    if "error" not in wx and wx.get("forecast"):
        out["max_c_today"] = wx["forecast"][0].get("max_c")
        out["rain_next_5_days_mm"] = round(sum(x.get("rain_mm") or 0 for x in wx["forecast"][:5]), 1)
        out["source"] = "open-meteo.com forecast (live)"
    dr = pestwatch.disease_risk(crop, place, country) if crop else {"error": "no crop"}
    if "error" not in dr and dr.get("worst_risk"):
        out["disease_weather_risk"] = dr["worst_risk"]
    return out


async def build_case(payload: dict, lang: str = "en") -> dict:
    lang = lang if lang in L else "en"
    t = L[lang]
    cons = payload.get("consent") if isinstance(payload.get("consent"), dict) else {}
    prof = payload.get("profile") if isinstance(payload.get("profile"), dict) else {}
    scan = payload.get("scan") if isinstance(payload.get("scan"), dict) else {}
    symptoms = [s for s in (payload.get("symptoms") or []) if s in SYMPTOMS][:len(SYMPTOMS)]
    note = _s(payload.get("note"), NOTE_MAX)
    crop = _s(prof.get("crop") or payload.get("crop"), 40)
    country = _s(prof.get("country"), 3).upper()
    place = _s(prof.get("place"), 60) if cons.get("share_location") else ""
    share_details = bool(cons.get("share_details"))

    farmer = {"language": lang, "country": country or None, "crop": crop or None}
    if place:
        farmer["place"] = place
    days = None
    if share_details and crop and prof.get("sowing_date"):
        g = await asyncio.to_thread(coach.crop_guide, crop, str(prof["sowing_date"]), "", country)
        if g.get("status") == "growing":
            days = g["day_of_crop"]
            farmer["day_of_crop"], farmer["stage"] = days, g.get("stage")
    wx = await asyncio.to_thread(_weather, place, crop, country) if place else {}
    level, why = urgency(symptoms, scan)
    sev = scan.get("severity_pct")
    scan_ev = None
    if sev is not None:
        scan_ev = {"severity_pct": sev, "band": scan.get("band"), "reliability": scan.get("reliability"),
                   "confidence_mean": (scan.get("confidence") or {}).get("mean"), "reasons": (scan.get("reasons") or [])[:8],
                   "method": "SAM 3.1 leaf measurement (automated, not a diagnosis)"}
    cid = "KM-" + secrets.token_hex(3).upper()
    case = {"id": cid, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "urgency": level, "urgency_reasons": why,
            "farmer": farmer, "symptoms": symptoms, "note": note, "scan": scan_ev, "weather": wx or None,
            "photo_consented": bool(cons.get("share_photo")), "data_labels": "weather = live forecast; scan = automated measurement; the rest = farmer-entered"}
    case["summary_text"] = summary(case, lang)
    return case


def summary(case: dict, lang: str) -> str:
    t = L.get(lang, L["en"])
    f, sc, wx = case["farmer"], case.get("scan"), case.get("weather") or {}
    lines = [f"{t['head']} [{case['id']}]", f"{t['urg']}: {t['urgency'][case['urgency']]}"]
    if f.get("crop"):
        lines.append(f"{t['crop']}: {f['crop']}" + (f" ({t['day']} {f['day_of_crop']})" if f.get("day_of_crop") is not None else ""))
    if f.get("place"):
        lines.append(f"{t['place']}: {f['place']}")
    if case["symptoms"]:
        lines.append(f"{t['sym']}: " + ", ".join(t[s] for s in case["symptoms"]))
    if sc:
        lines.append(f"{t['scan']}: " + t["scanline"].format(pct=sc["severity_pct"], band=sc.get("band") or "-", rel=sc.get("reliability") or "-"))
    if wx:
        lines.append(f"{t['wx']}: " + t["wxline"].format(t=wx.get("max_c_today", "-"), r=wx.get("rain_next_5_days_mm", "-"), k=wx.get("disease_weather_risk", "-")))
    if case.get("note"):
        lines.append(f"{t['note']}: {case['note']}")
    if case.get("photo_consented"):
        lines.append(t["photo"])
    lines.append(t["disc"])
    return "\n".join(lines)


def contacts(lang: str, country: str, text: str = "") -> dict:
    """Configured experts (EXPERT_CONTACTS env, JSON list) matching the language, with share links; else generic local help."""
    from . import tools
    try:
        raw = json.loads(os.getenv("EXPERT_CONTACTS") or "[]")
    except ValueError:
        raw = []
    out = []
    for c in raw if isinstance(raw, list) else []:
        if not isinstance(c, dict) or not c.get("value"):
            continue
        langs = c.get("languages") or []
        if langs and lang not in langs:
            continue
        kind, val, q = c.get("type", "whatsapp"), str(c["value"]), urllib.parse.quote(text)
        link = (f"https://wa.me/{''.join(ch for ch in val if ch.isdigit())}?text={q}" if kind == "whatsapp"
                else f"mailto:{val}?subject={urllib.parse.quote('Crop problem')}&body={q}" if kind == "email" else f"tel:{val}")
        out.append({"name": _s(c.get("name"), 60) or "Expert", "type": kind, "link": link})
    return {"experts": out, "configured": bool(out), "fallback": tools.get_expert_help(country or "IN"),
            "labels": {"symptoms": {s: L.get(lang, L["en"])[s] for s in SYMPTOMS}}}
