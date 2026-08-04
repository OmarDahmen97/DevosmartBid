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
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

load_dotenv()
Gemini_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=Gemini_key)


# ============================================================================
# 1. CONFIGURATION - PROFILS STANDARDS ET MOTS-CLÉS ASSOCIÉS
# ============================================================================

VALID_PROFILE_TITLES = [
    "AI Engineer",
    "Machine Learning Engineer",
    "Cloud Engineer",
    "Cloud Architect",
    "DevOps Engineer",
    "Data Engineer",
    "Data Analyst",
    "Business Intelligence Engineer",
    "Business Analyst",
    "Project Manager",
    "Product Owner",
    "Scrum Master",
    "Solution Architect",
    "IT Consultant",
    "Digital Transformation Consultant",
    "IT Governance Consultant",
    "ERP Consultant",
    "Full Stack Developer",
    "Backend Engineer",
    "Frontend Engineer",
    "Software Engineer",
    "Systems Administrator",
    "Network Engineer",
    "Cybersecurity Engineer",
    "Data Scientist",
    "QA Engineer",
    "Technical Writer",
    "UX/UI Designer",
    "Process Mining Specialist",
    "Generative AI Specialist",
    "IT Strategy Consultant"
]

PROFILE_KEYWORDS = {
    "Cloud Engineer": ["Azure", "Google Cloud", "AWS", "cloud", "deployment", "infrastructure", "cloud migration", "GCP"],
    "Cloud Architect": ["architecture", "cloud", "Azure", "Google Cloud", "AWS", "scalability", "high availability"],
    "AI Engineer": ["RAG", "IA Agentique", "Prompt Engineering", "Generative AI", "machine learning", "neural networks", "LLM", "NLP"],
    "Generative AI Specialist": ["RAG", "IA Agentique", "Prompt Engineering", "Generative AI", "LLM", "GenAI"],
    "Machine Learning Engineer": ["machine learning", "ML", "training", "model deployment", "scikit-learn", "TensorFlow", "PyTorch"],
    "Data Engineer": ["ETL", "data pipeline", "data warehouse", "Big Data", "Process Mining", "data integration", "data migration"],
    "Data Analyst": ["data analysis", "analytics", "Tableau", "Power BI", "reporting", "dashboards", "KPIs"],
    "Business Analyst": ["functional specifications", "process analysis", "workshops", "UAT", "requirements", "business needs", "gap analysis"],
    "Project Manager": ["Agile", "Scrum", "Waterfall", "sprint", "backlog", "stakeholder", "timeline", "planning", "coordination", "deliverables"],
    "Product Owner": ["backlog", "product backlog", "user stories", "prioritization", "stakeholder", "MVP", "vision"],
    "Scrum Master": ["Agile", "Scrum", "sprints", "retrospective", "daily standup", "ceremonies"],
    "Solution Architect": ["architecture", "application architecture", "technical specifications", "integration", "system design", "solution design"],
    "IT Consultant": ["consulting", "audit", "assessment", "recommendations", "advisory"],
    "Digital Transformation Consultant": ["transformation", "digital strategy", "roadmap", "master plan", "modernization", "digitalization"],
    "IT Governance Consultant": ["ITIL", "COBIT", "governance", "procedures", "maturity", "service catalog", "process improvement"],
    "ERP Consultant": ["SAP", "ERP", "S/4HANA", "implementation", "enterprise resource planning"],
    "DevOps Engineer": ["CI/CD", "automation", "deployment", "Docker", "Kubernetes", "Jenkins", "GitLab", "pipeline"],
    "Software Engineer": ["development", "coding", "Python", "Spring", "Angular", "Java", "backend", "frontend"],
    "Full Stack Developer": ["Spring", "Angular", "Python", "frontend", "backend", "API"],
    "Backend Engineer": ["Python", "Spring", "Java", "backend", "API", "microservices", "database"],
    "Process Mining Specialist": ["Process Mining", "Bizagi", "workflow", "process analysis", "bottleneck"],
    "IT Strategy Consultant": ["strategy", "master plan", "roadmap", "strategic recommendations", "target definition"],
    "Cybersecurity Engineer": ["security", "cybersecurity", "vulnerability", "penetration testing", "compliance"],
    "QA Engineer": ["UAT", "test cases", "test scenarios", "testing", "quality assurance", "validation"],
    "UX/UI Designer": ["UX", "UI", "wireframing", "Figma", "prototypes", "user experience", "interface"],
}


def get_weight_for_evidence(evidence_type: str) -> int:
    """Pondération des types de preuves."""
    weights = {
        "certification": 5,
        "skill": 4,
        "technology": 4,
        "responsibility_action": 3,
        "project_description": 3,
        "deliverable": 2,
        "single_mention": 2,
    }
    return weights.get(evidence_type, 2)


# ============================================================================
# 2. BUILD CV DATA (inchangé)
# ============================================================================

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


# ============================================================================
# 3. PRE-SCORING AVEC MOTS-CLÉS
# ============================================================================

def pre_score_profiles(cv_data: dict) -> Dict[str, Dict]:
    """
    Analyse le CV avant l'appel LLM pour calculer un score par profil.
    Retourne un dictionnaire {profile_name: {score, evidence_list}}
    """
    scores = defaultdict(lambda: {"score": 0, "evidence": [], "evidences": []})
    
    # Extraire toutes les données structurées
    all_skills = []
    all_certs = []
    all_technologies = []
    all_responsibilities = []
    all_deliverables = []
    all_project_descriptions = []
    
    for version in cv_data.get("versions", []):
        structured = version.get("structured", {})
        
        # Skills
        for skill in structured.get("skills", []):
            all_skills.append(skill)
        
        # Certifications
        for cert in structured.get("certifications", []):
            all_certs.append(cert.get("name", ""))
        
        # Experiences
        for exp in structured.get("experience", []):
            for tech in exp.get("technologies", []):
                all_technologies.append(tech)
            
            for resp in exp.get("responsibilities", []):
                all_responsibilities.append(resp.get("description", ""))
            
            for deliverable in exp.get("deliverables", []):
                all_deliverables.append(deliverable)
            
            # Description du poste
            if exp.get("description"):
                all_project_descriptions.append(exp.get("description", ""))
    
    # Pour chaque profil, calculer le score
    for profile_name, keywords in PROFILE_KEYWORDS.items():
        score = 0
        evidence_list = []
        
        # 1. Vérifier les certifications (poids 5)
        for cert in all_certs:
            cert_lower = cert.lower()
            for keyword in keywords:
                if keyword.lower() in cert_lower:
                    score += 5
                    evidence_list.append(f"Certification: {cert}")
                    break
        
        # 2. Vérifier les skills (poids 4)
        for skill in all_skills:
            skill_lower = skill.lower()
            for keyword in keywords:
                if keyword.lower() in skill_lower:
                    score += 4
                    evidence_list.append(f"Skill: {skill}")
                    break
        
        # 3. Vérifier les technologies (poids 4)
        for tech in all_technologies:
            tech_lower = tech.lower()
            for keyword in keywords:
                if keyword.lower() in tech_lower:
                    score += 4
                    evidence_list.append(f"Technology: {tech}")
                    break
        
        # 4. Vérifier les responsabilités (poids 3)
        for resp in all_responsibilities:
            resp_lower = resp.lower()
            matched = False
            for keyword in keywords:
                if keyword.lower() in resp_lower:
                    if not matched:
                        score += 3
                        evidence_list.append(f"Responsibility: {resp[:100]}...")
                        matched = True
                    break
        
        # 5. Vérifier les deliverables (poids 2)
        for deliverable in all_deliverables:
            deliverable_lower = deliverable.lower()
            for keyword in keywords:
                if keyword.lower() in deliverable_lower:
                    score += 2
                    evidence_list.append(f"Deliverable: {deliverable}")
                    break
        
        # 6. Vérifier les descriptions de projet (poids 2)
        for desc in all_project_descriptions:
            desc_lower = desc.lower()
            for keyword in keywords:
                if keyword.lower() in desc_lower:
                    score += 2
                    break
        
        # Limiter la liste d'evidence (max 5)
        evidence_list = evidence_list[:5]
        
        scores[profile_name] = {
            "score": score,
            "evidence": evidence_list,
            "evidences": evidence_list
        }
    
    # Ajouter un bonus si un profil a des certifications spécifiques
    # Exemple: si "Generative AI" dans une certif, +3 pour AI Engineer
    for profile_name, data in scores.items():
        for ev in data["evidence"]:
            if "Generative AI" in ev and "AI" in profile_name:
                data["score"] += 3
            elif "ITIL" in ev and "Governance" in profile_name:
                data["score"] += 3
    
    return dict(scores)


# ============================================================================
# 4. CONSTRUCTION DU PROMPT AVEC FEW-SHOT ET CONTEXTE
# ============================================================================

def build_score_context(scores: Dict[str, Dict]) -> str:
    """Construit le contexte de score pour le LLM."""
    lines = []
    sorted_scores = sorted(scores.items(), key=lambda x: x[1]["score"], reverse=True)
    
    for profile_name, data in sorted_scores:
        if data["score"] >= 3:  # Seulement les profils avec un score minimum
            lines.append(f"- {profile_name}: score={data['score']}")
            for ev in data["evidence"][:2]:
                lines.append(f"  * {ev}")
    
    return "\n".join(lines) if lines else "No pre-scoring data available."


def build_profile_detection_prompt_full(all_versions_full: list[dict], candidate_name: str, scores: Dict[str, Dict]) -> str:
    """Prompt amélioré avec Few-Shot et contexte de score."""
    
    score_context = build_score_context(scores)
    
    return f"""You are analyzing the career history of a candidate extracted from structured CV data. Candidate name: {candidate_name}

Your task: Identify ALL MAIN STANDARD PROFESSIONAL PROFILES (Macro-Roles) this candidate qualifies for based strictly on their experience, skills, and projects.

---

### EXAMPLES OF GOOD PROFILING (Few-Shot):

Candidate A: Skills = ["Python", "TensorFlow", "PyTorch", "MLflow"], Experience = ["Built recommendation system", "Fine-tuned LLMs", "Deployed models"]
→ Output: ["AI Engineer", "Machine Learning Engineer"]

Candidate B: Skills = ["AWS", "Terraform", "Docker", "Kubernetes", "Jenkins"], Experience = ["Deployed microservices", "Set up CI/CD pipelines", "Managed cloud infrastructure"]
→ Output: ["Cloud Engineer", "DevOps Engineer"]

Candidate C: Skills = ["SQL", "Tableau", "Power BI", "Python"], Experience = ["Created dashboards", "Data analysis", "ETL pipelines"]
→ Output: ["Data Analyst", "Business Intelligence Engineer"]

Candidate D: Skills = ["Agile", "Scrum", "Jira", "Risk Management"], Experience = ["Managed project team", "Budget tracking", "Stakeholder reporting"]
→ Output: ["Project Manager", "Scrum Master"]

Candidate E: Skills = ["ITIL", "COBIT", "Governance"], Experience = ["Defined IT procedures", "Service catalog", "Maturity assessment"]
→ Output: ["IT Governance Consultant"]

---

### PRE-SCORING ANALYSIS (Guides your decision):

The following pre-scoring was done automatically based on keyword matching.
**Use this as a guide ONLY** - your final decision should be based on actual evidence.

{score_context}

---

### 1. CLUSTERING & NAMING RULES (Standard Job Titles)
Base your profiling ONLY on what the candidate actually DID (action verbs, core deliverables) and their TECHNICAL/FUNCTIONAL DOMAIN.

- **Use Standard, Recognized Job Titles:** Use clear, mainstream job titles from this list: {', '.join(VALID_PROFILE_TITLES)}
- **Keep Profiles Distinct (No Over-Combination):** If a candidate has strong capabilities in two distinct domains, output them as separate standard profiles (e.g., list "AI Engineer" AND "Cloud Engineer" separately, rather than merging them into "Cloud & Generative AI Solutions Consultant"), UNLESS the dual role is a standard market title (e.g., "Data & AI Engineer").
- **Granularity Level:** Focus on functional and technical specialization rather than hyper-specific mission titles.
- **DO NOT cluster by client industry/sector:** Profiles like "Public Sector Consultant" or "Banking Analyst" are INVALID.

### 2. VALID VS INVALID SIGNALS
- **Valid signals:** Recurring technologies, tools, frameworks, technical deliverables, hands-on role responsibilities.
- **Invalid signals:** Client company names, client industry, location, dates.

### 3. EXPERIENCE AND PROJECT MATCHING
- Read every item in `experience[]` and `projects[]`, paying specific attention to `responsibilities[].description`.
- Compound experiences can contribute to more than one profile if the tasks clearly fit both domains.
- References must strictly use the provided index format: {{"version_number": X, "index": Y}}.

### 4. MINIMUM EVIDENCE REQUIREMENT
- Each profile MUST have at least 2 STRONG pieces of evidence (certifications, recurring skills, repeated responsibilities).
- A single mention is NOT sufficient.
- Certifications ALONE are NOT sufficient to create a profile (must have supporting experience).

### 5. CONFIDENCE SCORE
- Include a confidence_score (0.0 to 1.0) based on the strength and quantity of evidence.
- 0.9-1.0: Multiple certifications + recurring experience + skills
- 0.7-0.8: Strong experience + skills, maybe 1 certification
- 0.5-0.6: Some evidence but limited
- <0.5: Weak evidence (should not be included)

---

### OUTPUT FORMAT REQUIREMENTS
Return ONLY a valid JSON object (no markdown formatting, no text before or after). Format:
{{
  "profiles": [
    {{
      "profile_name": "Standard Job Title",
      "summary": "Short 2-line explanation of why the candidate fits this standard role based on evidence.",
      "confidence_score": 0.85,
      "experience_refs": [{{"version_number": 1, "index": 0}}],
      "project_refs": [],
      "key_skills_and_certifications": ["Skill 1", "Skill 2"]
    }}
  ]
}}

Candidate CV data:
{json.dumps(all_versions_full, ensure_ascii=False)}
"""


# ============================================================================
# 5. POST-FILTRAGE
# ============================================================================

def filter_profiles(profiles: List[Dict], cv_data: dict, min_score: int = 5) -> List[Dict]:
    """
    Filtre les profils retournés par le LLM pour éliminer les faux positifs.
    """
    filtered = []
    scores = pre_score_profiles(cv_data)
    
    for profile in profiles:
        profile_name = profile.get("profile_name", "")
        confidence = profile.get("confidence_score", 0.0)
        
        # 1. Vérifier que le profil existe dans nos mots-clés
        if profile_name not in PROFILE_KEYWORDS:
            continue
        
        # 2. Récupérer le score pré-calculé
        score_data = scores.get(profile_name, {})
        pre_score = score_data.get("score", 0)
        evidence = score_data.get("evidence", [])
        
        # 3. Critères de validation
        valid = True
        reasons = []
        
        # A. Score minimum
        if pre_score < min_score:
            valid = False
            reasons.append(f"Pre-score ({pre_score}) below threshold ({min_score})")
        
        # B. Confiance minimum
        if confidence < 0.4:
            valid = False
            reasons.append(f"Confidence ({confidence}) too low")
        
        # C. Au moins 2 preuves
        if len(evidence) < 2:
            valid = False
            reasons.append("Less than 2 evidence pieces")
        
        # D. Vérifier si une certification seule n'est pas le seul signal
        certs_in_evidence = [e for e in evidence if e.startswith("Certification:")]
        if len(certs_in_evidence) == len(evidence) and len(evidence) < 3:
            valid = False
            reasons.append("Only certifications, no experience evidence")
        
        if valid:
            # Ajouter la preuve au profil
            profile["filtered_evidence"] = evidence
            profile["pre_score"] = pre_score
            filtered.append(profile)
    
    return filtered


# ============================================================================
# 6. EXTRACTION JSON
# ============================================================================

def _extract_first_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[^\n]*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
        text = text.strip()
    return json.loads(text)


# ============================================================================
# 7. FONCTION PRINCIPALE
# ============================================================================

def detect_profiles_full(candidate_doc: dict, max_retries: int = 3) -> dict:
    """
    Call Gemini with the FULL structured CV, return detected profiles with
    post-filtering to eliminate false positives.
    """
    # Étape 1: Pre-scoring
    scores = pre_score_profiles(candidate_doc)
    
    # Étape 2: Build CV data
    all_versions_full = build_full_cv_for_profiling(candidate_doc)
    candidate_name = candidate_doc.get("name", "")
    
    # Étape 3: Build prompt avec contexte
    prompt = build_profile_detection_prompt_full(all_versions_full, candidate_name, scores)
    
    # Étape 4: Appel LLM
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-3.1-flash-lite",
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "max_output_tokens": 4000,
                },
            )
            raw_result = _extract_first_json(response.text or "")
            
            # Étape 5: Post-filtrage
            if "profiles" in raw_result:
                raw_result["profiles"] = filter_profiles(
                    raw_result["profiles"], 
                    candidate_doc,
                    min_score=5
                )
            
            return raw_result
            
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)
    
    return {"profiles": []}


# ============================================================================
# 8. TEST / EXAMPLE
# ============================================================================

if __name__ == "__main__":
    # Exemple d'utilisation
    with open("candidate_data.json", "r") as f:
        candidate_doc = json.load(f)
    
    result = detect_profiles_full(candidate_doc)
    print(json.dumps(result, indent=2, ensure_ascii=False))




