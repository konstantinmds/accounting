from app.meta import extract_effective_from, guess_jurisdiction


def test_guess_jurisdiction_url_priority():
    url = "https://www.pufbih.ba/document"
    text = ""
    assert guess_jurisdiction(url, text) == "FBIH"


def test_guess_jurisdiction_text_fallback():
    url = "https://example.com"
    text = "Brčko distrikt propis"  # contains special character
    assert guess_jurisdiction(url, text) == "BD"


def test_extract_effective_from():
    text = "Odluka stupa na snagu 12.05.2024. godine"
    assert extract_effective_from(text) == "2024-05-12"


def test_extract_effective_from_none():
    assert extract_effective_from("nema datuma") is None
