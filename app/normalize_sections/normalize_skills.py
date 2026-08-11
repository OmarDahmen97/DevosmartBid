# file: app/normalize_sections/normalize_skills.py
"""
Lightweight skill normalizer, meant to run on every extraction (no SBERT
dependency -- the embedding-based candidate-pair review lives in the
separate root-level normalize_skills.py script, run offline).

Two layers:
  1. Casing normalization, applied within a single CV's own skill list
     (batch, since picking the "best" casing needs to compare variants
     against each other -- there's nothing to compare a lone value against).
  2. MANUAL_ALIASES lookup -- synonyms confirmed by reviewing the embedding
     report (see normalize_skills.py at the project root). This dict is the
     single source of truth; the review script imports it from here rather
     than keeping its own copy.

Unlike countries/languages, there's no authoritative reference for skill
names, so MANUAL_ALIASES starts empty and grows as you review candidates
found by the offline embedding-based tool.
"""

from collections import defaultdict


# Global, persistent canonical casing table -- unlike normalize_casing()
# below (which only compares variants WITHIN a single CV's own list),
# this is the single source of truth for "what casing wins" ACROSS the
# whole database. Without this, two different candidates' documents each
# get internally-consistent casing independently, but nothing guarantees
# they converge on the SAME casing as each other -- "Data Analysis" in one
# CV and "data analysis" in another both look correct locally, yet the
# aggregate distinct-values view still shows both as separate entries.
#
# Seed/refresh this by running the offline review script (normalize_skills.py
# at the project root), which computes casing across the entire DB at once,
# then copy its suggested mapping here.
CANONICAL_CASING: dict[str, str] = {
    "data analysis": "Data Analysis",
    "it governance": "IT Governance",
    "jira": "JIRA",
    "project management": "Project Management",
    "scikit-learn": "Scikit-learn",
}


def _casing_score(value: str) -> int:
    """Prefer a variant with an uppercase letter beyond the first position
    (a sign of a correctly cased acronym or proper noun, e.g. "FastAPI")."""
    return sum(1 for c in value[1:] if c.isupper())


def normalize_casing(raw_values: list[str]) -> dict[str, str]:
    """Group values by case-insensitive key, pick one canonical casing per
    group. Returns {original_value: canonical_value} for every input."""
    groups: dict[str, list[str]] = defaultdict(list)
    for v in raw_values:
        groups[v.lower()].append(v)

    mapping = {}
    for key, variants in groups.items():
        canonical = sorted(set(variants), key=lambda v: (-_casing_score(v), v))[0]
        for v in variants:
            mapping[v] = canonical

    return mapping


# Confirmed synonyms, filled in manually by you after reviewing the offline
# embedding-based report. Empty by default -- add entries here as you
# validate them, never auto-populated. Takes priority over AUTO_ALIASES
# below if the same raw value appears in both (human judgment wins).
MANUAL_ALIASES: dict[str, str] = {
    "Advanced Data Analysis": "Data Analysis",
    "Agile Methodology": "Agile",
    "Agile/Scrum": "Agile Scrum",
    "Auditing": "Audit",
    "BCMS": "Business Continuity Planning",
    "BCP Procedures": "Business Continuity Planning",
    "BCP Strategy": "Business Continuity Planning",
    "BPMN 2.0": "BPMN",
    "BigQuery": "Google BigQuery",
    "Business Analysis": "Business Analysis & Requirements Gathering",
    "Business Continuity Plan": "Business Continuity Planning",
    "Business Process Modeling": "Business Process Modeling (BPMN)",
    "Business Requirements Analysis": "Business Analysis & Requirements Gathering",
    "CI/CD": "CI/CD pipelines",
    "Data Management and Analysis": "Data Analysis",
    "Digital Strategy": "Digital Transformation",
    "Digital transformation roadmap": "Digital Transformation",
    "ERP implementation": "ERP",
    "FAISS (Vector Databases)": "FAISS",
    "Finance and Accounting": "Accounting",
    "FlexCube by Oracle": "Oracle (FlexCube)",
    "Gap assessment": "Gap Analysis",
    "Gemini": "Google Gemini",
    "GenAI": "Generative AI",
    "General Accounting": "Accounting",
    "Google Cloud (Vertex AI)": "Vertex AI",
    "HRM": "Human Resources Management",
    "HTML5": "HTML",
    "IAM": "IAM (RSA)",
    "IS Governance": "IT Governance",
    "ISMS implementation": "ISMS",
    "IT Governance & Compliance": "IT Governance",
    "IT Master Plan": "IT Master Planning",
    "IT Planning": "IT Master Planning",
    "IT Project Management": "Project Management",
    "IT Risk Management": "Risk Management",
    "IT Strategy & Transformation": "IT Strategy",
    "IT master plan development": "IT Master Planning",
    "Jira": "JIRA",
    "LLMs": "LLM",
    "ML modeling": "Machine Learning",
    "Microsoft Azure": "Azure",
    "Microsoft Office": "Microsoft Office Suite",
    "Microsoft Suite": "Microsoft Office Suite",
    "Ollama": "Local Inference (Ollama)",
    "PCI DSS Audit": "PCI/DSS",
    "Payroll Management": "Payroll",
    "Process Optimization": "Process Improvement",
    "Process Reengineering": "Process Improvement",
    "Project Portfolio Management": "Project Management",
    "Project Tracking": "Project Management",
    "R": "R Programming",
    "React.js": "React",
    "RedHat": "Red Hat",
    "Requirement Gathering": "Requirements Engineering",
    "Requirements Documentation": "Requirements Engineering",
    "Requirements analysis": "Requirements Engineering",
    "Requirements formalisation": "Requirements Engineering",
    "Risk Analysis": "Risk Management",
    "SAP ERP": "SAP",
    "SAP S/4 HANA": "SAP S/4HANA",
    "SAP migration projects": "SAP",
    "Scrum": "Agile Scrum",
    "Shell scripts": "Shell",
    "Strategic planning": "Strategic direction",
    "Systems Management": "System Management",
    "Tailwind CSS": "TailwindCSS",
    "Talend": "Talend Open Studio",
    "UML Modeling": "UML",
    "VMS system": "VMS",
    "Vulnerability scans": "Vulnerability scan",
}

# --- AUTO_ALIASES: machine-generated by auto_normalize_skills.py ---
# Do not hand-edit this block -- it gets fully rewritten every time the
# script runs. Pairs are auto-merged above a high cosine similarity
# threshold, with a guard against merging values that contain different
# numeric identifiers (protects distinct standards/versions like
# "ISO 27001" vs "ISO 27002", which score above 0.95 despite being
# different standards). This guard doesn't catch every risky case (e.g.
# "Project Management" vs "Project Management Methodology" can still merge
# if both cross the threshold) -- periodic spot-checking of this block is
# still recommended even though it's applied without manual review per pair.
AUTO_ALIASES: dict[str, str] = {

}
# --- end AUTO_ALIASES ---


def normalize_skill_list(raw_values: list[str]) -> list[str]:
    """
    Normalize a single CV's skill list:
      1. CANONICAL_CASING lookup first -- global, DB-wide casing consistency.
      2. For anything not in CANONICAL_CASING, fall back to local casing
         normalization within this list only.
      3. MANUAL_ALIASES lookup (human-confirmed synonyms) -- checked first,
         overrides AUTO_ALIASES on conflict.
      4. AUTO_ALIASES lookup (machine-generated via embedding clustering,
         see auto_normalize_skills.py) -- applied if no manual override exists.
    Deduplicated, first-seen order preserved.
    """
    if not raw_values:
        return []

    local_casing_map = normalize_casing(raw_values)

    seen = set()
    result = []
    for raw in raw_values:
        key = raw.lower()
        cased = CANONICAL_CASING.get(key) or local_casing_map.get(raw, raw)
        canonical = MANUAL_ALIASES.get(cased) or AUTO_ALIASES.get(cased) or cased
        if canonical not in seen:
            seen.add(canonical)
            result.append(canonical)

    return result