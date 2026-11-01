"""Crop-insurance evidence file: turns the farmer's own evidence (photos, notes, documents), checklist ticks and claim timeline
into ONE printable, self-contained HTML report (save as PDF from the browser). It organises what the farmer has; it never
estimates the chance of approval and says so on the page. The only judgement computed is arithmetic on entered dates: whether
the loss was reported within the 72-hour window that applies to localized calamities under PMFBY. Everything is HTML-escaped.
Stateless: nothing is stored on the server.
"""
import html
import re
from datetime import datetime, timezone

from . import claim, locale as loc

STAGES = ("reported", "documents_submitted", "survey_done", "decision_waiting", "paid", "rejected")
MAX_PHOTOS, MAX_ITEMS, MAX_PHOTO_CHARS = 6, 30, 150_000
DATA_URL = re.compile(r"^data:image/(jpeg|png|webp);base64,[A-Za-z0-9+/=]+$")

T = {
    "en": {"title": "Crop loss evidence file", "farmer": "Farmer and field", "loss": "Loss details", "cause": "Cause", "when": "Date and time of loss", "crop": "Crop", "acres": "Area (acres)",
           "place": "Place", "policy": "Policy / application no.", "complaint": "Complaint / reference no.", "check": "Document checklist", "have": "Have", "need": "Still needed",
           "ev": "Evidence", "tl": "Claim progress", "window_yes": "Loss was reported {h} hours after it happened: within the 72-hour window.", "window_no": "Loss was reported {h} hours after it happened: after the 72-hour window. Ask the insurer what applies.",
           "window_na": "The 72-hour reporting window does not apply to this cause, or the report date is not entered.", "photo": "Photo", "note": "Note", "document": "Document",
           "stage": {"reported": "Loss reported", "documents_submitted": "Documents submitted", "survey_done": "Field survey done", "decision_waiting": "Waiting for decision", "paid": "Claim paid", "rejected": "Claim rejected"},
           "disc": "This file organises the farmer's own evidence and notes. It is not an insurance claim form and does not guarantee any claim: the insurer decides. Dates and numbers are as entered by the farmer.", "none": "None added", "gen": "Generated"},
    "te": {"title": "పంట నష్టం ఆధారాల ఫైల్", "farmer": "రైతు, పొలం", "loss": "నష్టం వివరాలు", "cause": "కారణం", "when": "నష్టం జరిగిన తేదీ, సమయం", "crop": "పంట", "acres": "విస్తీర్ణం (ఎకరాలు)",
           "place": "ప్రదేశం", "policy": "పాలసీ / దరఖాస్తు నం.", "complaint": "ఫిర్యాదు / రిఫరెన్స్ నం.", "check": "పత్రాల జాబితా", "have": "ఉన్నవి", "need": "ఇంకా కావాల్సినవి",
           "ev": "ఆధారాలు", "tl": "క్లెయిమ్ పురోగతి", "window_yes": "నష్టం జరిగిన {h} గంటల తర్వాత తెలియజేశారు: 72 గంటల గడువులోనే.", "window_no": "నష్టం జరిగిన {h} గంటల తర్వాత తెలియజేశారు: 72 గంటల గడువు దాటింది. బీమా సంస్థను అడగండి.",
           "window_na": "ఈ కారణానికి 72 గంటల నియమం వర్తించదు, లేదా తెలియజేసిన తేదీ నమోదు కాలేదు.", "photo": "ఫోటో", "note": "గమనిక", "document": "పత్రం",
           "stage": {"reported": "నష్టం తెలియజేశారు", "documents_submitted": "పత్రాలు సమర్పించారు", "survey_done": "పొలం సర్వే అయింది", "decision_waiting": "నిర్ణయం కోసం వేచి ఉన్నారు", "paid": "క్లెయిమ్ చెల్లించారు", "rejected": "క్లెయిమ్ తిరస్కరించారు"},
           "disc": "ఈ ఫైల్ రైతు ఆధారాలు, గమనికలను క్రమబద్ధీకరిస్తుంది. ఇది బీమా క్లెయిమ్ ఫారం కాదు, ఏ క్లెయిమ్‌కూ హామీ కాదు: బీమా సంస్థ నిర్ణయిస్తుంది. తేదీలు, సంఖ్యలు రైతు నమోదు చేసినవే.", "none": "ఏమీ చేర్చలేదు", "gen": "తయారైంది"},
    "hi": {"title": "फसल नुकसान साक्ष्य फ़ाइल", "farmer": "किसान और खेत", "loss": "नुकसान का विवरण", "cause": "कारण", "when": "नुकसान की तारीख़ और समय", "crop": "फसल", "acres": "क्षेत्र (एकड़)",
           "place": "स्थान", "policy": "पॉलिसी / आवेदन नं.", "complaint": "शिकायत / संदर्भ नं.", "check": "दस्तावेज़ सूची", "have": "हैं", "need": "अभी चाहिए",
           "ev": "साक्ष्य", "tl": "क्लेम की प्रगति", "window_yes": "नुकसान के {h} घंटे बाद सूचना दी गई: 72 घंटे की सीमा के भीतर।", "window_no": "नुकसान के {h} घंटे बाद सूचना दी गई: 72 घंटे की सीमा के बाद। बीमा कंपनी से पूछें।",
           "window_na": "इस कारण पर 72 घंटे का नियम लागू नहीं, या सूचना की तारीख़ दर्ज नहीं।", "photo": "फ़ोटो", "note": "नोट", "document": "दस्तावेज़",
           "stage": {"reported": "नुकसान की सूचना दी", "documents_submitted": "दस्तावेज़ जमा किए", "survey_done": "खेत का सर्वे हुआ", "decision_waiting": "फ़ैसले का इंतज़ार", "paid": "क्लेम मिला", "rejected": "क्लेम अस्वीकृत"},
           "disc": "यह फ़ाइल किसान के अपने साक्ष्य और नोट व्यवस्थित करती है। यह बीमा क्लेम फ़ॉर्म नहीं है और किसी क्लेम की गारंटी नहीं: फ़ैसला बीमा कंपनी करती है। तारीख़ें और संख्याएँ किसान द्वारा दर्ज हैं।", "none": "कुछ नहीं जोड़ा", "gen": "बनाई गई"},
}


def _dt(v):
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _t(v, n=200) -> str:
    return html.escape(str(v or "").strip()[:n])


def build(payload: dict, lang: str = "en") -> dict:
    lang = lang if lang in T else "en"
    L = T[lang]
    prof = payload.get("profile") if isinstance(payload.get("profile"), dict) else {}
    loss = payload.get("loss") if isinstance(payload.get("loss"), dict) else {}
    occurred = _dt(loss.get("occurred_at"))
    if not occurred:
        return {"error": "loss.occurred_at is needed (date and time of the loss)"}
    cause = loss.get("cause") if loss.get("cause") in claim.CAUSES else "other"
    cause_label = claim.T.get(lang, claim.T["en"])["cause"][cause]
    timeline = []
    for e in (payload.get("timeline") if isinstance(payload.get("timeline"), list) else [])[:MAX_ITEMS]:
        d = _dt(e.get("date")) if isinstance(e, dict) else None
        if d and e.get("stage") in STAGES:
            timeline.append({"stage": e["stage"], "date": d, "note": _t(e.get("note"), 300)})
    timeline.sort(key=lambda x: x["date"])
    reported = next((x["date"] for x in timeline if x["stage"] == "reported"), None)
    window = None
    timed = cause in claim.LOCALIZED or cause in claim.POST_HARVEST
    if timed and reported and loc.is_india(prof):
        hours = round((reported - occurred).total_seconds() / 3600, 1)
        window = {"hours_to_report": hours, "within_72h": 0 <= hours <= claim.WINDOW_H}
    checks = [{"text": _t(c.get("text"), 300), "done": bool(c.get("done"))} for c in (payload.get("checklist") if isinstance(payload.get("checklist"), list) else [])[:MAX_ITEMS] if isinstance(c, dict) and c.get("text")]
    items, photos = [], 0
    for e in (payload.get("evidence") if isinstance(payload.get("evidence"), list) else [])[:MAX_ITEMS]:
        if not isinstance(e, dict):
            continue
        kind = e.get("kind") if e.get("kind") in ("photo", "note", "document") else "note"
        img = e.get("data_url") if (kind == "photo" and payload.get("include_photos") and photos < MAX_PHOTOS) else None
        if img and (len(img) > MAX_PHOTO_CHARS or not DATA_URL.match(img)):
            img = None
        photos += bool(img)
        taken = _dt(e.get("taken_at"))
        items.append({"kind": kind, "label": _t(e.get("label"), 200), "taken_at": taken.isoformat() if taken else "", "img": img})
    place = ", ".join(x for x in (prof.get("district"), prof.get("state")) if x)
    ist = lambda d: d.strftime("%d %b %Y %H:%M UTC")
    rows = [(L["crop"], _t(loss.get("crop") or prof.get("main_crop"), 40)), (L["acres"], _t(loss.get("acres"), 10)), (L["place"], _t(place, 80)), (L["policy"], _t(payload.get("policy_no"), 40)),
            (L["complaint"], _t(payload.get("complaint_no"), 40)), (L["cause"], _t(cause_label)), (L["when"], ist(occurred))]
    h = [f"<!doctype html><html lang='{lang}'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{_t(L['title'])}</title>",
         "<style>body{font-family:system-ui,Arial,sans-serif;max-width:760px;margin:24px auto;padding:0 16px;color:#1b1b1b}h1{font-size:22px}h2{font-size:16px;border-bottom:1px solid #ccc;padding-bottom:4px;margin-top:24px}"
         "table{border-collapse:collapse;width:100%}td{padding:4px 8px;border-bottom:1px solid #eee;vertical-align:top}td:first-child{width:38%;color:#555}.ok{color:#1a7f37}.no{color:#b42318}"
         "img{max-width:100%;max-height:320px;border:1px solid #ccc;border-radius:6px}.ev{margin:12px 0}.disc{margin-top:28px;padding:10px;background:#fff6e0;border:1px solid #e0c36b;border-radius:6px;font-size:13px}@media print{.disc{break-inside:avoid}}</style></head><body>",
         f"<h1>{_t(L['title'])}</h1><p style='color:#666'>{_t(L['gen'])}: {ist(datetime.now(timezone.utc))}</p>", f"<h2>{_t(L['loss'])}</h2><table>"]
    h += [f"<tr><td>{_t(k)}</td><td>{v or '-'}</td></tr>" for k, v in rows] + ["</table>"]
    h.append(f"<p>{html.escape(L['window_yes'].format(h=window['hours_to_report']) if window and window['within_72h'] else L['window_no'].format(h=window['hours_to_report']) if window else L['window_na'])}</p>")
    h.append(f"<h2>{_t(L['check'])}</h2>" + ("<ul>" + "".join(f"<li class='{'ok' if c['done'] else 'no'}'>{'✔' if c['done'] else '✖'} {c['text']}</li>" for c in checks) + "</ul>" if checks else f"<p>{_t(L['none'])}</p>"))
    h.append(f"<h2>{_t(L['ev'])}</h2>")
    for e in items:
        h.append(f"<div class='ev'><b>{_t(L[e['kind']])}</b>: {e['label'] or '-'} {('<small>(' + html.escape(e['taken_at']) + ')</small>') if e['taken_at'] else ''}" + (f"<br><img src='{e['img']}' alt=''>" if e["img"] else "") + "</div>")
    if not items:
        h.append(f"<p>{_t(L['none'])}</p>")
    h.append(f"<h2>{_t(L['tl'])}</h2>" + ("<ol>" + "".join(f"<li><b>{_t(L['stage'][x['stage']])}</b> · {ist(x['date'])}" + (f"<br>{x['note']}" if x["note"] else "") + "</li>" for x in timeline) + "</ol>" if timeline else f"<p>{_t(L['none'])}</p>"))
    h.append(f"<div class='disc'>{_t(L['disc'], 600)}</div></body></html>")
    cur = timeline[-1]["stage"] if timeline else None
    return {"html": "".join(h), "filename": f"krishi-mitra-claim-{occurred.strftime('%Y%m%d')}.html", "window": window, "current_stage": cur,
            "checklist_done": sum(c["done"] for c in checks), "checklist_total": len(checks), "evidence_items": len(items), "photos_embedded": photos,
            "stage_text": L["stage"].get(cur) if cur else None, "disclaimer": L["disc"]}
