# file: auto_normalize_skills.py
"""
Fully automatic skill normalization pass, no manual pair-by-pair review:

  1. Casing normalization (CANONICAL_CASING + local, same as production).
  2. Embed every remaining distinct value with the shared SBERT model,
     cluster them via Union-Find on cosine similarity >= AUTO_MERGE_THRESHOLD
     (default 0.95, deliberately conservative -- most of the "related but
     distinct" false positives seen in the review report score below this).
  3. Safety guard: never merge two values whose extracted numeric
     identifiers differ (e.g. "ISO 27001" vs "ISO 27002", "27001" vs
     "27005") -- these scored 0.95-0.98 in testing despite being different
     standards. Values with no digits, or with the same digits, aren't
     affected by this guard.
  4. Rewrite the AUTO_ALIASES block in
     app/normalize_sections/normalize_skills.py with the resulting mapping
     (fully regenerated each run -- MANUAL_ALIASES and CANONICAL_CASING are
     untouched, they stay human-curated).
  5. Backfill candidatesV2 and merged_candidates with the new mapping.

This trades away per-pair human review for full automation, as requested --
be aware the numeric-identifier guard does not catch every risky case (e.g.
two skills at different granularity with no numbers in either label can
still merge if they cross the threshold). Spot-check AUTO_ALIASES
periodically even though it's applied without review.

Usage:
    python auto_normalize_skills.py
"""

import os
import re

import numpy as np
from pymongo import MongoClient
from dotenv import load_dotenv

from app.embedding.embedder import get_shared_embedder
from app.normalize_sections.normalize_skills import normalize_casing, CANONICAL_CASING

load_dotenv()
mongo_uri = os.getenv("MONGO_URI")
client = MongoClient(mongo_uri)
db = client["cv_platform"]
candidates_collection = db["candidatesV2"]
merged_candidates_collection = db["merged_candidates"]

AUTO_MERGE_THRESHOLD = 0.95

NORMALIZE_SKILLS_MODULE_PATH = os.path.join(
    "app", "normalize_sections", "normalize_skills.py"
)


# ---------------------------------------------------------------------------
# Step 1 -- casing normalization (reuse the same logic the pipeline uses)
# ---------------------------------------------------------------------------

def apply_casing(raw_values: list[str]) -> list[str]:
    local_map = normalize_casing(raw_values)
    resolved = []
    for v in raw_values:
        cased = CANONICAL_CASING.get(v.lower()) or local_map.get(v, v)
        resolved.append(cased)
    return sorted(set(resolved))


# ---------------------------------------------------------------------------
# Step 2-3 -- embedding clustering with the numeric-identifier guard
# ---------------------------------------------------------------------------

_DIGIT_RE = re.compile(r"\d+")


def _numeric_identifiers(value: str) -> set[str]:
    return set(_DIGIT_RE.findall(value))


def _safe_to_merge(a: str, b: str) -> bool:
    """False if both values contain numeric identifiers and those differ
    (protects distinct standards/versions like ISO 27001 vs ISO 27002)."""
    ids_a, ids_b = _numeric_identifiers(a), _numeric_identifiers(b)
    if ids_a and ids_b and ids_a != ids_b:
        return False
    return True


def cluster_by_embedding(values: list[str], threshold: float = AUTO_MERGE_THRESHOLD) -> dict[str, str]:
    """
    Union-Find clustering on cosine similarity >= threshold, skipping pairs
    blocked by the numeric-identifier guard. Returns {value: canonical} for
    every value that got merged into a cluster with more than one member
    (values with no match map to themselves and are omitted from the result,
    since normalize_skill_list already leaves unmatched values as-is).
    """
    embedder = get_shared_embedder()
    vectors = embedder.model.encode(values, convert_to_numpy=True, show_progress_bar=False)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1
    normed = vectors / norms
    similarity_matrix = normed @ normed.T

    parent = list(range(len(values)))

    def find(i):
        if parent[i] != i:
            parent[i] = find(parent[i])
        return parent[i]

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    merge_log = []
    n = len(values)
    for i in range(n):
        for j in range(i + 1, n):
            score = float(similarity_matrix[i, j])
            if score < threshold:
                continue
            if not _safe_to_merge(values[i], values[j]):
                print(f"  [skipped, numeric mismatch] '{values[i]}' <-> '{values[j]}' (score={score:.2f})")
                continue
            union(i, j)
            merge_log.append((values[i], values[j], score))

    clusters: dict[int, list[str]] = {}
    for idx in range(n):
        root = find(idx)
        clusters.setdefault(root, []).append(values[idx])

    print(f"\n{len(merge_log)} pair(s) auto-merged (threshold >= {threshold}):")
    for a, b, score in sorted(merge_log, key=lambda m: -m[2]):
        print(f"  [{score:.2f}] '{a}' <-> '{b}'")

    mapping: dict[str, str] = {}
    for members in clusters.values():
        if len(members) <= 1:
            continue
        # Canonical = shortest label (usually the least redundant phrasing);
        # ties broken alphabetically for determinism.
        canonical = sorted(members, key=lambda v: (len(v), v))[0]
        for m in members:
            if m != canonical:
                mapping[m] = canonical

    return mapping


# ---------------------------------------------------------------------------
# Step 4 -- rewrite the AUTO_ALIASES block in the production module
# ---------------------------------------------------------------------------

def rewrite_auto_aliases_block(mapping: dict[str, str]) -> None:
    with open(NORMALIZE_SKILLS_MODULE_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    start_marker = "AUTO_ALIASES: dict[str, str] = {"
    end_marker = "\n}\n# --- end AUTO_ALIASES ---"

    start_idx = content.index(start_marker) + len(start_marker)
    end_idx = content.index(end_marker)

    body_lines = [f'    "{raw}": "{canonical}",' for raw, canonical in sorted(mapping.items())]
    new_body = "\n" + "\n".join(body_lines) + "\n" if body_lines else "\n"

    new_content = content[:start_idx] + new_body + content[end_idx:]

    with open(NORMALIZE_SKILLS_MODULE_PATH, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"\nAUTO_ALIASES rewritten in {NORMALIZE_SKILLS_MODULE_PATH} ({len(mapping)} entries).")


# ---------------------------------------------------------------------------
# Step 5 -- backfill (re-import after rewrite so the new AUTO_ALIASES is used)
# ---------------------------------------------------------------------------

def backfill_database() -> None:
    import importlib
    import app.normalize_sections.normalize_skills as skills_module
    importlib.reload(skills_module)
    normalize_skill_list = skills_module.normalize_skill_list

    updated_v2 = 0
    for candidate in candidates_collection.find({"versions.structured.skills": {"$exists": True}}):
        versions = candidate.get("versions", [])
        changed = False
        for version in versions:
            structured = version.get("structured", {})
            raw_skills = structured.get("skills")
            if not raw_skills:
                continue
            normalized = normalize_skill_list(raw_skills)
            if normalized != raw_skills:
                structured["skills"] = normalized
                changed = True
        if changed:
            candidates_collection.update_one({"_id": candidate["_id"]}, {"$set": {"versions": versions}})
            updated_v2 += 1

    updated_merged = 0
    for doc in merged_candidates_collection.find({"skills": {"$exists": True}}):
        raw_skills = doc.get("skills")
        if not raw_skills:
            continue
        normalized = normalize_skill_list(raw_skills)
        if normalized != raw_skills:
            merged_candidates_collection.update_one({"_id": doc["_id"]}, {"$set": {"skills": normalized}})
            updated_merged += 1

    print(f"\n[Backfill] candidatesV2: {updated_v2} candidate(s) updated")
    print(f"[Backfill] merged_candidates: {updated_merged} candidate(s) updated")


def main():
    raw_values = sorted(v for v in merged_candidates_collection.distinct("skills") if v)
    print(f"{len(raw_values)} raw value(s)")

    after_casing = apply_casing(raw_values)
    print(f"After casing normalization: {len(after_casing)} distinct value(s)")

    print(f"\nClustering by embedding similarity (threshold >= {AUTO_MERGE_THRESHOLD})...")
    mapping = cluster_by_embedding(after_casing)

    rewrite_auto_aliases_block(mapping)
    backfill_database()

    final_count = len(after_casing) - len(mapping)
    print(f"\nDone. {len(raw_values)} -> {final_count} distinct skill(s) after full normalization.")


if __name__ == "__main__":
    main()