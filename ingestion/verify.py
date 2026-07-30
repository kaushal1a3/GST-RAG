"""
ingestion/verify.py
~~~~~~~~~~~~~~~~~~~~
Phase 1 self-check script.

Reports
-------
* Total leaf chunks indexed
* Total parent chunks
* Records skipped during load (with reasons)
* Embedding dimension
* ChromaDB collection item count
* BM25 corpus size

Sanity queries
--------------
Runs 3 sample queries against BOTH ChromaDB and BM25 independently and prints
the top-3 hits (law_title + unit_number + sub_unit_marker) for eyeballing.

Run:
    python -m ingestion.verify
"""
from __future__ import annotations

import io
import json
import logging
import pickle
import re
import sys
from pathlib import Path
from typing import Any

# Fix Windows cp1252 console encoding
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import config
from ingestion.loader import load_all
from ingestion.chunker import load_chunks

logging.basicConfig(
    level=logging.WARNING,           # keep noisy libs quiet during verify
    format="%(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hr(char: str = "-", width: int = 70) -> None:
    print(char * width)


def _section(title: str) -> None:
    _hr("=")
    print(f"  {title}")
    _hr("=")


def _tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if t]


def _format_hit(meta: dict[str, Any], score_label: str, score: Any) -> str:
    law = meta.get("law_title", meta.get("metadata", {}).get("law_title", "?"))
    unit = meta.get("raw_unit", meta.get("metadata", {}).get("raw_unit", "?"))
    marker = meta.get("sub_unit_marker", meta.get("metadata", {}).get("sub_unit_marker", "?"))
    return f"  [{score_label}={score:.4f}]  {law}  |  {unit}  |  {marker}"


# ---------------------------------------------------------------------------
# Stats section
# ---------------------------------------------------------------------------

def print_stats() -> dict[str, Any]:
    _section("1. CHUNK STATISTICS")

    # Load chunks
    leaf_chunks, parent_chunks, leaf_to_parent_map = load_chunks(config.PROCESSED_DIR)

    act_leaves = sum(1 for c in leaf_chunks if c.get("doc_type") == "act")
    rule_leaves = sum(1 for c in leaf_chunks if c.get("doc_type") == "rule")

    print(f"  Leaf chunks (total)  : {len(leaf_chunks):,}")
    print(f"    • Acts             : {act_leaves:,}")
    print(f"    • Rules            : {rule_leaves:,}")
    print(f"  Parent chunks        : {len(parent_chunks):,}")
    print(f"  Leaf→parent map size : {len(leaf_to_parent_map):,}")
    _hr()

    # Skipped records (re-run loader quickly)
    _section("2. LOADER SKIP REPORT")
    try:
        _, all_skipped, _ = load_all(config.ACT_CHUNKS_FILE, config.RULE_CHUNKS_FILE)
        if all_skipped:
            print(f"  {len(all_skipped)} record(s) skipped:")
            for s in all_skipped:
                print(f"    index={s.get('_index')}  reason={s.get('_skip_reason')}")
        else:
            print("  ✓ No records skipped – all source records loaded cleanly.")
    except Exception as exc:
        print(f"  ⚠ Could not re-run loader: {exc}")
    _hr()

    # Embeddings
    _section("3. EMBEDDING CACHE")
    import numpy as np
    emb_path = config.EMBEDDINGS_CACHE_FILE
    if emb_path.exists():
        data = np.load(str(emb_path))
        emb = data["embeddings"]
        print(f"  Cache file     : {emb_path}")
        print(f"  Shape          : {emb.shape}  (N × D)")
        print(f"  Dtype          : {emb.dtype}")
        print(f"  Dimension (D)  : {emb.shape[1]}")
        dim = emb.shape[1]
    else:
        print("  ⚠ Embedding cache not found!")
        dim = -1
    _hr()

    # ChromaDB
    _section("4. CHROMADB COLLECTION")
    try:
        import chromadb  # type: ignore
        client = chromadb.PersistentClient(path=str(config.CHROMA_DB_DIR))
        col = client.get_collection(config.CHROMA_COLLECTION_NAME)
        count = col.count()
        print(f"  Collection name  : {config.CHROMA_COLLECTION_NAME}")
        print(f"  Item count       : {count:,}")
        print(f"  DB path          : {config.CHROMA_DB_DIR}")
        chroma_ok = True
    except Exception as exc:
        print(f"  ⚠ ChromaDB error: {exc}")
        chroma_ok = False
        count = 0
    _hr()

    # BM25
    _section("5. BM25 INDEX")
    bm25_path = config.BM25_INDEX_FILE
    ids_path = config.BM25_IDS_FILE
    if bm25_path.exists() and ids_path.exists():
        with bm25_path.open("rb") as fh:
            bm25 = pickle.load(fh)
        with ids_path.open("r", encoding="utf-8") as fh:
            bm25_ids = json.load(fh)
        print(f"  BM25 index file  : {bm25_path}")
        print(f"  Corpus size      : {len(bm25.idf):,} unique tokens")
        print(f"  Document count   : {len(bm25_ids):,}")
        bm25_ok = True
    else:
        print("  ⚠ BM25 index not found!")
        bm25_ok = False
        bm25 = None
        bm25_ids = []
    _hr()

    return {
        "leaf_chunks": leaf_chunks,
        "parent_chunks": parent_chunks,
        "chroma_ok": chroma_ok,
        "bm25_ok": bm25_ok,
        "bm25": bm25 if bm25_ok else None,
        "bm25_ids": bm25_ids,
    }


# ---------------------------------------------------------------------------
# Sanity query section
# ---------------------------------------------------------------------------

SAMPLE_QUERIES = [
    "input tax credit",
    "composition scheme",
    "e-way bill",
]


def run_sanity_queries(state: dict[str, Any]) -> None:
    _section("6. SANITY QUERIES (top-3 per index)")

    leaf_map = {c["id"]: c for c in state["leaf_chunks"]}

    # --- Vector / ChromaDB ---
    if state["chroma_ok"]:
        print("\n  ── ChromaDB (vector similarity) ──")
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            import chromadb  # type: ignore

            model = SentenceTransformer(config.EMBEDDING_MODEL_NAME)
            client = chromadb.PersistentClient(path=str(config.CHROMA_DB_DIR))
            col = client.get_collection(config.CHROMA_COLLECTION_NAME)

            for query in SAMPLE_QUERIES:
                qvec = model.encode(
                    query, normalize_embeddings=True
                ).tolist()
                results = col.query(
                    query_embeddings=[qvec],
                    n_results=3,
                    include=["metadatas", "distances"],
                )
                print(f"\n  Query: '{query}'")
                metas = results["metadatas"][0]
                dists = results["distances"][0]
                for meta, dist in zip(metas, dists):
                    score = 1.0 - dist  # cosine distance → similarity
                    law = meta.get("law_title", "?")
                    unit = meta.get("raw_unit", "?")
                    marker = meta.get("sub_unit_marker", "?")
                    print(f"    [sim={score:.4f}]  {law}  |  {unit}  |  {marker}")
        except Exception as exc:
            print(f"  ⚠ Vector query failed: {exc}")
    else:
        print("  ⚠ Skipping vector queries – ChromaDB not available.")

    # --- BM25 ---
    if state["bm25_ok"]:
        print("\n  ── BM25 (keyword / exact) ──")
        bm25 = state["bm25"]
        bm25_ids = state["bm25_ids"]

        import numpy as np

        for query in SAMPLE_QUERIES:
            tokens = _tokenize(query)
            scores = bm25.get_scores(tokens)
            top_indices = np.argsort(scores)[::-1][:3]
            print(f"\n  Query: '{query}'")
            for idx in top_indices:
                chunk_id = bm25_ids[idx]
                chunk = leaf_map.get(chunk_id, {})
                score = scores[idx]
                law = chunk.get("law_title", "?")
                unit = chunk.get("raw_unit", "?")
                marker = chunk.get("sub_unit_marker", "?")
                print(f"    [bm25={score:.4f}]  {law}  |  {unit}  |  {marker}")
    else:
        print("  ⚠ Skipping BM25 queries – index not available.")

    _hr()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print()
    print("  GST RAG – Phase 1 Verification Report")
    print()
    state = print_stats()
    run_sanity_queries(state)
    print()
    print("  Verification complete.")
    print()
