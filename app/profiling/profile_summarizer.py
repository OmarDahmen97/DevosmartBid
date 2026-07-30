# app/profiling/profile_summarizer.py

"""
Condense a candidate's structured CV data down to the minimum needed to
detect distinct professional profiles (e.g. "BI Consultant", "Project
Manager") — titles, categories, and keywords only, never full descriptions.
This keeps the LLM classification call (profile_detector.py) small enough
to process all versions of a candidate in a single call.
"""


def summarize_experience_for_profiling(exp: dict, exp_index: int) -> dict:
    """
    Condense one experience down to just what's needed to detect a profile:
    title, company, dates, a short description snippet, and a short list of
    keywords (technologies + responsibility categories), never the full
    description paragraphs.
    """
    responsibilities = exp.get("responsibilities") or []
    resp_categories = [r.get("category") for r in responsibilities if r.get("category")]
    description = exp.get("description") or ""

    return {
        "index": exp_index,
        "title": exp.get("title"),
        "company": exp.get("company"),
        "dates": exp.get("dates"),
        "description_snippet": description[:120],
        "keywords": resp_categories[:5] + (exp.get("technologies") or [])[:5],
    }


def summarize_project_for_profiling(proj: dict, proj_index: int) -> dict:
    """Same idea as summarize_experience_for_profiling, but for projects."""
    description = proj.get("description") or ""
    return {
        "index": proj_index,
        "name": proj.get("name"),
        "description_snippet": description[:120],  # assez pour capter le type de travail, pas assez pour gonfler le prompt
        "keywords": (proj.get("technologies") or [])[:5],
    }

def summarize_cv_for_profiling(structured: dict) -> dict:
    """
    Build a compact representation of one CV version, keeping only what's
    needed to detect distinct professional profiles: titles, categories,
    and keywords — never full descriptions.
    """
    return {
        "summary_snippet": (structured.get("summary") or "")[:150],
        "expertise_categories": [
            item.get("category") for item in structured.get("expertise_areas", []) if item.get("category")
        ],
        "functional_categories": [
            item.get("category") for item in structured.get("functional_skills", []) if item.get("category")
        ],
        "skills": structured.get("skills", [])[:20],
        "experience": [
            summarize_experience_for_profiling(exp, i)
            for i, exp in enumerate(structured.get("experience", []))
        ],
        "projects": [
            summarize_project_for_profiling(proj, i)
            for i, proj in enumerate(structured.get("projects", []))
        ],
    }


def summarize_all_versions(candidate_doc: dict) -> list[dict]:
    """
    Summarize every version of a candidate's CV, ready to be sent to the
    profile detection LLM call in one shot.
    """
    return [
        {
            "version_number": v["version_number"],
            "summary": summarize_cv_for_profiling(v.get("structured", {})),
        }
        for v in candidate_doc.get("versions", [])
    ]