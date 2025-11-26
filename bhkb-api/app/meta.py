import re
from typing import Optional


def guess_jurisdiction(url: str, text: str) -> Optional[str]:
    """
    Heuristically derive jurisdiction from a URL or text body.

    Priority is URL, with a fallback to scanning text for known markers.
    Returns a short code when recognized, otherwise None.
    """
    lower_url = (url or "").lower()
    lower_text = (text or "").lower()

    if "pufbih" in lower_url or "federacija" in lower_text:
        return "FBIH"

    if "brcko" in lower_url or "brčko" in lower_text or "brcko" in lower_text:
        return "BD"

    if "vlada" in lower_url or "rs.gov" in lower_url:
        return "RS"

    return None


def extract_effective_from(text: str) -> Optional[str]:
    """
    Extract the first effective-from date in formats like DD.MM.YYYY.
    Returns ISO yyyy-mm-dd or None when missing.
    """
    match = re.search(r"(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2,4})", text)
    if not match:
        return None

    day, month, year = match.groups()
    if len(year) == 2:
        year = f"20{year}"

    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
