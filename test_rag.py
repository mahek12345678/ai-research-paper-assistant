from utils.rag import store_chunks, query_chunks, format_chunks_for_prompt, generate_answer, paper_exists
print(paper_exists("test.pdf"))       # should be True, since you already stored chunks with this filename
print(paper_exists("nonexistent.pdf"))  # should be False