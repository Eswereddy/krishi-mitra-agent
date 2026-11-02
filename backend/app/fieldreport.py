"""AI field report generator: turns a farmer's voice notes (already transcribed by Muse Voice Transcribe), typed notes and the latest leaf scan
into ONE structured field report that can be shared with an expert, an advisor or a bank.

Structure comes from two sources, and the report says which was used:
  * `model`: if a live model is available it extracts symptoms and activities from the notes as JSON; the answer is whitelisted in code
    (only known symptom and activity codes are kept; anything else is dropped), so the model cannot add anything to the report.
  * `rules`: otherwise plain keyword rules in English, Telugu and Hindi.
Urgency, weather, crop stage and the safe steps are computed in code from the symptoms, the scan and the crop tables, never written by a model.
Problem matches come from the repository's problem table and are labelled a first guess, not a diagnosis. No pesticide names or doses.
"""
import asyncio
import json
import re
import secrets
from datetime import datetime, timezone

from . import advisor, cases, config, twin

MAX_NOTES, NOTE_LEN = 20, 400
ACTIVITIES = ("sowing", "irrigation", "fertiliser", "weeding", "spraying", "harvesting")
SYM_RX = {
    "spots_on_leaves": r"spot|మచ్చ|धब्बे", "yellowing": r"yellow|పసుపు|పసుపు|पीले|पीला", "wilting": r"wilt|droop|వాడ|मुरझ",
    "holes_or_chewed": r"\bholes?\b|chew|caterpillar|worm|రంధ్ర|తిన్న|छेद|कुतर|इल्ली", "spreading_fast": r"spread\w*\W+(\w+\W+){0,2}(fast|quick\w*|rapid\w*)|(fast|quick\w*|rapid\w*)\W+spread|వేగంగా|तेज़ी|तेजी",
    "whole_field": r"whole field|entire field|all plants|మొత్తం పొలం|పొలం మొత్తం|पूरा खेत", "after_rain": r"after (the )?rain|వర్షం తర్వాత|बारिश के बाद",
    "insects_seen": r"insect|pest|bug|aphid|whitefly|thrips|పురుగు|కీటక|తెల్ల దోమ|कीट|मक्खी", "mould_or_powder": r"mou?ld|powder|fung|బూజు|ఫంగస్|फफूँद|फफूंद",
    "stunted": r"stunt|not growing|short plants|ఎదుగుదల|बढ़वार|बौन",
}
ACT_RX = {
    "sowing": r"\bsow|\bseed|planted|విత్త|बुवाई|बोया|बोई", "irrigation": r"irrigat|watered|gave water|watering|తడి|నీరు పెట్ట|పారించ|सिंचाई|पानी दिया",
    "fertiliser": r"fertili|urea|\bdap\b|manure|compost|ఎరువు|యూరియా|खाद|यूरिया", "weeding": r"weed|కలుపు|निराई|खरपतवार", "spraying": r"spray|పిచికారీ|छिड़काव",
    "harvesting": r"harvest|కోత|कटाई|कटाई",
}
ACT_LABEL = {
    "en": {"sowing": "Sowing", "irrigation": "Irrigation", "fertiliser": "Fertiliser / manure", "weeding": "Weeding", "spraying": "Spraying", "harvesting": "Harvest"},
    "te": {"sowing": "విత్తడం", "irrigation": "నీటి తడి", "fertiliser": "ఎరువు", "weeding": "కలుపు తీత", "spraying": "పిచికారీ", "harvesting": "కోత"},
    "hi": {"sowing": "बुवाई", "irrigation": "सिंचाई", "fertiliser": "खाद", "weeding": "निराई", "spraying": "छिड़काव", "harvesting": "कटाई"},
}
H = {
    "en": {"title": "Field report", "crop": "Crop", "place": "Place", "stage": "Crop stage", "day": "day {d}", "notes": "Farmer's notes", "sym": "Symptoms reported", "act": "Work done",
           "scan": "Leaf photo measurement", "scanline": "{pct}% of leaf area affected ({band}); photo reliability: {rel}", "match": "Possible matches (first guess, not a diagnosis)",
           "urg": "Urgency", "wx": "Weather since sowing", "wxline": "{r} mm rain on {w} wet days; longest dry spell {d} days", "steps": "Safe steps now", "ask": "Questions for the expert",
           "none": "none", "disc": "Built from the farmer's own notes, an automated photo measurement and crop tables. Not a diagnosis. No pesticide or dose is suggested.",
           "q1": "Which problem is this, and how serious is it?", "q2": "What safe steps should I take before any treatment?", "q3": "Should an officer visit the field?",
           "s_photo": "Take a clear photo of one affected leaf (top and underside) and one of the whole plant.", "s_check": "Check several plants across the field to see how widespread it is.",
           "s_note": "Write down when it started and what the weather was like."},
    "te": {"title": "పొలం నివేదిక", "crop": "పంట", "place": "ప్రదేశం", "stage": "పంట దశ", "day": "రోజు {d}", "notes": "రైతు గమనికలు", "sym": "చెప్పిన లక్షణాలు", "act": "చేసిన పనులు",
           "scan": "ఆకు ఫోటో కొలత", "scanline": "ఆకు విస్తీర్ణంలో {pct}% దెబ్బతింది ({band}); ఫోటో నమ్మకం: {rel}", "match": "సాధ్యమైన సరిపోలికలు (మొదటి అంచనా, నిర్ధారణ కాదు)",
           "urg": "అత్యవసరం", "wx": "విత్తిన తర్వాత వాతావరణం", "wxline": "{w} వర్షపు రోజుల్లో {r} మి.మీ వర్షం; ఎక్కువ పొడి కాలం {d} రోజులు", "steps": "ఇప్పుడు సురక్షిత చర్యలు",
           "ask": "నిపుణుడిని అడగాల్సినవి", "none": "ఏమీ లేవు", "disc": "రైతు గమనికలు, యంత్ర ఫోటో కొలత, పంట పట్టికల ఆధారంగా తయారైంది. ఇది నిర్ధారణ కాదు. పురుగుమందు, మోతాదు సూచించలేదు.",
           "q1": "ఇది ఏ సమస్య, ఎంత తీవ్రం?", "q2": "చికిత్సకు ముందు నేను తీసుకోవాల్సిన సురక్షిత చర్యలేంటి?", "q3": "అధికారి పొలం చూడాలా?",
           "s_photo": "ఒక దెబ్బతిన్న ఆకు (పైన, కింద), మొత్తం మొక్క స్పష్టమైన ఫోటోలు తీయండి.", "s_check": "పొలంలో పలు చోట్ల మొక్కలు చూసి ఎంత వ్యాపించిందో చూడండి.",
           "s_note": "ఎప్పుడు మొదలైంది, వాతావరణం ఎలా ఉందో రాసుకోండి."},
    "hi": {"title": "खेत रिपोर्ट", "crop": "फसल", "place": "स्थान", "stage": "फसल चरण", "day": "दिन {d}", "notes": "किसान के नोट", "sym": "बताए गए लक्षण", "act": "किया गया काम",
           "scan": "पत्ती फ़ोटो माप", "scanline": "पत्ती का {pct}% हिस्सा प्रभावित ({band}); फ़ोटो भरोसा: {rel}", "match": "संभावित मिलान (पहला अनुमान, निदान नहीं)",
           "urg": "तात्कालिकता", "wx": "बुवाई के बाद मौसम", "wxline": "{w} बरसात के दिनों में {r} मिमी बारिश; सबसे लंबा सूखा दौर {d} दिन", "steps": "अभी सुरक्षित कदम",
           "ask": "विशेषज्ञ से सवाल", "none": "कोई नहीं", "disc": "किसान के नोट, मशीन फ़ोटो माप और फसल तालिकाओं से बना। यह निदान नहीं है। कोई कीटनाशक या मात्रा नहीं सुझाई गई।",
           "q1": "यह कौन सी समस्या है और कितनी गंभीर?", "q2": "इलाज से पहले मुझे कौन से सुरक्षित कदम लेने चाहिए?", "q3": "क्या अधिकारी खेत देखने आएँ?",
           "s_photo": "एक प्रभावित पत्ती (ऊपर और नीचे) और पूरे पौधे की साफ़ फ़ोटो लें।", "s_check": "खेत में कई जगह पौधे देखें कि कितना फैला है।", "s_note": "लिखें कि कब शुरू हुआ और मौसम कैसा था।"},
}


def _clean(t, n=NOTE_LEN) -> str:
    return re.sub(r"[\x00-\x1f\x7f]+", " ", str(t or "")).strip()[:n]


def rule_extract(text: str) -> dict:
    t = text.lower()
    return {"symptoms": [k for k, rx in SYM_RX.items() if re.search(rx, t)], "activities": [k for k, rx in ACT_RX.items() if re.search(rx, t)], "english": ""}


async def model_extract(notes: list[str]) -> dict | None:
    """Ask the model for JSON, keep only whitelisted codes. Returns None if no live model or the answer is unusable."""
    if config.MOCK_MODE:
        return None
    from . import meta_client
    sys_p = ("Extract facts from a farmer's field notes (any language). Output ONLY JSON: "
             '{"symptoms": [...], "activities": [...], "english": "one short English sentence describing what the farmer sees"}. '
             f"symptoms must be a subset of {list(cases.SYMPTOMS)}; activities a subset of {list(ACTIVITIES)}. Include only what the notes explicitly say. No advice.")
    try:
        raw = await meta_client.chat([{"role": "system", "content": sys_p}, {"role": "user", "content": "\n".join(notes)[:3000]}])
        m = re.search(r"\{.*\}", raw, re.S)
        d = json.loads(m.group(0)) if m else None
    except Exception:
        return None
    if not isinstance(d, dict):
        return None
    return {"symptoms": [s for s in d.get("symptoms", []) if s in cases.SYMPTOMS], "activities": [a for a in d.get("activities", []) if a in ACTIVITIES],
            "english": _clean(d.get("english"), 200)}


async def build(payload: dict, lang: str = "en") -> dict:
    lang = lang if lang in H else "en"
    L, CL = H[lang], cases.L[lang]
    prof = payload.get("profile") if isinstance(payload.get("profile"), dict) else {}
    scan = payload.get("scan") if isinstance(payload.get("scan"), dict) else {}
    tw = payload.get("twin") if isinstance(payload.get("twin"), dict) else {}
    raw_notes = [n for n in (payload.get("notes") or [])[:MAX_NOTES] if isinstance(n, dict)]
    notes = [{"text": _clean(n.get("text")), "at": _clean(n.get("at"), 25), "source": "voice" if n.get("source") == "voice" else "typed"} for n in raw_notes if _clean(n.get("text"))]
    if not notes and not scan:
        return {"error": "Add at least one note or a leaf scan first."}
    crop = _clean(prof.get("crop") or tw.get("crop"), 40)
    place = _clean(prof.get("place") or tw.get("place"), 60)
    joined = "\n".join(n["text"] for n in notes)
    ext = await model_extract([n["text"] for n in notes]) if notes else None
    method = "model" if ext else "rules"
    ext = ext or rule_extract(joined)
    for n in notes:                                                   # per-note tags are always rule-based (cheap, traceable to the words)
        r = rule_extract(n["text"])
        n["symptoms"], n["activities"] = r["symptoms"], r["activities"]
    symptoms = sorted(set(ext["symptoms"]) | {s for n in notes for s in n["symptoms"]})
    acts = sorted(set(ext["activities"]) | {a for n in notes for a in n["activities"]})
    level, why = cases.urgency(symptoms, scan)
    look_text = " ".join([ext.get("english", ""), joined]).strip()
    match = advisor.lookup_problem(crop, look_text) if look_text and symptoms else {"matches": []}
    matches = [{"name": m["name"], "urgency": m["urgency"], "looks_like": m["looks_like"], "what_to_do": m["what_to_do"][:3], "expert_note": m["expert_note"]} for m in match.get("matches", [])[:2]]
    steps = [L["s_photo"], L["s_check"], L["s_note"]]
    scan_ev = None
    if scan.get("severity_pct") is not None:
        scan_ev = {"severity_pct": scan.get("severity_pct"), "band": scan.get("band"), "reliability": scan.get("reliability"), "method": "SAM 3.1 leaf measurement (automated, not a diagnosis)"}
    out = {"id": "FR-" + secrets.token_hex(3).upper(), "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "crop": crop or None, "place": place or None,
           "extraction": method, "notes": notes, "symptoms": symptoms, "activities": acts, "urgency": level, "urgency_reasons": why, "possible_matches": matches, "scan": scan_ev,
           "safe_steps": steps, "questions_for_expert": [L["q1"], L["q2"], L["q3"]] if level != "low" or symptoms else [L["q1"]],
           "labels": {"notes": "farmer-entered (voice notes transcribed by Muse Voice Transcribe)", "symptoms": f"extracted by {method}", "urgency": "computed by rules",
                      "possible_matches": "repository problem table, first guess", "scan": "automated measurement", "weather": "live archive (lags ~5 days), computed"}}
    if tw.get("crop") and tw.get("acres"):
        rep = await twin.report({**tw, "place": tw.get("place") or place}, lang)
        out["stage"] = rep.get("stage")
        out["weather_since_sowing"] = rep.get("weather_since_sowing")
    out["summary_text"] = summary(out, lang, CL)
    return out


def summary(r: dict, lang: str, CL: dict) -> str:
    L = H[lang]
    lines = [f'📋 {L["title"]} {r["id"]}', f'{L["crop"]}: {r["crop"] or "-"}' + (f' · {L["place"]}: {r["place"]}' if r["place"] else ""),
             f'{L["urg"]}: {CL["urgency"][r["urgency"]]}']
    if r.get("stage") and r["stage"].get("day_of_crop"):
        lines.append(f'{L["stage"]}: {L["day"].format(d=r["stage"]["day_of_crop"])}')
    if r["symptoms"]:
        lines.append(f'{L["sym"]}: ' + ", ".join(CL[s] for s in r["symptoms"]))
    if r["activities"]:
        lines.append(f'{L["act"]}: ' + ", ".join(ACT_LABEL[lang][a] for a in r["activities"]))
    if r["scan"]:
        lines.append(f'{L["scan"]}: ' + L["scanline"].format(pct=r["scan"]["severity_pct"], band=r["scan"]["band"], rel=r["scan"]["reliability"]))
    w = r.get("weather_since_sowing")
    if w:
        lines.append(f'{L["wx"]}: ' + L["wxline"].format(r=w.get("rain_mm"), w=w.get("wet_days"), d=w.get("longest_dry_spell_days")))
    if r["possible_matches"]:
        lines.append(f'{L["match"]}: ' + "; ".join(m["name"] for m in r["possible_matches"]))
    if r["notes"]:
        lines.append(f'{L["notes"]}:')
        lines += [f'- {n["text"][:200]}' for n in r["notes"][:5]]
    lines.append(f'{L["ask"]}: ' + " / ".join(r["questions_for_expert"]))
    lines.append(L["disc"])
    return "\n".join(lines)
