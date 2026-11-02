"""AI farmer learning coach: short interactive lessons with a quiz, matched to what the farmer asked about and to how much they already know.

Content is NOT written by the model: lessons and quiz questions are assembled in code from the knowledge graph (kg.py), so every
statement traces to data/problems.json or data/rotation.json, and every quiz answer is correct according to those tables (distractors are
drawn only from items that are NOT linked to the topic in them). Level (beginner / intermediate / advanced) comes from the farmer's own
quiz history, which stays on their phone and is sent with the request. Lesson text from the problem table is in English; question
wording, headings, conditions, soils and crop names are in Telugu / Hindi / English.
"""
import hashlib
import random

from . import kg, rotation

LEVELS = ("beginner", "intermediate", "advanced")
N_QUESTIONS = {"beginner": 2, "intermediate": 3, "advanced": 4}
T = {
    "en": {"see": "What you see", "favour": "What helps it spread", "do": "Safe steps you can take", "expert": "When to ask an expert", "link": "Why rotation matters here",
           "nitro": "Nitrogen and rotation", "soil": "Soil fit", "problems": "Problems that affect this crop", "share": "Crops sharing a problem",
           "q_cond": "In our table, which of these helps {p} to spread?", "q_step": "Which of these is listed as a safe step for {p}?", "q_crop": "Which other crop can {p} also affect?",
           "q_legume": "Which crop can add nitrogen to the soil before {c}?", "q_soil": "Which soil generally suits {c}?", "q_caution": "On which soil does {c} need extra care?",
           "right": "Correct.", "wrong": "Not quite. The answer is: {a}", "basis": "Built in code from the project's problem and rotation tables (not reviewed by an agronomist). General education, not advice for a particular field.",
           "no_topic": "Tell me a crop or a problem you see and I will make a lesson.", "level_why": "Level {l}: {n} quizzes taken, average {a}%."},
    "te": {"see": "మీరు ఏమి చూస్తారు", "favour": "ఇది వ్యాపించడానికి ఏది సహాయపడుతుంది", "do": "మీరు తీసుకోగల సురక్షిత చర్యలు", "expert": "నిపుణులను ఎప్పుడు అడగాలి", "link": "ఇక్కడ పంట మార్పిడి ఎందుకు ముఖ్యం",
           "nitro": "నత్రజని, పంట మార్పిడి", "soil": "నేల అనుకూలత", "problems": "ఈ పంటను ఆశించే సమస్యలు", "share": "ఇదే సమస్య ఉన్న పంటలు",
           "q_cond": "మా పట్టిక ప్రకారం {p} వ్యాపించడానికి వీటిలో ఏది సహాయపడుతుంది?", "q_step": "{p} కి వీటిలో ఏది సురక్షిత చర్యగా జాబితాలో ఉంది?", "q_crop": "{p} మరో ఏ పంటను కూడా ఆశించవచ్చు?",
           "q_legume": "{c} కి ముందు నేలకు నత్రజని చేర్చగల పంట ఏది?", "q_soil": "{c} కి సాధారణంగా ఏ నేల సరిపోతుంది?", "q_caution": "{c} కి ఏ నేలలో అదనపు జాగ్రత్త కావాలి?",
           "right": "సరైనది.", "wrong": "కాదు. సరైన జవాబు: {a}", "basis": "ప్రాజెక్ట్ సమస్యల, పంట మార్పిడి పట్టికల నుండి కోడ్ ద్వారా తయారైంది (వ్యవసాయ నిపుణుడు సమీక్షించలేదు). సాధారణ విద్య మాత్రమే, మీ పొలానికి ప్రత్యేక సలహా కాదు.",
           "no_topic": "ఒక పంట లేదా మీరు చూసే సమస్య చెప్పండి, పాఠం తయారుచేస్తాను.", "level_why": "స్థాయి {l}: {n} క్విజ్‌లు, సగటు {a}%."},
    "hi": {"see": "आप क्या देखते हैं", "favour": "इसे फैलने में क्या मदद करता है", "do": "आप कौन से सुरक्षित कदम ले सकते हैं", "expert": "विशेषज्ञ से कब पूछें", "link": "यहाँ फसल चक्र क्यों मायने रखता है",
           "nitro": "नाइट्रोजन और फसल चक्र", "soil": "मिट्टी की अनुकूलता", "problems": "इस फसल को प्रभावित करने वाली समस्याएँ", "share": "यही समस्या वाली फसलें",
           "q_cond": "हमारी तालिका के अनुसार इनमें से कौन {p} को फैलने में मदद करता है?", "q_step": "{p} के लिए इनमें से कौन सा सुरक्षित कदम सूची में है?", "q_crop": "{p} और किस फसल को प्रभावित कर सकता है?",
           "q_legume": "{c} से पहले कौन सी फसल मिट्टी में नाइट्रोजन जोड़ सकती है?", "q_soil": "{c} के लिए आम तौर पर कौन सी मिट्टी ठीक है?", "q_caution": "{c} को किस मिट्टी में अतिरिक्त सावधानी चाहिए?",
           "right": "सही।", "wrong": "ठीक नहीं। सही जवाब: {a}", "basis": "प्रोजेक्ट की समस्या और फसल चक्र तालिकाओं से कोड द्वारा बना (कृषि विशेषज्ञ ने समीक्षा नहीं की)। सामान्य शिक्षा, किसी खास खेत की सलाह नहीं।",
           "no_topic": "कोई फसल या दिखने वाली समस्या बताइए, मैं पाठ बनाऊँगा।", "level_why": "स्तर {l}: {n} क्विज़, औसत {a}%."},
}


def level_from(history) -> tuple[str, int, int | None]:
    """(level, quizzes_counted, average_percent) from the last 5 quiz results {score, total}."""
    rows = []
    for h in (history if isinstance(history, list) else [])[-5:]:
        try:
            s, t = float(h["score"]), float(h["total"])
        except (KeyError, TypeError, ValueError):
            continue
        if t > 0 and 0 <= s <= t:
            rows.append(s / t)
    if len(rows) < 2:
        return "beginner", len(rows), round(100 * sum(rows) / len(rows)) if rows else None
    avg = sum(rows) / len(rows)
    lvl = "advanced" if avg >= 0.9 and len(rows) >= 4 else "intermediate" if avg >= 0.7 else "beginner"
    return lvl, len(rows), round(100 * avg)


def _disp(nid: str, lang: str) -> str:
    n = kg.NODES[nid]
    return (n.get("te") if lang == "te" else n.get("hi") if lang == "hi" else None) or n["label"]


def _pick(rng, pool: list, n: int) -> list:
    pool = sorted(set(pool))
    rng.shuffle(pool)
    return pool[:n]


def _q(rng, qid: str, text: str, right: str, wrong_pool: list, explain: str) -> dict | None:
    wrong = _pick(rng, [w for w in wrong_pool if w != right], 3)
    if len(wrong) < 2:
        return None
    opts = wrong + [right]
    rng.shuffle(opts)
    return {"id": qid, "q": text, "options": opts, "answer_index": opts.index(right), "explain": explain}


def _topic(payload: dict, nth: int) -> str | None:
    q = str(payload.get("question") or "")[:200]
    nid = kg.find(q) if q.strip() else None
    if not nid:
        crop = str((payload.get("profile") or {}).get("main_crop") or "")
        nid = kg.find(crop) if crop else None
    if nid and nid.startswith("crop:"):                      # a crop: teach one of its problems, rotating with each lesson taken
        probs = sorted(e["dst"] for e in kg.EDGES if e["src"] == nid and e["rel"] == "affected_by")
        probs = [p for p in probs if not p.endswith("deficiency")] or probs
        return probs[nth % len(probs)] if probs and nth % (len(probs) + 1) != len(probs) else nid
    return nid


def build(payload: dict, lang: str = "en") -> dict:
    lang = lang if lang in T else "en"
    L = T[lang]
    hist = payload.get("history") if isinstance(payload.get("history"), list) else []
    level, n_q, avg = level_from(hist)
    nth = len(hist)
    nid = _topic(payload, nth)
    if not nid or nid not in kg.NODES:
        return {"error": L["no_topic"], "level": level}
    node = kg.NODES[nid]
    rng = random.Random(int(hashlib.sha1(f"{nid}|{nth}".encode()).hexdigest()[:8], 16))
    rel = [e for e in kg.EDGES if e["src"] == nid or e["dst"] == nid]
    sections, quiz = [], []
    if node["kind"] == "problem":
        conds = [e for e in rel if e["rel"] == "favoured_by"]
        practices = [e["dst"] for e in rel if e["rel"] == "managed_by"]
        crops = [e["src"] for e in rel if e["rel"] == "affected_by"]
        sections.append({"title": L["see"], "items": [node["looks_like"]]})
        cn = [_disp(e["dst"], lang) for e in conds]
        sections.append({"title": L["favour"], "items": cn[: 2 if level == "beginner" else 6]})
        sections.append({"title": L["do"], "items": [kg.NODES[p]["label"] for p in practices][: 2 if level == "beginner" else 6]})
        sections.append({"title": L["expert"], "items": [node["expert_note"]]})
        if level != "beginner" and len(crops) > 1:
            sections.append({"title": L["link"], "items": [", ".join(_disp(c, lang) for c in crops)]})
        pname = node["label"]
        all_c = [n["id"] for n in kg.NODES.values() if n["kind"] == "condition"]
        cand = []
        if conds:
            r = rng.choice(conds)["dst"]
            cand.append(_q(rng, "cond", L["q_cond"].format(p=pname), _disp(r, lang), [_disp(c, lang) for c in all_c if c not in {e["dst"] for e in conds}], ""))
        if practices:
            r = rng.choice(practices)
            other = [n["label"] for n in kg.NODES.values() if n["kind"] == "practice" and n["id"] not in practices]
            cand.append(_q(rng, "step", L["q_step"].format(p=pname), kg.NODES[r]["label"], other, ""))
        if len(crops) > 1:
            first = crops[0]
            others = [c for c in crops if c != first]
            cand.append(_q(rng, "crop", L["q_crop"].format(p=_disp(first, lang) + " / " + pname), _disp(rng.choice(others), lang),
                           [_disp(c, lang) for c in rotation_ids() if c not in crops], ""))
        quiz = [c for c in cand if c]
    else:
        cid = nid.split(":", 1)[1] if node["kind"] == "crop" else None
        if cid:
            fit = rotation._RULES["soil_fit"].get(cid, {})
            info = rotation.CROPS[cid]
            sections.append({"title": L["nitro"], "items": [f'{_disp(nid, lang)}: ' + info["n_role"]]})
            sections.append({"title": L["soil"], "items": [_disp("soil:" + s, lang) for s in fit.get("suits", [])]})
            probs = [_disp(e["dst"], lang) for e in rel if e["rel"] == "affected_by"]
            sections.append({"title": L["problems"], "items": probs[:6]})
            legumes = [k for k, v in rotation.CROPS.items() if v["n_role"] == "fixes"]
            heavy = [k for k, v in rotation.CROPS.items() if v["n_role"] == "heavy"]
            cand = [_q(rng, "legume", L["q_legume"].format(c=_disp(nid, lang)), _disp("crop:" + rng.choice(legumes), lang), [_disp("crop:" + h, lang) for h in heavy if h != cid], ""),
                    _q(rng, "soil", L["q_soil"].format(c=_disp(nid, lang)), _disp("soil:" + rng.choice(fit["suits"]), lang),
                       [_disp("soil:" + s, lang) for s in rotation._RULES["soils"] if s != "other" and s not in fit["suits"]], "") if fit.get("suits") else None,
                    _q(rng, "caution", L["q_caution"].format(c=_disp(nid, lang)), _disp("soil:" + rng.choice(fit["caution"]), lang),
                       [_disp("soil:" + s, lang) for s in rotation._RULES["soils"] if s != "other" and s not in fit["caution"]], "") if fit.get("caution") else None]
            quiz = [c for c in cand if c]
        else:
            sections.append({"title": node["kind_label"] if "kind_label" in node else node["kind"], "items": [_disp(nid, lang)]})
    quiz = quiz[: N_QUESTIONS[level]]
    for i, q in enumerate(quiz):
        q["id"] = f"{q['id']}-{i}"
        q["explain"] = L["wrong"].format(a=q["options"][q["answer_index"]])
    return {"topic": {"id": nid, "kind": node["kind"], "name": _disp(nid, lang)}, "level": level, "level_why": L["level_why"].format(l=level, n=n_q, a=avg if avg is not None else "-"),
            "sections": [s for s in sections if s["items"]], "quiz": quiz, "right": L["right"], "basis": L["basis"], "reviewed_by_agronomist": False}


def rotation_ids() -> list[str]:
    return ["crop:" + c for c in rotation.CROPS]
