"""
retrieval/reranker.py
~~~~~~~~~~~~~~~~~~~~~~
Cross-encoder reranker using a small, CPU-friendly model:
    cross-encoder/ms-marco-MiniLM-L-6-v2

The cross-encoder scores each (query, document) pair jointly, producing a
much more accurate relevance signal than bi-encoder similarity alone.

Configuration
-------------
RERANKER_ENABLED   (config.py bool)  – set False to skip reranking
RERANKER_MODEL     (config.py str)   – HuggingFace model identifier
RERANKER_TOP_K     (config.py int)   – how many fused candidates to rerank

The module degrades gracefully: if sentence-transformers is unavailable or
reranking is disabled it passes the fused list through unchanged.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)

# Default cross-encoder model (small, CPU-friendly, free)
DEFAULT_RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


@lru_cache(maxsize=1)
def _load_cross_encoder(model_name: str):
    """Lazily load and cache the CrossEncoder model."""
    try:
        from sentence_transformers import CrossEncoder  # type: ignore
        logger.info("Loading cross-encoder model: %s", model_name)
        model = CrossEncoder(model_name, max_length=512)
        return model
    except Exception as exc:
        logger.warning("Could not load cross-encoder (%s). Reranking disabled.", exc)
        return None


def rerank(
    query: str,
    candidates: list[dict[str, Any]],
    model_name: str = DEFAULT_RERANKER_MODEL,
    top_k: int = 5,
    enabled: bool = True,
) -> list[dict[str, Any]]:
    """
    Rerank *candidates* using a cross-encoder and return the top *top_k*.

    Parameters
    ----------
    query      : the original user query
    candidates : list of hybrid-fused chunk dicts (each has "document" key)
    model_name : HuggingFace cross-encoder model name
    top_k      : number of final results to return
    enabled    : if False, return candidates[:top_k] without reranking

    Returns
    -------
    Reranked list (length ≤ top_k) with an added "rerank_score" field.
    If reranking is disabled or fails, "rerank_score" is set to rrf_score.
    """
    if not candidates:
        return []

    if not enabled:
        logger.debug("Reranking disabled – returning top-%d by RRF score.", top_k)
        for c in candidates[:top_k]:
            c["rerank_score"] = c.get("rrf_score", 0.0)
        return candidates[:top_k]

    model = _load_cross_encoder(model_name)
    if model is None:
        logger.warning("Cross-encoder unavailable – falling back to RRF order.")
        for c in candidates[:top_k]:
            c["rerank_score"] = c.get("rrf_score", 0.0)
        return candidates[:top_k]

    # Build (query, document) pairs – use document text if available, else id
    pairs = [
        (query, c.get("document") or c.get("id", ""))
        for c in candidates
    ]

    try:
        scores = model.predict(pairs, show_progress_bar=False)
    except Exception as exc:
        logger.warning("Cross-encoder prediction failed (%s) – using RRF order.", exc)
        for c in candidates[:top_k]:
            c["rerank_score"] = c.get("rrf_score", 0.0)
        return candidates[:top_k]

    # Attach rerank scores and sort
    for c, score in zip(candidates, scores):
        c["rerank_score"] = float(score)

    candidates.sort(key=lambda x: x["rerank_score"], reverse=True)

    logger.debug(
        "Reranking complete: top score=%.4f, bottom score=%.4f (of %d candidates)",
        candidates[0]["rerank_score"],
        candidates[min(top_k - 1, len(candidates) - 1)]["rerank_score"],
        len(candidates),
    )
    return candidates[:top_k]
