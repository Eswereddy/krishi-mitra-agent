# Demo video script (3 minutes) and submission checklist

## Before recording
- Use the deployed Render URL (open it once first: the free plan sleeps). Record on a phone for the "farmer" feel.
- Confirm `/api/health` shows `"mock": false`. Never record in mock mode.
- Set `DATA_GOV_API_KEY` so mandi prices are live. If they are sample data, say so in the video.
- Fill the farmer profile first (state, district, "I own farmland", main crop).
- Do one full dry run. Keep a typed-question fallback ready in case a voice take fails.

## Script
| Time | Show | Say (short) |
|---|---|---|
| 0:00-0:20 | Farmer in a field / phone in hand | "Small farmers cannot easily find prices, weather, schemes or expert help, and most apps need typing in English. Krishi Mitra works by voice in Telugu, Hindi and English." |
| 0:20-0:50 | Tap mic, ask in Telugu: "వరి ధర ఎంత? నాకు ఏ పథకాలు వస్తాయి?" | "Muse Spark Open on Baseten transcribes the speech and the agent decides what to do." |
| 0:50-1:30 | Answer + **Agent steps** panel (mandi, schemes, weather) + ✅ verified | "It calls tools for live mandi prices, weather and scheme eligibility. Every figure must come from a tool result, so it cannot make up numbers." |
| 1:30-2:00 | Send a crop photo | "Muse Spark vision looks at the leaf, says what it may be, how sure it is, and safe next steps. No pesticide doses. If unsure it sends the farmer to the Kisan Call Centre." |
| 2:00-2:20 | Switch to Hindi, ask a question; tap 🔊 Listen | "Same agent in Hindi and English, and it can read the answer aloud." |
| 2:20-2:45 | Show the ⚠️ case (ask something the tools cannot answer, or show the test) | "If a figure cannot be verified, the farmer sees a warning, not a confident wrong answer. Verification is plain code outside the model." |
| 2:45-3:00 | Repo page + README | "Built during the hackathon on open-weight Muse Spark Open. Open source on GitHub." |

## What to state clearly (judges look for this)
- New work only: the repository was created on Oct 27-28, 2026; every commit is during the event.
- Open weights: Muse Spark Open (`meta-models/muse-spark-open`) served on Baseten.
- Data honesty: live prices only with the data.gov.in key; scheme info is indicative.

## Submission checklist (deadline Nov 4, 9:00 PM ET = Nov 5, 6:30 AM IST; submit by Nov 3)
- [ ] Repo is **public**, README is clear, no secrets committed (`git log -p | grep -i key` returns nothing real)
- [ ] 3-minute demo video uploaded, link opens when logged out
- [ ] Live URL works (open it right before submitting)
- [ ] Track: Indie Developer. Everyone who worked on it is listed (solo)
- [ ] Open-weights prize: ask Baseten/Discord to flag the project as running on Muse Spark Open
- [ ] Optional: post the demo on X and add the post link (Most Viral prize)
- [ ] Revoke any API key that was ever pasted in a chat or screenshot
