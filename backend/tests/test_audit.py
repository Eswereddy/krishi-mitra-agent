"""Offline tests for the Muse Wonder second opinion. Run from backend/: python tests/test_audit.py"""
import asyncio
import json
import os
os.environ["CACHE_TTL_S"] = "0"
os.environ["MOCK_MODE"] = "1"
os.environ.pop("MODEL_API_KEY", None)
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from app import audit, meta_models as mm  # noqa: E402
from app.main import app  # noqa: E402

STEPS = [{"tool": "get_mandi_price", "args": {}, "result": {"results": [{"market": "Kurnool", "modal_price_per_quintal": 7100}]}},
         {"tool": "get_weather", "args": {}, "result": {"error": "down"}}]


def _mock(reply: str, seen: dict | None = None, status: int = 200):
    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        if seen is not None:
            seen.update(url=str(req.url), body=body, auth=req.headers.get("authorization"))
        return httpx.Response(status, json={"output": [{"type": "message", "content": [{"type": "output_text", "text": reply}]}]})
    mm._TRANSPORT = httpx.MockTransport(handler)


def test_parse_is_lenient_and_bounded():
    d = audit.parse('Sure!\n```json\n{"verdict":"issues","issues":[{"claim":"a","problem":"b"}],"missing_caveats":["c","d","e","f"]}\n```')
    assert d["verdict"] == "issues" and d["issues"] == [{"claim": "a", "problem": "b"}] and len(d["missing_caveats"]) == 3
    assert audit.parse("no json here") is None and audit.parse("{broken") is None and audit.parse("[1]") is None
    assert audit.parse('{"verdict":"consistent"}')["verdict"] == "consistent"
    assert audit.parse('{"verdict":"consistent","issues":[{"claim":"x"}]}')["verdict"] == "issues"     # an issue always wins


def test_facts_only_contain_good_tool_results_and_are_capped():
    f = json.loads(audit.facts(STEPS))
    assert [x["tool"] for x in f] == ["get_mandi_price"]                    # the failed tool is not a "fact"
    big = [{"tool": "t", "result": {"x": "y" * 20000}}]
    assert len(audit.facts(big)) <= audit.MAX_FACT_CHARS and audit.facts("junk") == "[]"


def test_without_key_only_the_code_check_runs():
    r = asyncio.run(audit.second_opinion("Kurnool price is 7100 per quintal.", STEPS, "en"))
    assert r["available"] is False and r["reason"] == "no_key" and r["verdict"] == "consistent" and r["numbers_checked_in_code"]["passed"]
    bad = asyncio.run(audit.second_opinion("Kurnool price is 9900 per quintal.", STEPS, "en"))
    assert bad["verdict"] == "issues" and bad["numbers_checked_in_code"]["unverified"] == ["9900"]


def test_wonder_audit_request_and_result():
    os.environ["MODEL_API_KEY"] = "k"
    seen = {}
    _mock('{"verdict":"issues","issues":[{"claim":"sell now","problem":"no trend data was fetched"}],"missing_caveats":["Prices change daily"]}', seen)
    try:
        r = asyncio.run(audit.second_opinion("Price is 7100, sell now.", STEPS, "te"))
        assert seen["url"].endswith("/v1/responses") and seen["auth"] == "Bearer k"
        b = seen["body"]
        assert b["model"] == "muse-wonder-1.0" and b["reasoning"]["effort"] == "medium" and "Telugu" in b["input"] and "7100" in b["input"]
        assert r["available"] and r["verdict"] == "issues" and r["issues"][0]["problem"].startswith("no trend") and r["missing_caveats"] == ["Prices change daily"]
        # the model says "consistent" but a number is invented: code wins
        _mock('{"verdict":"consistent","issues":[],"missing_caveats":[]}')
        r2 = asyncio.run(audit.second_opinion("Price is 8800.", STEPS, "en"))
        assert r2["verdict"] == "issues" and r2["numbers_checked_in_code"]["unverified"] == ["8800"]
        _mock('{"verdict":"consistent","issues":[],"missing_caveats":[]}')
        assert asyncio.run(audit.second_opinion("Price is 7100.", STEPS, "en"))["verdict"] == "consistent"
        _mock("sorry cannot")
        assert asyncio.run(audit.second_opinion("Price is 7100.", STEPS, "en"))["reason"] == "auditor_unclear"
        _mock("x", status=500)
        r3 = asyncio.run(audit.second_opinion("Price is 7100.", STEPS, "en"))
        assert r3["reason"] == "auditor_unavailable" and r3["verdict"] == "unknown"       # failure never breaks the answer
        assert asyncio.run(audit.second_opinion("Price 7100", [], "en"))["reason"] == "no_tool_results"
    finally:
        os.environ.pop("MODEL_API_KEY", None)
        mm._TRANSPORT = None


def test_output_text_shapes_and_status():
    assert mm._output_text({"output_text": " hi "}) == "hi"
    assert mm._output_text({"output": [{"content": [{"type": "output_text", "text": "a"}, {"type": "reasoning", "text": "no"}]}]}) == "a"
    assert mm.status()["muse_wonder"]["model"] == "muse-wonder-1.0"


def test_endpoint():
    c = TestClient(app)
    assert c.post("/api/second-opinion", json={}).status_code == 400
    r = c.post("/api/second-opinion", json={"answer": "Price is 7100.", "steps": STEPS + ["junk", 5], "lang": "xx"})
    assert r.status_code == 200 and r.json()["verdict"] == "consistent" and r.json()["available"] is False


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok", fn.__name__)
    print(len(fns), "passed")
