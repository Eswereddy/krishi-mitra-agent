"""Crop-loss claim kit (PMFBY). The rule that costs farmers their claims: for localized calamities (hailstorm, local
flooding / inundation, landslide, cloudburst, fire) and for crop lying cut in the field after harvest hit by cyclone /
unseasonal rain, the loss must be INTIMATED within 72 hours. This module computes the exact deadline, says honestly when an
individual claim does not apply (area-level losses like drought are assessed by the government), and drafts the message.
All dates are computed in code. Rules summarised from the PMFBY operational guidelines: confirm with the insurer / agriculture
officer; helpline numbers are listed for that.
"""
from datetime import datetime, timedelta, timezone

from . import locale as loc

WINDOW_H = 72
LOCALIZED = ("hailstorm", "flood_local", "landslide", "cloudburst", "fire")
POST_HARVEST = ("post_harvest_rain",)
CAUSES = LOCALIZED + POST_HARVEST + ("other",)
HELPLINES = {"pmfby": "14447", "kisan_call_centre": "1800-180-1551"}

T = {
    "en": {
        "cause": {"hailstorm": "Hailstorm", "flood_local": "Local flooding / water-logging", "landslide": "Landslide",
                  "cloudburst": "Cloudburst", "fire": "Fire", "post_harvest_rain": "Cyclone / unseasonal rain on harvested crop drying in the field",
                  "other": "Drought, pest, disease or other"},
        "timed": "Report within 72 hours. Deadline: {d}.",
        "post": " This cover applies only up to 14 days after harvest, for crop left to dry in the field.",
        "area": "Losses like drought, widespread pest or disease are usually assessed for the whole area by the government (crop cutting experiments), so there is no 72-hour individual report. Ask the agriculture officer whether your area is notified, and keep your photos.",
        "check": ["Clear photos of the damaged crop and the whole field, taken today (with phone location and date switched on)",
                  "Insurance application receipt or policy number (PMFBY)", "Aadhaar and the bank passbook used for the policy",
                  "Land records (pattadar passbook / adangal) and survey number", "Crop name, sowing date and area in acres"],
        "how": "Call the crop insurance helpline {pmfby} (or your insurer, bank or agriculture officer) and report the loss, or use the Crop Insurance app. Note the complaint number they give.",
        "msg": ("To: The Agriculture Officer / Crop Insurance Company\nSubject: Intimation of crop loss under PMFBY\n\n"
                "I intimate a crop loss. Crop: {crop}. Area affected: {acres} acres. Cause: {cause}. Date and time of loss: {when}. "
                "Village / district: {place}. Policy / application number: [add]. Photos are attached. "
                "Please register this intimation and assess the loss.\n\nName: [add]   Mobile: [add]"),
    },
    "te": {
        "cause": {"hailstorm": "వడగళ్ల వాన", "flood_local": "స్థానిక వరద / నీరు నిలవడం", "landslide": "కొండచరియలు విరిగిపడటం",
                  "cloudburst": "మేఘ విస్ఫోటనం", "fire": "అగ్నిప్రమాదం", "post_harvest_rain": "కోసిన పంట పొలంలో ఆరబెట్టే సమయంలో తుఫాను / అకాల వర్షం",
                  "other": "కరువు, చీడపీడలు, తెగులు లేదా ఇతరం"},
        "timed": "72 గంటల్లో తెలియజేయాలి. గడువు: {d}.",
        "post": " ఇది కోత తర్వాత 14 రోజుల వరకు, పొలంలో ఆరబెట్టిన పంటకు మాత్రమే వర్తిస్తుంది.",
        "area": "కరువు, విస్తృతంగా చీడపీడలు లేదా తెగులు వంటి నష్టాలను ప్రభుత్వం మొత్తం ప్రాంతానికి అంచనా వేస్తుంది (పంట కోత ప్రయోగాలు), కాబట్టి 72 గంటల వ్యక్తిగత నివేదిక ఉండదు. మీ ప్రాంతం నోటిఫై అయిందో వ్యవసాయ అధికారిని అడగండి, ఫోటోలు దాచుకోండి.",
        "check": ["దెబ్బతిన్న పంట, మొత్తం పొలం స్పష్టమైన ఫోటోలు, ఈ రోజే తీసినవి (ఫోన్ లొకేషన్, తేదీ ఆన్ చేసి)",
                  "బీమా దరఖాస్తు రసీదు లేదా పాలసీ నంబర్ (PMFBY)", "ఆధార్, పాలసీకి ఇచ్చిన బ్యాంక్ పాస్‌బుక్",
                  "భూమి రికార్డులు (పట్టాదారు పాస్‌బుక్ / అడంగల్), సర్వే నంబర్", "పంట పేరు, విత్తిన తేదీ, ఎకరాల్లో విస్తీర్ణం"],
        "how": "పంట బీమా హెల్ప్‌లైన్ {pmfby} కు (లేదా మీ బీమా కంపెనీ, బ్యాంక్, వ్యవసాయ అధికారికి) కాల్ చేసి నష్టం తెలియజేయండి, లేదా Crop Insurance యాప్ వాడండి. వారు ఇచ్చే ఫిర్యాదు నంబర్ రాసుకోండి.",
        "msg": ("వీరికి: వ్యవసాయ అధికారి / పంట బీమా కంపెనీ\nవిషయం: PMFBY కింద పంట నష్టం సమాచారం\n\n"
                "నా పంటకు నష్టం జరిగింది. పంట: {crop}. ప్రభావిత విస్తీర్ణం: {acres} ఎకరాలు. కారణం: {cause}. నష్టం జరిగిన తేదీ, సమయం: {when}. "
                "గ్రామం / జిల్లా: {place}. పాలసీ / దరఖాస్తు నంబర్: [రాయండి]. ఫోటోలు జతచేశాను. "
                "దయచేసి ఈ సమాచారం నమోదు చేసి నష్టాన్ని అంచనా వేయండి.\n\nపేరు: [రాయండి]   మొబైల్: [రాయండి]"),
    },
    "hi": {
        "cause": {"hailstorm": "ओलावृष्टि", "flood_local": "स्थानीय बाढ़ / जलभराव", "landslide": "भूस्खलन",
                  "cloudburst": "बादल फटना", "fire": "आग", "post_harvest_rain": "कटाई के बाद खेत में सूखती फसल पर चक्रवात / बेमौसम बारिश",
                  "other": "सूखा, कीट, रोग या अन्य"},
        "timed": "72 घंटे के भीतर सूचना दें। अंतिम समय: {d}।",
        "post": " यह कटाई के बाद 14 दिन तक, खेत में सूखती फसल पर ही लागू है।",
        "area": "सूखा, व्यापक कीट या रोग जैसे नुकसान का आकलन सरकार पूरे क्षेत्र के लिए करती है (फसल कटाई प्रयोग), इसलिए 72 घंटे की व्यक्तिगत सूचना नहीं होती। कृषि अधिकारी से पूछें कि आपका क्षेत्र अधिसूचित है या नहीं, और फ़ोटो सँभालकर रखें।",
        "check": ["खराब फसल और पूरे खेत की साफ़ फ़ोटो, आज ही ली हुई (फ़ोन की लोकेशन और तारीख़ चालू रखकर)",
                  "बीमा आवेदन की रसीद या पॉलिसी नंबर (PMFBY)", "आधार और पॉलिसी में दिया बैंक पासबुक",
                  "ज़मीन के कागज़ और सर्वे नंबर", "फसल का नाम, बुवाई की तारीख़ और एकड़ में क्षेत्र"],
        "how": "फसल बीमा हेल्पलाइन {pmfby} पर (या अपनी बीमा कंपनी, बैंक, कृषि अधिकारी को) कॉल करके नुकसान की सूचना दें, या Crop Insurance ऐप इस्तेमाल करें। शिकायत नंबर लिख लें।",
        "msg": ("प्रति: कृषि अधिकारी / फसल बीमा कंपनी\nविषय: PMFBY के तहत फसल नुकसान की सूचना\n\n"
                "मेरी फसल को नुकसान हुआ है। फसल: {crop}। प्रभावित क्षेत्र: {acres} एकड़। कारण: {cause}। नुकसान की तारीख़ व समय: {when}। "
                "गाँव / ज़िला: {place}। पॉलिसी / आवेदन नंबर: [लिखें]। फ़ोटो संलग्न हैं। "
                "कृपया यह सूचना दर्ज करें और नुकसान का आकलन करें।\n\nनाम: [लिखें]   मोबाइल: [लिखें]"),
    },
}


def _parse(ts: str | None, now: datetime) -> datetime:
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return now


def build_claim(profile: dict | None, loss: dict | None, lang: str = "en", now: datetime | None = None) -> dict:
    code = lang if lang in T else "en"
    L = T[code]
    profile, loss = profile or {}, loss or {}
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    cause = loss.get("cause") if loss.get("cause") in CAUSES else "other"
    occurred = min(_parse(loss.get("occurred_at"), now), now)
    try:
        acres = float(loss.get("acres"))
        acres = acres if 0 < acres <= 1000 else None
    except (TypeError, ValueError):
        acres = None
    crop = str(loss.get("crop") or profile.get("main_crop") or "[crop]")[:30]
    place = ", ".join(x for x in (profile.get("district"), profile.get("state")) if x) or "[village / district]"
    timed = cause in LOCALIZED or cause in POST_HARVEST
    if not loc.is_india(profile):                      # PMFBY and its 72-hour rule are Indian: be generic abroad
        return _generic(profile, cause, crop, acres, place, occurred)
    out = {"cause": cause, "cause_label": L["cause"][cause], "individual_claim": timed, "helplines": HELPLINES,
           "occurred_at": occurred.isoformat(), "checklist": L["check"] if timed else L["check"][:1],
           "how": L["how"].format(pmfby=HELPLINES["pmfby"]),
           "message": L["msg"].format(crop=crop, acres=acres if acres is not None else "[acres]", cause=L["cause"][cause],
                                      when=occurred.astimezone(timezone(timedelta(hours=5, minutes=30))).strftime("%d %b %Y, %I:%M %p IST"),
                                      place=place)}
    if timed:
        deadline = occurred + timedelta(hours=WINDOW_H)
        left = (deadline - now).total_seconds() / 3600
        out.update({"deadline": deadline.isoformat(), "hours_left": round(max(left, 0), 1),
                    "status": "expired" if left <= 0 else "urgent" if left <= 24 else "open"})
        ist = deadline.astimezone(timezone(timedelta(hours=5, minutes=30))).strftime("%d %b %Y, %I:%M %p IST")
        out["guidance"] = L["timed"].format(d=ist) + (L["post"] if cause in POST_HARVEST else "")
    else:
        out.update({"status": "area_level", "guidance": L["area"]})
    return out


GENERIC = {
    "guidance": "Crop insurance rules differ by country and by policy, and many require you to report a loss within a few days. "
                "Do not wait: tell your insurer, cooperative or agricultural extension office as soon as it happens, and ask what the deadline is.",
    "how": "Call or visit your insurer, cooperative or local agricultural extension office today, report the loss and write down the reference number they give you.",
    "check": ["Clear photos of the damaged crop and the whole field, taken today (phone location and date switched on)",
              "Your insurance policy or membership number", "Proof of identity and of your land or lease",
              "Crop name, sowing date and area (acres or hectares)"],
    "msg": ("To: My crop insurer / agricultural extension office\nSubject: Notice of crop loss\n\n"
            "I am reporting a crop loss. Crop: {crop}. Area affected: {acres}. Cause: {cause}. Date and time of loss: {when}. "
            "Place: {place}. Policy number: [add]. Photos are attached. Please register this and tell me the next steps.\n\nName: [add]   Phone: [add]"),
}


def _generic(profile, cause, crop, acres, place, occurred) -> dict:
    cause_label = T["en"]["cause"][cause]
    return {"cause": cause, "cause_label": cause_label, "individual_claim": True, "status": "check_policy", "helplines": {},
            "occurred_at": occurred.isoformat(), "guidance": GENERIC["guidance"], "checklist": GENERIC["check"], "how": GENERIC["how"],
            "message": GENERIC["msg"].format(crop=crop, acres=acres if acres is not None else "[area]", cause=cause_label,
                                             when=occurred.strftime("%d %b %Y, %H:%M UTC"), place=place)}
