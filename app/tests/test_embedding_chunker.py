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

#model = SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')
#tokenizer=model.tokenizer
load_dotenv()
mongo_uri = os.getenv("MONGO_URI")
client = MongoClient(mongo_uri)
db = client["cv_platform"]
candidates = db["candidates"]

candidate = candidates.find_one({"normalized_name": "imed ben hammouda"})
version = candidate["versions"][0]
experiences = version["structured"]["experience"]
projects=version["structured"]["projects"]




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


embedder = Embedder()
store = VectorStore()

chunks = build_chunks_for_version(candidate, version, tokenizer=embedder.model.tokenizer)
enriched = embedder.embed_chunks(chunks)
store.index_chunks(enriched)

# test search (Passe A — sans filtre)
query_vec = embedder.model.encode(["expert en Power BI et cloud"])[0].tolist()
results = store.search(query_vec, top_k=3)
print(results["metadatas"])