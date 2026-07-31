"""
retrieval/vector_search.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Query Qdrant Cloud via REST API using Qdrant Cloud Inference.
Embedding is done server-side — no local model, no Gemini API, works on Vercel.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Optional

import config

logger = logging.getLogger(__name__)

# Qdrant Cloud Inference model — must match push_to_qdrant.py
INFERENCE_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


# ---------------------------------------------------------------------------
# Map canonical keywords to exact law titles stored in vector store
# ---------------------------------------------------------------------------
CANONICAL_LAW_TITLES: dict[str, list[str]] = {
    "Central Goods and Services Tax": [
        "Central Goods and Services Tax Act, 2017",
        "Central Goods and Services Tax Rules, 2017",
    ],
    "Integrated Goods and Services Tax": [
        "Integrated Goods and Services Tax Act, 2017",
        "Integrated Goods and Services Tax Rules, 2017",
    ],
    "Union Territory Goods and Services Tax": [
        "Union Territory Goods and Services Tax Act, 2017",
    ],
    "Compensation to States": [
        "Goods and Services Tax (Compensation to States) Act, 2017",
        "Goods and Services Tax Compensation Cess Rules, 2017",
    ],
    "Constitution (101st Amendment)": [
        "Constitution (One Hundred And First Amendment) Act, 2016",
    ],
    "Extension to Jammu And Kashmir": [
        "Central Goods And Services Tax (Extension To Jammu And Kashmir) Act, 2017",
        "Integrated Goods And Services Tax (Extension To Jammu And Kashmir) Act, 2017",
    ],
}


@lru_cache(maxsize=1)
def _qdrant_base_url() -> str:
    return (config.QDRANT_URL or "").rstrip("/")


def qdrant_vector_search(
    query: str,
    model_name: str,
    top_k: int = 15,
) -> Optional[list[dict[str, Any]]]:
    """
    Execute vector search via Qdrant Cloud REST API.
    Qdrant embeds the query server-side — no local embedding model required.
    Works identically on Vercel and local.
    """
    base_url = _qdrant_base_url()
    api_key = config.QDRANT_API_KEY
    collection = config.QDRANT_COLLECTION

    if not base_url or not api_key:
        logger.error("QDRANT_URL or QDRANT_API_KEY not configured!")
        return None

    try:
        import httpx  # type: ignore

        headers = {
            "api-key": api_key,
            "Content-Type": "application/json",
        }
        # Use /points/query REST endpoint with Cloud Inference text input
        body = {
            "query": {
                "text": query,
                "model": INFERENCE_MODEL,
            },
            "limit": top_k,
            "with_payload": True,
        }
        url = f"{base_url}/collections/{collection}/points/query"
        response = httpx.post(url, headers=headers, json=body, timeout=15.0)
        response.raise_for_status()

        data = response.json()
        results = data.get("result", {}).get("points", [])

        hits: list[dict[str, Any]] = []
        for point in results:
            payload = point.get("payload", {}) or {}
            chunk_id = payload.get("chunk_id", str(point.get("id", "")))
            hits.append({
                "id": chunk_id,
                "score": float(point.get("score", 0.0)),
                "metadata": payload,
                "document": payload.get("text", ""),
                "source": "vector_qdrant",
            })

        logger.info(
            "[QDRANT CLOUD] Cloud retrieval completed | Collection: '%s' | Hits: %d | Top Score: %.4f | Query: %r",
            collection,
            len(hits),
            hits[0]["score"] if hits else 0.0,
            query[:80],
        )
        return hits

    except Exception as exc:
        logger.error("[QDRANT CLOUD] Cloud retrieval error: %s", exc)
        return None


def vector_search(
    query: str,
    model_name: str = config.EMBEDDING_MODEL_NAME,
    top_k: int = 15,
    doc_type: Optional[str] = None,
    law_title_keywords: Optional[list[str]] = None,
    unit_numbers: Optional[list[str]] = None,
    db_path: Optional[str] = None,
    collection_name: Optional[str] = None,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """
    Return top-k semantically similar leaf chunks from Qdrant Cloud.
    Embedding handled server-side by Qdrant Cloud Inference via REST API.
    No local model downloads, no Gemini API, works on Vercel free tier.
    """
    hits = qdrant_vector_search(query=query, model_name=model_name, top_k=top_k)
    logger.info("[CLOUD RETRIEVAL DONE] Successfully retrieved %d chunks from Qdrant Cloud DB.", len(hits or []))
    return hits or []
