"""WhatsApp channel in global mode. Run from backend/: python tests/test_whatsapp_global.py"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["MOCK_MODE"] = "1"
os.environ.pop("MODEL_API_KEY", None)
import test_whatsapp as base  # noqa: E402
from app import brief, meta_client, plan, whatsapp  # noqa: E402

run, setup, text_msg, SENT, ASKED, AUDIO = base.run, base.setup, base.text_msg, base.SENT, base.ASKED, base.AUDIO


def test_country_sowing_and_lang_commands():
    setup()
    run(text_msg("g1", "/district Nakuru")); run(text_msg("g2", "/country ke")); run(text_msg("g3", "/crop Maize"))
    run(text_msg("g4", "/sowing 2026-09-01")); run(text_msg("g5", "/lang sw"))
    assert [m[1] for m in SENT] == ["✓ district: Nakuru", "✓ country: Kenya (KES)", "✓ crop: Maize", "✓ sowing date: 2026-09-01", "✓ language: Swahili"]
    run(text_msg("g6", "Bei ya mahindi ni ngapi?"))
    assert ASKED[0]["profile"] == {"district": "Nakuru", "country": "KE", "main_crop": "Maize", "sowing_date": "2026-09-01"}   # no Indian state abroad
    run(text_msg("g7", "/country Brazil")); assert SENT[-1][1] == "✓ country: Brazil (BRL)"
    run(text_msg("g8", "/country other")); assert "OTHER" not in SENT[-1][1] and SENT[-1][1].startswith("✓ country:")
    run(text_msg("g9", "/country Atlantis")); assert "Unknown country" in SENT[-1][1]
    run(text_msg("g10", "/sowing yesterday")); assert "2026-09-01" in SENT[-1][1]
    run(text_msg("g11", "/lang xx")); assert "Languages:" in SENT[-1][1]
    base.ratelimit._hits.clear()
    run(text_msg("g12", "/reset")); run(text_msg("g13", "hi"))
    assert ASKED[-1]["profile"] == {"state": "Andhra Pradesh"}


def test_brief_and_plan_commands_pick_language_by_country():
    setup()
    seen = []

    async def fb(profile, code): seen.append(("brief", code)); return {"answer": "b", "steps": [], "verification": {"passed": True, "checked": 0}}
    async def fp(profile, code): seen.append(("plan", code)); return {"answer": "p", "steps": [], "verification": {"passed": True, "checked": 0}}
    ob, op = brief.build_brief, plan.build_plan
    brief.build_brief, plan.build_plan = fb, fp
    try:
        run(text_msg("b1", "/brief")); run(text_msg("b2", "/plan"))              # India default: Telugu
        run(text_msg("b3", "/country KE")); run(text_msg("b4", "/brief")); run(text_msg("b5", "/plan"))
        run(text_msg("b6", "/lang es")); run(text_msg("b7", "/plan")); run(text_msg("b8", "/brief fr")); run(text_msg("b9", "/week hi"))
    finally:
        brief.build_brief, plan.build_plan = ob, op
    assert seen == [("brief", "te"), ("plan", "te"), ("brief", "en"), ("plan", "en"), ("plan", "es"), ("brief", "fr"), ("plan", "hi")]


def test_voice_reply_uses_the_chosen_language_and_muse_voice_gets_the_hint():
    setup()
    langs = []
    whatsapp.ttsmod.synthesize = lambda text, lang: langs.append(lang) or b"MP3"

    async def fake_dl(mid, mime): return b"OGG", "audio/ogg"
    async def fake_tr(data, name, mime): return "Bei ya mahindi ni ngapi?"            # Latin text: detect() alone would say English
    whatsapp._download_media, meta_client.transcribe = fake_dl, fake_tr
    run(text_msg("v0", "/lang sw"))
    run({"id": "v1", "from": "919876543210", "type": "audio", "audio": {"id": "m1", "mime_type": "audio/ogg"}})
    assert langs == ["sw"] and ASKED[0]["text"] == "Bei ya mahindi ni ngapi?"

    os.environ["MODEL_API_KEY"] = "k"
    got = {}

    async def fake_wav(data): return b"WAV", "audio/wav"
    async def fake_asr(wav, languages): got["langs"] = languages; return "habari"
    ow, oa = meta_client._to_wav, whatsapp.mm.asr_transcribe
    meta_client._to_wav, whatsapp.mm.asr_transcribe = fake_wav, fake_asr
    try:
        assert asyncio.run(whatsapp._transcribe(b"x", "audio/ogg", "sw")) == "habari" and got["langs"][0] == "Swahili"
        async def boom(wav, languages): raise RuntimeError("down")
        whatsapp.mm.asr_transcribe = boom
        assert asyncio.run(whatsapp._transcribe(b"x", "audio/ogg", "sw")) == "Bei ya mahindi ni ngapi?"    # falls back to Spark Open
    finally:
        meta_client._to_wav, whatsapp.mm.asr_transcribe = ow, oa
        os.environ.pop("MODEL_API_KEY", None)


def test_help_mentions_the_global_commands():
    assert "/country" in whatsapp.HELP and "/sowing" in whatsapp.HELP and "/plan" in whatsapp.HELP


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok", fn.__name__)
    print(len(fns), "passed")
