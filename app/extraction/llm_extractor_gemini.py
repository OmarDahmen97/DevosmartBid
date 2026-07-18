
from google import genai
import time
import json
import re
import os
from dotenv import load_dotenv
from app.extraction.chunker import split_raw_text_into_chunks
from app.extraction.prompt_builder import (
    build_prompt,
    build_prompt_tech6_general,
    build_prompt_tech6_missions,
    build_prompt_D2C_general,
    build_prompt_D2C_missions,
    resolve_candidate_name,
    is_d2c_format,
    build_prompt_generic,
    build_prompt_generic_chunk,
    is_tech6_format
)
#from app.config import get_groq_api_key


load_dotenv()
Gemini_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=Gemini_key)



CHUNKING_THRESHOLD = 5000


def _extract_first_json(text: str):
    """Extrait le premier objet/tableau JSON valide d'un texte, en ignorant
    tout contenu parasite avant ou après (ex: texte superflu, 'Extra data')."""
    text = text.strip()
    decoder = json.JSONDecoder()
    try:
        return decoder.raw_decode(text)[0]
    except json.JSONDecodeError:
        pass

    for opener, closer in (("{", "}"), ("[", "]")):
        idx = text.find(opener)
        if idx == -1:
            continue
        depth = 0
        in_str = False
        esc = False
        for i in range(idx, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == opener:
                    depth += 1
                elif ch == closer:
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[idx:i + 1])
                        except json.JSONDecodeError:
                            break
    raise ValueError("Aucun JSON valide trouvé dans la réponse du modèle")


def _parse_response(response, key: str | None = None) -> dict:
    """Parse la réponse JSON du modèle Gemini de façon robuste.

    Le modèle renvoie parfois un tableau JSON au premier niveau au lieu d'un
    objet, ou ajoute du texte parasite avant/après le JSON, ou des balises
    Markdown. Si `key` est fourni (ex: "missions"/"experience"), un tableau
    renvoyé directement est encapsulé sous cette clé. Sinon on renvoie le
    premier élément dict du tableau ou un dict vide.
    """
    text = (response.text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[^\n]*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
        text = text.strip()

    data = _extract_first_json(text)
    if isinstance(data, list):
        if key is not None:
            return {key: data}
        if data and isinstance(data[0], dict):
            return data[0]
        return {}
    return data if isinstance(data, dict) else {}


#TECH-6
def split_missions_block(raw_text: str) -> list[str]:
    # 1. Détection des débuts de missions
    months_pattern = r'(?:janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre)'
    pattern = rf'(?mi)^\s*(?:{months_pattern}\s+)?\d{{4}}(?:\s*(?:-|\u2013|\u2014)\s*(?:{months_pattern}\s+)?\d{{4}})?\s*\|'

    mission_starts = [m.start() for m in re.finditer(pattern, raw_text)]
    
    if not mission_starts:
        return [raw_text.strip()]

    end_marker = "|end of table"
    individual_missions = []
    
    # 2. Extraction de chaque mission de manière isolée
    for i in range(len(mission_starts)):
        start = mission_starts[i]
        marker_pos = raw_text.find(end_marker, start)
        end_limit = marker_pos + len(end_marker) if marker_pos != -1 else len(raw_text)

        next_start = mission_starts[i + 1] if i + 1 < len(mission_starts) else end_limit
        end = min(next_start, end_limit)
        
        individual_missions.append(raw_text[start:end].strip())

    # 3. Calcul de la longueur moyenne d'une mission
    total_chars = sum(len(m) for m in individual_missions)
    avg_length = total_chars / len(individual_missions)
    print(f"Missions détectées : {len(individual_missions)} | Longueur moyenne : {avg_length:.1f} caractères")

    # 4. Choix dynamique du nombre de missions par chunk
    # Si la moyenne est inférieure à 600 caractères, on fusionne 3 par 3. Sinon, 1 par 1.
    if avg_length < 600:
        missions_per_chunk = 3
        print("Missions courtes détectées -> Regroupement 3 par 3")
    else:
        missions_per_chunk = 1
        print("Missions longues détectées -> Découpage 1 par 1")

    # 5. Création des chunks
    chunks = []
    for i in range(0, len(individual_missions), missions_per_chunk):
        group = individual_missions[i:i + missions_per_chunk]
        chunks.append("\n\n---\n\n".join(group))

    return chunks

def build_prompt_tech6_general(raw_text: str, folder_name: str) -> str:
    return f"""Extract ONLY these fields from this CV text as JSON only, no other text, no markdown code fences.

{{
  "name": "full candidate name",
  "countries_worked": ["country1", "country2"],
  "professional_affiliations": ["affiliation1"],
  "education": [{{"degree": "...", "field_of_study": null, "institution": "...", "years": "..."}}],
  "certifications": [],
  "languages": [{{"language": "...", "level": "..."}}]
}}

This is a World Bank / EU standardized consultant CV (TECH-6 format). Extract ONLY the fields listed above — ignore the detailed mission/experience list entirely, it is handled separately.

IMPORTANT for name: if missing or reduced to initials, use this name instead, from the folder: "{folder_name}"

CV text:
{raw_text}"""


def build_prompt_tech6_missions(missions_text: str) -> str:
    return f"""Extract every mission listed in this CV excerpt as JSON only, no other text, no markdown code fences.

{{
  "missions": [{{"year": "...", "employer": "...", "country": "...", "activities": "combine all activities for this mission into one string"}}]
}}

This is an excerpt from a World Bank / EU consultant CV, listing individual missions. Extract EVERY mission listed — do not skip or summarize any entry.
If year is 1111 or missing, leave it null. 
Text excerpt:
{missions_text}"""


def extract_structured_sections_tech6_chunked(raw_text: str, folder_name: str = "") -> dict:
    prompt_general = build_prompt_tech6_general(raw_text, folder_name)
    response = client.models.generate_content(
    model="gemini-3.1-flash-lite",
    contents=prompt_general,
    config={
        "response_mime_type": "application/json",
        "max_output_tokens": 2000
    }
)
    general_data = _parse_response(response)

    all_projects = []

    mission_chunks = split_missions_block(raw_text)

    for chunk in mission_chunks:
        prompt_missions = build_prompt_tech6_missions(chunk)
        response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=prompt_missions,
        config={
            "response_mime_type": "application/json",
            "max_output_tokens": 4000
    }
)
        chunk_data = _parse_response(response, key="missions")

        for mission in chunk_data.get("missions", []):
            activities = mission.get("activities")
            if isinstance(activities, list):
                activities = " ".join(str(a) for a in activities)

            all_projects.append({
                "name": f"{mission.get('employer', 'N/A')} ({mission.get('year', 'N/A')})",
                "description": f"{mission.get('country', '')} — {activities or ''}".strip(" —"),
                "technologies": []
            })

        time.sleep(2)

    general_data["experience"] = []  # ce format TECH-6 traite tout comme des missions/projects, pas d'experience séparée
    general_data["projects"] = all_projects
    general_data["name"] = resolve_candidate_name(general_data.get("name", ""), folder_name)
    general_data.setdefault("summary", None)
    general_data.setdefault("expertise_areas", [])
    general_data.setdefault("functional_skills", [])
    general_data.setdefault("skills", [])

    return general_data

#D2C
def split_d2c_missions(raw_text: str, chunk_size: int = 1) -> list[str]:
    pattern = r'\n[^\n|]{3,80}\|\s*(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre|january|february|march|april|may|june|july|august|september|october|november|december|\d{4})[^\n]*'
    mission_starts = [m.start() for m in re.finditer(pattern, raw_text, re.IGNORECASE)]

    if not mission_starts:
        return [raw_text]

    chunks = []
    for i in range(0, len(mission_starts), chunk_size):
        start = mission_starts[i]
        end = mission_starts[i + chunk_size] if i + chunk_size < len(mission_starts) else len(raw_text)
        chunks.append(raw_text[start:end])  

    return chunks

def extract_structured_sections_d2c_chunked(raw_text: str, folder_name: str = "") -> dict:
    prompt_general = build_prompt_D2C_general(raw_text, folder_name)
    response = client.models.generate_content(
    model="gemini-3.1-flash-lite",
    contents=prompt_general,
    config={
        "response_mime_type": "application/json",
        "max_output_tokens": 3000
    }
)
    general_data = _parse_response(response)

    all_experience = []
    mission_chunks = split_d2c_missions(raw_text)

    for chunk in mission_chunks:
        prompt_missions = build_prompt_D2C_missions(chunk)
        response = client.models.generate_content(
    model="gemini-3.1-flash-lite",
    contents=prompt_missions,
    config={
        "response_mime_type": "application/json",
        "max_output_tokens": 4000
    }
)
        chunk_data = _parse_response(response, key="experience")
        all_experience.extend(chunk_data.get("experience", []))
        time.sleep(2)

    general_data["experience"] = all_experience
    general_data["projects"] = []
    general_data["countries_worked"] = []
    general_data["professional_affiliations"] = []
    general_data["name"] = resolve_candidate_name(general_data.get("name", ""), folder_name)

    return general_data
#general pdfs and non structured formats

def merge_generic_chunks(chunks_json_list: list[dict]) -> dict:
    """
    Fusionne une liste de dictionnaires JSON (extraits de chaque morceau de CV)
    en un seul dictionnaire structuré conforme à CVSchema.
    """
    # Structure de base identique à ton CVSchema
    merged_cv = {
        "name": "",
        "summary": None,
        "expertise_areas": [],
        "functional_skills": [],
        "countries_worked": [],
        "professional_affiliations": [],
        "skills": [],
        "education": [],
        "experience": [],
        "projects": [],
        "certifications": [],
        "languages": []
    }
    
    summaries = []
    
    for chunk in chunks_json_list:
        if not chunk or not isinstance(chunk, dict):
            continue
            
        # 1. Extraction du Nom (On prend le premier nom valide trouvé)
        if not merged_cv["name"] and chunk.get("name"):
            name_candidate = chunk["name"].strip()
            # On évite de garder des valeurs génériques ou vides
            if name_candidate.lower() not in ["null", "", "full candidate name", "candidate name"]:
                merged_cv["name"] = name_candidate
            
        # 2. Accumulation des résumés / objectifs professionnels
        if chunk.get("summary"):
            summary_text = chunk["summary"].strip()
            if summary_text and summary_text.lower() != "null":
                summaries.append(summary_text)
                
        # 3. Fusion des listes de chaînes de caractères simples (sans doublons sémantiques)
        # On utilise set() pour s'assurer que les skills, pays ou affiliations n'apparaissent pas deux fois
        for key in ["skills", "countries_worked", "professional_affiliations"]:
            if chunk.get(key) and isinstance(chunk[key], list):
                # On nettoie et on fusionne
                cleaned_items = [str(item).strip() for item in chunk[key] if item]
                merged_cv[key] = list(set(merged_cv[key] + cleaned_items))
                
        # 4. Fusion des listes d'objets complexes (on accumule tout simplement)
        # La validation et le nettoyage finaux seront gérés par ton Pydantic CVSchema
        object_keys = [
            "expertise_areas", 
            "functional_skills", 
            "education", 
            "experience", 
            "projects", 
            "certifications", 
            "languages"
        ]
        for key in object_keys:
            if chunk.get(key) and isinstance(chunk[key], list):
                merged_cv[key].extend(chunk[key])
                
    # On rassemble les morceaux de résumés s'il y en a plusieurs
    if summaries:
        # On enlève les doublons de phrases exactes au cas où un morceau d'overlap s'est répété
        unique_summaries = []
        for s in summaries:
            if s not in unique_summaries:
                unique_summaries.append(s)
        merged_cv["summary"] = " ".join(unique_summaries)
        
    return merged_cv

def extract_structured_sections_generic_chunked(raw_text: str, folder_name: str = "") -> dict:
    """
    Découpe un CV générique trop long en plusieurs petits morceaux (chunks),
    les envoie un par un au LLM en évitant les limites TPM de Groq.
    """
    # Chunks plus petits pour passer sous la limite TPM de 6000
    chunks = split_raw_text_into_chunks(raw_text, max_chars=1500, overlap=150)
    print(f"[Generic Chunking] CV split into {len(chunks)} chunks of 1500 characters each.")

    extracted_chunks_json = []

    for i, chunk_text in enumerate(chunks):
        print(f"   -> Chunk processing {i+1}/{len(chunks)}...")
        
        # Utilisation du prompt allégé
        prompt = build_prompt_generic_chunk(chunk_text, folder_name)
        
        try:
            response = client.models.generate_content(
    model="gemini-3.1-flash-lite",
    contents=prompt,
    config={
        "response_mime_type": "application/json",
        "max_output_tokens": 1500
    }
)
            
            chunk_data = _parse_response(response)
            extracted_chunks_json.append(chunk_data)
            
        except Exception as e:
            print(f"  Failed to extract from chunk {i+1}: {e}")
        
        # Pause of 3 seconds to allow the TPM/RPM quota to reset
        time.sleep(5.0)

    final_data = merge_generic_chunks(extracted_chunks_json)
    final_data["name"] = resolve_candidate_name(final_data.get("name", ""), folder_name)
    
    return final_data




#final extraction function
def extract_structured_sections(raw_text: str,file_path, folder_name: str = "", max_retries=3) -> dict:
    is_tech6 = is_tech6_format(raw_text)
    is_d2c = is_d2c_format(raw_text,file_path)

    # Cas 1 : Format TECH-6 long
    if is_tech6 and len(raw_text) > CHUNKING_THRESHOLD:
        print("Using TECH-6 chunked extraction (long CV)")
        return extract_structured_sections_tech6_chunked(raw_text, folder_name)

    # Cas 2 : Format D2C long
    if is_d2c and len(raw_text) > CHUNKING_THRESHOLD:
        print("Using D2C chunked extraction (long CV)")
        return extract_structured_sections_d2c_chunked(raw_text, folder_name)

    # Cas 3 : Format Générique / Non structuré long (AJOUTÉ)
    if len(raw_text) > CHUNKING_THRESHOLD:
        print(f"Using GENERIC chunked extraction (long CV: {len(raw_text)} chars)")
        return extract_structured_sections_generic_chunked(raw_text, folder_name)

    # Cas 4 : CV court (TECH-6, D2C ou Générique < CHUNKING_THRESHOLD) -> Traitement standard
    for attempt in range(max_retries):
        try:
            prompt = build_prompt(raw_text, folder_name,file_path)
            response = client.models.generate_content(
    model="gemini-3.1-flash-lite",
    contents=prompt,
    config={
        "response_mime_type": "application/json",
        "max_output_tokens": 16000
    }
)
            data = _parse_response(response)
            data["name"] = resolve_candidate_name(data.get("name", ""), folder_name)
            return data
        except Exception:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)



