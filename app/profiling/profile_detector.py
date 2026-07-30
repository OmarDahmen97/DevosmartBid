

"""
Send the condensed multi-version CV summary to Gemini to detect distinct
professional profiles (e.g. "BI Consultant", "Project Manager") within a
single candidate's career history. Returns, for each detected profile, the
list of (version_number, experience_index) / (version_number, project_index)
it covers — the actual CVSchema reconstruction happens separately, in
profile_builder.py, without another LLM call.
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


def build_profile_detection_prompt(all_versions_summary: list[dict], candidate_name: str) -> str:
    return f"""You are analyzing the career history of a candidate, extracted from multiple versions of their CV. Each version may be in a different language or emphasize different aspects of the same career.

Candidate name: {candidate_name}

Your task: detect DISTINCT PROFESSIONAL PROFILES this candidate could be positioned as (e.g. "Business Intelligence Consultant", "Project Manager", "Cloud Architect"). Base this ONLY on the FUNCTIONAL NATURE OF THE WORK — what the candidate actually did (design, build, manage, train, analyze...) and in what technical domain (infrastructure, BI, cloud, project governance...).

DO NOT cluster by client industry, sector, or employer name (e.g. "public sector" vs "banking" is NOT a valid distinction if the underlying work — e.g. project management, systems integration — is the same). Two projects for a bank and a ministry using the same skillset and delivering the same type of work belong in the SAME profile.

Valid clustering signals: recurring technologies/tools, recurring deliverable types (e.g. "migration", "architecture design", "team coaching", "dashboard development"), recurring role verbs in the description (architected / managed / trained / developed / audited).
Invalid clustering signals: client name, client industry/sector, project country, project dates.

Evidence to look for: distinct clusters of skills/expertise_areas that don't overlap technically (e.g. BI/reporting tools vs infrastructure/virtualization vs project management methodology), distinct types of projects, distinct certifications tracks. Two or more such clusters = two or more profiles, regardless of experience entry count.

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

Candidate CV data (condensed, multiple versions):
{json.dumps(all_versions_summary, ensure_ascii=False)}
"""


def _extract_first_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[^\n]*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
        text = text.strip()
    return json.loads(text)


def detect_profiles(all_versions_summary: list[dict], candidate_name: str, max_retries: int = 3) -> dict:
    """
    Call Gemini once with the condensed multi-version summary, return the
    detected profiles with their experience/project reference indices.
    """
    prompt = build_profile_detection_prompt(all_versions_summary, candidate_name)

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-3.1-flash-lite",
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "max_output_tokens": 3000,
                },
            )
            return _extract_first_json(response.text or "")
        except Exception:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)