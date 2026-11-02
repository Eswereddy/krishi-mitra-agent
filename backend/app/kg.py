"""Agricultural knowledge graph: crops, pests and diseases, the conditions that favour them, safe practices and soils, linked.

Built at start-up from two repository data files, so nothing here is a separate, hand-typed copy:
  * data/problems.json   (crop <-> problem, problem <-> favouring condition, problem <-> non-chemical practice)
  * data/rotation.json   (crop <-> soil fit, legume <-> heavy-feeder rotation links)
Every edge carries its `source` file, the original `evidence` text, and `reviewed: false` (no agronomist has reviewed these tables).
Condition nodes are derived from the favoured-by sentence with fixed keyword rules; the original sentence stays on the edge.
No pesticide names or doses exist in the graph.
"""
import json
import re
from pathlib import Path

from . import rotation

DATA = Path(__file__).parent / "data"
SOURCE_P, SOURCE_R = "problems.json", "rotation.json"
CONDITIONS = [  # (id, label, regex over the favoured-by text)
    ("humid", "High humidity or wet weather", r"humid|wet|rain|cloudy|dew"),
    ("dry", "Dry weather", r"\bdry\b|drought"),
    ("warm", "Warm weather", r"warm|hot"),
    ("cool", "Cool weather", r"cool|cold"),
    ("nitrogen", "Too much nitrogen", r"nitrogen"),
    ("waterlog", "Waterlogged or poorly drained soil", r"waterlog|standing water|poorly drained|drain"),
    ("residue", "Crop leftovers or the same crop again and again", r"residue|leftover|stalks|continuous|repeated|same crop"),
    ("dense", "Dense planting or over-spraying", r"dense|over-spray"),
    ("alkaline", "Alkaline or chalky soil", r"alkaline|chalky"),
    ("light", "Light soil or low organic matter", r"light soils|organic matter|nutrients"),
    ("pestbuild", "Insect build-up (thrips, whitefly)", r"thrips|whitefly|build-up"),
]
CONDITION_T = {
    "humid": ("అధిక తేమ లేదా తడి వాతావరణం", "अधिक नमी या गीला मौसम"), "dry": ("పొడి వాతావరణం", "सूखा मौसम"), "warm": ("వేడి వాతావరణం", "गर्म मौसम"),
    "cool": ("చల్లని వాతావరణం", "ठंडा मौसम"), "nitrogen": ("ఎక్కువ నత్రజని", "ज़्यादा नाइट्रोजन"),
    "waterlog": ("నీరు నిలిచే లేదా నీరు ఇంకని నేల", "जलभराव या खराब जल निकासी वाली मिट्टी"), "residue": ("పంట అవశేషాలు లేదా అదే పంట మళ్ళీ మళ్ళీ", "फसल अवशेष या बार-बार वही फसल"),
    "dense": ("దట్టంగా విత్తడం లేదా అతిగా పిచికారీ", "घनी बुवाई या ज़्यादा छिड़काव"), "alkaline": ("క్షార లేదా సున్నపు నేల", "क्षारीय या चूने वाली मिट्टी"),
    "light": ("తేలికపాటి నేల లేదా తక్కువ సేంద్రియ పదార్థం", "हल्की मिट्टी या कम जैविक पदार्थ"), "pestbuild": ("పురుగుల పెరుగుదల (తామర పురుగులు, తెల్ల దోమ)", "कीटों की बढ़त (थ्रिप्स, सफेद मक्खी)"),
}
SOIL_T = {"sandy": ("ఇసుక నేల", "रेतीली मिट्टी"), "loam": ("లోమ్ నేల", "दोमट मिट्टी"), "clay": ("బంకమట్టి", "चिकनी मिट्टी"), "black": ("నల్ల రేగడి నేల", "काली मिट्टी"),
          "red": ("ఎర్ర నేల", "लाल मिट्टी"), "alluvial": ("ఒండ్రు నేల", "जलोढ़ मिट्टी")}
KIND_LABEL = {
    "en": {"crop": "Crop", "problem": "Problem", "condition": "Favoured by", "practice": "Safe step", "soil": "Soil"},
    "te": {"crop": "పంట", "problem": "సమస్య", "condition": "అనుకూల పరిస్థితి", "practice": "సురక్షిత చర్య", "soil": "నేల"},
    "hi": {"crop": "फसल", "problem": "समस्या", "condition": "अनुकूल स्थिति", "practice": "सुरक्षित कदम", "soil": "मिट्टी"},
}
REL_LABEL = {
    "en": {"affected_by": "can be affected by", "favoured_by": "is favoured by", "managed_by": "is managed with", "suits": "generally suits", "caution": "needs care on",
           "can_follow": "can follow"},
    "te": {"affected_by": "కి వచ్చే సమస్య", "favoured_by": "కి అనుకూలం", "managed_by": "నియంత్రణ చర్య", "suits": "సాధారణంగా సరిపోతుంది", "caution": "జాగ్రత్త కావాలి", "can_follow": "తర్వాత వేయవచ్చు"},
    "hi": {"affected_by": "पर असर करने वाली", "favoured_by": "के लिए अनुकूल", "managed_by": "का नियंत्रण", "suits": "आम तौर पर ठीक", "caution": "में सावधानी", "can_follow": "के बाद उगा सकते हैं"},
}
NODES: dict[str, dict] = {}
EDGES: list[dict] = []


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60]


def _node(nid: str, kind: str, label: str, **extra) -> str:
    NODES.setdefault(nid, {"id": nid, "kind": kind, "label": label, **extra})
    return nid


def _edge(a: str, rel: str, b: str, source: str, evidence: str = "") -> None:
    EDGES.append({"src": a, "rel": rel, "dst": b, "source": source, "evidence": evidence, "reviewed": False})


def build() -> None:
    NODES.clear()
    EDGES.clear()
    for cid, c in rotation.CROPS.items():
        _node("crop:" + cid, "crop", c["name"], te=c.get("te"), hi=c.get("hi"), family=c["family"], nitrogen_role=c["n_role"])
    for soil in rotation._RULES["soils"]:
        if soil != "other":
            _node("soil:" + soil, "soil", soil.capitalize(), te=SOIL_T[soil][0], hi=SOIL_T[soil][1])
    for cid, f in rotation._RULES["soil_fit"].items():
        for s in f["suits"]:
            _edge("crop:" + cid, "suits", "soil:" + s, SOURCE_R, rotation._RULES["soil_note"])
        for s in f["caution"]:
            _edge("crop:" + cid, "caution", "soil:" + s, SOURCE_R, rotation._RULES["soil_note"])
    legumes = [c for c, v in rotation.CROPS.items() if v["n_role"] == "fixes"]
    heavy = [c for c, v in rotation.CROPS.items() if v["n_role"] == "heavy"]
    for h in heavy:
        for lg in legumes:
            _edge("crop:" + h, "can_follow", "crop:" + lg, SOURCE_R, "A heavy nitrogen feeder can use nitrogen left by a legume.")
    for p in json.loads((DATA / "problems.json").read_text()):
        pid = _node("problem:" + p["id"], "problem", p["name"], urgency=p["urgency"], looks_like=p["looks_like"], expert_note=p["expert_note"])
        for c in p["crops"]:
            cid = rotation.norm(c)
            if cid:
                _edge("crop:" + cid, "affected_by", pid, SOURCE_P, p["looks_like"])
        for cond_id, label, rx in CONDITIONS:
            if re.search(rx, p["favoured_by"], re.I):
                _node("condition:" + cond_id, "condition", label, te=CONDITION_T[cond_id][0], hi=CONDITION_T[cond_id][1])
                _edge(pid, "favoured_by", "condition:" + cond_id, SOURCE_P, p["favoured_by"])
        for step in p["what_to_do"]:
            sid = _node("practice:" + _slug(step), "practice", step)
            _edge(pid, "managed_by", sid, SOURCE_P, step)


def find(query: str) -> str | None:
    """Best node for a free-text query: exact label/alias, then a crop named inside the text (its problems are matched by keyword),
    then keyword hits on any problem."""
    q = str(query or "").strip().lower()
    if not q:
        return None
    cid = rotation.norm(q)
    if cid:
        return "crop:" + cid
    for n in NODES.values():
        if q in (n["label"].lower(), n["id"].split(":", 1)[1]) or (n.get("te") and q == n["te"]) or (n.get("hi") and q == n["hi"]):
            return n["id"]
    toks = set(re.findall(r"[a-z]{3,}", q)) | set(re.findall(r"[^\W\d_]+", q))
    mentioned = next((c for a, c in rotation._ALIAS.items() if a in toks), None)
    pool = json.loads((DATA / "problems.json").read_text())
    if mentioned:
        pool = [p for p in pool if mentioned in p["crops"]]
    best, score = None, 0
    for p in pool:
        s = sum(1 for k in p["keywords"] if k.lower() in q) * 2 + len(toks & set(re.findall(r"[a-z]{3,}", p["name"].lower())))
        if s > score:
            best, score = "problem:" + p["id"], s
    return best or ("crop:" + mentioned if mentioned else None)


def neighbors(nid: str, lang: str = "en") -> dict:
    lang = lang if lang in KIND_LABEL else "en"
    if nid not in NODES:
        return {"error": "unknown node"}
    edges = [e for e in EDGES if e["src"] == nid or e["dst"] == nid]
    ids = {nid} | {e["src"] for e in edges} | {e["dst"] for e in edges}
    nodes = []
    for i in sorted(ids):
        n = dict(NODES[i])
        n["display"] = (n.get("te") if lang == "te" else n.get("hi") if lang == "hi" else None) or n["label"]
        n["kind_label"] = KIND_LABEL[lang][n["kind"]]
        nodes.append(n)
    out_edges = [{**e, "text": f'{NODES[e["src"]]["label"]} {REL_LABEL["en"][e["rel"]]} {NODES[e["dst"]]["label"]}'} for e in edges]
    return {"center": nid, "nodes": nodes, "edges": out_edges, "reviewed_by_agronomist": False,
            "note": "Built from the repository's own problem and rotation tables (not reviewed by an agronomist). Not a diagnosis."}


def tool_crop_knowledge(query: str) -> dict:
    """Agent tool: what the knowledge graph says about a crop, a problem or a soil, with where each link comes from."""
    nid = find(query)
    if not nid:
        return {"error": "nothing found for that query", "try": [n["label"] for n in NODES.values() if n["kind"] == "crop"]}
    g = neighbors(nid)
    return {"about": NODES[nid]["label"], "kind": NODES[nid]["kind"], "links": [{"link": e["text"], "source_file": e["source"], "evidence": e["evidence"][:160]} for e in g["edges"][:30]],
            "note": g["note"]}


SPECS = [{"type": "function", "function": {
    "name": "crop_knowledge",
    "description": "Look up how a crop, a pest or disease, a favouring condition or a soil is linked to the others in the knowledge graph (problems of a crop, what favours a problem, "
                   "safe non-chemical steps, soil fit, rotation links). Cite that it comes from the project's own tables, not reviewed by an agronomist.",
    "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "crop, disease or soil name or what the farmer sees"}}, "required": ["query"]}}}]
FUNCS = {"crop_knowledge": tool_crop_knowledge}
build()
