# benchmark/runner_test_min0.py
"""
Test avec min_results=0 sur TOUTES les sections.
Objectif : voir le vrai pouvoir discriminant du distance_threshold.
"""
import yaml
import json
import os
from datetime import datetime
from typing import Dict
from collections import defaultdict

from app.embedding.embedder import Embedder
from app.embedding.vector_store import VectorStore
from app.generation.cv_json_builder import SEARCH_CONFIG, distance_to_score
from benchmark.judge import judge_chunk_relevance


def is_candidate_relevant_v2(store, query_vec, candidate_id, version_number, min_score=35.0,distance_threshold=2.0):
    critical_sections = ["summary", "skills", "expertise_areas", "experience","project"]
    best_scores = []
    has_any = False
    for section in critical_sections:
        res = store.search_section(
            query_vec, chunk_types=section, candidate_id=candidate_id,
            version_number=version_number, distance_threshold=distance_threshold,
            min_results=0, max_results=3,
        )
        if res:
            has_any = True
            best_scores.append(max(distance_to_score(r["distance"]) for r in res))
        else:
            best_scores.append(0.0)
    if not has_any:
        return False, 0.0
    sections_above = sum(1 for s in best_scores if s >= min_score)
    avg_score = sum(best_scores) / len(best_scores)
    return sections_above >= 1 and avg_score >= (min_score * 0.5), avg_score


class BenchmarkRunner:
    def __init__(self):
        self.embedder = Embedder()
        self.vector_store = VectorStore()
        with open("benchmark/ground_truth.yaml", "r", encoding="utf-8") as f:
            self.benchmark = yaml.safe_load(f)["benchmark"]

    def _embed_text(self, text: str) -> list:
        return self.embedder.model.encode(text).tolist()

    def evaluate_config(self, search_config: Dict, min_relevance_score: float = 35.0) -> Dict:
        results_by_section = defaultdict(lambda: {"vp": 0, "fp": 0, "fn": 0, "vn": 0})
        global_counts = {"tp": 0, "fp": 0, "fn": 0}
        threshold = next(iter(search_config.values()))["distance_threshold"]
        for mission in self.benchmark:
            mission_emb = self._embed_text(mission["mission_text"])
            for case in mission["cases"]:
                cid = case["candidate_id"]
                ver = case.get("version_number")
                expected = set(case["expected_sections"])
                label = case["label"]

                is_rel, avg_s = is_candidate_relevant_v2(
                    self.vector_store, mission_emb, cid, ver, min_relevance_score,threshold
                )

                if label == "non_match" and is_rel:
                    global_counts["fp"] += 1
                elif label != "non_match" and not is_rel:
                    global_counts["fn"] += 1
                elif label != "non_match" and is_rel:
                    global_counts["tp"] += 1

                for section, cfg in search_config.items():
                    chunks = self.vector_store.search_section(
                        query_embedding=mission_emb,
                        chunk_types=section,
                        candidate_id=cid,
                        version_number=ver,
                        distance_threshold=cfg["distance_threshold"],
                        min_results=cfg["min_results"],
                        max_results=cfg["max_results"],
                    )
                    chunk_text = chunks[0].get("text", "") if chunks else ""
                    is_relevant = judge_chunk_relevance(
                        mission["mission_text"], chunk_text, section, label
                    ) if chunks else False
                    should = section in expected

                    if chunks and is_relevant and should:
                        results_by_section[section]["vp"] += 1
                    elif chunks and is_relevant and not should:
                        results_by_section[section]["fp"] += 1
                    elif chunks and not is_relevant and should:
                        results_by_section[section]["fn"] += 1
                    elif not chunks and should:
                        results_by_section[section]["fn"] += 1
                    elif not chunks and not should:
                        results_by_section[section]["vn"] += 1
                    elif chunks and not is_relevant and not should:
                        results_by_section[section]["fp"] += 1

        metrics = {}
        for section, c in results_by_section.items():
            vp, fp, fn = c["vp"], c["fp"], c["fn"]
            p = vp / (vp + fp) if (vp + fp) > 0 else 0
            r = vp / (vp + fn) if (vp + fn) > 0 else 0
            f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0
            metrics[section] = {
                "vp": vp, "fp": fp, "fn": fn, "vn": c["vn"],
                "precision": round(p, 3), "recall": round(r, 3), "f1": round(f1, 3)
            }

        tp, fp, fn = global_counts["tp"], global_counts["fp"], global_counts["fn"]
        gp = tp / (tp + fp) if (tp + fp) > 0 else 0
        gr = tp / (tp + fn) if (tp + fn) > 0 else 0
        gf1 = 2 * gp * gr / (gp + gr) if (gp + gr) > 0 else 0

        return {
            "by_section": metrics,
            "global": {
                "min_relevance_score": min_relevance_score,
                "precision": round(gp, 3),
                "recall": round(gr, 3),
                "f1": round(gf1, 3),
                "details": global_counts,
            }
        }

    def grid_search(self, threshold_candidates=None, min_rel_candidates=None):
        if threshold_candidates is None:
            threshold_candidates = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
        if min_rel_candidates is None:
            min_rel_candidates = [30, 35, 40, 45, 50, 55, 60]

        # SURCHARGE : min_results=0 sur TOUTES les sections
        base = {k: dict(v) for k, v in SEARCH_CONFIG.items()}
        for k in base:
            base[k]["min_results"] = 0
            base[k]["max_results"] = 1  # au plus 1 résultat si pertinent

        all_results = []
        for threshold in threshold_candidates:
            for min_rel in min_rel_candidates:
                test_cfg = {k: {**c, "distance_threshold": threshold} for k, c in base.items()}
                metrics = self.evaluate_config(test_cfg, min_rel)
                all_results.append({
                    "threshold": threshold,
                    "min_relevance_score": min_rel,
                    "metrics": metrics
                })
                print(f"threshold={threshold} | min_rel={min_rel}% -> F1={metrics['global']['f1']}, P={metrics['global']['precision']}, R={metrics['global']['recall']}")

        ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
        out_dir = f"benchmark/results/{ts}"
        os.makedirs(out_dir, exist_ok=True)
        with open(f"{out_dir}/grid_search_min0.json", "w", encoding="utf-8") as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)

        best = max(all_results, key=lambda x: x["metrics"]["global"]["f1"])
        print(f"\n🏆 MEILLEUR : threshold={best['threshold']}, min_rel={best['min_relevance_score']}%")
        print(f"   F1={best['metrics']['global']['f1']}, P={best['metrics']['global']['precision']}, R={best['metrics']['global']['recall']}")
        return best, all_results


if __name__ == "__main__":
    runner = BenchmarkRunner()
    best_config, all_results = runner.grid_search()