# Krishi Mitra Agent

A Telugu voice + photo farming agent built for the Meta Global AI Developer Hackathon
(track: Indie Developer, theme: Build for Your World).

> **Everything in this repository was built during the hackathon window (Oct 27 – Nov 4, 2026).**

## Planned features
- Telugu voice questions via **Muse Voice Transcribe**
- Crop photo understanding via **Muse Spark** (vision)
- Multi-step agent (tool calling): mandi rates, scheme eligibility, next steps
- Optional switch to **Muse Spark Open** (Baseten) for open-weights

## Deploy (Render)
Docker web service: build uses the root `Dockerfile`. Set env vars `PROVIDER=baseten`, `BASETEN_API_KEY`, `OPEN_MODEL=meta-models/muse-spark-open-1026`.

## Run locally

Backend:
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env   # add MODEL_API_KEY
uvicorn app.main:app --reload --port 8000
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

## Progress log
- Day 1 (Oct 27): repo scaffold, FastAPI backend, Meta API client, `/api/transcribe`, `/api/ask`, voice-record UI.
- Day 1 (Oct 27): crop photo upload (`/api/diagnose`, Muse Spark vision) + UI.
- Day 2 (Oct 28): agent loop (`/api/agent`) with tools `get_mandi_price` (sample data for now) and `check_schemes`; mock mode for key-less dev; agent steps shown in UI.
- Day 2 (Oct 28): provider switch (`PROVIDER=baseten` -> Muse Spark Open `meta-models/muse-spark-open-1026`, or `meta`).
