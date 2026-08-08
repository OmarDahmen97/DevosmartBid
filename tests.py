import asyncio
import os
from fastapi import UploadFile

# Importez votre fonction depuis votre module
# from my_module import upload_cv

def test_upload_cv_by_path(file_paths: str | list[str]):
    """
    Exécute upload_cv() localement pour un ou plusieurs chemins de fichiers.
    Peut être appelée directement dans un test unit/intégration.
    """
    if isinstance(file_paths, str):
        file_paths = [file_paths]

    async def _run():
        upload_files = []
        opened_files = []

        try:
            for path in file_paths:
                f = open(path, "rb")
                opened_files.append(f)
                filename = os.path.basename(path)
                upload_files.append(UploadFile(file=f, filename=filename))

            # Exécution de la fonction asynchrone
            return await upload_cv(files=upload_files)

        finally:
            for f in opened_files:
                f.close()

    # Lance la boucle d'événements asynchrone
    return asyncio.run(_run())


# --- EXEMPLE D'UTILISATION DANS VOTRE FICHIER DE TEST ---

if __name__ == "__main__":
    # Test avec un seul fichier
    result = test_upload_cv_by_path("C:\\cv-platform\\data\\CV-20260708T092409Z-3-001\\CV\\CV Externe\\Amine MIAOUI\\cv\\Amine MIAOUI.docx")
    print("Résultat unitaire :", result)

    # Test avec plusieurs fichiers
    results = test_upload_cv_by_path([
        "./tests/samples/cv_test1.pdf",
        "./tests/samples/cv_test2.pdf"
    ])
    print("Résultat multiple :", results)