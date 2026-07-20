from sentence_transformers import SentenceTransformer

"""
Chunking of structured CV data (post-extraction, from MongoDB)
into text chunks ready for embedding and storage in ChromaDB.
"""

#model = SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')
#tokenizer = model.tokenizer
#max_length = model.max_seq_length


DEFAULT_MAX_TOKENS = 118
HARD_CAP_TOKENS = 120  # safety margin below the model's 128 max_seq_length

MAX_TOKENS_BY_TYPE = {
    "summary": 118,                  
    "skills": 100,                   
    "education": 80,                 
    "languages": 50,                 
    "expertise_areas": 118,          
    "functional_skills": 118,        
    "certifications": 50,            
    "countries_worked": 40,          
    "professional_affiliations": 40, 
    "experience": 118,               
    "project": 100,                  
}


def resolve_max_tokens(chunk_type: str, max_tokens_by_type: dict) -> int:
    """
    Resolve the max_tokens value for a given chunk_type, falling back to the
    default if not specified, and always capped at HARD_CAP_TOKENS regardless
    of configuration, to stay safely under the model's max_seq_length.
    """
    requested = max_tokens_by_type.get(chunk_type, DEFAULT_MAX_TOKENS)
    return min(requested, HARD_CAP_TOKENS)


def serialize_category_description_list(items: list[dict]) -> str:
    """Join a list of {category, description} dicts into one readable string."""
    parts = []
    for item in items:
        category = item.get("category")
        description = item.get("description")
        if category and description:
            parts.append(f"{category}: {description}")
        elif category:
            parts.append(category)
        elif description:
            parts.append(f"Note: {description}")
        # if both are None → skip
    return ". ".join(parts)


def serialize_string_list(items: list[str]) -> str:
    """Join a list of plain strings into one readable comma-separated string."""
    if not items:
        return ""
    return ", ".join(items)


def serialize_experience_to_text(experience: dict) -> str:
    """Convert one experience dict into a clean natural-language string, skipping empty fields."""
    title = experience.get("title")
    company = experience.get("company")
    dates = experience.get("dates")
    description = experience.get("description")
    responsibilities = experience.get("responsibilities") or []
    deliverables = experience.get("deliverables") or []
    technologies = experience.get("technologies") or []

    parts = []

    # Header: title + company + dates
    header_bits = [b for b in [title, company] if b]
    header = " chez ".join(header_bits) if len(header_bits) == 2 else (header_bits[0] if header_bits else "")
    if header and dates:
        header = f"{header} ({dates})"
    elif dates:
        header = dates
    if header:
        parts.append(header)

    if description:
        parts.append(description)

    responsibilities_text = serialize_category_description_list(responsibilities)
    if responsibilities_text:
        parts.append(f"Responsabilités: {responsibilities_text}")

    deliverables_text = serialize_string_list(deliverables)
    if deliverables_text:
        parts.append(f"Livrables: {deliverables_text}")

    technologies_text = serialize_string_list(technologies)
    if technologies_text:
        parts.append(f"Technologies: {technologies_text}")

    return ". ".join(parts)

def count_tokens(text: str, tokenizer) -> int:
    """Count the number of tokens a text will produce with the given tokenizer."""
    return len(tokenizer.encode(text))

def split_text_by_tokens(text: str, tokenizer, max_tokens: int, overlap: int = 20) -> list[str]:
    """Split text into overlapping token windows when it exceeds the model's max sequence length."""
    tokens = tokenizer.encode(text, add_special_tokens=False)
    if len(tokens) <= max_tokens:
        return [text]

    # scale overlap proportionally to max_tokens, capped by the fixed overlap
    # requested, to avoid degenerate windows on very small max_tokens
    safe_overlap = min(overlap, max_tokens // 3)  # at most 1/3 of the window

    chunks = []
    start = 0
    while start < len(tokens):
        end = start + max_tokens
        chunk_tokens = tokens[start:end]
        chunks.append(tokenizer.decode(chunk_tokens, skip_special_tokens=True))
        start += max_tokens - safe_overlap

    return chunks


def build_experience_chunks(
    experience_list: list[dict],
    candidate_id: str,
    candidate_name: str,
    version_number: int,
    tokenizer,
    max_tokens: int = 118,
) -> list[dict]:
    """Build one chunk per individual experience entry, splitting further if too long."""

    chunks = []

    for experience_index, exp in enumerate(experience_list):
        text = serialize_experience_to_text(exp)
        if not text:
            continue

        sub_texts = split_text_by_tokens(text, tokenizer, max_tokens=max_tokens)

        for part_index, sub_text in enumerate(sub_texts):
            metadata = {
                "candidate_id": candidate_id,
                "candidate_name": candidate_name,
                "version_number": version_number,
                "chunk_type": "experience",
                "company": exp.get("company"),
                "dates": exp.get("dates"),
                "experience_index": experience_index,
                "part_index": part_index,
            }
            chunks.append({"text": sub_text, "metadata": metadata})

    return chunks

#build section chunks
def serialize_education_list(items: list[dict]) -> str:
    """Join a list of education entries into one readable string."""
    parts = []
    for item in items:
        degree = item.get("degree")
        field = item.get("field_of_study")
        institution = item.get("institution")
        years = item.get("years")
        if not degree:
            continue
        entry = degree
        if field:
            entry += f" en {field}"
        if institution:
            entry += f", {institution}"
        if years:
            entry += f" ({years})"
        parts.append(entry)
    return ". ".join(parts)


def serialize_languages_list(items: list[dict]) -> str:
    """Join a list of language entries into one readable string."""
    parts = []
    for item in items:
        language = item.get("language")
        level = item.get("level")
        if not language:
            continue
        parts.append(f"{language} ({level})" if level else language)
    return ", ".join(parts)

def serialize_certifications_list(items: list[dict])-> str :
    """join a list of certifications entries into one readable string"""
    parts=[]
    for item in items:
        certification_name =item.get("name")
        issuer=item.get("issuer")
        year=item.get("year")
        if not certification_name:
            continue
        parts.append(f"{certification_name}" + (f", {issuer}" if issuer else "") + (f" ({year})" if year else ""))
    return ", ".join(parts)

def build_section_chunks(
    structured_data: dict,
    candidate_id: str,
    candidate_name: str,
    version_number: int,
    tokenizer,
    max_tokens_by_type: dict = None,
) -> list[dict]:
    """Build one chunk per section, using a per-type max_tokens (capped) if provided."""
    chunks = []
    max_tokens_by_type = max_tokens_by_type or MAX_TOKENS_BY_TYPE

    section_serializers = {
        "summary": lambda d: d.get("summary") or "",
        "skills": lambda d: serialize_string_list(d.get("skills", [])),
        "certifications": lambda d: serialize_certifications_list(d.get("certifications", [])),
        "countries_worked": lambda d: serialize_string_list(d.get("countries_worked", [])),
        "professional_affiliations": lambda d: serialize_string_list(d.get("professional_affiliations", [])),
        "education": lambda d: serialize_education_list(d.get("education", [])),
        "languages": lambda d: serialize_languages_list(d.get("languages", [])),
        "expertise_areas": lambda d: serialize_category_description_list(d.get("expertise_areas", [])),
        "functional_skills": lambda d: serialize_category_description_list(d.get("functional_skills", [])),
    }

    for section_name, serializer in section_serializers.items():
        text = serializer(structured_data)
        if not text:
            continue

        max_tokens = resolve_max_tokens(section_name, max_tokens_by_type)
        sub_texts = split_text_by_tokens(text, tokenizer, max_tokens=max_tokens)

        for part_index, sub_text in enumerate(sub_texts):
            metadata = {
                "candidate_id": candidate_id,
                "candidate_name": candidate_name,
                "version_number": version_number,
                "chunk_type": section_name,
                "part_index": part_index,
            }
            chunks.append({"text": sub_text, "metadata": metadata})

    return chunks



# build_project_chunks
def build_project_chunks(
    project_list: list[dict],
    candidate_id: str,
    candidate_name: str,
    version_number: int,
    tokenizer,
    max_tokens: int = 118,
) -> list[dict]:
    """Build one chunk per individual project entry."""
    chunks = []

    for project_index, project in enumerate(project_list):
        name = project.get("name")
        description = project.get("description")
        technologies = project.get("technologies") or []

        if not name:
            continue

        parts = [name]
        if description:
            parts.append(description)
        tech_text = serialize_string_list(technologies)
        if tech_text:
            parts.append(f"Technologies: {tech_text}")

        text = ". ".join(parts)
        sub_texts = split_text_by_tokens(text, tokenizer, max_tokens=max_tokens)

        for part_index, sub_text in enumerate(sub_texts):
            metadata = {
                "candidate_id": candidate_id,
                "candidate_name": candidate_name,
                "version_number": version_number,
                "chunk_type": "project",
                "project_index": project_index,
                "part_index": part_index,
            }
            chunks.append({"text": sub_text, "metadata": metadata})

    return chunks


def build_chunks_for_version(
    candidate_doc: dict,
    version: dict,
    tokenizer,
    max_tokens_by_type: dict = None,
) -> list[dict]:
    """Orchestrate all chunk builders for a single CV version, return the full list of chunks."""
    max_tokens_by_type = max_tokens_by_type or MAX_TOKENS_BY_TYPE

    candidate_id = str(candidate_doc["_id"])
    candidate_name = candidate_doc.get("name")
    version_number = version.get("version_number")
    structured = version.get("structured", {})

    all_chunks = []

    all_chunks.extend(build_section_chunks(
        structured_data=structured,
        candidate_id=candidate_id,
        candidate_name=candidate_name,
        version_number=version_number,
        tokenizer=tokenizer,
        max_tokens_by_type=max_tokens_by_type,
    ))

    all_chunks.extend(build_experience_chunks(
        experience_list=structured.get("experience", []),
        candidate_id=candidate_id,
        candidate_name=candidate_name,
        version_number=version_number,
        tokenizer=tokenizer,
        max_tokens=resolve_max_tokens("experience", max_tokens_by_type),
    ))

    all_chunks.extend(build_project_chunks(
        project_list=structured.get("projects", []),
        candidate_id=candidate_id,
        candidate_name=candidate_name,
        version_number=version_number,
        tokenizer=tokenizer,
        max_tokens=resolve_max_tokens("project", max_tokens_by_type),
    ))

    return all_chunks


