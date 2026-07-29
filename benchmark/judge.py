# benchmark/judge.py

import json
import time
import hashlib
import os
from groq import Groq, RateLimitError
from dotenv import load_dotenv

load_dotenv()
Groq_key = os.getenv("GROQ_API_KEY6")
client = Groq(api_key=Groq_key)

_judge_cache = {}  # évite de refaire le même appel si le grid search relance plusieurs fois la même combinaison


def _cache_key(mission_text: str, chunk_text: str, chunk_type: str) -> str:
    raw = f"{mission_text}|{chunk_text}|{chunk_type}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def build_judge_prompt(mission_text: str, chunk_text: str, chunk_type: str) -> str:
    return f"""You are evaluating whether a piece of a candidate's CV is relevant to a job mission, for benchmarking a semantic search system. The CV excerpt may be in a different language than the mission — judge based on MEANING, not matching words.

Mission:
{mission_text}

CV excerpt (section type: {chunk_type}):
{chunk_text}

Is this CV excerpt relevant to the mission? Answer with ONLY a JSON object, no other text:
{{"relevant": true}} or {{"relevant": false}}
"""


def judge_chunk_relevance(
    mission_text: str,
    chunk_text: str,
    chunk_type: str,
    candidate_label: str,
    max_retries: int = 3,
) -> bool:
    """
    LLM-based judge: evaluates whether a chunk is relevant to the mission,
    regardless of language (unlike the keyword-based version).
    """
    if candidate_label == "non_match":
        return False

    if not chunk_text.strip():
        return False

    key = _cache_key(mission_text, chunk_text, chunk_type)
    if key in _judge_cache:
        return _judge_cache[key]

    prompt = build_judge_prompt(mission_text, chunk_text, chunk_type)

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",  # rapide et léger, adapté au volume d'appels
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=20,
            )
            result = json.loads(response.choices[0].message.content)
            relevant = bool(result.get("relevant", False))
            _judge_cache[key] = relevant
            return relevant
        except RateLimitError:
            if attempt == max_retries - 1:
                _judge_cache[key] = False
                return False
            time.sleep(2 ** attempt)
        except Exception:
            _judge_cache[key] = False
            return False