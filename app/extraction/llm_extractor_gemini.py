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



load_dotenv()
Gemini_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=Gemini_key)
model_name="gemini-3.1-flash-lite"


CHUNKING_THRESHOLD = 5000


def _extract_first_json(text: str):
    """Extracts the first valid JSON object/array from a text, ignoring
    any noise content before or after (e.g., extra text, 'Extra data')."""
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
    raise ValueError("No valid JSON found in model response")


def _parse_response(response, key: str | None = None) -> dict:
    """Robustly parses the JSON response from the Gemini model.

    The model sometimes returns a top-level JSON array instead of an
    object, or adds stray text before/after the JSON, or Markdown tags.
    If `key` is provided (e.g., "missions"/"experience"), a directly returned
    array is wrapped under this key. Otherwise, it returns the first dict element
    of the array or an empty dict.
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
    # 1. Detection of mission start positions
    months_pattern = r'(?:janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre)'
    pattern = rf'(?mi)^\s*(?:{months_pattern}\s+)?\d{{4}}(?:\s*(?:-|\u2013|\u2014)\s*(?:{months_pattern}\s+)?\d{{4}})?\s*\|'

    mission_starts = [m.start() for m in re.finditer(pattern, raw_text)]
    
    if not mission_starts:
        return [raw_text.strip()]

    end_marker = "|end of table"
    individual_missions = []
    
    # 2. Extracting each mission individually
    for i in range(len(mission_starts)):
        start = mission_starts[i]
        marker_pos = raw_text.find(end_marker, start)
        end_limit = marker_pos + len(end_marker) if marker_pos != -1 else len(raw_text)

        next_start = mission_starts[i + 1] if i + 1 < len(mission_starts) else end_limit
        end = min(next_start, end_limit)
        
        individual_missions.append(raw_text[start:end].strip())

    # 3. Calculating average mission length
    total_chars = sum(len(m) for m in individual_missions)
    avg_length = total_chars / len(individual_missions)
    print(f"Missions detected: {len(individual_missions)} | Average length: {avg_length:.1f} characters")

    # 4. Dynamic selection of number of missions per chunk
    # If the average length is less than 600 characters, merge 3 by 3. Otherwise, 1 by 1.
    if avg_length < 600:
        missions_per_chunk = 3
        print("Short missions detected -> Grouping 3 by 3")
    else:
        missions_per_chunk = 1
        print("Long missions detected -> Splitting 1 by 1")

    # 5. Creating chunks
    chunks = []
    for i in range(0, len(individual_missions), missions_per_chunk):
        group = individual_missions[i:i + missions_per_chunk]
        chunks.append("\n\n---\n\n".join(group))

    return chunks





def extract_structured_sections_tech6_chunked(raw_text: str, folder_name: str = "") -> dict:
    prompt_general = build_prompt_tech6_general(raw_text, folder_name)
    response = client.models.generate_content(
    model=model_name,
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
        model=model_name,
        contents=prompt_missions,
        config={
            "response_mime_type": "application/json",
            "max_output_tokens": 4000
    }
)
        chunk_data = _parse_response(response, key="missions")
        

        for mission in chunk_data.get("missions", []):
            if not isinstance(mission, dict):
                continue

            # 1. Extraction avec les NOUVELLES clés du LLM
            dates = mission.get("dates")
            company = mission.get("company")
            title = mission.get("title")
            description = mission.get("description") or ""

            if isinstance(description, list):
                description = " ".join(str(d) for d in description)

            # 2. Construction dynamique du champ 'name' ou 'title'
            # Combine title et company proprement si disponibles
            header_parts = [p.strip() for p in [title, company] if p and str(p).strip()]
            base_name = " - ".join(header_parts) if header_parts else None

            # 3. Structuration de l'objet pour 'experience'
            all_projects.append({
                "title": title or "Position not specified",
                "company": company,
                "dates": dates,
                "description": description.strip(),
                "responsibilities": [],
                "deliverables": [],
                "technologies": []
            })

    time.sleep(2)

    general_data["experience"] = all_projects 
    general_data["projects"] = []
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
    model=model_name,
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
    model=model_name,
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
    Merges a list of JSON dictionaries (extracted from each CV chunk)
    into a single structured dictionary matching CVSchema.
    """
    # Base structure identical to your CVSchema
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
            
        # 1. Extract Name (Take the first valid name found)
        if not merged_cv["name"] and chunk.get("name"):
            name_candidate = chunk["name"].strip()
            # Avoid keeping generic or empty values
            if name_candidate.lower() not in ["null", "", "full candidate name", "candidate name"]:
                merged_cv["name"] = name_candidate
            
        # 2. Accumulate summaries / professional goals
        if chunk.get("summary"):
            summary_text = chunk["summary"].strip()
            if summary_text and summary_text.lower() != "null":
                summaries.append(summary_text)
                
        # 3. Merge simple string lists (without semantic duplicates)
        # We use set() to ensure that skills, countries, or affiliations do not appear twice
        for key in ["skills", "countries_worked", "professional_affiliations"]:
            if chunk.get(key) and isinstance(chunk[key], list):
                # Clean up and merge
                cleaned_items = [str(item).strip() for item in chunk[key] if item]
                merged_cv[key] = list(set(merged_cv[key] + cleaned_items))
                
        # 4. Merge lists of complex objects (simply accumulating everything)
        # Final validation and cleaning will be handled by your Pydantic CVSchema
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
                
    # Gather summary fragments if there are multiple
    if summaries:
        # Remove exact duplicate sentences in case an overlap fragment was repeated
        unique_summaries = []
        for s in summaries:
            if s not in unique_summaries:
                unique_summaries.append(s)
        merged_cv["summary"] = " ".join(unique_summaries)
        
    return merged_cv

def extract_structured_sections_generic_chunked(raw_text: str, folder_name: str = "") -> dict:
    """
    Splits an overly long generic CV into multiple smaller chunks,
    sending them one by one to the LLM while avoiding Groq's TPM limits.
    """
    # Smaller chunks to stay under the 6,000 TPM limit
    chunks = split_raw_text_into_chunks(raw_text, max_chars=1500, overlap=150)
    print(f"[Generic Chunking] CV split into {len(chunks)} chunks of 1500 characters each.")

    extracted_chunks_json = []

    for i, chunk_text in enumerate(chunks):
        print(f"   -> Chunk processing {i+1}/{len(chunks)}...")
        
        # Using the lightweight prompt
        prompt = build_prompt_generic_chunk(chunk_text, folder_name)
        
        try:
            response = client.models.generate_content(
    model=model_name,
    contents=prompt,
    config={
        "response_mime_type": "application/json",
        "max_output_tokens": 1500
    }
)
            
            chunk_data = _parse_response(response,key="missions")
            extracted_chunks_json.append(chunk_data)
            
        except Exception as e:
            print(f"   Failed to extract from chunk {i+1}: {e}")
        
        # Pause of 5 seconds to allow the TPM/RPM quota to reset
        time.sleep(5.0)

    final_data = merge_generic_chunks(extracted_chunks_json)
    final_data["name"] = resolve_candidate_name(final_data.get("name", ""), folder_name)
    
    return final_data




#final extraction function
def extract_structured_sections(raw_text: str,file_path, folder_name: str = "", max_retries=3) -> dict:
    is_tech6 = is_tech6_format(raw_text)
    is_d2c = is_d2c_format(raw_text,file_path)

    # Case 1: Long TECH-6 format
    if is_tech6 and len(raw_text) > CHUNKING_THRESHOLD:
        print("Using TECH-6 chunked extraction (long CV)")
        return extract_structured_sections_tech6_chunked(raw_text, folder_name)

    # Case 2: Long D2C format
    if is_d2c and len(raw_text) > CHUNKING_THRESHOLD:
        print("Using D2C chunked extraction (long CV)")
        return extract_structured_sections_d2c_chunked(raw_text, folder_name)

    # Case 3: Long Generic / Unstructured format (ADDED)
    if len(raw_text) > CHUNKING_THRESHOLD:
        print(f"Using GENERIC chunked extraction (long CV: {len(raw_text)} chars)")
        return extract_structured_sections_generic_chunked(raw_text, folder_name)

    # Case 4: Short CV (TECH-6, D2C or Generic < CHUNKING_THRESHOLD) -> Standard processing
    for attempt in range(max_retries):
        try:
            prompt = build_prompt(raw_text, folder_name,file_path)
            response = client.models.generate_content(
    model=model_name,
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