# 🧾 GST RAG — Retrieval-Augmented Generation for Indian GST Law

> A production-ready Retrieval-Augmented Generation (RAG) system for querying Indian Goods and Services Tax legislation (Acts + Rules), delivering precise legal citations and fully grounded responses.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Node](https://img.shields.io/badge/Node.js-18+-339933.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688.svg)
![React](https://img.shields.io/badge/React-18-61DAFB.svg)

---

## 📌 Overview

**GST RAG** combines hybrid retrieval (semantic + lexical), cross-encoder reranking, and an LLM-driven generation layer to answer questions about Indian GST law with **verifiable, section-level citations**. It is designed to minimize hallucination risk in a domain — tax law — where precision is non-negotiable.

Every answer the system produces is traceable back to a specific Act, Section, and Sub-clause in the source legislation.

---

## ✨ Key Features

- **Hybrid Retrieval** — combines dense semantic search (Qdrant) with sparse lexical search (BM25) merged via Reciprocal Rank Fusion (RRF).
- **Cross-Encoder Reranking** — a lightweight `ms-marco-MiniLM-L-6-v2` reranker re-scores top candidates for relevance before generation.
- **Grounded Legal Generation** — every claim in a generated answer is required to trace back to a retrieved statutory chunk.
- **Agentic Retrieval Loop** — LangChain-powered multi-pass agent that can autonomously decide when to re-query for more context.
- **Precise Citations** — responses cite exact Act/Rule titles, Section/Rule numbers, and sub-clauses (e.g., *Section 16(2)(a), CGST Act, 2017*).
- **Built-in Evaluation Harness** — benchmark suite for retrieval accuracy, citation groundedness, and trick-query rejection.
- **Dual Vector Store Support** — Qdrant Cloud by default, with a local ChromaDB fallback for offline/dev use.
- **Serverless-Ready** — backend structured for deployment on Vercel Serverless Functions.

---

## System Architecture

The GST RAG system is built on a highly reliable, dual-path retrieval pipeline designed to maximize citation accuracy and prevent hallucinations. The flow of data from user query to grounded answer is structured as follows:

```text
               +----------------------------------------+
               |         React 18 + Vite UI             |
               +-------------------+--------------------+
                                   |
                                   | (POST /query)
                                   v
               +----------------------------------------+
               |           FastAPI Gateway              |
               +-------------------+--------------------+
                                   |
                                   v
               +----------------------------------------+
               |     LLM Query Router (Gemini)          |
               | (Routes query & designs search terms)  |
               +-------------------+--------------------+
                                   |
                  +----------------+----------------+
                  |                                 |
                  | (Semantic Search)               | (Lexical Search)
                  v                                 v
        +-------------------+             +-------------------+
        |   Qdrant Cloud    |             | Local BM25 Index  |
        |  (Vector Store)   |             |  (rank_bm25 pkl)  |
        +---------+---------+             +---------+---------+
                  |                                 |
                  | (Top Vectors)                   | (Top Keywords)
                  +----------------+----------------+
                                   |
                                   v
               +----------------------------------------+
               |     Reciprocal Rank Fusion (RRF)       |
               |       (Blends & scores candidates)     |
               +-------------------+--------------------+
                                   |
                                   v
               +----------------------------------------+
               |        Cross-Encoder Reranker          |
               |      (ms-marco-MiniLM-L-6-v2)          |
               +-------------------+--------------------+
                                   |
                                   v
               +----------------------------------------+
               |   Context Expander & Citations Match   |
               |   (Retrieves neighboring/parent text)  |
               +-------------------+--------------------+
                                   |
                                   v
               +----------------------------------------+
               |     LLM Answer Synthesizer (Gemini)    |
               |    (Grounded response generation)      |
               +-------------------+--------------------+
                                   |
                                   | (JSON Response)
                                   v
               +----------------------------------------+
               |          React 18 + Vite UI            |
               | (Renders Answer, Sources & Citations)  |
               +----------------------------------------+
```

---

## 🧰 Tech Stack

| Layer | Library / Service | Notes |
|---|---|---|
| **Frontend UI** | React 18 + Vite | Fast web interface styled with Tailwind CSS, Lucide icons, and Marked for markdown rendering. |
| **Backend API** | FastAPI + Uvicorn | High-performance async API, deployable as Vercel Serverless Functions. |
| **Vector DB (Cloud)** | Qdrant Cloud | Default cloud vector store, queried via REST and server-side Cloud Inference. |
| **Vector DB (Local)** | ChromaDB | Local persistent vector storage, kept as a historical/offline fallback layer. |
| **Keyword Search** | `rank_bm25` (BM25Okapi) | High-speed local lexical search built from raw legislation chunks. |
| **Reranker** | `sentence-transformers` | CPU-friendly cross-encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`) for joint relevance scoring. |
| **LLM Provider** | Google Gemini (default) | Grounded legal generation using `gemini-2.5-flash` via the Google GenAI SDK. |
| **Agentic Loop** | LangChain | Multi-pass agent logic for autonomous retrieval tool orchestration. |

---

## 📁 Project Structure

```
gst-rag/
├── backend/
│   ├── api/                    # FastAPI web service & Vercel serverless handlers
│   ├── config.py                # Central system configuration
│   ├── data/
│   │   ├── raw/                 # Source law PDF/JSON files
│   │   └── processed/           # Indexes, embeddings, and chunk metadata
│   ├── eval/                    # Evaluation runner & benchmark queries
│   ├── generation/              # LLM answer generation & LangChain agent
│   ├── ingestion/                # PDF extraction, chunking, & vector indexing
│   ├── requirements.txt          # Python backend dependencies
│   └── retrieval/                # Hybrid RRF, query router, & reranker
├── frontend/                     # React + Vite web UI (HTML/JSX/CSS)
├── vercel.json                   # Vercel deployment configuration
└── README.md
```

---

## ✅ Prerequisites

- **Python** 3.10+
- **Node.js** 18+ and npm
- A **Google Gemini API key** ([Google AI Studio](https://aistudio.google.com/))
- A **Qdrant Cloud** instance URL + API key (or use the local ChromaDB fallback)

---

## 🚀 Installation

### 1. Set Up the Python Backend

```bash
cd backend
python -m venv .venv

# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Set Up the React Frontend

```bash
cd frontend
npm install
```

---

## 📥 Ingestion Pipeline

### Source Files

Place raw GST law chunk files under `backend/data/processed/`:

- `normalized_act_chunks.json` — ~1,083 Act sub-sections
- `normalized_rule_chunks.json` — ~773 Rule sub-rules

### Build the Indexes

Run the ingestion pipeline to build local lexical indexes and push embeddings to the vector database:

```bash
# From the backend directory
python -m ingestion.build_index

# Force a full rebuild (wipes existing indexes and recomputes)
python -m ingestion.build_index --reset
```

The pipeline will:

1. Normalize statutory Act/Rule JSON schemas.
2. Segment text into fine-grained leaf chunks and contextual parent chunks.
3. Compute semantic embeddings and ingest leaf chunks into the Qdrant Cloud vector store.
4. Serialize and cache local BM25 indexes and fallback ChromaDB collections.

---

## ⚙️ Configuration

Configure the system centrally via `backend/config.py` or a `.env` file in the `backend/` directory.

```bash
# .env example
LLM_PROVIDER=gemini
GEMINI_MODEL=gemini-2.5-flash
GEMINI_API_KEY=your_gemini_api_key_here

VECTOR_DB_PROVIDER=qdrant
QDRANT_URL=https://your-instance.qdrant.io
QDRANT_API_KEY=your_qdrant_api_key_here
```

| Variable | Default Value | Notes |
|---|---|---|
| `LLM_PROVIDER` | `gemini` | Fixed provider for production answer generation. |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Fast, accurate model tuned for tax reasoning tasks. |
| `GEMINI_API_KEY` | *(required)* | Your Gemini API Key from Google AI Studio. |
| `VECTOR_DB_PROVIDER` | `qdrant` | `qdrant` for cloud-based search, or `chroma` for local-only fallback. |
| `QDRANT_URL` | *(required for cloud)* | Your Qdrant Cloud instance endpoint. |
| `QDRANT_API_KEY` | *(required for cloud)* | Your Qdrant Cloud security token. |

> ⚠️ **Never commit real API keys.** Keep your `.env` file out of version control (add it to `.gitignore`).

---

## ▶️ Running the Application Locally

Run the FastAPI backend and the React development server concurrently.

**Step 1 — Start the FastAPI backend**

```bash
# From the backend directory
python -m uvicorn api.main:app --reload --port 8000
```

This serves the API at `http://127.0.0.1:8000`.

**Step 2 — Start the React + Vite frontend**

```bash
# From the frontend directory
npm run dev
```

Open the app in your browser at the URL shown in the terminal (typically `http://localhost:5173`).

---

## 📊 Evaluation Benchmark

The system includes an offline validation harness to monitor answer groundedness and retrieval precision.

```bash
# From the backend directory
python -m eval.eval_runner
```

### Key Metrics

| Metric | Description |
|---|---|
| **Hit Rate @1 / @5** | Percentage of queries that retrieve the exact target statutory section within the top 1 / top 5 results. |
| **MRR @5** | Mean Reciprocal Rank — average position of the correct citation among top-5 results. |
| **Citation Groundedness** | Strict verification that 100% of generated legal claims trace back to retrieved contexts, with no hallucinations. |
| **Trick Query Rejection** | Confirms that out-of-scope or nonsensical questions are gracefully rejected rather than triggering fabricated advice. |

---

## 📖 Citation & Grounding Policy

To ensure legal precision and compliance, every generated answer must cite:

1. **Exact Act or Rule title** (e.g., *Central Goods and Services Tax Act, 2017*)
2. **Specific Section or Rule identifier** (e.g., *Section 16*)
3. **Target sub-unit markers or clauses** (e.g., *Sub-section (2)(a)*)

**Example:**

> "Under Section 16(2)(a) of the Central Goods and Services Tax Act, 2017, a registered person is entitled to claim input tax credit only if they are in possession of a valid tax invoice..."

Answers that cannot be fully grounded in retrieved source text are rejected rather than generated speculatively.

---

## 🗺️ Roadmap

- [ ] Multi-turn conversational memory with citation-aware follow-ups
- [ ] Support for State GST (SGST) and Union Territory GST (UTGST) schedules
- [ ] Notification & circular ingestion pipeline (CBIC updates)
- [ ] Fine-grained access control for multi-tenant deployments

---

## 🤝 Contributing

Contributions are welcome. Please open an issue to discuss significant changes before submitting a pull request, and ensure new features include corresponding evaluation coverage in `backend/eval/`.

---


## ⚠️ Disclaimer

This tool is intended for informational and research purposes only and does **not** constitute legal or tax advice. Always consult a qualified tax professional or refer to official CBIC/GST portal publications before making compliance decisions.
