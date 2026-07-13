import pdfplumber

def extract_pdf_text(file_path: str) -> str:
    text_parts = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

            for table in page.extract_tables():
                for row in table:
                    cells = [str(cell).strip() for cell in row if cell]
                    if cells:
                        text_parts.append(" | ".join(cells))

    return "\n\n".join(text_parts)