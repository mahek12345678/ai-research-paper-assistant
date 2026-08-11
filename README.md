# AI Research Paper Assistant

A Retrieval-Augmented Generation (RAG) system that lets you upload a research paper (or any PDF) and ask natural-language questions about it — with every answer grounded in and cited from the actual document, not the model's memory.

**Live Demo:** _[add link after deployment]_

---

## Why This Project

Most "chat with your PDF" demos are thin wrappers around an LLM with no real retrieval discipline — they hallucinate, mix content across documents, and silently degrade as more files get uploaded. This project was built to do the opposite: a correctly-scoped, honestly-documented v1 where every design decision (and every bug found along the way) is deliberate and explainable.

---

## Tech Stack

| Layer | Choice | Why |
|---|---|---|
| API | FastAPI | Async-first, automatic OpenAPI docs, minimal boilerplate for a focused backend |
| PDF Extraction | PyMuPDF (fitz) | Fast, reliable text extraction with page-level metadata for citations |
| Embeddings | sentence-transformers (`all-MiniLM-L6-v2`) | Lightweight, runs locally with no API cost, strong enough semantic quality for document-level retrieval |
| Vector Store | ChromaDB (persistent) | Zero-config, embedded, no separate DB server to manage — the right trade-off for a single-node v1 (vs. pgvector/FAISS, which pay off at higher scale) |
| LLM | Groq API (`llama-3.3-70b-versatile`) | Very low latency inference, keeps question-answering fast without sacrificing answer quality |
| Frontend | Vanilla JS | No framework overhead for a small, focused UI — upload, ask, view answers |

---

## Features

- **Upload & index PDFs** — text extraction, chunking, and embedding on upload
- **Ask natural-language questions** — answers are generated only from retrieved chunks, with source page citations
- **Multi-paper support** — list all uploaded papers, scoped Q&A per paper
- **Grounded answers, not hallucinations** — the system says "not in this document" when it genuinely doesn't know

### Verified Test Cases

| Test | Result |
|---|---|
| Factual retrieval (single fact) | ✅ Correct, cited |
| List / multi-item retrieval (e.g. "list all skills") | ✅ Complete, correctly categorized, no omissions |
| Reasoning over context (e.g. cross-referencing two sections) | ✅ Model reasoned across retrieved chunks instead of just quoting them, and flagged its own uncertainty rather than guessing |
| Out-of-context refusal | ✅ Correctly declines when the answer isn't in the document |
| Single-paper scoping | ✅ Answers only draw from the currently active paper |
| Upload / duplicate handling | ✅ Verified end-to-end |
| Real research paper (non-resume test document) | ✅ Correct problem statement, methodology, dataset sizes, and results (e.g. exact accuracy figures) pulled with citations; model honestly noted when fine-grained architecture detail wasn't present in retrieved chunks |

---

## Architecture

```
                    ┌──────────────┐
   PDF Upload  ───▶ │ PyMuPDF      │  extract text + page metadata
                    └──────┬───────┘
                           ▼
                    ┌──────────────┐
                    │ Chunker      │  fixed-size chunks w/ overlap
                    └──────┬───────┘
                           ▼
                    ┌──────────────┐
                    │ MiniLM       │  embed chunks
                    │ (sentence-   │
                    │ transformers)│
                    └──────┬───────┘
                           ▼
                    ┌──────────────┐
                    │ ChromaDB     │  persistent vector store
                    └──────┬───────┘
                           │  top-k retrieval on question
                           ▼
   User Question ─▶ ┌──────────────┐
                    │ Groq LLM     │  answer grounded in retrieved
                    │ (Llama 3.3)  │  chunks only, with citations
                    └──────┬───────┘
                           ▼
                       Answer + Sources
```

**Chunking strategy:** Fixed-size chunking (with overlap) was chosen over layout-aware or semantic chunking for v1 — simpler to implement and reason about, and sufficient for well-structured documents like research papers and resumes. The known trade-off (see Limitations) is that it can occasionally split a semantically coherent unit (e.g. a bullet list of related skills) across two chunks, which can affect retrieval if the split-off half isn't in the top-k.

**Why ChromaDB over pgvector/FAISS:** For a single-node v1 with a handful of documents, an embedded persistent vector store removes an entire piece of infrastructure (no separate DB to provision, connect to, or manage). pgvector or FAISS would make sense at a scale where either multi-node search or heavier metadata filtering is needed — a deliberate deferral, not an oversight.

---

## Setup Instructions

```bash
# clone and enter the project
git clone <repo-url>
cd ai-research-paper-assistant

# create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# install dependencies
pip install -r requirements.txt

# set environment variables
# create a .env file with:
# GROQ_API_KEY=your_key_here

# run the server
uvicorn main:app --reload
```

Then open `http://127.0.0.1:8000` in your browser.

---

## API Endpoints

### `POST /upload`
Uploads and indexes a PDF.

**Request:** `multipart/form-data` with a `file` field (PDF)

**Response:**
```json
{
  "paper_id": "paper4",
  "filename": "paper4.pdf",
  "status": "uploaded",
  "chunks_indexed": 42
}
```

### `POST /ask`
Asks a question about the currently active paper.

**Request:**
```json
{
  "paper_id": "paper4",
  "question": "What datasets or methodology were used in this research?"
}
```

**Response:**
```json
{
  "answer": "The research used three datasets: D-I, D-II, and D-III...",
  "sources": ["paper4.pdf - page 6", "paper4.pdf - page 7"]
}
```

### `GET /papers`
Lists all uploaded papers with their chunk counts.

**Response:**
```json
[
  { "paper_id": "paper4", "filename": "paper4.pdf", "chunk_count": 42 }
]
```

---

## Known Limitations / v2 Roadmap

These are documented, deliberate v1 scope decisions — not oversights.

1. **Single-paper scoping** — only one paper is "active" at a time; multi-paper cross-referencing isn't supported yet. v2: allow querying across multiple uploaded papers at once.
2. **Filename-based duplicate detection** — duplicates are detected by filename, not content hash, so the same file uploaded under two different names gets indexed twice, crowding out top-k retrieval. v2: content-hash-based deduplication.
3. **Fixed-size chunking** — chunks are split by character/token count with overlap, not by semantic or layout boundaries, so a chunk can occasionally cut a coherent section in two. v2: layout-aware or semantic chunking.
4. **No layout-awareness in PDF extraction** — tables, multi-column layouts, and figures are extracted as flat text, which can degrade extraction quality on visually complex papers. v2: layout-aware extraction (e.g. via a vision-capable model or structured PDF parser).
5. **No authentication** — the API is open, suitable for a local/demo deployment only. v2: basic auth or API keys before any multi-user deployment.
6. **Synchronous processing** — PDF upload and indexing block the request; large PDFs will be slow to upload. v2: background task queue (e.g. Celery + Redis) for async processing.
7. **No automated test suite** — testing so far has been manual, end-to-end verification (see table above). v2: pytest coverage for the extraction, chunking, and retrieval pipeline.

---

## Engineering Decisions Worth Discussing

Real bugs found and root-caused during development — kept here as concrete examples of debugging process, not just a features list.

- **Silent retrieval-degradation bug:** Uploading the same document twice under two different filenames wasn't caught by filename-based duplicate detection, silently doubling that document's chunks in the vector store and crowding out other documents from top-k retrieval. Root-caused by inspecting retrieval results directly, not just the final answer.
- **Retrieval crowding from duplicate content:** Directly related to the above — demonstrates why duplicate detection strategy (filename vs. content hash) materially affects answer quality, not just storage efficiency.
- **Fixed-size chunking boundary loss:** Found a concrete case where a chunk boundary split a list of related items, causing one item (a specific project) to be missed from top-5 retrieval despite being clearly present in the source document. Verified by manually inspecting which chunks were retrieved vs. which chunk actually contained the missing content.

---

## Metrics

_To be filled in after deployment:_
- Max PDF size tested:
- Average `/ask` response time:
- Average `/upload` processing time:
