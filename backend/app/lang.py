"""Language helpers: Telugu (te), English (en), Hindi (hi). "auto" = reply in the farmer's language."""
import re

NAMES = {"te": "Telugu", "en": "English", "hi": "Hindi", "es": "Spanish", "fr": "French", "pt": "Portuguese",
         "sw": "Swahili", "id": "Indonesian", "bn": "Bengali"}

WARNING = {
    "te": "\n\n⚠️ ఈ సంఖ్యలను నేను ధృవీకరించలేకపోయాను: {n}. దయచేసి అధికారిక కార్యాలయంలో నిర్ధారించుకోండి.",
    "en": "\n\n⚠️ I could not verify these figures: {n}. Please confirm at the official office.",
    "hi": "\n\n⚠️ मैं इन आंकड़ों की पुष्टि नहीं कर सका: {n}। कृपया आधिकारिक कार्यालय में पुष्टि करें।",
}


def detect(text: str) -> str:
    te = len(re.findall(r"[\u0C00-\u0C7F]", text))
    hi = len(re.findall(r"[\u0900-\u097F]", text))
    if re.search(r"[\u0980-\u09FF]", text):
        return "bn"
    if te and te >= hi:
        return "te"
    if hi:
        return "hi"
    return "en" if re.search(r"[A-Za-z]", text) else "te"


def resolve(lang: str | None, text: str = "") -> str:
    return lang if lang in NAMES else detect(text)


def instruction(code: str, mirror: bool = False) -> str:
    """mirror=True: the farmer picked "auto" and wrote in Latin letters, which could be English, Spanish, French,
    Swahili...: answer in whatever language the question was written in instead of forcing English."""
    if mirror:
        return "Always answer in the same language the farmer wrote in, in simple words, short and practical."
    return f"Always answer in simple {NAMES[code]}, short and practical."
