"""
retrieval/query_rewriter.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Pre-processes and rewrites raw user queries into dense, domain-specific search queries.
Ensures the raw/conversational user query is not sent directly to vector DB.

Transformations:
1. Strips conversational fluff and filler phrases ("can you explain", "hi", "tell me about", etc.).
2. Expands domain acronyms (ITC -> Input Tax Credit ITC, CGST -> Central Goods and Services Tax, RCM, etc.).
3. Formats explicit section, rule, and act references into standardized legal search terms.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from retrieval.query_parser import ParsedQuery

logger = logging.getLogger(__name__)

# Common conversational noise prefixes/phrases to strip out
CONVERSATIONAL_PATTERNS: list[str] = [
    r"^\s*(?:hi|hello|hey|greetings|dear\s+assistant)[,\s!.]*",
    r"\b(?:can\s+you\s+(?:please\s+)?(?:tell|explain|show|help|find|provide|describe)(?:\s+me)?)\b",
    r"\b(?:could\s+you\s+(?:please\s+)?(?:tell|explain|show|help|find|provide|describe)(?:\s+me)?)\b",
    r"\b(?:please\s+(?:tell|explain|show|help|find|provide|describe)(?:\s+me)?)\b",
    r"\b(?:i\s+(?:want|would\s+like|need)\s+to\s+(?:know|understand|find))\b",
    r"\b(?:what\s+is|what\s+are|how\s+does|how\s+do|is\s+there|what\s+does|which\s+section|which\s+rule)\b",
    r"\b(?:tell\s+me\s+about|says\s+about|talks\s+about|give\s+details\s+of|details\s+on)\b",
]

# Map of domain acronyms to expanded legal terms for improved vector alignment
ACRONYM_MAP: dict[str, str] = {
    r"\bitc\b": "Input Tax Credit ITC",
    r"\bcgst\b": "Central Goods and Services Tax CGST",
    r"\bigst\b": "Integrated Goods and Services Tax IGST",
    r"\butgst\b": "Union Territory Goods and Services Tax UTGST",
    r"\bsgst\b": "State Goods and Services Tax SGST",
    r"\bgst\b": "Goods and Services Tax GST",
    r"\brcm\b": "Reverse Charge Mechanism RCM",
    r"\bgstr\b": "Goods and Services Tax Return GSTR",
    r"\beinvoice\b|\be-invoice\b": "Electronic Invoice e-invoicing",
    r"\beway\b|\be-way\b": "E-Way Bill electronic way bill",
}


def rewrite_query(
    raw_query: str,
    parsed: Optional[ParsedQuery] = None,
) -> str:
    """
    Transform a raw user query into an optimized, dense legal search query for vector search.

    Parameters
    ----------
    raw_query : original natural-language query from the user
    parsed    : ParsedQuery object (optional) containing extracted sections/rules/acts

    Returns
    -------
    Rewritten query string optimized for vector embedding similarity and keyword retrieval.
    """
    cleaned = raw_query.strip()

    # 1. Strip conversational fluff
    for pattern in CONVERSATIONAL_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()

    # 2. Expand common GST acronyms
    rewritten = cleaned
    for pattern, expansion in ACRONYM_MAP.items():
        rewritten = re.sub(pattern, expansion, rewritten, flags=re.IGNORECASE)

    # 3. Incorporate explicit section/rule references from ParsedQuery if available
    if parsed and parsed.has_explicit_refs():
        ref_parts: list[str] = []
        if parsed.mentioned_sections:
            ref_parts.extend([f"Section {s}" for s in parsed.mentioned_sections])
        if parsed.mentioned_rules:
            ref_parts.extend([f"Rule {r}" for r in parsed.mentioned_rules])
        if parsed.mentioned_acts:
            ref_parts.extend(parsed.mentioned_acts)

        context_str = " ".join(ref_parts)
        if context_str.lower() not in rewritten.lower():
            rewritten = f"{context_str} {rewritten}"

    # 4. Clean extra spaces and punctuation left over
    rewritten = re.sub(r"\s+", " ", rewritten).strip(" ?.,!")

    # Fall back to raw_query if stripping resulted in an empty string
    final_query = rewritten.strip() if rewritten.strip() else raw_query.strip()

    logger.info(
        "Query rewritten for vector DB | raw=%r -> search_query=%r",
        raw_query[:80], final_query[:80],
    )
    return final_query
