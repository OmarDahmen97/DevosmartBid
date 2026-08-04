"""
app/generation/section_richness_report.py

Read-only diagnostic script that measures content richness of
expertise_areas, functional_skills, and skills across all candidates
and all versions in the candidates collection.
"""

import csv
import os
import statistics
from collections import defaultdict

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

SECTIONS = ["expertise_areas", "functional_skills", "skills"]
COLLECTION_NAME = "candidates"
OUTPUT_PATH = os.path.join("data", "section_richness_report.csv")


def get_collection():
    client = MongoClient(os.getenv("MONGO_URI"))
    db = client["cv_platform"]
    return db[COLLECTION_NAME]


def compute_element_length(section, element):
    if section in ("expertise_areas", "functional_skills"):
        category = element.get("category") or ""
        description = element.get("description") or ""
        return len(category) + len(description)
    if section == "skills":
        return len(str(element))
    return 0


def compute_richness(section, items):
    if not items:
        return 0, 0.0, 0.0

    num_elements = len(items)
    lengths = [compute_element_length(section, item) for item in items]
    avg_element_length = sum(lengths) / num_elements
    richness_score = avg_element_length * num_elements
    return num_elements, avg_element_length, richness_score


def percentile(sorted_data, p):
    if not sorted_data:
        return 0.0
    k = (len(sorted_data) - 1) * (p / 100.0)
    f = int(k)
    c = f + 1
    if c >= len(sorted_data):
        return float(sorted_data[f])
    d0 = sorted_data[f] * (c - k)
    d1 = sorted_data[c] * (k - f)
    return d0 + d1


def aggregate_stats(values):
    sorted_values = sorted(values)
    n = len(sorted_values)
    if n == 0:
        return {}

    return {
        "count": n,
        "min": min(sorted_values),
        "max": max(sorted_values),
        "mean": statistics.mean(sorted_values),
        "median": statistics.median(sorted_values),
        "p25": percentile(sorted_values, 25),
        "p75": percentile(sorted_values, 75),
        "p90": percentile(sorted_values, 90),
        "zero_count": sum(1 for v in values if v == 0),
    }


def main():
    collection = get_collection()
    total_candidates = collection.count_documents({})
    print(f"Total candidates: {total_candidates}")

    rows = []
    skipped = 0

    for candidate in collection.find({}):
        versions = candidate.get("versions", [])
        if not versions:
            skipped += 1
            continue

        candidate_id = str(candidate["_id"])
        candidate_name = candidate.get("name", "")

        for version in versions:
            version_number = version.get("version_number")
            structured = version.get("structured", {})

            for section in SECTIONS:
                items = structured.get(section, [])
                if items is None:
                    items = []

                num_elements, avg_element_length, richness_score = compute_richness(
                    section, items
                )

                rows.append(
                    {
                        "candidate_id": candidate_id,
                        "candidate_name": candidate_name,
                        "version_number": version_number,
                        "section": section,
                        "num_elements": num_elements,
                        "avg_element_length": round(avg_element_length, 2),
                        "richness_score": round(richness_score, 2),
                    }
                )

    print(f"Candidates skipped (no versions): {skipped}")
    print(f"Total candidate-version-section rows: {len(rows)}")

    section_values = defaultdict(list)
    for row in rows:
        section_values[row["section"]].append(row["richness_score"])

    print("\n" + "=" * 70)
    print("SECTION RICHNESS REPORT")
    print("=" * 70)

    for section in SECTIONS:
        values = section_values[section]
        stats = aggregate_stats(values)
        print(f"\n[{section}]")
        print(f"  candidate-version count : {stats['count']}")
        print(f"  min                     : {stats['min']:.2f}")
        print(f"  max                     : {stats['max']:.2f}")
        print(f"  mean                    : {stats['mean']:.2f}")
        print(f"  median                  : {stats['median']:.2f}")
        print(f"  p25                     : {stats['p25']:.2f}")
        print(f"  p75                     : {stats['p75']:.2f}")
        print(f"  p90                     : {stats['p90']:.2f}")
        print(f"  zero richness_count     : {stats['zero_count']}")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "candidate_id",
                "candidate_name",
                "version_number",
                "section",
                "num_elements",
                "avg_element_length",
                "richness_score",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nExported raw results to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
