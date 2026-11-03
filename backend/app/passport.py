"""Farm Sustainability Passport: a plain report of what the farmer's OWN records on the phone support, and nothing else.

The rule is evidence first. A line goes under "What the records support" only if it is computed from records on the phone (irrigation log, Khata,
field notes, expert cases, safety checks, logged advice) or the farmer attached a dated photo, receipt or record to a practice they declare.
A practice declared without evidence is listed under "Not claimed yet" with the exact next step. There is no score, no badge, no certification
wording, no carbon or emission figure and no forecast. "Not independently verified" is stated wherever evidence is only attached by the farmer.
Savings are claimed only when a baseline exists, the log spans four weeks with four irrigations and the farmer says every irrigation was logged
(a missing log would fake a saving). Absence claims (for example "no synthetic pesticide") cannot be shown from phone records and are never supported.
Computed in code, never by a model.
"""
import datetime as dt

L_PER_MM_ACRE = 4046.86
EVIDENCE_KINDS = ("photo", "receipt", "record")
PRACTICES = ("residue_not_burned", "mulching", "drip_or_sprinkler", "rainwater_harvest", "compost_or_manure", "legume_or_cover", "solar_pump", "no_synthetic_pesticide")
ABSENCE = {"no_synthetic_pesticide"}
MIN_IRR, MIN_SPAN_DAYS = 4, 28

P = {  # practice names
    "en": {"residue_not_burned": "Crop residue not burned (incorporated, mulched or removed)", "mulching": "Mulching", "drip_or_sprinkler": "Drip or sprinkler irrigation", "rainwater_harvest": "Rainwater harvesting",
           "compost_or_manure": "Compost or farmyard manure applied", "legume_or_cover": "Legume or cover crop grown", "solar_pump": "Solar pump", "no_synthetic_pesticide": "No synthetic pesticide used"},
    "te": {"residue_not_burned": "పంట అవశేషాలు కాల్చలేదు (కలిపేశాను, మల్చ్ చేశాను లేదా తీసేశాను)", "mulching": "మల్చింగ్", "drip_or_sprinkler": "డ్రిప్ లేదా స్ప్రింక్లర్ సాగు నీరు", "rainwater_harvest": "వర్షపు నీటి సేకరణ",
           "compost_or_manure": "కంపోస్ట్ లేదా పశువుల ఎరువు వేశాను", "legume_or_cover": "పప్పు జాతి లేదా కవర్ పంట వేశాను", "solar_pump": "సోలార్ పంపు", "no_synthetic_pesticide": "రసాయన పురుగుమందు వాడలేదు"},
    "hi": {"residue_not_burned": "फसल अवशेष नहीं जलाए (मिलाए, मल्च किए या हटाए)", "mulching": "मल्चिंग", "drip_or_sprinkler": "ड्रिप या स्प्रिंकलर सिंचाई", "rainwater_harvest": "वर्षा जल संचयन",
           "compost_or_manure": "कम्पोस्ट या गोबर की खाद डाली", "legume_or_cover": "दलहन या कवर फसल उगाई", "solar_pump": "सोलर पंप", "no_synthetic_pesticide": "रासायनिक कीटनाशक नहीं डाला"},
}
EV = {"en": {"photo": "photo", "receipt": "receipt", "record": "record"}, "te": {"photo": "ఫోటో", "receipt": "రసీదు", "record": "రికార్డు"}, "hi": {"photo": "फ़ोटो", "receipt": "रसीद", "record": "रिकॉर्ड"}}
CAT = {"en": {"fertilizer": "fertiliser", "pesticide": "crop protection", "seed": "seed"}, "te": {"fertilizer": "ఎరువులు", "pesticide": "పంట రక్షణ", "seed": "విత్తనాలు"}, "hi": {"fertilizer": "खाद", "pesticide": "फसल सुरक्षा", "seed": "बीज"}}

T = {
    "en": {
        "title": "Farm Sustainability Passport", "sec_ok": "What the records support", "sec_no": "Not claimed yet", "sec_never": "This passport never claims",
        "st_recorded": "From records on this phone", "st_attached": "Evidence attached by the farmer, not independently verified",
        "water_recorded": "Water use is recorded: {n} irrigations between {a} and {b}, {mm} mm in total{lit}.", "lit": " (about {l} litres on {ac} acres)",
        "water_saving": "Water use was {pct}% below your own usual amount over {w} weeks: {used} mm used against {base} mm. Your usual amount is your own baseline, not a standard.",
        "inputs": "Input spending is recorded in {n} entries: {cats}. This is money spent, not the quantity used.", "rotation": "Records show entries for {k} crops: {list}. This shows what was grown, not a planned rotation.",
        "obs": "{n} field notes and {m} expert cases are recorded between {a} and {b}{hi}.", "obs_hi": ", {h} of them high urgency", "safety": "{n} machine safety checks are logged, the last on {d}; {s} ended in STOP. A logged check shows the check was run, not that the machine was operated safely.",
        "decisions": "{n} advice items are logged; {d} marked done; {r} with a result entered.",
        "practice_ok": "{p}: evidence attached ({kind}, {date}: {note}).",
        "no_water_recorded": ("Water use is not recorded", "No irrigation with a date and mm is logged.", "Log each irrigation in Water and pump cost."),
        "no_water_saving": {"nobase": ("Water saving is not claimed", "No usual weekly amount (baseline) is set.", "Enter your usual water per week in Water and pump cost."),
                            "few": ("Water saving is not claimed", "Fewer than {m} irrigations are logged.", "Log every irrigation for at least four weeks."),
                            "short": ("Water saving is not claimed", "The log covers less than {d} days.", "Keep logging for at least four weeks."),
                            "incomplete": ("Water saving is not claimed", "You have not confirmed that every irrigation was logged. A missing log would look like a saving.", "Confirm only if every irrigation in the period was logged."),
                            "none": ("Water saving is not claimed", "Water used was not below your usual amount.", "Nothing to claim for this period.")},
        "no_inputs": ("Reduced fertiliser or crop-protection use is not claimed", "Spend is not use: a lower bill can come from lower prices, and this app records spend, not quantity.", "Record the quantity used each season before comparing seasons."),
        "no_rotation": ("Crop rotation is not claimed", "Records show fewer than two different crops.", "Record expenses or sales against each crop you grow."),
        "no_practice": ("{p}: not claimed", "You said you do this, but no dated photo, receipt or record is attached.", "Attach a dated photo, receipt or record with a short note."),
        "no_absence": ("{p}: not claimed", "An absence cannot be shown by a photo or receipt, so phone records cannot support it.", "Ask an agriculture officer or a certifier to inspect the field."),
        "never": ["Organic or any certified status", "Carbon, emission or climate-benefit figures", "Yield, income or price forecasts", "Anything not in the records above"],
        "basis": "Built from records kept on this phone. The server only calculates the report from what is sent and stores nothing.", "disclaimer": "This is a record summary, not a certificate or an audit. The farmer's own attached evidence is not independently verified.",
        "farm": "Field", "date": "Date", "none_ok": "No claim is supported by the records yet."},
    "te": {
        "title": "వ్యవసాయ సుస్థిరత పాస్‌పోర్ట్", "sec_ok": "రికార్డులు ఏమి నిరూపిస్తున్నాయి", "sec_no": "ఇంకా క్లెయిమ్ చేయనివి", "sec_never": "ఈ పాస్‌పోర్ట్ ఎప్పుడూ చెప్పనివి",
        "st_recorded": "ఈ ఫోన్‌లోని రికార్డుల నుంచి", "st_attached": "రైతు జత చేసిన ఆధారం, స్వతంత్రంగా ధృవీకరించలేదు",
        "water_recorded": "నీటి వినియోగం నమోదైంది: {a} నుంచి {b} మధ్య {n} సార్లు నీరు పెట్టారు, మొత్తం {mm} మి.మీ{lit}.", "lit": " ({ac} ఎకరాలకు సుమారు {l} లీటర్లు)",
        "water_saving": "{w} వారాల్లో మీ సాధారణ మొత్తం కన్నా {pct}% తక్కువ నీరు వాడారు: {base} మి.మీ బదులు {used} మి.మీ. మీ సాధారణ మొత్తం మీ సొంత ప్రమాణం మాత్రమే, ఇది ప్రమాణం కాదు.",
        "inputs": "{n} నమోదులలో ఇన్‌పుట్ ఖర్చు నమోదైంది: {cats}. ఇది ఖర్చు చేసిన డబ్బు, వాడిన పరిమాణం కాదు.", "rotation": "{k} పంటలకు నమోదులు ఉన్నాయి: {list}. ఇది ఏమి పండించారో చూపుతుంది, ప్రణాళికాబద్ధమైన పంట మార్పిడి కాదు.",
        "obs": "{a} నుంచి {b} మధ్య {n} పొలం నోట్లు, {m} నిపుణుల కేసులు నమోదయ్యాయి{hi}.", "obs_hi": ", వాటిలో {h} అత్యవసరం", "safety": "{n} యంత్ర భద్రత తనిఖీలు నమోదయ్యాయి, చివరిది {d}; {s} 'ఆపండి'తో ముగిశాయి. తనిఖీ నమోదైతే తనిఖీ చేశారని మాత్రమే అర్థం, యంత్రాన్ని సురక్షితంగా నడిపారని కాదు.",
        "decisions": "{n} సలహాలు నమోదయ్యాయి; {d} పూర్తయ్యాయి; {r} కు ఫలితం నమోదైంది.",
        "practice_ok": "{p}: ఆధారం జతచేశారు ({kind}, {date}: {note}).",
        "no_water_recorded": ("నీటి వినియోగం నమోదు కాలేదు", "తేదీ, మి.మీ తో ఏ నీటి పారుదల నమోదు కాలేదు.", "నీరు, పంపు ఖర్చులో ప్రతి నీటి పారుదలను నమోదు చేయండి."),
        "no_water_saving": {"nobase": ("నీటి ఆదా క్లెయిమ్ చేయలేదు", "సాధారణ వారపు మొత్తం (బేస్‌లైన్) నమోదు చేయలేదు.", "నీరు, పంపు ఖర్చులో మీ సాధారణ వారపు నీరు నమోదు చేయండి."),
                            "few": ("నీటి ఆదా క్లెయిమ్ చేయలేదు", "{m} కన్నా తక్కువ నీటి పారుదలలు నమోదయ్యాయి.", "కనీసం నాలుగు వారాలు ప్రతి నీటి పారుదలను నమోదు చేయండి."),
                            "short": ("నీటి ఆదా క్లెయిమ్ చేయలేదు", "నమోదు {d} రోజుల కన్నా తక్కువ కాలాన్ని కవర్ చేస్తోంది.", "కనీసం నాలుగు వారాలు నమోదు కొనసాగించండి."),
                            "incomplete": ("నీటి ఆదా క్లెయిమ్ చేయలేదు", "ప్రతి నీటి పారుదల నమోదైందని మీరు నిర్ధారించలేదు. నమోదు లేకపోతే ఆదా లాగా కనిపిస్తుంది.", "ఆ కాలంలో ప్రతి నీటి పారుదల నమోదైతేనే నిర్ధారించండి."),
                            "none": ("నీటి ఆదా క్లెయిమ్ చేయలేదు", "వాడిన నీరు మీ సాధారణ మొత్తం కన్నా తక్కువ కాదు.", "ఈ కాలానికి క్లెయిమ్ చేయడానికి ఏమీ లేదు.")},
        "no_inputs": ("ఎరువు లేదా పంట రక్షణ వాడకం తగ్గింది అని క్లెయిమ్ చేయలేదు", "ఖర్చు అంటే వాడకం కాదు: తక్కువ బిల్లు తక్కువ ధరల వల్ల కూడా రావచ్చు; ఈ యాప్ ఖర్చును నమోదు చేస్తుంది, పరిమాణాన్ని కాదు.", "సీజన్లను పోల్చే ముందు ప్రతి సీజన్‌లో వాడిన పరిమాణాన్ని నమోదు చేయండి."),
        "no_rotation": ("పంట మార్పిడి క్లెయిమ్ చేయలేదు", "రికార్డులలో రెండు కన్నా తక్కువ వేర్వేరు పంటలు ఉన్నాయి.", "మీరు పండించే ప్రతి పంటకు ఖర్చులు లేదా అమ్మకాలు నమోదు చేయండి."),
        "no_practice": ("{p}: క్లెయిమ్ చేయలేదు", "మీరు ఇది చేస్తున్నానని చెప్పారు, కానీ తేదీతో ఫోటో, రసీదు లేదా రికార్డు జతచేయలేదు.", "తేదీతో ఫోటో, రసీదు లేదా రికార్డును చిన్న నోట్‌తో జతచేయండి."),
        "no_absence": ("{p}: క్లెయిమ్ చేయలేదు", "లేకపోవడాన్ని ఫోటో లేదా రసీదుతో చూపలేం, కాబట్టి ఫోన్ రికార్డులు దీన్ని నిరూపించలేవు.", "వ్యవసాయ అధికారి లేదా సర్టిఫైయర్‌తో పొలాన్ని తనిఖీ చేయించండి."),
        "never": ["ఆర్గానిక్ లేదా ఏ ధృవీకరణ హోదా", "కార్బన్, ఉద్గారాలు లేదా వాతావరణ ప్రయోజన సంఖ్యలు", "దిగుబడి, ఆదాయం లేదా ధర అంచనాలు", "పై రికార్డులలో లేని ఏదైనా"],
        "basis": "ఈ ఫోన్‌లో ఉంచిన రికార్డులతో తయారైంది. పంపిన వివరాలతో సర్వర్ కేవలం లెక్కిస్తుంది, ఏదీ నిల్వ చేయదు.", "disclaimer": "ఇది రికార్డుల సారాంశం మాత్రమే, సర్టిఫికెట్ లేదా ఆడిట్ కాదు. రైతు జతచేసిన ఆధారాన్ని స్వతంత్రంగా ధృవీకరించలేదు.",
        "farm": "పొలం", "date": "తేదీ", "none_ok": "రికార్డులు ఇంకా ఏ క్లెయిమ్‌ను సమర్థించడం లేదు."},
    "hi": {
        "title": "खेत स्थिरता पासपोर्ट", "sec_ok": "रिकॉर्ड क्या साबित करते हैं", "sec_no": "अभी दावा नहीं किया", "sec_never": "यह पासपोर्ट कभी दावा नहीं करता",
        "st_recorded": "इस फ़ोन के रिकॉर्ड से", "st_attached": "किसान का जोड़ा सबूत, स्वतंत्र रूप से सत्यापित नहीं",
        "water_recorded": "पानी का उपयोग दर्ज है: {a} से {b} के बीच {n} सिंचाइयाँ, कुल {mm} मिमी{lit}.", "lit": " ({ac} एकड़ पर लगभग {l} लीटर)",
        "water_saving": "{w} हफ़्तों में आपकी अपनी सामान्य मात्रा से {pct}% कम पानी लगा: {base} मिमी की जगह {used} मिमी। आपकी सामान्य मात्रा आपका अपना आधार है, कोई मानक नहीं।",
        "inputs": "{n} प्रविष्टियों में इनपुट खर्च दर्ज है: {cats}। यह खर्च हुआ पैसा है, इस्तेमाल की मात्रा नहीं।", "rotation": "{k} फसलों की प्रविष्टियाँ हैं: {list}। यह दिखाता है क्या उगाया गया, योजनाबद्ध फसल चक्र नहीं।",
        "obs": "{a} से {b} के बीच {n} खेत नोट और {m} विशेषज्ञ केस दर्ज हैं{hi}.", "obs_hi": ", इनमें {h} बहुत ज़रूरी", "safety": "{n} मशीन सुरक्षा जाँच दर्ज हैं, आख़िरी {d} को; {s} 'रुकें' पर खत्म हुईं। दर्ज जाँच बताती है कि जाँच की गई, यह नहीं कि मशीन सुरक्षित चलाई गई।",
        "decisions": "{n} सलाहें दर्ज हैं; {d} पूरी हुईं; {r} का नतीजा दर्ज है।",
        "practice_ok": "{p}: सबूत जोड़ा गया ({kind}, {date}: {note}).",
        "no_water_recorded": ("पानी का उपयोग दर्ज नहीं", "तारीख और मिमी के साथ कोई सिंचाई दर्ज नहीं।", "पानी और पंप खर्च में हर सिंचाई दर्ज करें।"),
        "no_water_saving": {"nobase": ("पानी की बचत का दावा नहीं", "सामान्य साप्ताहिक मात्रा (आधार) नहीं डाली।", "पानी और पंप खर्च में अपना सामान्य साप्ताहिक पानी डालें।"),
                            "few": ("पानी की बचत का दावा नहीं", "{m} से कम सिंचाइयाँ दर्ज हैं।", "कम से कम चार हफ़्ते हर सिंचाई दर्ज करें।"),
                            "short": ("पानी की बचत का दावा नहीं", "रिकॉर्ड {d} दिन से कम का है।", "कम से कम चार हफ़्ते रिकॉर्ड रखें।"),
                            "incomplete": ("पानी की बचत का दावा नहीं", "आपने पुष्टि नहीं की कि हर सिंचाई दर्ज है। छूटा रिकॉर्ड बचत जैसा दिखेगा।", "तभी पुष्टि करें जब उस अवधि की हर सिंचाई दर्ज हो।"),
                            "none": ("पानी की बचत का दावा नहीं", "इस्तेमाल हुआ पानी आपकी सामान्य मात्रा से कम नहीं था।", "इस अवधि के लिए दावा करने को कुछ नहीं।")},
        "no_inputs": ("खाद या फसल सुरक्षा में कमी का दावा नहीं", "खर्च इस्तेमाल नहीं है: कम बिल सस्ते दाम से भी आ सकता है, और यह ऐप खर्च दर्ज करता है, मात्रा नहीं।", "सीज़न की तुलना से पहले हर सीज़न की इस्तेमाल की मात्रा दर्ज करें।"),
        "no_rotation": ("फसल चक्र का दावा नहीं", "रिकॉर्ड में दो से कम अलग फसलें हैं।", "हर उगाई फसल के नाम से खर्च या बिक्री दर्ज करें।"),
        "no_practice": ("{p}: दावा नहीं", "आपने कहा कि आप यह करते हैं, पर तारीख वाला फ़ोटो, रसीद या रिकॉर्ड नहीं जुड़ा।", "तारीख वाला फ़ोटो, रसीद या रिकॉर्ड छोटे नोट के साथ जोड़ें।"),
        "no_absence": ("{p}: दावा नहीं", "किसी चीज़ का न होना फ़ोटो या रसीद से नहीं दिखाया जा सकता, इसलिए फ़ोन रिकॉर्ड इसे साबित नहीं कर सकते।", "कृषि अधिकारी या प्रमाणन संस्था से खेत की जाँच करवाएँ।"),
        "never": ["जैविक या कोई प्रमाणित दर्जा", "कार्बन, उत्सर्जन या जलवायु लाभ के आँकड़े", "उपज, आय या भाव के अनुमान", "ऊपर के रिकॉर्ड में न हो ऐसा कुछ भी"],
        "basis": "इस फ़ोन में रखे रिकॉर्ड से बना। सर्वर भेजे गए विवरण से सिर्फ़ गणना करता है और कुछ भी सहेजता नहीं।", "disclaimer": "यह रिकॉर्ड का सार है, प्रमाणपत्र या ऑडिट नहीं। किसान का जोड़ा सबूत स्वतंत्र रूप से सत्यापित नहीं है।",
        "farm": "खेत", "date": "तारीख", "none_ok": "रिकॉर्ड अभी किसी दावे का समर्थन नहीं करते।"},
}


def _en(x: str) -> str:
    for a, b in (("1 irrigations", "1 irrigation"), ("1 entries", "1 entry"), ("1 crops", "1 crop"), ("1 field notes", "1 field note"), ("1 expert cases", "1 expert case"),
                 ("1 machine safety checks are", "1 machine safety check is"), ("1 advice items are", "1 advice item is"), ("; 1 ended", "; 1 ended")):
        x = x.replace(a, b)
    return x


def _d(v):
    try:
        return dt.date.fromisoformat(str(v)[:10])
    except Exception:
        return None


def _n(v, lo=0.0, hi=1e9):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if lo <= x <= hi else None


def _rows(v, cap):
    return [x for x in v if isinstance(x, dict)][:cap] if isinstance(v, list) else []


def build(payload: dict, lang: str = "en", today: dt.date | None = None) -> dict:
    lang = lang if lang in T else "en"
    t, today = T[lang], today or dt.date.today()
    p = payload or {}
    farm = p.get("farm") if isinstance(p.get("farm"), dict) else {}
    acres = _n(farm.get("acres"), 0.01, 100000)
    ok, no = [], []
    fx = _en if lang == "en" else (lambda x: x)

    def good(code, kind, status, text, evidence=None):
        ok.append({"code": code, "kind": kind, "status": status, "status_text": t["st_" + status], "text": fx(text), "evidence": evidence or []})

    # --- water (irrigation log)
    irr = []
    for e in _rows(p.get("irrigation"), 400):
        d, mm = _d(e.get("date")), _n(e.get("mm"), 0.01, 2000)
        if d and mm and d <= today:
            irr.append((d, mm))
    irr.sort()
    if irr:
        tot = round(sum(m for _, m in irr), 1)
        lit = t["lit"].format(l=f"{round(tot * acres * L_PER_MM_ACRE):,}", ac=f"{acres:g}") if acres else ""
        good("water_recorded", "record", "recorded", t["water_recorded"].format(n=len(irr), a=irr[0][0].isoformat(), b=irr[-1][0].isoformat(), mm=f"{tot:g}", lit=lit))
        base = _n((p.get("irrigation_baseline_mm_per_week")), 1, 2000)
        span = (irr[-1][0] - irr[0][0]).days
        why = None
        if not base: why = "nobase"
        elif len(irr) < MIN_IRR: why = "few"
        elif span < MIN_SPAN_DAYS: why = "short"
        elif p.get("irrigation_log_complete") is not True: why = "incomplete"
        else:
            weeks = span / 7
            allowed = base * weeks
            if tot < allowed:
                good("water_saving", "record", "recorded", t["water_saving"].format(pct=round((allowed - tot) / allowed * 100), w=f"{round(weeks, 1):g}", used=f"{tot:g}", base=f"{round(allowed, 1):g}"))
            else:
                why = "none"
        if why:
            h, r, n_ = t["no_water_saving"][why]
            no.append({"code": "water_saving", "text": h, "why": r.format(m=MIN_IRR, d=MIN_SPAN_DAYS), "next": n_})
    else:
        h, r, n_ = t["no_water_recorded"]
        no.append({"code": "water_recorded", "text": h, "why": r, "next": n_})

    # --- inputs (Khata spend) and crops grown
    kh = [(e, _d(e.get("date"))) for e in _rows(p.get("khata"), 600)]
    spend = {}
    for e, d in kh:
        amt = _n(e.get("amount_rs"), 0.01, 1e9)
        if e.get("type") == "expense" and e.get("category") in CAT["en"] and amt and d and d <= today:
            c = spend.setdefault(e["category"], [0, 0]); c[0] += amt; c[1] += 1
    if spend:
        cats = ", ".join(f"{CAT[lang][k]} ₹{round(v[0]):,}" for k, v in sorted(spend.items()))
        good("inputs_recorded", "record", "recorded", t["inputs"].format(n=sum(v[1] for v in spend.values()), cats=cats))
    no.append({"code": "input_reduction", "text": t["no_inputs"][0], "why": t["no_inputs"][1], "next": t["no_inputs"][2]})
    crops = {}
    for e, d in kh:
        c = str(e.get("crop") or "").strip().lower()[:40]
        if c and d and d <= today:
            lo, hi = crops.get(c, (d, d)); crops[c] = (min(lo, d), max(hi, d))
    if len(crops) >= 2:
        good("rotation", "record", "recorded", t["rotation"].format(k=len(crops), list="; ".join(f"{c.title()} ({a.isoformat()} to {b.isoformat()})" for c, (a, b) in sorted(crops.items(), key=lambda kv: kv[1][0]))))
    else:
        no.append({"code": "rotation", "text": t["no_rotation"][0], "why": t["no_rotation"][1], "next": t["no_rotation"][2]})

    # --- field observations, safety checks, logged advice
    notes = [d for d in (_d(e.get("at")) for e in _rows(p.get("notes"), 100)) if d and d <= today]
    cases = [(_d(e.get("at")), e.get("urgency")) for e in _rows(p.get("cases"), 100)]
    cases = [(d, u) for d, u in cases if d and d <= today]
    ds = notes + [d for d, _ in cases]
    if ds:
        high = sum(1 for _, u in cases if u == "high")
        good("observations", "record", "recorded", t["obs"].format(n=len(notes), m=len(cases), a=min(ds).isoformat(), b=max(ds).isoformat(), hi=t["obs_hi"].format(h=high) if high else ""))
    sf = [(_d(e.get("date")), e.get("level")) for e in _rows(p.get("safety"), 200)]
    sf = [(d, lv) for d, lv in sf if d and d <= today]
    if sf:
        good("machine_safety", "record", "recorded", t["safety"].format(n=len(sf), d=max(d for d, _ in sf).isoformat(), s=sum(1 for _, lv in sf if lv == "stop")))
    oc = _rows(p.get("outcomes"), 300)
    if oc:
        good("decisions", "record", "recorded", t["decisions"].format(n=len(oc), d=sum(1 for o in oc if o.get("done") is True), r=sum(1 for o in oc if isinstance(o.get("actual"), dict) and o["actual"])))

    # --- practices the farmer declares: supported only with dated evidence; absence claims never
    seen = set()
    for e in _rows(p.get("practices"), 20):
        code = e.get("code")
        if code not in PRACTICES or code in seen:
            continue
        seen.add(code)
        name = P[lang][code]
        if code in ABSENCE:
            h, r, n_ = t["no_absence"]; no.append({"code": code, "text": h.format(p=name), "why": r, "next": n_}); continue
        ev = e.get("evidence") if isinstance(e.get("evidence"), dict) else {}
        d, note = _d(ev.get("date")), str(ev.get("note") or "").strip()
        if ev.get("kind") in EVIDENCE_KINDS and d and d <= today and len(note) >= 5:
            good(code, "practice", "attached", t["practice_ok"].format(p=name, kind=EV[lang][ev["kind"]], date=d.isoformat(), note=note[:120]), [ev["kind"]])
        else:
            h, r, n_ = t["no_practice"]; no.append({"code": code, "text": h.format(p=name), "why": r, "next": n_})

    farm_line = ", ".join(x for x in (str(farm.get("crop") or "").strip()[:40], str(farm.get("place") or "").strip()[:60], (f"{acres:g} acres" if acres else "")) if x)
    lines = [t["title"], f"{t['date']}: {today.isoformat()}" + (f" · {t['farm']}: {farm_line}" if farm_line else ""), "", t["sec_ok"].upper()]
    lines += [f"- {c['text']} [{c['status_text']}]" for c in ok] or [t["none_ok"]]
    lines += ["", t["sec_no"].upper()] + [f"- {c['text']}: {c['why']} → {c['next']}" for c in no]
    lines += ["", t["sec_never"].upper()] + [f"- {x}" for x in t["never"]] + ["", t["basis"], t["disclaimer"]]
    return {"title": t["title"], "generated": today.isoformat(), "farm": farm_line, "supported": ok, "not_claimed": no, "never": t["never"], "basis": t["basis"],
            "disclaimer": t["disclaimer"], "headings": {"ok": t["sec_ok"], "no": t["sec_no"], "never": t["sec_never"]}, "counts": {"supported": len(ok), "not_claimed": len(no)}, "text": "\n".join(lines)}
