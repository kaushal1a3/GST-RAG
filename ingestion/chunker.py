"""
ingestion/chunker.py
~~~~~~~~~~~~~~~~~~~~~
Produce two granularities of chunk from the normalised records.

LEAF chunks
-----------
One per normalised record (sub-section / sub-rule granularity).
These are what get embedded and stored in the vector index.

PARENT chunks
-------------
All leaf records that share the same (law_title, chapter, unit_number) are
grouped and their texts concatenated in original order to form one "full
section" or "full rule" document.  The parent_id follows the same slug
convention as leaf IDs.

Outputs
-------
data/processed/leaf_chunks.json        – list of leaf chunk dicts
data/processed/parent_chunks.json      – list of parent chunk dicts
data/processed/leaf_to_parent_map.json – {leaf_id: parent_id}
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parent_slug(law_title: str, chapter: str, unit_number: str) -> str:
    """Deterministic slug for a parent chunk."""
    key = f"{law_title.lower()}|{chapter.lower()}|{unit_number.lower()}"
    readable = re.sub(r"[^a-z0-9]+", "-", key)[:80].strip("-")
    digest = hashlib.sha1(key.encode()).hexdigest()[:8]
    return f"parent-{readable}-{digest}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_chunks(
    normalized_records: list[dict[str, Any]],
) -> tuple[
    list[dict[str, Any]],   # leaf_chunks
    list[dict[str, Any]],   # parent_chunks
    dict[str, str],          # leaf_to_parent_map
]:
    """
    Build leaf chunks, parent chunks, and the leaf→parent mapping.

    Parameters
    ----------
    normalized_records : output of normalizer.normalize_all

    Returns
    -------
    leaf_chunks        : each normalised record augmented with parent_id
    parent_chunks      : aggregated full-section / full-rule documents
    leaf_to_parent_map : {leaf_id: parent_id}
    """
    # 1. Group leaves by (law_title, chapter, unit_number) while preserving order
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for rec in normalized_records:
        key = (rec["law_title"], rec["chapter"], rec["unit_number"])
        groups[key].append(rec)

    leaf_chunks: list[dict[str, Any]] = []
    parent_chunks: list[dict[str, Any]] = []
    leaf_to_parent_map: dict[str, str] = {}

    for (law_title, chapter, unit_number), members in groups.items():
        # Build parent
        parent_id = _parent_slug(law_title, chapter, unit_number)
        combined_text = "\n\n".join(m["text"] for m in members)

        # Use first member for representative metadata
        first = members[0]
        parent_chunk: dict[str, Any] = {
            "id": parent_id,
            "doc_type": first["doc_type"],
            "law_title": law_title,
            "chapter": chapter,
            "unit_number": unit_number,
            "raw_unit": first.get("raw_unit", ""),
            "unit_title": first.get("unit_title"),
            "date": first.get("date", ""),
            "text": combined_text,
            "leaf_ids": [m["id"] for m in members],
            "num_leaves": len(members),
        }
        parent_chunks.append(parent_chunk)

        # Augment each leaf with its parent_id
        for member in members:
            leaf = dict(member)
            leaf["parent_id"] = parent_id
            leaf_chunks.append(leaf)
            leaf_to_parent_map[leaf["id"]] = parent_id

    logger.info(
        "Chunking complete: %d leaf chunks, %d parent chunks",
        len(leaf_chunks), len(parent_chunks),
    )
    return leaf_chunks, parent_chunks, leaf_to_parent_map


def save_chunks(
    leaf_chunks: list[dict[str, Any]],
    parent_chunks: list[dict[str, Any]],
    leaf_to_parent_map: dict[str, str],
    processed_dir: Path,
) -> None:
    """Persist all three artefacts as JSON to *processed_dir*."""
    processed_dir.mkdir(parents=True, exist_ok=True)

    leaf_path = processed_dir / "leaf_chunks.json"
    parent_path = processed_dir / "parent_chunks.json"
    map_path = processed_dir / "leaf_to_parent_map.json"

    with leaf_path.open("w", encoding="utf-8") as fh:
        json.dump(leaf_chunks, fh, ensure_ascii=False, indent=2)
    logger.info("Saved %d leaf chunks -> %s", len(leaf_chunks), leaf_path)

    with parent_path.open("w", encoding="utf-8") as fh:
        json.dump(parent_chunks, fh, ensure_ascii=False, indent=2)
    logger.info("Saved %d parent chunks -> %s", len(parent_chunks), parent_path)

    with map_path.open("w", encoding="utf-8") as fh:
        json.dump(leaf_to_parent_map, fh, ensure_ascii=False, indent=2)
    logger.info("Saved leaf→parent map (%d entries) -> %s", len(leaf_to_parent_map), map_path)


def load_chunks(
    processed_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, str]]:
    """Reload persisted chunk artefacts from disk."""
    leaf_path = processed_dir / "leaf_chunks.json"
    parent_path = processed_dir / "parent_chunks.json"
    map_path = processed_dir / "leaf_to_parent_map.json"

    with leaf_path.open("r", encoding="utf-8") as fh:
        leaf_chunks: list[dict[str, Any]] = json.load(fh)
    with parent_path.open("r", encoding="utf-8") as fh:
        parent_chunks: list[dict[str, Any]] = json.load(fh)
    with map_path.open("r", encoding="utf-8") as fh:
        leaf_to_parent_map: dict[str, str] = json.load(fh)

    return leaf_chunks, parent_chunks, leaf_to_parent_map
