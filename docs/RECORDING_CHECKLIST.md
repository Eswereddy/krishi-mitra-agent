# Recording checklist (do this on the last day)

## 1. Environment (30 minutes before)
- [ ] Open the live Render URL once to wake it (free plan sleeps). Reload until `/api/health` answers.
- [ ] `/api/health` shows `"mock": false`. **Never record in mock mode.**
- [ ] `DATA_GOV_API_KEY` set so India mandi prices are live. If a price is sample data, say so on camera.
- [ ] `EXPERT_CONTACTS` set to a real WhatsApp number you control, so the expert share opens a real chat.
- [ ] Run `python eval/suite_v2.py --live --out ../EVAL_V2.md` on the deployed backend. Commit the real numbers. Quote only those.
- [ ] Revoke and rotate any API key that was ever pasted in chat or a screenshot.

## 2. Test each beat once, off camera
- [ ] Telugu voice question gives a spoken answer with live steps and a "verified" tick.
- [ ] Leaf photos: one good (clear overlay), one blurry/dark (shows "retake"). Use **real** crop leaves, outdoors, daylight.
- [ ] Expert case builds, preview reads well in Telugu, WhatsApp opens with the text.
- [ ] Profile has village + crop + sowing date, so early warning and My field show real data. If no warning is active, pick a day/place that has one or say "all clear" honestly; do not fake it.
- [ ] Buyer compare: enter two offers (one asks an advance).
- [ ] Kenya + Kiswahili maize price (WFP/HDX) loads. If HDX is slow, skip the beat.
- [ ] Airplane mode: offline banner and saved brief open.

## 3. Recording
- [ ] Phone, portrait, do-not-disturb, battery above 50%, large font, screen recording with audio.
- [ ] Quiet room or outdoors with a clear voice. Read the script in `DEMO.md`; keep to 3:00 (judges stop at 3 minutes).
- [ ] Show the product, not slides: 25% of the score is the demo.
- [ ] Say once, clearly: open weights (Spark Open, Glimmer), which Meta model does which job (`docs/MODELS.md`), data stays on the phone.
- [ ] Do not claim anything you did not verify live (accuracy, languages, buyers verified, SAM accuracy).

## 4. Submission (deadline Nov 4, 9:00 PM ET = Nov 5, 6:30 AM IST; submit by Nov 3)
- [ ] Repo public, README clear, no secrets in history.
- [ ] Video uploaded; the link opens when logged out.
- [ ] Live URL works right before submitting.
- [ ] Track: Indie Developer. Mention bonus prizes you target: Best Open-Weights Build, Best Agentic Use-Case, Community Vote, Most Viral (post the demo on X).
- [ ] Attach: `docs/architecture.png`, `docs/MODELS.md`, `docs/TEST_REPORT.md`, `EVAL_V2.md`.
