"""
Send the FULL structured CV (all versions, all fields, minus raw_text) to
Gemini to detect distinct professional profiles. Unlike profile_detector.py
(condensed summary), this sends every description/responsibility verbatim —
better recall on CVs where titles are null and the real signal lives in
responsibilities[].description, at the cost of a larger prompt.

raw_text is excluded on purpose: it's a near-duplicate of `structured` in
unparsed form (same content, just not split into fields) — including both
would double the prompt size for zero extra signal.
"""

import json
import time
import re
import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
Gemini_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=Gemini_key)


def build_full_cv_for_profiling(candidate_doc: dict) -> list[dict]:
    """
    Same shape as summarize_all_versions(), but each version carries the
    full `structured` dict as-is (minus raw_text, which lives one level up
    and is never included here in the first place).
    """
    return [
        {
            "version_number": v["version_number"],
            "structured": v.get("structured", {}),
        }
        for v in candidate_doc.get("versions", [])
    ]


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


def detect_profiles_full(candidate_doc: dict, max_retries: int = 3) -> dict:
    """
    Call Gemini once with the FULL structured CV (all versions, raw_text
    excluded), return the detected profiles with their experience/project
    reference indices. Use this instead of detect_profiles() when the
    condensed summary loses too much signal (title=null entries, long
    responsibilities that don't compress well into keywords).
    """
    all_versions_full = build_full_cv_for_profiling(candidate_doc)
    candidate_name = candidate_doc.get("name", "")

    prompt = build_profile_detection_prompt_full(all_versions_full, candidate_name)

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-3.1-flash-lite",
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "max_output_tokens": 4000,  # relevé vs 3000 : plus d'entrées visibles = potentiellement plus de refs en sortie
                },
            )
            return _extract_first_json(response.text or "")
        except Exception:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)