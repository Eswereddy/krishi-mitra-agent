# Krishi Mitra: submission text

Copy each section into the hackathon form. Replace the three links at the bottom before submitting.

## One-line pitch
A voice-first farming agent that talks to small farmers in Telugu, Hindi and English, checks live mandi prices, weather and government schemes with real tools, and never shows a number it cannot verify.

## The problem
Small farmers in India often cannot type long questions, read English websites, or find out which government schemes they qualify for. The things they need on a given day (today's mandi price, whether to sell now or wait, whether it will rain before spraying, which scheme covers crop loss) live in different places, in English, behind forms. A wrong price or a confident wrong answer costs real money.

## What Krishi Mitra does
- **Talk to it.** Tap Talk and have a hands-free conversation: it listens, answers out loud, and listens again. Typing and crop photos work too.
- **A real agent, not a chatbot.** The model decides which of 16 tools to call, in several steps: mandi price, best markets to sell, price trend (rising or falling), weather forecast, scheme eligibility with documents needed, an exact income calculator, expert help (Kisan Call Centre), and an advisor set: government MSP, take-home value after transport and fees, spray-day finder, a crop-problem lookup that never names pesticides or doses, a one-line sell-or-hold recommendation, irrigation advice and Kisan Credit Card interest. A one-tap **Today brief** (weather, irrigation, spraying, price, MSP gap, sell/hold) is built with no model call, so it is instant and works offline from the model.
- **Where to sell, after transport.** A far market that pays more can leave less money in hand. `sell_plan` ranks markets by what reaches the farmer after distance, commission and loading.
- **Which crop to grow.** `compare_crops` ranks crops for the season by expected profit per acre, with the downside if the price falls 10%, water need and duration. Yield and cost are labelled assumptions.
- **Price alerts and weather warnings.** Set a target price once; the app tells the farmer when a live price reaches it (never from sample or old data). The Today brief warns about heat, heavy rain and strong wind.
- **Sell now or wait.** It combines the price trend, the best markets and the weather into one clear recommendation, and says it is guidance, not a guarantee.
- **Photo to action plan.** A crop photo goes through the same agent: likely problem and how sure it is, weather to time spraying, crop insurance if there is real loss, and a call button to a human expert when unsure. It gives no pesticide doses.
- **You can watch it work.** Each tool call appears live while the answer is being prepared.
- **Built for rural conditions.** Installable app, works offline for saved answers, large-text mode, and a server voice fallback so Telugu and Hindi can be heard even on devices with no such voice installed.

## How Meta models are used
- **Muse Spark Open** (open weights, served on Baseten) does the chat, tool calling, image understanding and speech transcription. One model for text, vision and audio keeps the app simple.
- A provider switch (`PROVIDER=baseten` or `PROVIDER=meta`) lets the same code run on the Meta Model API.

## Why you can trust the numbers (verification layer)
Idea taken from Meta's Agents 102 workshop. After the model writes its answer, plain code outside the model checks that every figure of three or more digits (prices, rupee amounts) appears in a tool result. If not, the model must rewrite using only tool data (up to two tries). If it still fails, the farmer sees a visible "could not verify" warning instead of a confident wrong number. Income maths is done by a calculator tool, never by the model. Prices are live only when the data.gov.in key is set; otherwise the answer is clearly labelled sample data.

## How it is built
React (Vite) PWA, FastAPI backend, Muse Spark Open on Baseten. Live data: Agmarknet via data.gov.in and Open-Meteo. One Docker service on Render serves both. Offline tests cover the verification layer, the tools (network mocked), the streaming endpoint and language handling. See `docs/architecture.svg`.

## Challenges we solved
- Browser audio (WebM) had to be converted to WAV before the model could transcribe it; short or unclear speech sometimes made the model refuse, so transcription results are checked and the farmer is asked to repeat instead of getting a made-up question.
- Models sometimes said "market" instead of "district" in tool arguments, and the government dataset changes field names between versions; the tools handle both.
- Many laptops have no Telugu text-to-speech voice, so the app falls back to a server-generated voice.

## Honest limits
- Scheme information is indicative; the app always points to the official office or site to confirm.
- It does not give pesticide doses and sends serious or uncertain cases to a human expert.
- Price history and live prices depend on data.gov.in being reachable and on the API key; the app says when it is showing sample data.
- Telugu, Hindi and English only for now.

## What is next
More languages, village-level weather from the farmer's location, price alerts over WhatsApp, and real transport quotes instead of assumed rates.

## Links (fill in before submitting)
- Live app: <https://krishi-mitra-agent.onrender.com/>
- Demo video (3 min): <PASTE VIDEO URL>
- Code: https://github.com/Eswereddy/krishi-mitra-agent
