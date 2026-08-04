"""
Quick test to verify that is_candidate_relevant_v2 uses all selected sections
dynamically instead of only the static 3 (summary, experience, project).
"""
import os
from dotenv import load_dotenv
from pymongo import MongoClient

from app.embedding.embedder import Embedder
from app.embedding.vector_store import VectorStore
from app.generation.cv_json_builder import (
    is_candidate_relevant_v2,
    select_search_sections,
    distance_to_score,
)
from app.config import PASS_A_SECTION_THRESHOLDS

load_dotenv()

mongo_client = MongoClient(os.getenv("MONGO_URI"))
db = mongo_client["cv_platform"]
candidates_collection = db["candidates"]

MISSION_TEXT = (
    "We are looking for an experienced Project Manager to lead the end-to-end delivery of "
    "digital transformation initiatives. You will be responsible for planning and coordinating "
    "project scope, budget, and timelines, managing stakeholders and steering committees, "
    "overseeing cross-functional teams, tracking risks and deliverables, and ensuring projects "
    "are delivered on time and within budget. Strong experience in project governance, "
    "planning methodologies (Agile/Waterfall), and coordination with software vendors and "
    "technical teams is required."
)

candidate = candidates_collection.find_one({"normalized_name": "amira bensoltane"})
if not candidate:
    print("Candidate not found")
    exit(1)

candidate_id = str(candidate["_id"])
versions = candidate.get("versions", [])
if not versions:
    print("No versions")
    exit(1)

latest_version = versions[-1]
structured = latest_version.get("structured", {})

print("=" * 70)
print("DYNAMIC SECTION SELECTION TEST")
print("=" * 70)

all_possible_sections = [
    "summary", "skills", "expertise_areas", "functional_skills",
    "education", "languages", "certifications",
    "countries_worked", "professional_affiliations",
    "experience", "project",
]

selected = select_search_sections(structured, all_possible_sections)
print(f"\nCandidate: {candidate.get('name')} (v{latest_version['version_number']})")
print(f"Total possible sections: {len(all_possible_sections)}")
print(f"Selected sections (has content): {len(selected)}")
for section in selected:
    value = structured.get(section)
    if section in ("expertise_areas", "functional_skills", "skills"):
        from app.generation.cv_json_builder import compute_list_section_richness
        richness = compute_list_section_richness(section, value or [])
        print(f"  - {section}: {len(value or [])} items, richness={richness:.1f}")
    else:
        val_str = str(value) if value else ""
        print(f"  - {section}: {len(val_str)} chars")

print("\n" + "=" * 70)
print("RELEVANCE CHECK (dynamic sections)")
print("=" * 70)

embedder = Embedder()
store = VectorStore()
query_vec = embedder.model.encode(MISSION_TEXT).tolist()

for version in versions:
    version_number = version["version_number"]
    structured_v = version.get("structured", {})
    selected_v = select_search_sections(structured_v, all_possible_sections)

    is_rel, avg_score = is_candidate_relevant_v2(
        store=store,
        query_vec=query_vec,
        candidate_id=candidate_id,
        version_number=version_number,
        structured=structured_v,
    )

    print(f"\nv{version_number}: relevant={is_rel}, avg_score={avg_score:.1f}%")
    print(f"  Sections checked: {selected_v}")
    for section in selected_v:
        threshold = PASS_A_SECTION_THRESHOLDS.get(section, 0.8)
        res = store.search_section(
            query_vec, chunk_types=section, candidate_id=candidate_id,
            version_number=version_number, distance_threshold=threshold,
            min_results=0, max_results=3,
        )
        if res:
            best = max(distance_to_score(r["distance"]) for r in res)
            print(f"    {section}: best_score={best:.1f}% (threshold={threshold})")
        else:
            print(f"    {section}: no results (threshold={threshold})")

print("\n" + "=" * 70)
print("RELEVANCE CHECK (OLD static 3 sections only)")
print("=" * 70)

for version in versions:
    version_number = version["version_number"]
    is_rel, avg_score = is_candidate_relevant_v2(
        store=store,
        query_vec=query_vec,
        candidate_id=candidate_id,
        version_number=version_number,
        structured=None,
        section_thresholds={
            "summary": 0.6,
            "experience": 0.35,
            "project": 0.5,
        },
    )
    print(f"\nv{version_number}: relevant={is_rel}, avg_score={avg_score:.1f}%")
