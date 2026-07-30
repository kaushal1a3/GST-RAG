"""
eval/eval_runner.py
~~~~~~~~~~~~~~~~~~~~
Evaluation runner measuring Retrieval Accuracy, Citation Quality, MRR,
and Hallucination Rates across benchmark GST test queries.

Metrics Calculated:
- Hit Rate@1: % of valid queries where expected section/rule is top-1
- Hit Rate@5: % of valid queries where expected section/rule is in top-5
- MRR@5 (Mean Reciprocal Rank): average of (1 / rank) for expected hits
- Rejection Rate: % of trick/out-of-corpus queries correctly declared "not found"
- Hallucination Check: % of generated citations present in retrieved context
"""
from __future__ import annotations

import io
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

# UTF-8 stdout fix for Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import config
from retrieval.pipeline import retrieve
from generation.llm_client import generate_answer

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


def _hr(char: str = "-", width: int = 75) -> None:
    print(char * width)


def _extract_answer_citations(answer_text: str) -> list[str]:
    """
    Extract cited unit numbers from formatted LLM citation tags:
    e.g. '[Central Goods and Services Tax Act, 2017, Section 16, (1)]' -> '16'
    """
    pattern = re.compile(r"\[[^\]]+,\s*(?:Section|Rule)?\s*(\d+[A-Za-z]*)\s*,\s*[^\]]+\]", re.IGNORECASE)
    matches = pattern.findall(answer_text)
    return list(dict.fromkeys(matches))


def run_eval(test_queries_path: Path | None = None, top_k: int = 5) -> dict[str, Any]:
    """
    Run evaluation harness across all benchmark queries in test_queries.json.
    """
    path = test_queries_path or (config.PROJECT_ROOT / "eval" / "test_queries.json")
    if not path.exists():
        raise FileNotFoundError(f"Benchmark file not found: {path}")

    with path.open("r", encoding="utf-8") as fh:
        queries: list[dict[str, Any]] = json.load(fh)

    print()
    _hr("=")
    print("  GST RAG SYSTEM -- EVALUATION HARNESS")
    print(f"  Benchmark File : {path.name} ({len(queries)} test queries)")
    print(f"  Retrieval Top-K: {top_k}")
    print(f"  Embedding Model: {config.EMBEDDING_MODEL_NAME}")
    print(f"  Reranker Model : {config.RERANKER_MODEL}")
    _hr("=")

    valid_count = 0
    hits_at_1 = 0
    hits_at_5 = 0
    rr_sum = 0.0

    trick_count = 0
    trick_rejections = 0

    hallucination_checks = 0
    hallucination_passes = 0

    print(f"\n  {'ID':<5} {'Category':<16} {'Query Snippet':<32} {'Expected':<10} {'Rank':<6} {'Result':<10}")
    _hr("-")

    for item in queries:
        qid = item["id"]
        cat = item["category"]
        q_text = item["query"]
        should_find = item["should_find"]
        exp_unit = item.get("expected_unit")
        exp_law = item.get("expected_law")

        # 1. Run retrieval
        retrieved = retrieve(query=q_text, final_top_k=top_k)
        retrieved_units = [
            c.get("metadata", {}).get("unit_number") or c.get("parent_unit_number", "")
            for c in retrieved
        ]

        snippet = (q_text[:29] + "...") if len(q_text) > 32 else q_text

        if should_find:
            valid_count += 1
            rank = None
            for idx, unit in enumerate(retrieved_units, 1):
                if exp_unit and unit == exp_unit:
                    rank = idx
                    break

            if rank == 1:
                hits_at_1 += 1
                hits_at_5 += 1
                rr_sum += 1.0
                status_str = "HIT @ 1 OK"
            elif rank is not None and rank <= 5:
                hits_at_5 += 1
                rr_sum += 1.0 / rank
                status_str = f"HIT @ {rank} OK"
            else:
                status_str = "MISS"
                rank = "-"

            exp_label = f"Sec/R {exp_unit}" if exp_unit else "N/A"
            print(f"  {qid:<5} {cat:<16} {snippet:<32} {exp_label:<10} {str(rank):<6} {status_str:<10}")

        else:
            # Trick query handling
            trick_count += 1
            answer = generate_answer(query=q_text, context_chunks=retrieved, provider="mock")
            if "not contain information" in answer.lower():
                trick_rejections += 1
                status_str = "REJECTED OK"
            else:
                status_str = "FAILED REJECT"
            print(f"  {qid:<5} {cat:<16} {snippet:<32} {'TRICK':<10} {'-':<6} {status_str:<10}")

        # 2. Hallucination check on answer generation for valid queries
        if should_find:
            answer = generate_answer(query=q_text, context_chunks=retrieved, provider="mock")
            cited_units = _extract_answer_citations(answer)
            if cited_units:
                hallucination_checks += 1
                # Check if every cited unit was in retrieved units
                unsupported = [c for c in cited_units if c not in retrieved_units]
                if not unsupported:
                    hallucination_passes += 1

    # Metrics Summary
    hr1 = (hits_at_1 / valid_count * 100) if valid_count else 0.0
    hr5 = (hits_at_5 / valid_count * 100) if valid_count else 0.0
    mrr = (rr_sum / valid_count) if valid_count else 0.0
    rejection_rate = (trick_rejections / trick_count * 100) if trick_count else 0.0
    hallucination_rate = (
        ((hallucination_checks - hallucination_passes) / hallucination_checks * 100)
        if hallucination_checks else 0.0
    )

    _hr("=")
    print("  EVALUATION SUMMARY REPORT")
    _hr("=")
    print(f"  Valid Test Queries Evaluated : {valid_count}")
    print(f"  Trick / Out-of-Corpus Queries: {trick_count}")
    print(f"  Hit Rate @ 1 (Top-1 Acc)      : {hr1:.2f}%  ({hits_at_1}/{valid_count})")
    print(f"  Hit Rate @ 5 (Top-5 Acc)      : {hr5:.2f}%  ({hits_at_5}/{valid_count})")
    print(f"  Mean Reciprocal Rank (MRR@5)  : {mrr:.4f}")
    print(f"  Trick Query Rejection Rate   : {rejection_rate:.2f}%  ({trick_rejections}/{trick_count})")
    print(f"  Citation Groundedness Rate   : {100.0 - hallucination_rate:.2f}%  (Hallucination Rate: {hallucination_rate:.2f}%)")
    _hr("=")
    print()

    return {
        "valid_count": valid_count,
        "trick_count": trick_count,
        "hit_rate_at_1": hr1,
        "hit_rate_at_5": hr5,
        "mrr_at_5": mrr,
        "rejection_rate": rejection_rate,
        "groundedness_rate": 100.0 - hallucination_rate,
    }


if __name__ == "__main__":
    run_eval()
