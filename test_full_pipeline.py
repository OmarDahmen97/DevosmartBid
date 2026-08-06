#test_full_pipeline.py
import os
from app.ingestion.format_detector import detect_format, UnsupportedFormatError
from app.extraction.pdf_extractor import extract_pdf_text
from app.extraction.docx_extractor import extract_docx_text
from app.extraction.pptx_extractor import extract_pptx_text
from app.extraction.contact_parser import extract_contact_info, validate_email_matches_name
#choice between Gemini3.1-flash-lite and Groq llama-3.3-70b-versatile 
from app.extraction.llm_extractor import extract_structured_sections ; print("Groq")
#from app.extraction.llm_extractor_gemini import extract_structured_sections ; print("Gemini")
from app.extraction.local_llm_extractor import extract_structured_sections_local
from app.ingestion.folder_walker import find_cv_files, find_cv_files_external
from app.schema import CVSchema
from app.storage import save_cv , find_existing_by_raw_text
from deep_translator import GoogleTranslator
from langdetect import detect
import deepl

# --- AJOUT : merge/dédup ---
from pymongo import MongoClient
from app.merging.experience_similarity import build_merged_candidate_cv, DEFAULT_SIMILARITY_THRESHOLD

deepl_key = os.getenv("DEEPL_API_KEY")

# --- AJOUT : connexions Mongo pour le merge ---
mongo_uri = os.getenv("MONGO_URI")
_mongo_client = MongoClient(mongo_uri)
_db = _mongo_client["cv_platform"]
_candidates_col = _db["candidatesV2"]
_merged_candidates_col = _db["merged_candidates"]


# --- AJOUT : fonction de sync merge ---
def sync_merged_candidate(candidate_id: str, threshold: float = DEFAULT_SIMILARITY_THRESHOLD) -> None:
    """
    Reconstruit et sauvegarde la version fusionnée d'un candidat dans
    merged_candidates. Idempotent — safe à chaque ingestion.
    """
    merged_cv = build_merged_candidate_cv(
        mongo_collection=_candidates_col,
        candidate_id=candidate_id,
        target_collection=_merged_candidates_col,
        threshold=threshold,
    )
    nb_exp = len(merged_cv.get("experience", []))
    print(f"MERGED — candidate_id={candidate_id} -> {nb_exp} experience(s) unique(s) -> merged_candidates")


def adapt_data_to_schema(data: dict) -> dict:
    """
    Adapte les données extraites par le LLM pour qu'elles correspondent 
    strictement aux attentes du schéma Pydantic d'origine.
    """
    # 1. CORRIGÉ : Mapper sur "category" (car ExpertiseArea attend "category" et/ou "description")
    for field in ["expertise_areas", "functional_skills"]:
        if field in data and isinstance(data[field], list):
            adapted_list = []
            for item in data[field]:
                if isinstance(item, str):
                    # On mappe la string sur "category"
                    adapted_list.append({"category": item, "description": None})
                elif isinstance(item, dict):
                    # Si le LLM a généré une clé "name" par erreur, on la bascule sur "category"
                    if "name" in item and "category" not in item:
                        item["category"] = item.pop("name")
                    
                    if not item.get("category") and not item.get("description"):
                        item["category"] = "Non spécifié"
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
                
                if "technologies" in project:
                    techs = project["technologies"]
                    if isinstance(techs, list):
                        project["technologies"] = [
                            t.get("name") if isinstance(t, dict) else str(t)
                            for t in techs if t is not None
                        ]
                    else:
                        project["technologies"] = []

    # 3. Nettoyer les expériences (notamment les technologies polluées)
    if "experience" in data and isinstance(data["experience"], list):
        for exp in data["experience"]:
            if isinstance(exp, dict):
                if "technologies" in exp:
                    techs = exp["technologies"]
                    if isinstance(techs, list):
                        cleaned_techs = []
                        for t in techs:
                            if isinstance(t, dict):
                                # Sécurité si le LLM a fait un dictionnaire pour une tech
                                cleaned_techs.append(t.get("name") or t.get("category") or "Inconnu")
                            elif t is not None:
                                cleaned_techs.append(str(t))
                        exp["technologies"] = cleaned_techs
                    else:
                        exp["technologies"] = []

    # 4. Nettoyer les certifications
    if "certifications" in data and isinstance(data["certifications"], list):
        for cert in data["certifications"]:
            if isinstance(cert, dict) and cert.get("name") is None:
                # Si c'est un dictionnaire mais sans la clé requise "name"
                cert["name"] = "Certification"

    # 5. Nettoyer les langues
    if "languages" in data and isinstance(data["languages"], list):
        for lang in data["languages"]:
            if isinstance(lang, dict) and lang.get("language") is None:
                lang["language"] = "Langue non spécifiée"

    return data


# --- AJOUT : mode merge-only (skip extraction + storage, fusionne juste l'existant) ---
import sys
MERGE_ONLY = "--merge-only" in sys.argv or os.getenv("MERGE_ONLY", "false").lower() == "true"

if MERGE_ONLY:
    print("MODE: MERGE_ONLY — skip extraction/storage, fusion de tous les candidats existants")
    for candidate in _candidates_col.find({}, {"_id": 1}):
        candidate_id = str(candidate["_id"])
        try:
            sync_merged_candidate(candidate_id)
        except Exception as e:
            print(f"FAILED merge candidate_id={candidate_id}: {type(e).__name__}: {e}")
    raise SystemExit(0)

SAMPLES_DIR = "data/samples"
# --- D2C ---
results = find_cv_files('data/D2C Pôle Consulting-20260708T092849Z-3-001')

# --- CV Externe (TECH-6, générique) ---
#results = [(path, "") for path in find_cv_files_external('data/CV-20260708T092409Z-3-001/CV/CV Externe')]
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
        language = detect(text)
        print(language)
        translator = deepl.Translator(deepl_key)
        original_text=None
        if language == "fr":
            original_text=text
            result = translator.translate_text(text, target_lang="EN-US")
            print("text translated")
            text = result.text
            
        #API
        data = {**extract_contact_info(text), **extract_structured_sections(text,path,folder_name)}
        #Local LLM
        #data = {**extract_contact_info(text), **extract_structured_sections_local(text,folder_name,path)}
        data = adapt_data_to_schema(data)
        if not validate_email_matches_name(data.get("email"), data.get("name", "")):
            data["email"] = None
        cv = CVSchema(**data)
        result = save_cv(cv, text,original_text)
        print(f"{result['status'].upper()} — email: {result['email']} — name:  {result['name']}, v{result['version']}")

        # --- AJOUT : sync merged_candidates (skip si duplicate exact) ---
        if result["status"] != "duplicate":
            sync_merged_candidate(result["candidate_id"])

    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")