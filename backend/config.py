"""
config.py – Central configuration for the GST RAG system.
All path, model, and runtime settings live here so every module imports
from one place.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Root paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.resolve()
load_dotenv(PROJECT_ROOT / ".env")
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

# ---------------------------------------------------------------------------
# Source data files (user puts these here)
# ---------------------------------------------------------------------------
ACT_CHUNKS_FILE = PROCESSED_DIR / "normalized_act_chunks.json"
RULE_CHUNKS_FILE = PROCESSED_DIR / "normalized_rule_chunks.json"

# ---------------------------------------------------------------------------
# Processed / index artefacts
# ---------------------------------------------------------------------------
LEAF_CHUNKS_FILE = PROCESSED_DIR / "leaf_chunks.json"
PARENT_CHUNKS_FILE = PROCESSED_DIR / "parent_chunks.json"
LEAF_TO_PARENT_MAP_FILE = PROCESSED_DIR / "leaf_to_parent_map.json"
EMBEDDINGS_CACHE_FILE = PROCESSED_DIR / "embeddings_cache.npz"
EMBEDDINGS_HASH_FILE = PROCESSED_DIR / "embeddings_source_hash.txt"
BM25_INDEX_FILE = PROCESSED_DIR / "bm25_index.pkl"
BM25_IDS_FILE = PROCESSED_DIR / "bm25_ids.json"
CHROMA_DB_DIR = PROCESSED_DIR / "chroma_db"

# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Embedding model (Gemini Embedding 2 / text-embedding-004)
# ---------------------------------------------------------------------------
EMBEDDING_MODEL_NAME: str = "BAAI/bge-small-en-v1.5"   # kept for local FastEmbed fallback
EMBEDDING_BATCH_SIZE: int = 128
EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "768"))   # 768 for Google text-embedding-004

# Google embedding model (Gemini Embedding 2 – no local download needed)
GOOGLE_EMBEDDING_MODEL: str = os.getenv("GOOGLE_EMBEDDING_MODEL", "gemini-embedding-2")

# ---------------------------------------------------------------------------
# Vector Store Settings (Qdrant Cloud)
# ---------------------------------------------------------------------------
VECTOR_DB_PROVIDER: str = "qdrant"
QDRANT_URL: str = os.getenv("QDRANT_URL", "")
QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")
QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "gst_leaf_chunks")



# ---------------------------------------------------------------------------
# BM25 tokenisation
# ---------------------------------------------------------------------------
BM25_TOKENIZE_PATTERN: str = r"[^a-z0-9]"  # split on non-alphanumeric after lower

# ---------------------------------------------------------------------------
# LLM / Generation  (Phase 3 – provider-agnostic)
# ---------------------------------------------------------------------------
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini")  # "gemini" | "ollama"
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")

# ---------------------------------------------------------------------------
# Retrieval knobs
# ---------------------------------------------------------------------------
VECTOR_TOP_K: int = 10
BM25_TOP_K: int = 10
HYBRID_TOP_K: int = 5       # after reranking / fusion
BM25_WEIGHT: float = 0.4    # weight in Reciprocal Rank Fusion
VECTOR_WEIGHT: float = 0.6
RRF_K: int = 60             # RRF constant
CITATION_BOOST: float = 2.0 # score multiplier for explicit citation matches

# ---------------------------------------------------------------------------
# Reranker
# ---------------------------------------------------------------------------
RERANKER_ENABLED: bool = True
RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
RERANKER_TOP_K: int = 5     # final results after reranking (from HYBRID_TOP_K candidates)
RERANKER_CANDIDATES: int = 20  # how many fused candidates to feed into reranker

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# ---------------------------------------------------------------------------
# LangChain Agentic RAG  (Phase 3 extension)
# ---------------------------------------------------------------------------
LANGCHAIN_AGENT_ENABLED: bool = True
AGENT_MAX_ITERATIONS: int = int(os.getenv("AGENT_MAX_ITERATIONS", "5"))
AGENT_VERBOSE: bool = os.getenv("AGENT_VERBOSE", "true").lower() == "true"
