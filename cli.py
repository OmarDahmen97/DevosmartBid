import typer
from app.extraction.pdf_extractor import extract_pdf_text
from app.extraction.docx_extractor import extract_docx_text
from app.extraction.contact_parser import extract_contact_info
from app.extraction.llm_extractor import extract_structured_sections
from app.ingestion.format_detector import detect_format
from app.schema import CVSchema
import sys
sys.stdout.reconfigure(encoding='utf-8')

app = typer.Typer()

@app.command()
def parse(file_path: str):
    text = extract_pdf_text(file_path) if file_path.endswith(".pdf") else extract_docx_text(file_path)
    data = {**extract_contact_info(text), **extract_structured_sections(text)}
    cv = CVSchema(**data)
    typer.echo(cv.model_dump_json(indent=2))

@app.command()
def extract_raw(file_path: str):
    fmt = detect_format(file_path)
    typer.echo(f"Format: {fmt}")
    text = extract_pdf_text(file_path) if fmt == "pdf" else extract_docx_text(file_path)
    typer.echo(text)

if __name__ == "__main__":
    app()