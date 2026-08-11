from chromadb.utils import embedding_functions
import chromadb
from chromadb import PersistentClient
from groq import Groq
import os
import re

# --- Embeddings ---
embedding_model = embedding_functions.ONNXMiniLM_L6_V2()
def embed_texts(texts: list[str]):
    return embedding_model(texts)
# --- ChromaDB setup ---
chroma_client = PersistentClient(path="chroma_db")
collection = chroma_client.get_or_create_collection("research_papers")

# --- Groq client (created once, reused across requests) ---
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# --- format_chunks_for_prompt (exact, verified this session) ---
def format_chunks_for_prompt(query_results):
    documents = query_results['documents'][0]
    metadatas = query_results['metadatas'][0]

    formatted = []
    for text, meta in zip(documents, metadatas):
        formatted.append({
            "text": text,
            "filename": meta["filename"]
        })

    return formatted

# --- build_prompt (exact, verified this session) ---
def build_prompt(question: str, chunks: list[dict]) -> str:
    context = "\n\n".join(
        [f"[Source: {c['filename']}]\n{c['text']}" for c in chunks]
    )

    prompt = f"""You are a research assistant answering questions based ONLY on the provided excerpts from academic papers.

Context excerpts:
{context}

Question: {question}

Instructions:
- Answer using ONLY information from the excerpts above.
- If the excerpts don't contain enough information to answer, say "I don't have enough information in the provided documents to answer this question."
- Do not use any outside knowledge.
- Mention which source(s) (by filename) support your answer.

Answer:"""

    return prompt

# --- generate_answer (exact, verified this session) ---
def generate_answer(question: str, chunks: list[dict]) -> str:
    prompt = build_prompt(question, chunks)

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        max_tokens=1024,
    )

    return response.choices[0].message.content

# --- paper_exists (exact, verified this session) ---
def paper_exists(filename: str) -> bool:
    results = collection.get(where={"filename": filename})
    return len(results["ids"]) > 0
def clear_collection():
    all_items = collection.get()
    if all_items["ids"]:
        collection.delete(ids=all_items["ids"])

def store_chunks(paper_id: str, filename: str, chunks: list[str]):
    ids = [f"{paper_id}_chunk_{i}" for i in range(len(chunks))]
    embeddings = embed_texts(chunks)
    metadatas = [{"paper_id": paper_id, "filename": filename} for _ in chunks]

    collection.add(
        ids=ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=metadatas
    )

def query_chunks(question: str, n_results: int = 4, paper_id: str = None):
    query_embedding = embed_texts([question])

    if paper_id:
        results = collection.query(
            query_embeddings=query_embedding,
            n_results=n_results,
            where={"paper_id": paper_id}
        )
    else:
        results = collection.query(
            query_embeddings=query_embedding,
            n_results=n_results
        )
    return results