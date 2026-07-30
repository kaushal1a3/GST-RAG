"""
retrieval/query_parser.py
~~~~~~~~~~~~~~~~~~~~~~~~~~
Detect explicit legal references in a user query and extract structured filters.

Parsed result:
    {
      "raw_query":         str  – original query, unchanged
      "mentioned_sections": list[str]  – e.g. ["16", "17"]
      "mentioned_rules":    list[str]  – e.g. ["36", "86A"]
      "mentioned_acts":     list[str]  – matched act keywords / full names
      "filters": {
          "unit_numbers": list[str]   – union of sections + rules for metadata filter
          "doc_type":     str | None  – "act" | "rule" | None (if ambiguous)
          "law_title_keywords": list[str]  – normalised act keywords
      }
    }
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Known act keyword → canonical fragment used in metadata filter matching
# ---------------------------------------------------------------------------
ACT_KEYWORD_MAP: dict[str, str] = {
    # short abbreviations
    r"\bcgst\b": "Central Goods and Services Tax",
    r"\bigst\b": "Integrated Goods and Services Tax",
    r"\butgst\b": "Union Territory Goods and Services Tax",
    r"\bsgst\b": "State Goods and Services Tax",  # generic mention
    r"\bcompensation\s+cess\b": "Compensation to States",
    r"\bcess\b": "Compensation to States",
    r"\b101st\s+amendment\b": "Constitution (101st Amendment)",
    r"\bconstitution.*amendment\b": "Constitution (101st Amendment)",
    r"\bjammu\b|\bkashmir\b|\bj&?k\b": "Extension to Jammu And Kashmir",
    # long-form
    r"central goods and services tax act": "Central Goods and Services Tax Act",
    r"integrated goods and services tax act": "Integrated Goods and Services Tax Act",
    r"union territory goods and services tax act": "Union Territory Goods and Services Tax Act",
    r"gst.*compensation": "Compensation to States",
}

# ---------------------------------------------------------------------------
# Regex patterns for section and rule references
# ---------------------------------------------------------------------------
# Matches: "section 16", "sec 17", "section 17(5)", "sec. 16(2)(a)", "s. 16"
_SECTION_PATTERN = re.compile(
    r"\b(?:section|sec\.?)\s*(\d+[A-Za-z]*(?:\s*\(\w+\))*)",
    re.IGNORECASE,
)

# Matches: "rule 36", "rule 86A", "rule 36(4)"
_RULE_PATTERN = re.compile(
    r"\brule\s*(\d+[A-Za-z]*(?:\s*\(\w+\))*)",
    re.IGNORECASE,
)

# Matches bare numeric references when preceded by "sub-section" or "clause"
_SUBSECTION_PATTERN = re.compile(
    r"\bsub[-\s]?section\s*\((\w+)\)",
    re.IGNORECASE,
)


def _extract_unit_number(raw: str) -> str:
    """Strip sub-clauses to get the base unit number: '17(5)' → '17', '86A(1)' → '86A'."""
    return re.split(r"[\s(]", raw.strip())[0]


@dataclass
class ParsedQuery:
    """Structured output of the query parser."""
    raw_query: str
    mentioned_sections: list[str] = field(default_factory=list)   # base numbers only
    mentioned_rules: list[str] = field(default_factory=list)       # base numbers only
    mentioned_acts: list[str] = field(default_factory=list)        # canonical fragments
    # sub-clause markers found (informational)
    mentioned_sub_markers: list[str] = field(default_factory=list)

    # Flattened filter block for downstream use
    @property
    def filters(self) -> dict:
        unit_numbers = list(dict.fromkeys(self.mentioned_sections + self.mentioned_rules))
        doc_type: Optional[str] = None
        if self.mentioned_sections and not self.mentioned_rules:
            doc_type = "act"
        elif self.mentioned_rules and not self.mentioned_sections:
            doc_type = "rule"

        return {
            "unit_numbers": unit_numbers,
            "doc_type": doc_type,
            "law_title_keywords": self.mentioned_acts,
        }

    def has_explicit_refs(self) -> bool:
        """True if the query contains any specific section/rule/act references."""
        return bool(self.mentioned_sections or self.mentioned_rules or self.mentioned_acts)

    def to_dict(self) -> dict:
        return {
            "raw_query": self.raw_query,
            "mentioned_sections": self.mentioned_sections,
            "mentioned_rules": self.mentioned_rules,
            "mentioned_acts": self.mentioned_acts,
            "mentioned_sub_markers": self.mentioned_sub_markers,
            "filters": self.filters,
        }


def parse_query(query: str) -> ParsedQuery:
    """
    Parse a natural-language GST query and extract explicit legal references.

    Parameters
    ----------
    query : natural-language user query

    Returns
    -------
    ParsedQuery dataclass instance
    """
    q_lower = query.lower()

    # 1. Extract section references
    sections: list[str] = []
    for m in _SECTION_PATTERN.finditer(query):
        base = _extract_unit_number(m.group(1))
        if base not in sections:
            sections.append(base)

    # 2. Extract rule references
    rules: list[str] = []
    for m in _RULE_PATTERN.finditer(query):
        base = _extract_unit_number(m.group(1))
        if base not in rules:
            rules.append(base)

    # 3. Sub-section markers (informational)
    sub_markers: list[str] = []
    for m in _SUBSECTION_PATTERN.finditer(query):
        marker = f"({m.group(1)})"
        if marker not in sub_markers:
            sub_markers.append(marker)

    # 4. Detect act keywords
    acts: list[str] = []
    for pattern, canonical in ACT_KEYWORD_MAP.items():
        if re.search(pattern, q_lower, re.IGNORECASE):
            if canonical not in acts:
                acts.append(canonical)

    return ParsedQuery(
        raw_query=query,
        mentioned_sections=sections,
        mentioned_rules=rules,
        mentioned_acts=acts,
        mentioned_sub_markers=sub_markers,
    )
