# file: app/merging/experience_similarity.py
"""Simple embedding-based approach to detect duplicate/same-mission
experiences across CV versions.

Each experience is serialized to text and embedded. A lightweight
company prefilter runs before the embedding comparison — without it,
missions at different clients under the same employer (e.g. two
different Devoteam client missions) score falsely high on text
similarity alone, since consulting mission descriptions share a lot
of generic vocabulary (methodology, governance, deliverables...).

Only experiences from DIFFERENT versions are compared — two
experiences within the same version are never candidates for merging,
since they already coexist as distinct entries on the same CV.
"""

import re

import numpy as np
from rapidfuzz.fuzz import token_set_ratio
from rapidfuzz import fuzz

from app.config import EMBEDDING_BATCH_SIZE
from app.embedding.embedder import Embedder
from difflib import SequenceMatcher

from bson import ObjectId
_embedder_instance = None


def _get_embedder() -> Embedder:
    """Lazy singleton — avoid reloading the SBERT model on every call."""
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = Embedder()
    return _embedder_instance


# ---- lightweight company prefilter (no fuzzy library dependency) ----

NULL_LIKE_VALUES = {
    "", None, "null",
    "non spécifié", "non specifie", "not specified", "n/a", "na",
    "none", "unspecified", "not available",
}

PUNCTUATION_RE = re.compile(r"[.,\-&()–/]")


def _normalize_company(raw: str | None) -> str | None:
    if raw is None or raw.strip().lower() in NULL_LIKE_VALUES:
        return None
    return PUNCTUATION_RE.sub(" ", raw.strip().lower())


def _companies_plausibly_match(raw_a: str | None, raw_b: str | None, threshold: float = 0.75) -> bool:
    """
    Checks if two company names plausibly match using a hybrid approach:
    1. Direct substring/token overlap (exact match, word sharing, inclusion)
    2. Fuzzy matching (Levenshtein/gestalt pattern matching via difflib) for typos/variations.

    Returns True if either name is None (can't rule it out).
    """
    a = _normalize_company(raw_a)
    b = _normalize_company(raw_b)

    if a is None or b is None:
        return True  # can't confidently rule out -> let embedding decide

    if not a or not b:
        return True

    # 1. Exact match or full containment (ex: "societe generale" vs "societe generale cib")
    if a == b or a in b or b in a:
        return True

    # 2. Token / Word level matching (exact shared words or substring matching on tokens)
    tokens_a = set(a.split())
    tokens_b = set(b.split())

    if tokens_a & tokens_b:  # Shared word (e.g., "devoteam")
        return True

    # 3. Fuzzy ratio on full string (captures typos e.g., "devoteam" vs "devoteam")
    ratio = fuzz.token_set_ratio(a, b)/100
    if ratio >= threshold:
        return True

    # 4. Fuzzy token matching (captures minor spelling mistakes inside individual words)
    for ta in tokens_a:
        for tb in tokens_b:
            # Ignore very short tokens (<= 2 chars) to avoid false positives on acronyms/stopwords
            if len(ta) > 2 and len(tb) > 2:
                if fuzz.token_set_ratio(ta, tb)/100 >= 0.85:
                    return True

    return False


# ---- text serialization ----

def serialize_experience_to_text(experience: dict) -> str:
    """
    Build a single text representation of an experience block. Company
    is deliberately excluded — it's handled separately as a prefilter,
    since burying it inside a long text blob makes it lose its weight
    as a discriminating signal.
    """
    parts = []

    title = experience.get("title")
    if title:
        parts.append(title)

    dates = experience.get("dates")
    if dates:
        parts.append(dates)

    description = experience.get("description")
    if description:
        parts.append(description)

    for resp in experience.get("responsibilities", []) or []:
        if isinstance(resp, dict):
            category = resp.get("category")
            desc = resp.get("description")
            if category:
                parts.append(category)
            if desc:
                parts.append(desc)
        elif isinstance(resp, str):
            parts.append(resp)

    deliverables = experience.get("deliverables", []) or []
    parts.extend(d for d in deliverables if isinstance(d, str) and d.strip())

    technologies = experience.get("technologies", []) or []
    parts.extend(t for t in technologies if isinstance(t, str) and t.strip())

    return " ".join(parts).strip()


# ---- embedding + similarity ----

def embed_experiences(experiences: list[dict]) -> list[np.ndarray]:
    texts = [serialize_experience_to_text(exp) for exp in experiences]
    embedder = _get_embedder()
    vectors = embedder.model.encode(
        texts,
        batch_size=EMBEDDING_BATCH_SIZE,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    return list(vectors)


def cosine_similarity(vector_a: np.ndarray, vector_b: np.ndarray) -> float:
    denom = np.linalg.norm(vector_a) * np.linalg.norm(vector_b)
    if denom == 0:
        return 0.0
    return float(np.dot(vector_a, vector_b) / denom)


def pairwise_similarities(
    experiences: list[dict], versions: list[int]
) -> list[tuple[int, int, float]]:
    """
    Returns (index_a, index_b, similarity) only for pairs that:
    - come from different versions (same-version pairs are never merge
      candidates)
    - pass the lightweight company prefilter

    `versions` must be the same length as `experiences`, giving the
    source version_number for each experience at the same index.
    """
    if len(experiences) != len(versions):
        raise ValueError("experiences and versions must have the same length")

    vectors = embed_experiences(experiences)
    results = []
    for i in range(len(vectors)):
        for j in range(i + 1, len(vectors)):
            if versions[i] == versions[j]:
                continue  # skip same-version pairs
            if not _companies_plausibly_match(
                experiences[i].get("company"), experiences[j].get("company")
            ):
                continue
            sim = cosine_similarity(vectors[i], vectors[j])
            results.append((i, j, sim))
    return results


DEFAULT_SIMILARITY_THRESHOLD = 0.82

def merge_and_deduplicate_experiences(
    cv_versions_structured: list[dict], threshold: float = DEFAULT_SIMILARITY_THRESHOLD
) -> list[dict]:
    flat_experiences: list[dict] = []
    flat_version_indices: list[int] = []

    # 1. Aplatir toutes les expériences
    for v_idx, structured in enumerate(cv_versions_structured):
        exps = structured.get("experience", []) or []
        for exp in exps:
            flat_experiences.append(exp)
            flat_version_indices.append(v_idx)

    if not flat_experiences:
        return []

    # 2. Calculer les similarités inter-versions
    pairs = pairwise_similarities(flat_experiences, flat_version_indices)
    matching_pairs = [(i, j, sim) for i, j, sim in pairs if sim >= threshold]

    # 3. Composantes connexes (Union-Find)
    parent = list(range(len(flat_experiences)))

    def find(i: int) -> int:
        if parent[i] == i:
            return i
        parent[i] = find(parent[i])
        return parent[i]

    def union(i: int, j: int):
        root_i, root_j = find(i), find(j)
        if root_i != root_j:
            parent[root_i] = root_j

    for i, j, _ in matching_pairs:
        union(i, j)

    clusters: dict[int, list[int]] = {}
    for idx in range(len(flat_experiences)):
        root = find(idx)
        clusters.setdefault(root, []).append(idx)

    # 4. Sélection de la meilleure version pour chaque groupe
    merged_experiences: list[dict] = []
    for cluster_indices in clusters.values():
        best_idx = max(
            cluster_indices,
            key=lambda idx: (
                flat_version_indices[idx],
                len(serialize_experience_to_text(flat_experiences[idx]))
            ),
        )
        merged_experiences.append(flat_experiences[best_idx])

    # 5. Garde-fou anti sur-fusion : si le résultat fusionné contient
    # moins d'expériences que la meilleure version prise seule, c'est
    # signe de faux positifs (deux missions différentes fusionnées à
    # tort). Dans ce cas on retombe sur les expériences de cette
    # version max plutôt que de risquer une perte de données.
    experiences_per_version: dict[int, list[dict]] = {}
    for exp, v_idx in zip(flat_experiences, flat_version_indices):
        experiences_per_version.setdefault(v_idx, []).append(exp)

    if experiences_per_version:
        max_version_idx = max(
            experiences_per_version, key=lambda v: len(experiences_per_version[v])
        )
        max_version_experiences = experiences_per_version[max_version_idx]

        if len(merged_experiences) < len(max_version_experiences):
            return max_version_experiences

    return merged_experiences


# ---- richest-version selection for non-experience sections ----
#
# Rather than always taking the latest version's value, each section is
# picked independently from whichever version carries the most information
# for that specific section. Richness is judged in two stages:
#   1. how many sub-fields are actually populated (e.g. both "category" and
#      "description" filled in, vs only one, vs empty)
#   2. total text length, used only to break ties on stage 1
#
# On an exact tie, the version that appears later in cv_versions_structured
# wins — preserving "prefer the latest version" as the final tiebreaker,
# consistent with the rest of the pipeline.

def _richness_scalar(value) -> tuple[int, int]:
    """Richness for a single scalar field (summary, phone, linkedin, github, email)."""
    if not value or not str(value).strip():
        return (0, 0)
    return (1, len(str(value)))


def _richness_dict_list(items: list) -> tuple[int, int]:
    """
    Richness for a list of sub-structured entries (expertise_areas,
    functional_skills, education, certifications, languages, projects).
    Stage 1 counts populated sub-fields across all entries (e.g. an entry
    with both category and description counts more than one with only
    category) — this is what makes a version "more complete" rather than
    just "longer". Stage 2 sums text length as the tiebreaker.
    """
    if not items:
        return (0, 0)

    populated_subfields = 0
    total_length = 0
    for item in items:
        if isinstance(item, dict):
            for value in item.values():
                if value not in (None, "", []):
                    populated_subfields += 1
                    total_length += len(str(value))
        elif item:
            populated_subfields += 1
            total_length += len(str(item))

    return (populated_subfields, total_length)


def _richness_string_list(items: list) -> tuple[int, int]:
    """Richness for a flat list of strings (skills, countries_worked, professional_affiliations)."""
    if not items:
        return (0, 0)
    return (len(items), sum(len(str(i)) for i in items))


def select_richest_section(cv_versions_structured: list[dict], field: str, richness_fn) -> object:
    """
    Scan every version's value for `field` and return the one richness_fn
    scores highest, using tuple comparison so stage 1 (sub-field
    completeness / element count) always outranks stage 2 (text length).
    """
    best_value = None
    best_score = (-1, -1)

    for structured in cv_versions_structured:
        value = structured.get(field)
        score = richness_fn(value)
        if score >= best_score:  # >= so the later version wins on exact ties
            best_score = score
            best_value = value

    return best_value


def merge_static_sections_by_richness(cv_versions_structured: list[dict]) -> dict:
    """
    Build the set of non-experience fields for the merged document, each
    picked independently from its richest source version.
    """
    scalar_fields = ["summary", "phone", "linkedin", "github", "email"]
    dict_list_fields = [
        "expertise_areas", "functional_skills",
        "education", "certifications", "languages", "projects",
    ]
    string_list_fields = ["skills", "countries_worked", "professional_affiliations"]

    merged = {}

    for field in scalar_fields:
        merged[field] = select_richest_section(cv_versions_structured, field, _richness_scalar)

    for field in dict_list_fields:
        merged[field] = select_richest_section(cv_versions_structured, field, _richness_dict_list) or []

    for field in string_list_fields:
        merged[field] = select_richest_section(cv_versions_structured, field, _richness_string_list) or []

    return merged


def build_merged_candidate_cv(
    mongo_collection,
    candidate_id: str,
    target_collection=None,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> dict:
    """
    Construit le CV consolidé, puis l'enregistre dans target_collection
    (merged_candidates). Chaque section est traitée indépendamment :
    - "experience" est fusionnée/dédupliquée par similarité sémantique
      inter-versions (merge_and_deduplicate_experiences)
    - toutes les autres sections sont prises depuis la version la plus
      riche en information pour cette section spécifique, pas
      systématiquement la dernière version (merge_static_sections_by_richness)
    """
    # 1. Récupération du candidat source
    candidate = mongo_collection.find_one({"_id": ObjectId(candidate_id)})
    if not candidate:
        return {}

    versions = candidate.get("versions", [])
    if not versions:
        return {}

    # 2. Récupération des données structurées
    latest_version = versions[-1]
    latest_structured = latest_version.get("structured", {})
    cv_versions_structured = [v.get("structured", {}) for v in versions if "structured" in v]

    if not cv_versions_structured:
        return {}

    # 3. Fusion des expériences — skip l'embedding si une seule version
    if len(cv_versions_structured) > 1:
        deduplicated_experiences = merge_and_deduplicate_experiences(
            cv_versions_structured, threshold=threshold
        )
    else:
        deduplicated_experiences = latest_structured.get("experience", []) or []

    # 4. Sélection par richesse pour toutes les autres sections
    static_sections = merge_static_sections_by_richness(cv_versions_structured)

    # Nom original et normalisé (pas soumis à la sélection par richesse —
    # l'identité du candidat reste ancrée sur le document top-level)
    name = candidate.get("name") or latest_structured.get("name")
    normalized_name = candidate.get("normalized_name") or (name.lower() if name else None)

    # 5. Construction du document ordonné
    result = {
        # Identifiants & Métadonnées de base
        "candidate_id": ObjectId(candidate_id),
        "name": name,
        "normalized_name": normalized_name,

        # Coordonnées
        "email": candidate.get("email") or static_sections["email"],
        "phone": static_sections["phone"],
        "linkedin": static_sections["linkedin"],
        "github": static_sections["github"],

        # Profil & Compétences
        "summary": static_sections["summary"],
        "skills": static_sections["skills"],
        "expertise_areas": static_sections["expertise_areas"],
        "functional_skills": static_sections["functional_skills"],

        # Parcours Professionnel (Fusionné) & Projets
        "experience": deduplicated_experiences,
        "projects": static_sections["projects"],

        # Formations, Certifications & Langues
        "education": static_sections["education"],
        "certifications": static_sections["certifications"],
        "languages": static_sections["languages"],

        # Informations complémentaires
        "countries_worked": static_sections["countries_worked"],
        "professional_affiliations": static_sections["professional_affiliations"],
    }

    # 6. Sauvegarde / Upsert dans MongoDB Atlas
    if target_collection is not None:
        target_collection.update_one(
            {"candidate_id": ObjectId(candidate_id)},
            {"$set": result},
            upsert=True
        )

    return result