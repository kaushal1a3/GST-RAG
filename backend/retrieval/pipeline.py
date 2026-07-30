"""
retrieval/pipeline.py
~~~~~~~~~~~~~~~~~~~~~~
High-level retrieval pipeline that wires together:
    query_parser → vector_search → keyword_search
    → hybrid_retriever → reranker → context_expander

Usage
-----
    from retrieval.pipeline import retrieve

    results = retrieve("What does Section 16 CGST say about ITC eligibility?")
    for r in results:
        print(r["parent_raw_unit"], r["parent_law_title"])
        print(r["expanded_context"][:300])
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import config
from retrieval.query_parser import parse_query, ParsedQuery
from retrieval.query_rewriter import rewrite_query
from retrieval.vector_search import vector_search
from retrieval.keyword_search import keyword_search
from retrieval.hybrid_retriever import hybrid_retrieve
from retrieval.reranker import rerank
from retrieval.context_expander import expand_with_parent

logger = logging.getLogger(__name__)


def retrieve(
    query: str,
    vector_top_k: int | None = None,
    bm25_top_k: int | None = None,
    reranker_candidates: int | None = None,
    final_top_k: int | None = None,
    reranker_enabled: bool | None = None,
) -> list[dict[str, Any]]:
    """
    Full retrieval pipeline for a GST query.

    Parameters
    ----------
    query               : natural-language question
    vector_top_k        : override config.VECTOR_TOP_K
    bm25_top_k          : override config.BM25_TOP_K
    reranker_candidates : override config.RERANKER_CANDIDATES (fused pool)
    final_top_k         : override config.RERANKER_TOP_K (returned results)
    reranker_enabled    : override config.RERANKER_ENABLED

    Returns
    -------
    List of final chunk dicts (length ≤ final_top_k), each with:
        id, metadata, document, rrf_score, rerank_score,
        expanded_context, parent_id, parent_found,
        parent_law_title, parent_raw_unit, parent_unit_number
    """
    # --- Resolve parameters from config defaults ---
    _vtk = vector_top_k or config.VECTOR_TOP_K
    _btk = bm25_top_k or config.BM25_TOP_K
    _rc = reranker_candidates or config.RERANKER_CANDIDATES
    _ftk = final_top_k or config.RERANKER_TOP_K
    _re = reranker_enabled if reranker_enabled is not None else config.RERANKER_ENABLED

    logger.info("Retrieval pipeline | query=%r", query[:120])

    # 1. Parse query
    parsed: ParsedQuery = parse_query(query)
    logger.info(
        "  Parsed: sections=%s rules=%s acts=%s",
        parsed.mentioned_sections, parsed.mentioned_rules, parsed.mentioned_acts,
    )

    filters = parsed.filters
    doc_type = filters.get("doc_type")
    law_kws = filters.get("law_title_keywords", [])
    unit_nums = filters.get("unit_numbers", [])

    # 2. Rewrite query (do NOT send raw conversational query directly to vector DB)
    search_query = rewrite_query(query, parsed=parsed)

    # 3. Vector search using preprocessed search query
    v_hits = vector_search(
        query=search_query,
        model_name=config.EMBEDDING_MODEL_NAME,
        db_path=str(config.CHROMA_DB_DIR),
        collection_name=config.CHROMA_COLLECTION_NAME,
        top_k=_vtk,
        doc_type=doc_type,
        law_title_keywords=law_kws,
        unit_numbers=unit_nums,
    )
    logger.info("  Vector hits: %d", len(v_hits))

    # 4. BM25 search using preprocessed search query
    b_hits = keyword_search(
        query=search_query,
        bm25_path=str(config.BM25_INDEX_FILE),
        ids_path=str(config.BM25_IDS_FILE),
        top_k=_btk,
    )
    logger.info("  BM25 hits: %d", len(b_hits))

    # 4. Hybrid fusion
    fused = hybrid_retrieve(
        query=query,
        parsed_query=parsed,
        vector_hits=v_hits,
        bm25_hits=b_hits,
        vector_weight=config.VECTOR_WEIGHT,
        bm25_weight=config.BM25_WEIGHT,
        rrf_k=config.RRF_K,
        top_n=_rc,
        leaf_chunks_path=str(config.LEAF_CHUNKS_FILE),
        citation_boost=config.CITATION_BOOST,
    )
    logger.info("  Fused candidates: %d", len(fused))

    # 5. Rerank
    reranked = rerank(
        query=query,
        candidates=fused,
        model_name=config.RERANKER_MODEL,
        top_k=_ftk,
        enabled=_re,
    )
    logger.info("  Final after reranking: %d", len(reranked))

    # 6. Parent expansion
    expanded = expand_with_parent(
        final_chunks=reranked,
        parent_chunks_path=str(config.PARENT_CHUNKS_FILE),
        leaf_to_parent_path=str(config.LEAF_TO_PARENT_MAP_FILE),
    )

    return expanded
