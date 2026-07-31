"""
ingestion/push_to_qdrant.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Script to push GST leaf chunk text to Qdrant Cloud using Qdrant Cloud Inference.
Embedding is done server-side via Qdrant REST API — no local model, no Gemini, no rate limits.

Usage:
    python ingestion/push_to_qdrant.py

Requirements in .env:
    QDRANT_URL=https://xxx-xxx.cloud.qdrant.io
    QDRANT_API_KEY=your_qdrant_api_key
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent.resolve()
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
logger = logging.getLogger(__name__)

# Qdrant Cloud Inference model — server-side, free on all tiers, 384-dim.
INFERENCE_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
VECTOR_DIM = 384


def main():
    print("=" * 60)
    print(" GST RAG - Push Text to Qdrant Cloud (Cloud Inference)")
    print(f" Embedding model: {INFERENCE_MODEL} (server-side REST)")
    print("=" * 60)

    qdrant_url = (os.getenv("QDRANT_URL") or config.QDRANT_URL).rstrip("/")
    qdrant_api_key = os.getenv("QDRANT_API_KEY") or config.QDRANT_API_KEY
    collection_name = os.getenv("QDRANT_COLLECTION") or config.QDRANT_COLLECTION

    if not qdrant_url or not qdrant_api_key:
        print("\n[ERROR] QDRANT_URL and QDRANT_API_KEY must be set in .env or environment variables.")
        sys.exit(1)

    print(f"\n1. Connecting to Qdrant Cloud:\n   URL: {qdrant_url}\n   Collection: {collection_name}")

    try:
        import httpx
    except ImportError:
        print("\n[ERROR] httpx not installed. Run: pip install httpx")
        sys.exit(1)

    headers = {
        "api-key": qdrant_api_key,
        "Content-Type": "application/json",
    }
    base = f"{qdrant_url}/collections/{collection_name}"

    # Test connection
    resp = httpx.get(qdrant_url, headers=headers, timeout=10)
    resp.raise_for_status()
    print("   Connected successfully.")

    # Load Leaf Chunks JSON
    if not config.LEAF_CHUNKS_FILE.exists():
        print(f"\n[ERROR] Leaf chunks file not found at {config.LEAF_CHUNKS_FILE}")
        sys.exit(1)

    with open(config.LEAF_CHUNKS_FILE, "r", encoding="utf-8") as f:
        leaf_chunks = json.load(f)
    print(f"2. Loaded {len(leaf_chunks)} leaf chunks.")

    # Create/re-create collection
    print(f"\n3. Preparing collection '{collection_name}' (dim={VECTOR_DIM}, model={INFERENCE_MODEL})...")
    # Delete existing
    del_resp = httpx.delete(base, headers=headers, timeout=30)
    if del_resp.status_code in (200, 404):
        print("   Deleted existing collection (if any).")
    else:
        print(f"   Delete response: {del_resp.status_code}")

    # Create new collection
    create_body = {
        "vectors": {
            "size": VECTOR_DIM,
            "distance": "Cosine",
        }
    }
    cr = httpx.put(base, headers=headers, json=create_body, timeout=30)
    cr.raise_for_status()
    print(f"   Created collection '{collection_name}' (dim={VECTOR_DIM}) successfully.")

    # Upload points via REST — Qdrant Cloud Inference embeds text server-side
    BATCH_SIZE = 100
    total = len(leaf_chunks)
    print(f"\n4. Uploading {total} points (Qdrant embeds text server-side via REST)...")

    with httpx.Client(headers=headers, timeout=120.0) as client:
        for start in range(0, total, BATCH_SIZE):
            batch = leaf_chunks[start : start + BATCH_SIZE]
            points = []
            for idx, chunk in enumerate(batch):
                point_id = start + idx + 1
                text = chunk.get("text", "")
                payload = {
                    "chunk_id": chunk.get("id", chunk.get("chunk_id", f"leaf-{start + idx}")),
                    "text": text,
                    "law_title": chunk.get("law_title", ""),
                    "unit_number": chunk.get("unit_number", ""),
                    "raw_unit": chunk.get("raw_unit", ""),
                    "sub_unit_marker": chunk.get("sub_unit_marker", ""),
                    "chapter": chunk.get("chapter", ""),
                    "unit_title": chunk.get("unit_title", ""),
                    "doc_type": chunk.get("doc_type", "act"),
                    "parent_id": chunk.get("parent_id", ""),
                }
                points.append({
                    "id": point_id,
                    "payload": payload,
                    # Qdrant Cloud Inference: pass text + model, no local embedding
                    "vector": {
                        "text": text,
                        "model": INFERENCE_MODEL,
                    },
                })

            body = {"points": points}
            r = client.put(f"{base}/points?wait=true", json=body)
            if r.status_code not in (200, 206):
                print(f"\n[ERROR] Batch {start}-{start + len(batch)}: HTTP {r.status_code}: {r.text[:300]}")
                sys.exit(1)

            end = min(start + BATCH_SIZE, total)
            print(f"   Uploaded points {start + 1}–{end} of {total}")

    print("\n[SUCCESS] All chunks uploaded to Qdrant Cloud!")
    print(f"   Collection : {collection_name}")
    print(f"   Embed model: {INFERENCE_MODEL} (Qdrant Cloud Inference — REST, server-side)")
    print("   Your Vercel backend can query with zero local embedding code.")
    print("=" * 60)


if __name__ == "__main__":
    main()
