"""
retrieval/verify.py
~~~~~~~~~~~~~~~~~~~~
Phase 2 self-check: runs 10 test queries through the full retrieval pipeline
and prints parsed filters, top-5 results, and parent expansion status.

Run:
    python -m retrieval.verify
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# Fix Windows cp1252 console encoding
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

logging.basicConfig(
    level=logging.WARNING,   # silence noisy libs
    format="%(levelname)-8s  %(message)s",
)

import config
from retrieval.query_parser import parse_query
from retrieval.pipeline import retrieve

# ---------------------------------------------------------------------------
# Test queries – covers all required categories
# ---------------------------------------------------------------------------
TEST_QUERIES = [
    # ── Exact section lookup ────────────────────────────────────────────────
    {
        "label": "Exact section – ITC eligibility",
        "query": "What does Section 16 of CGST Act say about ITC eligibility?",
        "expect_unit": "16",
    },
    {
        "label": "Exact section – Blocked credits",
        "query": "What are the blocked credits under Section 17(5) of CGST Act?",
        "expect_unit": "17",
    },
    {
        "label": "Exact rule lookup – Rule 86A",
        "query": "What is Rule 86A and when can ITC ledger be blocked?",
        "expect_unit": "86A",
    },
    {
        "label": "Exact rule lookup – Rule 36",
        "query": "What conditions must be met under Rule 36 for claiming ITC?",
        "expect_unit": "36",
    },
    # ── Conceptual / keyword queries ────────────────────────────────────────
    {
        "label": "Conceptual – Composition scheme threshold",
        "query": "What is the composition scheme threshold and who is eligible?",
        "expect_unit": None,
    },
    {
        "label": "Conceptual – E-way bill requirement",
        "query": "When is an e-way bill required for goods movement?",
        "expect_unit": None,
    },
    {
        "label": "Conceptual – Place of supply for services",
        "query": "How is the place of supply determined for services in IGST?",
        "expect_unit": None,
    },
    # ── Cross-act / comparative queries ─────────────────────────────────────
    {
        "label": "Cross-act – CGST vs IGST registration",
        "query": "Difference between CGST and IGST registration requirements",
        "expect_unit": None,
    },
    # ── Penalty / offence ───────────────────────────────────────────────────
    {
        "label": "Penalty for non-filing",
        "query": "What is the penalty for late filing of GST returns?",
        "expect_unit": None,
    },
    # ── Definition lookup ───────────────────────────────────────────────────
    {
        "label": "Definition – taxable supply",
        "query": "Define taxable supply under CGST Act",
        "expect_unit": None,
    },
]


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _hr(char: str = "-", width: int = 72) -> None:
    print(char * width)


def _banner(text: str) -> None:
    _hr("=")
    print(f"  {text}")
    _hr("=")


def _print_result(rank: int, chunk: dict, expect_unit: str | None) -> None:
    meta = chunk.get("metadata", {})
    law = meta.get("law_title", chunk.get("parent_law_title", "?"))
    raw_unit = meta.get("raw_unit", chunk.get("parent_raw_unit", "?"))
    unit_num = meta.get("unit_number", "?")
    marker = meta.get("sub_unit_marker", "?")
    rrf = chunk.get("rrf_score", 0.0)
    rerank_s = chunk.get("rerank_score", 0.0)
    parent_ok = "✓" if chunk.get("parent_found") else "✗"

    # Flag if expected unit is top-1
    hit_marker = ""
    if rank == 1 and expect_unit and unit_num == expect_unit:
        hit_marker = "  << EXACT HIT OK"
    elif rank == 1 and expect_unit and unit_num != expect_unit:
        hit_marker = f"  << EXPECTED {expect_unit} -- GOT {unit_num} MISS"

    print(
        f"  [{rank}] {law}\n"
        f"      Unit: {raw_unit}  |  Marker: {marker}\n"
        f"      RRF={rrf:.5f}  Rerank={rerank_s:.4f}  Parent:{parent_ok}"
        f"{hit_marker}"
    )


def run_verification() -> None:
    print()
    _banner("GST RAG – Phase 2 Retrieval Verification")
    print(f"  Embedding model : {config.EMBEDDING_MODEL_NAME}")
    print(f"  Reranker model  : {config.RERANKER_MODEL}  (enabled={config.RERANKER_ENABLED})")
    print(f"  Vector top-k    : {config.VECTOR_TOP_K}")
    print(f"  BM25 top-k      : {config.BM25_TOP_K}")
    print(f"  Reranker cands  : {config.RERANKER_CANDIDATES}")
    print(f"  Final top-k     : {config.RERANKER_TOP_K}")
    print()

    exact_hits = 0
    exact_total = sum(1 for q in TEST_QUERIES if q["expect_unit"])

    for i, tq in enumerate(TEST_QUERIES, 1):
        query = tq["query"]
        label = tq["label"]
        expect_unit = tq.get("expect_unit")

        _hr()
        print(f"  Query {i}/{len(TEST_QUERIES)}: [{label}]")
        print(f"  ?  {query}")

        # Parse
        parsed = parse_query(query)
        print(f"  >> Parsed filters: sections={parsed.mentioned_sections} "
              f"rules={parsed.mentioned_rules} acts={parsed.mentioned_acts}")

        # Retrieve
        try:
            results = retrieve(query, reranker_enabled=config.RERANKER_ENABLED)
        except Exception as exc:
            print(f"  !! Retrieval FAILED: {exc}")
            import traceback; traceback.print_exc()
            continue

        print(f"  Top-{len(results)} results:")
        for rank, chunk in enumerate(results, 1):
            _print_result(rank, chunk, expect_unit)

        # Exact-hit check
        if expect_unit and results:
            top_unit = results[0].get("metadata", {}).get("unit_number", "")
            if top_unit == expect_unit:
                exact_hits += 1

        print()

    # Summary
    _hr("=")
    print(f"  Exact citation hits: {exact_hits}/{exact_total}")
    if exact_hits == exact_total:
        print("  OK: All exact section/rule queries returned the correct chunk at rank-1.")
    else:
        missed = exact_total - exact_hits
        print(f"  WARN: {missed} exact citation(s) did NOT land at rank-1 - review above.")
    _hr("=")
    print()


if __name__ == "__main__":
    run_verification()
