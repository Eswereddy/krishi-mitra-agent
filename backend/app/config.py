import os

from dotenv import load_dotenv

load_dotenv()

# PROVIDER=meta     -> Meta Model API (closed Muse Spark, needs MODEL_API_KEY + card)
# PROVIDER=baseten  -> Muse Spark Open on Baseten (open weights, hackathon credits)
PROVIDER = os.getenv("PROVIDER", "baseten").lower()

META_BASE_URL = os.getenv("META_BASE_URL", "https://api.meta.ai/v1")
META_API_KEY = os.getenv("MODEL_API_KEY", "")
META_CHAT_MODEL = os.getenv("META_CHAT_MODEL", "muse-spark-1.3")

# Hackathon note: use meta-models/muse-spark-open-1026 (not the id in Baseten docs).
BASETEN_BASE_URL = os.getenv("BASETEN_BASE_URL", "https://inference.baseten.co/v1")
BASETEN_API_KEY = os.getenv("BASETEN_API_KEY", "")
OPEN_MODEL = os.getenv("OPEN_MODEL", "meta-models/muse-spark-open-1026")

if PROVIDER == "baseten":
    CHAT_BASE, CHAT_KEY, CHAT_MODEL = BASETEN_BASE_URL, BASETEN_API_KEY, OPEN_MODEL
else:
    CHAT_BASE, CHAT_KEY, CHAT_MODEL = META_BASE_URL, META_API_KEY, META_CHAT_MODEL

# Mock mode: fake responses so the UI/flow can be built without an API key.
# MOCK_MODE=1 forces it on, MOCK_MODE=0 forces it off, default "auto" = on when no key.
_mock = os.getenv("MOCK_MODE", "auto").lower()
MOCK_MODE = _mock in ("1", "true") or (_mock == "auto" and not CHAT_KEY)

REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "60"))
