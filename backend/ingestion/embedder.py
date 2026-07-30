"""
ingestion/embedder.py
~~~~~~~~~~~~~~~~~~~~~~
Embed all leaf chunk texts using BAAI/bge-small-en-v1.5 via sentence-transformers.

Features
--------
* Content-hash-based caching: embeddings are only recomputed when the source
  texts have changed (checked via SHA-256 of the sorted JSON of all texts).
* tqdm progress bar during embedding.
* Persists to data/processed/embeddings_cache.npz (numpy compressed).
* Returns embeddings as a numpy float32 array aligned with the leaf chunk list.
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Hash helper
# ---------------------------------------------------------------------------

def _compute_source_hash(leaf_chunks: list[dict[str, Any]]) -> str:
    """SHA-256 of the concatenated texts (in list order) – used for cache validation."""
    texts = [c["text"] for c in leaf_chunks]
    payload = json.dumps(texts, ensure_ascii=False, sort_keys=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


# ---------------------------------------------------------------------------
# Core embedding logic
# ---------------------------------------------------------------------------

def _load_model(model_name: str):
    """Lazy-import SentenceTransformer and load the model."""
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "sentence-transformers is not installed. "
            "Run: pip install sentence-transformers"
        ) from exc
    logger.info("Loading embedding model: %s", model_name)
    return SentenceTransformer(model_name)


def embed_chunks(
    leaf_chunks: list[dict[str, Any]],
    model_name: str,
    batch_size: int,
    cache_path: Path,
    hash_path: Path,
    force_recompute: bool = False,
) -> np.ndarray:
    """
    Return a (N, D) float32 numpy array of embeddings aligned with *leaf_chunks*.

    The result is cached to *cache_path* (.npz).  On re-run the hash of the
    input texts is compared against *hash_path*; if unchanged the cache is
    returned immediately.

    Parameters
    ----------
    leaf_chunks     : list of unified leaf chunk dicts
    model_name      : HuggingFace model identifier
    batch_size      : encoding batch size
    cache_path      : path to the .npz cache file
    hash_path       : path to the plain-text hash file
    force_recompute : if True, always re-embed even if cache is valid

    Returns
    -------
    embeddings : numpy float32 array of shape (len(leaf_chunks), dim)
    """
    current_hash = _compute_source_hash(leaf_chunks)

    # --- Check cache validity ---
    if not force_recompute and cache_path.exists() and hash_path.exists():
        stored_hash = hash_path.read_text(encoding="utf-8").strip()
        if stored_hash == current_hash:
            logger.info("Embedding cache is valid. Loading from %s", cache_path)
            data = np.load(str(cache_path))
            embeddings = data["embeddings"]
            logger.info(
                "Loaded %d embeddings of dim %d from cache.",
                embeddings.shape[0], embeddings.shape[1],
            )
            return embeddings
        else:
            logger.info("Embedding cache is stale (hash mismatch). Re-embedding …")
    else:
        logger.info("No valid embedding cache found. Computing embeddings …")

    # --- Compute embeddings ---
    model = _load_model(model_name)
    texts = [chunk["text"] for chunk in leaf_chunks]

    try:
        from tqdm import tqdm  # type: ignore
        show_progress = True
    except ImportError:
        show_progress = False

    logger.info(
        "Embedding %d texts with batch_size=%d …", len(texts), batch_size
    )
    embeddings: np.ndarray = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=show_progress,
        normalize_embeddings=True,   # bge models prefer normalised embeddings for cosine
        convert_to_numpy=True,
    ).astype(np.float32)

    logger.info(
        "Embedding done: shape=%s, dtype=%s", embeddings.shape, embeddings.dtype
    )

    # --- Persist ---
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(str(cache_path), embeddings=embeddings)
    hash_path.write_text(current_hash, encoding="utf-8")
    logger.info("Saved embedding cache -> %s", cache_path)

    return embeddings
