"""
retrieval/llm_query_router.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
LLM-driven query router and search query generator.

Makes a direct LLM call before querying the vector DB to:
1. Determine if the user's prompt requires querying the legal vector DB at all
   (e.g., greetings like "Hello" or meta-questions do NOT query vector DB).
2. Formulate 1-3 highly targeted legal search queries for the vector DB
   if search is required.
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Optional

import config
from retrieval.query_parser import parse_query, ParsedQuery

logger = logging.getLogger(__name__)


@dataclass
class LLMQueryRoutingResult:
    """Result of the first LLM analysis call."""
    needs_vector_db_search: bool
    direct_response: Optional[str] = None
    search_queries: list[str] = field(default_factory=list)
    parsed_query: Optional[ParsedQuery] = None


ROUTER_SYSTEM_PROMPT = """You are an expert AI Query Analyzer for an Indian GST (Goods and Services Tax) Legal RAG system.

Your task is to analyze the user's input prompt and decide:
1. Does this prompt require searching the Indian GST legal vector database (Acts & Rules)?
2. If YES, formulate 1 to 2 clean, highly specific legal search queries to send to the vector DB.
3. If NO (e.g. greetings like "hello", "hi", "good morning", pleasantries, questions about who/what you are, or general conversational chit-chat), provide a polite direct response.

Respond STRICTLY in JSON format with no Markdown code block wrappers or extra text.

JSON Schema:
{
  "needs_vector_db_search": boolean,
  "direct_response": string or null,
  "search_queries": [list of strings]
}

Examples:
User: "Hello, good morning!"
Response:
{
  "needs_vector_db_search": false,
  "direct_response": "Hello! Good morning. I am your AI assistant for Indian GST law. How can I assist you with GST Acts or Rules today?",
  "search_queries": []
}

User: "What is Section 16 of CGST Act about?"
Response:
{
  "needs_vector_db_search": true,
  "direct_response": null,
  "search_queries": ["Section 16 Central Goods and Services Tax Act input tax credit eligibility ITC"]
}

User: "Can I claim ITC on capital goods under rule 36?"
Response:
{
  "needs_vector_db_search": true,
  "direct_response": null,
  "search_queries": ["Rule 36 CGST Rules input tax credit capital goods documentary requirements"]
}
"""


def _call_llm_raw(system_prompt: str, user_prompt: str, provider: str) -> str:
    """Execute a direct LLM call returning raw output."""
    provider = provider.lower()
    api_key = config.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")

    if provider == "gemini" and api_key:
        try:
            from google import genai  # type: ignore
            from google.genai import types  # type: ignore
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.0,
                    max_output_tokens=500,
                ),
            )
            return response.text.strip() if response.text else ""
        except Exception as exc:
            logger.warning("Gemini raw call failed in query router: %s", exc)

    elif provider == "claude" and os.environ.get("ANTHROPIC_API_KEY"):
        try:
            import requests
            headers = {
                "x-api-key": os.environ["ANTHROPIC_API_KEY"],
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            payload = {
                "model": os.environ.get("CLAUDE_MODEL", "claude-3-haiku-20240307"),
                "max_tokens": 500,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            }
            resp = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload, timeout=15)
            resp.raise_for_status()
            return resp.json()["content"][0]["text"].strip()
        except Exception as exc:
            logger.warning("Claude raw call failed in query router: %s", exc)

    elif provider == "ollama":
        try:
            import requests
            url = f"{config.OLLAMA_BASE_URL.rstrip('/')}/api/generate"
            payload = {
                "model": config.OLLAMA_MODEL,
                "system": system_prompt,
                "prompt": user_prompt,
                "stream": False,
                "options": {"temperature": 0.0},
            }
            resp = requests.post(url, json=payload, timeout=15)
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except Exception as exc:
            logger.warning("Ollama raw call failed in query router: %s", exc)

    # Fallback return None signaling fallback behavior
    return ""


def analyze_and_route_query(
    user_prompt: str,
    provider: Optional[str] = None,
) -> LLMQueryRoutingResult:
    """
    First LLM Call: Analyze user prompt to determine if vector DB search is needed
    and generate optimal search queries for vector DB.
    """
    selected_provider = (provider or config.LLM_PROVIDER).lower()
    parsed = parse_query(user_prompt)

    # Fast heuristic check for simple greetings to save API latency if desired
    greetings = {"hi", "hello", "hey", "greetings", "good morning", "good afternoon", "good evening"}
    clean_user = user_prompt.strip().lower().strip("!.,?")
    if clean_user in greetings:
        logger.info("Fast-path greeting detected for query %r: skipping vector DB search", user_prompt)
        return LLMQueryRoutingResult(
            needs_vector_db_search=False,
            direct_response="Hello! How can I help you with Indian Goods and Services Tax (GST) law today?",
            search_queries=[],
            parsed_query=parsed,
        )

    logger.info("First LLM Call: Routing query %r (provider=%s)", user_prompt[:80], selected_provider)

    raw_output = _call_llm_raw(
        system_prompt=ROUTER_SYSTEM_PROMPT,
        user_prompt=f"User Prompt: {user_prompt}",
        provider=selected_provider,
    )

    if raw_output:
        try:
            # Strip markdown json blocks if present
            clean_json = re.sub(r"^```(?:json)?\s*", "", raw_output, flags=re.MULTILINE)
            clean_json = re.sub(r"\s*```$", "", clean_json, flags=re.MULTILINE).strip()
            data = json.loads(clean_json)

            needs_search = bool(data.get("needs_vector_db_search", True))
            direct_resp = data.get("direct_response")
            search_queries = data.get("search_queries", [])

            if not needs_search and not direct_resp:
                direct_resp = "How can I assist you with Indian GST provisions or tax rules?"

            logger.info(
                "LLM Router Decision | needs_search=%s search_queries=%s",
                needs_search, search_queries,
            )

            return LLMQueryRoutingResult(
                needs_vector_db_search=needs_search,
                direct_response=direct_resp,
                search_queries=search_queries if isinstance(search_queries, list) else [str(search_queries)],
                parsed_query=parsed,
            )

        except Exception as exc:
            logger.warning("Failed to parse JSON from LLM router output (%s). Output was: %r", exc, raw_output)

    # Default fallback: if LLM fails or is mock provider
    from retrieval.query_rewriter import rewrite_query
    fallback_search_query = rewrite_query(user_prompt, parsed=parsed)
    
    # Check if query contains legal terms or section/rule mentions
    has_legal_intent = parsed.has_explicit_refs() or any(
        kw in clean_user for kw in ["itc", "gst", "tax", "rule", "section", "act", "return", "exemption", "rate", "penalty", "invoice"]
    )

    if not has_legal_intent and len(clean_user.split()) <= 3:
        return LLMQueryRoutingResult(
            needs_vector_db_search=False,
            direct_response="Hello! I am your assistant for Indian GST law. Please ask a specific question about GST Acts, Rules, or provisions.",
            search_queries=[],
            parsed_query=parsed,
        )

    return LLMQueryRoutingResult(
        needs_vector_db_search=True,
        direct_response=None,
        search_queries=[fallback_search_query],
        parsed_query=parsed,
    )
