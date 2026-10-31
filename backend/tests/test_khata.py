"""Offline tests for the voice ledger (Khata) and the crop-loss claim kit: python tests/test_khata.py from backend/."""
import asyncio
import os
os.environ["CACHE_TTL_S"] = "0"
os.environ["MOCK_MODE"] = "1"
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import claim, config, ledger, meta_client  # noqa: E402


def test_rule_parser_three_languages():
    p = lambda s, c="": asyncio.run(ledger.parse_entry(s, c))
    e = p("bought urea for Rs 1,500 today")
    assert (e["type"], e["category"], e["amount_rs"], e["amount_in_words"], e["via"]) == ("expense", "fertilizer", 1500, True, "rules")
    s = p("sold 8 quintals groundnut at 7000")
    assert (s["type"], s["category"], s["amount_rs"], s["quantity_q"], s["crop"]) == ("income", "sale", 56000, 8.0, "groundnut")
    assert s["amount_in_words"] is True                                    # 8 x 7000 is built from numbers the farmer said
    te = p("యూరియా కొన్నాను ౨౫౦౦ రూపాయలు")                                  # Telugu digits
    assert te["category"] == "fertilizer" and te["amount_rs"] == 2500
    hi = p("मज़दूरी में 3000 रुपये दिए")
    assert hi["category"] == "labour" and hi["amount_rs"] == 3000
    assert p("paid for spray 800", "cotton")["crop"] == "cotton"           # falls back to the profile crop
    assert p("received pm kisan subsidy 2000")["category"] == "subsidy"
    assert p("bought something")["error"] == "no_amount" and p("")["error"] == "empty"
    assert p("spent 99999999999 rupees")["error"] == "no_amount"            # absurd amounts are rejected


def test_model_output_is_validated_and_ungrounded_amounts_are_flagged():
    config.MOCK_MODE = False
    config.CHAT_KEY = "k"
    orig = meta_client.chat
    try:
        async def good(messages, use_open_model=False, **extra):
            assert extra.get("temperature") == 0
            return 'Sure! {"type":"expense","category":"seed","amount_rs":2000,"quantity_q":null,"crop":"paddy","note":"paddy seed"}'
        meta_client.chat = good
        e = asyncio.run(ledger.parse_entry("రెండు వేలకు వరి విత్తనాలు కొన్నాను"))      # amount said in words, no digits
        assert e["via"] == "model" and e["amount_rs"] == 2000 and e["amount_in_words"] is False   # UI must ask to confirm

        async def bad(messages, use_open_model=False, **extra):
            return "I cannot do that"
        meta_client.chat = bad
        e = asyncio.run(ledger.parse_entry("bought diesel 500"))
        assert e["via"] == "rules" and e["category"] == "irrigation" and e["amount_rs"] == 500

        async def boom(messages, use_open_model=False, **extra):
            raise RuntimeError("model down")
        meta_client.chat = boom
        assert asyncio.run(ledger.parse_entry("tractor 1200"))["category"] == "machinery"

        async def weird(messages, use_open_model=False, **extra):
            return '{"type":"income","category":"magic","amount_rs":"abc"}'
        meta_client.chat = weird
        assert asyncio.run(ledger.parse_entry("sold cotton 5000"))["via"] == "rules"
    finally:
        meta_client.chat = orig
        config.MOCK_MODE = True
        config.CHAT_KEY = ""


def _entries():
    mk = lambda t, c, a, crop="": {"type": t, "category": c, "amount_rs": a, "crop": crop, "note": "x", "date": "2026-10-01"}
    return [mk("expense", "seed", 4000, "groundnut"), mk("expense", "fertilizer", 6000, "groundnut"), mk("expense", "labour", 10000, "groundnut"),
            mk("income", "sale", 56000, "groundnut"), {"bad": 1}, "x", mk("expense", "labour", -5)]


def test_report_is_exact_in_all_languages():
    r = ledger.report(_entries(), 2, "en")
    assert r["entries"] == 4 and r["income_rs"] == 56000 and r["expense_rs"] == 20000 and r["net_rs"] == 36000
    assert r["cost_per_acre_rs"] == 10000 and r["by_category"][0] == {"category": "labour", "amount_rs": 10000, "share_pct": 50}
    assert r["by_crop"][0]["net_rs"] == 36000
    assert "Net profit: ₹36,000" in r["text"] and "Cost per acre: ₹10,000" in r["text"] and "Not an audited" in r["text"]
    assert "నికర లాభం: ₹36,000" in ledger.report(_entries(), 2, "te")["text"]
    assert "शुद्ध मुनाफ़ा: ₹36,000" in ledger.report(_entries(), 2, "hi")["text"]
    mixed = ledger.report([{"type": "expense", "category": "seed", "amount_rs": 100, "crop": "Groundnut"},
                           {"type": "income", "category": "sale", "amount_rs": 900, "crop": "groundnut"}], 1, "en")
    assert len(mixed["by_crop"]) == 1 and mixed["by_crop"][0]["net_rs"] == 800      # "Groundnut" and "groundnut" are one crop
    loss = ledger.report([{"type": "expense", "category": "seed", "amount_rs": 5000}], None, "en")
    assert loss["net_rs"] == -5000 and "Net loss: ₹5,000" in loss["text"] and loss["cost_per_acre_rs"] is None
    assert ledger.report("nope", 3)["entries"] == 0 and ledger.report(_entries(), "abc")["acres"] is None


def test_claim_deadline_is_exactly_72_hours():
    now = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
    occurred = (now - timedelta(hours=30)).isoformat()
    r = claim.build_claim({"district": "Kurnool", "main_crop": "Groundnut"}, {"cause": "hailstorm", "occurred_at": occurred, "acres": 2.5}, "en", now)
    assert r["individual_claim"] and r["status"] == "open" and r["hours_left"] == 42.0
    assert r["deadline"] == (now + timedelta(hours=42)).isoformat() and len(r["checklist"]) == 5
    assert "Groundnut" in r["message"] and "2.5 acres" in r["message"] and "Kurnool" in r["message"] and "14447" in r["how"]
    urgent = claim.build_claim({}, {"cause": "fire", "occurred_at": (now - timedelta(hours=60)).isoformat()}, "en", now)
    assert urgent["status"] == "urgent" and urgent["hours_left"] == 12.0
    late = claim.build_claim({}, {"cause": "landslide", "occurred_at": (now - timedelta(hours=80)).isoformat()}, "en", now)
    assert late["status"] == "expired" and late["hours_left"] == 0
    future = claim.build_claim({}, {"cause": "fire", "occurred_at": (now + timedelta(hours=5)).isoformat()}, "en", now)
    assert future["hours_left"] == 72.0                                   # an event cannot be in the future


def test_area_level_losses_are_not_given_a_fake_deadline_and_post_harvest_has_14_day_note():
    now = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
    r = claim.build_claim({}, {"cause": "other"}, "en", now)
    assert r["individual_claim"] is False and r["status"] == "area_level" and "deadline" not in r
    assert "crop cutting" in r["guidance"] and len(r["checklist"]) == 1
    p = claim.build_claim({}, {"cause": "post_harvest_rain", "occurred_at": now.isoformat()}, "en", now)
    assert p["individual_claim"] and "14 days" in p["guidance"]
    assert claim.build_claim({}, {"cause": "bogus"}, "en", now)["cause"] == "other"
    assert claim.build_claim({}, {"cause": "hailstorm", "occurred_at": "garbage", "acres": "x"}, "en", now)["hours_left"] == 72.0


def test_claim_in_all_languages_and_endpoints():
    now = datetime.now(timezone.utc)
    for code in ("en", "te", "hi"):
        r = claim.build_claim({"main_crop": "Paddy"}, {"cause": "hailstorm", "occurred_at": now.isoformat()}, code)
        assert r["guidance"] and r["message"] and r["how"] and "{" not in r["message"] and "{" not in r["how"], code
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    j = c.post("/api/claim/draft", json={"profile": {"district": "Kurnool"}, "loss": {"cause": "hailstorm"}, "lang": "te"}).json()
    assert j["status"] == "open" and j["cause_label"] == "వడగళ్ల వాన"
    assert c.post("/api/claim/draft", json={}).status_code == 200
    j = c.post("/api/ledger/parse", json={"text": "bought urea 1500", "crop": "paddy"}).json()
    assert j["amount_rs"] == 1500 and j["crop"] == "paddy" and j["date"]
    assert c.post("/api/ledger/report", json={"entries": _entries(), "acres": 2, "lang": "en"}).json()["net_rs"] == 36000


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok", fn.__name__)
    print(f"{len(fns)} passed")
