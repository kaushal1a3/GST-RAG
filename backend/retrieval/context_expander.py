"""
retrieval/context_expander.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Parent-chunk expansion.

For each final leaf chunk returned by reranking, look up its parent_id from
the leaf_to_parent_map and attach the FULL parent section/rule text as
`expanded_context`.  This gives the LLM complete legal context rather than
an isolated sub-clause.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_parent_data(parent_path: str, map_path: str):
    """Load and cache parent chunks and the leaf→parent map from disk.
    Returns (empty_dict, empty_dict) if files do not exist (e.g. on Vercel serverless);
    chunks will fall back to using their own document text as expanded_context.
    """
    if not Path(parent_path).exists() or not Path(map_path).exists():
        logger.warning(
            "Parent chunk files not found (%s / %s) — parent expansion disabled. "
            "Each chunk's own text will be used as context.",
            parent_path, map_path,
        )
        return {}, {}

    with open(parent_path, "r", encoding="utf-8") as fh:
        parent_chunks: list[dict] = json.load(fh)
    with open(map_path, "r", encoding="utf-8") as fh:
        leaf_to_parent: dict[str, str] = json.load(fh)

    # Build parent lookup dict for O(1) access
    parent_lookup: dict[str, dict] = {p["id"]: p for p in parent_chunks}

    logger.info(
        "Context expander loaded: %d parent chunks, %d leaf→parent mappings.",
        len(parent_lookup), len(leaf_to_parent),
    )
    return parent_lookup, leaf_to_parent



def expand_with_parent(
    final_chunks: list[dict[str, Any]],
    parent_chunks_path: str,
    leaf_to_parent_path: str,
) -> list[dict[str, Any]]:
    """
    Attach `expanded_context` and `parent_id` to each chunk in *final_chunks*.

    Parameters
    ----------
    final_chunks          : list of reranked leaf chunk dicts (each has "id" key)
    parent_chunks_path    : path to parent_chunks.json
    leaf_to_parent_path   : path to leaf_to_parent_map.json

    Returns
    -------
    Same list, each dict augmented with:
        parent_id          : str  – id of the parent chunk
        parent_found       : bool – True if parent was located
        expanded_context   : str  – full text of the parent section/rule
        parent_law_title   : str  – law title from parent (for citation)
        parent_unit_number : str  – unit number from parent (for citation)
        parent_raw_unit    : str  – raw unit string e.g. "Section 16."
    """
    parent_lookup, leaf_to_parent = _load_parent_data(
        parent_chunks_path, leaf_to_parent_path
    )

    for chunk in final_chunks:
        leaf_id = chunk.get("id", "")
        # parent_id may already be in metadata (from ChromaDB hit)
        parent_id = (
            chunk.get("metadata", {}).get("parent_id")
            or leaf_to_parent.get(leaf_id)
        )

        if not parent_id or parent_id not in parent_lookup:
            chunk["parent_id"] = parent_id or ""
            chunk["parent_found"] = False
            chunk["expanded_context"] = chunk.get("document", "")
            chunk["parent_law_title"] = chunk.get("metadata", {}).get("law_title", "")
            chunk["parent_unit_number"] = chunk.get("metadata", {}).get("unit_number", "")
            chunk["parent_raw_unit"] = chunk.get("metadata", {}).get("raw_unit", "")
            logger.debug("Parent not found for leaf: %s (parent_id=%s)", leaf_id, parent_id)
            continue

        parent = parent_lookup[parent_id]
        chunk["parent_id"] = parent_id
        chunk["parent_found"] = True
        chunk["expanded_context"] = parent["text"]
        chunk["parent_law_title"] = parent.get("law_title", "")
        chunk["parent_unit_number"] = parent.get("unit_number", "")
        chunk["parent_raw_unit"] = parent.get("raw_unit", "")

    expanded_count = sum(1 for c in final_chunks if c.get("parent_found"))
    logger.debug(
        "Parent expansion: %d/%d chunks expanded successfully.",
        expanded_count, len(final_chunks),
    )
    return final_chunks
