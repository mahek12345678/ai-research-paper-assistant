import fitz  # PyMuPDF
def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Extracts raw text from a PDF given its bytes.

    KNOWN LIMITATION (v1): For multi-column academic layouts, PyMuPDF's
    default get_text() can interleave text in a confusing reading order
    (e.g., author affiliations bleeding into abstract text). The proper
    fix is get_text("blocks") with position-based sorting — deferred to v2.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    full_text = ""
    for page in doc:
        full_text += page.get_text()
        full_text += "\n"

    doc.close()
    return full_text

def remove_duplicate_lines(text: str, min_length: int = 40) -> str:
    """
    Removes lines that repeat frequently across the document — typically
    running headers, footers, or license boilerplate that PyMuPDF
    re-extracts on every single page.

    Only lines with length >= min_length are considered for deduplication,
    so short lines (e.g., page numbers, section headers like "3. Results")
    are left untouched even if they repeat.
    """
    lines = text.split("\n")

    # Count how many times each line appears
    line_counts = {}
    for line in lines:
        stripped = line.strip()
        if len(stripped) >= min_length:
            line_counts[stripped] = line_counts.get(stripped, 0) + 1

    # A line repeating 3+ times is almost certainly a header/footer, not real content
    repeated_lines = {line for line, count in line_counts.items() if count >= 3}

    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped in repeated_lines:
            continue
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)

import re

def sanitize_filename(filename: str) -> str:
    name = filename.rsplit(".", 1)[0]          # strip extension, e.g. "My Paper (Final).pdf" -> "My Paper (Final)"
    name = name.lower()                          # lowercase
    name = re.sub(r"[^a-z0-9]+", "_", name)      # replace anything not a-z/0-9 with underscore
    name = name.strip("_")                       # remove leading/trailing underscores
    return name