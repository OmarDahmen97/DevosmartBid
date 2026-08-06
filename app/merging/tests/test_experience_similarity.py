# file: app/merging/tests/test_experience_similarity.py
"""
Manual test: for each multi-version candidate, embed every experience
across all versions and print all pairwise similarities (cross-version
only) sorted descending, to visually inspect where true duplicates
cluster vs distinct missions.

Usage: python -m app.merging.tests.test_experience_similarity
"""

import os

from dotenv import load_dotenv
from pymongo import MongoClient

from app.merging.experience_similarity import pairwise_similarities

load_dotenv()
client = MongoClient(os.getenv("MONGO_URI"))
candidates = client["cv_platform"]["candidatesV2"]


def get_all_experiences(candidate: dict) -> tuple[list[dict], list[int]]:
    """Returns (experiences, versions) aligned lists across all versions."""
    experiences = []
    versions = []
    for version in candidate.get("versions", []):
        version_number = version.get("version_number")
        for exp in version.get("structured", {}).get("experience", []):
            experiences.append(exp)
            versions.append(version_number)
    return experiences, versions


def main():
    multi_version_candidates = candidates.find({"versions.1": {"$exists": True}})

    for candidate in multi_version_candidates:
        name = candidate.get("name", "UNKNOWN")
        experiences, versions = get_all_experiences(candidate)

        if len(experiences) < 2:
            continue

        pairs = pairwise_similarities(experiences, versions)
        pairs.sort(key=lambda x: x[2], reverse=True)

        print(f"\n{'=' * 70}")
        print(f"Candidate: {name} ({len(experiences)} experiences total)")
        print(f"{'=' * 70}")

        for i, j, sim in pairs[:30]:
            company_i = experiences[i].get("company")
            company_j = experiences[j].get("company")
            dates_i = experiences[i].get("dates")
            dates_j = experiences[j].get("dates")
            print(f"  {sim:.3f}  v{versions[i]} vs v{versions[j]}")
            print(f"           {company_i!r} {dates_i!r} <-> {company_j!r} {dates_j!r}")


if __name__ == "__main__":
    main()