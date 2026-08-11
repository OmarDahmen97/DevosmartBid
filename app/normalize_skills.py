# file: normalize_skills.py
"""
Offline review tool for skill near-duplicates. Reuses the casing
normalization and MANUAL_ALIASES from app.normalize_sections.normalize_skills
(the single source of truth, also used by the extraction pipeline) and adds
the expensive part -- embedding-based candidate pair detection -- which is
NOT run at extraction time, only here, occasionally, to help grow
MANUAL_ALIASES.

  1. CASING NORMALIZATION (automatic, safe) -- same as the pipeline uses.

  2. EMBEDDING-BASED NEAR-DUPLICATE DETECTION (semi-automatic, requires
     validation) -- uses the same SBERT model as the rest of the pipeline
     (via the shared singleton) to catch synonyms phrased differently,
     which fuzzy matching alone would miss ("Agile Scrum" / "Scrum
     methodology"). Always shown for review, NEVER merged automatically.

     Embeddings are BETTER than fuzzy matching at surfacing candidates
     (higher recall), but NOT more reliable at deciding alone: two skills
     related to the same theme ("BCP Strategy" / "BCP/DRP" / "BIA") will
     have high semantic similarity without being the same skill. Each pair
     therefore shows TWO scores -- embedding AND fuzzy -- to help you
     judge: a pair with high embedding but low fuzzy score is flagged as
     riskier (thematic closeness, not necessarily lexical).

After reviewing the report, add confirmed synonyms directly to
MANUAL_ALIASES in app/normalize_sections/normalize_skills.py -- that's the
one place the extraction pipeline reads from.

Usage:
    python normalize_skills.py
"""

import os

import numpy as np
from pymongo import MongoClient
from dotenv import load_dotenv
from rapidfuzz import fuzz

from app.embedding.embedder import get_shared_embedder
from normalize_skills import normalize_casing, MANUAL_ALIASES

load_dotenv()
mongo_uri = os.getenv("MONGO_URI")
client = MongoClient(mongo_uri)
db = client["cv_platform"]
merged_candidates = db["merged_candidates"]


# Cosine similarity threshold above which a pair is considered "candidate".
# Deliberately high (0.80) to limit noise -- even at this level, some pairs
# will be thematically close without being identical; that's what the
# fuzzy_score column and your judgment are for.
EMBEDDING_THRESHOLD = 0.80

# Below this fuzzy score, a pair with high embedding similarity is flagged
# as riskier: the closeness comes from general meaning/theme, not an
# obvious rewording of the same label.
FUZZY_RISK_THRESHOLD = 60


def find_near_duplicate_candidates_embeddings(
    values: list[str], threshold: float = EMBEDDING_THRESHOLD
) -> list[tuple[str, str, float, int]]:
    """
    Embed every value with the shared SBERT model, compute pairwise cosine
    similarity, and return candidate pairs above `threshold` along with
    their fuzzy score for cross-reference. Purely diagnostic -- nothing is
    merged here.
    """
    embedder = get_shared_embedder()
    vectors = embedder.model.encode(values, convert_to_numpy=True, show_progress_bar=False)

    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1  # avoid division by zero on empty/degenerate strings
    normed = vectors / norms
    similarity_matrix = normed @ normed.T

    candidates = []
    n = len(values)
    for i in range(n):
        for j in range(i + 1, n):
            score = float(similarity_matrix[i, j])
            if score >= threshold:
                fuzzy_score = fuzz.token_sort_ratio(values[i], values[j])
                candidates.append((values[i], values[j], score, fuzzy_score))

    candidates.sort(key=lambda c: -c[2])
    return candidates


def main():
    raw_values = sorted(v for v in merged_candidates.distinct("skills") if v)
    print(f"{len(raw_values)} raw value(s)\n")

    # Step 1
    casing_map = normalize_casing(raw_values)
    after_casing = sorted(set(casing_map.values()))
    print(f"[Step 1] After casing normalization: {len(after_casing)} distinct value(s)")
    changed = {k: v for k, v in casing_map.items() if k != v}
    if changed:
        print("  Casing changes applied:")
        for raw, canonical in sorted(changed.items()):
            print(f"    {raw}  ->  {canonical}")

    # Step 1 + already-validated manual aliases (from the pipeline's module)
    if MANUAL_ALIASES:
        after_aliases = sorted({MANUAL_ALIASES.get(v, v) for v in after_casing})
        print(f"\n[Manual aliases] After applying MANUAL_ALIASES: {len(after_aliases)} distinct value(s)")

    # Step 2 -- embedding-based review report (changes nothing)
    print(f"\n[Step 2] Searching for near-duplicates via embeddings (cosine threshold >= {EMBEDDING_THRESHOLD})")
    print("         among the remaining values... (report only, no automatic merging)\n")
    candidates = find_near_duplicate_candidates_embeddings(after_casing)

    if not candidates:
        print("No suspicious pair found.")
    else:
        for a, b, embed_score, fuzzy_score in candidates:
            risk_flag = " ⚠ needs review (thematic closeness, different phrasing)" \
                if fuzzy_score < FUZZY_RISK_THRESHOLD else ""
            print(f"  [embed={embed_score:.2f} | fuzzy={fuzzy_score}] '{a}'  <->  '{b}'{risk_flag}")


if __name__ == "__main__":
    main()