"""
ingestion/build_index.py
~~~~~~~~~~~~~~~~~~~~~~~~~
Orchestrates the full ingestion pipeline:

  load -> normalize -> chunk -> embed -> ChromaDB upsert + BM25 build

Run as:
    python -m ingestion.build_index          # normal run
    python -m ingestion.build_index --reset  # wipe and rebuild from scratch

Steps
-----
1. Load raw JSON files via loader.py
2. Normalise records via normalizer.py
3. Build leaf / parent chunks via chunker.py
4. Embed leaf chunk texts via embedder.py (with disk cache)
5. Upsert into local ChromaDB collection "gst_leaf_chunks"
6. Build BM25 index (rank_bm25) and pickle to disk
"""
from __future__ import annotations

import argparse
import json
import logging
import pickle
import re
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path when run as __main__
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import config
from ingestion.loader import load_all
from ingestion.normalizer import normalize_all
from ingestion.chunker import build_chunks, save_chunks
from ingestion.embedder import embed_chunks

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# BM25 helpers
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    """Simple tokenizer: lowercase + split on non-alphanumeric."""
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if t]


def build_bm25(
    leaf_chunks: list[dict[str, Any]],
    bm25_path: Path,
    ids_path: Path,
) -> None:
    """
    Build a BM25Okapi index over *leaf_chunks* and pickle it.

    Also stores the ordered list of chunk IDs as JSON so retrieval can map
    BM25 result indices back to chunk IDs.
    """
    try:
        from rank_bm25 import BM25Okapi  # type: ignore
    except ImportError as exc:
        raise ImportError("rank_bm25 not installed. Run: pip install rank-bm25") from exc

    logger.info("Tokenising %d texts for BM25 …", len(leaf_chunks))
    corpus = [_tokenize(c["text"]) for c in leaf_chunks]
    ids = [c["id"] for c in leaf_chunks]

    logger.info("Building BM25Okapi index …")
    bm25 = BM25Okapi(corpus)

    bm25_path.parent.mkdir(parents=True, exist_ok=True)
    with bm25_path.open("wb") as fh:
        pickle.dump(bm25, fh, protocol=pickle.HIGHEST_PROTOCOL)
    logger.info("BM25 index saved -> %s", bm25_path)

    with ids_path.open("w", encoding="utf-8") as fh:
        json.dump(ids, fh, ensure_ascii=False)
    logger.info("BM25 ID list saved -> %s", ids_path)


# ---------------------------------------------------------------------------
# ChromaDB helpers
# ---------------------------------------------------------------------------

def _get_chroma_client(db_path: Path):
    """Create / return a persistent ChromaDB client."""
    try:
        import chromadb  # type: ignore
    except ImportError as exc:
        raise ImportError("chromadb not installed. Run: pip install chromadb") from exc

    db_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(db_path))
    return client


def upsert_to_chroma(
    leaf_chunks: list[dict[str, Any]],
    embeddings,                    # np.ndarray shape (N, D)
    db_path: Path,
    collection_name: str,
    reset: bool = False,
) -> None:
    """
    Upsert all leaf chunks into ChromaDB with their embeddings and metadata.

    Parameters
    ----------
    reset : if True, deletes and recreates the collection first.
    """
    import numpy as np  # local import – numpy must be installed

    client = _get_chroma_client(db_path)

    if reset:
        try:
            client.delete_collection(collection_name)
            logger.info("Deleted existing collection '%s'.", collection_name)
        except Exception:
            pass  # collection didn't exist

    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )
    logger.info(
        "ChromaDB collection '%s' has %d existing items.",
        collection_name, collection.count(),
    )

    ids = [c["id"] for c in leaf_chunks]
    documents = [c["text"] for c in leaf_chunks]

    # ChromaDB metadata values must be str / int / float / bool – None not allowed
    def _safe(v: Any) -> str:
        return str(v) if v is not None else ""

    metadatas = [
        {
            "doc_type":        _safe(c.get("doc_type")),
            "law_title":       _safe(c.get("law_title")),
            "chapter":         _safe(c.get("chapter")),
            "unit_number":     _safe(c.get("unit_number")),
            "raw_unit":        _safe(c.get("raw_unit")),
            "unit_title":      _safe(c.get("unit_title")),
            "sub_unit_marker": _safe(c.get("sub_unit_marker")),
            "date":            _safe(c.get("date")),
            "parent_id":       _safe(c.get("parent_id")),
        }
        for c in leaf_chunks
    ]

    embed_list = embeddings.tolist()

    # Upsert in batches to avoid OOM and ChromaDB request-size limits
    BATCH = 500
    total = len(ids)
    for start in range(0, total, BATCH):
        end = min(start + BATCH, total)
        collection.upsert(
            ids=ids[start:end],
            embeddings=embed_list[start:end],
            documents=documents[start:end],
            metadatas=metadatas[start:end],
        )
        logger.info("  Upserted batch %d/%d (items %d–%d)", start // BATCH + 1,
                    (total + BATCH - 1) // BATCH, start, end - 1)

    final_count = collection.count()
    logger.info(
        "ChromaDB upsert complete. Collection '%s' now has %d items.",
        collection_name, final_count,
    )


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_pipeline(reset: bool = False) -> None:
    """Execute the full ingestion pipeline end-to-end."""
    logger.info("=" * 60)
    logger.info("GST RAG – Ingestion Pipeline")
    logger.info("=" * 60)

    # ------------------------------------------------------------------
    # 1. Load
    # ------------------------------------------------------------------
    logger.info("[1/6] Loading raw source files …")
    all_valid, all_skipped, _ = load_all(
        act_path=config.ACT_CHUNKS_FILE,
        rule_path=config.RULE_CHUNKS_FILE,
    )
    if all_skipped:
        logger.warning("  %d records were skipped during load.", len(all_skipped))

    # ------------------------------------------------------------------
    # 2. Normalise
    # ------------------------------------------------------------------
    logger.info("[2/6] Normalising records …")
    normalized, norm_warnings = normalize_all(all_valid)
    for w in norm_warnings:
        logger.warning("  NORM: %s", w)
    logger.info("  %d records normalised (%d warnings).", len(normalized), len(norm_warnings))

    # ------------------------------------------------------------------
    # 3. Chunk
    # ------------------------------------------------------------------
    logger.info("[3/6] Building chunks …")
    leaf_chunks, parent_chunks, leaf_to_parent_map = build_chunks(normalized)
    save_chunks(leaf_chunks, parent_chunks, leaf_to_parent_map, config.PROCESSED_DIR)

    # ------------------------------------------------------------------
    # 4. Embed
    # ------------------------------------------------------------------
    logger.info("[4/6] Embedding leaf chunks …")
    embeddings = embed_chunks(
        leaf_chunks=leaf_chunks,
        model_name=config.EMBEDDING_MODEL_NAME,
        batch_size=config.EMBEDDING_BATCH_SIZE,
        cache_path=config.EMBEDDINGS_CACHE_FILE,
        hash_path=config.EMBEDDINGS_HASH_FILE,
        force_recompute=reset,
    )

    # ------------------------------------------------------------------
    # 5. ChromaDB upsert
    # ------------------------------------------------------------------
    logger.info("[5/6] Upserting into ChromaDB …")
    upsert_to_chroma(
        leaf_chunks=leaf_chunks,
        embeddings=embeddings,
        db_path=config.CHROMA_DB_DIR,
        collection_name=config.CHROMA_COLLECTION_NAME,
        reset=reset,
    )

    # ------------------------------------------------------------------
    # 6. BM25
    # ------------------------------------------------------------------
    logger.info("[6/6] Building BM25 index …")
    build_bm25(
        leaf_chunks=leaf_chunks,
        bm25_path=config.BM25_INDEX_FILE,
        ids_path=config.BM25_IDS_FILE,
    )

    logger.info("=" * 60)
    logger.info("Ingestion pipeline complete.")
    logger.info(
        "  Leaf chunks  : %d", len(leaf_chunks)
    )
    logger.info(
        "  Parent chunks: %d", len(parent_chunks)
    )
    logger.info("=" * 60)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build GST RAG ingestion indexes."
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Wipe existing indexes and rebuild from scratch.",
    )
    args = parser.parse_args()
    run_pipeline(reset=args.reset)
