from app.config import SEARCH_CONFIG
from app.generation.cv_json_builder import (
    is_candidate_relevant_v2,
    build_matched_cv_json,
    distance_to_score,
)
from app.generation.mongo_resolver import (
    resolve_chunk_to_mongo_source,
    resolve_list_section_matches,
)