from typing import Optional, Literal
import re

Jur = Literal["BIH","FBIH","RS","BD"]

def guess_jurisdiction(url: str, page_text: str) -> Optional[Jur]:
    u = url.lower(); t = page_text.lower()
    if any(k in u for k in ["uino.gov.ba","uind.gov.ba","uino"]): return "BIH"
    if "pufbih" in u or "fbih" in u: return "FBIH"
    if "poreskaupravars" in u or "vladars" in u or "apif" in u: return "RS"
    if "brcko" in u or "bdc" in u: return "BD"
    if "republika srpska" in t: return "RS"
    if "federacija bosne i hercegovine" in t: return "FBIH"
    if "brčko distrikt" in t or "brcko distrikt" in t: return "BD"
    if "bosne i hercegovine" in t: return "BIH"
    return None

EFF_FROM_RE = re.compile(r'(stupa na snagu|primjenjuje se od)\s+(\d{1,2}\.\d{1,2}\.\d{4}\.?)', re.IGNORECASE)


def extract_effective_from(text: str) -> Optional[str]:
    m = EFF_FROM_RE.search(text)
    if not m: return None
    d = m.group(2).strip(".")
    day, month, year = d.split(".")
    return f"{year}-{int(month):02d}-{int(day):02d}"
