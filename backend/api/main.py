"""
api/main.py
~~~~~~~~~~~
FastAPI Web Service for Indian GST Retrieval-Augmented Generation (RAG).

Endpoints
---------
POST /query
    Request:  { "question": str, "top_k": int (optional), "provider": str (optional) }
    Response: { "question": str, "answer": str, "citations": [...], "retrieved_chunk_ids": [...] }

GET /health
    Response: { "status": "ok", "leaf_chunks_count": int, "parent_chunks_count": int, ... }

POST /reindex
    Request:  { "confirm": bool }
    Response: { "status": str, "message": str }
"""
from __future__ import annotations

import io
import json
import logging
import sys
import urllib.parse
from pathlib import Path
from typing import Any, Optional

# UTF-8 stdout fix for Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import config
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from retrieval.pipeline import retrieve
from retrieval.llm_query_router import analyze_and_route_query
from generation.llm_client import generate_answer
from ingestion.build_index import run_pipeline

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# FastAPI App Initialization
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Indian GST RAG API",
    description="Zero-cost, grounded RAG system for querying Indian Goods and Services Tax law.",
    version="1.0.0",
)

import os


def extract_path_from_header_value(val: bytes) -> str | None:
    try:
        decoded = val.decode("utf-8")
        if decoded.startswith("http://") or decoded.startswith("https://"):
            parsed = urllib.parse.urlparse(decoded)
            return parsed.path
        return decoded
    except Exception:
        return None


class VercelPathMiddleware:
    """
    ASGI middleware to restore the original request path from Vercel's proxy headers.
    When Vercel rewrites `/(.*)` to `/api/index`, the request path inside ASGI is changed to
    `/api/index`, which breaks FastAPI routing. This middleware extracts the original path
    from Vercel-specific request headers and overrides `scope["path"]` before routing.
    """
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))

            # Check Vercel-specific headers to find the original matched route path
            original_path = None
            for header_name in [b"x-matched-path", b"x-vercel-matched-path", b"x-original-url", b"x-forwarded-url"]:
                if header_name in headers:
                    path = extract_path_from_header_value(headers[header_name])
                    if path:
                        if not path.startswith("/"):
                            path = "/" + path
                        original_path = path
                        break

            if original_path:
                logger.info("Rewriting ASGI path from %r to %r based on headers", scope.get("path"), original_path)
                scope["path"] = original_path

        await self.app(scope, receive, send)


# Add VercelPathMiddleware to handle routing correctly under Vercel's rewrites
app.add_middleware(VercelPathMiddleware)

# Allow all origins for CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.options("/{full_path:path}")
def options_catch_all(full_path: str):
    """Explicit catch-all OPTIONS handler to ensure CORS preflight requests succeed with 200 OK."""
    return JSONResponse(status_code=200, content={"status": "ok"})





# ---------------------------------------------------------------------------
# Request & Response Schemas
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    question: str = Field(
        ...,
        description="Natural-language GST legal question.",
        example="What does Section 16 of CGST Act say about ITC eligibility?",
    )
    top_k: Optional[int] = Field(
        default=None,
        description="Number of context chunks to retrieve (default: config.RERANKER_TOP_K).",
        ge=1,
        le=20,
    )
    provider: Optional[str] = Field(
        default="gemini",
        description="LLM provider (fixed to 'gemini').",
    )


class Citation(BaseModel):
    law_title: str
    unit_number: str
    sub_unit_marker: str
    snippet: str


class QueryResponse(BaseModel):
    question: str
    answer: str
    citations: list[Citation]
    retrieved_chunk_ids: list[str]
    needs_vector_db_search: Optional[bool] = True
    search_queries: Optional[list[str]] = None


class AgentCitation(BaseModel):
    law_title: str
    unit_number: str
    sub_unit_marker: str


class AgentQueryResponse(BaseModel):
    question: str
    answer: str
    citations: list[AgentCitation]
    tool_calls_made: int
    provider_used: str


class HealthResponse(BaseModel):
    status: str
    leaf_chunks_count: int
    parent_chunks_count: int
    chroma_loaded: bool
    bm25_loaded: bool
    embedding_model: str
    llm_provider: str


class ReindexRequest(BaseModel):
    confirm: bool = Field(
        ...,
        description="Must be set to true to execute index wipe and rebuild.",
    )


class ReindexResponse(BaseModel):
    status: str
    message: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/", tags=["General"])
@app.get("/api", tags=["General"])
@app.get("/api/index", tags=["General"])
def root():
    """Welcome endpoint pointing to docs."""
    return {
        "title": "Indian GST RAG API",
        "docs_url": "/docs",
        "health_url": "/health",
        "query_url": "/query",
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
@app.get("/api/health", response_model=HealthResponse, tags=["Health"])
@app.get("/api/index/health", response_model=HealthResponse, tags=["Health"])
def health_check():

    """Return system operational and index loading status."""
    leaf_count = 0
    parent_count = 0
    chroma_ok = False
    bm25_ok = config.BM25_INDEX_FILE.exists()

    if config.LEAF_CHUNKS_FILE.exists():
        try:
            with open(config.LEAF_CHUNKS_FILE, "r", encoding="utf-8") as fh:
                leaf_count = len(json.load(fh))
        except Exception:
            pass

    if config.PARENT_CHUNKS_FILE.exists():
        try:
            with open(config.PARENT_CHUNKS_FILE, "r", encoding="utf-8") as fh:
                parent_count = len(json.load(fh))
        except Exception:
            pass

    try:
        import chromadb  # type: ignore
        client = chromadb.PersistentClient(path=str(config.CHROMA_DB_DIR))
        col = client.get_collection(config.CHROMA_COLLECTION_NAME)
        chroma_ok = col.count() > 0
    except Exception:
        chroma_ok = False

    return HealthResponse(
        status="ok",
        leaf_chunks_count=leaf_count,
        parent_chunks_count=parent_count,
        chroma_loaded=chroma_ok,
        bm25_loaded=bm25_ok,
        embedding_model=config.EMBEDDING_MODEL_NAME,
        llm_provider=config.LLM_PROVIDER,
    )


@app.post("/query", response_model=QueryResponse, tags=["RAG Query"])
@app.post("/api/query", response_model=QueryResponse, tags=["RAG Query"])
@app.post("/api/index/query", response_model=QueryResponse, tags=["RAG Query"])
def handle_query(req: QueryRequest):
    """
    Process a natural language GST query through the end-to-end RAG pipeline:
    1. First LLM Call: Route query & decide if vector DB search is needed.
    2. Vector DB Retrieval using LLM-formulated search queries (if needed).
    3. Second LLM Call: Grounded LLM generation with citations.
    """
    question = req.question.strip()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question parameter cannot be empty.",
        )

    top_k = req.top_k or config.RERANKER_TOP_K
    provider = "gemini"

    logger.info("API /query received: %r (top_k=%d, provider=%s)", question[:80], top_k, provider)

    try:
        # 1. First LLM Call: analyze query to determine if vector DB search is required & formulate search terms
        routing = analyze_and_route_query(user_prompt=question, provider=provider)

        if not routing.needs_vector_db_search:
            logger.info("Vector DB search skipped by LLM router for query %r", question[:80])
            return QueryResponse(
                question=question,
                answer=routing.direct_response or "Hello! How can I assist you with Indian GST law today?",
                citations=[],
                retrieved_chunk_ids=[],
                needs_vector_db_search=False,
                search_queries=[],
            )

        # 2. Retrieval using LLM-formulated search query
        search_query = routing.search_queries[0] if routing.search_queries else question
        logger.info("Executing vector DB search with LLM-formulated query: %r", search_query[:80])
        chunks = retrieve(query=search_query, final_top_k=top_k)

        # 3. Second LLM Call: Answer generation grounded on retrieved chunks
        answer = generate_answer(query=question, context_chunks=chunks, provider=provider)

        # 3. Format citations
        citations: list[Citation] = []
        retrieved_ids: list[str] = []

        for c in chunks:
            chunk_id = c.get("id", "")
            retrieved_ids.append(chunk_id)

            meta = c.get("metadata", {})
            law = c.get("parent_law_title") or meta.get("law_title", "GST Law")
            unit_num = c.get("parent_unit_number") or meta.get("unit_number", "N/A")
            raw_unit = c.get("parent_raw_unit") or meta.get("raw_unit", f"Section {unit_num}")
            marker = meta.get("sub_unit_marker", "Intro/General")

            snippet_text = c.get("expanded_context") or c.get("document", "")
            snippet = snippet_text[:250].replace("\n", " ").strip() + "..." if snippet_text else ""

            citations.append(
                Citation(
                    law_title=law,
                    unit_number=raw_unit,
                    sub_unit_marker=marker,
                    snippet=snippet,
                )
            )

        return QueryResponse(
            question=question,
            answer=answer,
            citations=citations,
            retrieved_chunk_ids=retrieved_ids,
            needs_vector_db_search=True,
            search_queries=routing.search_queries,
        )

    except Exception as exc:
        logger.error("Error processing query %r: %s", question, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during query processing: {exc}",
        ) from exc


@app.post("/agent-query", response_model=AgentQueryResponse, tags=["Agentic RAG"])
@app.post("/api/agent-query", response_model=AgentQueryResponse, tags=["Agentic RAG"])
@app.post("/api/index/agent-query", response_model=AgentQueryResponse, tags=["Agentic RAG"])
def handle_agent_query(req: QueryRequest):
    """
    Process a GST query through the LangChain agentic loop with LLM tool calling.

    The agent autonomously decides:
    - Which retrieval tools to invoke (hybrid search, section lookup, parent text)
    - How many retrieval loops to run before generating the final answer
    - When it has sufficient grounded context to stop looping

    This endpoint requires a valid LLM API key (GEMINI_API_KEY / ANTHROPIC_API_KEY)
    configured in config.py or as an environment variable.
    Falls back to mock single-pass if no key is configured.
    """
    question = req.question.strip()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question parameter cannot be empty.",
        )

    provider = "gemini"
    logger.info(
        "API /agent-query received: %r (provider=%s)", question[:80], provider
    )

    try:
        from generation.lc_agent import run_agent
        result = run_agent(query=question, provider=provider)

        return AgentQueryResponse(
            question=question,
            answer=result["answer"],
            citations=[
                AgentCitation(
                    law_title=c.get("law_title", ""),
                    unit_number=c.get("unit_number", ""),
                    sub_unit_marker=c.get("sub_unit_marker", ""),
                )
                for c in result.get("citations", [])
            ],
            tool_calls_made=result["tool_calls_made"],
            provider_used=result["provider_used"],
        )

    except Exception as exc:
        logger.error(
            "Error in /agent-query for %r: %s", question, exc, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent query failed: {exc}",
        ) from exc


@app.post("/reindex", response_model=ReindexResponse, tags=["Admin"])
@app.post("/api/reindex", response_model=ReindexResponse, tags=["Admin"])
@app.post("/api/index/reindex", response_model=ReindexResponse, tags=["Admin"])
def handle_reindex(req: ReindexRequest):

    """Re-run Phase 1 ingestion to wipe and rebuild indexes."""
    if not req.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation required. Set 'confirm: true' in request body to reindex.",
        )

    logger.warning("API /reindex triggered. Rebuilding indexes from scratch ...")
    try:
        run_pipeline(reset=True)
        return ReindexResponse(
            status="reindexed",
            message="Ingestion pipeline completed successfully. Indexes have been rebuilt.",
        )
    except Exception as exc:
        logger.error("Reindexing failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reindexing failed: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# Mount React 18 Frontend Static Files (local dev only — skip on Vercel)
# ---------------------------------------------------------------------------
_is_vercel = os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV")
if not _is_vercel:
    _frontend_dist = _PROJECT_ROOT / "frontend" / "dist"
    _frontend_dir = _PROJECT_ROOT / "frontend"
    if _frontend_dist.exists():
        app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
    elif _frontend_dir.exists():
        app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")


# ---------------------------------------------------------------------------
# Main CLI Entry Point for running via python -m api.main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True)
