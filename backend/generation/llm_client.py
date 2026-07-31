"""
generation/llm_client.py
~~~~~~~~~~~~~~~~~~~~~~~~
Provider-agnostic LLM Client for Indian GST RAG.

Supported Providers (configured via config.LLM_PROVIDER or LLM_PROVIDER env var):
- "gemini" : Google Gemini API (models like gemini-3.5-flash-lite / gemini-2.0-flash)
- "claude" : Anthropic Claude API (claude-3-5-sonnet / claude-3-haiku)
- "ollama" : Fully local Ollama instance (e.g. llama3 / mistral)
- "mock"   : Extractor fallback (useful for offline testing / CI without API keys)

Signature:
    generate_answer(query: str, context_chunks: list[dict], provider: str | None = None) -> str
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional

_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import config
from generation.prompt_templates import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Provider Implementation 1: Gemini
# ---------------------------------------------------------------------------

def _call_gemini(system_prompt: str, user_prompt: str) -> str:
    """Call Google Gemini API."""
    api_key = config.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY is not set. Please set the GEMINI_API_KEY environment variable "
            "or change LLM_PROVIDER in config.py to 'ollama' or 'mock'."
        )

    model_name = config.GEMINI_MODEL

    try:
        import google.generativeai as genai  # type: ignore
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system_prompt,
        )
        response = model.generate_content(
            user_prompt,
            generation_config={"temperature": 0.1, "max_output_tokens": 1500},
        )
        return response.text.strip()
    except ImportError:
        # Fallback to direct HTTP request using requests if google-generativeai library is not installed
        import requests
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}],
                }
            ],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1500},
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()


# ---------------------------------------------------------------------------
# Provider Implementation 2: Anthropic Claude
# ---------------------------------------------------------------------------

def _call_claude(system_prompt: str, user_prompt: str) -> str:
    """Call Anthropic Claude API."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is not set.")

    import requests
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": os.environ.get("CLAUDE_MODEL", "claude-3-haiku-20240307"),
        "max_tokens": 1500,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data["content"][0]["text"].strip()


# ---------------------------------------------------------------------------
# Provider Implementation 3: Local Ollama
# ---------------------------------------------------------------------------

def _call_ollama(system_prompt: str, user_prompt: str) -> str:
    """Call local Ollama server."""
    base_url = config.OLLAMA_BASE_URL
    model_name = config.OLLAMA_MODEL
    url = f"{base_url.rstrip('/')}/api/generate"

    import requests
    payload = {
        "model": model_name,
        "system": system_prompt,
        "prompt": user_prompt,
        "stream": False,
        "options": {"temperature": 0.1},
    }

    try:
        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "").strip()
    except Exception as exc:
        raise RuntimeError(
            f"Failed to connect to local Ollama server at {base_url} (model '{model_name}'). "
            f"Ensure Ollama is running (`ollama run {model_name}`). Error: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Provider Implementation 4: Offline Mock / Extractor Fallback
# ---------------------------------------------------------------------------

def _call_mock(query: str, context_chunks: list[dict[str, Any]]) -> str:
    """
    Offline fallback synthesizer for environments with no active LLM API keys.
    Extracts key sentences and applies mandatory citation format.
    """
    if not context_chunks:
        return "The provided legal context does not contain information to answer this question."

    # Note: rerank_score threshold deliberately removed.
    # Cross-encoder scores are NOT calibrated — a negative score does not mean
    # the chunk is irrelevant. When used as a fallback, always try to answer.

    lines = [f"Based on the provided Indian GST legal context:\n"]
    found_any = False

    for chunk in context_chunks[:3]:
        meta = chunk.get("metadata", {})
        law = chunk.get("parent_law_title") or meta.get("law_title", "GST Law")
        unit_num = chunk.get("parent_unit_number") or meta.get("unit_number", "")
        raw_unit = chunk.get("parent_raw_unit") or meta.get("raw_unit", "")
        marker = meta.get("sub_unit_marker") or "Intro/General"

        text = chunk.get("expanded_context") or chunk.get("document", "")
        if not text.strip():
            continue

        # Extract first 2 meaningful sentences
        sentences = [s.strip() for s in text.replace("\n", " ").split(".") if len(s.strip()) > 15]
        excerpt = ". ".join(sentences[:2]) if sentences else text[:250]

        # Use raw_unit if available; fall back to unit_num-based label
        display_unit = raw_unit or (f"Section/Rule {unit_num}" if unit_num else "Provision")
        citation_ref = f"[{law}, {display_unit}, {marker}]"

        lines.append(f"• According to {display_unit}: {excerpt}. {citation_ref}")
        found_any = True

    if not found_any:
        return "The provided legal context does not contain information to answer this question."

    return "\n\n".join(lines)



# ---------------------------------------------------------------------------
# Main Public Entry Point
# ---------------------------------------------------------------------------

def generate_answer(
    query: str,
    context_chunks: list[dict[str, Any]],
    provider: Optional[str] = None,
) -> str:
    """
    Generate a grounded legal answer with strict citations for *query*.

    Parameters
    ----------
    query          : User question
    context_chunks : List of expanded context chunks from retrieval pipeline
    provider       : LLM provider ("gemini", "claude", "ollama", "mock").
                     Defaults to config.LLM_PROVIDER.

    Returns
    -------
    Grounded answer string with citations.
    """
    selected_provider = (provider or config.LLM_PROVIDER).lower()
    logger.info("Generating answer using provider: %s", selected_provider)

    user_prompt = build_user_prompt(query, context_chunks)

    # Check if context is completely empty or non-legal
    if not context_chunks:
        return "The provided legal context does not contain information to answer this question."

    try:
        if selected_provider == "gemini":
            return _call_gemini(SYSTEM_PROMPT, user_prompt)
        elif selected_provider == "claude":
            return _call_claude(SYSTEM_PROMPT, user_prompt)
        elif selected_provider == "ollama":
            return _call_ollama(SYSTEM_PROMPT, user_prompt)
        elif selected_provider == "mock":
            return _call_mock(query, context_chunks)
        else:
            logger.warning("Unknown provider '%s'; attempting Gemini", selected_provider)
            return _call_gemini(SYSTEM_PROMPT, user_prompt)
    except Exception as exc:
        logger.warning("LLM provider '%s' failed (%s). Falling back to mock generator.", selected_provider, exc)
        return _call_mock(query, context_chunks)
