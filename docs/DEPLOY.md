# Deployment guide (Render, one Docker service)

1. Push to `main`; Render builds the `Dockerfile` (frontend is built and served by FastAPI).
2. Environment variables (Render dashboard, never in git):
   - `PROVIDER=baseten`, `BASETEN_API_KEY`, `OPEN_MODEL=meta-models/muse-spark-open-1026`
   - Optional Meta Model API: `MODEL_API_KEY` (Voice, SAM 3.1, Wonder, Image)
   - `DATA_GOV_API_KEY` (live India mandi prices)
   - Optional: `EXPERT_CONTACTS` (JSON list), `GLIMMER_BASE_URL`, `GLIMMER_API_KEY`, `GLIMMER_MODEL`, WhatsApp variables
   - Tuning: `RATE_AGENT_PER_MIN`, `RATE_VOICE_PER_MIN`, `TRUSTED_PROXIES=1`, `CACHE_TTL_S`, `DEBUG_ENDPOINTS=0`
3. Verify: `/api/health` shows `"mock": false`; call the app once, then check `/api/status` for per-model calls and errors.
4. Run `python eval/suite_v2.py --live --out ../EVAL_V2.md` and commit the real numbers.
5. Monitoring: Render logs show `krishi.access` lines; alert on repeated `500` or rising `errors` in `/api/status`.
6. Backup: no server-side farmer data exists. Back up by keeping `backend/app/data/buyers.json` in git and the environment variables in a password manager.
7. Key hygiene: rotate any key ever pasted into a chat or screenshot; Render free plan sleeps, so open the URL before demos.
