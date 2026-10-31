"""Countries, currencies and languages. India stays the default so nothing changes for existing users; any other
country switches the app to country-neutral behaviour (no Indian prices, schemes or helplines are ever shown abroad)."""

# ISO2 -> (name, ISO currency code, symbol)
COUNTRIES = {
    "IN": ("India", "INR", "₹"), "KE": ("Kenya", "KES", "KSh"), "NG": ("Nigeria", "NGN", "₦"), "ET": ("Ethiopia", "ETB", "Br"),
    "TZ": ("Tanzania", "TZS", "TSh"), "UG": ("Uganda", "UGX", "USh"), "GH": ("Ghana", "GHS", "GH₵"), "ZA": ("South Africa", "ZAR", "R"),
    "RW": ("Rwanda", "RWF", "RF"), "ZM": ("Zambia", "ZMW", "ZK"), "MW": ("Malawi", "MWK", "MK"), "MZ": ("Mozambique", "MZN", "MT"),
    "SN": ("Senegal", "XOF", "CFA"), "ML": ("Mali", "XOF", "CFA"), "CM": ("Cameroon", "XAF", "FCFA"), "EG": ("Egypt", "EGP", "E£"),
    "MA": ("Morocco", "MAD", "MAD"), "BD": ("Bangladesh", "BDT", "৳"), "PK": ("Pakistan", "PKR", "Rs"), "NP": ("Nepal", "NPR", "Rs"),
    "LK": ("Sri Lanka", "LKR", "Rs"), "ID": ("Indonesia", "IDR", "Rp"), "PH": ("Philippines", "PHP", "₱"), "VN": ("Vietnam", "VND", "₫"),
    "TH": ("Thailand", "THB", "฿"), "MM": ("Myanmar", "MMK", "K"), "KH": ("Cambodia", "KHR", "៛"), "BR": ("Brazil", "BRL", "R$"),
    "MX": ("Mexico", "MXN", "$"), "CO": ("Colombia", "COP", "$"), "PE": ("Peru", "PEN", "S/"), "AR": ("Argentina", "ARS", "$"),
    "CL": ("Chile", "CLP", "$"), "GT": ("Guatemala", "GTQ", "Q"), "HN": ("Honduras", "HNL", "L"), "US": ("United States", "USD", "$"),
    "GB": ("United Kingdom", "GBP", "£"), "FR": ("France", "EUR", "€"), "ES": ("Spain", "EUR", "€"), "DE": ("Germany", "EUR", "€"),
    "OTHER": ("Other country", "USD", "$"),
}
DEFAULT_COUNTRY = "IN"
# the AI answers in all of these; the first group also has full voice + UI translations
EXTRA_LANGS = {"es": "Spanish", "fr": "French", "pt": "Portuguese", "sw": "Swahili", "id": "Indonesian", "bn": "Bengali"}


def country_of(profile: dict | None) -> str:
    c = str((profile or {}).get("country") or DEFAULT_COUNTRY).upper()
    return c if c in COUNTRIES else "OTHER"


def is_india(profile: dict | None) -> bool:
    return country_of(profile) == "IN"


def currency_of(profile: dict | None) -> tuple[str, str]:
    """(ISO code, symbol): the farmer's own choice if given, else the country's currency."""
    p = profile or {}
    code, sym = COUNTRIES[country_of(p)][1:]
    own = str(p.get("currency") or "").strip().upper()
    if own and own != code and own.isalpha() and len(own) == 3:
        return own, own
    return code, sym
