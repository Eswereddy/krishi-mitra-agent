"""Krishi Machine Guardian: compares a short engine recording with the SAME machine's saved healthy recording and reports what changed.

Honest scope (shown to the farmer every time): there is no trained model and no library of real engine faults behind this. It looks at a few
measurable things (steadiness of engine rate, regular pulses, sharp impulses, a new steady whine, hiss/rattle energy) and only claims a
change when it differs from the machine's own healthy baseline. Thresholds were tuned on synthetic signals and are NOT validated on real
machines. Possible causes are possibilities, never a diagnosis; a mechanic must inspect. Without a baseline it gives measurements and the
urgency of the symptoms the operator ticked, and no sound-based claim. No chemical or product names. Computed in code, not by a model.
"""
from . import guardian_dsp as dsp

MACHINES = ("tractor", "harvester", "pump", "other")
SYMPTOMS = ("smoke_black", "smoke_white_blue", "overheating", "oil_light", "loss_of_power", "hard_start", "vibration", "burning_smell", "leak", "grinding")
STOP_NOW = {"oil_light", "burning_smell", "overheating", "grinding"}
SOON = {"smoke_black", "smoke_white_blue", "loss_of_power", "hard_start", "vibration", "leak"}
SPEED_TOL = 0.15
LANGS = ("en", "te", "hi")

# pattern -> {"t": title, "c": [possible causes], "s": [safe engine-off checks]} per language
P = {
    "unsteady_rate": {
        "en": ("Engine speed is hunting (rising and falling)", ["Fuel starvation or air in the fuel line", "Blocked fuel or air filter", "Governor or throttle linkage sticking"],
               ["Engine off and cool: check fuel level and fuel filter bowl for water or dirt", "Check the air filter and clean or replace it as per the manual", "Check throttle cable moves freely"]),
        "te": ("ఇంజిన్ వేగం పెరుగుతూ తగ్గుతోంది", ["ఇంధన సరఫరా తగ్గడం లేదా ఇంధన పైపులో గాలి", "ఇంధన లేదా ఎయిర్ ఫిల్టర్ మూసుకుపోవడం", "గవర్నర్ లేదా థ్రాటిల్ లింకేజ్ ఇరుక్కోవడం"],
               ["ఇంజిన్ ఆపి చల్లారాక: ఇంధనం స్థాయి, ఫిల్టర్ బౌల్‌లో నీరు/మురికి చూడండి", "ఎయిర్ ఫిల్టర్ చూసి మాన్యువల్ ప్రకారం శుభ్రం/మార్చండి", "థ్రాటిల్ కేబుల్ సులభంగా కదులుతోందో చూడండి"]),
        "hi": ("इंजन की गति ऊपर-नीचे हो रही है", ["ईंधन कम पहुँचना या ईंधन पाइप में हवा", "ईंधन या एयर फ़िल्टर जाम", "गवर्नर या थ्रॉटल लिंकेज अटकना"],
               ["इंजन बंद और ठंडा होने पर: ईंधन स्तर और फ़िल्टर बाउल में पानी/गंदगी देखें", "एयर फ़िल्टर देखकर मैनुअल के अनुसार साफ़/बदलें", "थ्रॉटल केबल आसानी से चल रही है या नहीं देखें"]),
    },
    "irregular_pulses": {
        "en": ("Engine beats are uneven, like a cylinder missing", ["Weak fuel supply to one cylinder", "Injector or valve clearance out of setting", "Air leak on the intake side"],
               ["Engine off and cool: look for loose or cracked fuel and air hoses", "Check the fuel filter", "Note when it happens (cold start, load, idle) and tell the mechanic"]),
        "te": ("ఇంజిన్ కొట్టుకోవడం అసమానంగా ఉంది, ఒక సిలిండర్ మిస్ అయినట్లు", ["ఒక సిలిండర్‌కు ఇంధనం తక్కువగా వెళ్లడం", "ఇంజెక్టర్ లేదా వాల్వ్ క్లియరెన్స్ సరిగా లేకపోవడం", "ఇన్‌టేక్ వైపు గాలి లీకేజ్"],
               ["ఇంజిన్ ఆపి చల్లారాక: ఇంధన/గాలి పైపులు వదులుగా లేదా పగిలాయేమో చూడండి", "ఇంధన ఫిల్టర్ చూడండి", "ఎప్పుడు జరుగుతోందో (చల్లగా స్టార్ట్, లోడ్, ఐడిల్) గమనించి మెకానిక్‌కు చెప్పండి"]),
        "hi": ("इंजन की धड़कन असमान है, जैसे एक सिलेंडर छूट रहा हो", ["एक सिलेंडर को ईंधन कम मिलना", "इंजेक्टर या वाल्व क्लियरेंस गड़बड़", "इनटेक की तरफ़ हवा का रिसाव"],
               ["इंजन बंद और ठंडा होने पर: ईंधन/हवा के पाइप ढीले या फटे तो नहीं देखें", "ईंधन फ़िल्टर देखें", "कब होता है (ठंडा स्टार्ट, लोड, आइडल) नोट करके मैकेनिक को बताएँ"]),
    },
    "knock_like": {
        "en": ("Sharp repeated knocks that were not in the healthy recording", ["Worn bearing or loose part inside the engine", "Injection timing or fuel quality problem", "Loose flywheel, pulley or mounting"],
               ["Stop running the engine under load", "Engine off: check oil level and look for loose bolts on pulley and mounts", "Have a mechanic inspect before further heavy work"]),
        "te": ("ఆరోగ్యకర రికార్డింగ్‌లో లేని పదునైన పునరావృత కొట్టుకునే శబ్దాలు", ["ఇంజిన్ లోపల బేరింగ్ అరుగుదల లేదా వదులైన భాగం", "ఇంజెక్షన్ టైమింగ్ లేదా ఇంధన నాణ్యత సమస్య", "ఫ్లైవీల్, పుల్లీ లేదా మౌంటింగ్ వదులు"],
               ["లోడ్ మీద ఇంజిన్ నడపడం ఆపండి", "ఇంజిన్ ఆపి: ఆయిల్ స్థాయి, పుల్లీ మరియు మౌంట్ బోల్టులు వదులుగా ఉన్నాయేమో చూడండి", "భారీ పనికి ముందు మెకానిక్‌తో చూపించండి"]),
        "hi": ("स्वस्थ रिकॉर्डिंग में न मौजूद तेज़ बार-बार ठक-ठक", ["इंजन के अंदर बेयरिंग घिसना या ढीला पुर्ज़ा", "इंजेक्शन टाइमिंग या ईंधन की गुणवत्ता की समस्या", "फ्लाईव्हील, पुली या माउंटिंग ढीली"],
               ["लोड में इंजन चलाना बंद करें", "इंजन बंद करके: तेल स्तर और पुली व माउंट के बोल्ट ढीले तो नहीं देखें", "भारी काम से पहले मैकेनिक से जाँच करवाएँ"]),
    },
    "rattle_hiss": {
        "en": ("More rattle or hiss than the healthy recording", ["Loose guard, shield or exhaust part", "Exhaust or intake leak", "Loose belt or worn pulley"],
               ["Engine off and cool: shake guards, shields and exhaust clamps by hand to find loose parts", "Check belt tension and condition", "Look and listen for a leak at the exhaust joint"]),
        "te": ("ఆరోగ్యకర రికార్డింగ్ కంటే ఎక్కువ గడగడ లేదా సుయ్ శబ్దం", ["గార్డ్, షీల్డ్ లేదా ఎగ్జాస్ట్ భాగం వదులు", "ఎగ్జాస్ట్ లేదా ఇన్‌టేక్ లీకేజ్", "బెల్ట్ వదులు లేదా పుల్లీ అరుగుదల"],
               ["ఇంజిన్ ఆపి చల్లారాక: గార్డ్‌లు, షీల్డ్‌లు, ఎగ్జాస్ట్ క్లాంపులను చేత్తో కదిపి వదులైనవి కనుక్కోండి", "బెల్ట్ బిగుతు, స్థితి చూడండి", "ఎగ్జాస్ట్ జాయింట్ దగ్గర లీకేజ్ చూడండి"]),
        "hi": ("स्वस्थ रिकॉर्डिंग से ज़्यादा खड़खड़ाहट या सीटी जैसी आवाज़", ["गार्ड, शील्ड या एग्ज़ॉस्ट का हिस्सा ढीला", "एग्ज़ॉस्ट या इनटेक में रिसाव", "बेल्ट ढीली या पुली घिसी"],
               ["इंजन बंद और ठंडा होने पर: गार्ड, शील्ड, एग्ज़ॉस्ट क्लैंप हाथ से हिलाकर ढीले हिस्से ढूँढें", "बेल्ट का कसाव और हालत देखें", "एग्ज़ॉस्ट जोड़ पर रिसाव देखें"]),
    },
    "whine_squeal": {
        "en": ("A new steady high whine or squeal", ["Dry or worn bearing (pump, alternator, fan, water pump)", "Slipping or glazed belt", "Gear or pump wear"],
               ["Engine off: spin fan, pulleys and pump shaft by hand and feel for roughness or play", "Check belt tension", "Check grease or oil points as per the manual"]),
        "te": ("కొత్త నిరంతర పదునైన కీచుమనే శబ్దం", ["బేరింగ్ పొడిబారడం లేదా అరుగుదల (పంపు, ఆల్టర్నేటర్, ఫ్యాన్, వాటర్ పంపు)", "బెల్ట్ జారడం లేదా గట్టిపడటం", "గేర్ లేదా పంపు అరుగుదల"],
               ["ఇంజిన్ ఆపి: ఫ్యాన్, పుల్లీలు, పంపు షాఫ్ట్‌ను చేత్తో తిప్పి గరుకుదనం లేదా ఆటను చూడండి", "బెల్ట్ బిగుతు చూడండి", "మాన్యువల్ ప్రకారం గ్రీజు/ఆయిల్ పాయింట్లు చూడండి"]),
        "hi": ("नई लगातार तेज़ सीटी या चीख़ जैसी आवाज़", ["बेयरिंग सूखी या घिसी (पंप, अल्टरनेटर, पंखा, वॉटर पंप)", "बेल्ट फिसलना या कड़ी हो जाना", "गियर या पंप घिसना"],
               ["इंजन बंद करके: पंखा, पुली और पंप शाफ्ट हाथ से घुमाकर खुरदरापन या ढीलापन देखें", "बेल्ट का कसाव देखें", "मैनुअल के अनुसार ग्रीस/तेल के बिंदु देखें"]),
    },
}

SYM = {
    "smoke_black": {"en": "Black smoke", "te": "నల్లని పొగ", "hi": "काला धुआँ"},
    "smoke_white_blue": {"en": "White or blue smoke", "te": "తెల్లని లేదా నీలి పొగ", "hi": "सफ़ेद या नीला धुआँ"},
    "overheating": {"en": "Overheating", "te": "ఇంజిన్ వేడెక్కడం", "hi": "इंजन गरम होना"},
    "oil_light": {"en": "Oil pressure warning", "te": "ఆయిల్ ప్రెషర్ హెచ్చరిక", "hi": "ऑयल प्रेशर चेतावनी"},
    "loss_of_power": {"en": "Loss of power", "te": "శక్తి తగ్గడం", "hi": "ताक़त घटना"},
    "hard_start": {"en": "Hard to start", "te": "స్టార్ట్ కావడం కష్టం", "hi": "स्टार्ट होने में दिक्कत"},
    "vibration": {"en": "Strong vibration", "te": "ఎక్కువ కంపనం", "hi": "तेज़ कंपन"},
    "burning_smell": {"en": "Burning smell", "te": "కాలిన వాసన", "hi": "जलने की गंध"},
    "leak": {"en": "Oil, fuel or water leak", "te": "ఆయిల్, ఇంధనం లేదా నీటి లీకేజ్", "hi": "तेल, ईंधन या पानी का रिसाव"},
    "grinding": {"en": "Grinding from gearbox, PTO or pump", "te": "గేర్‌బాక్స్, PTO లేదా పంపు నుంచి రాపిడి శబ్దం", "hi": "गियरबॉक्स, PTO या पंप से घिसने की आवाज़"},
}

U = {
    "stop_now": {"en": ("STOP NOW", "Switch the engine off safely, let it cool, and do not run it again until a mechanic has checked it."),
                 "te": ("ఇప్పుడే ఆపండి", "ఇంజిన్‌ను సురక్షితంగా ఆపి, చల్లారనివ్వండి. మెకానిక్ చూసే వరకు మళ్లీ నడపకండి."),
                 "hi": ("अभी रोकें", "इंजन सुरक्षित तरीके से बंद करें, ठंडा होने दें, और मैकेनिक की जाँच तक दोबारा न चलाएँ।")},
    "soon": {"en": ("GET IT CHECKED SOON", "Avoid heavy load. Arrange a mechanic check before the next long or heavy job."),
             "te": ("త్వరలో చూపించండి", "భారీ లోడ్ మానండి. తదుపరి పెద్ద పనికి ముందు మెకానిక్‌తో చూపించండి."),
             "hi": ("जल्दी जाँच करवाएँ", "भारी लोड से बचें। अगले लंबे या भारी काम से पहले मैकेनिक से जाँच करवाएँ।")},
    "monitor": {"en": ("KEEP WATCHING", "Fine for light work. Do the checks below and record again in a few days to see if it grows."),
                "te": ("గమనిస్తూ ఉండండి", "తేలికపాటి పనికి పర్వాలేదు. కింది తనిఖీలు చేసి, కొన్ని రోజుల తర్వాత మళ్లీ రికార్డ్ చేసి పెరిగిందో చూడండి."),
                "hi": ("नज़र रखें", "हल्के काम के लिए ठीक। नीचे की जाँच करें और कुछ दिन बाद दोबारा रिकॉर्ड करके देखें कि बढ़ा तो नहीं।")},
    "nothing_found": {"en": ("NO CHANGE FOUND", "Nothing in this recording differs from the healthy one. This does not prove the machine is healthy."),
                      "te": ("మార్పు కనబడలేదు", "ఈ రికార్డింగ్‌లో ఆరోగ్యకర దానికి భిన్నంగా ఏమీ కనబడలేదు. యంత్రం బాగుందని దీని అర్థం కాదు."),
                      "hi": ("कोई बदलाव नहीं मिला", "इस रिकॉर्डिंग में स्वस्थ रिकॉर्डिंग से अलग कुछ नहीं मिला। इसका मतलब यह नहीं कि मशीन ठीक है।")},
    "no_baseline": {"en": ("NO BASELINE", "Save a recording while the machine is running well, then compare later. Until then only measurements and your ticked symptoms are used."),
                    "te": ("బేస్‌లైన్ లేదు", "యంత్రం బాగా నడుస్తున్నప్పుడు ఒక రికార్డింగ్ సేవ్ చేయండి, తర్వాత పోల్చవచ్చు. అప్పటివరకు కొలతలు, మీరు టిక్ చేసిన లక్షణాలే వాడతాము."),
                    "hi": ("बेसलाइन नहीं है", "मशीन ठीक चलते समय एक रिकॉर्डिंग सहेजें, फिर बाद में तुलना करें। तब तक सिर्फ़ माप और आपके चुने लक्षण इस्तेमाल होंगे।")},
    "unreliable": {"en": ("CANNOT COMPARE", "Engine speed differs too much from the healthy recording. Record again at the same speed as the baseline."),
                   "te": ("పోల్చలేము", "ఇంజిన్ వేగం ఆరోగ్యకర రికార్డింగ్‌తో చాలా తేడాగా ఉంది. బేస్‌లైన్ వేగంతోనే మళ్లీ రికార్డ్ చేయండి."),
                   "hi": ("तुलना नहीं हो सकती", "इंजन की गति स्वस्थ रिकॉर्डिंग से बहुत अलग है। बेसलाइन वाली गति पर दोबारा रिकॉर्ड करें।")},
    "bad": {"en": ("RECORD AGAIN", "This recording cannot be used."),
            "te": ("మళ్లీ రికార్డ్ చేయండి", "ఈ రికార్డింగ్ వాడలేము."),
            "hi": ("दोबारा रिकॉर्ड करें", "यह रिकॉर्डिंग इस्तेमाल नहीं हो सकती।")},
}

BAD = {
    "short": {"en": "Too short: record at least 4 seconds of steady running.", "te": "చాలా చిన్నది: స్థిరంగా నడుస్తున్నప్పుడు కనీసం 4 సెకన్లు రికార్డ్ చేయండి.", "hi": "बहुत छोटी: स्थिर चलते इंजन की कम से कम 4 सेकंड रिकॉर्डिंग करें।"},
    "quiet": {"en": "Too quiet: hold the phone closer (about an arm's length from the engine, never near moving parts).", "te": "శబ్దం చాలా తక్కువ: ఫోన్‌ను దగ్గరగా పట్టండి (ఇంజిన్ నుంచి చేయి దూరం, కదిలే భాగాల దగ్గర కాదు).", "hi": "आवाज़ बहुत कम: फ़ोन पास लाएँ (इंजन से हाथ भर दूर, घूमते हिस्सों के पास नहीं)।"},
    "clipped": {"en": "Too loud, the sound is distorted: move the phone further away.", "te": "శబ్దం చాలా ఎక్కువ, వక్రీకరణ ఉంది: ఫోన్‌ను దూరంగా ఉంచండి.", "hi": "आवाज़ बहुत तेज़ और बिगड़ी हुई: फ़ोन थोड़ा दूर रखें।"},
    "unsteady_level": {"en": "Loudness changed a lot during the recording (engine speed or load changed). Keep speed steady.", "te": "రికార్డింగ్ సమయంలో శబ్దం బాగా మారింది (వేగం లేదా లోడ్ మారింది). వేగాన్ని స్థిరంగా ఉంచండి.", "hi": "रिकॉर्डिंग में आवाज़ बहुत बदली (गति या लोड बदला)। गति स्थिर रखें।"},
    "no_engine_rate": {"en": "Could not find a clear engine rhythm. Record closer to the engine at steady speed.", "te": "స్పష్టమైన ఇంజిన్ లయ దొరకలేదు. స్థిరమైన వేగంలో ఇంజిన్‌కు దగ్గరగా రికార్డ్ చేయండి.", "hi": "इंजन की साफ़ लय नहीं मिली। स्थिर गति पर इंजन के पास रिकॉर्ड करें।"},
}

NOTE = {
    "en": "This tool has no trained model and has not been tested on real machines. It only shows what changed compared with this machine's own healthy recording. Possible causes are possibilities, not a diagnosis. A mechanic must inspect. Never put hands, clothes or the phone near moving parts.",
    "te": "ఈ సాధనానికి శిక్షణ పొందిన మోడల్ లేదు, నిజమైన యంత్రాలపై పరీక్షించలేదు. ఈ యంత్రం యొక్క సొంత ఆరోగ్యకర రికార్డింగ్‌తో పోలిస్తే ఏమి మారిందో మాత్రమే చూపుతుంది. సాధ్యమైన కారణాలు అంచనాలు మాత్రమే, నిర్ధారణ కాదు. మెకానిక్ పరిశీలించాలి. కదిలే భాగాల దగ్గర చేతులు, బట్టలు, ఫోన్ ఉంచకండి.",
    "hi": "इस टूल में कोई प्रशिक्षित मॉडल नहीं है और इसे असली मशीनों पर परखा नहीं गया है। यह सिर्फ़ इस मशीन की अपनी स्वस्थ रिकॉर्डिंग से तुलना करके बदलाव दिखाता है। संभावित कारण अनुमान हैं, निदान नहीं। मैकेनिक को जाँचना होगा। घूमते हिस्सों के पास हाथ, कपड़े या फ़ोन न रखें।",
}
MECH = {"en": "Call a mechanic if the problem comes back after the checks, or if you see smoke, a leak, or a warning light.",
        "te": "తనిఖీల తర్వాత కూడా సమస్య ఉంటే, లేదా పొగ, లీకేజ్, హెచ్చరిక లైట్ కనబడితే మెకానిక్‌ను పిలవండి.",
        "hi": "जाँच के बाद भी समस्या रहे, या धुआँ, रिसाव या चेतावनी लाइट दिखे तो मैकेनिक बुलाएँ।"}


def _tr(d, lang):
    return d.get(lang) or d["en"]


def _near(a, b, tol):
    return abs(a - b) <= tol * b


def compare(feat, base):
    """Return pattern codes that differ from the baseline; empty list if none. Thresholds: heuristic, synthetic-tuned."""
    out = []
    if feat["f0_cv"] >= max(0.03, 3 * base["f0_cv"]):
        out.append("unsteady_rate")
        return out  # the rate itself is unstable; other shape measures are not meaningful then
    rattle = feat["hf_ratio"] >= max(0.1, base["hf_ratio"] + 0.08)
    if feat["impulses_per_s"] - base["impulses_per_s"] >= 3:
        out.append("knock_like")
    elif feat["subharmonic_ratio"] - base["subharmonic_ratio"] >= 0.12 or (not rattle and base["harmonic_ratio"] - feat["harmonic_ratio"] >= 0.12):
        out.append("irregular_pulses")
    if rattle:
        out.append("rattle_hiss")
    bt = [t["hz"] for t in base.get("tones", [])]
    if any(t["db"] >= 20 and t["hz"] >= 1000 and not any(_near(t["hz"], h, 0.04) for h in bt) for t in feat.get("tones", [])):
        out.append("whine_squeal")
    return out


def analyze(feat, bad, base, machine, symptoms, lang="en"):
    """feat/base: dicts from guardian_dsp.features; bad: quality reasons for feat."""
    lang = lang if lang in LANGS else "en"
    machine = machine if machine in MACHINES else "other"
    syms = [s for s in (symptoms or []) if s in SYMPTOMS]
    notes, patterns, state = [], [], None
    if bad:
        state = "bad"
        notes = [_tr(BAD[b], lang) for b in bad]
    else:
        if feat is None or feat.get("f0_hz") is None:
            notes.append(_tr(BAD["no_engine_rate"], lang))
        if feat and feat.get("level_cv", 0) > 0.25:
            notes.append(_tr(BAD["unsteady_level"], lang))
        if base is None:
            state = "no_baseline"
        elif feat.get("f0_hz") is None or base.get("f0_hz") is None or abs(feat["f0_hz"] - base["f0_hz"]) > SPEED_TOL * base["f0_hz"]:
            state = "unreliable"
        else:
            patterns = compare(feat, base)
            state = "found" if patterns else "nothing_found"
    if state == "bad":
        level = "bad"
    else:
        level = "ok"
        if any(p in ("unsteady_rate", "rattle_hiss") for p in patterns) or syms:
            level = "monitor"
        if any(p in ("knock_like", "irregular_pulses", "whine_squeal") for p in patterns) or any(s in SOON for s in syms):
            level = "soon"
        if any(s in STOP_NOW for s in syms) or ("knock_like" in patterns and any(s in ("loss_of_power", "vibration", "smoke_white_blue", "smoke_black") for s in syms)):
            level = "stop_now"
    head_key = {"stop_now": "stop_now", "soon": "soon", "monitor": "monitor", "bad": "bad"}.get(level)
    if head_key is None:
        head_key = state if state in ("nothing_found", "no_baseline", "unreliable") else "nothing_found"
    title, advice = _tr(U[head_key], lang)
    found = []
    for p in patterns:
        t, causes, steps = _tr(P[p], lang)
        found.append({"code": p, "title": t, "possible_causes": causes[:3], "checks": steps})
    sym_out = [{"code": s, "text": _tr(SYM[s], lang)} for s in syms]
    state_msg = _tr(U[state], lang)[1] if state in ("no_baseline", "unreliable") else None
    measures = None
    if feat and not bad:
        measures = {k: feat.get(k) for k in ("f0_hz", "f0_cv", "harmonic_ratio", "subharmonic_ratio", "hf_ratio", "impulses_per_s", "seconds")}
        measures["tones_hz"] = [t["hz"] for t in feat.get("tones", [])][:3]
    return {"level": level, "title": title, "advice": advice, "state": state, "state_note": state_msg, "machine": machine, "patterns": found,
            "symptoms": sym_out, "recording_notes": notes, "mechanic": _tr(MECH, lang), "measurements": measures,
            "validated": False, "note": _tr(NOTE, lang)}


def from_pcm(pcm, baseline, machine, symptoms, lang="en"):
    import numpy as np
    x = np.frombuffer(pcm[: 2 * dsp.SR * int(dsp.MAX_S)], dtype="<i2").astype(np.float64) / 32768.0
    bad = dsp.quality(x, dsp.SR)
    feat = None if bad else dsp.features(x)
    out = analyze(feat, bad, baseline, machine, symptoms, lang)
    out["features"] = feat  # the phone may keep these as this machine's healthy baseline; the recording itself is not kept
    return out
