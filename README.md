pyh# GST RAG – Retrieval-Augmented Generation for Indian GST Law

A fully local, zero-cost RAG system for querying Indian Goods and Services Tax
legislation (Acts + Rules) with precise legal citations.

---

## Tech Stack

| Layer | Library |
|---|---|
| Embeddings | `sentence-transformers` (BAAI/bge-small-en-v1.5, CPU) |
| Vector Store | ChromaDB (local persistent) |
| Keyword Search | `rank_bm25` (BM25Okapi, pure Python) |
| LLM | Gemini free-tier (default) or local Ollama (switchable) |
| API | FastAPI + Uvicorn |
| Frontend | Gradio |

---

## Project Structure

```
gst-rag/
├── data/
│   ├── raw/                # place source JSON files here (not in version control)
│   └── processed/          # auto-generated indexes and chunk files
├── ingestion/
│   ├── loader.py           # load & validate raw JSON
│   ├── normalizer.py       # unified schema across acts/rules
│   ├── chunker.py          # leaf + parent chunk construction
│   ├── embedder.py         # sentence-transformer embeddings w/ caching
│   ├── build_index.py      # full pipeline orchestrator
│   └── verify.py           # Phase 1 self-check
├── retrieval/              # (Phase 2)
├── generation/             # (Phase 3)
├── api/                    # (Phase 4)
├── frontend/               # (Phase 5)
├── eval/                   # (Phase 6)
├── config.py               # all settings in one place
├── requirements.txt
└── README.md
```

---

## Prerequisites

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

---

## Phase 1: Ingestion

### Source files

Place the two raw JSON files in `data/processed/` (they are already there if
provided by the user):

| File | Records |
|---|---|
| `data/processed/normalized_act_chunks.json` | ~1083 act sub-sections |
| `data/processed/normalized_rule_chunks.json` | ~773 rule sub-rules |

> The pipeline also looks for files in `data/raw/` via `config.py`.  Update
> `ACT_CHUNKS_FILE` / `RULE_CHUNKS_FILE` in `config.py` if your paths differ.

### Run the ingestion pipeline

```bash
# Normal run (uses embedding cache on subsequent runs)
python -m ingestion.build_index

# Force full rebuild (wipes ChromaDB collection + recomputes embeddings)
python -m ingestion.build_index --reset
```

**What it does:**

1. **Load** – reads both JSON files, validates required fields, skips malformed records.
2. **Normalise** – maps act/rule schemas to a unified schema with deterministic IDs.
3. **Chunk** – produces `leaf_chunks.json` (one per sub-section/sub-rule) and
   `parent_chunks.json` (full sections), plus `leaf_to_parent_map.json`.
4. **Embed** – encodes all leaf texts with BGE-small (SHA-256 cache check avoids
   re-embedding on unchanged inputs).
5. **ChromaDB** – upserts leaf chunks + embeddings into a local persistent
   collection `gst_leaf_chunks`.
6. **BM25** – builds a `BM25Okapi` index, pickled to `bm25_index.pkl` with an
   ordered ID list `bm25_ids.json`.

### Artefacts produced

| Path | Description |
|---|---|
| `data/processed/leaf_chunks.json` | ~1856 leaf chunk records |
| `data/processed/parent_chunks.json` | ~N parent (full-section) records |
| `data/processed/leaf_to_parent_map.json` | leaf_id → parent_id |
| `data/processed/embeddings_cache.npz` | numpy float32 embeddings |
| `data/processed/embeddings_source_hash.txt` | hash for cache validity |
| `data/processed/chroma_db/` | ChromaDB persistent store |
| `data/processed/bm25_index.pkl` | pickled BM25Okapi object |
| `data/processed/bm25_ids.json` | ordered list of chunk IDs |

### Verify

```bash
python -m ingestion.verify
```

Prints chunk counts, skip report, embedding dimensions, ChromaDB collection
size, BM25 corpus stats, and 3 sample queries against both indexes.

---

## Phase 3: Generation & API

### LLM Provider Configuration

The generation layer is provider-agnostic and configured via `config.py` or environment variables:

| Provider | Config Value | Required Environment Variable | Cost / Notes |
|---|---|---|---|
| **Gemini** (Default) | `gemini` | `GEMINI_API_KEY` | Free-tier API key from Google AI Studio |
| **Claude** | `claude` | `ANTHROPIC_API_KEY` | Anthropic API key |
| **Ollama** | `ollama` | None (`OLLAMA_BASE_URL` default `http://localhost:11434`) | Fully local, zero API keys |
| **Mock** | `mock` | None | Offline fallback for CI / testing |

**Setting Environment Variables:**
```bash
# Windows PowerShell:
$env:LLM_PROVIDER="gemini"
$env:GEMINI_API_KEY="your_free_gemini_api_key_here"

# Linux / macOS:
export LLM_PROVIDER="gemini"
export GEMINI_API_KEY="your_free_gemini_api_key_here"
```

### Running the System (API + Frontend)

#### Step 1: Start the FastAPI Backend
```bash
python -m uvicorn api.main:app --reload --port 8000
```

#### Step 2: Start the Streamlit Frontend UI (in a separate terminal)
```bash
streamlit run frontend/app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser to interact with the visual chat UI!

---

## Phase 5: Evaluation Harness

The evaluation module ([`eval/eval_runner.py`](eval/eval_runner.py)) measures retrieval quality, citation accuracy, MRR, and hallucination prevention against benchmark questions ([`eval/test_queries.json`](eval/test_queries.json)).

### Run the Evaluation Benchmark

```bash
python -m eval.eval_runner
```

### Metrics Calculated

- **Hit Rate @ 1**: Percentage of valid queries where the expected section/rule lands at rank 1.
- **Hit Rate @ 5**: Percentage of valid queries where the expected section/rule appears in top-5 results.
- **MRR @ 5 (Mean Reciprocal Rank)**: Average reciprocal rank $\frac{1}{\text{rank}}$ of the first correct citation.
- **Trick Query Rejection Rate**: Accuracy on out-of-corpus queries (confirms the system outputs *"not found"* rather than hallucinating).
- **Citation Groundedness Rate**: Verifies that 100% of generated citations exist in the retrieved context.

### Adding New Test Queries

Edit [`eval/test_queries.json`](eval/test_queries.json) and add a test case:

```json
{
  "id": "q21",
  "category": "exact_section",
  "query": "What is the penalty for failure to furnish return under Section 47?",
  "expected_law": "Central Goods and Services Tax Act, 2017",
  "expected_unit": "47",
  "expected_marker": null,
  "should_find": true
}
```


The Streamlit UI ([`frontend/app.py`](frontend/app.py)) provides a legal chat interface:
- **Chat Interface**: Interactive query input with conversational memory.
- **Collapsible Sources**: Every assistant response includes a toggleable *"Legal Sources & Citations"* section displaying the exact Act/Rule, section/rule number, sub-unit marker, and text snippet.
- **Sidebar Controls**:
  - Real-time API connection & index status (`/health`)
  - Configurable `top_k` slider (1 to 15 context chunks)
  - LLM Provider selector (`gemini`, `claude`, `ollama`, `mock`)

### API Endpoints

#### 1. `POST /query`
Request:
```json
{
  "question": "What does Section 16 of CGST Act say about ITC eligibility?",
  "top_k": 5,
  "provider": "gemini"
}
```

Response:
```json
{
  "question": "What does Section 16 of CGST Act say about ITC eligibility?",
  "answer": "Every registered person shall be entitled to take credit of input tax charged on any supply of goods or services... [Central Goods and Services Tax Act, 2017, Section 16, (1)].",
  "citations": [
    {
      "law_title": "Central Goods and Services Tax Act, 2017",
      "unit_number": "Section 16.",
      "sub_unit_marker": "(1)",
      "snippet": "Short title and commencement..."
    }
  ],
  "retrieved_chunk_ids": ["central-goods-and-services-tax-act-2017-section-16-1-a1b2c3d4"]
}
```

#### 2. `GET /health`
Returns system index counts, ChromaDB status, and active embedding/LLM configuration.

#### 3. `POST /reindex`
Request: `{ "confirm": true }` to trigger a full index wipe and rebuild.

---

## Phase 3 Verification

```bash
python -m generation.verify
```
Runs end-to-end API test suite and outputs full JSON responses for sample queries.


---

## Data Sources

| Document | Type |
|---|---|
| Central Goods and Services Tax Act, 2017 | Act |
| Integrated Goods and Services Tax Act, 2017 | Act |
| Union Territory Goods and Services Tax Act, 2017 | Act |
| GST (Compensation to States) Act, 2017 | Act |
| Central / Integrated GST (Extension to J&K) Acts | Act |
| Constitution (101st Amendment) Act, 2016 | Act |
| Central Goods and Services Tax Rules, 2017 | Rule |
| UT-specific rule sets (Dadra & NH, Daman & Diu, Lakshadweep, Chandigarh) | Rule |
| GST Compensation Cess Rules | Rule |
| GST Settlement of Funds Rules | Rule |

---

## Citation Policy

Every generated answer **must** cite:
- Exact Act / Rule name
- Section / Rule number
- Sub-section / Sub-rule marker (e.g. `(2)(a)`)

Example: *"Section 16(2)(a) of the Central Goods and Services Tax Act, 2017 provides…"*
