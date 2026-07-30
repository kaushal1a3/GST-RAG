"""
ingestion/loader.py
~~~~~~~~~~~~~~~~~~~~
Load raw JSON source files for GST Acts and Rules.

Validates required fields on every record; malformed records are logged and
skipped so the pipeline never crashes on bad input.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Required fields per doc_type
# ---------------------------------------------------------------------------
_ACT_REQUIRED_FIELDS: frozenset[str] = frozenset(
    ["doc_type", "title", "date", "chapter", "section",
     "section_title", "sub_section_marker", "Content"]
)
_RULE_REQUIRED_FIELDS: frozenset[str] = frozenset(
    ["doc_type", "title", "date", "chapter", "rule",
     "rule_title", "sub_rule_marker", "Content"]
)
_COMMON_REQUIRED: frozenset[str] = frozenset(["doc_type", "Content"])


def _required_fields_for(record: dict[str, Any]) -> frozenset[str]:
    """Return the set of required fields based on doc_type."""
    dtype = record.get("doc_type", "")
    if dtype == "act":
        return _ACT_REQUIRED_FIELDS
    if dtype == "rule":
        return _RULE_REQUIRED_FIELDS
    return _COMMON_REQUIRED


def _validate(record: dict[str, Any], index: int, source: str) -> list[str]:
    """Return a list of validation error messages (empty = valid)."""
    errors: list[str] = []
    dtype = record.get("doc_type")
    if dtype not in ("act", "rule"):
        errors.append(f"Unknown doc_type={dtype!r}")
        return errors  # can't do type-specific checks without a known type

    required = _required_fields_for(record)
    missing = required - record.keys()
    if missing:
        errors.append(f"Missing fields: {sorted(missing)}")

    # Ensure Content is a non-empty string
    content = record.get("Content", "")
    if not isinstance(content, str) or not content.strip():
        errors.append("Content is empty or not a string")

    return errors


def load_json_file(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Load one JSON file (a list of records).

    Returns
    -------
    valid_records : list of dicts that passed validation
    skipped       : list of dicts with an extra '_skip_reason' key for logging
    """
    logger.info("Loading %s", path)
    if not path.exists():
        raise FileNotFoundError(f"Source file not found: {path}")

    with path.open("r", encoding="utf-8") as fh:
        raw: list[dict[str, Any]] = json.load(fh)

    if not isinstance(raw, list):
        raise ValueError(f"Expected a JSON array in {path}, got {type(raw)}")

    valid: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for idx, record in enumerate(raw):
        if not isinstance(record, dict):
            skipped.append({"_index": idx, "_skip_reason": "Not a dict", "_raw": str(record)[:120]})
            continue
        errors = _validate(record, idx, str(path))
        if errors:
            skip_entry = dict(record)
            skip_entry["_index"] = idx
            skip_entry["_skip_reason"] = "; ".join(errors)
            skipped.append(skip_entry)
            logger.warning("Skipping record %d from %s: %s", idx, path.name, skip_entry["_skip_reason"])
        else:
            valid.append(record)

    logger.info(
        "  -> %d valid, %d skipped from %s",
        len(valid), len(skipped), path.name,
    )
    return valid, skipped


def load_all(
    act_path: Path,
    rule_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Convenience function to load both act and rule source files.

    Returns
    -------
    all_valid  : combined list of valid records (acts first, then rules)
    all_skipped: combined list of skipped records
    act_valid  : valid act records only (useful for per-type stats)
    """
    act_valid, act_skipped = load_json_file(act_path)
    rule_valid, rule_skipped = load_json_file(rule_path)

    all_valid = act_valid + rule_valid
    all_skipped = act_skipped + rule_skipped

    logger.info(
        "Total loaded: %d records (%d acts, %d rules); %d skipped",
        len(all_valid), len(act_valid), len(rule_valid), len(all_skipped),
    )
    return all_valid, all_skipped, act_valid
