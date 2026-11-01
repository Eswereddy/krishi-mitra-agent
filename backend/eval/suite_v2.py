"""Evaluation suite v2: what can be MEASURED WITHOUT a live model, measured for real, plus an optional live section.

    cd backend && python eval/suite_v2.py --out ../EVAL_V2.md          # offline, deterministic, runs anywhere
    python eval/suite_v2.py --live --out ../EVAL_V2.md                 # also runs the 28-question live agent eval (needs a model key)

Honesty rules: every section says exactly what it does and does not prove. Offline sections test OUR code (verification layer,
photo-quality gate, content, caching, fallbacks) with synthetic inputs and stubbed networks; they say nothing about how the live
model or live APIs behave. Live numbers appear only when --live is used and are never invented. Tool-selection accuracy exists
only in the live section.
"""
import argparse
import asyncio
import os
import re
import statistics
import sys
import time
from pathlib import Path

os.environ.setdefault("CACHE_TTL_S", "0")
os.environ.setdefault("MOCK_MODE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image, ImageFilter  # noqa: E402
import random  # noqa: E402
from app import (buyers, cases, claim, router, climate, coach, config, doctor, meta_client, outcomes, pestwatch, tools, twin, verify, warning)  # noqa: E402
from app.main import app  # noqa: E402

REPORT: list[dict] = []


def section(title, scope, checks, extra=None):
    """checks: list of (name, passed:boolean). Records the section for the report."""
    REPORT.append({"title": title, "scope": scope, "checks": checks, "extra": extra or []})


# ---------------------------------------------------------------- 1. numerical verification + hallucination probes
def numerical():
    P = [{"tool": "get_mandi_price", "result": {"results": [{"modal_price_per_quintal": 6200}]}}]
    W = [{"tool": "get_weather", "result": {"forecast": [{"max_c": 33.1, "min_c": 22.0, "rain_mm": 4.2, "rain_chance_pct": 60}]}}]
    tr = [{"tool": "get_price_trend", "result": {"change_pct": 5.3}}]
    good = [("Groundnut is Rs 6,200 per quintal", P), ("ధర 6200 రూపాయలు", P), ("Max 33.1°C and 4.2 mm rain", W), ("Rain chance 60%", W), ("Up 5.3%", tr)]
    bad = [("Groundnut is Rs 7,400 per quintal", P), ("Rs 6,200 per quintal and Rs 9,000 later", P), ("Max 38°C tomorrow", W), ("Expect 25 mm of rain", W),
           ("Rain chance 90%", W), ("Prices rose 15%", tr), ("Price is Rs 6200", []), ("The mandi pays ₹5,000", [{"tool": "x", "result": {"error": "no data"}}])]
    ok_good = [verify.verify_answer(a, s)["passed"] for a, s in good]
    caught = [not verify.verify_answer(a, s)["passed"] for a, s in bad]
    section("Numerical verification and hallucinated-figure detection",
            "Our verification layer on hand-written (answer, tool result) pairs. Proves the checker catches wrong or unsupported figures; "
            "does not measure how often the live model makes them.",
            [(f"correct figures accepted: {sum(ok_good)}/{len(good)}", all(ok_good)),
             (f"fabricated / unsupported figures caught: {sum(caught)}/{len(bad)}", all(caught))],
            [f"false accept rate {100 - 100 * sum(caught) // len(bad)}%, false reject rate {100 - 100 * sum(ok_good) // len(good)}% on these cases (n={len(good) + len(bad)})"])


CHEM = re.compile(r"\b(mancozeb|chlorpyrifos|imidacloprid|carbendazim|cypermethrin|glyphosate|profenofos|dimethoate|acephate|monocrotophos|"
                  r"copper oxychloride|metalaxyl|paraquat|endosulfan)\b|\b\d+(\.\d+)?\s?(ml|g|gm|mg)\s?(/|per)\s?(l|litre|liter|acre|ha|hectare)\b", re.I)


def _leaves(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from _leaves(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from _leaves(v)


def no_chemicals():
    sources = {"doctor.STEPS": doctor.STEPS, "doctor.REASONS": doctor.REASONS, "doctor.ESCALATION": doctor.ESCALATION, "warning.AT": warning.AT,
               "warning.T": warning.T, "cases.L": cases.L, "coach.TASKS": coach.TASKS, "outcomes.T": outcomes.T, "twin.T": twin.T, "buyers.T": buyers.T}
    hits = [(n, t[:60]) for n, src in sources.items() for t in _leaves(src) if CHEM.search(t)]
    section("Unsafe-advice scan of built-in advice text",
            "Scans every built-in advice string (te/hi/en) for pesticide product names and dose patterns. Proves our static content never "
            "names a product or dose; says nothing about model-written answers.",
            [(f"{len(sources)} advice tables scanned, product/dose mentions found: {len(hits)}", not hits)], [f"hit: {h}" for h in hits])


# ---------------------------------------------------------------- 2. image reliability (synthetic)
def _img(kind, seed):
    r = random.Random(seed)
    if kind == "tiny":
        return Image.effect_noise((120, 120), 60)
    base = Image.effect_noise((640, 480), 70 + r.randint(0, 20)).convert("L")
    if kind == "dark":
        base = base.point(lambda v: v // 8)
    elif kind == "bright":
        base = base.point(lambda v: 225 + v // 10)
    elif kind == "blurry":
        base = base.filter(ImageFilter.GaussianBlur(9))
    return base.convert("RGB")


def images():
    n, hits, rows = 0, {}, []
    sam_ok = {"found": True, "severity_pct": 12.0, "band": "moderate", "leaf_found": True, "spots": [{"box": [0, 0, 1, 1], "confidence": 0.9}]}
    for kind, want_clear in (("good", True), ("dark", False), ("bright", False), ("blurry", False), ("tiny", False)):
        got = 0
        for seed in range(8):
            q = doctor.photo_quality(_img(kind, seed))
            rel = doctor.assess(sam_ok, q)["reliability"]
            got += (rel == "clear") == want_clear
            n += 1
        hits[kind] = got
        rows.append(f"{kind}: {got}/8 gated correctly")
    section("Image reliability gate (Farm Doctor)",
            f"Synthetic images (noise textures, darkened, over-exposed, Gaussian-blurred, tiny) pushed through photo_quality + assess with a confident "
            f"fake SAM result. Proves the gate stops bad photos from being called reliable. Does NOT measure SAM 3.1 accuracy or real leaf photos: "
            f"thresholds must still be checked on real phone photos.", [(f"{sum(hits.values())}/{n} photos classified as expected", sum(hits.values()) == n)], rows)


# ---------------------------------------------------------------- 3. multilingual completeness
SCRIPT = {"te": re.compile(r"[ఀ-౿]"), "hi": re.compile(r"[ऀ-ॿ]")}


def _flat(o, p=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from _flat(v, f"{p}/{k}")
    elif isinstance(o, (list, tuple)):
        for i, v in enumerate(o):
            yield from _flat(v, f"{p}/{i}")
    else:
        yield p, o


def multilingual():
    top = {"cases.L": cases.L, "outcomes.T": outcomes.T, "twin.T": twin.T, "warning.T": warning.T, "buyers.T": buyers.T, "claim.T": claim.T,
           "doctor.STEPS": doctor.STEPS, "doctor.REASONS": doctor.REASONS, "doctor.ESCALATION": doctor.ESCALATION}
    leaf = {"warning.AT": warning.AT, "coach.TASKS": coach.TASKS, "coach.STAGES": coach.STAGES}
    problems, count = [], 0
    for name, d in top.items():
        base = dict(_flat(d.get("en", {})))
        for lg in ("te", "hi"):
            other = dict(_flat(d.get(lg, {})))
            count += 1
            miss = set(base) - set(other)
            if miss:
                problems.append(f"{name}[{lg}] missing {len(miss)} keys, e.g. {sorted(miss)[0]}")
            for p, v in other.items():
                if isinstance(v, str) and (not v.strip() or (len(base.get(p, "")) > 25 and not SCRIPT[lg].search(v))):
                    problems.append(f"{name}[{lg}]{p} empty or not in script")
    for name, d in leaf.items():
        for code, langs in d.items():
            count += 1
            for lg in ("te", "hi"):
                v = langs.get(lg)
                if not v or (len(langs.get("en", "")) > 25 and not SCRIPT[lg].search(v)):
                    problems.append(f"{name}[{code}][{lg}] missing or not in script")
    section("Multilingual completeness (te / hi / en)",
            "Every built-in table has the same keys in Telugu and Hindi as in English, none empty, and long strings actually contain Telugu/Devanagari script. "
            "Proves coverage, not translation quality: a native speaker must still review the wording.",
            [(f"{count} table-language pairs checked, problems: {len(problems)}", not problems)], problems[:10])


# ---------------------------------------------------------------- 4. data freshness and labelling
def freshness():
    checks = []
    calls = {"n": 0}
    os.environ["CACHE_TTL_S"] = "100"
    real = time.monotonic
    clock = {"t": real()}
    tools.time.monotonic = lambda: clock["t"]
    try:
        tools._CACHE.clear()

        def fn():
            calls["n"] += 1
            return {"v": calls["n"]}
        a = tools._cached("ev", "k", fn)
        b = tools._cached("ev", "k", fn)
        clock["t"] += 101
        c = tools._cached("ev", "k", fn)
        checks.append(("cache serves a repeat within TTL, then refetches after it expires", a == b and c["v"] == 2 and calls["n"] == 2))
        n0 = calls["n"]
        tools._cached("ev", "bad", lambda: (calls.__setitem__("n", calls["n"] + 1), {"error": "x"})[1], ok=lambda v: "error" not in v)
        tools._cached("ev", "bad", lambda: (calls.__setitem__("n", calls["n"] + 1), {"error": "x"})[1], ok=lambda v: "error" not in v)
        checks.append(("failed fetches are never cached (retried each time)", calls["n"] - n0 == 2))
    finally:
        tools.time.monotonic = real
        os.environ["CACHE_TTL_S"] = "0"
        tools._CACHE.clear()
    os.environ.pop("DATA_GOV_API_KEY", None)
    r = tools.get_mandi_price("groundnut", "Andhra Pradesh", "Kurnool")
    src = str(r.get("source", ""))
    checks.append((f"price fallback is labelled (source = '{src}')", "sample" in src or "snapshot" in src or "data.gov" in src or "agmarknet" in src))
    checks.append(("sample data carries an explanatory note", "sample" not in src or bool(r.get("note"))))
    tools.get_weather = lambda place, days=7: {"place": "K", "source": "open-meteo.com", "forecast": [{"date": "2026-10-30", "max_c": 30, "min_c": 20, "rain_mm": 0, "wind_kmh": 5}]}
    pestwatch.disease_risk = lambda *a, **k: {"needs_attention": False}
    w = asyncio.run(warning.check("tomato", "K", "IN"))
    checks.append(("warnings say their source is a live forecast", "live" in w["source"]))
    section("Data freshness and labelling",
            "Cache expiry logic, no caching of failures, and that fallbacks and live sources are labelled. Network is stubbed. Does NOT test that the real "
            "APIs are reachable or current: check live on Render.", checks)


# ---------------------------------------------------------------- 5. failure recovery
def failures():
    checks = []
    calls = []
    real_post = meta_client._post_chat

    async def flaky(base, key, model, messages, extra):
        calls.append(model)
        if len(calls) == 1:
            raise httpx.ConnectTimeout("t")
        return {"content": "fallback answer", "tool_calls": None}
    meta_client._post_chat = flaky
    config.GLIMMER_BASE_URL, config.GLIMMER_API_KEY, config.GLIMMER_MODEL = "http://g", "k", "glimmer"
    out = asyncio.run(meta_client.chat_message([{"role": "user", "content": "hi"}]))
    checks.append(("main model timeout -> open-weight Glimmer fallback answers", out["content"] == "fallback answer" and calls[-1] == "glimmer"))

    async def always(base, key, model, messages, extra):
        raise httpx.ConnectTimeout("t")
    meta_client._post_chat = always
    try:
        asyncio.run(meta_client.chat_message([{"role": "user", "content": "hi"}]))
        both = False
    except httpx.HTTPError:
        both = True
    checks.append(("both models down -> clean error raised (handled as friendly 502 by the API)", both))
    req = httpx.Request("POST", "http://x")

    async def bad_request(base, key, model, messages, extra):
        calls.append(model)
        raise httpx.HTTPStatusError("bad", request=req, response=httpx.Response(400, request=req))
    meta_client._post_chat = bad_request
    calls.clear()
    try:
        asyncio.run(meta_client.chat_message([{"role": "user", "content": "hi"}]))
    except httpx.HTTPStatusError:
        pass
    checks.append(("our own bad request (400) is not retried on the fallback model", len(calls) == 1))
    meta_client._post_chat = real_post
    config.GLIMMER_BASE_URL = ""

    tools.TOOL_FUNCS["boom"] = lambda **k: (_ for _ in ()).throw(RuntimeError("boom"))
    r = tools.run_tool("boom", {})
    checks.append(("a crashing tool returns an error result instead of crashing the agent", "error" in r and "boom" not in tools.TOOL_FUNCS.get("none", "")))
    del tools.TOOL_FUNCS["boom"]

    tools.get_weather = lambda place, days=7: {"error": "weather service unavailable"}
    c = TestClient(app)
    wr = c.post("/api/warnings/check", json={"crop": "tomato", "place": "K"})
    checks.append(("weather down -> warnings returns a JSON error, not a crash", wr.status_code == 200 and "error" in wr.json()))
    cs = c.post("/api/case/build", json={"consent": {"share_details": True, "share_location": True}, "profile": {"crop": "tomato", "place": "K"}, "symptoms": ["wilting"]})
    checks.append(("weather down -> expert case still builds (weather omitted, not invented)", cs.status_code == 200 and cs.json()["weather"] is None))
    climate._fetch = lambda *a: {"error": "down"}
    tw = c.post("/api/twin/report", json={"twin": {"crop": "tomato", "acres": 1, "place": "K", "sowing_date": "2026-08-01"}})
    checks.append(("history archive down -> twin report says weather is unavailable", tw.status_code == 200 and any(f["basis"] == "unavailable" for f in tw.json()["facts"])))
    section("Failure recovery",
            "Injected failures in the model call, a tool and the weather/archive services. Proves graceful degradation paths in our code. The offline PWA "
            "behaviour (saved brief/plan, cached shell) is checked in the browser, not here.", checks)


# ---------------------------------------------------------------- 6. latency (compute only)
def latency():
    tools.get_weather = lambda place, days=7: {"place": "K", "forecast": [{"date": "2026-10-30", "max_c": 41, "min_c": 20, "rain_mm": 30, "wind_kmh": 50}] * 7}
    pestwatch.disease_risk = lambda *a, **k: {"needs_attention": False}
    climate._fetch = lambda place, country, s, e: {"place": "K", "daily": {"time": [], "precipitation_sum": [], "temperature_2m_mean": []}}
    c = TestClient(app)
    reqs = {
        "/api/case/build": {"consent": {"share_details": True}, "symptoms": ["wilting"], "profile": {"crop": "tomato"}},
        "/api/outcomes/report": {"records": [{"text": "x", "done": True}] * 50},
        "/api/twin/report": {"twin": {"crop": "tomato", "acres": 2, "place": "K", "sowing_date": "2026-08-01"}},
        "/api/warnings/check": {"crop": "tomato", "place": "K"},
        "/api/buyers/compare": {"offers": [{"price": 2300}] * 5, "quantity": 10},
        "/api/claim/draft": {"profile": {}, "loss": {"cause": "hailstorm", "occurred_at": "2026-10-30T10:00:00+00:00"}},
    }
    rows, ok = [], True
    from app import ratelimit
    for path, body in reqs.items():
        ts = []
        for _ in range(25):
            ratelimit._hits.clear()
            t0 = time.perf_counter()
            r = c.post(path, json=body)
            ts.append((time.perf_counter() - t0) * 1000)
            ok &= r.status_code == 200
        ts.sort()
        rows.append(f"{path}: median {statistics.median(ts):.1f} ms, p95 {ts[int(len(ts) * .95) - 1]:.1f} ms (25 runs)")
    section("Latency (compute only)",
            "Time inside our endpoints with the network STUBBED, so this is our code's cost only. Real latency is dominated by the model and weather calls "
            "and is measured only in the live section.", [("all endpoints answered 200 during timing", ok)], rows)


def routing():
    import json as _json
    import run_eval
    full = len(_json.dumps(tools.TOOL_SPECS))
    rows, hit, narrowed, ratios, misses = [], 0, 0, [], []
    for q, profile, lang, expected in run_eval.CASES:
        offered = router.select(tools.TOOL_SPECS, q)
        names = {s["function"]["name"] for s in offered}
        ok = bool(expected & names)
        hit += ok
        narrowed += len(offered) < len(tools.TOOL_SPECS)
        ratios.append(len(_json.dumps(offered)) / full)
        if not ok:
            misses.append(f"MISS: '{q}' needs one of {sorted(expected)} but offered {len(offered)} tools without it")
    n = len(run_eval.CASES)
    section("Tool router (offline recall)",
            "For each of the 28 evaluation questions: is at least one expected tool among the tools offered to the model? Keywords were written while looking "
            "at these same questions, so this is IN-SAMPLE recall and will be lower on new questions; unclear questions get all tools. Does not measure which tool the model picks.",
            [(f"expected tool offered: {hit}/{n}", hit == n)],
            [f"questions narrowed below all {len(tools.TOOL_SPECS)} tools: {narrowed}/{n}", f"average prompt size for tool specs: {100 * statistics.mean(ratios):.0f}% of sending everything"] + misses)


HELD_OUT = [  # written AFTER the keywords, never used to tune them
    ("My tomato leaves have brown spots", {"lookup_problem"}), ("What is the rate for cotton in Adoni?", {"get_mandi_price"}),
    ("Is my farm too dry this month compared to other years?", {"season_check"}), ("How much urea should I buy? What does a kg of nitrogen cost me?", {"compare_inputs"}),
    ("Can I get a bank loan at 2% interest?", {"loan_compare", "kcc_interest"}), ("When to sow sorghum in Nakuru?", {"planting_window"}),
    ("Bei ya maharage ni ngapi?", {"get_market_price"}), ("Cuanta agua necesita mi maiz?", {"water_plan"}),
    ("Is it safe to keep my groundnut at 12% moisture?", {"storage_check"}), ("Heat stress for my buffalo tomorrow?", {"livestock_heat"}),
    ("How many days until my cotton is ready?", {"crop_guide"}), ("Tell me something useful", {"get_expert_help"}),
]


def routing_heldout():
    hits, notes = 0, []
    for q, exp in HELD_OUT:
        offered = {s["function"]["name"] for s in router.select(tools.TOOL_SPECS, q)}
        ok = bool(exp & offered)
        hits += ok
        notes.append(f"{'ok' if ok else 'MISS'}: '{q}' -> {len(offered)} tools offered")
    section("Tool router (held-out questions)",
            f"{len(HELD_OUT)} questions written after the keywords and never used to tune them. A better estimate of recall on new questions, but still a small hand-written set.",
            [(f"expected tool offered: {hits}/{len(HELD_OUT)}", hits == len(HELD_OUT))], notes)


SECTIONS = [numerical, routing, routing_heldout, no_chemicals, images, multilingual, freshness, failures, latency]


def render(live_report: str | None) -> str:
    total = sum(len(s["checks"]) for s in REPORT)
    passed = sum(p for s in REPORT for _, p in s["checks"])
    L = ["# Evaluation report v2", "",
         f"Mode: **offline deterministic** (no live model, networks stubbed) {'+ live agent run below' if live_report else '(live agent run NOT included: no --live)'}.",
         f"Generated by `python eval/suite_v2.py`; every number below was produced by that run. **{passed}/{total} checks passed.**", ""]
    for s in REPORT:
        L += [f"## {s['title']}", "", f"_Scope: {s['scope']}_", ""]
        L += [f"- {'PASS' if p else 'FAIL'}: {n}" for n, p in s["checks"]]
        L += [f"- {e}" for e in s["extra"]]
        L.append("")
    L += ["## Not measured here", "",
          "- Tool-selection accuracy, live answer quality, live latency and live data freshness need a model key and network: run with `--live`.",
          "- SAM 3.1 accuracy on real leaf photos, and translation quality by native speakers, are human checks.", ""]
    if live_report:
        L += ["## Live agent run", "", live_report]
    return "\n".join(L)


async def live() -> str:
    import run_eval
    rows = [await run_eval.run_case(*c) for c in run_eval.CASES]
    n = len(rows)
    tool_ok, ver_ok = sum(r["ok_tool"] for r in rows), sum(r["verified"] for r in rows)
    secs = sorted(r["secs"] for r in rows)
    lines = [f"- Right tool called (tool selection): **{tool_ok}/{n}**", f"- Every figure verified, no India-only terms abroad: **{ver_ok}/{n}**",
             f"- Latency: median **{statistics.median(secs):.1f}s**, p95 {secs[int(n * .95) - 1]:.1f}s, slowest {secs[-1]:.1f}s", "",
             "| Question | Tools | Tool OK | Verified | Rewrites |", "|---|---|---|---|---|"]
    lines += [f"| {r['q']} | {', '.join(r['tools']) or r.get('error', '-')} | {'yes' if r['ok_tool'] else 'NO'} | {'yes' if r['verified'] else 'NO'} | {r['rewrites']} |" for r in rows]
    return "\n".join(lines)


def run_all() -> list[dict]:
    REPORT.clear()
    for fn in SECTIONS:
        fn()
    return REPORT


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--live", action="store_true")
    a = ap.parse_args()
    run_all()
    live_md = None
    if a.live:
        sys.path.insert(0, str(Path(__file__).parent))
        os.environ["MOCK_MODE"] = "0"
        config.MOCK_MODE = False
        live_md = asyncio.run(live())
    md = render(live_md)
    print(md)
    if a.out:
        Path(a.out).write_text(md + "\n")
