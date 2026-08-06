import os
from dotenv import load_dotenv
from pymongo import MongoClient



EMBEDDING_MODEL_NAME = "paraphrase-multilingual-mpnet-base-v2"
EMBEDDING_MAX_SEQ_LENGTH = 128
EMBEDDING_BATCH_SIZE = 32

CHROMA_PERSIST_PATH = "./chroma_data"
CHROMA_COLLECTION_NAME = "cv_chunks"

DEFAULT_MAX_TOKENS = 118
HARD_CAP_TOKENS = 120

MAX_TOKENS_BY_TYPE = {
    "summary": 118,
    "skills": 100,
    "education": 80,
    "languages": 50,
    "expertise_areas": 118,
    "functional_skills": 118,
    "certifications": 50,
    "countries_worked": 40,
    "professional_affiliations": 40,
    "experience": 118,
    "project": 100,
}

MIN_RELEVANCE_SCORE = 50.0

PASS_A_SECTION_THRESHOLDS = {
    "summary": 0.6,
    "experience": 0.35,
    "project": 0.5,
    "skills": 0.3,
    "expertise_areas": 0.3,
    "functional_skills": 0.3,
    # sections factuelles/catégorielles -- un "match" sémantique dessus a
    # rarement du sens pour évaluer la pertinence d'une mission, donc
    # resserrées fortement plutôt que retirées
    "education": 0.3,
    "certifications": 0.33,
    "languages": 0.6,
    "countries_worked": 0.65,
    "professional_affiliations": 0.4,
}

SECTION_RICHNESS_THRESHOLD = 500.0

SEARCH_CONFIG = {
    "summary": {"distance_threshold": 0.6, "min_results": 1, "max_results": 1},
    "skills": {"distance_threshold": 0.7, "min_results": 1, "max_results": 10},
    "functional_skills": {"distance_threshold": 0.7, "min_results": 1, "max_results": 10},
    "expertise_areas": {"distance_threshold": 0.6, "min_results": 1, "max_results": 10},
    "experience": {"distance_threshold": 0.35, "min_results": 0, "max_results": 10},
    "project": {"distance_threshold": 0.5, "min_results": 0, "max_results": 10},
    "education": {"distance_threshold": 0.7, "min_results": 0, "max_results": 10},
    "languages": {"distance_threshold": 0.8, "min_results": 0, "max_results": 10},
    "certifications": {"distance_threshold": 0.8, "min_results": 0, "max_results": 10},
    "countries_worked": {"distance_threshold": 0.8, "min_results": 0, "max_results": 10},
    "professional_affiliations": {"distance_threshold": 0.8, "min_results": 0, "max_results": 10},
}

EXPERIENCE_SEARCH_CONFIG = {"distance_threshold": 0.35, "min_results": 0, "max_results": 6}
PROJECT_SEARCH_CONFIG = {"distance_threshold": 0.5, "min_results": 0, "max_results": 6}

INDEXED_TYPES = {"experience", "project"}
LIST_TYPES = {"expertise_areas", "functional_skills", "education", "languages", "certifications"}