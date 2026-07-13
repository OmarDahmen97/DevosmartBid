
from datetime import time
from groq import Groq, RateLimitError
import time
import json
import re

from app.extraction.prompt_builder import (
    build_prompt,
    build_prompt_tech6_general,
    build_prompt_tech6_missions,
    build_prompt_D2C_general,
    build_prompt_D2C_missions,
    resolve_candidate_name,
    is_d2c_format,
)
from app.config import get_groq_api_key
import os
from dotenv import load_application_environment, load_dotenv
load_dotenv()
Groq_key = os.getenv("GROQ_API_KEY")
client = MongoClient(Groq_key)




CHUNKING_THRESHOLD = 8000


#TECH-6
def split_missions_block(raw_text: str) -> list[str]:
    # 1. Détection des débuts de missions
    months_pattern = r'(?:janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre)'
    pattern = rf'(?mi)^\s*(?:{months_pattern}\s+)?\d{{4}}(?:\s*-\s*(?:{months_pattern}\s+)?\d{{4}})?\s*\|'

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
        print("Missions longues détectées -> Découpage 1 par² 1")

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
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt_general}],
        response_format={"type": "json_object"},
        max_tokens=2000
    )
    general_data = json.loads(response.choices[0].message.content)

    all_projects = []

    mission_chunks = split_missions_block(raw_text)

    for chunk in mission_chunks:
        prompt_missions = build_prompt_tech6_missions(chunk)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt_missions}],
            response_format={"type": "json_object"},
            max_tokens=4000
        )
        chunk_data = json.loads(response.choices[0].message.content)

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
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt_general}],
        response_format={"type": "json_object"},
        max_tokens=3000
    )
    general_data = json.loads(response.choices[0].message.content)

    all_experience = []
    mission_chunks = split_d2c_missions(raw_text)

    for chunk in mission_chunks:
        prompt_missions = build_prompt_D2C_missions(chunk)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt_missions}],
            response_format={"type": "json_object"},
            max_tokens=4000
        )
        chunk_data = json.loads(response.choices[0].message.content)
        all_experience.extend(chunk_data.get("experience", []))
        time.sleep(2)

    general_data["experience"] = all_experience
    general_data["projects"] = []
    general_data["countries_worked"] = []
    general_data["professional_affiliations"] = []
    general_data["name"] = resolve_candidate_name(general_data.get("name", ""), folder_name)

    return general_data
#general pdfs and non structured formats





#final extraction function
def extract_structured_sections(raw_text: str, folder_name: str = "", max_retries=3) -> dict:
    is_tech6 = "tech-6" in raw_text.lower() or "tech 6" in raw_text.lower()
    is_d2c = is_d2c_format(raw_text)

    if is_tech6 and len(raw_text) > CHUNKING_THRESHOLD:
        print("Using TECH-6 chunked extraction (long CV)")
        return extract_structured_sections_tech6_chunked(raw_text, folder_name)

    if is_d2c and len(raw_text) > CHUNKING_THRESHOLD:
        print("Using D2C chunked extraction (long CV)")

        return extract_structured_sections_d2c_chunked(raw_text, folder_name)

    for attempt in range(max_retries):
        try:
            prompt = build_prompt(raw_text, folder_name)
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=16000
            )
            data = json.loads(response.choices[0].message.content)
            data["name"] = resolve_candidate_name(data.get("name", ""), folder_name)
            return data
        except RateLimitError:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)