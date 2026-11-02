"""AI agricultural research assistant: answers ONLY from documents the farmer or advisor supplies (ICAR, state agriculture university or
KVK PDFs and text), with the passage and its source shown for every claim.

Flow: the document is uploaded once and split into passages on the server (stateless: nothing is stored), the PHONE keeps the passages,
and each question sends the passages back with the question. Retrieval is BM25 keyword search in plain code. If no passage supports the
question the assistant says so and does not call the model. When a model answers, it is told to use only the numbered passages; the
answer is then checked in code: every [n] citation must exist and every number must appear in the cited passages, otherwise the answer
is flagged as not grounded. The app ships with no documents; text must come from the user or from files added to data/research/.
"""
import io
import math
import re
from collections import Counter
from pathlib import Path

MAX_UPLOAD, MAX_PAGES, MAX_CHUNKS, CHUNK_CHARS, MAX_CHUNK_IN = 5_000_000, 150, 300, 900, 1200
TOP_K = 5
_STOP = set("the a an and or of to in on for with is are was were be by as at it this that from which can may will not no than into its their have has had do does".split())
_WORD = re.compile(r"[^\W_]+", re.UNICODE)
CORPUS_DIR = Path(__file__).parent / "data" / "research"
T = {
    "en": {"none": "I found nothing in your documents that answers this. I will not guess: add a document that covers it, or ask in different words.",
           "nodocs": "No documents are loaded yet. Upload an ICAR or agriculture university PDF or text file first.", "extract": "Closest passage from your documents (no model was used):",
           "ungrounded": "Warning: part of this answer could not be matched to the passages. Check the passages below before using it.", "lang": "English"},
    "te": {"none": "మీ పత్రాల్లో దీనికి జవాబు దొరకలేదు. నేను ఊహించను: ఈ విషయం ఉన్న పత్రం చేర్చండి, లేదా వేరే మాటల్లో అడగండి.",
           "nodocs": "ఇంకా పత్రాలు లేవు. ముందు ICAR లేదా వ్యవసాయ విశ్వవిద్యాలయ PDF లేదా టెక్స్ట్ ఫైల్ అప్‌లోడ్ చేయండి.", "extract": "మీ పత్రాల నుండి దగ్గరి భాగం (మోడల్ వాడలేదు):",
           "ungrounded": "హెచ్చరిక: ఈ జవాబులో కొంత భాగం పత్రం భాగాలతో సరిపోలలేదు. వాడే ముందు కింది భాగాలు చూడండి.", "lang": "Telugu"},
    "hi": {"none": "आपके दस्तावेज़ों में इसका जवाब नहीं मिला। मैं अंदाज़ा नहीं लगाऊँगा: इस विषय का दस्तावेज़ जोड़ें, या दूसरे शब्दों में पूछें।",
           "nodocs": "अभी कोई दस्तावेज़ नहीं है। पहले ICAR या कृषि विश्वविद्यालय का PDF या टेक्स्ट फ़ाइल अपलोड करें।", "extract": "आपके दस्तावेज़ों से सबसे करीबी अंश (मॉडल नहीं चला):",
           "ungrounded": "चेतावनी: इस जवाब का कुछ हिस्सा अंशों से मेल नहीं खाया। उपयोग से पहले नीचे के अंश देखें।", "lang": "Hindi"},
}


def _clean(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", t or "")).strip()


def chunk_text(text: str, title: str, page: int | None = None) -> list[dict]:
    """Split on sentence boundaries into ~CHUNK_CHARS passages."""
    sents = re.split(r"(?<=[.!?।])\s+", _clean(text))
    out, cur = [], ""
    for s in sents:
        if len(cur) + len(s) + 1 > CHUNK_CHARS and cur:
            out.append(cur)
            cur = ""
        cur = (cur + " " + s).strip()
        while len(cur) > CHUNK_CHARS * 1.5:                       # a very long unpunctuated run
            out.append(cur[:CHUNK_CHARS])
            cur = cur[CHUNK_CHARS:]
    if cur:
        out.append(cur)
    return [{"title": title[:120], "page": page, "text": c} for c in out if len(c) > 40]


def ingest(data: bytes, filename: str) -> dict:
    """Upload -> passages (not stored). Supports PDF, TXT, MD, HTML."""
    if len(data) > MAX_UPLOAD:
        return {"error": "File too large (max 5 MB)"}
    name = (filename or "document")[:120]
    chunks: list[dict] = []
    if data[:5] == b"%PDF-" or name.lower().endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            for i, page in enumerate(reader.pages[:MAX_PAGES], 1):
                chunks += chunk_text(page.extract_text() or "", name, i)
        except Exception as e:
            return {"error": f"Could not read this PDF ({type(e).__name__}). Scanned PDFs without text cannot be read."}
    else:
        text = data.decode("utf-8", errors="replace")
        if name.lower().endswith((".html", ".htm")) or text.lstrip().lower().startswith("<!doctype html") or "<html" in text[:500].lower():
            text = re.sub(r"(?is)<(script|style).*?</\1>", " ", text)
            text = re.sub(r"<[^>]+>", " ", text)
        chunks = chunk_text(text, name)
    if not chunks:
        return {"error": "No readable text found in this file."}
    return {"title": name, "chunks": chunks[:MAX_CHUNKS], "truncated": len(chunks) > MAX_CHUNKS, "count": min(len(chunks), MAX_CHUNKS)}


def builtin_chunks() -> list[dict]:
    out = []
    if CORPUS_DIR.is_dir():
        for f in sorted(CORPUS_DIR.glob("*.txt"))[:50]:
            raw = f.read_text(encoding="utf-8", errors="replace")
            title = re.search(r"^Title:\s*(.+)$", raw, re.M)
            src = re.search(r"^Source:\s*(.+)$", raw, re.M)
            body = re.sub(r"^(Title|Source):.*$", "", raw, flags=re.M)
            label = (title.group(1) if title else f.stem) + (f" ({src.group(1)})" if src else "")
            out += chunk_text(body, label)
    return out


def _tokens(text: str) -> list[str]:
    return [w for w in (x.lower() for x in _WORD.findall(text or "")) if w not in _STOP and len(w) > 1]


def search(query: str, chunks: list[dict], k: int = TOP_K) -> list[dict]:
    """BM25 over the supplied passages. Returns only passages with a positive score."""
    docs = [(_tokens(c["text"]), c) for c in chunks]
    q = set(_tokens(query))
    if not q or not docs:
        return []
    n = len(docs)
    avg = sum(len(d) for d, _ in docs) / n or 1
    df = Counter(t for d, _ in docs for t in set(d))
    scored = []
    for d, c in docs:
        tf = Counter(d)
        s = 0.0
        for t in q:
            if tf[t]:
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                s += idf * tf[t] * 2.5 / (tf[t] + 1.5 * (0.25 + 0.75 * len(d) / avg))
        if s > 0:
            scored.append((s, c))
    scored.sort(key=lambda x: -x[0])
    return [{"n": i + 1, "title": c["title"], "page": c.get("page"), "text": c["text"], "score": round(s, 2)} for i, (s, c) in enumerate(scored[:k])]


def check(answer: str, passages: list[dict]) -> dict:
    """Is the answer grounded? Every [n] must be a real passage; every number (2+ digits or decimal) must appear in a cited passage."""
    from . import verify
    cited = {int(x) for x in re.findall(r"\[(\d{1,2})\]", answer or "")}
    valid = {p["n"] for p in passages}
    bad_cites = sorted(cited - valid)
    cited_text = " ".join(p["text"] for p in passages if p["n"] in cited) or " ".join(p["text"] for p in passages)
    allowed = verify.numbers(cited_text)
    nums = {n for n in verify.numbers(re.sub(r"\[\d{1,2}\]", " ", answer or "")) if len(n) >= 2}
    missing = sorted(nums - allowed)
    return {"grounded": bool(cited) and not bad_cites and not missing, "cited": sorted(cited & valid), "bad_citations": bad_cites, "numbers_not_in_passages": missing}


def extract_answer(passages: list[dict], lang: str, query: str = "") -> str:
    """No-model answer: the two sentences of the best passage that share the most words with the question, quoted as they are."""
    L = T.get(lang, T["en"])
    sents = re.split(r"(?<=[.!?।])\s+", passages[0]["text"])
    q = set(_tokens(query))
    best = sorted(range(len(sents)), key=lambda i: (-len(q & set(_tokens(sents[i]))), i))[:2]
    return f'{L["extract"]} ' + " ".join(sents[i] for i in sorted(best)) + " [1]"


async def ask(question: str, chunks: list[dict], lang: str = "en", use_model: bool = True) -> dict:
    from . import config, meta_client
    lang = lang if lang in T else "en"
    L = T[lang]
    chunks = [{"title": str(c.get("title", ""))[:120], "page": c.get("page") if isinstance(c.get("page"), int) else None, "text": _clean(str(c.get("text", "")))[:MAX_CHUNK_IN]}
              for c in (chunks if isinstance(chunks, list) else [])[:MAX_CHUNKS] if isinstance(c, dict)]
    chunks += builtin_chunks()
    if not chunks:
        return {"answer": L["nodocs"], "passages": [], "grounded": False, "mode": "no-documents"}
    query = question
    if lang != "en" and use_model and not config.MOCK_MODE and sum(ord(ch) > 127 for ch in question) > len(question) / 3:
        try:                                                  # documents are mostly English: search with an English rewrite of the question
            query = (await meta_client.chat([{"role": "system", "content": "Rewrite the farmer's question as a short English keyword search query. Output only the query."},
                                              {"role": "user", "content": question[:300]}]))[:200] or question
        except Exception:
            query = question
    passages = search(query, chunks)
    if not passages:
        return {"answer": L["none"], "passages": [], "grounded": False, "mode": "no-match", "query_used": query}
    if config.MOCK_MODE or not use_model:
        return {"answer": extract_answer(passages, lang, query), "passages": passages, "grounded": True, "mode": "extract", "query_used": query,
                "checks": check(extract_answer(passages, lang, query), passages)}
    ctx = "\n".join(f'[{p["n"]}] ({p["title"]}{", p." + str(p["page"]) if p["page"] else ""}) {p["text"]}' for p in passages)
    msgs = [{"role": "system", "content": f"You answer a farmer's question ONLY from the numbered passages. Cite the passage number like [1] after every claim. Do not use any other knowledge. "
                                           f"If the passages do not answer the question, say so. Never name pesticides or doses unless a passage does, and then quote it exactly. Answer in {L['lang']}, in 4 short sentences or fewer."},
            {"role": "user", "content": f"Passages:\n{ctx}\n\nQuestion: {question[:400]}"}]
    ans = (await meta_client.chat(msgs)).strip()
    chk = check(ans, passages)
    if not chk["grounded"]:
        ans += "\n\n" + L["ungrounded"]
    return {"answer": ans, "passages": passages, "grounded": chk["grounded"], "mode": "model", "query_used": query, "checks": chk}
