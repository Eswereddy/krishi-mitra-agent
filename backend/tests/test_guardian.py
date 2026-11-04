"""Machine Guardian: baseline comparison on SYNTHETIC engine-like sounds (not real machines). No false alarm across seeds, each fault maps to its own pattern,
quality gates, no baseline -> no sound claim, symptom urgency, three languages, no chemicals, endpoint."""
import json, os, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["MOCK_MODE"] = "1"
os.environ["RATE_AGENT_PER_MIN"] = "1000"
import numpy as np
from fastapi.testclient import TestClient
from app import guardian as g, guardian_dsp as d
from app.main import app
from synth_engine import engine

c = TestClient(app)
BASE = d.features(engine(seed=1))


def run(sig, base=BASE, syms=(), lang="en", machine="tractor"):
    f = d.features(sig)
    return g.analyze(f, d.quality(sig, 8000), base, machine, list(syms), lang)


def pats(r):
    return [p["code"] for p in r["patterns"]]


def pcm(x):
    return (np.clip(x, -1, 1) * 32767).astype("<i2").tobytes()


def test_no_false_alarm_on_healthy_recordings():
    for seed in range(2, 12):
        for noise in (0.02, 0.04):
            r = run(engine(seed=seed, noise=noise))
            assert r["state"] == "nothing_found" and r["level"] == "ok" and not r["patterns"], (seed, noise, r["patterns"], r["measurements"])


def test_gain_change_is_not_a_fault():
    for gain in (0.3, 0.6, 1.0):
        assert run(engine(seed=3, gain=gain))["state"] == "nothing_found", gain


def test_each_fault_maps_to_its_pattern():
    assert pats(run(engine(seed=5, wobble=0.12))) == ["unsteady_rate"]
    assert "irregular_pulses" in pats(run(engine(seed=6, misfire_every=4)))
    assert pats(run(engine(seed=7, knock=10))) == ["knock_like"]
    assert pats(run(engine(seed=8, whine=0.06))) == ["whine_squeal"]
    assert pats(run(engine(seed=9, rattle=0.15))) == ["rattle_hiss"]


def test_faults_are_found_for_other_seeds():
    for s in range(20, 25):
        assert "knock_like" in pats(run(engine(seed=s, knock=10))), s
        assert "whine_squeal" in pats(run(engine(seed=s, whine=0.06))), s
        assert "unsteady_rate" in pats(run(engine(seed=s, wobble=0.12))), s


def test_urgency_levels():
    assert run(engine(seed=5, wobble=0.12))["level"] == "monitor"
    assert run(engine(seed=7, knock=10))["level"] == "soon"
    assert run(engine(seed=7, knock=10), syms=["loss_of_power"])["level"] == "stop_now"
    assert run(engine(seed=2), syms=["oil_light"])["level"] == "stop_now"
    assert run(engine(seed=2), syms=["smoke_black"])["level"] == "soon"


def test_speed_mismatch_refuses_to_compare():
    r = run(engine(seed=10, f0=78))
    assert r["state"] == "unreliable" and not r["patterns"] and r["state_note"]


def test_no_baseline_makes_no_sound_claim():
    r = run(engine(seed=7, knock=10), base=None)
    assert r["state"] == "no_baseline" and not r["patterns"] and r["measurements"]
    assert run(engine(seed=7, knock=10), base=None, syms=["oil_light"])["level"] == "stop_now"


def test_quality_gates():
    short = engine(seed=1, secs=2)
    assert run(short)["state"] == "bad" and "short" in d.quality(short, 8000)
    quiet = engine(seed=1) * 0.0005
    assert "quiet" in d.quality(quiet, 8000)
    assert "clipped" in d.quality(np.clip(engine(seed=1) * 40, -1, 1), 8000)
    r = run(np.zeros(8000 * 6))
    assert r["level"] == "bad" and r["recording_notes"] and not r["patterns"]


def test_text_three_languages_and_no_chemicals():
    for lang in ("en", "te", "hi"):
        r = run(engine(seed=7, knock=10), lang=lang, syms=["smoke_black"])
        assert r["note"] and r["mechanic"] and r["patterns"][0]["checks"] and r["symptoms"][0]["text"]
        assert r["validated"] is False
    assert re.search(r"[ఀ-౿]", run(engine(seed=7, knock=10), lang="te")["title"] + run(engine(seed=7, knock=10), lang="te")["patterns"][0]["title"])
    blob = json.dumps({"P": g.P, "U": g.U, "NOTE": g.NOTE}, ensure_ascii=False).lower()
    for w in ("pesticide", "insecticide", "fungicide", "herbicide", "mg/", "ml/"):
        assert w not in blob, w
    for p in g.P.values():
        assert set(p) == {"en", "te", "hi"} and all(len(v[1]) <= 3 and v[2] for v in p.values())


def test_causes_are_possibilities_and_note_is_honest():
    n = g.NOTE["en"].lower()
    assert "not a diagnosis" in n and "no trained model" in n and "not been tested on real machines" in n


def test_endpoint():
    sig = engine(seed=7, knock=10)
    r = c.post("/api/guardian/analyze", files={"pcm": ("a.pcm", pcm(sig))}, data={"machine": "pump", "symptoms": json.dumps(["leak"]), "baseline": json.dumps(BASE), "lang": "en"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["machine"] == "pump" and [p["code"] for p in j["patterns"]] == ["knock_like"] and j["symptoms"][0]["code"] == "leak"
    f = c.post("/api/guardian/analyze", files={"pcm": ("a.pcm", pcm(engine(seed=2)))}, data={}).json()["features"]
    r2 = c.post("/api/guardian/analyze", files={"pcm": ("a.pcm", pcm(engine(seed=3)))}, data={"baseline": json.dumps(f)}).json()
    assert r2["state"] == "nothing_found"  # features returned by the server work as a baseline
    r = c.post("/api/guardian/analyze", files={"pcm": ("a.pcm", pcm(sig))}, data={"baseline": "{bad"})
    assert r.status_code == 400
    r = c.post("/api/guardian/analyze", files={"pcm": ("a.pcm", b"\0\0")}, data={})
    assert r.status_code == 400
    r = c.post("/api/guardian/analyze", files={"pcm": ("a.pcm", pcm(sig))}, data={"baseline": json.dumps({"f0_hz": 1})})
    assert r.status_code == 400


if __name__ == "__main__":
    for n, f in sorted(globals().items()):
        if n.startswith("test_"):
            f()
            print("ok", n)
