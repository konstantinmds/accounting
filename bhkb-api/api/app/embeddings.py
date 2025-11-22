import os, numpy as np, httpx
from typing import List

VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")
EMBED_MODEL = "voyage-context-3"

async def embed_voyage(texts: List[str]) -> List[List[float]]:
    if not VOYAGE_API_KEY:
        return _fallback_vecs(texts)
    url = "https://api.voyageai.com/v1/embeddings"
    headers = {"Authorization": f"Bearer {VOYAGE_API_KEY}", "Content-Type": "application/json"}
    payload = {"input": texts, "model": EMBED_MODEL}
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()["data"]
        return [item["embedding"] for item in data]

    
def _fallback_vecs(texts):
    import hashlib
    out = []
    for t in texts:
        h = hashlib.sha256(t.encode("utf-8", errors="ignore")).digest()
        rng = np.random.default_rng(int(np.frombuffer(h[:8], dtype=np.uint64)[0]))
        v = rng.standard_normal(1024).astype("float32")
        v /= max(1e-6, np.linalg.norm(v))
        out.append(v.tolist())
    return out
