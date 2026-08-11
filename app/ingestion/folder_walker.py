import os

IGNORED_EXTENSIONS_PREFIX = "~$"
CV_EXTENSIONS = (".pdf", ".docx", ".pptx")


def find_cv_files(root_dir: str) -> list[tuple[str, str]]:
    
    results = []

    for dirpath, dirnames, filenames in os.walk(root_dir):
        cv_files = [
            f for f in filenames
            if not f.startswith(IGNORED_EXTENSIONS_PREFIX)
            and f.lower().endswith(CV_EXTENSIONS)
        ]

        if not cv_files:
            continue  # empty folder or no CV — silently ignored

        candidate_folder_name = os.path.basename(dirpath)

        for f in cv_files:
            results.append((os.path.join(dirpath, f), candidate_folder_name))

    return results




def find_cv_files_external(root_dir: str, cv_subfolder_name: str = "cv") -> list[str]:
    results = []

    for dirpath, dirnames, filenames in os.walk(root_dir):
        if os.path.basename(dirpath).lower() != cv_subfolder_name.lower():
            continue

        cv_files = [
            f for f in filenames
            if not f.startswith(IGNORED_EXTENSIONS_PREFIX)
            and f.lower().endswith(CV_EXTENSIONS)
        ]

        for f in cv_files:
            results.append(os.path.join(dirpath, f))

    return results