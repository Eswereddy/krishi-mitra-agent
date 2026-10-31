"""Agent evaluation you can run yourself and quote in the submission.

    cd backend && python eval/run_eval.py            # live model (needs BASETEN_API_KEY or the provider key in .env)
    python eval/run_eval.py --out ../EVAL.md         # also write the report

For each question it records: did the agent call the expected tool(s), did every figure in the answer pass the
verification layer, how many rewrites were needed, and how long it took. Nothing is hand-graded: the two numbers
that matter for trust are "right tool" and "figures verified". Cases cover India and other countries.
"""
import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import agent  # noqa: E402

IN = {"country": "IN", "state": "Andhra Pradesh", "district": "Kurnool", "main_crop": "Groundnut", "owns_land": True}
KE = {"country": "KE", "state": "", "district": "Nakuru", "main_crop": "Maize", "owns_land": True}
BR = {"country": "BR", "state": "", "district": "Londrina", "main_crop": "Soybean", "owns_land": True}

CASES = [
    # (question, profile, lang, any-of expected tools)
    ("What is the paddy price in Kurnool today?", IN, "en", {"get_mandi_price"}),
    ("Where can I sell groundnut for the highest price?", IN, "en", {"best_markets", "sell_plan"}),
    ("Should I sell groundnut now or wait?", IN, "en", {"hold_or_sell"}),
    ("Will it rain this week in Kurnool?", IN, "en", {"get_weather"}),
    ("Which government schemes can I get?", IN, "en", {"check_schemes"}),
    ("I have 10 quintals groundnut at Rs 6000, what is my income?", IN, "en", {"calculate_revenue", "net_market_value"}),
    ("What is the MSP of paddy?", IN, "en", {"get_msp"}),
    ("Interest on a Rs 1 lakh KCC loan for 6 months?", IN, "en", {"kcc_interest"}),
    ("Is today a good day to spray?", IN, "en", {"spray_window"}),
    ("Do I need to water my crop today?", IN, "en", {"irrigation_advice"}),
    ("Which crop gives more profit this rabi on 2 acres?", IN, "en", {"compare_crops"}),
    ("నా జిల్లాలో వరి ధర ఎంత?", IN, "te", {"get_mandi_price"}),
    ("मेरे ज़िले में मूँगफली का भाव क्या है?", IN, "hi", {"get_mandi_price", "best_markets"}),
    ("What is the maize price in Nakuru?", KE, "en", {"get_market_price"}),
    ("Bei ya mahindi Nakuru ni ngapi?", KE, "sw", {"get_market_price"}),
    ("Can I plant maize this week?", KE, "en", {"planting_window"}),
    ("Will it rain in Nakuru this week?", KE, "en", {"get_weather"}),
    ("¿Cuál es el precio de la soja?", BR, "es", {"get_market_price"}),
    ("Quando devo plantar soja?", BR, "pt", {"planting_window"}),
    ("Who can I call about a crop disease?", KE, "en", {"get_expert_help", "lookup_problem"}),
    ("My maize grain is at 16% moisture, can I store it?", KE, "en", {"storage_check"}),
    ("Will the heat be too much for my cows this week?", KE, "en", {"livestock_heat"}),
    ("A trader offers 1000 for 12 months at 3% a month flat. Is that a fair loan?", KE, "en", {"loan_compare"}),
    ("I spent 54000 and expect 1800 kg of maize. At what price do I break even?", KE, "en", {"breakeven_price"}),
    ("How much water does my maize need this week?", KE, "en", {"water_plan"}),
    ("Is this season drier than normal in Nakuru?", KE, "en", {"season_check"}),
    ("It has been very humid. Will disease come to my tomatoes?", KE, "en", {"disease_risk"}),
    ("Should I store my maize and sell later? Which month is usually best?", KE, "en", {"price_seasonality"}),
]
FORBIDDEN_ABROAD = ("₹", "MSP", "PMFBY", "Kisan Call", "1800-180")      # must never appear for a farmer outside India


async def run_case(q, profile, lang, expected):
    t0 = time.time()
    try:
        out = await agent.run_agent(q, lang=lang, profile=profile)
    except Exception as e:                       # a failed call counts as a failed case, not a crash
        return {"q": q, "ok_tool": False, "verified": False, "rewrites": 0, "secs": time.time() - t0, "tools": [], "error": str(e)[:120]}
    tools = [s["tool"] for s in out.get("steps", [])]
    v = out.get("verification") or {}
    leak = profile["country"] != "IN" and any(w in out.get("answer", "") for w in FORBIDDEN_ABROAD)
    return {"q": q, "tools": tools, "ok_tool": bool(expected & set(tools)), "verified": bool(v.get("passed")) and not leak,
            "rewrites": v.get("rewrites", 0), "secs": time.time() - t0, "leak": leak}


async def main(out_path: str | None):
    rows = [await run_case(*c) for c in CASES]
    n = len(rows)
    tool_ok = sum(r["ok_tool"] for r in rows)
    ver_ok = sum(r["verified"] for r in rows)
    first_try = sum(r["verified"] and r["rewrites"] == 0 for r in rows)
    secs = [r["secs"] for r in rows]
    lines = [f"# Agent evaluation ({n} questions, India + other countries)", "",
             f"- Right tool called: **{tool_ok}/{n}** ({tool_ok * 100 // n}%)",
             f"- Every figure verified (and no India-only terms abroad): **{ver_ok}/{n}** ({ver_ok * 100 // n}%)",
             f"- Verified on the first try, no rewrite: **{first_try}/{n}**",
             f"- Median time: **{statistics.median(secs):.1f}s**, slowest {max(secs):.1f}s", "",
             "| Question | Tools called | Tool OK | Verified | Rewrites |", "|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['q']} | {', '.join(r['tools']) or r.get('error', '-')} | {'yes' if r['ok_tool'] else 'NO'} | "
                     f"{'yes' if r['verified'] else 'NO'} | {r['rewrites']} |")
    report = "\n".join(lines)
    print(report)
    if out_path:
        Path(out_path).write_text(report + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    asyncio.run(main(ap.parse_args().out))
