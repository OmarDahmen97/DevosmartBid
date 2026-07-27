from app.profiling.profile_summarizer import summarize_all_versions
import json
from app.embedding.embedding_chunker import count_tokens
from app.embedding.embedding_chunker import (
    serialize_category_description_list,
    serialize_string_list,
    count_tokens,
    split_text_by_tokens,
    serialize_experience_to_text,
    build_experience_chunks,
    build_project_chunks,
    build_chunks_for_version,
    
)
import os
from pymongo import MongoClient
from dotenv import load_dotenv
from app.embedding.embedder import Embedder
from app.embedding.vector_store import VectorStore
from bson import ObjectId


load_dotenv()
mongo_uri = os.getenv("MONGO_URI")
client = MongoClient(mongo_uri)
db = client["cv_platform"]
candidates = db["candidates"]

candidate = candidates.find_one({"normalized_name": "leith majdoub"})
version = candidate["versions"][0]
experiences = version["structured"]["experience"]
projects=version["structured"]["projects"]
candidate_id = str(candidate["_id"])


#embedder = Embedder()
#store = VectorStore()
#store.delete_candidate_chunks(candidate_id, version_number=version["version_number"])
#chunks = build_chunks_for_version(candidate, version, tokenizer=embedder.model.tokenizer)
#enriched = embedder.embed_chunks(chunks)
#store.index_chunks(enriched)

from app.profiling.profile_summarizer import summarize_all_versions
from app.profiling.profile_detector import detect_profiles
import json

all_versions_summary = summarize_all_versions(candidate)
result = detect_profiles(all_versions_summary, candidate.get("name", ""))
print(json.dumps(result, indent=2, ensure_ascii=False))