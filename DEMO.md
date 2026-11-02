# Demo video script (3 minutes) and submission checklist

## Before recording
- Use the deployed Render URL (open it once first: the free plan sleeps). Record on a phone for the "farmer" feel.
- Confirm `/api/health` shows `"mock": false`. Never record in mock mode.
- Set `DATA_GOV_API_KEY` so mandi prices are live. If they are sample data, say so in the video.
- Fill the farmer profile first (state, district, "I own farmland", main crop).
- Do one full dry run. Keep a typed-question fallback ready in case a voice take fails.

## Script (3 minutes, one story: a farmer's day, end to end)
| Time | Show | Say (short) |
|---|---|---|
| 0:00-0:15 | Phone in a field. First-run notice, tap OK | "Krishi Mitra: an AI agent for small farmers, in their language. Their data stays on their phone." |
| 0:15-0:50 | **Talk** in Telugu: sell groundnut now or wait? Live steps appear, answer is spoken, price chart, "verified" tick, sources | "Muse Voice transcribes, Muse Spark Open picks the tools, and every figure is checked against tool results. It cannot invent a price." |
| 0:50-1:25 | Farm Doctor: take a leaf photo. Show the overlay, damage %, confidence, reliability, safe non-chemical steps. Then retake with a blurry photo to show "retake" | "SAM 3.1 finds the damage; the percentage is computed from pixels. A bad photo is refused, not guessed. No pesticide names or doses." |
| 1:25-1:45 | Tap **Send to an expert**: symptoms, consent ticks, case preview, WhatsApp share | "When it is serious or unsure, the farmer sends one clear case to a human, with the weather and the measurement." |
| 1:45-2:10 | **Early warning** banner for the crop, then **My field**: report with "basis" under each line | "Crop-specific alerts with preventive actions. Every line of the field report says where it came from." |
| 2:10-2:30 | **Compare buyers**: two offers, net income, "Unverified" label and the advance warning | "The highest price is not always the best deal. We show net income and never call a buyer verified unless it is in our registry." |
| 2:30-2:45 | **My results**: mark advice done, enter actual cost, predicted vs actual | "It learns whether advice helped." |
| 2:45-3:00 | Switch country to Kenya, Kiswahili: maize price card, Indian schemes gone. End on repo and `EVAL_V2.md` | "Global by design. Open weights, open source, and an evaluation we publish, including what it does not prove." |

Optional 15-second beats if time allows: **Second opinion** (Muse Wonder audits an answer), **airplane mode** (saved brief and plan open offline), **Glimmer fallback** (only if you run your own Glimmer server).

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

## Coach beat (20 seconds)
Set a sowing date about 8 weeks ago, tap "This week": the plan shows the crop stage, jobs for this week and days to harvest. If the forecast is dry at flowering you get the red irrigation line.

## Eco beat (15 seconds)
Ask "How much water does my crop need this week?": the water card shows millimetres and litres after rain, the day to irrigate by, and the rainwater you could store. Say: "irrigating only the shortfall saves water, power and money".

## Protection beat (20 seconds, strong emotional moment)
Ask "A trader offers me a loan at 3% a month for 12 months, flat. Is that fair?" The loan card shows the real yearly rate next to a bank offer. Say: "the farmer sees what the loan really costs".

## Optional wow beats (use if you have time in the 3 minutes)
- **Where to sell:** ask "Where should I sell 10 quintals of groundnut after transport costs?". Point at the 🏆 market and the "+₹ more than the nearest market" line: a far market that pays more can lose once transport is counted.
- **Which crop:** ask "Which crop gives more profit on 2 acres this rabi?". Show the "if price falls 10%" column and say yield/cost are labelled assumptions.
- **Price alert:** tap the 🔔, set groundnut "goes above" a price below today's, tap Check now: the banner appears. Say that only live prices can trigger it.
- **SAM 3.1 leaf measurement:** add a leaf photo, tap 🔬 Measure damage: the overlay shows the marked lesions and the percentage. Say that the model finds the regions and code computes the percentage, and that it is not a diagnosis. (needs `MODEL_API_KEY`)
- **Muse Image card:** tap 🖼️ Card under an answer and share it to WhatsApp. (needs `MODEL_API_KEY`)
- **This week:** tap 📅 This week. Show the 🔴 Do first items and the 7-day strip; say it decides and ranks the actions itself and every figure is verified.
- **Khata:** tap 📒, say "sold 8 quintals groundnut at 7000", confirm, then "urea 1500"; tap Season report. Say the records stay on the phone and the model only extracts, code does the maths.
- **Crop loss:** tap 🌧️, choose Hailstorm, tap Get deadline: the 72-hour countdown, checklist, helpline and message. Then switch the cause to Drought to show it does not invent a deadline.

## Knowledge beat (30 seconds, shows trust and depth)
1. Ask any question, then tap **Why this answer?**: show the "SAMPLE data" / "indicative" labels and where each number came from.
2. Open **Crop rotation**: last crop groundnut, soil black: show the ranked next crops and tap one to show its reasons. Say it is rule-based, not a yield forecast.
3. Open **Research assistant**: upload an ICAR PDF you prepared beforehand, ask a question, point at the [1] citation and the passage. Then ask something the document does not cover and show that it says "not found".
4. Open **Field report**: speak a short note about spots on leaves, build the report, show urgency and the expert questions.
Do NOT claim the tables are expert-reviewed, and do not show the research assistant without a real document you uploaded yourself.

