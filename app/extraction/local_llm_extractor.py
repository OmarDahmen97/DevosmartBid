import ollama
import json
import re



def build_prompt(raw_text: str, folder_name: str) -> str:
    if "tech-6" in raw_text.lower() or "tech 6" in raw_text.lower():
        print("Using TECH-6 prompt")
        return build_prompt_tech6(raw_text, folder_name)
    print("Using D2C prompt")
    return build_prompt_D2C(raw_text, folder_name)
    # TODO: ajouter une vraie distinction D2C vs générique une fois
    # build_prompt_generic() écrit — actuellement tout non-TECH-6 tombe
    # sur D2C, ce qui est incorrect pour les CV externes sans template

def build_prompt_tech6(raw_text: str, folder_name: str) -> str:
    return f"""Extract the following fields from this CV text as JSON only, no other text, no markdown code fences.

{{
  "name": "full candidate name",
  "summary": null,
  "countries_worked": ["country1", "country2"],
  "professional_affiliations": ["affiliation1"],
  "skills": [],
  "education": [{{"degree": "...", "field_of_study": null, "institution": "...", "years": "..."}}],
  "certifications": [],
  "languages": [{{"language": "...", "level": "spoken/read/written proficiency if stated"}}],
  "experience": [{{
    "title": "position held",
    "company": "employer name",
    "dates": "from year to year",
    "description": null,
    "responsibilities": [],
    "deliverables": [],
    "technologies": []
  }}],
  "projects": [{{"name": "mission/project name", "description": "activities performed, location, funding source if mentioned", "technologies": []}}]
}}

This CV follows the World Bank / EU standardized consultant CV format (TECH-6), with fixed numbered sections, roughly in this order:
1. Proposed position (ignore, not personal data)
2. Consulting firm name (ignore, not personal data)
3. Employee name → "name"
4. Date of birth, nationality (ignore, do not extract into any field)
5. Education → "education"
6. Professional association memberships → "professional_affiliations"
7. Additional training (merge into "education" as additional entries, or into "certifications" if clearly a certification)
8. Countries worked in → "countries_worked"
9. Languages, usually rated by proficiency level per skill (spoken/read/written) → "languages"
10. Employment record, reverse chronological, employer + position + dates → "experience" (title, company, dates)
11. Detailed tasks per assignment/mission, usually including project name, year, location, funding source, position, activities → map each into "projects" (name = project/mission name, description = combining location, funding source and activities described)
12. Prior experience most illustrative of competence for the current assignment → merge relevant content into "projects" if not already captured

IMPORTANT: this format always ends with a signed declaration/certification statement (e.g. "I certify that..."). This is NOT candidate data — do not extract it into any field, ignore it completely.

IMPORTANT for name: if the name found in the CV text is missing or reduced to initials/an abbreviation, use this name instead, taken from the folder this file was found in: "{folder_name}"

CV text:
{raw_text}"""

def build_prompt_D2C(raw_text: str, folder_name: str) -> str:
    return f"""Extract the following fields from this CV text as JSON only, no other text, no markdown code fences.

{{
  "name": "full candidate name",
  "summary": "the FIRST short professional summary paragraph only, right after the name",
  "expertise_areas": [{{"category": "...", "description": "..."}}],
  "functional_skills": [{{"category": "...", "description": "..."}}],
  "skills": ["skill1", "skill2"],
  "education": [{{"degree": "degree type (e.g. Bachelor's/Licence/Master)", "field_of_study": "field description if stated separately", "institution": "...", "years": "..."}}],
  "certifications": [{{"name": "...", "issuer": "...", "year": "..."}}],
  "languages": [{{"language": "...", "level": "..."}}],
  "experience": [{{
    "title": "mission/role title",
    "company": "client company name",
    "dates": "...",
    "description": "mission context",
    "responsibilities": [{{"category": "...", "description": "full merged text for this category"}}],
    "deliverables": ["deliverable1", "deliverable2"],
    "technologies": ["tech1", "tech2"]
  }}],
  "projects": []
}}

This CV follows a fixed company template, in reading order (plain text only, no page numbers). The text may be in French or English — identify sections by their STRUCTURE and POSITION, not by specific keywords, since headers vary by language.

1. Candidate name, followed by a short professional summary paragraph (→ "summary"). Immediately after, there are usually 2-4 labeled areas, each a short label followed by ":" and one or more explanatory sentences — each is a separate entry in "expertise_areas" (category = label, description = text after it), NOT part of "summary".
2. Education and certifications. When a degree appears as "DegreeType" followed by "YYYY : field description", set "degree" to the degree type, "field_of_study" to the description, "years" to the year.
3. A brief overall experience recap (short, not the detailed missions).
4. Languages.
5. A short recent-experience summary list (company, role, duration) — use for "experience" only if no more detailed version of the same role appears later in the text.
6. Two distinct skills sections, told apart by their CONTENT PATTERN, not by title wording:
   - One lists concrete tool/technology names grouped under category headers (e.g. header "Programming Languages" with items "Python", "SQL"). Extract ONLY the concrete names into "skills" — never the category headers.
   - The other lists short category names each followed by ONE descriptive sentence (not a list of names). Extract each as a separate entry in "functional_skills" (category = short name, description = the sentence after it).
7.Some lines under the technical skills section mention MULTIPLE tool/technology/platform names within a single descriptive sentence, rather than one name per line. Extract EVERY concrete name mentioned in each sentence into "skills" — do not extract only the first name mentioned, and do not skip names embedded mid-sentence alongside a description of what was done with them.
8. Detailed professional experience, one block per mission: client company, role and dates, mission title, context, a responsibilities section (→ responsibilities, one entry per category with bullets merged), a deliverables section (→ deliverables, one string per item), a technical environment section (→ technologies, flat list merging all sub-groups like databases/languages/OS/tools/methodologies).

IMPORTANT for name: if the name found in the CV text is missing or reduced to initials/an abbreviation, use this name instead, taken from the folder this file was found in: "{folder_name}"

CV text:
{raw_text}"""

def resolve_candidate_name(extracted_name: str, folder_name: str) -> str:
    """
    Filet de sécurité si le LLM ignore l'instruction de fallback dans le
    prompt. Détecte un nom probablement réduit à des initiales.
    """
    cleaned = (extracted_name or "").replace(".", "").replace(" ", "")
    if len(cleaned) <= 3:
        return folder_name.strip()
    return extracted_name.strip()



def _parse_response_local(response: dict, key: str | None = None) -> dict:
    text = (response.get("message", {}).get("content") or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[^\n]*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
        text = text.strip()

    data = json.loads(text)
    if isinstance(data, list):
        if key is not None:
            return {key: data}
        if data and isinstance(data[0], dict):
            return data[0]
        return {}
    return data if isinstance(data, dict) else {}


def extract_structured_sections_local(raw_text: str, folder_name: str="", max_retries=3) -> dict:
    for attempt in range(max_retries):
       
            prompt = build_prompt(raw_text, folder_name)
            response = ollama.chat(
            model="qwen2.5:7b",
            messages=[{"role": "user", "content": prompt}],
           format="json"
    )

    return _parse_response_local(response)
        

