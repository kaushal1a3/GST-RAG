"""
ingestion/push_to_qdrant.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Script to push GST leaf chunk vector embeddings to Qdrant Cloud Cluster.

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
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
logger = logging.getLogger(__name__)


def main():
    print("=" * 60)
    print(" GST RAG - Push Vector Embeddings to Qdrant Cloud")
    print("=" * 60)

    qdrant_url = os.getenv("QDRANT_URL") or config.QDRANT_URL
    qdrant_api_key = os.getenv("QDRANT_API_KEY") or config.QDRANT_API_KEY
    collection_name = os.getenv("QDRANT_COLLECTION") or config.QDRANT_COLLECTION

    if not qdrant_url or not qdrant_api_key:
        print("\n[ERROR] QDRANT_URL and QDRANT_API_KEY must be set in .env or environment variables.")
        print("Example:")
        print("  QDRANT_URL=https://your-cluster-id.us-east4-0.gcp.cloud.qdrant.io")
        print("  QDRANT_API_KEY=your_qdrant_api_key")
        sys.exit(1)

    print(f"\n1. Connecting to Qdrant Cloud cluster:\n   URL: {qdrant_url}\n   Collection: {collection_name}")
    
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams, PointStruct
        client = QdrantClient(
            url=qdrant_url, 
            api_key=qdrant_api_key, 
            timeout=60.0,
            check_compatibility=False
        )
    except ImportError:
        print("\n[ERROR] qdrant-client not installed. Run: pip install qdrant-client")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Connection failed: {e}")
        sys.exit(1)

    # Load Leaf Chunks JSON
    if not config.LEAF_CHUNKS_FILE.exists():
        print(f"\n[ERROR] Leaf chunks file not found at {config.LEAF_CHUNKS_FILE}")
        sys.exit(1)

    with open(config.LEAF_CHUNKS_FILE, "r", encoding="utf-8") as f:
        leaf_chunks = json.load(f)
    print(f"2. Loaded {len(leaf_chunks)} leaf chunks from processed dataset.")
    # Compute embeddings via Google text-embedding-004 (no local model download needed)
    google_api_key = os.getenv("GEMINI_API_KEY") or config.GEMINI_API_KEY
    if not google_api_key:
        print("\n[ERROR] GEMINI_API_KEY must be set to generate embeddings via Google API.")
        sys.exit(1)

    from google import genai as google_genai  # type: ignore  # new official SDK
    genai_client = google_genai.Client(api_key=google_api_key)

    embed_model = os.getenv("GOOGLE_EMBEDDING_MODEL", config.GOOGLE_EMBEDDING_MODEL).replace("models/", "")
    print(f"3. Computing embeddings via Google API model: {embed_model}")
    print(f"   Processing {len(leaf_chunks)} chunks in batches of 100...")

    texts = [c.get("text", "") for c in leaf_chunks]
    embeddings_list: list[list[float]] = []

    for i in range(0, len(texts), 100):
        batch = texts[i : i + 100]
        result = genai_client.models.embed_content(
            model=embed_model,
            contents=batch,
        )
        for emb in result.embeddings:
            embeddings_list.append(list(emb.values))
        print(f"   Embedded {min(i + 100, len(texts))}/{len(texts)} chunks...")

    import numpy as np_local
    embeddings = np_local.array(embeddings_list, dtype="float32")
    actual_dim = embeddings.shape[1]
    print(f"   Embedding dim: {actual_dim}")

    if len(embeddings) != len(leaf_chunks):
        print(f"[ERROR] Mismatch: {len(leaf_chunks)} chunks vs {len(embeddings)} embeddings.")
        sys.exit(1)

    # Create/re-create Qdrant collection using the actual embedding dimension
    print(f"\n4. Preparing Qdrant collection '{collection_name}' (dim={actual_dim}, Distance=COSINE)...")
    try:
        if client.collection_exists(collection_name):
            client.delete_collection(collection_name)

        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=actual_dim, distance=Distance.COSINE)
        )
        print(f"   Created collection '{collection_name}' (dim={actual_dim}) successfully.")
    except Exception as exc:
        print(f"   Warning preparing collection: {exc}. Attempting upload...")


    # Upload points in batches of 100
    batch_size = 100
    total_points = len(leaf_chunks)
    print(f"5. Pushing {total_points} vectors to Qdrant Cloud in batches of {batch_size}...")

    points = []
    for idx, (chunk, vector) in enumerate(zip(leaf_chunks, embeddings)):
        point_id = idx + 1  # integer ID
        payload = {
            "chunk_id": chunk.get("id", chunk.get("chunk_id", f"leaf-{idx}")),
            "text": chunk.get("text", ""),
            "law_title": chunk.get("law_title", ""),
            "unit_number": chunk.get("unit_number", ""),
            "raw_unit": chunk.get("raw_unit", ""),
            "sub_unit_marker": chunk.get("sub_unit_marker", ""),
            "chapter": chunk.get("chapter", ""),
            "unit_title": chunk.get("unit_title", ""),
            "doc_type": chunk.get("doc_type", "act"),
            "parent_id": chunk.get("parent_id", "")
        }
        points.append(PointStruct(id=point_id, vector=vector.tolist(), payload=payload))

        if len(points) >= batch_size or idx == total_points - 1:
            client.upsert(collection_name=collection_name, points=points)
            print(f"   Uploaded points {idx + 1 - len(points) + 1} to {idx + 1} of {total_points}")
            points = []

    print("\n[SUCCESS] All vector embeddings pushed to Qdrant Cloud!")
    print(f"   Collection: {collection_name}")
    print("   Your Vercel backend can now retrieve vectors from Qdrant Cloud.")
    print("=" * 60)


if __name__ == "__main__":
    main()
