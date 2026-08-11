from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from utils.rag import store_chunks, paper_exists, query_chunks, format_chunks_for_prompt, generate_answer, collection, clear_collection
from pydantic import BaseModel

class AskRequest(BaseModel):
    question: str
    paper_id: str | None = None
load_dotenv()
app = FastAPI(title="AI Research Paper Assistant")
app.mount("/static", StaticFiles(directory="static"), name="static")
@app.get("/")
def serve_frontend():
    return FileResponse("static/index.html")
@app.get("/health")
def health_check():
    return {"status": "ok"}

from fastapi import UploadFile, File, HTTPException
from utils.pdf_extract import extract_text_from_pdf, remove_duplicate_lines, sanitize_filename
from utils.chunker import chunk_text
from utils.rag import store_chunks, paper_exists

@app.post("/upload")
async def upload_paper(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    paper_id = sanitize_filename(file.filename)
    file_bytes = await file.read()

    try:
        raw_text = extract_text_from_pdf(file_bytes)

        if not raw_text or not raw_text.strip():
            raise ValueError("No extractable text found in this PDF (it may be a scanned image-only file).")

        cleaned_text = remove_duplicate_lines(raw_text)
        chunks = chunk_text(cleaned_text)

        if not chunks:
            raise ValueError("Text extraction succeeded but produced no chunks.")

        clear_collection()
        store_chunks(paper_id=paper_id, filename=file.filename, chunks=chunks)

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")

    return {
        "paper_id": paper_id,
        "filename": file.filename,
        "chunks_stored": len(chunks)
    }

@app.post("/ask")
async def ask_question(request: AskRequest):
    question = request.question.strip()

    if not question:
        raise HTTPException(status_code=422, detail="Question cannot be empty.")

    try:
        query_results = query_chunks(question, n_results=5, paper_id=request.paper_id)
        chunks = format_chunks_for_prompt(query_results)

        if not chunks:
            return {
                "answer": "No relevant content found in the uploaded paper.",
                "sources": []
            }

        answer = generate_answer(question, chunks)
        sources = list(set(chunk["filename"] for chunk in chunks))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate answer: {str(e)}")

    return {
        "answer": answer,
        "sources": sources
    }
@app.get("/papers")
async def get_papers():
    try:
        all_items = collection.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch papers: {str(e)}")

    papers = {}

    for metadata in all_items["metadatas"]:
        paper_id = metadata["paper_id"]
        filename = metadata["filename"]

        if paper_id not in papers:
            papers[paper_id] = {
                "paper_id": paper_id,
                "filename": filename,
                "chunk_count": 0
            }

        papers[paper_id]["chunk_count"] += 1

    return {"papers": list(papers.values())}