"""
retrieval/hybrid_retriever.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Fuse vector and BM25 results using weighted Reciprocal Rank Fusion (RRF),
with citation-boosting for queries that mention explicit section/rule numbers or acts.

Loads full leaf metadata from leaf_chunks.json so BM25 hits always have complete,
accurate metadata (law_title, unit_number, raw_unit, sub_unit_marker, doc_type).
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any, Optional

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_leaf_metadata(leaf_chunks_path: str) -> dict[str, dict[str, Any]]:
    """Load leaf_chunks.json and index metadata by chunk id.
    Returns an empty dict if the file does not exist (e.g. on Vercel serverless);
    in that case metadata from vector-hit payloads is used directly.
    """
    from pathlib import Path
    if not Path(leaf_chunks_path).exists():
        logger.warning(
            "leaf_chunks.json not found at %s — metadata will be sourced "
            "from vector hit payloads only.",
            leaf_chunks_path,
        )
        return {}
    with open(leaf_chunks_path, "r", encoding="utf-8") as fh:
        chunks: list[dict[str, Any]] = json.load(fh)
    logger.info("Loaded metadata index for %d leaf chunks.", len(chunks))
    return {c["id"]: c for c in chunks}



def _rrf_score(rank: int, k: int) -> float:
    """Standard Reciprocal Rank Fusion score for a given rank (1-based)."""
    return 1.0 / (k + rank)


def fuse_results(
    vector_hits: list[dict[str, Any]],
    bm25_hits: list[dict[str, Any]],
    vector_weight: float,
    bm25_weight: float,
    rrf_k: int,
    top_n: int,
    leaf_chunks_path: str = "data/processed/leaf_chunks.json",
    mentioned_unit_numbers: Optional[list[str]] = None,
    mentioned_acts: Optional[list[str]] = None,
    citation_boost: float = 3.0,
    act_boost: float = 1.5,
) -> list[dict[str, Any]]:
    """
    Fuse vector and BM25 result lists using weighted RRF.
    """
    leaf_meta_map = _load_leaf_metadata(leaf_chunks_path)

    # Build rank maps (1-based)
    vector_rank_map: dict[str, int] = {h["id"]: i + 1 for i, h in enumerate(vector_hits)}
    bm25_rank_map: dict[str, int] = {h["id"]: i + 1 for i, h in enumerate(bm25_hits)}
    vector_score_map: dict[str, float] = {h["id"]: h["score"] for h in vector_hits}
    bm25_score_map: dict[str, float] = {h["id"]: h["score"] for h in bm25_hits}
    vector_doc_map: dict[str, str] = {h["id"]: h.get("document", "") for h in vector_hits}

    all_ids: set[str] = set(vector_rank_map) | set(bm25_rank_map)
    max_rank = max(len(vector_hits), len(bm25_hits), 1) + 1

    cited_units = set(mentioned_unit_numbers or [])
    cited_acts = [a.lower() for a in (mentioned_acts or [])]

    fused: list[dict[str, Any]] = []
    for chunk_id in all_ids:
        v_rank = vector_rank_map.get(chunk_id, max_rank)
        b_rank = bm25_rank_map.get(chunk_id, max_rank)

        rrf = (
            vector_weight * _rrf_score(v_rank, rrf_k)
            + bm25_weight * _rrf_score(b_rank, rrf_k)
        )

        # Get authoritative metadata: prefer leaf_chunks.json, fall back to hit payload
        full_leaf = leaf_meta_map.get(chunk_id, {})

        # When leaf_chunks.json is unavailable (Vercel), use metadata from vector hit payload
        hit_meta: dict = {}
        for hit in (*vector_hits, *bm25_hits):
            if hit["id"] == chunk_id:
                hit_meta = hit.get("metadata", {})
                break

        def _get(key: str, default: str = "") -> str:
            return full_leaf.get(key) or hit_meta.get(key, default)

        meta = {
            "doc_type":        _get("doc_type"),
            "law_title":       _get("law_title"),
            "chapter":         _get("chapter"),
            "unit_number":     _get("unit_number"),
            "raw_unit":        _get("raw_unit"),
            "unit_title":      full_leaf.get("unit_title") or hit_meta.get("unit_title"),
            "sub_unit_marker": _get("sub_unit_marker"),
            "date":            _get("date"),
            "parent_id":       _get("parent_id"),
        }
        document_text = (
            full_leaf.get("text")
            or hit_meta.get("text")
            or vector_doc_map.get(chunk_id, "")
        )

        unit_number = meta["unit_number"]
        law_title = meta["law_title"].lower()

        # Citation boost – multiply score if chunk's unit_number is explicitly mentioned
        is_unit_boosted = False
        if cited_units and unit_number in cited_units:
            rrf *= citation_boost
            is_unit_boosted = True

        # Act boost – multiply score if chunk's law_title matches mentioned act keyword
        if cited_acts:
            for act_kw in cited_acts:
                if act_kw in law_title:
                    rrf *= act_boost
                    break

        fused.append({
            "id": chunk_id,
            "rrf_score": rrf,
            "vector_rank": v_rank,
            "bm25_rank": b_rank,
            "vector_score": vector_score_map.get(chunk_id, 0.0),
            "bm25_score": bm25_score_map.get(chunk_id, 0.0),
            "metadata": meta,
            "document": document_text,
            "citation_boosted": is_unit_boosted,
        })

    fused.sort(key=lambda x: x["rrf_score"], reverse=True)
    return fused[:top_n]


def hybrid_retrieve(
    query: str,
    parsed_query,
    vector_hits: list[dict[str, Any]],
    bm25_hits: list[dict[str, Any]],
    vector_weight: float,
    bm25_weight: float,
    rrf_k: int,
    top_n: int,
    leaf_chunks_path: str = "data/processed/leaf_chunks.json",
    citation_boost: float = 3.0,
    act_boost: float = 1.5,
) -> list[dict[str, Any]]:
    """
    High-level hybrid retrieval entry point.
    """
    mentioned_units = parsed_query.filters.get("unit_numbers", []) if parsed_query else []
    mentioned_acts = parsed_query.filters.get("law_title_keywords", []) if parsed_query else []

    results = fuse_results(
        vector_hits=vector_hits,
        bm25_hits=bm25_hits,
        vector_weight=vector_weight,
        bm25_weight=bm25_weight,
        rrf_k=rrf_k,
        top_n=top_n,
        leaf_chunks_path=leaf_chunks_path,
        mentioned_unit_numbers=mentioned_units,
        mentioned_acts=mentioned_acts,
        citation_boost=citation_boost,
        act_boost=act_boost,
    )

    logger.debug(
        "Hybrid retrieval: %d vector + %d bm25 → %d fused (top rrf=%.4f)",
        len(vector_hits), len(bm25_hits), len(results),
        results[0]["rrf_score"] if results else 0.0,
    )
    return results
