"""
retrieval/vector_search.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Query Qdrant Cloud Vector DB for semantically similar GST chunks.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Optional

import config

logger = logging.getLogger(__name__)


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


class QueryEmbedder:
    """Embed queries using Google GenAI (text-embedding-004 / Gemini Embedding 2), FastEmbed, or SentenceTransformers."""

    def __init__(self, model_name: Optional[str] = None):
        import os
        self.model_name = model_name or config.EMBEDDING_MODEL_NAME
        self.mode = None
        self._model = None

        api_key = config.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")

        # --- 1. Primary: Google GenAI (Gemini Embedding 2 - gemini-embedding-2) ---
        if api_key:
            try:
                from google import genai as google_genai  # type: ignore
                from google.genai import types as google_genai_types  # type: ignore
                embed_model = getattr(config, "GOOGLE_EMBEDDING_MODEL", "gemini-embedding-2").replace("models/", "")
                g_client = google_genai.Client(api_key=api_key)
                self._embed_dim = 384
                embed_cfg = google_genai_types.EmbedContentConfig(output_dimensionality=self._embed_dim) if "gemini-embedding" in embed_model else None
                test = g_client.models.embed_content(model=embed_model, contents="test", config=embed_cfg)
                if test and test.embeddings:
                    self._google_client = g_client
                    self._google_embed_model = embed_model
                    self._genai_types = google_genai_types
                    self.mode = "google"
                    logger.info("Using Google GenAI embedding model: %s (dim=%d)", embed_model, len(test.embeddings[0].values))
            except Exception as err_g:
                logger.warning("Google embedding initialization failed (%s); trying local fallbacks...", err_g)

        # --- 2. Secondary Fallback: FastEmbed ONNX ---
        if self.mode is None:
            try:
                from fastembed import TextEmbedding  # type: ignore
                _cache = os.environ.get("FASTEMBED_CACHE_DIR", "/tmp/fastembed_cache")
                os.makedirs(_cache, exist_ok=True)
                logger.info("Falling back to FastEmbed ONNX model: %s (cache=%s)", self.model_name, _cache)
                self._model = TextEmbedding(model_name=self.model_name, cache_dir=_cache)
                self.mode = "fastembed"
            except Exception as err_fe:
                logger.warning("FastEmbed unavailable (%s); trying SentenceTransformers...", err_fe)

        # --- 3. Tertiary Fallback: SentenceTransformers ---
        if self.mode is None:
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore
                logger.info("Falling back to SentenceTransformer model: %s", self.model_name)
                self._model = SentenceTransformer(self.model_name)
                self.mode = "sentence_transformers"
            except Exception as err_st:
                logger.error("SentenceTransformers unavailable (%s).", err_st)

        if self.mode is None:
            raise RuntimeError("No embedding library available. Set GEMINI_API_KEY or install fastembed.")

    def encode(self, query: str) -> list[float]:
        if self.mode == "google":
            embed_cfg = self._genai_types.EmbedContentConfig(output_dimensionality=self._embed_dim) if "gemini-embedding" in self._google_embed_model else None
            result = self._google_client.models.embed_content(
                model=self._google_embed_model,
                contents=query,
                config=embed_cfg,
            )
            return list(result.embeddings[0].values)
        elif self.mode == "fastembed":
            generator = self._model.embed([query])
            vec = list(generator)[0]
            return vec.tolist() if hasattr(vec, "tolist") else list(vec)
        elif self.mode == "sentence_transformers":
            vec = self._model.encode(query, normalize_embeddings=True, convert_to_numpy=True)
            return vec.tolist() if hasattr(vec, "tolist") else list(vec)
        return []


@lru_cache(maxsize=1)
def _get_model(model_name: str) -> QueryEmbedder:
    """Load and cache the query embedding model."""
    return QueryEmbedder(model_name)


@lru_cache(maxsize=1)
def _get_qdrant_client():
    """Connect and cache Qdrant Cloud Client."""
    if not config.QDRANT_URL or not config.QDRANT_API_KEY:
        logger.error("QDRANT_URL or QDRANT_API_KEY not configured!")
        return None
    try:
        from qdrant_client import QdrantClient  # type: ignore
        client = QdrantClient(
            url=config.QDRANT_URL,
            api_key=config.QDRANT_API_KEY,
            timeout=10.0
        )
        logger.info("Connected to Qdrant Cloud cluster: %s", config.QDRANT_URL)
        return client
    except Exception as exc:
        logger.error("Failed to connect to Qdrant Cloud: %s", exc)
        return None


def qdrant_vector_search(
    query: str,
    model_name: str,
    top_k: int = 15
) -> Optional[list[dict[str, Any]]]:
    """Execute vector search using Qdrant Cloud."""
    q_client = _get_qdrant_client()
    if not q_client:
        return None

    try:
        model = _get_model(model_name)
        qvec = model.encode(query)

        # Support both newer query_points() and older search() APIs in qdrant-client
        if hasattr(q_client, "query_points"):
            response = q_client.query_points(
                collection_name=config.QDRANT_COLLECTION,
                query=qvec,
                limit=top_k
            )
            search_results = getattr(response, "points", [])
        else:
            search_results = q_client.search(
                collection_name=config.QDRANT_COLLECTION,
                query_vector=qvec,
                limit=top_k
            )

        hits: list[dict[str, Any]] = []
        for point in search_results:
            payload = getattr(point, "payload", {}) or {}
            point_id = getattr(point, "id", "")
            chunk_id = payload.get("chunk_id", str(point_id))
            hits.append({
                "id": chunk_id,
                "score": float(getattr(point, "score", 0.0)),
                "metadata": payload,
                "document": payload.get("text", ""),
                "source": "vector_qdrant",
            })

        logger.info(
            "[QDRANT CLOUD] Cloud retrieval completed | Collection: '%s' | Hits: %d | Top Score: %.4f | Query: %r",
            config.QDRANT_COLLECTION,
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
    Embed *query* and return top-k semantically similar leaf chunks directly from Qdrant Cloud.
    No local vector database is used.
    """
    hits = qdrant_vector_search(query=query, model_name=model_name, top_k=top_k)
    logger.info("[CLOUD RETRIEVAL DONE] Successfully retrieved %d chunks from Qdrant Cloud DB.", len(hits or []))
    return hits or []
