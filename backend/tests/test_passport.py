"""Sustainability passport: nothing is claimed without evidence, savings need a complete four-week log, absence claims are never supported, no certification wording."""
import datetime as dt, os, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["MOCK_MODE"] = "1"
os.environ["RATE_AGENT_PER_MIN"] = "1000"
from fastapi.testclient import TestClient
from app import passport as p
from app.main import app

c = TestClient(app)
TODAY = dt.date(2026, 11, 3)
IRR = [{"date": f"2026-09-{d:02d}", "mm": 40} for d in (1, 8, 15, 22, 29)]
BAN = re.compile(r"certified|eco-friendly|carbon|net zero|score|rating|organic|sustainable|green|climate-smart|pesticide-free|chemical-free", re.I)


def codes(payload, lang="en"):
    r = p.build(payload, lang, TODAY)
    return {x["code"]: x for x in r["supported"]}, {x["code"]: x for x in r["not_claimed"]}, r


def test_empty_passport_claims_nothing():
    ok, no, r = codes({})
    assert ok == {} and r["counts"]["supported"] == 0
    assert {"water_recorded", "input_reduction", "rotation"} <= set(no), no.keys()
    assert "No claim is supported" in r["text"]


def test_water_saving_needs_every_condition():
    base = {"irrigation": IRR, "irrigation_baseline_mm_per_week": 60, "irrigation_log_complete": True}
    ok, no, _ = codes(base)
    assert "water_saving" in ok and "17%" in ok["water_saving"]["text"] and "baseline, not a standard" in ok["water_saving"]["text"]
    for change, why in [({"irrigation_baseline_mm_per_week": None}, "No usual weekly"), ({"irrigation_log_complete": False}, "not confirmed"), ({"irrigation_log_complete": None}, "not confirmed"),
                        ({"irrigation": IRR[:3]}, "Fewer than 4"), ({"irrigation": [{"date": "2026-09-01", "mm": 40}, {"date": "2026-09-05", "mm": 40}, {"date": "2026-09-09", "mm": 40}, {"date": "2026-09-12", "mm": 40}]}, "less than 28 days"),
                        ({"irrigation_baseline_mm_per_week": 30}, "not below")]:
        ok, no, _ = codes({**base, **change})
        assert "water_saving" not in ok, change
        assert "water_saving" in no and why in no["water_saving"]["why"], (change, no.get("water_saving"))


def test_numbers_are_computed_correctly():
    ok, _, _ = codes({"farm": {"acres": 2}, "irrigation": IRR})
    t = ok["water_recorded"]["text"]
    assert "5 irrigations between 2026-09-01 and 2026-09-29, 200 mm in total" in t and "1,618,744 litres on 2 acres" in t
    ok, _, _ = codes({"khata": [{"date": "2026-08-02", "type": "expense", "category": "fertilizer", "amount_rs": 1500}, {"date": "2026-08-03", "type": "expense", "category": "fertilizer", "amount_rs": 500},
                                {"date": "2026-08-03", "type": "expense", "category": "labour", "amount_rs": 900}]})
    assert "2 entries: fertiliser ₹2,000" in ok["inputs_recorded"]["text"] and "labour" not in ok["inputs_recorded"]["text"] and "not the quantity used" in ok["inputs_recorded"]["text"]


def test_input_reduction_is_never_claimed():
    for payload in ({}, {"khata": [{"date": "2025-01-01", "type": "expense", "category": "fertilizer", "amount_rs": 9000}, {"date": "2026-08-01", "type": "expense", "category": "fertilizer", "amount_rs": 100}]}):
        ok, no, _ = codes(payload)
        assert "input_reduction" in no and "input_reduction" not in ok


def test_rotation_needs_two_crops_and_says_what_it_shows():
    ok, no, _ = codes({"khata": [{"date": "2026-01-01", "type": "income", "category": "crop_sale", "amount_rs": 5, "crop": "Paddy"}]})
    assert "rotation" in no
    ok, _, _ = codes({"khata": [{"date": "2026-01-01", "crop": "Paddy"}, {"date": "2026-08-01", "crop": "groundnut"}]})
    assert "2 crops" in ok["rotation"]["text"] and "not a planned rotation" in ok["rotation"]["text"]


def test_practice_needs_dated_evidence():
    good = {"kind": "photo", "date": "2026-09-10", "note": "mulch on rows"}
    ok, no, _ = codes({"practices": [{"code": "mulching", "evidence": good}]})
    assert ok["mulching"]["status"] == "attached" and "not independently verified" in ok["mulching"]["status_text"]
    bad = [None, {}, {"kind": "photo", "date": "2026-09-10", "note": "ok"}, {"kind": "photo", "date": "2027-01-01", "note": "future dated note"}, {"kind": "video", "date": "2026-09-10", "note": "wrong kind of evidence"},
           {"kind": "photo", "date": "not a date", "note": "bad date text here"}]
    for ev in bad:
        ok, no, _ = codes({"practices": [{"code": "mulching", "evidence": ev}]})
        assert "mulching" in no and "mulching" not in ok, ev
    ok, no, _ = codes({"practices": [{"code": "made_up"}, {"code": "mulching", "evidence": good}, {"code": "mulching", "evidence": good}]})
    assert list(ok).count("mulching") == 1 and "made_up" not in ok and "made_up" not in no


def test_absence_claims_are_never_supported():
    ev = {"kind": "receipt", "date": "2026-09-10", "note": "bought neem oil only"}
    ok, no, _ = codes({"practices": [{"code": "no_synthetic_pesticide", "evidence": ev}]})
    assert "no_synthetic_pesticide" in no and "no_synthetic_pesticide" not in ok and "absence cannot be shown" in no["no_synthetic_pesticide"]["why"]


def test_records_and_safety_are_described_without_overclaiming():
    ok, _, _ = codes({"notes": [{"at": "2026-10-01 08:00", "text": "x"}], "cases": [{"at": "2026-10-02T10:00:00", "urgency": "high"}], "safety": [{"date": "2026-10-30", "level": "stop"}, {"date": "2026-10-31", "level": "ok"}],
                      "outcomes": [{"done": True, "actual": {"cost": 1}}, {"done": False}]})
    assert "1 field note and 1 expert case" in ok["observations"]["text"] and "1 of them high urgency" in ok["observations"]["text"]
    assert "2 machine safety checks are logged" in ok["machine_safety"]["text"] and "not that the machine was operated safely" in ok["machine_safety"]["text"]
    assert "2 advice items are logged; 1 marked done; 1 with a result" in ok["decisions"]["text"]


def test_no_certification_words_in_any_language_or_case():
    big = {"farm": {"crop": "Paddy", "place": "Kurnool", "acres": 3}, "irrigation": IRR, "irrigation_baseline_mm_per_week": 60, "irrigation_log_complete": True,
           "khata": [{"date": "2026-08-02", "type": "expense", "category": "pesticide", "amount_rs": 700, "crop": "a"}, {"date": "2026-08-03", "crop": "b"}],
           "practices": [{"code": x, "evidence": {"kind": "record", "date": "2026-09-10", "note": "dated record"}} for x in p.PRACTICES] + [{"code": "mulching"}]}
    for lang in ("en", "te", "hi"):
        ok, no, r = codes(big, lang)
        for x in list(ok.values()) + list(no.values()):
            body = x["text"] + " " + x.get("why", "") + " " + x.get("next", "")
            if lang == "en": assert not BAN.search(body), (x["code"], body)
        assert r["text"] and r["disclaimer"]
    en = codes(big)[2]
    assert not BAN.search(" ".join(en["never"]).replace("Organic or any certified status", "").replace("Carbon, emission or climate-benefit figures", ""))
    assert re.search(r"[ఀ-౿]", codes(big, "te")[2]["text"]) and re.search(r"[ऀ-ॿ]", codes(big, "hi")[2]["text"])


def test_every_claim_traces_to_a_record_or_attached_evidence():
    _, _, r = codes({"farm": {"acres": 1}, "irrigation": IRR})
    for x in r["supported"]:
        assert x["status"] in ("recorded", "attached") and x["kind"] in ("record", "practice")
    assert r["counts"]["supported"] == len(r["supported"])
    assert "stores nothing" in r["basis"]


def test_bad_input_never_crashes():
    for payload in ({"irrigation": "x", "khata": 5, "practices": {"a": 1}, "notes": [1, None], "farm": "str"}, {"irrigation": [{"date": "2999-01-01", "mm": 40}, {"date": "x", "mm": "y"}, {"mm": 5}]},
                    {"khata": [{"date": "2026-01-01", "type": "expense", "category": "seed", "amount_rs": "abc"}]}):
        r = p.build(payload, "en", TODAY)
        assert r["counts"]["supported"] == 0


def test_endpoint():
    r = c.post("/api/passport/build", json={"lang": "hi", "farm": {"acres": 1}, "irrigation": IRR})
    assert r.status_code == 200 and r.json()["supported"][0]["code"] == "water_recorded" and "खेत स्थिरता" in r.json()["title"]
    assert c.post("/api/passport/build", json={}).status_code == 200


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(); print("ok", n)
