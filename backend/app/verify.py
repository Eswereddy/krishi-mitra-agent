"""Verification layer (idea from Meta's Agents 102 / legal-agent-workshop):
the agent's final answer is checked by plain code, outside the model's control.

Rule: every figure of 3+ digits in the answer (prices, rupee amounts) must appear in a
tool result. Otherwise the answer is sent back for a rewrite, and if it still fails
the farmer sees an explicit "not verified" warning instead of a confident wrong number.
"""
import json
import re

_TELUGU_DIGITS = str.maketrans("౦౧౨౩౪౫౬౭౮౯०१२३४५६७८९", "01234567890123456789")
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def numbers(text: str) -> set[str]:
    text = text.translate(_TELUGU_DIGITS)
    out = set()
    for m in _NUM.findall(text):
        n = m.replace(",", "").rstrip(".")
        if n:
            out.add(n.split(".")[0] if n.endswith(".0") else n)
    return out


def verify_answer(answer: str, steps: list[dict]) -> dict:
    """Return {"passed": bool, "unverified": [figures not found in any tool result]}."""
    allowed = numbers(json.dumps([s.get("result") for s in steps], ensure_ascii=False))
    claimed = {n for n in numbers(answer) if len(n.split(".")[0]) >= 3}
    unverified = sorted(claimed - allowed)
    return {"passed": not unverified, "unverified": unverified}


def warning(unverified: list[str], lang: str = "te") -> str:
    from .lang import WARNING
    return WARNING.get(lang, WARNING["en"]).format(n=", ".join(unverified))
