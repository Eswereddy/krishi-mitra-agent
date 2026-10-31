"""Crop coach: where is my crop today and what should I do this week? Works anywhere.

From the sowing date the coach works out the growth stage (days since sowing against an indicative crop duration),
lists the few jobs that matter at that stage, warns when the most water-sensitive stage meets a dry week, and says
how many days remain to the expected harvest. All of it is computed here in code from fixed tables and the forecast.
It never names pesticides or doses and always labels durations as indicative.
"""
import json
from datetime import date, datetime
from pathlib import Path

DATA = Path(__file__).parent / "data"
LATE_FACTOR = 1.3            # beyond 130% of the expected duration we stop pretending to know the stage
DRY_AHEAD_MM = 5             # less rain than this in the next 5 days = dry week ahead
_today = date.today          # tests replace this

TASKS = {
    "check_emergence": {"en": "Walk the field and check that the seedlings have come up evenly.",
                        "te": "పొలం తిరిగి మొలకలు సమానంగా వచ్చాయో చూడండి.", "hi": "खेत में घूमकर देखें कि अंकुर बराबर निकले हैं या नहीं।"},
    "fill_gaps": {"en": "Re-sow the gaps in the first week so the crop stays even.",
                  "te": "మొదటి వారంలోనే ఖాళీలలో మళ్లీ విత్తండి.", "hi": "पहले हफ़्ते में खाली जगहों पर दोबारा बुवाई करें।"},
    "keep_weed_free": {"en": "Keep the field weed-free: weeds steal water and nutrients most at this stage.",
                       "te": "కలుపు లేకుండా ఉంచండి: ఈ దశలో కలుపు నీరు, పోషకాలను ఎక్కువగా లాక్కుంటుంది.", "hi": "खेत को खरपतवार से मुक्त रखें: इस समय खरपतवार पानी और पोषक तत्व सबसे ज़्यादा छीनते हैं।"},
    "weed_first": {"en": "Do the main weeding now, while the weeds are still small.",
                   "te": "కలుపు చిన్నగా ఉన్నప్పుడే ఇప్పుడే ప్రధాన కలుపు తీయండి.", "hi": "खरपतवार छोटे हैं, अभी मुख्य निराई करें।"},
    "check_nutrition": {"en": "Look at leaf colour. Pale or yellow leaves can mean the crop needs feeding: ask your extension officer what and how much.",
                        "te": "ఆకు రంగు చూడండి. పాలిపోయిన లేదా పసుపు ఆకులు ఎరువు అవసరమని సూచించవచ్చు: ఏది, ఎంత అని వ్యవసాయ అధికారిని అడగండి.",
                        "hi": "पत्तियों का रंग देखें। पीली या फीकी पत्तियाँ खाद की ज़रूरत बता सकती हैं: क्या और कितनी, कृषि अधिकारी से पूछें।"},
    "scout": {"en": "Check 5 spots in the field twice a week for pests and disease. If something looks wrong, send a photo to Krishi Mitra.",
              "te": "వారానికి రెండుసార్లు పొలంలో 5 చోట్ల తెగుళ్లు, రోగాల కోసం చూడండి. ఏదైనా తేడాగా ఉంటే కృషి మిత్రకు ఫోటో పంపండి.",
              "hi": "हफ़्ते में दो बार खेत में 5 जगह कीट और रोग देखें। कुछ गड़बड़ लगे तो कृषि मित्र को फोटो भेजें।"},
    "water_critical": {"en": "This is the most water-sensitive stage: do not let the soil dry out.",
                       "te": "ఇది నీటికి అత్యంత సున్నితమైన దశ: నేల పొడిబారకుండా చూడండి.", "hi": "यह पानी के प्रति सबसे संवेदनशील अवस्था है: मिट्टी को सूखने न दें।"},
    "water_steady": {"en": "Keep soil moisture even: avoid both drought and waterlogging.",
                     "te": "నేల తేమ సమంగా ఉంచండి: కరువు, నీరు నిలవడం రెండూ వద్దు.", "hi": "मिट्टी की नमी बराबर रखें: सूखा और जलभराव दोनों से बचें।"},
    "stop_water": {"en": "Cut back irrigation as the crop matures so it ripens evenly.",
                   "te": "పంట పక్వానికి వస్తున్నందున నీటి తడులు తగ్గించండి.", "hi": "फसल पकने लगी है, सिंचाई कम करें ताकि बराबर पके।"},
    "watch_maturity": {"en": "Check the maturity signs and harvest at the right dryness to avoid losses.",
                       "te": "పక్వ లక్షణాలు చూసి సరైన ఆరిన స్థితిలో కోయండి, నష్టం తగ్గుతుంది.", "hi": "पकने के लक्षण देखें और सही सूखेपन पर कटाई करें ताकि नुकसान न हो।"},
    "plan_harvest": {"en": "Harvest is near: arrange labour, bags and transport, and check where to sell for the best price.",
                     "te": "కోత దగ్గరపడింది: కూలీలు, సంచులు, రవాణా సిద్ధం చేసుకోండి, ఎక్కడ అమ్మితే మంచి ధర వస్తుందో చూడండి.",
                     "hi": "कटाई पास है: मज़दूर, बोरे और ढुलाई तैयार करें, और देखें कहाँ बेचने पर अच्छा भाव मिलेगा।"},
    "dry_storage": {"en": "Prepare clean, dry storage: moisture spoils the harvest.",
                    "te": "శుభ్రమైన, పొడి నిల్వ సిద్ధం చేయండి: తేమ పంటను పాడుచేస్తుంది.", "hi": "साफ़ और सूखा भंडारण तैयार करें: नमी उपज खराब करती है।"},
}
STAGES = {
    "establishment": {"en": "Establishment", "te": "మొలక దశ", "hi": "अंकुरण"},
    "vegetative": {"en": "Vegetative growth", "te": "ఎదుగుదల దశ", "hi": "वानस्पतिक वृद्धि"},
    "flowering": {"en": "Flowering and fruit/pod set", "te": "పూత, కాత దశ", "hi": "फूल और फल/फली बनना"},
    "filling": {"en": "Grain / pod / fruit filling", "te": "గింజ, కాయ నిండే దశ", "hi": "दाना/फली/फल भरना"},
    "maturity": {"en": "Maturity and harvest", "te": "పక్వత, కోత దశ", "hi": "पकना और कटाई"},
}


def text(code: str, lang: str) -> str:
    return (TASKS.get(code) or {}).get(lang) or (TASKS.get(code) or {}).get("en", code)


def stage_label(name: str, lang: str) -> str:
    return STAGES[name].get(lang) or STAGES[name]["en"]


def _tables():
    return json.loads((DATA / "crop_stages.json").read_text())


def _parse(d) -> date | None:
    if isinstance(d, date):
        return d
    try:
        return datetime.strptime(str(d).strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def crop_guide(crop: str, sowing_date: str, place: str = "", country: str = "") -> dict:
    """Stage, this week's jobs, water warning and days to expected harvest for a crop sown on `sowing_date` (YYYY-MM-DD)."""
    from . import agro, tools
    c = agro._crop(crop)
    tb = _tables()
    if not c or c["id"] not in tb["durations"]:
        return {"error": f"no crop guide for '{crop}' yet", "known_crops": sorted(tb["durations"])}
    sown = _parse(sowing_date)
    if not sown:
        return {"error": "sowing date must look like 2026-07-15"}
    days = (_today() - sown).days
    dur = tb["durations"][c["id"]]
    base = {"crop": c["id"], "sowing_date": sown.isoformat(), "expected_duration_days": dur,
            "note": ("Crop duration and stage timing are indicative: varieties, season and climate shift them by weeks. "
                     "Watch the crop itself and confirm with your agriculture extension officer.")}
    if days < 0:
        return {**base, "status": "not_sown", "days_until_sowing": -days, "tasks": []}
    pct = days / dur * 100
    if pct > 100 * LATE_FACTOR:
        return {**base, "status": "past_expected_harvest", "day_of_crop": days, "tasks": []}
    stages = tb["stages"][tb["types"][c["id"]]]
    idx = next((i for i, s in enumerate(stages) if pct < s[2]), len(stages) - 1)
    name, lo, hi, task_codes, critical = stages[idx]
    out = {**base, "status": "growing", "day_of_crop": days, "progress_pct": round(min(pct, 100)), "stage": name,
           "stage_label": STAGES[name]["en"], "water_critical": critical,
           "days_to_expected_harvest": max(dur - days, 0),
           "tasks": [{"code": t, "text": TASKS[t]["en"]} for t in task_codes]}
    if idx + 1 < len(stages):
        out["next_stage"] = {"stage": stages[idx + 1][0], "in_days": max(round(hi / 100 * dur) - days, 0)}
    if critical and place:
        wx = tools.get_weather(place, 5)
        if "error" not in wx:
            rain = round(sum(x.get("rain_mm") or 0 for x in wx["forecast"][:5]), 1)
            out["rain_next_5_days_mm"] = rain
            out["dry_week_ahead"] = rain < DRY_AHEAD_MM
            if out["dry_week_ahead"]:
                out["tasks"].insert(0, {"code": "irrigate_now", "text": "Little rain is coming in this water-sensitive stage: irrigate if the soil is dry."})
    return out


TASKS["irrigate_now"] = {"en": "Little rain is coming in this water-sensitive stage: irrigate if the soil is dry.",
                         "te": "ఈ నీటికి సున్నితమైన దశలో వర్షం తక్కువగా వస్తోంది: నేల పొడిగా ఉంటే నీరు పెట్టండి.",
                         "hi": "इस संवेदनशील अवस्था में बारिश कम आ रही है: मिट्टी सूखी हो तो सिंचाई करें।"}

FUNCS = {"crop_guide": crop_guide}
SPECS = [{"type": "function", "function": {
    "name": "crop_guide",
    "description": ("Crop coach: from the sowing date, tells the growth stage, this week's jobs, whether a dry week meets the "
                    "water-sensitive stage, and days to expected harvest. Works in any country. Use for 'what should I do now "
                    "for my crop', 'how is my crop doing', 'when is harvest'. Needs the sowing date (profile sowing_date or ask once)."),
    "parameters": {"type": "object", "properties": {
        "crop": {"type": "string"}, "sowing_date": {"type": "string", "description": "YYYY-MM-DD"},
        "place": {"type": "string", "description": "village or district, for the rain check"},
        "country": {"type": "string"}}, "required": ["crop", "sowing_date"]}}}]
