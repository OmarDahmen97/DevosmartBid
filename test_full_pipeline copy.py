# test_full_pipeline.py
import os
from app.ingestion.format_detector import detect_format, UnsupportedFormatError
from app.extraction.pdf_extractor import extract_pdf_text
from app.extraction.docx_extractor import extract_docx_text
from app.extraction.pptx_extractor import extract_pptx_text
from app.extraction.contact_parser import extract_contact_info
from app.extraction.llm_extractor import extract_structured_sections
from app.extraction.local_llm_extractor import extract_structured_sections_local
from app.ingestion.folder_walker import find_cv_files
from app.schema import CVSchema
from app.storage import save_cv , find_existing_by_raw_text

SAMPLES_DIR = "data/samples"
resultes=find_cv_files('data/D2C Pôle Consulting-20260708T092849Z-3-001')
for filename in os.listdir(SAMPLES_DIR):
    if filename.startswith("~$"):
        continue

    path = os.path.join(SAMPLES_DIR, filename)
    print(f"\n{'='*50}\n{filename}\n{'='*50}")

    try:
        fmt = detect_format(path)
    except UnsupportedFormatError as e:
        print(f"SKIPPED: {e}")
        continue

    try:
        text = (
            extract_pdf_text(path) if fmt == "pdf"
            else extract_docx_text(path) if fmt == "docx"
            else extract_pptx_text(path)
        )

        existing_version = find_existing_by_raw_text(text)
        if existing_version is not None:
            print(f"DUPLICATE (skipped LLM) — v{existing_version}")
            continue
        folder_name
        #Grok
        #data = {**extract_contact_info(text), **extract_structured_sections    (text,folder_name)}
        #Local LLM
        data = {**extract_contact_info(text), **extract_structured_sections_local(text,folder_name)}
        cv = CVSchema(**data)
        result = save_cv(cv, text)
        print(f"{result['status'].upper()} — {result['email']}, v{result['version']}")
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")