"""
ingestion/normalizer.py
~~~~~~~~~~~~~~~~~~~~~~~~
Produce a UNIFIED record schema from the raw act and rule records.

Unified schema
--------------
{
  "id":              str   – deterministic slug built from title+unit+sub_marker
  "doc_type":        "act" | "rule"
  "law_title":       str   – cleaned title (no embedded newlines)
  "chapter":         str   – cleaned chapter heading
  "unit_number":     str   – e.g. "16" extracted from "Section 16." / "Rule 36."
  "unit_title":      str | None  – None when the title is "Untitled"
  "sub_unit_marker": str   – e.g. "(1)", "(2)(a)", "Intro/General"
  "text":            str   – the Content field, whitespace-normalised but legally intact
  "date":            str
}

Design notes
------------
* Whitespace is normalised (no leading/trailing, internal runs collapsed) but
  the actual legal wording (words, punctuation, citations) is NOT altered.
* The ID is deterministic so re-running produces the same IDs and ChromaDB
  upserts stay idempotent.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_ws(text: str) -> str:
    """
    Collapse whitespace runs (including newlines) to single spaces and strip.
    Legal words are preserved exactly.
    """
    return re.sub(r"\s+", " ", text).strip()


def _extract_number(raw: str) -> str:
    """
    Extract the numeric / alphanumeric identifier from strings like
    'Section 16.', 'Rule 36.', 'Section 2A.', 'Article 246A.'.
    Falls back to the cleaned raw string if no number is found.
    """
    # Match optional word prefix, then the identifier (digits + optional letters)
    m = re.search(r"(\d+[A-Za-z]*)", raw)
    if m:
        return m.group(1)
    return _clean_ws(raw)


def _make_slug(*parts: str) -> str:
    """
    Build a URL/filesystem-safe slug from arbitrary string parts.
    Uses SHA-1 of the joined lowercased key so IDs remain short and stable.
    """
    key = "|".join(_clean_ws(p).lower() for p in parts)
    # Replace non-alphanumeric with hyphens for readability (first 80 chars)
    readable = re.sub(r"[^a-z0-9]+", "-", key)[:80].strip("-")
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]
    return f"{readable}-{digest}"


def normalize_record(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Convert a single raw record (act or rule) into the unified schema.

    Parameters
    ----------
    raw : dict with either act-schema or rule-schema fields

    Returns
    -------
    Unified record dict.
    """
    dtype: str = raw["doc_type"]
    law_title = _clean_ws(raw.get("title", ""))
    chapter = _clean_ws(raw.get("chapter", ""))
    date = _clean_ws(raw.get("date", ""))
    content = _clean_ws(raw.get("Content", ""))

    if dtype == "act":
        raw_unit = raw.get("section", "")
        raw_title = raw.get("section_title", "")
        raw_marker = raw.get("sub_section_marker", "")
    else:  # "rule"
        raw_unit = raw.get("rule", "")
        raw_title = raw.get("rule_title", "")
        raw_marker = raw.get("sub_rule_marker", "")

    unit_number = _extract_number(raw_unit)
    raw_unit_clean = _clean_ws(raw_unit)

    unit_title_raw = _clean_ws(raw_title)
    unit_title: str | None = None if unit_title_raw.lower() in ("untitled", "") else unit_title_raw

    sub_unit_marker = _clean_ws(raw_marker)

    record_id = _make_slug(law_title, raw_unit_clean, sub_unit_marker)

    return {
        "id": record_id,
        "doc_type": dtype,
        "law_title": law_title,
        "chapter": chapter,
        "unit_number": unit_number,
        "unit_title": unit_title,
        "sub_unit_marker": sub_unit_marker,
        "text": content,
        "date": date,
        # Keep the raw unit string too (useful for citations)
        "raw_unit": raw_unit_clean,
    }


def normalize_all(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Normalise a list of raw records into unified schema.

    Returns
    -------
    normalized : list of unified records
    warnings   : list of warning strings for duplicate IDs (de-duplicated by
                 appending a counter suffix so every ID is unique)
    """
    normalized: list[dict[str, Any]] = []
    seen_ids: dict[str, int] = {}
    warnings: list[str] = []

    for raw in records:
        norm = normalize_record(raw)
        base_id = norm["id"]

        if base_id in seen_ids:
            seen_ids[base_id] += 1
            new_id = f"{base_id}-{seen_ids[base_id]}"
            warnings.append(
                f"Duplicate ID {base_id!r} -> renamed to {new_id!r} "
                f"(law={norm['law_title']!r}, unit={norm['raw_unit']!r}, "
                f"marker={norm['sub_unit_marker']!r})"
            )
            norm["id"] = new_id
        else:
            seen_ids[base_id] = 0

        normalized.append(norm)

    return normalized, warnings
