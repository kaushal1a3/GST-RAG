"""
generation/verify.py
~~~~~~~~~~~~~~~~~~~~
Phase 3 self-check script.

Runs sample queries end-to-end through the Generation + API layer and prints
full JSON responses for 3 specific test cases:
1. Exact citation query ("Section 16 ITC eligibility")
2. Conceptual query ("E-way bill requirement")
3. Out-of-corpus query ("Capital of France") -> confirms it says "not found" rather than hallucinating!

Run:
    python -m generation.verify
"""
from __future__ import annotations

import io
import json
import logging
import sys
from pathlib import Path

# UTF-8 stdout fix
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

logging.basicConfig(level=logging.WARNING)

import config
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def _hr(char: str = "-", width: int = 72) -> None:
    print(char * width)


def _banner(text: str) -> None:
    _hr("=")
    print(f"  {text}")
    _hr("=")


def run_verification() -> None:
    print()
    _banner("GST RAG – Phase 3 End-to-End API & Generation Verification")

    # 1. Health check
    print("\n  [1] Testing GET /health endpoint ...")
    health_resp = client.get("/health")
    print(f"  Status Code: {health_resp.status_code}")
    print(f"  Payload: {json.dumps(health_resp.json(), indent=2)}")
    _hr()

    # 2. Test 3 target queries via POST /query
    test_cases = [
        {
            "category": "A. Exact Citation Query",
            "question": "What does Section 16 of CGST Act say about ITC eligibility?",
            "provider": "mock",
        },
        {
            "category": "B. Conceptual Query",
            "question": "When is an e-way bill required for goods movement?",
            "provider": "mock",
        },
        {
            "category": "C. Out-of-Corpus Query (Hallucination Prevention Test)",
            "question": "What is the capital of France and what are its GST rates?",
            "provider": "mock",
        },
    ]

    for tc in test_cases:
        _hr()
        print(f"  Category: {tc['category']}")
        print(f"  Question: {tc['question']}")

        response = client.post(
            "/query",
            json={"question": tc["question"], "provider": tc["provider"], "top_k": 5},
        )

        print(f"  Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print("\n  FULL JSON RESPONSE:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(f"  ERROR: {response.text}")
        print()

    _hr("=")
    print("  Phase 3 End-to-End Verification Complete.")
    _hr("=")
    print()


if __name__ == "__main__":
    run_verification()
