"""Machine safety check: every rule is reachable, the worst warning decides the level, text exists in en/te/hi, and the answer never claims to see hazards."""
import itertools, os, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["MOCK_MODE"] = "1"
os.environ["RATE_AGENT_PER_MIN"] = "1000"
from fastapi.testclient import TestClient
from app import safety as s
from app.main import app

c = TestClient(app)


def codes(machine, conds):
    return {w["code"] for w in s.check({"machine": machine, "conditions": list(conds)})["warnings"]}


def test_all_text_in_three_languages():
    for code, t in s.W.items():
        for lang in ("en", "te", "hi"):
            assert len(t[lang]) == 2 and all(x.strip() for x in t[lang]), (code, lang)
    assert re.search(r"[ఀ-౿]", s.W["children_near"]["te"][0]) and re.search(r"[ऀ-ॿ]", s.W["children_near"]["hi"][0])
    assert set(s.LV["en"]) == set(s.LV["te"]) == set(s.LV["hi"]) and set(s.NOTE) == {"en", "te", "hi"}


def test_every_rule_is_reachable():
    seen = set()
    for m in s.MACHINES:
        for n in (1, 2):
            for combo in itertools.combinations(s.CODES, n):
                seen |= codes(m, combo)
    assert seen == set(s.W), "unreachable: %s, unknown: %s" % (set(s.W) - seen, seen - set(s.W))


def test_every_ticked_condition_matters_somewhere():
    for cond in s.CODES:
        assert any(codes(m, [cond]) or any(codes(m, [cond, o]) - codes(m, [o]) for o in s.CODES) for m in s.MACHINES), cond


def test_levels_and_ordering():
    r = s.check({"machine": "tractor", "conditions": ["slope_steep", "ground_wet", "children_near", "no_rops_belt", "night", "road_crossing", "hot_midday"]})
    assert r["level"] == "stop" and r["counts"]["stop"] == 2
    lv = [s.LEVELS[w["level"]] for w in r["warnings"]]
    assert lv == sorted(lv, reverse=True), "worst first"
    assert s.check({"machine": "pump", "conditions": []})["level"] == "ok"
    assert s.check({"machine": "tractor", "conditions": ["tired"]})["level"] == "high"
    assert s.check({"machine": "tractor", "conditions": ["hot_midday"]})["level"] == "caution"
    assert s.check({"machine": "tractor", "conditions": ["slope_steep"]})["level"] == "caution"


def test_key_safety_rules():
    assert "steep_wet_roll" in codes("tractor", ["slope_steep", "ground_wet"]) and "steep_wet_roll" not in codes("sprayer", ["slope_steep", "ground_wet"])
    assert codes("tractor", ["power_lines", "implement_raised"]) == {"power_raised"}
    assert "reverse_people" in codes("trailer", ["reversing", "people_near"])
    assert "pto_guard_missing" in codes("thresher", ["pto_guard_missing"]) and "pto_guard_missing" not in codes("sprayer", ["pto_guard_missing"])
    assert s.check({"machine": "sprayer", "conditions": ["strong_wind"]})["level"] == "high"
    assert s.check({"machine": "tractor", "conditions": ["unwell_or_drowsy"]})["level"] == "stop"
    assert s.check({"machine": "tractor", "conditions": ["riders"]})["level"] == "stop"
    assert "no_rops_belt" in codes("tractor", ["no_rops_belt"]) and not codes("pump", ["no_rops_belt"])
    r = s.check({"machine": "tractor", "conditions": ["children_near", "reversing", "people_near", "night", "road_crossing"]})
    assert r["collision_warnings"] >= 2


def test_honest_note_and_no_chemicals():
    for lang in ("en", "te", "hi"):
        r = s.check({"machine": "tractor", "conditions": ["children_near"]}, lang)
        assert r["note"] == s.NOTE[lang] and r["basis"].startswith("operator-reported")
    en = " ".join(" ".join(v["en"]) for v in s.W.values()).lower() + s.NOTE["en"].lower()
    assert "cannot see" in en and "cannot detect a collision" in en
    assert not re.search(r"\b(mg|ml|kg/ha|litre per|dose|dosage|insecticide|pesticide|fungicide)\b", en)


def test_input_handling():
    r = s.check({"machine": "Tractor", "conditions": ["night", "night", "not_a_code", 7]})
    assert r["reported"] == 1 and "not_a_code" in r["ignored"]
    assert s.check({"machine": "tractor", "conditions": "junk"})["level"] == "ok"
    try: s.check({"machine": "rocket"}); assert False
    except ValueError: pass
    assert len(s.check({"machine": "tractor", "conditions": ["night"] * 500})["warnings"]) <= 3


def test_endpoint():
    r = c.post("/api/safety/check", json={"machine": "tractor", "conditions": ["children_near"], "lang": "hi"})
    assert r.status_code == 200 and r.json()["level"] == "stop" and r.json()["warnings"][0]["text"] == s.W["children_near"]["hi"][0]
    assert c.post("/api/safety/check", json={"machine": "x"}).status_code == 400
    assert c.post("/api/safety/check", json={}).status_code == 400


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(); print("ok", n)
