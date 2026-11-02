"""Crop rotation simulator and knowledge graph: rules are explainable, sources are labelled, nothing is invented."""
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["MOCK_MODE"] = "1"
from fastapi.testclient import TestClient
from app import kg, rotation, tools
from app.main import app

c = TestClient(app)


def test_same_crop_is_penalised_and_legume_after_cereal_rewarded():
    r = rotation.simulate({"history": ["paddy"], "scenarios": [["paddy"], ["groundnut"]], "soil": "other"})
    by = {s["ids"][0]: s for s in r["scenarios"]}
    assert by["paddy"]["total_points"] < 0 < by["groundnut"]["total_points"]
    assert any("same pests" in x["reason"] for x in by["paddy"]["steps"][0]["reasons"])
    assert r["scenarios"][0]["ids"] == ["groundnut"], "best scenario comes first"


def test_shared_problems_come_from_the_problem_table():
    assert "Leaf curl virus (spread by whitefly)" in rotation.shared_problems("cotton", "tomato")
    assert rotation.shared_problems("paddy", "groundnut") == []
    r = rotation.simulate({"history": ["cotton"], "scenarios": [["tomato"]]})
    assert any("share" in x["reason"] for x in r["scenarios"][0]["steps"][0]["reasons"])


def test_sequences_unknown_crops_and_limits():
    r = rotation.simulate({"history": ["cotton", "xyz"], "scenarios": [["groundnut", "maize"], ["nonsense"], ["cotton"] * 9]}, "te")
    assert len(r["scenarios"]) == 2 and r["unrecognised"], "unknown crop reported, not guessed"
    assert max(len(s["ids"]) for s in r["scenarios"]) == rotation.MAX_STEPS
    assert r["reviewed_by_agronomist"] is False
    assert "yield" in rotation.simulate({})["basis"].lower(), "must say it is not a yield forecast"


def test_off_season_and_soil_points():
    r = rotation.simulate({"history": [], "scenarios": [["cotton"]], "soil": "sandy", "season": "rabi"})
    pts = {x["points"] for x in r["scenarios"][0]["steps"][0]["reasons"]}
    assert rotation.OFF_SEASON in pts and rotation.SOIL_CAUTION in pts


def test_rotation_tool_and_endpoint():
    out = tools.run_tool("rotation_compare", {"previous_crop": "cotton", "soil": "black"})
    assert out["ranking"] and "error" not in out
    assert "error" in tools.run_tool("rotation_compare", {"previous_crop": "zzz"})
    j = c.post("/api/rotation/simulate", json={"history": ["groundnut"], "soil": "black", "lang": "hi"}).json()
    assert j["scenarios"] and j["history"] == ["मूंगफली"]


def test_graph_every_edge_has_source_and_is_unreviewed():
    assert len(kg.NODES) > 50 and len(kg.EDGES) > 100
    assert all(e["source"] in ("problems.json", "rotation.json") and e["reviewed"] is False and e["src"] in kg.NODES and e["dst"] in kg.NODES for e in kg.EDGES)
    blob = " ".join(n["label"] + " " + str(n.get("looks_like", "")) for n in kg.NODES.values()).lower()
    for bad in ("mg/l", "ml per", "per litre", "chlorpyrifos", "imidacloprid", "mancozeb"):
        assert bad not in blob, "no pesticide names or doses"


def test_graph_search_and_neighbors():
    assert kg.find("groundnut tikka spots") == "problem:groundnut-leafspot"
    assert kg.find("tomato blight").startswith("problem:tomato")
    assert kg.find("zzzz qqq") is None
    g = kg.neighbors("problem:groundnut-leafspot", "te")
    assert {n["kind"] for n in g["nodes"]} >= {"crop", "problem", "condition", "practice"}
    assert g["reviewed_by_agronomist"] is False
    assert kg.neighbors("nope")["error"]


def test_graph_endpoints():
    j = c.get("/api/kg/node", params={"q": "cotton whitefly", "lang": "en"}).json()
    assert j["center"] == "problem:cotton-leafcurl" and j["edges"]
    assert c.get("/api/kg/node", params={"q": "zzzz"}).status_code == 404
    assert c.get("/api/kg/crops").json()["crops"]
    t = tools.run_tool("crop_knowledge", {"query": "late blight"})
    assert t["links"] and all("source_file" in x for x in t["links"])


if __name__ == "__main__":
    for k, v in list(globals().items()):
        if k.startswith("test_"):
            v()
            print("ok", k)
