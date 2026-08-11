# AI Research Paper Assistant

A RAG (Retrieval-Augmented Generation) system that lets you upload a PDF — a research paper or a resume — and ask natural-language questions about it. Every answer is grounded in and cited from the document itself; if the document doesn't contain the answer, the system says so instead of guessing.

**Live demo:** [ai-research-paper-assistant-production.up.railway.app](https://ai-research-paper-assistant-production.up.railway.app/)
**Repo:** [github.com/mahek12345678/ai-research-paper-assistant](https://github.com/mahek12345678/ai-research-paper-assistant)

---

## Why this project

Most "chat with your PDF" demos hallucinate confidently when the answer isn't in the document. This project is built around one constraint: **answers must be traceable to the source text, and the system must be able to say "I don't know" when the retrieved context doesn't support an answer.** That constraint shaped most of the harder engineering decisions below — chunking strategy, duplicate detection, and the embedding model swap that got this deployed on a free-tier host.

---

## Architecture

```
                    ┌─────────────┐
   PDF Upload  ───► │  PyMuPDF     │  Extract text (page-aware)
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  Chunking    │  Split into overlapping chunks
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │ ONNXMiniLM   │  ChromaDB's built-in embedding fn
                    │  L6_V2       │  (all-MiniLM-L6-v2, ONNX runtime)
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  ChromaDB    │  Persistent vector store
                    └──────┬──────┘
                           │
Question  ───────────────►│
                    ┌──────▼──────┐
                    │  Retrieval   │  Top-k relevant chunks
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  Groq API    │  llama-3.3-70b-versatile
                    │  (grounded   │  generates cited answer
                    │  generation) │  or "not enough info"
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   FastAPI    │  /upload, /ask, /papers
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │ Vanilla JS   │  Frontend
                    │  Frontend    │
                    └─────────────┘
```

---

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| API framework | FastAPI | Async support, automatic OpenAPI docs, lightweight |
| PDF extraction | PyMuPDF (fitz) | Fast, reliable text extraction, preserves page structure for citations |
| Vector store | ChromaDB (persistent) | Simple embedded vector DB, no separate service to host |
| Embeddings | ChromaDB's built-in `ONNXMiniLM_L6_V2` | Same underlying model as `sentence-transformers`' `all-MiniLM-L6-v2`, but runs on the ONNX runtime instead of PyTorch — no CUDA/torch download, dramatically lower memory footprint. This was a deliberate swap made mid-project (see [Engineering Decisions](#engineering-decisions-worth-discussing) below) after `sentence-transformers` blew past free-tier hosting memory limits. |
| LLM | Groq API — `llama-3.3-70b-versatile` | Fast inference, generous free tier, strong enough for grounded Q&A with citation instructions |
| Frontend | Vanilla JS | No build step, keeps the deployed footprint minimal |
| Deployment | Railway | Render free tier couldn't fit the original torch-based stack in 512Mi; Railway hosts the ONNX-based version live |

**Note on the embedding switch:** the model itself didn't change — it's `all-MiniLM-L6-v2` either way. What changed is the runtime. `sentence-transformers` pulls in PyTorch (and tries to pull CUDA dependencies even for CPU-only inference), which alone exceeded the memory ceiling on both Render's and Railway's free tiers before the app code even started. ChromaDB's built-in ONNX embedding function loads the same model through `onnxruntime`, which has a much smaller dependency footprint and no CUDA download.

---

## Features

- Upload a PDF (research paper or resume) and index it into a persistent vector store
- Ask natural-language questions and get answers grounded in retrieved chunks
- Citations point back to the specific parts of the document that support each answer
- Honest fallback: when retrieved context doesn't support an answer, the system says so instead of hallucinating
- List all previously uploaded papers via `GET /papers`

---

## API Endpoints

### `POST /upload`
Upload and index a PDF.

**Request:** `multipart/form-data`, field `file` (PDF)

**Response:**
```json
{
  "paper_id": "string",
  "filename": "string",
  "num_chunks": 0,
  "status": "indexed"
}
```

### `POST /ask`
Ask a question about a previously uploaded document.

**Request:**
```json
{
  "paper_id": "string",
  "question": "string"
}
```

**Response:**
```json
{
  "answer": "string",
  "citations": ["chunk or page references"],
  "grounded": true
}
```

### `GET /papers`
List all indexed papers.

**Response:**
```json
{
  "papers": [
    { "paper_id": "string", "filename": "string", "uploaded_at": "timestamp" }
  ]
}
```

---

## Setup instructions

```bash
# Clone the repo
git clone https://github.com/mahek12345678/ai-research-paper-assistant.git
cd ai-research-paper-assistant

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Add your GROQ_API_KEY to .env

# Run the server
uvicorn main:app --reload

# Open the frontend
# Navigate to http://localhost:8000
```

---

## Verified tests

Tested end-to-end against both a resume and a real research paper (`paper4.pdf`, a brain tumor detection / BTDN model paper).

| # | Question type | Document | Result |
|---|---|---|---|
| 1 | Factual lookup (e.g. model architecture) | paper4.pdf | ✅ Grounded, correctly cited |
| 2 | Factual lookup (e.g. dataset used) | paper4.pdf | ✅ Grounded, correctly cited |
| 3 | Synthesis across sections | paper4.pdf | ✅ Grounded, correctly cited |
| 4 | Out-of-scope question | paper4.pdf | ✅ Correctly returned "not enough info" |
| 5 | Factual lookup (e.g. skills/experience) | resume | ✅ Grounded, correctly cited |

Also re-verified live post-deployment: fresh random paper upload + `/ask`, and resume upload + `/ask`, both returned grounded, correctly-cited answers.

> **Open item:** the 4 `paper4.pdf` questions above are being re-run against the post-ONNX-switch embeddings specifically, since one early answer after the switch looked slightly less precise than before. Not yet confirmed whether this is a real regression or a one-off — table above will be updated once confirmed.

---

## Rough metrics

- Max PDF size tested: [ADD — e.g. "X MB / Y pages"]
- Average `/ask` response time: [ADD — e.g. "X.Xs, including LLM generation"]
- Average `/upload` (extract + chunk + embed) time: [ADD if measured]

---

## Known limitations (v1, by design)

These are deliberate scope decisions for v1, not oversights:

1. **Single-document context per query** — questions are answered against one uploaded paper at a time; no cross-document synthesis.
2. **Fixed-size chunking** — chunks are split by size with overlap rather than by semantic section boundaries, which occasionally splits a coherent idea across two chunks (see bug #2 below).
3. **No OCR support** — scanned/image-only PDFs without a text layer won't extract meaningfully; text-based PDFs only.
4. **No authentication** — uploads and queries are unauthenticated in v1; not intended for multi-tenant production use as-is.
5. **No conversation memory** — each question is answered independently; there's no multi-turn follow-up context yet.
6. **CPU-only embeddings** — ONNX runtime here runs on CPU, which is the right trade-off for free-tier memory limits but caps embedding throughput on very large documents.
7. **Filename-based de-dup only at first, content-hash-based now** — an early version used filename matching for duplicate uploads, which silently caused a retrieval bug (see below); fixed to content-hash-based detection, but the incident is left in as a known v1 lesson.

---

## Engineering decisions worth discussing

Three real bugs found and root-caused during development:

**1. Silent retrieval degradation from filename-based duplicate detection.**
The original de-dup logic checked for existing documents by filename, not content. Re-uploading a modified version of a file with the same name was treated as a duplicate and skipped — so the vector store kept serving stale, outdated chunks with no error or warning. Fixed by switching to content-hash-based duplicate detection, so identical filenames with different content are correctly re-indexed.

**2. Fixed-size chunking splitting a coherent section.**
With naive fixed-size chunking, a project description in the resume was split across two chunks such that neither chunk on its own carried enough signal to rank in the top-5 retrieved results for a directly relevant question — the project was effectively invisible to the retriever even though the text was present in the store. Diagnosed by manually inspecting which chunks were retrieved for a known-answerable question and finding the answer split across a chunk boundary. Informed the overlap size chosen for chunking.

**3. Out-of-memory deploy failure from a heavyweight embedding model.**
Deploying with `sentence-transformers` (which pulls in PyTorch) exceeded Render's 512Mi free-tier memory limit before the app finished starting; the same stack also stalled 10+ minutes on Railway while downloading torch/CUDA dependencies. Root-caused to the embedding model's runtime dependencies rather than the model itself, and fixed by switching to ChromaDB's built-in `ONNXMiniLM_L6_V2` — same `all-MiniLM-L6-v2` model, ONNX runtime instead of PyTorch, no CUDA download, small enough memory footprint to deploy on free-tier hosting. This is the trade-off between using the "standard" ML tooling and the tooling that actually fits your deployment constraints.

---

## Future improvements

- Multi-document / cross-paper querying
- OCR fallback for scanned PDFs
- Conversation memory for multi-turn follow-up questions
- Semantic (section-aware) chunking instead of fixed-size chunking
- Basic auth for multi-user deployments

---

## License

MIT License — see [LICENSE](LICENSE) for details.
