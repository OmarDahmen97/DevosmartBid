
import os
from app.ingestion.format_detector import detect_format, UnsupportedFormatError
from app.extraction.pdf_extractor import extract_pdf_text
from app.extraction.docx_extractor import extract_docx_text
from app.extraction.pptx_extractor import extract_pptx_text
from app.extraction.contact_parser import extract_contact_info, validate_email_matches_name
from app.extraction.llm_extractor import extract_structured_sections
from app.extraction.local_llm_extractor import extract_structured_sections_local
from app.ingestion.folder_walker import find_cv_files, find_cv_files_external
from app.schema import CVSchema
from app.storage import save_cv , find_existing_by_raw_text


SAMPLES_DIR = "data/samples"
# --- D2C ---
#results = find_cv_files('data/D2C Pôle Consulting-20260708T092849Z-3-001')

# --- CV Externe (TECH-6, générique) ---
results = [(path, "") for path in find_cv_files_external('data/CV-20260708T092409Z-3-001/CV/CV Externe')]
i=0
for path, folder_name in results:
    """if i>=1:
        break
    i += 1"""
    filename = os.path.basename(path)
    if filename.startswith("~$"):
        continue

    #path = os.path.join(SAMPLES_DIR, filename)
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
        data = {**extract_contact_info(text), **extract_structured_sections(text,folder_name)}
        #Local LLM
        #data = {**extract_contact_info(text), **extract_structured_sections_local(text,folder_name)}
        if not validate_email_matches_name(data.get("email"), data.get("name", "")):
            data["email"] = None
        cv = CVSchema(**data)
        result = save_cv(cv, text)
        print(f"{result['status'].upper()} — email: {result['email']} — name:  {result['name']}, v{result['version']}")
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")