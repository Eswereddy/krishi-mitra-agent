"""Tool router: send the model only the tools that can matter for THIS question, instead of all 28 on every call.
That cuts prompt size and latency. Safety rules: a few general tools are always offered; when no topic matches (a short follow-up,
an unusual language, anything unclear) ALL tools are offered, so routing can only narrow, never block, a question it does not
understand. Keywords are a plain list per topic (English, Telugu, Hindi plus Swahili, Spanish, Portuguese hints). Router recall
on the evaluation questions is measured in eval/suite_v2.py: those questions were seen while writing the keywords, so it is in-sample.
"""
import re

ALWAYS = ("get_expert_help", "get_weather", "calculate_revenue")
TOPICS = {
    "price": (("get_mandi_price", "best_markets", "get_price_trend", "hold_or_sell", "get_msp", "net_market_value", "sell_plan", "compare_crops",
               "get_market_price", "price_seasonality", "breakeven_price", "storage_check"),
              r"price|rate\b|sell|market|mandi|msp|income|profit|revenue|earn|wait|hold|store|storage|moisture|break.?even|worth|"
              r"धर|भाव|बेच|मंडी|कीमत|मुनाफ|आमदनी|ధర|అమ్మ|మార్కెట్|లాభ|ఆదాయ|నిల్వ|bei\b|soko|uza|precio|vender|mercado|preço|preco|vend"),
    "weather_water": (("get_weather", "spray_window", "irrigation_advice", "water_plan", "season_check", "livestock_heat", "disease_risk"),
                      r"weather|rain|forecast|water|irrigat|spray|dry|drought|heat|hot\b|humid|season|wind|cow|cattle|buffalo|goat|poultry|livestock|"
                      r"मौसम|बारिश|पानी|सिंचाई|गर्मी|छिड़काव|పశు|వర్ష|వాతావరణ|నీరు|తడి|వేడి|పిచికారీ|mvua|maji|lluvia|agua|riego|chuva|água|clima"),
    "crop_care": (("lookup_problem", "disease_risk", "crop_guide", "planting_window", "spray_window", "storage_check", "compare_inputs", "get_weather"),
                  r"disease|pest|leaf|leaves|spot|yellow|wilt|insect|worm|mould|mold|fung|plant|sow|seed|grow|stage|fertili[sz]|urea|dap|manure|harvest|crop|"
                  r"पत्त|कीट|रोग|बुवाई|खाद|फसल|कटाई|ఆకు|మచ్చ|తెగులు|పురుగు|విత్త|ఎరువు|పంట|కోత|ugonjwa|mbegu|plaga|plantar|siembra|praga|doen|plantio"),
    "money": (("check_schemes", "kcc_interest", "loan_compare", "calculate_revenue", "compare_inputs"),
              r"scheme|loan|kcc|credit|interest|insurance|subsid|pm.?kisan|pmfby|bank|emi|borrow|lend|"
              r"योजना|ऋण|बीमा|ब्याज|सब्सिडी|పథక|రుణ|బీమా|వడ్డీ|mkopo|riba|bima|préstamo|prestamo|seguro|empréstimo|emprestimo|seguro"),
}
_RX = {k: re.compile(v[1], re.I) for k, v in TOPICS.items()}


def topics(text: str, has_image: bool = False) -> set[str]:
    hit = {k for k, rx in _RX.items() if rx.search(text or "")}
    if has_image:
        hit |= {"crop_care", "weather_water", "money"}        # a photo: problem, spray timing and insurance may all matter
    return hit


def names(text: str, has_image: bool = False) -> set[str] | None:
    """Tool names to offer, or None meaning 'offer everything'."""
    hit = topics(text, has_image)
    if not hit:
        return None
    out = set(ALWAYS)
    for k in hit:
        out |= set(TOPICS[k][0])
    return out


def select(specs: list[dict], text: str, has_image: bool = False) -> list[dict]:
    keep = names(text, has_image)
    if keep is None:
        return specs
    chosen = [s for s in specs if s["function"]["name"] in keep]
    return chosen or specs
