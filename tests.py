import re
from app.extraction.pdf_extractor import extract_pdf_text
from app.extraction.docx_extractor import extract_docx_text


text = extract_pdf_text("data/samples/translated_eng.pdf")  # Replace with your actual PDF file path


pattern = r"---EDUCATION-*-*\s*\n(.*?)(?=\n---)"
match = re.search(pattern, text, re.DOTALL)
education_block = match.group(1) if match else None
print(education_block)

