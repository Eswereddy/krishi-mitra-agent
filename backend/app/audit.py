"""Second opinion: a different Meta model (Muse Wonder, a reasoning model) audits an answer given by the agent
(Muse Spark Open). Two models from two families of the stack must agree before the farmer is told "checked".

What each part does:
  * numbers: checked in code (verify.py) against the tool results. This is the hard check and always runs.
  * logic and caveats: Muse Wonder reads ONLY the tool results and the answer and says whether the advice follows
    from the data, and what caveat is missing. Its notes are advice for the farmer, never new figures.
Without MODEL_API_KEY only the code check runs, and the result says so.
"""
import json
import re

from . import lang as langmod, meta_models as mm, verify

MAX_FACT_CHARS = 7000
MAX_ITEMS = 3
MAX_LEN = 220

INSTRUCTIONS = """You are an independent auditor for a farm-advice assistant. You receive TOOL RESULTS (the only trusted facts)
and the ANSWER the assistant gave a farmer. Judge the answer using only the tool results.
Check: (1) does every claim follow from the tool results, (2) is any figure, date or place missing from them,
(3) is a caveat missing (prices change daily, assumptions, ask an officer) or is the advice riskier than the data supports.
Rules: never add new numbers, never name pesticides or doses, never give medical advice. Be brief and plain.
Reply with JSON only, no markdown fences:
{"verdict":"consistent" or "issues","issues":[{"claim":"<short quote>","problem":"<why it is not supported>"}],"missing_caveats":["<short>"]}
At most 3 issues and 3 caveats. Write the text values in LANGUAGE."""


def facts(steps) -> str:
    """Compact, size-capped view of the tool results (what the agent actually saw)."""
    out = []
    for s in steps if isinstance(steps, list) else []:
        if isinstance(s, dict) and isinstance(s.get("result"), dict) and not s["result"].get("error"):
            out.append({"tool": str(s.get("tool", ""))[:40], "result": s["result"]})
    txt = json.dumps(out, ensure_ascii=False, default=str, separators=(",", ":"))
    return txt[:MAX_FACT_CHARS]


def _short(v) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip()[:MAX_LEN]


def parse(raw: str) -> dict | None:
    """Lenient JSON parse of the auditor's reply (it may wrap the JSON in text or fences). None if unusable."""
    m = re.search(r"\{.*\}", raw or "", re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except ValueError:
        return None
    if not isinstance(d, dict):
        return None
    issues = []
    for i in (d.get("issues") or [])[:MAX_ITEMS]:
        if isinstance(i, dict) and (i.get("claim") or i.get("problem")):
            issues.append({"claim": _short(i.get("claim")), "problem": _short(i.get("problem"))})
    caveats = [_short(c) for c in (d.get("missing_caveats") or [])[:MAX_ITEMS] if _short(c)]
    return {"verdict": "issues" if issues or d.get("verdict") == "issues" else "consistent",
            "issues": issues, "missing_caveats": caveats}


async def second_opinion(answer: str, steps, lang: str = "en") -> dict:
    answer = str(answer or "")[:4000]
    steps = [s for s in (steps if isinstance(steps, list) else [])[:12] if isinstance(s, dict)]
    code = verify.verify_answer(answer, steps)
    out = {"numbers_checked_in_code": {"passed": bool(code["passed"]), "unverified": code.get("unverified", [])},
           "auditor": mm.WONDER_MODEL, "available": mm.available(), "verdict": "issues" if not code["passed"] else "unknown",
           "issues": [], "missing_caveats": []}
    fx = facts(steps)
    if not mm.available() or fx in ("", "[]"):
        out["reason"] = "no_key" if not mm.available() else "no_tool_results"
        if code["passed"] and fx not in ("", "[]"):
            out["verdict"] = "consistent"      # code check only
        return out
    prompt = f"LANGUAGE: {langmod.NAMES.get(lang, 'English')}\n\nTOOL RESULTS:\n{fx}\n\nANSWER:\n{answer}"
    try:
        raw = await mm.wonder(INSTRUCTIONS, prompt, effort="medium")
    except Exception:                                   # the audit is optional: never break the answer
        out["reason"] = "auditor_unavailable"
        return out
    d = parse(raw)
    if not d:
        out["reason"] = "auditor_unclear"
        return out
    out.update(issues=d["issues"], missing_caveats=d["missing_caveats"])
    out["verdict"] = "issues" if (d["verdict"] == "issues" or not code["passed"]) else "consistent"
    return out
