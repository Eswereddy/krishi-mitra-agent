import os

from dotenv import load_dotenv

load_dotenv()

# Meta Model API (OpenAI-compatible chat completions + ASR)
META_BASE_URL = os.getenv("META_BASE_URL", "https://api.meta.ai/v1")
META_API_KEY = os.getenv("MODEL_API_KEY", "")
META_CHAT_MODEL = os.getenv("META_CHAT_MODEL", "muse-spark-1.3")

# Optional: Baseten-hosted open-weight model (for the open-weights bonus prize).
# For this hackathon use model id: meta-models/muse-spark-open-1026
BASETEN_BASE_URL = os.getenv("BASETEN_BASE_URL", "")
BASETEN_API_KEY = os.getenv("BASETEN_API_KEY", "")
OPEN_MODEL = os.getenv("OPEN_MODEL", "meta-models/muse-spark-open-1026")

# Mock mode: fake responses so the UI/flow can be built without an API key.
# MOCK_MODE=1 forces it on, MOCK_MODE=0 forces it off, default "auto" = on when no key.
_mock = os.getenv("MOCK_MODE", "auto").lower()
MOCK_MODE = _mock in ("1", "true") or (_mock == "auto" and not META_API_KEY)

REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "60"))
