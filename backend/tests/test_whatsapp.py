"""Offline tests for the WhatsApp channel (no Meta account, no network). Run from backend/: python tests/test_whatsapp.py"""
import asyncio
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["MOCK_MODE"] = "1"
for k in ("WHATSAPP_APP_SECRET", "WHATSAPP_ALLOWED_NUMBERS", "WHATSAPP_ALLOW_UNSIGNED"):
    os.environ.pop(k, None)

from fastapi.testclient import TestClient  # noqa: E402

from app import main, meta_client, ratelimit, whatsapp  # noqa: E402

SENT, AUDIO, ASKED = [], [], []


def payload(*msgs):
    return {"entry": [{"changes": [{"value": {"messages": list(msgs)}}]}]}


def text_msg(mid, text, sender="919876543210"):
    return {"id": mid, "from": sender, "type": "text", "text": {"body": text}}


def setup():
    SENT.clear(); AUDIO.clear(); ASKED.clear()
    whatsapp._SEEN.clear(); whatsapp._SESSIONS.clear(); ratelimit._hits.clear()
    os.environ.pop("WHATSAPP_ALLOWED_NUMBERS", None)

    async def send_text(to, text): SENT.append((to, text))
    async def send_audio(to, mp3): AUDIO.append((to, mp3))
    async def mark_read(mid): pass
    async def fake_agent(text, use_open=False, lang="auto", profile=None, history=None, image=None, on_event=None):
        ASKED.append({"text": text, "profile": profile, "history": history, "image": image})
        return {"answer": "**Groundnut** ₹6,200 per quintal\n\n# Tip\nSell soon", "steps": [],
                "verification": {"passed": True, "unverified": [], "checked": 1}}
    whatsapp._send_text, whatsapp._send_audio, whatsapp._mark_read = send_text, send_audio, mark_read
    whatsapp.agent.run_agent = fake_agent
    whatsapp.ttsmod.synthesize = lambda text, lang: b"MP3DATA"


def run(msg):
    asyncio.run(whatsapp.handle_message(whatsapp.extract_messages(payload(msg))[0]))


def test_webhook_verification_handshake():
    os.environ["WHATSAPP_VERIFY_TOKEN"] = "s3cret"
    c = TestClient(main.app)
    ok = c.get("/webhook/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": "s3cret", "hub.challenge": "12345"})
    assert ok.status_code == 200 and ok.text == "12345"
    bad = c.get("/webhook/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": "nope", "hub.challenge": "1"})
    assert bad.status_code == 403


def test_signature_is_required_and_checked():
    body = json.dumps(payload()).encode()
    os.environ["WHATSAPP_APP_SECRET"] = "app-secret"
    good = "sha256=" + hmac.new(b"app-secret", body, hashlib.sha256).hexdigest()
    c = TestClient(main.app)
    assert c.post("/webhook/whatsapp", content=body, headers={"x-hub-signature-256": good}).status_code == 200
    assert c.post("/webhook/whatsapp", content=body, headers={"x-hub-signature-256": "sha256=bad"}).status_code == 403
    assert c.post("/webhook/whatsapp", content=body).status_code == 403
    del os.environ["WHATSAPP_APP_SECRET"]
    assert c.post("/webhook/whatsapp", content=body).status_code == 403          # no secret configured: rejected
    os.environ["WHATSAPP_ALLOW_UNSIGNED"] = "1"
    assert c.post("/webhook/whatsapp", content=body).status_code == 200          # explicit local-test opt-in
    del os.environ["WHATSAPP_ALLOW_UNSIGNED"]


def test_extract_messages_handles_text_audio_image_and_ignores_statuses():
    p = payload(text_msg("a", "hi"),
                {"id": "b", "from": "91", "type": "audio", "audio": {"id": "m1", "mime_type": "audio/ogg; codecs=opus"}},
                {"id": "c", "from": "91", "type": "image", "image": {"id": "m2", "mime_type": "image/jpeg", "caption": "leaf"}})
    p["entry"][0]["changes"].append({"value": {"statuses": [{"id": "x"}]}})
    msgs = whatsapp.extract_messages(p)
    assert [m["type"] for m in msgs] == ["text", "audio", "image"]
    assert msgs[2]["text"] == "leaf" and msgs[1]["media_id"] == "m1"


def test_text_question_gets_formatted_verified_reply_without_voice():
    setup()
    run(text_msg("t1", "groundnut price?"))
    to, reply = SENT[0]
    assert to == "919876543210" and "*Groundnut*" in reply and "**" not in reply and "# Tip" not in reply
    assert "All figures verified" in reply and not AUDIO


def test_duplicate_delivery_is_answered_once():
    setup()
    run(text_msg("dup", "price?")); run(text_msg("dup", "price?"))
    assert len(ASKED) == 1


def test_profile_commands_reach_the_agent_and_history_is_kept():
    setup()
    run(text_msg("c1", "/district Kurnool")); run(text_msg("c2", "/crop Groundnut")); run(text_msg("c3", "/land yes"))
    assert ASKED == [] and SENT[0][1] == "✓ district: Kurnool"
    run(text_msg("q1", "price today?"))
    assert ASKED[0]["profile"] == {"state": "Andhra Pradesh", "district": "Kurnool", "main_crop": "Groundnut", "owns_land": True}
    run(text_msg("q2", "and cotton?"))
    assert ASKED[1]["history"][0] == {"role": "user", "content": "price today?"}
    run(text_msg("c4", "/reset")); run(text_msg("q3", "price?"))
    assert ASKED[2]["history"] == [] and "district" not in ASKED[2]["profile"]


def test_allow_list_blocks_other_numbers():
    setup()
    os.environ["WHATSAPP_ALLOWED_NUMBERS"] = "+91 98765 43210, 15550001111"
    run(text_msg("a1", "hi", sender="919000000000"))
    assert not SENT and not ASKED
    run(text_msg("a2", "hi", sender="919876543210"))
    assert ASKED
    del os.environ["WHATSAPP_ALLOWED_NUMBERS"]


def test_voice_note_is_transcribed_answered_and_replied_with_voice():
    setup()
    async def fake_dl(mid, mime): return b"OGG", "audio/ogg"
    async def fake_tr(data, name, mime): return "వేరుశనగ ధర ఎంత?"
    whatsapp._download_media, meta_client.transcribe = fake_dl, fake_tr
    run({"id": "v1", "from": "919876543210", "type": "audio", "audio": {"id": "m1", "mime_type": "audio/ogg"}})
    assert ASKED[0]["text"] == "వేరుశనగ ధర ఎంత?"
    assert SENT[0][1].startswith("🎤 _వేరుశనగ ధర ఎంత?_") and AUDIO == [("919876543210", b"MP3DATA")]


def test_unclear_voice_note_asks_to_repeat_instead_of_guessing():
    setup()
    async def fake_dl(mid, mime): return b"OGG", "audio/ogg"
    async def fake_tr(data, name, mime): raise meta_client.AudioNotUnderstood("x")
    whatsapp._download_media, meta_client.transcribe = fake_dl, fake_tr
    run({"id": "v2", "from": "919876543210", "type": "audio", "audio": {"id": "m1"}})
    assert not ASKED and "voice" in SENT[0][1].lower()


def test_photo_goes_to_the_agent_with_caption_and_no_history():
    setup()
    async def fake_dl(mid, mime): return b"JPEGBYTES", "image/jpeg"
    whatsapp._download_media = fake_dl
    run({"id": "p1", "from": "919876543210", "type": "image", "image": {"id": "m2", "caption": "ఆకులు పసుపు"}})
    assert ASKED[0]["image"] == (b"JPEGBYTES", "image/jpeg") and ASKED[0]["text"] == "ఆకులు పసుపు"
    run({"id": "p2", "from": "919876543210", "type": "image", "image": {"id": "m3"}})
    assert "crop photo" in ASKED[1]["text"]


def test_rate_limit_per_sender_and_failures_are_polite():
    setup()
    for i in range(ratelimit.LIMITS["/api/agent"]):
        run(text_msg(f"r{i}", "price?"))
    n = len(ASKED)
    run(text_msg("rx", "price?"))
    assert len(ASKED) == n and "wait" in SENT[-1][1].lower()
    setup()
    async def boom(*a, **k): raise RuntimeError("model down")
    whatsapp.agent.run_agent = boom
    run(text_msg("f1", "price?"))
    assert "try again" in SENT[0][1].lower()


def test_long_replies_are_split_under_the_limit():
    parts = whatsapp.split_text(("word " * 300 + "\n\n") * 6, limit=1000)
    assert len(parts) > 1 and all(len(p) <= 1000 for p in parts)
    assert whatsapp.split_text("x" * 5000, limit=1000)[0] != ""


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
