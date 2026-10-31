"""Offline tests for Farm Doctor evidence (photo quality, reliability, escalation, safe steps).
Run from backend/: python tests/test_doctor.py"""
import io
import os
os.environ["CACHE_TTL_S"] = "0"
os.environ["MOCK_MODE"] = "1"
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import httpx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402
import test_meta_extras as base  # noqa: E402
from app import doctor, meta_models as mm  # noqa: E402
from app.main import app  # noqa: E402

GOOD_Q = {"brightness": 120, "sharpness": 20.0, "issues": [], "ok": True}


def res(pct, found=True, leaf=True, confs=(0.9,)):
    band = "none" if not found else "mild" if pct < 5 else "moderate" if pct < 25 else "severe"
    return {"found": found, "severity_pct": pct if found else 0.0, "band": band, "leaf_found": leaf,
            "spots": [{"box": [0, 0, 1, 1], "confidence": c} for c in confs] if found else []}


def test_photo_quality_flags_dark_bright_blurry_small():
    assert doctor.photo_quality(Image.open(io.BytesIO(base._photo())))["ok"]
    dark = doctor.photo_quality(Image.new("RGB", (400, 300), (5, 5, 5)))
    assert "dark" in dark["issues"] and "blurry" in dark["issues"]
    assert "bright" in doctor.photo_quality(Image.new("RGB", (400, 300), (250, 250, 250)))["issues"]
    assert "small" in doctor.photo_quality(Image.new("RGB", (100, 100), (90, 90, 90)))["issues"]
    assert "blurry" in doctor.photo_quality(Image.new("RGB", (400, 300), (60, 140, 60)))["issues"]       # flat = no detail
    from PIL import ImageFilter
    sharp = Image.open(io.BytesIO(base._photo()))
    assert doctor.photo_quality(sharp)["sharpness"] > 20 and "blurry" in doctor.photo_quality(sharp.filter(ImageFilter.GaussianBlur(6)))["issues"]


def test_reliability_levels_and_reasons():
    a = doctor.assess(res(12.0), GOOD_Q)
    assert a["reliability"] == "clear" and a["reasons"] == [] and not a["escalation"]["needed"] and a["confidence"] == {"lowest": 0.9, "mean": 0.9, "spots_with_confidence": 1}
    u = doctor.assess(res(12.0, confs=(0.5, 0.3)), GOOD_Q)
    assert u["reliability"] == "uncertain" and {"low_confidence", "some_spots_doubtful"} <= set(u["reasons"]) and u["escalation"] == {"needed": True, "reasons": ["not_reliable"]}
    assert "near_band_edge" in doctor.assess(res(24.0), GOOD_Q)["reasons"] and "near_band_edge" in doctor.assess(res(5.9), GOOD_Q)["reasons"]
    assert "leaf_not_found" in doctor.assess(res(12.0, leaf=False), GOOD_Q)["reasons"]
    bad = doctor.assess(res(12.0), dict(GOOD_Q, issues=["blurry"], ok=False))
    assert bad["reliability"] == "retake" and "photo_blurry" in bad["reasons"] and bad["escalation"]["needed"]
    nothing = doctor.assess(res(0, found=False, leaf=False), GOOD_Q)
    assert nothing["reliability"] == "retake" and nothing["reasons"] == ["nothing_recognised"] and not nothing["escalation"]["needed"]
    healthy = doctor.assess(res(0, found=False, leaf=True), GOOD_Q)
    assert healthy["reliability"] == "clear" and not healthy["escalation"]["needed"]


def test_severe_damage_escalates_even_when_clear():
    a = doctor.assess(res(40.0), GOOD_Q)
    assert a["reliability"] == "clear" and a["escalation"] == {"needed": True, "reasons": ["severe_damage"]}
    both = doctor.assess(res(40.0, confs=(0.4,)), GOOD_Q)
    assert both["escalation"]["reasons"] == ["severe_damage", "not_reliable"]


def test_steps_are_safe_complete_and_localized():
    for r, rel in ((res(3.0), "clear"), (res(12.0), "clear"), (res(40.0), "clear"), (res(12.0), "uncertain"), (res(0, found=False), "clear"), (res(12.0), "retake")):
        codes = doctor.step_codes(r, rel)
        assert codes[-1] == "no_spray_without_advice" and len(set(codes)) == len(codes)
        for lang in ("en", "te", "hi"):
            assert all(c in doctor.STEPS[lang] for c in codes)
    assert "send_to_expert" in doctor.step_codes(res(40.0), "clear") and "send_to_expert" in doctor.step_codes(res(12.0), "uncertain")
    assert "send_to_expert" not in doctor.step_codes(res(3.0), "clear") and doctor.step_codes(res(12.0), "retake")[0] == "retake_light"
    for lang, table in doctor.STEPS.items():
        for code, text in table.items():
            assert not any(w in text.lower() for w in ("pesticide", "fungicide", "insecticide", "mg/", "ml/", "kg/ha")) or code == "no_spray_without_advice", (lang, code)
    assert set(doctor.STEPS["en"]) == set(doctor.STEPS["te"]) == set(doctor.STEPS["hi"])
    assert set(doctor.REASONS["en"]) == set(doctor.REASONS["te"]) == set(doctor.REASONS["hi"])
    assert set(doctor.ESCALATION["en"]) == set(doctor.ESCALATION["hi"])


def test_endpoint_returns_evidence_in_the_farmers_language():
    c = TestClient(app)

    def handler(req: httpx.Request):
        prompt = __import__("json").loads(req.content)["input"][0]["content"][0]["text"]
        text = base.LESIONS if prompt == "diseased leaf spot" else base.LEAF
        return httpx.Response(200, text=f"data: {__import__('json').dumps({'type': 'response.output_text.delta', 'delta': text})}\n\n")
    base._transport(handler)
    os.environ["MODEL_API_KEY"] = "k"
    try:
        j = c.post("/api/leaf-scan", files={"image": ("a.jpg", base._photo(), "image/jpeg")}, data={"lang": "te"}).json()
        assert j["reliability"] == "clear" and j["escalation"]["needed"] is False and j["needs_expert"] is False
        assert j["confidence"]["mean"] == 0.9 and j["photo"]["ok"] and j["steps"][-1]["code"] == "no_spray_without_advice"
        assert j["steps"][0]["text"] == doctor.STEPS["te"]["remove_leaves"] and j["overlay"].startswith("data:image/jpeg")
        e = c.post("/api/leaf-scan", files={"image": ("a.jpg", base._photo(), "image/jpeg")}).json()
        assert e["steps"][0]["text"] == doctor.STEPS["en"]["remove_leaves"]                      # default language
        flat = io.BytesIO(); Image.new("RGB", (400, 300), (60, 140, 60)).save(flat, "JPEG")
        r = c.post("/api/leaf-scan", files={"image": ("a.jpg", flat.getvalue(), "image/jpeg")}).json()
        assert r["reliability"] == "retake" and r["needs_expert"] is True and r["steps"][0]["code"] == "retake_light"
        assert any(x["code"] == "photo_blurry" for x in r["reason_texts"])
    finally:
        os.environ.pop("MODEL_API_KEY", None)
        mm._TRANSPORT = None


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok", fn.__name__)
    print(len(fns), "passed")
