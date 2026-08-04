"""
app/extraction/pipeline.py

Single-CV extraction + storage, refactored out of the batch ingestion script
into a reusable function that returns the full stored candidate document
(so downstream matching / profile detection can use it directly).
"""

import os
from app.ingestion.format_detector import detect_format, UnsupportedFormatError
from app.extraction.pdf_extractor import extract_pdf_text
from app.extraction.docx_extractor import extract_docx_text
from app.extraction.pptx_extractor import extract_pptx_text
from app.extraction.contact_parser import extract_contact_info, validate_email_matches_name
from app.extraction.llm_extractor_gemini import extract_structured_sections
from app.schema import CVSchema
from app.storage import save_cv, find_existing_by_raw_text
from langdetect import detect
import deepl

deepl_key = os.getenv("DEEPL_API_KEY")


def adapt_data_to_schema(data: dict) -> dict:
    """
    Adapte les données extraites par le LLM pour qu'elles correspondent
    strictement aux attentes du schéma Pydantic d'origine.
    """
    for field in ["expertise_areas", "functional_skills"]:
        if field in data and isinstance(data[field], list):
            adapted_list = []
            for item in data[field]:
                if isinstance(item, str):
                    adapted_list.append({"category": item, "description": None})
                elif isinstance(item, dict):
                    if "name" in item and "category" not in item:
                        item["category"] = item.pop("name")
                    if not item.get("category") and not item.get("description"):
                        item["category"] = "Non spécifié"
                    adapted_list.append(item)
                else:
                    adapted_list.append(item)
            data[field] = adapted_list

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

    if "experience" in data and isinstance(data["experience"], list):
        for exp in data["experience"]:
            if isinstance(exp, dict):
                if "technologies" in exp:
                    techs = exp["technologies"]
                    if isinstance(techs, list):
                        cleaned_techs = []
                        for t in techs:
                            if isinstance(t, dict):
                                cleaned_techs.append(t.get("name") or t.get("category") or "Inconnu")
                            elif t is not None:
                                cleaned_techs.append(str(t))
                        exp["technologies"] = cleaned_techs
                    else:
                        exp["technologies"] = []

    if "certifications" in data and isinstance(data["certifications"], list):
        for cert in data["certifications"]:
            if isinstance(cert, dict) and cert.get("name") is None:
                cert["name"] = "Certification"

    if "languages" in data and isinstance(data["languages"], list):
        for lang in data["languages"]:
            if isinstance(lang, dict) and lang.get("language") is None:
                lang["language"] = "Langue non spécifiée"

    return data


def extract_and_store_cv(path: str, folder_name: str = "", candidates_collection=None) -> dict:
    """
    Full single-CV extraction + storage pipeline. Returns the full candidate
    Mongo document (with _id and versions) so downstream matching / profile
    detection can use it directly.

    Unlike the batch script this was refactored from, failures are NOT caught
    and logged here -- they propagate to the caller, since a single-CV usage
    flow needs to know if extraction failed, not silently skip and continue.

    Raises:
        UnsupportedFormatError: unsupported file format.
        pydantic.ValidationError: extracted data doesn't fit CVSchema.
        RuntimeError: save_cv reported success but the candidate wasn't found
                      afterward (storage inconsistency -- should never happen).
        Exception: any extraction/translation/LLM call failure, unmodified.
    """
    if candidates_collection is None:
        from app.storage import candidates as candidates_collection

    filename = os.path.basename(path)
    print(f"[1/7] Détection du format : {filename}")
    fmt = detect_format(path)  # raises UnsupportedFormatError if not supported
    print(f"      -> format détecté : {fmt}")

    print(f"[2/7] Extraction du texte brut ({fmt})...")
    text = (
        extract_pdf_text(path) if fmt == "pdf"
        else extract_docx_text(path) if fmt == "docx"
        else extract_pptx_text(path)
    )
    print(f"      -> {len(text)} caractères extraits")

    print("[3/7] Vérification de doublon (raw_text exact)...")
    existing_version = find_existing_by_raw_text(text)
    if existing_version is not None:
        print(f"      -> DOUBLON détecté (version {existing_version} déjà en base), pas de ré-extraction LLM")
        candidate = candidates_collection.find_one({"versions.raw_text": text})
        if candidate:
            return candidate
        raise RuntimeError(
            f"find_existing_by_raw_text reported v{existing_version} but no matching candidate found"
        )
    print("      -> pas de doublon, poursuite du traitement")

    print("[4/7] Détection de la langue...")
    language = detect(text)
    print(f"      -> langue détectée : {language}")
    original_text = None
    if language == "fr":
        print("      -> traduction FR -> EN via DeepL...")
        translator = deepl.Translator(deepl_key)
        original_text = text
        text = translator.translate_text(text, target_lang="EN-US").text
        print("      -> traduction terminée")

    print("[5/7] Extraction structurée (LLM)...")
    data = {**extract_contact_info(text), **extract_structured_sections(text, path, folder_name)}
    print(f"      -> sections extraites : {list(data.keys())}")

    print("[6/7] Adaptation au schéma + validation...")
    data = adapt_data_to_schema(data)
    if not validate_email_matches_name(data.get("email"), data.get("name", "")):
        print("      -> email incohérent avec le nom, mis à null")
        data["email"] = None
    cv = CVSchema(**data)
    print(f"      -> schéma validé pour : {cv.name}")

    print("[7/7] Stockage MongoDB...")
    result = save_cv(cv, text, original_text)
    print(f"      -> {result['status']} — {result['name']} (v{result['version']})")

    # save_cv stores original_text if present, else the (untranslated) text --
    # exactly the same value find_existing_by_raw_text checks against above.
    # Querying on this raw_text is robust to save_cv's internal fuzzy name
    # matching (which can attach this version to an existing candidate whose
    # normalized_name differs slightly from this cv_schema.name).
    stored_raw_text = original_text or text
    candidate = candidates_collection.find_one({"versions.raw_text": stored_raw_text})

    if candidate is None:
        raise RuntimeError(f"save_cv reported success ({result}) but candidate not found in Mongo afterward")

    print(f"Pipeline d'extraction terminé pour {cv.name}.\n")
    return candidate