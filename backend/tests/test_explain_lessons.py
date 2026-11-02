"""Explainable answers, learning coach and follow-ups."""
import os, sys
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["MOCK_MODE"] = "1"
from fastapi.testclient import TestClient
from app import explain, kg, lessons, memory, tools
from app.main import app

c = TestClient(app)
STEPS = [{"tool": n, "args": a, "result": tools.run_tool(n, a)} for n, a in
         [("get_mandi_price", {"commodity": "Paddy", "district": "Kurnool"}), ("get_msp", {"commodity": "paddy"})]]
PRICE = int(STEPS[0]["result"]["results"][0]["modal_price_per_quintal"])


def test_explain_labels_sample_vs_indicative_and_traces_figures():
    e = explain.build(f"Paddy modal price is Rs {PRICE} per quintal.", STEPS, "en")
    kinds = {x["tool"]: x["kind"] for x in e["evidence"]}
    assert kinds["get_mandi_price"] == "sample" and kinds["get_msp"] == "indicative"
    tr = {t["figure"]: t for t in e["figure_trace"]}
    assert tr[PRICE]["tool"] == "get_mandi_price" and "modal_price" in tr[PRICE]["field"]
    assert e["checks"]["passed"] and e["computed_in_code"] and e["could_change"]


def test_explain_flags_invented_figures_and_no_tool_answers():
    e = explain.build(f"Price is Rs {PRICE} and will reach 9999 soon.", STEPS, "en")
    assert not e["checks"]["passed"] and "9999" in e["checks"]["unverified"]
    assert any(t["figure"] == 9999 and t["tool"] is None for t in e["figure_trace"])
    n = explain.build("Keep fields clean.", [], "te")
    assert n["evidence"] == [] and n["no_tool_note"]
    f = explain.build("x", [{"tool": "get_weather", "args": {}, "result": {"error": "down"}}], "hi")
    assert f["evidence"][0]["kind"] == "failed"


def test_explain_endpoint_is_stateless_and_survives_junk():
    j = c.post("/api/explain", json={"answer": f"Rs {PRICE}", "steps": STEPS, "lang": "te"}).json()
    assert j["evidence"][0]["title"] == "మండి ధర"
    assert c.post("/api/explain", json={"answer": 5, "steps": "bad", "lang": "zz"}).status_code == 200
    assert c.post("/api/explain", json={"steps": [None, 3, {"tool": 7, "result": "x"}]}).status_code == 200


def test_level_from_history():
    assert lessons.level_from([])[0] == "beginner"
    assert lessons.level_from([{"score": 2, "total": 2}] * 2)[0] == "intermediate"
    assert lessons.level_from([{"score": 3, "total": 3}] * 5)[0] == "advanced"
    assert lessons.level_from([{"score": 0, "total": 3}] * 5)[0] == "beginner"
    assert lessons.level_from([{"score": 9, "total": 3}, "x", {"score": 1}])[0] == "beginner", "bad rows ignored"


def test_quiz_answers_are_correct_per_tables_and_options_distinct():
    for q in ["groundnut leaves spots", "tomato blight", "cotton whitefly", "paddy", "maize armyworm"]:
        for hist in ([], [{"score": 3, "total": 3}] * 4):
            r = lessons.build({"question": q, "history": hist}, "en")
            assert r["quiz"] and r["sections"]
            for z in r["quiz"]:
                assert len(set(z["options"])) == len(z["options"]) >= 3 and 0 <= z["answer_index"] < len(z["options"])
    r = lessons.build({"question": "groundnut leaf spot tikka"}, "en")
    q = next(z for z in r["quiz"] if z["id"].startswith("cond"))
    favoured = {kg.NODES[e["dst"]]["label"] for e in kg.EDGES if e["src"] == r["topic"]["id"] and e["rel"] == "favoured_by"}
    assert q["options"][q["answer_index"]] in favoured
    assert all(o not in favoured for i, o in enumerate(q["options"]) if i != q["answer_index"]), "distractors must not be linked to the problem"


def test_level_changes_lesson_size_and_language():
    b = lessons.build({"question": "groundnut leaf spot"}, "en")
    a = lessons.build({"question": "groundnut leaf spot", "history": [{"score": 3, "total": 3}] * 5}, "en")
    assert a["level"] == "advanced" and len(a["quiz"]) >= len(b["quiz"]) and len(a["sections"]) >= len(b["sections"])
    te = lessons.build({"question": "cotton"}, "te")
    assert te["topic"]["name"] and any("ఀ" <= ch <= "౿" for ch in te["quiz"][0]["q"])
    assert lessons.build({"question": "hello there"}, "en")["error"]
    assert c.post("/api/lessons/build", json={"question": "zzz"}).status_code == 404
    assert c.post("/api/lessons/build", json={"question": "rice blast", "lang": "hi"}).status_code == 200


def test_lesson_rotates_topic_for_a_crop():
    seen = {lessons.build({"profile": {"main_crop": "paddy"}, "history": [{"score": 1, "total": 2}] * n}, "en")["topic"]["id"] for n in range(6)}
    assert len(seen) >= 3


def test_followups_due_window_and_answered():
    recs = [{"id": "a", "date": "2026-10-20", "text": "Hold groundnut", "kind": "sell"}, {"id": "b", "date": "2026-11-01", "text": "fresh", "kind": "sell"},
            {"id": "c", "date": "2026-10-01", "text": "done one", "kind": "sell", "done": True}, {"id": "d", "date": "2026-08-01", "text": "too old", "kind": "sell"},
            {"id": "e", "date": "bad", "text": "x"}, "junk", {"id": "f", "date": "2026-10-29", "text": "spray day", "kind": "protect", "snoozed_until": "2026-11-05"}]
    out = memory.followups(recs, date(2026, 11, 2), "en")
    assert [x["id"] for x in out] == ["a"] and out[0]["age_days"] == 13 and "Hold groundnut" in out[0]["question"]
    assert memory.followups(None) == [] and len(memory.followups([{"id": str(i), "date": "2026-10-01", "text": "t", "kind": "sell"} for i in range(9)], date(2026, 11, 2))) == 3
    assert c.post("/api/memory/followups", json={"records": recs, "lang": "hi"}).status_code == 200


if __name__ == "__main__":
    for k, v in list(globals().items()):
        if k.startswith("test_"):
            v()
            print("ok", k)
