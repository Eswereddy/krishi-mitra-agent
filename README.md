# 🌾 Krishi Mitra: a voice-first farming agent in Telugu, Hindi and English

Built for the **Meta Global AI Developer Hackathon** (Indie track, "Build for Your World").
**Everything in this repository was built during the hackathon window (Oct 27 – Nov 4, 2026).**

## The problem
Small farmers in India often cannot type long questions, read English websites, or find out which
government schemes they qualify for. Prices, weather and expert advice live in different places.
Krishi Mitra lets a farmer **speak** (or type, or send a **photo** of the crop) in their own language and get a
short, practical answer, read aloud if they want.

## What it does
- **Voice in, in any of 3 languages:** Telugu, Hindi, English (auto-detected, or pick one).
- **Photo to action plan:** one crop photo goes through the *same agent* (vision + tool calling): it names the likely problem and how sure it is, checks the weather to time spraying, mentions crop insurance if there is real loss, and sends the farmer to a human expert when unsure.
- **Multi-turn:** follow-up questions work ("and groundnut?"). Quick-ask buttons for common questions.
- **A real agent, not a chatbot:** the model decides which tools to call, in several steps:
  `get_mandi_price`, `best_markets` (where to sell for the highest price) and `get_price_trend` (rising or falling? sell now or wait?), all from Agmarknet via data.gov.in, `get_weather` (Open-Meteo),
  `check_schemes` (PM-KISAN, PMFBY, KCC, state support, with the documents needed), `calculate_revenue` (exact income maths, never done by the model), `get_expert_help` (Kisan Call Centre 1800-180-1551), plus the advisor tools below (`get_msp`, `net_market_value`, `spray_window`, `lookup_problem`, `hold_or_sell`).
- **Live agent steps:** the answer streams its progress ("checking mandi prices… checking weather… re-checking figures") so the farmer, and the judge, can see the agent working. Endpoints: `/api/agent/stream` and `/api/diagnose/stream` (newline-delimited JSON).
- **Sell now or wait:** the agent combines the price trend, best markets and the weather forecast into one clear recommendation (guidance, not a guarantee).
- **The agent can always talk:** browser voice when the device has one for the language, otherwise a server-generated voice (`/api/tts`, gTTS), so Telugu and Hindi are audible even on laptops without those voices.
- **Works on weak networks:** installable PWA with an offline shell; saved answers stay readable and playable offline; large-text mode for older farmers.
- **Verification layer (idea from Meta's Agents 102 workshop):** every figure in the final answer must come from a tool result.
  Otherwise the answer is sent back for a rewrite, and if it still fails the farmer sees an explicit "could not verify" warning, never a confident made-up number.
- **Honest about limits:** no pesticide doses, escalates to a human expert when unsure, says when price data is sample data.
- **New chat UI:** WhatsApp-style conversation, hands-free **voice conversation mode** (listen, answer, speak, listen again, with automatic end-of-speech detection), mic button with live waveform, **photo upload** from camera, gallery or drag-and-drop with preview (add a spoken or typed question to the photo), **read-aloud** for every answer (Telugu/Hindi/English voices, auto-read option), rich cards for mandi prices, best markets, weather, schemes (with documents) and income calculator, one-tap call to the Kisan Call Centre, light/dark theme, installable as a phone app (PWA manifest).
- **Listen button** (browser speech synthesis), **share on WhatsApp**, **farmer profile** (state, district, land, crop; saved on the device), typed input fallback.

## How Meta models are used
- **Muse Spark Open** (`meta-models/muse-spark-open-1026`, open weights, served on Baseten): chat, tool calling, image understanding, and audio understanding for speech transcription.
- Provider switch in `backend/app/config.py`: `PROVIDER=baseten` (open weights) or `PROVIDER=meta` (Meta Model API).

## Architecture
![Architecture](docs/architecture.svg)

React (Vite) frontend → FastAPI backend (`backend/app`) → Muse Spark Open. One Docker service serves both.
`agent.py` (tool loop + progress events) · `tools.py` (7 tools, live data with fallbacks) · `tts.py` (server voice fallback) · `verify.py` (answer verification) · `lang.py` (3 languages) · `meta_client.py` (model client, WebM→WAV conversion for audio).

## Demo and submission
See [DEMO.md](DEMO.md) for the 3-minute demo script and submission checklist.

## Tests (offline, no API key needed)
```bash
cd backend && python tests/test_verify.py && python tests/test_tools.py && python tests/test_stream.py && python tests/test_hardening.py && python tests/test_grounding.py && python tests/test_whatsapp.py && python tests/test_advisor.py && python tests/test_planner.py && python tests/test_meta_extras.py && python tests/test_plan.py && python tests/test_khata.py
```

## Run locally
```bash
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt            # ffmpeg must be installed for voice
cp ../.env.example .env                    # add BASETEN_API_KEY (and optional DATA_GOV_API_KEY)
uvicorn app.main:app --reload --port 8000
cd ../frontend && npm install && npm run dev
```
Without an API key the app runs in **mock mode** (fake answers, for UI development only).

## Deploy (Render)
Docker web service using the root `Dockerfile`. Environment variables: `PROVIDER=baseten`, `BASETEN_API_KEY`,
`OPEN_MODEL=meta-models/muse-spark-open-1026`, optional `DATA_GOV_API_KEY` (free key from data.gov.in for live mandi prices).

## WhatsApp channel (Meta WhatsApp Cloud API)
Farmers who will not install an app can use the same agent on WhatsApp: send a **text**, a **voice note** (answered in text and a voice reply) or a **crop photo**. Same tools, same verification layer (`backend/app/whatsapp.py`).
1. developers.facebook.com → create an app → add the **WhatsApp** product → use the test number.
2. Set on Render: `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_APP_SECRET` (App settings → Basic), `WHATSAPP_VERIFY_TOKEN` (any string you choose). Optional: `WHATSAPP_ALLOWED_NUMBERS` (comma separated, digits only) to restrict who can use the bot, `WHATSAPP_VOICE_REPLY=0` to turn voice replies off.
3. WhatsApp → Configuration: callback URL `https://<your-app>.onrender.com/webhook/whatsapp`, the same verify token, then subscribe to the **messages** field.
4. Add your phone as a test recipient and send "hi". Commands: `/district Kurnool`, `/crop Groundnut`, `/land yes`, `/reset`, `/help`.
Safety: requests are accepted only with a valid `X-Hub-Signature-256`, duplicate deliveries are answered once, each sender is rate limited, and no tokens are stored in the repo. The temporary token expires in 24 hours; for a longer demo create a System User token.

## Stronger verification and saved data
- **Field-aware verification:** money figures must come from a price/amount field in a tool result (a year, phone number or rain percentage cannot be passed off as a price); percentages, temperatures and rainfall must match a weather/trend field (rounding allowed); other 3+ digit numbers must appear in a tool result. The result reports how many figures were checked.
- **Saved real data, never invented:** if data.gov.in is slow or down, the agent uses a dated snapshot of real Agmarknet prices (`python scripts/snapshot_mandi.py`, needs your free `DATA_GOV_API_KEY`), labelled "Saved data" in the UI and in the answer. Only if no snapshot exists does it fall back to clearly-labelled sample data.

## Production safety
- Per-IP rate limits on the model, voice and TTS endpoints (default 12 agent requests/min, 20 voice requests/min; `RATE_AGENT_PER_MIN`, `RATE_VOICE_PER_MIN`), so a public demo URL cannot burn the API credits.
- Public data (Agmarknet, weather) is cached for 10 minutes (`CACHE_TTL_S`, 0 = off); failed lookups are never cached.
- Independent tool calls from one model turn run in parallel.
- `/api/debug/*` and `/api/models` are hidden unless `DEBUG_ENDPOINTS=1`.
- CI (GitHub Actions) runs the offline tests and the frontend build on every push.

## Advisor tools (new)
Five more tools (and two below) in `backend/app/advisor.py`, same rules as the rest: exact arithmetic in code, labelled sources, no invented numbers.
- `get_msp`: government Minimum Support Price per quintal (Kharif 2026-27, Rabi 2027-28 now being sown, Rabi 2026-27) from CCEA announcements in `data/msp.json`. Says MSP applies only to what the government buys.
- `net_market_value`: what a farmer really takes home from a market after commission, loading and transport, to compare a near market with a far one that pays more. Cost rates are labelled assumptions.
- `spray_window`: which of the next days suit spraying (rain chance, wind, heat). Never a dose.
- `lookup_problem`: 20 common problems for paddy, groundnut, cotton, chilli, tomato and maize matched from the farmer's own description (`data/problems.json`). Gives symptoms, field checks and non-chemical steps only, never a pesticide name or dose, and always sends the farmer to the agriculture officer.
- `hold_or_sell`: one sell-now / hold-a-little / ask-about-procurement recommendation from the price trend, best market and MSP (fixed rules, perishable crops are always "sell now").
The chat shows a card for each. MSP figures were checked on 29 Oct 2026; update `data/msp.json` when new MSPs are announced.

## Daily brief, irrigation and KCC interest (new)
- **Today button (`/api/brief`, WhatsApp `/brief`):** one tap gives today's weather, whether to irrigate, whether it is a good day to spray, the price of the farmer's main crop, the price trend, MSP comparison and a sell/hold guide, in Telugu, Hindi or English. It is built from tool results with fixed templates (no model call): instant, works without an API key, and every figure still passes the verification layer.
- `irrigation_advice`: irrigate or wait, from the rain forecast and heat (the farmer is told to check the soil by hand).
- `kcc_interest`: Kisan Credit Card crop-loan interest at 7% (4% effective if repaid within a year), exact rupees and the saving; the benefit applies on up to Rs 3 lakh (checked Oct 2026, rules are renewed every year, the bank gives the final figure).

## Planning, alerts and risk warnings (new)
- **`sell_plan` (where to sell after transport):** ranks the best-paying markets by the money that actually reaches the farmer's hand, using the distance from the farmer's village (Open-Meteo geocoding, straight line x 1.3 for roads), commission, loading and transport. A far market that pays Rs 100 more per quintal can lose to a near one; the card shows exactly why. Rates are labelled assumptions.
- **`compare_crops` (which crop to grow):** for kharif or rabi and any number of acres, ranks crops by expected profit using indicative yield and cost per acre (`data/crop_economics.json`, clearly labelled as assumptions) and the latest mandi price (or MSP when there is no market price). It also shows the profit if the price falls 10%, water need and crop duration, so risk is visible.
- **Price alerts (bell icon):** "tell me when groundnut goes above Rs 7,500". Alerts stay on the phone (no account, no personal data on the server); the app checks `/api/alerts/check` every 15 minutes, when it comes back online and on demand, and shows a banner and a phone notification. **Only live prices can trigger an alert**: sample or saved data never says "price reached".
- **Weather risk warnings in the Today brief:** heat (40 degC or more), heavy rain (25 mm or more) and strong wind (40 km/h or more) are called out with the worst day and what to do, in Telugu, Hindi and English, and pass the same verification layer.
- **Hardening:** the rate limiter now trusts only the address added by the proxy (a client can no longer dodge it with a fake `X-Forwarded-For`), idle clients are swept from memory, uploads are type- and size-checked (photos 8 MB, audio 10 MB), and the agent's "could not finish" message is in the farmer's language. `/api/health` reports the tool count and whether live prices are on.
- 16 tools in total; 10 new offline tests in `backend/tests/test_planner.py`.

## Khata and crop-loss kit (new)
- **📒 Khata (voice farm ledger):** say "bought urea for 1500" or "sold 8 quintals groundnut at 7000" in Telugu, Hindi or English (typed or by voice). The model only **extracts** one entry (`/api/ledger/parse`, with a rule-based fallback if the model is down); an amount that is not clearly in the farmer's own words is flagged, and the farmer always confirms before saving. Entries stay **on the phone** (no account). One tap gives a **season report** (income, cost of cultivation, net, cost per acre, where the money went, per crop), computed exactly in code, shareable on WhatsApp or as CSV: the record a bank or insurer asks for and most farmers do not have.
- **🌧️ Crop-loss kit (`/api/claim/draft`):** the PMFBY rule that costs farmers their claims is the **72-hour intimation window** for localized calamities (hailstorm, local flooding, landslide, cloudburst, fire) and for harvested crop drying in the field. The kit computes the exact deadline with a live countdown, gives the checklist (photos, policy number, land records), the helpline numbers and a ready message to send, in three languages. It is honest where there is no individual claim: for drought or widespread pest it says losses are assessed area-wide by the government and sends the farmer to the agriculture officer instead of inventing a deadline. Rules are summarised from the PMFBY guidelines: confirm with the insurer.

## Week plan and more schemes (new)
- **📅 This week (`/api/plan`):** one tap and the agent looks at the next 7 days and decides what to do, ranked **Do first / This week / Good to know**: heavy rain, heat or wind warnings, sell-or-hold and "below MSP" for the main crop, the next good irrigation day, the best spraying day, and the schemes the farmer qualifies for, with a 7-day strip (weather, irrigate, spray). Fixed rules and templates in Telugu, Hindi and English, no model call, and every figure passes the verification layer. If the forecast is unavailable it says so instead of planning blind.
- **Six more schemes** in the scheme check, each with documents and where to apply: Soil Health Card, e-NAM, PM Kisan Maan-Dhan pension, PMKSY drip/sprinkler subsidy, PM-KUSUM solar pumps, Agriculture Infrastructure Fund. Subsidy rates that differ by state are not quoted; the card sends the farmer to the office to confirm.

## More of Meta's model family (new, optional)
The core agent runs on **Muse Spark Open** (open weights, Baseten). With a Meta Model API key (`MODEL_API_KEY`, works alongside `PROVIDER=baseten`) three more Meta models switch on. Nothing in the existing flow changes; each feature is a separate endpoint and degrades gracefully without the key. `GET /api/meta-models` shows which models a deployment uses.
- **Muse Voice Transcribe** (`muse-voice-transcribe-1.0`) through `/api/asr`: a dedicated speech model for Telugu/Hindi/English voice questions. If the call fails, the app falls back to the Spark Open audio path, so voice never stops working.
- **SAM 3.1** (`sam-3.1`) through `/api/leaf-scan` (button "Measure damage" on a photo): segments "diseased leaf spot" and "leaf", and the damage percentage is **computed in code from the masks** (the model finds the regions, never the number). It is a measurement, not a diagnosis: no disease name, no pesticide, heavy damage points to the Kisan Call Centre. Masks are decoded with Meta's official `meta-sam-parser`.
- **Muse Image** (`muse-image-1.0`) through `/api/advice-card` (button "Card" under an answer): turns the first sentence of an already-verified answer into a shareable card for WhatsApp groups. Only that sentence is put on the card, so no new figures can appear.
Tested offline with a mocked Meta API (`backend/tests/test_meta_extras.py`). Run these against the live API once with your key before recording the demo.

## Global mode: any country, any language (new)
Krishi Mitra is not India-only. Pick a country in "My details" (40 countries + Other) and the app switches:
- **Prices:** `get_market_price` reads WFP food-price data from the Humanitarian Data Exchange (open data, many developing countries). It is monthly data, so every answer says how old it is. If a country has no data, the agent asks the farmer for the price he was offered and uses `calculate_revenue`. It never invents a price.
- **Money:** answers use the farmer's own currency (KES, NGN, BRL...). The verification layer checks currency amounts the same way it checks rupees.
- **Languages:** Telugu, Hindi and English plus Spanish, French, Portuguese, Swahili, Indonesian and Bengali. For any other language the agent mirrors the language the farmer wrote in. Voice (Muse Voice language bias, browser voices, server TTS) follows the chosen language.
- **India-only features stay India-only:** MSP, PMFBY claim kit, Kisan Call Centre, Agmarknet alerts and Indian schemes are switched off abroad (claim kit gives a generic "check your policy" guide), so a farmer elsewhere never sees a wrong rupee figure or wrong helpline.
- Weather (Open-Meteo), the daily brief, week plan, Khata and photo advice work anywhere.
- Tests: `backend/tests/test_global.py`. The HDX endpoint could not be reached from the build sandbox, so test it once live: ask for maize prices with country Kenya.

## Second opinion with Muse Wonder (new)
Under every answer that used tools, a "Second opinion" button asks **Muse Wonder** (Meta's reasoning model, `muse-wonder-1.0`) to audit the answer written by Muse Spark Open. Wonder sees only the tool results and the answer, and says whether the advice follows from the data and which caution is missing. The number check still runs in code and always wins: if a figure is not in the tool results the verdict is "issues" whatever the model says. Two Meta models, one hard code check. Endpoint: `POST /api/second-opinion`; works without a key as a code-only check. Tests: `backend/tests/test_audit.py`.

## Planting window, frost warning and a self-run evaluation (new)
- **Planting window** (`planting_window`, any country): soil temperature, soil moisture, coming rain and frost from Open-Meteo decide "sow now / wait", computed in code. Germination temperatures are indicative guidance (`data/crop_planting.json`); the card tells the farmer to check the soil by hand.
- **Frost warning** in the daily brief (night at or below 2 C), in all brief languages.
- **Evaluation:** `cd backend && python eval/run_eval.py --out ../EVAL.md` runs 20 questions (India, Kenya, Brazil; 6 languages) through the live agent and reports right-tool rate, share of answers whose figures all verify (and with no India-only terms abroad), rewrites and latency. Run it once on your deployment and quote the numbers.

## Crop coach: a guide for every farmer (new)
Enter the sowing date in "My details" and Krishi Mitra becomes a coach (`crop_guide`, any country, 16 crops): it works out the growth stage, lists the few jobs that matter this week (weeding, scouting, feeding check, harvest and storage planning), counts days to the expected harvest, and raises an urgent line when the most water-sensitive stage meets a dry week (rain forecast from Open-Meteo). It also appears in the week plan, in Telugu, Hindi and English. Durations are indicative and labelled so; it never names pesticides or doses. Tests: `backend/tests/test_coach.py`.

## Season check and Muse Glimmer fallback (new)
- **Season check** (`season_check`, any country): rain and temperature of the last 30 days against the same 30 days of the last 10 years (Open-Meteo historical archive), computed in code: "rain is 45% of normal". Shown as a card, in the week plan (dry or wet season line in te/hi/en) and available to the agent for "is this a drought year?". Archive data lags about 5 days and covers a grid cell, so it is a planning signal, not a forecast.
- **Muse Glimmer fallback** (open weights, Apache 2.0, about 30B, runs on one GPU): set `GLIMMER_BASE_URL` (any OpenAI-compatible server: vLLM, SGLang, Fireworks, Modal), optional `GLIMMER_API_KEY` and `GLIMMER_MODEL` (default `meta-models/Muse-Glimmer-30B`). If the main model call fails with a timeout, connection error, 5xx or 429, the same request goes to Glimmer so the farmer still gets an answer. A cooperative can also run it on a local machine. Shown in `/api/meta-models`. Tests: `backend/tests/test_climate.py`.

## Data honesty
- Mandi prices are live only when `DATA_GOV_API_KEY` is set and data.gov.in responds; otherwise the tool returns clearly labelled **sample data**.
- Scheme details are indicative and must be confirmed with the official office (links are returned by the tool).

## Progress log
- Day 1 (Oct 27): repo scaffold, FastAPI backend, Meta API client, voice-record UI, crop photo upload.
- Day 2 (Oct 28): agent loop with tools, mock mode, Baseten provider switch, answer verification layer, Docker deploy.
- Day 3 (Oct 29): photo-to-action-plan through the agent, multi-turn, best markets, revenue calculator, scheme documents, WhatsApp share, quick-ask buttons, transcription guard, image shrinking. Also: Telugu/English/Hindi, typed input, WebM→WAV audio fix for Baseten, weather + expert-help + live mandi tools, farmer profile, listen button.
- Day 4 (Oct 30): sell_plan, compare_crops, price alerts, weather risk warnings, rate-limit and upload hardening.
