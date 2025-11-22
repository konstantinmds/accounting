import io, mimetypes
from typing import Any, Literal, Tuple
import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader


Mime = Literal["text/html","application/pdf","text/plain","application/octet-stream"]

async def fetch_bytes(url: str) -> Tuple[bytes, Mime]:
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.get(url)
        r.raise_for_status()
        ct = r.headers.get("content-type","").split(";")[0].strip().lower()
        if not ct:
            # guess from extension
            guessed = mimetypes.guess_type(url)[0]
            ct = guessed or "application/octet-stream"
        return r.content, ct  # type: ignore
    

def extract_text(data: bytes, content_type: str) -> str:
    if content_type.startswith("text/html"):
        soup = BeautifulSoup(data, "lxml")
        for tag in soup(["script","style","noscript","nav","footer","header"]): tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        return " ".join(text.split())
    if content_type == "application/pdf":
        pdf = PdfReader(io.BytesIO(data))
        pages = []
        for p in pdf.pages:
            pages.append((p.extract_text() or ""))
        return "\n\n".join(pages)
    try:
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return ""
