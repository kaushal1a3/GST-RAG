"""
generation/lc_tools.py
~~~~~~~~~~~~~~~~~~~~~~
LangChain Tool definitions for the GST RAG Agentic loop.

Three tools are exposed to the LLM:
  1. hybrid_gst_search        – full hybrid (vector + BM25 + rerank) pipeline
  2. lookup_specific_section  – targeted search by a named Section / Rule number
  3. get_parent_section_text  – fetch the full parent section text for a known chunk ID

All tools wrap the existing retrieval/ pipeline functions with zero duplication.
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import config
from langchain.tools import tool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: format chunks for LLM consumption
# ---------------------------------------------------------------------------

def _format_chunks(chunks: list[dict[str, Any]], max_chars: int = 3000) -> str:
    """Render retrieved chunks as a compact text block for the LLM."""
    if not chunks:
        return "No relevant GST provisions found."

    parts: list[str] = []
    total = 0
    for i, c in enumerate(chunks, 1):
        meta = c.get("metadata", {})
        law = c.get("parent_law_title") or meta.get("law_title", "GST Law")
        unit = c.get("parent_raw_unit") or meta.get("raw_unit", "N/A")
        marker = meta.get("sub_unit_marker", "")
        chunk_id = c.get("id", "")
        text = c.get("expanded_context") or c.get("document", "")

        entry = (
            f"--- [{i}] {law} | {unit} {marker} ---\n"
            f"chunk_id: {chunk_id}\n"
            f"{text.strip()}\n"
        )
        if total + len(entry) > max_chars:
            parts.append("[...further results truncated to stay within context limit]")
            break
        parts.append(entry)
        total += len(entry)

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Tool 1: Hybrid GST Search (primary retrieval tool)
# ---------------------------------------------------------------------------

@tool
def hybrid_gst_search(query: str) -> str:
    """
    Search the Indian GST legal corpus (Acts + Rules) using a hybrid
    vector + BM25 retrieval pipeline with cross-encoder reranking.

    Use this tool when:
    - The user asks a general GST question.
    - You need to find which section/rule covers a particular topic.
    - You are unsure which specific section to look up.

    Input: A natural-language GST question or keyword phrase.
    Output: Top matching GST provisions with law title, section/rule number,
            sub-clause marker, and full legal text.
    """
    logger.info("[Tool] hybrid_gst_search | query=%r", query[:120])
    try:
        from retrieval.pipeline import retrieve
        chunks = retrieve(query=query, final_top_k=config.RERANKER_TOP_K)
        return _format_chunks(chunks)
    except Exception as exc:
        logger.error("[Tool] hybrid_gst_search failed: %s", exc)
        return f"Search failed: {exc}"


# ---------------------------------------------------------------------------
# Tool 2: Targeted Section / Rule Lookup
# ---------------------------------------------------------------------------

@tool
def lookup_specific_section(section_query: str) -> str:
    """
    Look up a specific named Section or Rule in the Indian GST law corpus.

    Use this tool when:
    - The user explicitly mentions a Section number (e.g., "Section 16", "Section 47").
    - The user mentions a specific Rule (e.g., "Rule 36", "Rule 42").
    - A previous search result references a section that you need more detail about.

    Input: A string containing the section/rule reference AND a brief topic description.
           Examples:
             "Section 16 CGST ITC eligibility"
             "Section 47 CGST penalty late filing"
             "Rule 36 CGST Rules input tax credit"

    Output: The full text of the matching section/rule provisions with citations.
    """
    logger.info("[Tool] lookup_specific_section | section_query=%r", section_query[:120])
    try:
        from retrieval.pipeline import retrieve
        # Use a tighter final_top_k since we are targeting a specific section
        chunks = retrieve(query=section_query, final_top_k=3)
        return _format_chunks(chunks)
    except Exception as exc:
        logger.error("[Tool] lookup_specific_section failed: %s", exc)
        return f"Section lookup failed: {exc}"


# ---------------------------------------------------------------------------
# Tool 3: Get Full Parent Section Text by chunk_id
# ---------------------------------------------------------------------------

@tool
def get_parent_section_text(chunk_id: str) -> str:
    """
    Retrieve the complete full-section text for a known GST chunk ID.

    Use this tool when:
    - A previous search result gave you a chunk_id but you need the FULL parent
      section context (not just the sub-clause snippet).
    - You need to verify surrounding clauses within the same section.

    Input: The exact chunk_id string returned by a previous search tool call.
           Example: "central-goods-and-services-tax-act-2017-section-16-1-a1b2c3"

    Output: The complete parent section text with law title and section number.
    """
    logger.info("[Tool] get_parent_section_text | chunk_id=%r", chunk_id[:120])
    try:
        from retrieval.context_expander import expand_with_parent
        # Build a minimal chunk stub so expand_with_parent can resolve it
        stub = [{"id": chunk_id.strip(), "metadata": {}, "document": ""}]
        expanded = expand_with_parent(
            final_chunks=stub,
            parent_chunks_path=str(config.PARENT_CHUNKS_FILE),
            leaf_to_parent_path=str(config.LEAF_TO_PARENT_MAP_FILE),
        )
        if not expanded:
            return f"Could not find parent section for chunk_id: {chunk_id!r}"

        c = expanded[0]
        law = c.get("parent_law_title", "GST Law")
        unit = c.get("parent_raw_unit", "N/A")
        text = c.get("expanded_context") or c.get("document", "")
        return f"[{law} | {unit}]\n\n{text.strip()}"
    except Exception as exc:
        logger.error("[Tool] get_parent_section_text failed: %s", exc)
        return f"Failed to retrieve parent section text: {exc}"


# ---------------------------------------------------------------------------
# Public list of all agent tools
# ---------------------------------------------------------------------------

GST_AGENT_TOOLS = [
    hybrid_gst_search,
    lookup_specific_section,
    get_parent_section_text,
]
