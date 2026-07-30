"""
generation/prompt_templates.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
System and User prompt templates for grounded Indian GST answer generation.

Strict Instructions for LLM:
1. Answer ONLY using the provided legal context chunks.
2. Always cite using the exact format: [<law_title>, <unit_number>, <sub_unit_marker>]
   immediately after every claim drawn from a specific chunk.
3. If multiple provisions apply or conflict, state each provision with its citation.
4. If the answer is NOT found in the provided context, state explicitly:
   "The provided legal context does not contain information to answer this question."
   NEVER fabricate or guess section numbers or legal wording.
5. If amendment/substitution footnotes (e.g. "Substituted w.e.f...") appear in the text
   and are relevant, mention them in the answer.
"""
from __future__ import annotations

import json
from typing import Any

SYSTEM_PROMPT = """You are an expert Indian Goods and Services Tax (GST) legal counsel and AI assistant.
Your job is to provide accurate, grounded answers to GST questions based STRICTLY on the legal context chunks provided.

STRICT LEGAL ANSWERING RULES:
1. Grounding: Answer ONLY using the information contained in the provided CONTEXT CHUNKS. Do NOT use outside knowledge or make assumptions not supported by the context.
2. Mandatory Citations: Every single legal claim, condition, threshold, or rule must be immediately followed by its exact legal citation in this format:
   [<law_title>, <unit_number>, <sub_unit_marker>]
   Examples:
   - [Central Goods and Services Tax Act, 2017, Section 16, (2)(a)]
   - [Central Goods and Services Tax Rules, 2017, Rule 86A, (1)]
   - [Integrated Goods and Services Tax Act, 2017, Section 12, Intro/General]
3. Absence of Information: If the provided context chunks do NOT contain enough information to answer the question, state explicitly:
   "The provided legal context does not contain information to answer this question."
   Never attempt to invent or fabricate section/rule numbers, effective dates, or legal provisions.
4. Multiple Provisions / Conflicts: If multiple sections or rules apply, list each clearly with its respective citation.
5. Amendment Footnotes: Pay close attention to amendment notes (e.g. "Substituted vide Notification...", "Omitted w.e.f..."). If relevant to the user's question, mention the historical context or amendment details.
6. Tone & Format: Be concise, precise, professional, and clear. Use bullet points for conditions or lists.
"""


def format_context_chunk(index: int, chunk: dict[str, Any]) -> str:
    """Format a single expanded context chunk for inclusion in the LLM prompt."""
    meta = chunk.get("metadata", {})
    law_title = chunk.get("parent_law_title") or meta.get("law_title", "GST Law")
    raw_unit = chunk.get("parent_raw_unit") or meta.get("raw_unit", "Provision")
    unit_num = chunk.get("parent_unit_number") or meta.get("unit_number", "")
    sub_marker = meta.get("sub_unit_marker", "Intro/General")
    
    # Text: prefer expanded_context (parent section text), fallback to document text
    text = chunk.get("expanded_context") or chunk.get("document", "")

    header = f"--- CHUNK {index} ---"
    citation_ref = f"[{law_title}, {raw_unit}, {sub_marker}]"
    
    return f"{header}\nCitation Tag: {citation_ref}\nLaw: {law_title}\nUnit: {raw_unit} (Unit Number: {unit_num})\nSub-unit Marker: {sub_marker}\n\nContent:\n{text}\n"


def build_user_prompt(query: str, context_chunks: list[dict[str, Any]]) -> str:
    """Build the user prompt combining the query and formatted context chunks."""
    if not context_chunks:
        formatted_context = "No context chunks available."
    else:
        formatted_context = "\n".join(
            format_context_chunk(i + 1, chunk)
            for i, chunk in enumerate(context_chunks)
        )

    return f"""USER QUESTION:
{query}

PROVIDED LEGAL CONTEXT CHUNKS:
{formatted_context}

INSTRUCTIONS:
Answer the USER QUESTION using ONLY the PROVIDED LEGAL CONTEXT CHUNKS above. Include precise citations [<law_title>, <unit_number>, <sub_unit_marker>] for every claim. If the information is not in the context, explicitly state so.
"""
