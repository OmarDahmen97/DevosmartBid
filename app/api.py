# file: app/api.py
"""
app/api.py

FastAPI layer over the CV platform pipeline. Two main flows:

1. Upload  -> POST /cv/upload (single or multiple files). Each file is
   extracted, stored as a new version in candidatesV2 (or flagged duplicate),
   then merged into merged_candidates automatically.

2. Mission matching + selection ->
   POST /candidates/match           mission text -> relevant candidates (id, name, score)
   GET  /candidates                 non-semantic search: by name and/or section filter
   GET  /candidates/filters/{section}  distinct values for a section, to populate a dropdown
   GET  /candidates/{candidate_id}  full consolidated candidate detail
   POST /cv/{candidate_id}/experiences-ranked  experiences/projects ranked by
        similarity to a mission, each with a score and an auto_selected flag
   POST /generation/cv              stub -- template generation not implemented yet
"""

from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Query
from pydantic import BaseModel
import shutil
import tempfile
import os

from app.extraction.pipeline import extract_and_store_cv
from app.generation.cv_json_builder import get_ranked_experiences, get_ranked_projects
from app.main_usage import (
    candidates_collection,
    merged_candidates_collection,
    sync_merged_candidate,
    index_merged_candidate,
    get_embedder,
    get_store,
    run_mission_matching,
    get_candidate_detail,
    get_distinct_section_values,
    search_candidates,
    delete_candidate,
    generate_cv_from_selection,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load SBERT (Embedder) and Chroma (VectorStore) once at startup, so the
    # first real request isn't the one paying for the model load time.
    # get_embedder()/get_store() are already singletons -- calling them here
    # just makes the loading happen eagerly instead of lazily.
    print("[startup] Chargement du modèle SBERT et de ChromaDB...")
    get_embedder()
    get_store()
    print("[startup] Prêt.")
    yield


app = FastAPI(title="CV Platform API", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class MissionRequest(BaseModel):
    mission_text: str


class SelectedCandidate(BaseModel):
    candidate_id: str
    selected_experience_indices: list[int] = []
    selected_project_indices: list[int] = []


class GenerationRequest(BaseModel):
    candidates: list[SelectedCandidate]


# ---------------------------------------------------------------------------
# 1. Upload
# ---------------------------------------------------------------------------

def _store_and_merge_one(tmp_path: str, original_filename: str) -> dict:
    """Extract + store one CV file, then sync its merged view. Errors are
    caught per-file so one bad file in a batch upload doesn't fail the rest."""
    try:
        candidate = extract_and_store_cv(tmp_path, candidates_collection=candidates_collection)
        candidate_id = str(candidate["_id"])

        merged = sync_merged_candidate(candidate_id)

        return {
            "filename": original_filename,
            "candidate_id": candidate_id,
            "name": candidate.get("name"),
            "email": candidate.get("email"),
            "status": candidate.get("_pipeline_status"),
            "version": candidate.get("_pipeline_version"),
            "experience_count_after_merge": len(merged.get("experience", [])) if merged else 0,
        }
    except Exception as e:
        return {"filename": original_filename, "error": f"{type(e).__name__}: {e}"}


@app.post("/cv/upload-single")
async def upload_cv_single(file: UploadFile = File(...)):
    """Single-file variant of /cv/upload, kept for convenient Swagger UI testing
    (Swagger UI doesn't render array-of-file fields as a file picker)."""
    suffix = os.path.splitext(file.filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    result = _store_and_merge_one(tmp_path, file.filename)
    os.remove(tmp_path)
    return result


@app.post("/cv/upload")
async def upload_cv(files: list[UploadFile] = File(...)):
    """
    Upload one or more CV files. Each is extracted and stored as a new
    version (or flagged as a duplicate) in candidatesV2, then automatically
    merged into merged_candidates if it introduces new experiences.
    """
    results = []

    for file in files:
        suffix = os.path.splitext(file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        results.append(_store_and_merge_one(tmp_path, file.filename))
        os.remove(tmp_path)

    return {"results": results}


# ---------------------------------------------------------------------------
# 2. Mission matching
# ---------------------------------------------------------------------------

@app.post("/candidates/match")
async def match_mission(request: MissionRequest):
    """
    Scan every stored candidate against the mission text, return the
    relevant ones (candidate_id, name, email, avg_score), sorted by score
    descending. The front-end pre-selects all of them and lets the user
    deselect / add more via search or filters.
    """
    relevant = run_mission_matching(request.mission_text)
    return {"candidates": relevant}


# ---------------------------------------------------------------------------
# 2a. Non-semantic search / filters, to add candidates outside the mission match
# ---------------------------------------------------------------------------

@app.get("/candidates")
async def list_candidates(
    name: Optional[str] = Query(None, description="Case-insensitive substring match on candidate name"),
    section: Optional[str] = Query(None, description="Section to filter on, e.g. 'skills'"),
    values: Optional[str] = Query(None, description="Comma-separated values to match in that section"),
):
    """
    Non-semantic candidate search, used to add candidates to the selection
    outside of mission matching: by name, and/or by exact membership in a
    flat-list section (skills, countries_worked, professional_affiliations).
    """
    value_list = [v.strip() for v in values.split(",")] if values else None

    try:
        candidates = search_candidates(name=name, section=section, values=value_list)
    except ValueError as e:
        return {"error": str(e)}

    return {"candidates": candidates}


@app.get("/candidates/filters/{section}")
async def get_section_filter_values(section: str):
    """
    Distinct values for a flat-list section, to populate a dropdown filter
    (e.g. every distinct skill across all candidates).
    """
    try:
        values = get_distinct_section_values(section)
    except ValueError as e:
        return {"error": str(e)}

    return {"section": section, "values": values}


@app.get("/candidates/{candidate_id}")
async def get_candidate(candidate_id: str):
    """Full consolidated (merged) candidate document: static sections + all experiences/projects."""
    candidate = get_candidate_detail(candidate_id)
    if not candidate:
        return {"error": f"Aucun candidat trouvé pour candidate_id='{candidate_id}'"}
    return candidate


@app.delete("/candidates/{candidate_id}")
async def delete_candidate_endpoint(candidate_id: str):
    """
    Delete a candidate entirely -- candidatesV2, merged_candidates, and all
    of their indexed Chroma chunks. Irreversible.
    """
    try:
        result = delete_candidate(candidate_id)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
    return result


# ---------------------------------------------------------------------------
# 2b. Per-candidate ranked experiences (review / manual adjustment step)
# ---------------------------------------------------------------------------

@app.post("/cv/{candidate_id}/experiences-ranked")
async def get_ranked_experiences_and_projects(candidate_id: str, request: MissionRequest):
    """
    Every experience/project for this candidate, ranked by similarity to
    the mission, each with its score (0-100%) and an auto_selected flag
    (pre-checked in the UI if True). The user adjusts the selection before
    generating the final CV.
    """
    merged = sync_merged_candidate(candidate_id)
    if not merged:
        return {"error": f"Candidat introuvable pour candidate_id='{candidate_id}'"}

    index_merged_candidate(merged)

    query_vec = get_embedder().model.encode(request.mission_text).tolist()
    store = get_store()

    experiences = get_ranked_experiences(store, merged_candidates_collection, candidate_id, query_vec)
    projects = get_ranked_projects(store, merged_candidates_collection, candidate_id, query_vec)

    return {"experiences": experiences, "projects": projects}


# ---------------------------------------------------------------------------
# 3. CV generation (not implemented yet)
# ---------------------------------------------------------------------------

@app.post("/generation/cv")
async def generate_cv(request: GenerationRequest):
    """
    Generate the final CV(s) in template format from the user's confirmed
    candidate + experience/project selection. NOT YET IMPLEMENTED -- returns
    a stub response so the front-end can build and test its request format
    ahead of the real implementation.
    """
    return generate_cv_from_selection(request.model_dump())