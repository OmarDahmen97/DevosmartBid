import os
import json
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

# Dossier temporaire pour ne plus jamais attendre l'API pendant tes tests
CACHE_DIR = "data/cache_tests"
os.makedirs(CACHE_DIR, exist_ok=True)

# =========================================================
# 1. FONCTION DE NETTOYAGE (DÉJÀ CORRIGÉE ET OPTIMISÉE)
# =========================================================
def adapt_data_to_schema(data: dict) -> dict:
    """
    Adapte les données extraites par le LLM pour qu'elles correspondent 
    strictement aux attentes du schéma Pydantic d'origine.
    """
    # 1. Convertir UNIQUEMENT expertise_areas et functional_skills en objets d'expertise
    for field in ["expertise_areas", "functional_skills"]:
        if field in data and isinstance(data[field], list):
            adapted_list = []
            for item in data[field]:
                if isinstance(item, str):
                    adapted_list.append({"name": item})
                elif isinstance(item, dict):
                    if not item.get("name"):
                        item["name"] = "Non spécifié"
                    adapted_list.append(item)
                else:
                    adapted_list.append(item)
            data[field] = adapted_list

    # 2. Nettoyer les projets (et réparer le format de leurs technologies)
    if "projects" in data and isinstance(data["projects"], list):
        for project in data["projects"]:
            if isinstance(project, dict):
                if project.get("name") is None:
                    project["name"] = "Projet non spécifié"
                
                # SÉCURITÉ CRITIQUE : Si technologies est une string ou None, on le transforme en liste vide []
                if "technologies" in project:
                    techs = project["technologies"]
                    if isinstance(techs, list):
                        project["technologies"] = [
                            t.get("name") if isinstance(t, dict) else str(t)
                            for t in techs if t is not None
                        ]
                    else:
                        # Si c'est une string vide "" ou autre chose, on met une liste vide []
                        project["technologies"] = []

    # 3. Nettoyer les expériences (notamment les technologies polluées)
    if "experience" in data and isinstance(data["experience"], list):
        for exp in data["experience"]:
            if isinstance(exp, dict):
                # SÉCURITÉ CRITIQUE : Si technologies est une string ou None, on le transforme en liste vide []
                if "technologies" in exp:
                    techs = exp["technologies"]
                    if isinstance(techs, list):
                        cleaned_techs = []
                        for t in techs:
                            if isinstance(t, dict):
                                cleaned_techs.append(t.get("name") or "Inconnu")
                            elif t is not None:
                                cleaned_techs.append(str(t))
                        exp["technologies"] = cleaned_techs
                    else:
                        exp["technologies"] = []

    # 4. Nettoyer les certifications
    if "certifications" in data and isinstance(data["certifications"], list):
        for cert in data["certifications"]:
            if isinstance(cert, dict) and cert.get("name") is None:
                cert["name"] = "Certification"

    # 5. Nettoyer les langues
    if "languages" in data and isinstance(data["languages"], list):
        for lang in data["languages"]:
            if isinstance(lang, dict) and lang.get("language") is None:
                lang["language"] = "Langue non spécifiée"

    return data


# =========================================================
# 2. PIPELINE PRINCIPAL AVEC SYSTÈME DE CACHE
# =========================================================

SAMPLES_DIR = "data/samples"
results = [(path, "") for path in find_cv_files_external('data/CV-20260708T092409Z-3-001/CV/CV Externe')]

i = 0
for path, folder_name in results:
    if i >= 1:
        break
    i += 1
    
    filename = os.path.basename(path)
    if filename.startswith("~$"):
        continue

    print(f"\n{'='*50}\n{filename}\n{'='*50}")

    # Fichier de cache unique pour ce CV
    cache_filepath = os.path.join(CACHE_DIR, f"{filename}_llm_raw.json")

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

        # --- SYSTÈME DE CACHE POUR ÉVITER LES 15 MIN D'ATTENTE ---
        if os.path.exists(cache_filepath):
            print(f"-> [CACHE] Chargement direct des données LLM depuis : {cache_filepath}")
            with open(cache_filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            print("-> [LLM] Données non trouvées en local. Appel API en cours (veuillez patienter)...")
            data = {**extract_contact_info(text), **extract_structured_sections(text, folder_name)}
            
            # Sauvegarde de sécurité dans le cache
            with open(cache_filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"-> [CACHE] Extraction sauvegardée en local sous : {cache_filepath}")
        # ---------------------------------------------------------
        
        # Adaptation automatique des données pour Pydantic
        data = adapt_data_to_schema(data)
        
        # Validation email / nom
        if not validate_email_matches_name(data.get("email"), data.get("name", "")):
            data["email"] = None
            
        # Validation Pydantic & Sauvegarde en BDD
        cv = CVSchema(**data)
        result = save_cv(cv, text)
        print(f"{result['status'].upper()} — email: {result['email']} — name:  {result['name']}, v{result['version']}")
        
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")