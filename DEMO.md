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
- Open weights: Muse Spark Open (`meta-models/muse-spark-open-1026`) served on Baseten.
- Data honesty: live prices only with the data.gov.in key; scheme info is indicative.

## Submission checklist (deadline Nov 4, 9:00 PM ET = Nov 5, 6:30 AM IST; submit by Nov 3)
- [ ] Repo is **public**, README is clear, no secrets committed (`git log -p | grep -i key` returns nothing real)
- [ ] 3-minute demo video uploaded, link opens when logged out
- [ ] Live URL works (open it right before submitting)
- [ ] Track: Indie Developer. Everyone who worked on it is listed (solo)
- [ ] Open-weights prize: ask Baseten/Discord to flag the project as running on Muse Spark Open
- [ ] Optional: post the demo on X and add the post link (Most Viral prize)
- [ ] Revoke any API key that was ever pasted in a chat or screenshot

## Global beat (20 seconds, strong for a global judging panel)
Switch country to Kenya, language to Kiswahili, ask "Bei ya mahindi Nakuru ni ngapi?". Show the KSh price card with its date and trend, then point out that MSP and Indian schemes disappeared on purpose.

## Cross-check beat (15 seconds, for "Best Agentic Use-Case" and Meta tooling)
After an answer with a price card, tap "Second opinion": Muse Wonder audits it, and the figure check from code is shown next to it.

## Planting beat (15 seconds)
Country Kenya, ask "Can I plant maize this week?": the planting card shows soil temperature against what maize needs, rain and coldest night, then a clear sow / wait.

## Optional wow beats (use if you have time in the 3 minutes)
- **Where to sell:** ask "Where should I sell 10 quintals of groundnut after transport costs?". Point at the 🏆 market and the "+₹ more than the nearest market" line: a far market that pays more can lose once transport is counted.
- **Which crop:** ask "Which crop gives more profit on 2 acres this rabi?". Show the "if price falls 10%" column and say yield/cost are labelled assumptions.
- **Price alert:** tap the 🔔, set groundnut "goes above" a price below today's, tap Check now: the banner appears. Say that only live prices can trigger it.
- **SAM 3.1 leaf measurement:** add a leaf photo, tap 🔬 Measure damage: the overlay shows the marked lesions and the percentage. Say that the model finds the regions and code computes the percentage, and that it is not a diagnosis. (needs `MODEL_API_KEY`)
- **Muse Image card:** tap 🖼️ Card under an answer and share it to WhatsApp. (needs `MODEL_API_KEY`)
- **This week:** tap 📅 This week. Show the 🔴 Do first items and the 7-day strip; say it decides and ranks the actions itself and every figure is verified.
- **Khata:** tap 📒, say "sold 8 quintals groundnut at 7000", confirm, then "urea 1500"; tap Season report. Say the records stay on the phone and the model only extracts, code does the maths.
- **Crop loss:** tap 🌧️, choose Hailstorm, tap Get deadline: the 72-hour countdown, checklist, helpline and message. Then switch the cause to Drought to show it does not invent a deadline.
