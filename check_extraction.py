from utils.pdf_extract import extract_text_from_pdf

with open(r"C:\Users\lenovo\Downloads\paper4.pdf", "rb") as f:
    text = extract_text_from_pdf(f.read())

print("Contains 'abstract':", "abstract" in text.lower())
print("Contains 'introduction':", "introduction" in text.lower())
print("---FIRST 1000 CHARS---")
print(text[:1000])