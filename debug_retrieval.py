from utils.rag import query_chunks, format_chunks_for_prompt

results = query_chunks("What projects are listed in this resume?", n_results=5)
chunks = format_chunks_for_prompt(results)

for i, chunk in enumerate(chunks):
    print(f"--- Chunk {i+1} (from {chunk['filename']}) ---")
    print(chunk['text'])
    print()