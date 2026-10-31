"""Farm Doctor evidence: how far can the SAM 3.1 leaf measurement be trusted, what safe steps follow, and when a human must look.

Everything here is computed in code from the SAM masks and from the photo itself:
  * photo quality: brightness and sharpness (simple image statistics, heuristic thresholds)
  * reliability: clear / uncertain / retake, with the reasons, from mask confidence, whether a leaf was found, how close the damage
    is to a severity boundary, and the photo quality
  * escalation: when the case should go to an agricultural expert
  * safe steps: non-chemical care only. It never names a disease, a pesticide or a dose.
"""
from PIL import ImageFilter, ImageStat

DARK, BRIGHT, BLURRY = 35, 225, 3.0            # heuristic thresholds (mean brightness 0-255, edge strength)
MIN_SIDE = 200                                  # smaller images are too small to judge
CONF_CLEAR, CONF_LOW = 0.6, 0.4                 # mean / lowest SAM mask confidence
BOUNDARIES = (5, 25)                            # severity band edges (mild / moderate / severe)
NEAR = 2.0                                      # within this many points of a boundary = near the edge of a band
SEVERE_PCT = 25


def photo_quality(img) -> dict:
    gray = img.convert("L")
    small = gray.copy()
    small.thumbnail((320, 320))
    brightness = round(ImageStat.Stat(gray).mean[0])
    edges = small.filter(ImageFilter.FIND_EDGES)
    w, h = edges.size
    edges = edges.crop((2, 2, w - 2, h - 2)) if min(w, h) > 8 else edges            # the filter leaves artefacts on the border
    sharp = round(ImageStat.Stat(edges).stddev[0], 1)
    issues = []
    if min(img.size) < MIN_SIDE:
        issues.append("small")
    if brightness < DARK:
        issues.append("dark")
    elif brightness > BRIGHT:
        issues.append("bright")
    if sharp < BLURRY:
        issues.append("blurry")
    return {"brightness": brightness, "sharpness": sharp, "issues": issues, "ok": not issues}


def assess(result: dict, quality: dict) -> dict:
    """Reliability, confidence summary and escalation for a measure() result."""
    confs = [s["confidence"] for s in result.get("spots", []) if s.get("confidence") is not None]
    conf = {"lowest": min(confs), "mean": round(sum(confs) / len(confs), 2), "spots_with_confidence": len(confs)} if confs else None
    reasons = [f"photo_{i}" for i in quality["issues"]]
    if result["found"]:
        if not result.get("leaf_found"):
            reasons.append("leaf_not_found")
        if conf and conf["mean"] < CONF_CLEAR:
            reasons.append("low_confidence")
        if conf and conf["lowest"] < CONF_LOW:
            reasons.append("some_spots_doubtful")
        if any(abs(result["severity_pct"] - b) <= NEAR for b in BOUNDARIES):
            reasons.append("near_band_edge")
    elif not result.get("leaf_found"):
        reasons.append("nothing_recognised")
    retake = bool(quality["issues"]) or "nothing_recognised" in reasons
    reliability = "retake" if retake else "uncertain" if reasons else "clear"
    esc = []
    if result["found"] and result["severity_pct"] >= SEVERE_PCT:
        esc.append("severe_damage")
    if result["found"] and reliability != "clear":
        esc.append("not_reliable")
    return {"reliability": reliability, "reasons": reasons, "confidence": conf, "photo": quality,
            "escalation": {"needed": bool(esc), "reasons": esc}}


def step_codes(result: dict, reliability: str) -> list[str]:
    if reliability == "retake":
        return ["retake_light", "retake_close", "retake_one_leaf", "no_spray_without_advice"]
    band = result.get("band")
    if not result["found"]:
        return ["healthy_keep_scouting", "scout_again", "no_spray_without_advice"]
    base = ["remove_leaves", "keep_leaves_dry", "scout_again"]
    if band in ("moderate", "severe"):
        base += ["airflow_spacing", "clean_tools", "check_neighbours"]
    if band == "severe" or reliability == "uncertain":
        base.append("send_to_expert")
    return base + ["no_spray_without_advice"]


STEPS = {
    "en": {
        "retake_light": "Retake the photo in daylight, in the shade of your hand, not against the sun.",
        "retake_close": "Hold the phone steady about 20 cm from the leaf so the spots are sharp.",
        "retake_one_leaf": "Photograph one leaf with the whole leaf in view, on a plain background if possible.",
        "no_spray_without_advice": "Do not spray anything until an agriculture officer confirms the problem, the product and the dose.",
        "healthy_keep_scouting": "No spots were found in this photo. Early problems can be hidden: keep checking leaves, also the underside.",
        "scout_again": "Check the plants again in 3 days and take a new photo from the same spot to see if it is spreading.",
        "remove_leaves": "Remove the worst affected leaves by hand, put them in a bag away from the field (do not leave them on the ground).",
        "keep_leaves_dry": "Avoid watering the leaves, especially in the evening. Water at the base of the plant.",
        "airflow_spacing": "Open up the plants and remove dense weeds so air can pass and leaves dry quickly.",
        "clean_tools": "Wash hands and tools after touching affected plants, before touching healthy ones.",
        "check_neighbours": "Walk the rows around this plant and check 10 plants for the same signs.",
        "send_to_expert": "Send this evidence to an agriculture expert today (use Ask an expert).",
    },
    "te": {
        "retake_light": "పగటి వెలుతురులో, చేతి నీడలో ఫోటో మళ్లీ తీయండి. సూర్యునికి ఎదురుగా వద్దు.",
        "retake_close": "ఫోన్ ను ఆకుకు సుమారు 20 సెం.మీ. దూరంలో స్థిరంగా పట్టుకోండి, మచ్చలు స్పష్టంగా కనిపించాలి.",
        "retake_one_leaf": "ఒక ఆకు మొత్తం కనిపించేలా ఫోటో తీయండి, వీలైతే సాదా నేపథ్యంలో.",
        "no_spray_without_advice": "వ్యవసాయ అధికారి సమస్యను, మందును, మోతాదును నిర్ధారించే వరకు ఏమీ పిచికారీ చేయవద్దు.",
        "healthy_keep_scouting": "ఈ ఫోటోలో మచ్చలు కనిపించలేదు. మొదటి దశలో కనిపించకపోవచ్చు: ఆకులను (అడుగు భాగం కూడా) చూస్తూ ఉండండి.",
        "scout_again": "3 రోజుల తర్వాత మళ్లీ చూసి, అదే చోట నుంచి కొత్త ఫోటో తీయండి, వ్యాపిస్తోందో లేదో తెలుస్తుంది.",
        "remove_leaves": "ఎక్కువ దెబ్బతిన్న ఆకులను చేత్తో తీసి, పొలానికి దూరంగా సంచిలో వేయండి (నేలపై వదలవద్దు).",
        "keep_leaves_dry": "ఆకులపై నీరు పోయవద్దు, ముఖ్యంగా సాయంత్రం. మొక్క మొదట్లో నీరు పెట్టండి.",
        "airflow_spacing": "మొక్కల మధ్య గాలి తగిలేలా దట్టమైన కలుపు తీయండి, ఆకులు త్వరగా ఆరతాయి.",
        "clean_tools": "దెబ్బతిన్న మొక్కలను ముట్టుకున్న తర్వాత, ఆరోగ్యమైనవి ముట్టుకునే ముందు చేతులు, పనిముట్లు కడగండి.",
        "check_neighbours": "ఈ మొక్క చుట్టూ వరుసల్లో 10 మొక్కలను చూసి అవే లక్షణాలు ఉన్నాయేమో చూడండి.",
        "send_to_expert": "ఈ ఆధారాలను ఈ రోజే వ్యవసాయ నిపుణునికి పంపండి (నిపుణుని అడగండి వాడండి).",
    },
    "hi": {
        "retake_light": "दिन की रोशनी में, हाथ की छाया में फोटो दोबारा लें। सूरज के सामने नहीं।",
        "retake_close": "फोन को पत्ती से लगभग 20 सेमी दूर स्थिर पकड़ें ताकि धब्बे साफ़ दिखें।",
        "retake_one_leaf": "एक पूरी पत्ती दिखाते हुए फोटो लें, हो सके तो सादे पीछे के साथ।",
        "no_spray_without_advice": "कृषि अधिकारी समस्या, दवा और मात्रा पक्की न करें तब तक कुछ भी न छिड़कें।",
        "healthy_keep_scouting": "इस फोटो में धब्बे नहीं मिले। शुरुआती समस्या छिपी हो सकती है: पत्तियाँ (नीचे की तरफ़ भी) देखते रहें।",
        "scout_again": "3 दिन बाद फिर देखें और उसी जगह से नई फोटो लें, पता चलेगा फैल रहा है या नहीं।",
        "remove_leaves": "ज़्यादा प्रभावित पत्तियाँ हाथ से तोड़ें और खेत से दूर थैले में रखें (ज़मीन पर न छोड़ें)।",
        "keep_leaves_dry": "पत्तियों पर पानी न डालें, खासकर शाम को। पौधे की जड़ के पास पानी दें।",
        "airflow_spacing": "पौधों के बीच हवा चले, इसके लिए घना खरपतवार हटाएँ ताकि पत्तियाँ जल्दी सूखें।",
        "clean_tools": "प्रभावित पौधे छूने के बाद, स्वस्थ पौधे छूने से पहले हाथ और औज़ार धोएँ।",
        "check_neighbours": "इस पौधे के आसपास की कतारों में 10 पौधे देखें कि वही लक्षण हैं या नहीं।",
        "send_to_expert": "यह सबूत आज ही कृषि विशेषज्ञ को भेजें (विशेषज्ञ से पूछें इस्तेमाल करें)।",
    },
}
REASONS = {
    "en": {"photo_dark": "The photo is too dark.", "photo_bright": "The photo is too bright or washed out.",
           "photo_blurry": "The photo looks blurry or has little detail.", "photo_small": "The photo is too small.",
           "leaf_not_found": "The whole leaf was not found, so the damage is measured against the whole photo.",
           "low_confidence": "The model is not very sure about the marked spots.",
           "some_spots_doubtful": "Some marked spots are doubtful.",
           "near_band_edge": "The damage is close to the edge between two levels, so the level could change with a better photo.",
           "nothing_recognised": "No leaf or spots were recognised in this photo."},
    "te": {"photo_dark": "ఫోటో చాలా చీకటిగా ఉంది.", "photo_bright": "ఫోటో చాలా ప్రకాశవంతంగా ఉంది.",
           "photo_blurry": "ఫోటో అస్పష్టంగా ఉంది లేదా వివరాలు తక్కువ.", "photo_small": "ఫోటో చాలా చిన్నది.",
           "leaf_not_found": "మొత్తం ఆకు గుర్తించలేదు, కాబట్టి నష్టం మొత్తం ఫోటోతో పోల్చి కొలిచాం.",
           "low_confidence": "గుర్తించిన మచ్చలపై మోడల్ కు పూర్తి నమ్మకం లేదు.",
           "some_spots_doubtful": "కొన్ని మచ్చలు సందేహాస్పదం.",
           "near_band_edge": "నష్టం రెండు స్థాయిల అంచున ఉంది, మంచి ఫోటోతో స్థాయి మారవచ్చు.",
           "nothing_recognised": "ఈ ఫోటోలో ఆకు లేదా మచ్చలు గుర్తించలేదు."},
    "hi": {"photo_dark": "फोटो बहुत अँधेरी है।", "photo_bright": "फोटो बहुत चमकीली है।",
           "photo_blurry": "फोटो धुंधली है या उसमें कम विवरण है।", "photo_small": "फोटो बहुत छोटी है।",
           "leaf_not_found": "पूरी पत्ती नहीं मिली, इसलिए नुकसान पूरी फोटो के हिसाब से मापा गया।",
           "low_confidence": "मॉडल को चिह्नित धब्बों पर पूरा भरोसा नहीं है।",
           "some_spots_doubtful": "कुछ धब्बे संदिग्ध हैं।",
           "near_band_edge": "नुकसान दो स्तरों की सीमा के पास है, बेहतर फोटो से स्तर बदल सकता है।",
           "nothing_recognised": "इस फोटो में पत्ती या धब्बे नहीं पहचाने गए।"},
}
ESCALATION = {
    "en": {"severe_damage": "A large part of the leaf is marked.", "not_reliable": "The measurement is not reliable enough to act on alone."},
    "te": {"severe_damage": "ఆకులో పెద్ద భాగం గుర్తించబడింది.", "not_reliable": "కొలత ఒంటరిగా నమ్మి చర్య తీసుకునేంత నమ్మదగినది కాదు."},
    "hi": {"severe_damage": "पत्ती का बड़ा हिस्सा चिह्नित है।", "not_reliable": "यह माप अकेले भरोसे पर कदम उठाने लायक नहीं है।"},
}


def localize(result: dict, a: dict, lang: str) -> dict:
    """Add the farmer-facing texts (te, hi or en) to an assessment."""
    lg = lang if lang in STEPS else "en"
    codes = step_codes(result, a["reliability"])
    return {"steps": [{"code": c, "text": STEPS[lg][c]} for c in codes],
            "reason_texts": [{"code": r, "text": REASONS[lg][r]} for r in a["reasons"] if r in REASONS[lg]],
            "escalation_texts": [ESCALATION[lg][r] for r in a["escalation"]["reasons"]]}
