from utils.pdf_extract import sanitize_filename  # or wherever you put it

print(sanitize_filename("My Paper (Final) v2.pdf"))
print(sanitize_filename("attention_is_all_you_need.pdf"))
print(sanitize_filename("Some--Weird   Name!!.PDF"))