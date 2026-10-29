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
| 0:20-0:55 | Tap **Talk** (voice mode). Ask in Telugu: "వేరుశనగ ఇప్పుడే అమ్మాలా లేక వేచి ఉండాలా?" Watch the **live steps** appear, then the answer is spoken | "Muse Spark Open on Baseten transcribes the speech. The agent decides which tools to call, and you can watch each step happen. It answers out loud, then listens again, hands-free." |
| 0:55-1:30 | Scroll the answer: price-trend chart, best markets, weather cards, ✓ verified + sources line | "Prices come from Agmarknet, weather from Open-Meteo. Every figure must come from a tool result, so it cannot make up numbers." |
| 1:30-2:00 | Take or drop a crop photo, add a voice question | "Muse Spark vision looks at the leaf, says what it may be and how sure it is, checks the weather for spraying. No pesticide doses. If unsure it shows the Kisan Call Centre call button." |
| 2:00-2:20 | Switch to Hindi, ask a question; tap 🔊 Listen | "Same agent in Hindi and English. If the phone has no Telugu voice, the server speaks for it." |
| 2:20-2:40 | Turn on airplane mode: offline banner, open a saved answer, tap Listen | "Rural networks drop. The app opens offline and saved answers still work." |
| 2:40-3:00 | Repo page + README | "Built during the hackathon on open-weight Muse Spark Open. Open source on GitHub." |

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
