"""
generation/lc_agent.py
~~~~~~~~~~~~~~~~~~~~~~
LangChain-powered agentic RAG loop for Indian GST legal queries.

Architecture
------------
- Uses LangChain's `create_tool_calling_agent` + `AgentExecutor`.
- The LLM autonomously decides which tools to call and loops until
  it has enough evidence to produce a final grounded answer.
- Supports: Gemini (default), Claude, Ollama (tool-capable models only).
- Falls back to the mock extractor if no provider is configured.

Flow
----
  User Query
      │
      ▼
  LangChain AgentExecutor
      │  ← LLM decides: call hybrid_gst_search, lookup_specific_section,
      │                  or get_parent_section_text
      │  ← Observes tool output
      │  ← Loops until max_iterations or LLM outputs Final Answer
      ▼
  Grounded Answer with citations

Public API
----------
    from generation.lc_agent import run_agent

    result = run_agent("What is ITC eligibility under Section 16 CGST?")
    # result = {"answer": str, "citations": [...], "tool_calls_made": int}
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional

_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import config
from generation.lc_tools import GST_AGENT_TOOLS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# System prompt for the agent
# ---------------------------------------------------------------------------

AGENT_SYSTEM_PROMPT = """You are a precise Indian GST (Goods and Services Tax) legal assistant.
Your task is to answer questions about Indian GST law by retrieving and citing the exact
legal provisions from the GST Acts and Rules.

MANDATORY RULES:
1. ONLY use information retrieved via the provided tools. Do NOT use any prior knowledge.
2. ALWAYS cite the exact law title, section/rule number, and sub-clause in your answer.
3. If the retrieved context does not contain enough information, call additional tools to
   look up more sections before concluding.
4. If information is genuinely not found after thorough search, state:
   "This information is not available in the provided Indian GST legal corpus."
5. Do NOT speculate or hallucinate. Ground every statement in retrieved text.
6. Be concise but complete — include all relevant sub-clauses if they are retrieved.

Citation format: [Law Title, Section/Rule Number, Sub-clause]
Example: [Central Goods and Services Tax Act, 2017, Section 16, (1)]
"""


# ---------------------------------------------------------------------------
# LLM factory: build the appropriate LangChain ChatModel
# ---------------------------------------------------------------------------

def _build_llm(provider: str) -> Any:
    """Instantiate the LangChain ChatModel for the given provider."""

    if provider == "gemini":
        api_key = config.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. Set the environment variable or use "
                "LLM_PROVIDER='ollama' / 'claude' instead."
            )
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI  # type: ignore
        except ImportError as e:
            raise ImportError(
                "langchain-google-genai is required for Gemini. "
                "Run: pip install langchain-google-genai"
            ) from e
        return ChatGoogleGenerativeAI(
            model=config.GEMINI_MODEL,
            google_api_key=api_key,
            temperature=0.1,
            max_output_tokens=2048,
        )

    elif provider == "claude":
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set.")
        try:
            from langchain_anthropic import ChatAnthropic  # type: ignore
        except ImportError as e:
            raise ImportError(
                "langchain-anthropic is required for Claude. "
                "Run: pip install langchain-anthropic"
            ) from e
        claude_model = os.environ.get("CLAUDE_MODEL", "claude-3-haiku-20240307")
        return ChatAnthropic(
            model=claude_model,
            anthropic_api_key=api_key,
            temperature=0.1,
            max_tokens=2048,
        )

    elif provider == "ollama":
        base_url = config.OLLAMA_BASE_URL
        model_name = config.OLLAMA_MODEL
        try:
            from langchain_ollama import ChatOllama  # type: ignore
        except ImportError:
            try:
                from langchain_community.chat_models import ChatOllama  # type: ignore
            except ImportError as e:
                raise ImportError(
                    "langchain-ollama or langchain-community is required for Ollama. "
                    "Run: pip install langchain-ollama"
                ) from e
        return ChatOllama(
            model=model_name,
            base_url=base_url,
            temperature=0.1,
        )

    else:
        raise ValueError(
            f"Provider '{provider}' does not support tool calling in agentic mode. "
            "Use 'gemini', 'claude', or 'ollama' (with a tool-capable model)."
        )


# ---------------------------------------------------------------------------
# Citation extractor: parse citations from final answer text
# ---------------------------------------------------------------------------

def _extract_citations_from_answer(answer: str) -> list[dict[str, str]]:
    """
    Extract citation dicts from the final answer text.
    Looks for patterns like [Law Title, Section X, (1)].
    """
    import re
    citations: list[dict[str, str]] = []
    seen: set[str] = set()

    # Pattern: [<law>, <unit>, <marker>]  — flexible to handle missing sub-clause
    pattern = re.compile(
        r"\[([^\[\]]+?),\s*((?:Section|Rule|Article)\s*[\d\w]+(?:\.\s*[\d\w]+)*)"
        r"(?:,\s*([^\[\]]+?))?\]",
        re.IGNORECASE,
    )
    for m in pattern.finditer(answer):
        law = m.group(1).strip()
        unit = m.group(2).strip()
        marker = (m.group(3) or "").strip()
        key = f"{law}|{unit}|{marker}"
        if key not in seen:
            seen.add(key)
            citations.append({"law_title": law, "unit_number": unit, "sub_unit_marker": marker})

    return citations


# ---------------------------------------------------------------------------
# Core: run the agentic loop
# ---------------------------------------------------------------------------

def run_agent(
    query: str,
    provider: Optional[str] = None,
    max_iterations: Optional[int] = None,
    verbose: Optional[bool] = None,
) -> dict[str, Any]:
    """
    Run the LangChain agentic RAG loop for a GST legal query.

    Parameters
    ----------
    query          : Natural-language GST question from the user.
    provider       : LLM provider ('gemini', 'claude', 'ollama').
                     Defaults to config.LLM_PROVIDER.
    max_iterations : Maximum agent loop iterations. Defaults to config.AGENT_MAX_ITERATIONS.
    verbose        : Log each agent step to stdout. Defaults to config.AGENT_VERBOSE.

    Returns
    -------
    dict with keys:
        answer          : str — grounded legal answer with citations
        citations       : list[dict] — extracted citation objects
        tool_calls_made : int — number of tool invocations in this loop
        provider_used   : str — actual LLM provider used
    """
    selected_provider = (provider or config.LLM_PROVIDER).lower()
    _max_iter = max_iterations if max_iterations is not None else config.AGENT_MAX_ITERATIONS
    _verbose = verbose if verbose is not None else config.AGENT_VERBOSE

    logger.info(
        "run_agent | provider=%s max_iterations=%d query=%r",
        selected_provider, _max_iter, query[:120],
    )

    # --- Try to build the agentic loop; fall back to mock if provider unsupported ---
    try:
        llm = _build_llm(selected_provider)
    except (ValueError, ImportError) as exc:
        logger.warning("Agent LLM build failed (%s). Falling back to single-pass mock.", exc)
        return _fallback_mock(query)

    # --- Construct agent (DO NOT pre-bind tools; create_tool_calling_agent handles it) ---
    try:
        from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder  # type: ignore
        from langchain.agents import create_tool_calling_agent, AgentExecutor  # type: ignore
    except ImportError as e:
        logger.error("LangChain core not installed: %s", e)
        return _fallback_mock(query)

    prompt = ChatPromptTemplate.from_messages([
        ("system", AGENT_SYSTEM_PROMPT),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    # Pass raw llm – create_tool_calling_agent binds the tools internally.
    # Calling llm.bind_tools() before this causes double-binding which makes
    # Gemini return an empty response (no text AND no tool calls).
    agent = create_tool_calling_agent(llm, GST_AGENT_TOOLS, prompt)
    executor = AgentExecutor(
        agent=agent,
        tools=GST_AGENT_TOOLS,
        max_iterations=_max_iter,
        verbose=_verbose,
        return_intermediate_steps=True,
        handle_parsing_errors="The model returned an empty response. Please call a tool or provide a final answer.",
    )

    # --- Execute the agentic loop ---
    try:
        result = executor.invoke({"input": query})
    except Exception as exc:
        err_msg = str(exc)
        # Empty output guard: nudge the model with an explicit follow-up
        if "output text or tool calls" in err_msg or "empty" in err_msg.lower():
            logger.warning(
                "Empty model output detected – retrying with explicit nudge. Error: %s", err_msg
            )
            try:
                nudge_query = (
                    f"{query}\n\n"
                    "Please start by calling the hybrid_gst_search tool with the above question."
                )
                result = executor.invoke({"input": nudge_query})
            except Exception as exc2:
                logger.error("Retry also failed: %s", exc2, exc_info=True)
                return _fallback_mock(query, error=str(exc2))
        else:
            logger.error("AgentExecutor failed: %s", exc, exc_info=True)
            return _fallback_mock(query, error=err_msg)

    raw_answer: str = result.get("output", "")

    # If output is still empty after the loop, fall back gracefully
    if not raw_answer.strip():
        logger.warning("Agent returned empty output – falling back to mock.")
        return _fallback_mock(query, error="Agent produced no output")

    intermediate_steps = result.get("intermediate_steps", [])
    tool_calls_made = len(intermediate_steps)

    logger.info(
        "Agent completed: tool_calls=%d provider=%s", tool_calls_made, selected_provider
    )

    citations = _extract_citations_from_answer(raw_answer)

    return {
        "answer": raw_answer,
        "citations": citations,
        "tool_calls_made": tool_calls_made,
        "provider_used": selected_provider,
    }


# ---------------------------------------------------------------------------
# Fallback: single-pass mock (no LLM required)
# ---------------------------------------------------------------------------

def _fallback_mock(query: str, error: Optional[str] = None) -> dict[str, Any]:
    """Single-pass mock fallback used when the agent LLM cannot be instantiated."""
    from retrieval.pipeline import retrieve
    from generation.llm_client import _call_mock

    logger.info("_fallback_mock | query=%r", query[:120])
    try:
        chunks = retrieve(query=query)
        answer = _call_mock(query, chunks)
    except Exception as exc:
        answer = f"Could not process query: {exc}"
        chunks = []

    prefix = f"[Agent fallback – {error}]\n\n" if error else ""
    return {
        "answer": prefix + answer,
        "citations": _extract_citations_from_answer(answer),
        "tool_calls_made": 0,
        "provider_used": "mock",
    }
