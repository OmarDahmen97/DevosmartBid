"""
Same as profile_detector_full_cv.py (full structured CV, raw_text excluded),
but calling a LOCAL model (qwen2.5:7b via Ollama) instead of Gemini.

Kept as a separate function/file rather than a flag on detect_profiles_full()
so both can be benchmarked side by side without touching the Gemini path.
"""

import json
import time
import re
import ollama

from app.profiling.profile_detector_full_cv import build_full_cv_for_profiling

OLLAMA_MODEL = "qwen2.5:7b"


def build_profile_detection_prompt_full(all_versions_full: list[dict], candidate_name: str) -> str:
    return f"""You are analyzing the career history of a candidate, extracted from multiple versions of their CV. Each version may be in a different language or emphasize different aspects of the same career.

Candidate name: {candidate_name}

Your task: detect DISTINCT PROFESSIONAL PROFILES this candidate could be positioned as (e.g. "Business Intelligence Consultant", "Project Manager", "Cloud Architect"). Base this ONLY on the FUNCTIONAL NATURE OF THE WORK — what the candidate actually did (design, build, manage, train, analyze...) and in what technical domain (infrastructure, BI, cloud, project governance, security...).

DO NOT cluster by client industry, sector, or employer name (e.g. "public sector" vs "banking" is NOT a valid distinction if the underlying work is the same). Two missions for a bank and a ministry using the same skillset and delivering the same type of work belong in the SAME profile.

Valid clustering signals: recurring technologies/tools, recurring deliverable types (e.g. "migration", "architecture design", "team coaching", "dashboard development", "penetration test", "audit"), recurring role verbs in the description (architected / managed / trained / developed / audited).
Invalid clustering signals: client name, client industry/sector, project country, project dates.

Many entries have title=null or description=null — in those cases, the real signal is in responsibilities[].description. Read every responsibility description individually before assigning an entry; do not classify based on the title alone, and do not default an ambiguous entry into whichever profile group is largest.

Distinguish management/leadership roles (directing a team, a CERT, a SOC, a regional practice) from hands-on technical delivery roles (auditing, pentesting, hardening, building) even if they share the same technical domain — they are different profiles if the nature of the work (direct vs. oversee) differs.

Important: senior consultants often hold one long-tenure role whose TITLE ALONE already spans several domains (e.g. "Cloud Architect & BI Architect & Senior Trainer"). Parse compound titles and descriptions for multiple domains even within a single experience entry.

For each experience/project, you are given its (version_number, index) — use these to reference it, do not invent new indices.

Return ONLY JSON, no other text, no markdown fences, in this exact format:
{{
  "profiles": [
    {{
      "profile_name": "Business Intelligence Consultant",
      "experience_refs": [{{"version_number": 1, "index": 0}}, {{"version_number": 1, "index": 3}}],
      "project_refs": [{{"version_number": 1, "index": 0}}]
    }}
  ]
}}

Every experience/project index provided in the input MUST appear in exactly one profile's refs — pick the profile it fits best if it touches multiple domains.
Every ref object MUST contain both "version_number" and "index" — never omit either field.

Candidate CV data (full structured data, all versions, raw_text excluded):
{json.dumps(all_versions_full, ensure_ascii=False)}
"""


def _extract_first_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[^\n]*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
        text = text.strip()
    return json.loads(text)


def _validate_profiles_schema(result: dict) -> bool:
    """Ensure every ref has both version_number and index, catches LLM JSON glitches."""
    if not isinstance(result, dict) or "profiles" not in result:
        return False
    for profile in result.get("profiles", []):
        for ref in profile.get("experience_refs", []) + profile.get("project_refs", []):
            if "version_number" not in ref or "index" not in ref:
                return False
    return True


def _repair_profiles_schema(result: dict) -> dict:
    """
    Drop malformed refs (missing version_number or index) instead of failing
    the whole call. Qwen2.5:7b occasionally omits a field on a single ref
    out of dozens -- discarding that one ref is a much smaller loss than
    discarding the entire profile detection result.
    """
    dropped = 0
    for profile in result.get("profiles", []):
        for key in ("experience_refs", "project_refs"):
            clean_refs = []
            for ref in profile.get(key, []):
                if "version_number" in ref and "index" in ref:
                    clean_refs.append(ref)
                else:
                    dropped += 1
            profile[key] = clean_refs
    if dropped:
        print(f"[detect_profiles_full_local] Dropped {dropped} malformed ref(s) from LLM output.")
    return result


def detect_profiles_full_local(candidate_doc: dict, max_retries: int = 3) -> dict:
    """
    Same contract as detect_profiles_full() (Gemini version): full structured
    CV in, {"profiles": [...]} out. Runs entirely locally via Ollama —
    no external API call, no data leaving the machine.
    """
    all_versions_full = build_full_cv_for_profiling(candidate_doc)
    candidate_name = candidate_doc.get("name", "")

    prompt = build_profile_detection_prompt_full(all_versions_full, candidate_name)

    last_raw_content = None
    for attempt in range(max_retries):
        try:
            response = ollama.chat(
                model=OLLAMA_MODEL,
                messages=[{"role": "user", "content": prompt}],
                format="json",  # forces valid JSON output, Ollama's equivalent of Gemini's response_mime_type
                options={
                    "temperature": 0.1 + attempt * 0.2,  # bump temperature on retry, otherwise a near-deterministic
                                                          # low-temp call just regenerates the same malformed output
                    "num_predict": 4000,
                },
            )
            content = response["message"]["content"]
            last_raw_content = content
            result = _extract_first_json(content)

            if not _validate_profiles_schema(result):
                print(f"[detect_profiles_full_local] Attempt {attempt + 1}: malformed refs detected, raw output below:")
                print(content)
                result = _repair_profiles_schema(result)

            return result
        except json.JSONDecodeError:
            print(f"[detect_profiles_full_local] Attempt {attempt + 1}: invalid JSON, raw output below:")
            print(last_raw_content)
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)
        except Exception:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)