"""Research assistant (grounded, cited, honest when nothing matches) and field report generator."""
import asyncio, io, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["MOCK_MODE"] = "1"
from fastapi.testclient import TestClient
from app import config, fieldreport, meta_client, research
from app.main import app

c = TestClient(app)
DOC = ("Groundnut leaf spot is favoured by humid weather. Remove crop residue after harvest to reduce the disease. "
       "A spacing of 30 cm between rows is recommended for bunch types. Irrigate at pegging and pod development. ") * 3


def test_ingest_text_html_and_pdf():
    r = research.ingest(DOC.encode(), "icar.txt")
    assert r["count"] >= 1 and r["chunks"][0]["title"] == "icar.txt"
    h = research.ingest(b"<html><script>alert(1)</script><p>" + DOC.encode() + b"</p></html>", "a.html")
    assert "alert" not in h["chunks"][0]["text"] and "<p>" not in h["chunks"][0]["text"]
    from pypdf import PdfWriter
    w = PdfWriter(); w.add_blank_page(200, 200); buf = io.BytesIO(); w.write(buf)
    assert "error" in research.ingest(buf.getvalue(), "scan.pdf"), "a PDF without text must say so"
    assert "error" in research.ingest(b"", "empty.txt")
    assert "error" in research.ingest(b"a" * (research.MAX_UPLOAD + 1), "big.txt")


def test_search_ranks_relevant_passage_and_returns_nothing_for_unrelated():
    chunks = [{"title": "A", "page": 1, "text": "Spacing of 30 cm between rows is recommended for bunch groundnut."}, {"title": "B", "page": 2, "text": "Marketing of cotton lint in Telangana mandis."}]
    assert research.search("row spacing groundnut", chunks)[0]["title"] == "A"
    assert research.search("quantum computing", chunks) == [] and research.search("", chunks) == [] and research.search("x", []) == []


def test_check_requires_real_citations_and_numbers_from_passages():
    p = [{"n": 1, "text": "Spacing of 30 cm between rows."}]
    assert research.check("Use 30 cm spacing [1].", p)["grounded"]
    assert not research.check("Use 45 cm spacing [1].", p)["grounded"]
    assert research.check("Use 30 cm [2].", p)["bad_citations"] == [2]
    assert not research.check("Use spacing.", p)["grounded"], "no citation means not grounded"


def test_ask_extract_mode_no_docs_and_no_match():
    chunks = research.ingest(DOC.encode(), "icar.txt")["chunks"]
    a = asyncio.run(research.ask("what spacing between rows for groundnut?", chunks, "en"))
    assert a["mode"] == "extract" and "30 cm" in a["answer"] and a["passages"][0]["title"] == "icar.txt" and a["grounded"]
    assert asyncio.run(research.ask("tractor loan interest", chunks, "en"))["mode"] == "no-match"
    assert asyncio.run(research.ask("anything", [], "te"))["mode"] == "no-documents"
    assert asyncio.run(research.ask("spacing", [{"text": 5}, "junk", None], "en"))["mode"] in ("no-documents", "no-match")


def test_model_answer_is_flagged_when_ungrounded(monkeypatch=None):
    chunks = research.ingest(DOC.encode(), "icar.txt")["chunks"]
    config.MOCK_MODE = False
    orig = meta_client.chat
    try:
        async def bad(msgs, *a, **k): return "Use 45 cm spacing [1]."
        meta_client.chat = bad
        a = asyncio.run(research.ask("what spacing between rows for groundnut?", chunks, "en"))
        assert a["mode"] == "model" and not a["grounded"] and "Warning" in a["answer"]
        async def good(msgs, *a, **k): return "Rows are spaced 30 cm apart [1]."
        meta_client.chat = good
        assert asyncio.run(research.ask("what spacing between rows for groundnut?", chunks, "en"))["grounded"]
    finally:
        meta_client.chat = orig
        config.MOCK_MODE = True


def test_research_endpoints():
    r = c.post("/api/research/ingest", files={"document": ("icar.txt", DOC.encode(), "text/plain")})
    assert r.status_code == 200 and r.json()["chunks"]
    assert c.post("/api/research/ingest", files={"document": ("e.txt", b"", "text/plain")}).status_code == 422
    a = c.post("/api/research/ask", json={"question": "row spacing groundnut", "chunks": r.json()["chunks"], "lang": "en"})
    assert a.status_code == 200 and a.json()["passages"]
    assert c.post("/api/research/ask", json={"question": "  "}).status_code == 400


def run(p, lang="en"):
    return asyncio.run(fieldreport.build(p, lang))


def test_field_report_extracts_and_computes_urgency():
    r = run({"profile": {"crop": "groundnut", "place": "Kurnool"}, "notes": [{"text": "Brown spots on leaves after rain, spreading fast. I irrigated and applied urea.", "source": "voice"}],
             "scan": {"severity_pct": 12, "band": "moderate", "reliability": "clear"}})
    assert {"spots_on_leaves", "after_rain", "spreading_fast"} <= set(r["symptoms"]) and {"irrigation", "fertiliser"} <= set(r["activities"])
    assert r["urgency"] == "high" and r["extraction"] == "rules" and r["notes"][0]["source"] == "voice"
    assert r["possible_matches"] and "pesticide or dose" in r["summary_text"] and r["scan"]["method"].startswith("SAM")
    blob = str(r).lower()
    assert "chlorpyrifos" not in blob and "ml per" not in blob


def test_field_report_languages_and_empty_and_junk():
    assert run({}, "te")["error"]
    t = run({"notes": [{"text": "ఆకులపై మచ్చలు, పసుపు రంగు"}], "profile": {"crop": "chilli"}}, "te")
    assert "spots_on_leaves" in t["symptoms"] and "పొలం నివేదిక" in t["summary_text"]
    j = run({"notes": [{"text": "x" * 5000}, 7, None, {"text": "\x00\x01 weeds"}], "profile": "bad", "twin": 3, "scan": []}, "hi")
    assert len(j["notes"][0]["text"]) == fieldreport.NOTE_LEN and "weeding" in j["activities"]
    assert len(run({"notes": [{"text": "spots"}] * 50})["notes"]) == fieldreport.MAX_NOTES


def test_field_report_model_output_is_whitelisted():
    config.MOCK_MODE = False
    orig = meta_client.chat
    try:
        async def evil(msgs, *a, **k): return 'Sure {"symptoms": ["wilting", "DROP TABLE", "apply_chlorpyrifos"], "activities": ["spraying", "hack"], "english": "plants drooping"}'
        meta_client.chat = evil
        r = run({"notes": [{"text": "మొక్కలు వాడిపోతున్నాయి"}], "profile": {"crop": "tomato"}})
        assert r["extraction"] == "model" and "wilting" in r["symptoms"] and "spraying" in r["activities"]
        assert not {"DROP TABLE", "apply_chlorpyrifos", "hack"} & (set(r["symptoms"]) | set(r["activities"]))
        async def boom(msgs, *a, **k): raise RuntimeError("down")
        meta_client.chat = boom
        assert run({"notes": [{"text": "wilting plants"}]})["extraction"] == "rules", "model failure falls back to rules"
    finally:
        meta_client.chat = orig
        config.MOCK_MODE = True


def test_field_report_endpoint():
    ok = c.post("/api/fieldreport/build", json={"notes": [{"text": "yellow leaves"}], "profile": {"crop": "maize"}, "lang": "en"})
    assert ok.status_code == 200 and ok.json()["id"].startswith("FR-")
    assert c.post("/api/fieldreport/build", json={}).status_code == 400


if __name__ == "__main__":
    for k, v in list(globals().items()):
        if k.startswith("test_"):
            v()
            print("ok", k)
