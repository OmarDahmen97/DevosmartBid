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
}

SEARCH_CONFIG = {
    "summary": {"distance_threshold": 0.6, "min_results": 1, "max_results": 1},
    "skills": {"distance_threshold": 0.7, "min_results": 1, "max_results": 1},
    "functional_skills": {"distance_threshold": 0.7, "min_results": 1, "max_results": 1},
    "expertise_areas": {"distance_threshold": 0.6, "min_results": 1, "max_results": 1},
    "experience": {"distance_threshold": 0.35, "min_results": 0, "max_results": 1},
    "project": {"distance_threshold": 0.5, "min_results": 0, "max_results": 1},
    "education": {"distance_threshold": 0.7, "min_results": 0, "max_results": 1},
    "languages": {"distance_threshold": 0.8, "min_results": 0, "max_results": 1},
    "certifications": {"distance_threshold": 0.8, "min_results": 0, "max_results": 1},
    "countries_worked": {"distance_threshold": 0.8, "min_results": 0, "max_results": 1},
    "professional_affiliations": {"distance_threshold": 0.8, "min_results": 0, "max_results": 1},
}

EXPERIENCE_SEARCH_CONFIG = {"distance_threshold": 0.35, "min_results": 0, "max_results": 6}
PROJECT_SEARCH_CONFIG = {"distance_threshold": 0.5, "min_results": 0, "max_results": 6}

INDEXED_TYPES = {"experience", "project"}
LIST_TYPES = {"expertise_areas", "functional_skills", "education", "languages", "certifications"}