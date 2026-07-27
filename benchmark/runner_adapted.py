# benchmark/runner.py
import yaml
import json
import os
from datetime import datetime
from typing import Dict, List
from collections import defaultdict

from app.embedding.embedder import Embedder
from app.embedding.vector_store import VectorStore
from app.generation.cv_json_builder import SEARCH_CONFIG, distance_to_score
from benchmark.judge import judge_chunk_relevance


class BenchmarkRunner:
    def __init__(self):
        self.embedder = Embedder()
        self.vector_store = VectorStore()

        with open("benchmark/ground_truth.yaml", "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            self.benchmark = data["benchmark"]

    def evaluate_config(self, search_config: Dict, min_relevance_score: float = 0.25) -> Dict:
        results_by_section = defaultdict(lambda: {"vp": 0, "fp": 0, "fn": 0, "vn": 0})
        global_counts = {"true_positive": 0, "false_positive": 0, "false_negative": 0}

        for mission in self.benchmark:
            mission_emb = self.embedder.embed_text(mission["mission_text"])

            for case in mission["cases"]:
                candidate_id = case["candidate_id"]
                version_number = case.get("version_number")  # <-- IMPORTANT : gère les versions
                expected_sections = set(case["expected_sections"])
                label = case["label"]

                # --- Garde-fou Passe A (is_candidate_relevant) ---
                all_scores = []
                for section, cfg in search_config.items():
                    chunks = self.vector_store.search_section(
                        query_embedding=mission_emb,
                        candidate_id=candidate_id,
                        chunk_type=section,
                        version_number=version_number,  # <-- passe la version
                        distance_threshold=cfg["distance_threshold"],
                        min_results=cfg["min_results"],
                        max_results=cfg["max_results"]
                    )
                    if chunks:
                        best_dist = chunks[0].get("distance", 1.0)
                        all_scores.append(distance_to_score(best_dist))

                avg_best_score = sum(all_scores) / len(all_scores) if all_scores else 0
                is_globally_relevant = avg_best_score >= min_relevance_score

                if label == "non_match" and is_globally_relevant:
                    global_counts["false_positive"] += 1
                elif label != "non_match" and not is_globally_relevant:
                    global_counts["false_negative"] += 1
                elif label != "non_match" and is_globally_relevant:
                    global_counts["true_positive"] += 1

                # --- Évaluation section par section ---
                for section, cfg in search_config.items():
                    chunks = self.vector_store.search_section(
                        query_embedding=mission_emb,
                        candidate_id=candidate_id,
                        chunk_type=section,
                        version_number=version_number,
                        distance_threshold=cfg["distance_threshold"],
                        min_results=cfg["min_results"],
                        max_results=cfg["max_results"]
                    )

                    chunk_text = chunks[0].get("text", "") if chunks else ""
                    is_relevant = judge_chunk_relevance(
                        mission["mission_text"], chunk_text, section, label
                    ) if chunks else False

                    should_match = section in expected_sections

                    if chunks and is_relevant and should_match:
                        results_by_section[section]["vp"] += 1
                    elif chunks and is_relevant and not should_match:
                        results_by_section[section]["fp"] += 1
                    elif chunks and not is_relevant and should_match:
                        results_by_section[section]["fn"] += 1
                    elif not chunks and should_match:
                        results_by_section[section]["fn"] += 1
                    elif not chunks and not should_match:
                        results_by_section[section]["vn"] += 1
                    elif chunks and not is_relevant and not should_match:
                        results_by_section[section]["fp"] += 1

        # Calcul métriques
        metrics = {}
        for section, counts in results_by_section.items():
            vp, fp, fn = counts["vp"], counts["fp"], counts["fn"]
            precision = vp / (vp + fp) if (vp + fp) > 0 else 0
            recall = vp / (vp + fn) if (vp + fn) > 0 else 0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

            metrics[section] = {
                "vp": vp, "fp": fp, "fn": fn, "vn": counts["vn"],
                "precision": round(precision, 3),
                "recall": round(recall, 3),
                "f1": round(f1, 3)
            }

        gp, gfp, gfn = global_counts["true_positive"], global_counts["false_positive"], global_counts["false_negative"]
        global_precision = gp / (gp + gfp) if (gp + gfp) > 0 else 0
        global_recall = gp / (gp + gfn) if (gp + gfn) > 0 else 0
        global_f1 = 2 * global_precision * global_recall / (global_precision + global_recall) if (global_precision + global_recall) > 0 else 0

        return {
            "by_section": metrics,
            "global": {
                "min_relevance_score": min_relevance_score,
                "precision": round(global_precision, 3),
                "recall": round(global_recall, 3),
                "f1": round(global_f1, 3),
                "details": global_counts
            }
        }

    def grid_search(self, threshold_candidates=None, min_relevance_candidates=None):
        if threshold_candidates is None:
            threshold_candidates = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
        if min_relevance_candidates is None:
            min_relevance_candidates = [0.20, 0.25, 0.30, 0.35, 0.40]

        base_config = {k: dict(v) for k, v in SEARCH_CONFIG.items()}
        all_results = []

        for threshold in threshold_candidates:
            for min_rel in min_relevance_candidates:
                test_config = {
                    k: {**cfg, "distance_threshold": threshold}
                    for k, cfg in base_config.items()
                }

                metrics = self.evaluate_config(test_config, min_rel)
                all_results.append({
                    "threshold": threshold,
                    "min_relevance_score": min_rel,
                    "metrics": metrics
                })
                print(f"✓ threshold={threshold} | min_rel={min_rel} → F1={metrics['global']['f1']}")

        # Sauvegarde
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        out_dir = f"benchmark/results/{timestamp}"
        os.makedirs(out_dir, exist_ok=True)

        with open(f"{out_dir}/grid_search.json", "w", encoding="utf-8") as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)

        best = max(all_results, key=lambda x: x["metrics"]["global"]["f1"])
        print(f"\n🏆 MEILLEUR : threshold={best['threshold']}, min_rel={best['min_relevance_score']}")
        print(f"   F1={best['metrics']['global']['f1']}, P={best['metrics']['global']['precision']}, R={best['metrics']['global']['recall']}")

        return best, all_results


if __name__ == "__main__":
    runner = BenchmarkRunner()
    best_config, all_results = runner.grid_search()
