"""
retrieval/vector_search.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Query vector databases (Qdrant Cloud or local ChromaDB) for semantically similar chunks.

Supports Qdrant Cloud integration via QDRANT_URL and QDRANT_API_KEY environment variables,
with automatic fallback to local ChromaDB if unavailable.
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
    """Wrapper supporting FastEmbed (lightweight ONNX) and SentenceTransformers (PyTorch)."""
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.mode = None
        self._model = None

        try:
            from fastembed import TextEmbedding  # type: ignore
            logger.info("Initializing FastEmbed (ONNX) model for query embedding: %s", model_name)
            self._model = TextEmbedding(model_name=model_name)
            self.mode = "fastembed"
        except Exception as err_fe:
            logger.debug("FastEmbed unavailable (%s); trying SentenceTransformers...", err_fe)
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore
                logger.info("Initializing SentenceTransformer (PyTorch) model: %s", model_name)
                self._model = SentenceTransformer(model_name)
                self.mode = "sentence_transformers"
            except Exception as err_st:
                logger.error("Neither fastembed nor sentence_transformers available: %s", err_st)
                raise RuntimeError("No embedding library available. Install fastembed or sentence-transformers.") from err_st

    def encode(self, query: str) -> list[float]:
        if self.mode == "fastembed":
            generator = self._model.embed([query])
            vec = list(generator)[0]
            return vec.tolist() if hasattr(vec, "tolist") else list(vec)
        else:
            vec = self._model.encode(query, normalize_embeddings=True, convert_to_numpy=True)
            return vec.tolist() if hasattr(vec, "tolist") else list(vec)


@lru_cache(maxsize=1)
def _get_model(model_name: str) -> QueryEmbedder:
    """Load and cache the query embedding model."""
    return QueryEmbedder(model_name)


@lru_cache(maxsize=1)
def _get_qdrant_client():
    """Connect and cache Qdrant Cloud Client."""
    if not config.QDRANT_URL or not config.QDRANT_API_KEY:
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


@lru_cache(maxsize=1)
def _get_chroma_collection(db_path: str, collection_name: str):
    """Open and cache local ChromaDB persistent collection."""
    try:
        import chromadb  # type: ignore
        client = chromadb.PersistentClient(path=db_path)
        col = client.get_collection(collection_name)
        logger.info(
            "Opened ChromaDB collection '%s' (%d items).",
            collection_name, col.count(),
        )
        return col
    except Exception as exc:
        logger.warning("Local ChromaDB collection unavailable: %s", exc)
        return None


def _build_where_filter(
    doc_type: Optional[str],
    law_title_keywords: list[str],
    unit_numbers: list[str],
) -> Optional[dict]:
    """Build a valid ChromaDB 'where' filter dict."""
    clauses: list[dict] = []

    if doc_type in ("act", "rule"):
        clauses.append({"doc_type": {"$eq": doc_type}})

    if unit_numbers:
        if len(unit_numbers) == 1:
            clauses.append({"unit_number": {"$eq": unit_numbers[0]}})
        else:
            clauses.append({"unit_number": {"$in": unit_numbers}})

    matching_titles: set[str] = set()
    for kw in law_title_keywords:
        for key, titles in CANONICAL_LAW_TITLES.items():
            if key.lower() in kw.lower() or kw.lower() in key.lower():
                matching_titles.update(titles)

    if matching_titles:
        title_list = list(matching_titles)
        if len(title_list) == 1:
            clauses.append({"law_title": {"$eq": title_list[0]}})
        else:
            clauses.append({"law_title": {"$in": title_list}})

    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


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

        search_results = q_client.search(
            collection_name=config.QDRANT_COLLECTION,
            query_vector=qvec,
            limit=top_k
        )

        hits: list[dict[str, Any]] = []
        for point in search_results:
            payload = point.payload or {}
            chunk_id = payload.get("chunk_id", str(point.id))
            hits.append({
                "id": chunk_id,
                "score": float(point.score),
                "metadata": payload,
                "document": payload.get("text", ""),
                "source": "vector_qdrant",
            })

        logger.info("Qdrant Cloud vector search returned %d hits for query: %r", len(hits), query[:80])
        return hits
    except Exception as exc:
        logger.warning("Qdrant Cloud search error (%s); falling back to local ChromaDB.", exc)
        return None


def vector_search(
    query: str,
    model_name: str,
    db_path: str,
    collection_name: str,
    top_k: int = 15,
    doc_type: Optional[str] = None,
    law_title_keywords: Optional[list[str]] = None,
    unit_numbers: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    """
    Embed *query* and return top-k semantically similar leaf chunks.
    Tries Qdrant Cloud first if configured, falling back to local ChromaDB.
    """
    # 1. Try Qdrant Cloud if credentials exist
    if config.QDRANT_URL and config.QDRANT_API_KEY:
        q_hits = qdrant_vector_search(query=query, model_name=model_name, top_k=top_k)
        if q_hits is not None and len(q_hits) > 0:
            return q_hits

    # 2. Fallback to Local ChromaDB
    try:
        model = _get_model(model_name)
        col = _get_chroma_collection(db_path, collection_name)
        if col is None:
            return []

        qvec: list[float] = model.encode(query)

        where_filter = _build_where_filter(
            doc_type=doc_type,
            law_title_keywords=law_title_keywords or [],
            unit_numbers=unit_numbers or [],
        )

        query_kwargs: dict[str, Any] = {
            "query_embeddings": [qvec],
            "n_results": top_k,
            "include": ["metadatas", "distances", "documents"],
        }
        if where_filter:
            query_kwargs["where"] = where_filter

        results = None
        if where_filter:
            try:
                results = col.query(**query_kwargs)
                if not results or not results["ids"][0]:
                    logger.info("Filtered Chroma query returned 0 results; falling back to unfiltered search.")
                    results = None
            except Exception as exc:
                logger.warning("Chroma query with filter failed (%s); falling back to unfiltered search.", exc)
                results = None

        if results is None:
            query_kwargs.pop("where", None)
            results = col.query(**query_kwargs)

        ids = results["ids"][0]
        distances = results["distances"][0]
        metadatas = results["metadatas"][0]
        documents = results["documents"][0]

        hits: list[dict[str, Any]] = []
        for chunk_id, dist, meta, doc in zip(ids, distances, metadatas, documents):
            similarity = max(0.0, 1.0 - dist)
            hits.append({
                "id": chunk_id,
                "score": similarity,
                "metadata": meta,
                "document": doc,
                "source": "vector",
            })

        logger.debug("Local Chroma vector search returned %d hits for query: %r", len(hits), query[:80])
        return hits
    except Exception as err:
        logger.error("Local Chroma search failed: %s", err)
        return []
