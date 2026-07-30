"""
app/profiling/profile_builder.py

Takes the output of detect_profiles_full() (or the local variant) and builds
a new document per candidate, structured like the original candidate document
but with "profiles" instead of "versions". Each profile carries:
  - its own matched experience/project entries (via the refs from the detector)
  - static sections (summary, skills, expertise_areas, etc.) MERGED/deduped
    across every version_number touched by that profile's refs

Stored in a separate Mongo collection ("candidate_profiles"), never mutates
the original "candidates" collection.
"""

import json
from pymongo.collection import Collection

STATIC_LIST_FIELDS = [
    "expertise_areas",
    "functional_skills",
    "education",
    "certifications",
    "languages",
]
STATIC_FLAT_LIST_FIELDS = [
    "skills",
    "countries_worked",
    "professional_affiliations",
]


def _dedupe_dict_list(items: list[dict]) -> list[dict]:
    """Dedupe a list of dicts by their normalized JSON representation, preserving first-seen order."""
    seen = set()
    result = []
    for item in items:
        key = json.dumps(item, sort_keys=True, ensure_ascii=False)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _dedupe_flat_list(items: list[str]) -> list[str]:
    """Dedupe a list of strings, preserving first-seen order."""
    seen = set()
    result = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _merge_languages(items: list[dict]) -> list[dict]:
    """
    Languages dedupe by language name specifically (not full dict equality),
    since the same language can appear with a null level in one version and
    a real level in another -- keep the most informative entry.
    """
    by_language: dict[str, dict] = {}
    for item in items:
        lang = item.get("language")
        if not lang:
            continue
        existing = by_language.get(lang)
        if existing is None or (not existing.get("level") and item.get("level")):
            by_language[lang] = item
    return list(by_language.values())


def _merge_summary(summaries: list[str]) -> str | None:
    """
    Dedupe distinct non-empty summaries. If more than one distinct summary
    remains (different versions genuinely wrote different summaries), join
    them rather than silently dropping one -- keeps the field a plain string
    so downstream code doesn't need to handle summary being sometimes a list.
    """
    distinct = []
    seen = set()
    for s in summaries:
        s = (s or "").strip()
        if s and s not in seen:
            seen.add(s)
            distinct.append(s)
    if not distinct:
        return None
    if len(distinct) == 1:
        return distinct[0]
    return " | ".join(distinct)


def merge_static_sections(candidate_doc: dict, version_numbers: set) -> dict:
    """
    Merge/dedupe static sections (summary, skills, expertise_areas, etc.)
    across every version in `version_numbers`. Never touches experience/projects.
    """
    versions = [
        v for v in candidate_doc.get("versions", [])
        if v["version_number"] in version_numbers
    ]

    merged = {}

    merged["summary"] = _merge_summary(
        [v.get("structured", {}).get("summary") for v in versions]
    )

    for field in STATIC_LIST_FIELDS:
        combined = []
        for v in versions:
            combined.extend(v.get("structured", {}).get(field) or [])
        if field == "languages":
            merged[field] = _merge_languages(combined)
        else:
            merged[field] = _dedupe_dict_list(combined)

    for field in STATIC_FLAT_LIST_FIELDS:
        combined = []
        for v in versions:
            combined.extend(v.get("structured", {}).get(field) or [])
        merged[field] = _dedupe_flat_list(combined)

    return merged


def _get_entry(candidate_doc: dict, section: str, ref: dict):
    """Fetch a single experience/project dict by (version_number, index). Returns None if out of range."""
    version_number = ref.get("version_number")
    index = ref.get("index")
    version = next(
        (v for v in candidate_doc.get("versions", []) if v["version_number"] == version_number),
        None,
    )
    if version is None:
        return None
    items = version.get("structured", {}).get(section, [])
    if index is None or index >= len(items):
        return None
    return items[index]


def build_profiles_document(candidate_doc: dict, detection_result: dict) -> dict:
    """
    Build the full "candidate_profiles" document for one candidate, from the
    raw candidate doc + the {"profiles": [...]} output of detect_profiles_full().
    """
    profiles_out = []

    for profile in detection_result.get("profiles", []):
        exp_refs = profile.get("experience_refs", [])
        proj_refs = profile.get("project_refs", [])

        version_numbers = {r["version_number"] for r in exp_refs + proj_refs}
        merged_static = merge_static_sections(candidate_doc, version_numbers)

        matched_experience = [
            e for e in (_get_entry(candidate_doc, "experience", r) for r in exp_refs) if e is not None
        ]
        matched_projects = [
            p for p in (_get_entry(candidate_doc, "projects", r) for r in proj_refs) if p is not None
        ]

        profiles_out.append({
            "profile_name": profile.get("profile_name"),
            "source_versions": sorted(version_numbers),
            "structured": {
                **merged_static,
                "experience": matched_experience,
                "projects": matched_projects,
            },
        })

    return {
        "candidate_id": str(candidate_doc["_id"]),
        "name": candidate_doc.get("name"),
        "normalized_name": candidate_doc.get("normalized_name"),
        "email": candidate_doc.get("email"),
        "profiles": profiles_out,
    }


def store_candidate_profiles(collection: Collection, profiles_doc: dict) -> None:
    """
    Upsert into the candidate_profiles collection, keyed on candidate_id.
    Overwrites any previously stored profiles for this candidate (profile
    detection is meant to be re-run when the source CV changes, not appended to).
    """
    collection.update_one(
        {"candidate_id": profiles_doc["candidate_id"]},
        {"$set": profiles_doc},
        upsert=True,
    )