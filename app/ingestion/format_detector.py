import zipfile

class UnsupportedFormatError(Exception):
    pass

def _is_pdf(file_path: str) -> bool:
    with open(file_path, "rb") as f:
        return f.read(4) == b"%PDF"

def _is_docx(file_path: str) -> bool:
    if not zipfile.is_zipfile(file_path):
        return False
    with zipfile.ZipFile(file_path) as z:
        return "word/document.xml" in z.namelist()
    
def _is_pptx(file_path: str) -> bool:
    if not zipfile.is_zipfile(file_path):
        return False
    with zipfile.ZipFile(file_path) as z:
        return "ppt/presentation.xml" in z.namelist()    

def detect_format(file_path: str) -> str:
    if _is_pdf(file_path):
        return "pdf"
    if _is_docx(file_path):
        return "docx"
    if _is_pptx(file_path):
        return "pptx"
    
    raise UnsupportedFormatError(f"Unrecognized format: {file_path}")