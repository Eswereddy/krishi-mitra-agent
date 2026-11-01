# Repository audit (verified against source and tests, not the README)

Audit date: 2026-11-01. Method: read the code paths, grep for controls, run all 30 backend test files and the frontend build. "Verified" = a test exercises it with the network stubbed; **nothing below was verified against the live Meta APIs, live data.gov.in, WFP/HDX or Open-Meteo from the build sandbox.**

## 1. Fully implemented (code + tests)
- Tool-calling agent (28 tools, max 6 steps), figure verification with rewrite loop, streaming NDJSON endpoints, mock mode only without a key.
- Global mode (40 countries), locale/currency handling, India-only features gated.
- Today brief, 7-day plan (no model call), price alerts, Khata (money notebook), crop-loss (PMFBY 72-hour) kit.
- Farm Doctor evidence (SAM masks, pixel-computed %, photo gate, confidence, reliability, safe steps, escalation), expert case builder with consent, outcome tracking, farm digital twin, village early warning, buyer offer comparison.
- WhatsApp webhook (HMAC signature check, commands, voice notes), Telugu/Hindi/English UI plus 6 more languages, PWA with offline saved brief/plan.
- Offline evaluation suite (`EVAL_V2.md`), per-feature tests, CI running every test file.

## 2. Partially implemented
- **Meta model integrations**: calls exist for Spark Open, Voice, SAM 3.1, Wonder, Image, Glimmer; unverified live. `meta_client.transcribe` still carries a "confirm field names against the API reference" note.
- **Smart irrigation**: crop water need and irrigate-by date exist (`water_plan`); no pumping-cost or water-saving tracking.
- **Crop insurance**: deadline, checklist and drafted message exist; no evidence organiser, claim-progress tracker or downloadable report.
- **Agent**: no confirmation step before consequential actions, no consent-based long-term memory (history is on the device), no per-answer confidence score beyond verification.
- **Authentication**: none by design (device-first, stateless server). Public endpoints are protected only by rate limits.
- **Glimmer**: needs the owner's own server (`GLIMMER_BASE_URL`).

## 3. Broken
No failing test and no known crash. Fixed during this audit: a crashing tool could crash the agent; a missing disease field could 500 the expert case endpoint.

## 4. Missing
Per-farm accounts and a database (deliberately not built), pump/electricity cost tracking, claim tracker, downloadable evidence report, agent memory with consent, tool router (all 28 tool specs are sent on every model call), live-measured evaluation numbers, demo video.

## 5. Duplicates / overlap
`/api/transcribe` and `/api/asr` (two speech endpoints); `/api/ask` vs `/api/agent`; brief vs plan overlap by design; `MAX_*_BYTES` defined in two files; legacy `needs_expert` kept beside the new escalation object.

## 6. Security findings
| Finding | Status |
|---|---|
| No request logging or monitoring | **Fixed**: privacy-safe access log (method, path, status, ms), `/api/status` model telemetry |
| No security headers | **Fixed**: nosniff, frame deny, referrer, permissions policy. CSP not added (inline styles and Google Fonts); remaining risk is low for a no-login app |
| No request-size cap on JSON | **Fixed**: 1 MB JSON, 12 MB uploads |
| Upload trusted Content-Type only | **Fixed** on `/api/diagnose`: JPEG/PNG/WebP signature check; leaf scan fully decodes the image |
| Decompression bomb | **Fixed**: Pillow pixel cap 40 MP |
| Outbound URLs (with place names) in logs | **Fixed**: httpx logger at WARNING |
| Several endpoints had no rate limit | **Fixed**: claim, outcomes, ledger report, expert |
| Rate limiter is in memory, per process | Open: fine for one Render instance; resets on restart |
| Public endpoints without auth can spend model credits | Open: mitigated by rate limits only; add an API gate or Cloudflare if the URL goes viral |
| Farmer data in `localStorage` is unencrypted on the device | Open, by design; disclosed in the consent notice |
| Secrets | Verified: `.env` is gitignored, no key patterns found in tracked files, keys are server-side only |

## 7. Performance
Tools run in threads and in parallel per step; cache TTL 600 s; failures never cached. Concerns: 28 tool specs per model call (tokens, latency); one process; no agent-answer cache.

## 8. Hackathon judging weaknesses
- Meta tooling (25%): strong breadth, but unverified live and the first thing a judge asks. Mitigation: run `suite_v2.py --live`, show `/api/status` and the "served by" line in the demo.
- Impact (30%): needs real-world evidence. Outcome tracking exists; with no field trial, claim only what the tests prove.
- Demo (25%): recording is the remaining big item; script and checklist exist.
- Technical depth (20%): verification layer, computed-in-code numbers and the published evaluation are the differentiators.
