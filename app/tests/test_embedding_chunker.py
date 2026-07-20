# test_embedding_chunker.py
from pymongo import MongoClient
from dotenv import load_dotenv
import os
from app.embedding.embedding_chunker import (
    serialize_category_description_list,
    serialize_string_list,
    count_tokens,
    split_text_by_tokens,
    serialize_experience_to_text,
    build_experience_chunks,
    build_project_chunks,
    build_chunks_for_version,
    
)
from sentence_transformers import SentenceTransformer
from app.embedding.embedder import Embedder
from app.embedding.embedding_chunker import build_chunks_for_version
from app.embedding.embedder import Embedder
from app.embedding.embedding_chunker import build_chunks_for_version
from app.embedding.vector_store import VectorStore
from bson import ObjectId

#model = SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')
#tokenizer=model.tokenizer





#test serialize_category_description_list
"""test = [
    {"category": "Audit", "description": None},
    {"category": None, "description": "Quelque chose d'important"},
    {"category": None, "description": None},
]
print(serialize_category_description_list(test))"""

# test serialize_string_list
"""test = ["IFRS", "Assurances CIMA", "OHADA", "Normes Françaises"]
print(serialize_string_list(test))
# "IFRS, Assurances CIMA, OHADA, Normes Françaises"

print(serialize_string_list([]))"""

# test serialize_experience_to_text
"""for exp in experiences[0:5]:
    print(serialize_experience_to_text(exp))
    print("---")"""
# test split_text_by_tokens
"""functional_skills_yasmine_v1=functional_skills = [
    {"category": "Business & Technical Requirements Gathering", "description": "Expertise in conducting workshops and interviews to collect, analyze, and formalize business and technical needs."},
    {"category": "Documentation & Specifications", "description": "Skilled in developing functional and technical documentation that clearly articulates business needs, system behaviors, and data flows, supporting accurate implementation and project traceability."},
    {"category": "Prototyping & Interface Modeling", "description": "Develops interface mockups and prototypes to visualize system behavior, support requirement validation, and enhance user experience (UX)."},
    {"category": "Project Coordination & PMO Support", "description": "Coordinates tasks, monitors progress, and mitigates risks to ensure on-time, quality delivery."},
    {"category": "User Acceptance Testing (UAT)", "description": "Defines test scenarios and acceptance criteria, manages UAT execution, and validates solution conformity with business requirements and data integrity standards."},
    {"category": "Business Process Modeling & Optimization", "description": "Analyzes existing business workflows, identifies inefficiencies, and designs optimized to-be processes aligned with digital transformation goals."},
    {"category": "Stakeholder management", "description": "Facilitating collaboration between business and technical teams to ensure project alignment."},
]
long_text = serialize_category_description_list(functional_skills_yasmine_v1)  # le texte de tout à l'heure
print(count_tokens(long_text, tokenizer))  # vérifie que ça dépasse bien 128

sub_chunks = split_text_by_tokens(long_text, tokenizer, max_tokens=118, overlap=20)
print(len(sub_chunks))
for c in sub_chunks:
    print(count_tokens(c, tokenizer), "-", c[:80])"""
#test build_experience_chunks
"""chunks = build_experience_chunks(
    experience_list=experiences,
    candidate_id=str(candidate["_id"]),
    candidate_name=candidate["name"],
    version_number=version["version_number"],
    tokenizer=model.tokenizer,
)

print(len(chunks))
for c in chunks[:3]:
    print(c)
    print("---")"""
# test build_section_chunks
"""from app.embedding.embedding_chunker import build_section_chunks

chunks = build_section_chunks(
    structured_data=version["structured"],
    candidate_id=str(candidate["_id"]),
    candidate_name=candidate["name"],
    version_number=version["version_number"],
    tokenizer=tokenizer,
)

print(len(chunks))
for c in chunks:
    print(c["metadata"]["chunk_type"], "-", c["text"][:80])
    print("---")"""
# test build_project_chunks
"""chunks = build_project_chunks(
    project_list=projects,
    candidate_id=str(candidate["_id"]),
    candidate_name=candidate["name"],
    version_number=version["version_number"],
    tokenizer=tokenizer,
)

print(len(chunks))
for c in chunks[:5]:
    print(c)
    print("---")"""
# test build_chunks_for_version
"""chunks = build_chunks_for_version(candidate, version, tokenizer=tokenizer)

print(len(chunks))
print(chunks[9])"""

#test embedding :


"""embedder = Embedder()
chunks = build_chunks_for_version(
    candidate,
    version,
    tokenizer=embedder.model.tokenizer,  # réutilise le tokenizer déjà chargé
)
enriched = embedder.embed_chunks(chunks)
print(len(enriched))
print(len(enriched[0]["embedding"]))  # should be 768
print(enriched[0]["metadata"])"""

# test vector_store








def resolve_chunk_to_mongo_source(mongo_collection, metadata: dict) -> dict:
    """
    Given a chunk's metadata (from a Chroma search result), fetch the corresponding
    full structured object (experience, project, or section) from MongoDB.
    Returns the original structured data, not the serialized/truncated chunk text.
    """
    candidate = mongo_collection.find_one({"_id": ObjectId(metadata["candidate_id"])})
    if not candidate:
        return None

    version = next(
        (v for v in candidate["versions"] if v["version_number"] == metadata["version_number"]),
        None,
    )
    if not version:
        return None

    structured = version["structured"]
    chunk_type = metadata["chunk_type"]

    if chunk_type == "experience":
        experiences = structured.get("experience", [])
        idx = metadata["experience_index"]
        return experiences[idx] if idx < len(experiences) else None

    elif chunk_type == "project":
        projects = structured.get("projects", [])
        idx = metadata["project_index"]
        return projects[idx] if idx < len(projects) else None

    else:
        # section-level chunk_type (skills, summary, education, etc.)
        return structured.get(chunk_type)

# test search (Passe A — sans filtre)

#results = store.search(query_vec, top_k=3)
#print(results["metadatas"])

"""results = store.search_section(query_vec, chunk_types=["experience", "project"], candidate_id=candidate_id,
    distance_threshold=0.6, min_results=2, max_results=4
)


for r in results:
    print(round(r["distance"], 3), r["metadata"].get("company"))
    full_data = resolve_chunk_to_mongo_source(candidates, r["metadata"])
    print(full_data)
    print("---")"""


def print_matched_cv(mongo_collection, candidate_id: str, version_number: int, matched_results: list[dict]):
    """
    Affiche l'intégralité d'un CV depuis MongoDB en mettant en évidence les éléments 
    qui ont matché lors de la recherche vectorielle (fournis dans matched_results).
    Les sections non matchées ou absentes de Chroma s'affichent entièrement sans filtre.
    """
    candidate = mongo_collection.find_one({"_id": ObjectId(candidate_id)})
    if not candidate:
        print(f"[-] Candidat avec l'ID {candidate_id} introuvable.")
        return

    version = next(
        (v for v in candidate["versions"] if v["version_number"] == version_number),
        None,
    )
    if not version:
        print(f"[-] Version {version_number} introuvable pour ce candidat.")
        return

    structured = version.get("structured", {})

    matched_metadatas = [r["metadata"] for r in matched_results if "metadata" in r]

    matched_experience_indices = {
        m["experience_index"] for m in matched_metadatas if m.get("chunk_type") == "experience"
    }
    matched_project_indices = {
        m["project_index"] for m in matched_metadatas if m.get("chunk_type") == "project"
    }
    matched_sections = {
        m["chunk_type"] for m in matched_metadatas
        if m.get("chunk_type") not in ("experience", "project")
    }

    # count how many chunks were retrieved for each chunk_type (for display)
    chunk_counts = {}
    for m in matched_metadatas:
        chunk_type = m.get("chunk_type")
        chunk_counts[chunk_type] = chunk_counts.get(chunk_type, 0) + 1

    print("=" * 80)
    print(f"Profil Complet : {structured.get('name', 'Nom inconnu').upper()} (Version {version_number})")
    print(f"Total chunks matchés (toutes sections confondues) : {len(matched_metadatas)}")
    print("=" * 80)

    text_sections = {
        "summary": "RÉSUMÉ PROFESSIONNEL",
        "skills": "COMPÉTENCES GÉNÉRALES",
        "functional_skills": "COMPÉTENCES FONCTIONNELLES",
        "expertise_areas": "DOMAINES D'EXPERTISE",
        "certifications": "CERTIFICATIONS",
        "languages": "LANGUES",
        "education": "FORMATION / PARCOURS ACADÉMIQUE",
        "countries_worked": "PAYS D'EXPÉRIENCE",
        "professional_affiliations": "AFFILIATIONS PROFESSIONNELLES"
    }

    for key, label in text_sections.items():
        data = structured.get(key)
        if not data:
            continue

        is_match = key in matched_sections
        n_chunks = chunk_counts.get(key, 0)
        match_status = f"[🎯 MATCH VECTORIEL - {n_chunks} chunk(s)]" if is_match else "[ℹ️ COMPLÉMENTAIRE]"

        print(f"\n--- {label} {match_status} ---")

        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    if "language" in item:
                        print(f"• {item['language']} ({item.get('level', '')})")
                    elif "name" in item and "issuer" in item:
                        print(f"• {item['name']} - Délivré par {item['issuer']} ({item.get('year', '')})")
                    elif "category" in item and "description" in item:
                        print(f"• {item['category']} : {item['description']}")
                    elif "degree" in item:
                        print(f"• {item.get('degree')} en {item.get('field_of_study')} @ {item.get('institution')}")
                    else:
                        print(f"• {item}")
                else:
                    print(f"• {item}")
        else:
            print(data.strip())

    experiences = structured.get("experience", [])
    if experiences:
        n_exp_matched = chunk_counts.get("experience", 0)
        print(f"\n--- EXPÉRIENCES PROFESSIONNELLES ({n_exp_matched} chunk(s) matché(s)) ---")
        seen_exp_signatures = set()

        for idx, exp in enumerate(experiences):
            is_match = idx in matched_experience_indices
            match_status = "[🎯 MATCH]" if is_match else "[    ]"

            title = exp.get('title', 'Poste inconnu')
            company = exp.get('company', 'Entreprise inconnue')
            dates = exp.get('dates', 'Dates non spécifiées')

            signature = (title.lower().strip(), company.lower().strip())
            if signature in seen_exp_signatures:
                print(f"{match_status} [{idx}] (Doublon masqué) {title} @ {company}")
                continue
            seen_exp_signatures.add(signature)

            print(f"{match_status} [{idx}] {title} @ {company} ({dates})")
            if exp.get('description'):
                print(f"    Description: {exp['description']}")
            if exp.get('technologies'):
                print(f"    Technologies: {', '.join(exp['technologies'])}")
            print("    " + "-"*40)

    projects = structured.get("projects", [])
    if projects:
        n_proj_matched = chunk_counts.get("project", 0)
        print(f"\n--- PROJETS PARTICULIERS ({n_proj_matched} chunk(s) matché(s)) ---")
        for idx, proj in enumerate(projects):
            is_match = idx in matched_project_indices
            match_status = "[🎯 MATCH]" if is_match else "[    ]"

            if isinstance(proj, dict):
                print(f"{match_status} [{idx}] {proj.get('name', 'Projet sans nom')}")
                if proj.get('description'):
                    print(f"    Description: {proj['description']}")
                if proj.get('technologies'):
                    print(f"    Technologies: {', '.join(proj['technologies'])}")
            else:
                print(f"{match_status} [{idx}] {proj}")
            print("    " + "-"*40)

    print("\n" + "=" * 80)


    # Test the full CV printer



load_dotenv()
mongo_uri = os.getenv("MONGO_URI")
client = MongoClient(mongo_uri)
db = client["cv_platform"]
candidates = db["candidates"]

candidate = candidates.find_one({"normalized_name": "yasmine goubantini"})
version = candidate["versions"][1]
experiences = version["structured"]["experience"]
projects=version["structured"]["projects"]
candidate_id = str(candidate["_id"])


embedder = Embedder()
store = VectorStore()
store.delete_candidate_chunks(candidate_id, version_number=version["version_number"])
chunks = build_chunks_for_version(candidate, version, tokenizer=embedder.model.tokenizer)
enriched = embedder.embed_chunks(chunks)
store.index_chunks(enriched)

mission_text = """
We are seeking a Senior Enterprise Architect to drive the design and deployment of a large-scale, cloud-based Business Intelligence (BI) platform.
In this role, you will define the target architecture for multi-source data integration, implement robust ETL/ELT pipelines, and deploy BI tools (Power BI) across business teams. You will also oversee the migration to a cloud infrastructure (Azure or AWS), automate deployment workflows using CI/CD practices, and ensure data governance within a strict regulatory environment.
A proven track record in coaching and mentoring technical teams is highly desirable, as well as a strong command of MLOps challenges to industrialize data models.
"""
query_vec = embedder.model.encode([mission_text])[0].tolist()

"""section_types = [
    "summary", "skills", "education", "languages",
    "expertise_areas", "functional_skills", "certifications",
    "countries_worked", "professional_affiliations",
]

matched_metadatas = []

# summary — strict, un seul résultat suffit
res = store.search_section(
    query_vec, chunk_types="summary", candidate_id=candidate_id,
    distance_threshold=0.5, min_results=1, max_results=1
)
matched_metadatas.extend(res)

# skills — plus tolérant, un seul chunk de toute façon (une section = un chunk)
res = store.search_section(
    query_vec, chunk_types="skills", candidate_id=candidate_id,
    distance_threshold=0.7, min_results=1, max_results=2
)
matched_metadatas.extend(res)

# functional_skills — plus tolérant, un seul chunk de toute façon (une section = un chunk)
res = store.search_section(
    query_vec, chunk_types="functional_skills", candidate_id=candidate_id,
    distance_threshold=0.7, min_results=1, max_results=1
)
matched_metadatas.extend(res)


# education
res = store.search_section(
    query_vec, chunk_types="education", candidate_id=candidate_id,
    distance_threshold=0.7, min_results=1, max_results=1
)
matched_metadatas.extend(res)

# expertise_areas
res = store.search_section(
    query_vec, chunk_types="expertise_areas", candidate_id=candidate_id,
    distance_threshold=0.6, min_results=1, max_results=1
)
matched_metadatas.extend(res)

# experience + project — mélangés volontairement, plusieurs résultats
res = store.search_section(
    query_vec, chunk_types=["experience", "project"], candidate_id=candidate_id,
    distance_threshold=0.6, min_results=2, max_results=6
)
matched_metadatas.extend(res)

print_matched_cv(candidates, candidate_id, version["version_number"], matched_metadatas)"""


from app.generation.mongo_resolver import resolve_list_section_matches, resolve_chunk_to_mongo_source

# list-type sections (resolved via text-overlap matching)
LIST_TYPE_SECTIONS = ["expertise_areas", "functional_skills", "education", "languages", "certifications"]

# simple-value sections (resolved by taking the raw Mongo field directly)
SIMPLE_TYPE_SECTIONS = ["summary", "skills", "countries_worked", "professional_affiliations"]

for chunk_type in LIST_TYPE_SECTIONS:
    res = store.search_section(
        query_vec, chunk_types=chunk_type, candidate_id=candidate_id, version_number=version["version_number"],
        distance_threshold=0.7, min_results=1, max_results=1
    )
    print(f"\n=== {chunk_type.upper()} ===")
    for r in res:
        matched_items = resolve_list_section_matches(candidates, r["metadata"], r["text"])
        print("Chunk text:", r["text"])
        print(f"Matched {len(matched_items)} item(s):")
        for item in matched_items:
            print(" →", item)

for chunk_type in SIMPLE_TYPE_SECTIONS:
    res = store.search_section(
        query_vec, chunk_types=chunk_type, candidate_id=candidate_id, version_number=version["version_number"],
        distance_threshold=0.7, min_results=1, max_results=1
    )
    print(f"\n=== {chunk_type.upper()} ===")
    for r in res:
        value = resolve_chunk_to_mongo_source(candidates, r["metadata"])
        print("Chunk text:", r["text"])
        print("Resolved value:", value)

# experience + project — searched together, resolved by exact index
res = store.search_section(
    query_vec, chunk_types=["experience", "project"], candidate_id=candidate_id, version_number=version["version_number"],
    distance_threshold=0.6, min_results=2, max_results=6
)
print(f"\n=== EXPERIENCE + PROJECT ===")
for r in res:
    item = resolve_chunk_to_mongo_source(candidates, r["metadata"])
    print("Chunk text:", r["text"][:150])
    print("Resolved item:", item)
    print("---")

print('=' * 50)

"""from app.generation.cv_json_builder import build_matched_cv_json
import json

final_json = build_matched_cv_json(store, candidates, candidate_id, version["version_number"], query_vec)
print(json.dumps(final_json, indent=2, ensure_ascii=False))"""