"""
retrieval/keyword_search.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
BM25 keyword / exact-match search over leaf chunks.

Loads the pickled BM25Okapi index and the ordered ID list produced by
ingestion/build_index.py, tokenises the query identically to ingestion,
and returns top-k results by BM25 score.
"""
from __future__ import annotations

import json
import logging
import pickle
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tokeniser (must match ingestion/build_index.py exactly)
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    """Lowercase + split on non-alphanumeric characters."""
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if t]


# ---------------------------------------------------------------------------
# Lazy singleton – load BM25 index once per process
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_bm25_index(bm25_path: str, ids_path: str):
    """Load and cache the BM25 index and ID list from disk."""
    logger.info("Loading BM25 index from %s …", bm25_path)
    with open(bm25_path, "rb") as fh:
        bm25 = pickle.load(fh)
    with open(ids_path, "r", encoding="utf-8") as fh:
        ids: list[str] = json.load(fh)
    logger.info("BM25 index loaded: %d documents.", len(ids))
    return bm25, ids


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def keyword_search(
    query: str,
    bm25_path: str,
    ids_path: str,
    top_k: int = 15,
) -> list[dict[str, Any]]:
    """
    Run BM25 keyword search against all leaf chunks.

    Parameters
    ----------
    query     : natural-language query string (will be tokenised)
    bm25_path : path to the pickled BM25Okapi object
    ids_path  : path to the JSON list of chunk IDs (aligned with BM25 corpus)
    top_k     : number of top results to return

    Returns
    -------
    List of result dicts sorted by descending BM25 score:
        { id: str, score: float, rank: int, source: "bm25" }
    """
    bm25, ids = _load_bm25_index(bm25_path, ids_path)

    tokens = _tokenize(query)
    if not tokens:
        logger.warning("keyword_search: query tokenised to empty list: %r", query)
        return []

    scores: np.ndarray = bm25.get_scores(tokens)

    # Get top-k indices (descending score)
    top_indices = np.argsort(scores)[::-1][:top_k]

    hits: list[dict[str, Any]] = []
    for rank, idx in enumerate(top_indices):
        score = float(scores[idx])
        if score <= 0.0:
            break  # no more relevant hits
        hits.append({
            "id": ids[int(idx)],
            "score": score,
            "rank": rank + 1,
            "source": "bm25",
        })

    logger.debug(
        "BM25 search returned %d hits (top score=%.4f) for query: %r",
        len(hits), hits[0]["score"] if hits else 0.0, query[:80],
    )
    return hits
