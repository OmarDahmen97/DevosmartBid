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
import itertools
from app.embedding.embedder import Embedder
from app.embedding.vector_store import VectorStore
from app.config import SEARCH_CONFIG
from app.generation.cv_json_builder import distance_to_score
from benchmark.judge import judge_chunk_relevance


def is_candidate_relevant_v2(store, query_vec, candidate_id, version_number, min_score=35.0, section_thresholds=None):
    critical_sections = ["summary", "experience", "project"]  # skills/expertise_areas retirés
    if section_thresholds is None:
        section_thresholds = {s: 0.8 for s in critical_sections}

    best_scores = []
    for section in critical_sections:
        threshold = section_thresholds.get(section, 0.8)
        res = store.search_section(
            query_vec, chunk_types=section, candidate_id=candidate_id,
            version_number=version_number, distance_threshold=threshold,
            min_results=0, max_results=3,
        )
        if res:
            best_scores.append(max(distance_to_score(r["distance"]) for r in res))
        # sinon : on n'ajoute rien -> les sections vides ne tirent plus la moyenne vers le bas

    if not best_scores:
        return False, 0.0

    sections_above = sum(1 for s in best_scores if s >= min_score)
    avg_score = sum(best_scores) / len(best_scores)
    return sections_above >= 1 and avg_score >= (min_score * 0.5), avg_score


class BenchmarkRunner:
    # --- grids to sweep, tune ranges based on what we saw in the benchmark ---
    EXPERIENCE_THRESHOLDS = [0.3, 0.35, 0.4]
    SUMMARY_THRESHOLDS = [0.6, 0.7, 0.8]
    MIN_RELEVANCE_SCORES = [30, 35, 40, 45, 50, 55, 60]
 
    # fixed, unchanged across the grid -- adjust if your min/max_results also need tuning
    FIXED_MIN_RESULTS = 1
    FIXED_MAX_RESULTS = 5
 
    # project kept in search_config so is_candidate_relevant_v2 / other callers that
    # expect all 3 keys don't break, but its threshold stays fixed (not swept) since
    # there's nothing to optimize against.
    PROJECT_THRESHOLD = 0.5
 
    def __init__(self):
        self.embedder = Embedder()
        self.vector_store = VectorStore()
        with open("benchmark/ground_truth.yaml", "r", encoding="utf-8") as f:
            self.benchmark = yaml.safe_load(f)["benchmark"]
 
    def _embed_text(self, text: str) -> list:
        return self.embedder.model.encode(text).tolist()
 
    def evaluate_config(self, search_config: Dict, min_relevance_score: float = 35.0) -> Dict:
        TARGET_SECTIONS = ("summary", "experience", "project")
 
        results_by_section = defaultdict(lambda: {"vp": 0, "fp": 0, "fn": 0, "vn": 0})
        global_counts = {"tp": 0, "fp": 0, "fn": 0}
        by_label_counts = defaultdict(lambda: {"correct": 0, "total": 0})
 
        section_thresholds = {section: cfg["distance_threshold"] for section, cfg in search_config.items()}
 
        for mission in self.benchmark:
            mission_emb = self._embed_text(mission["mission_text"])
            for case in mission["cases"]:
                cid = case["candidate_id"]
                ver = case.get("version_number")
                expected = set(case["expected_sections"])
                label = case["label"]
 
                is_rel, avg_s = is_candidate_relevant_v2(
                    self.vector_store, mission_emb, cid, ver, min_relevance_score, section_thresholds
                )
                expected_relevant = label != "non_match"
                by_label_counts[label]["total"] += 1
                if is_rel == expected_relevant:
                    by_label_counts[label]["correct"] += 1
 
                if label == "non_match" and is_rel:
                    global_counts["fp"] += 1
                elif label != "non_match" and not is_rel:
                    global_counts["fn"] += 1
                elif label != "non_match" and is_rel:
                    global_counts["tp"] += 1
 
                for section, cfg in search_config.items():
                    if section not in TARGET_SECTIONS:
                        continue
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
 
        by_label_accuracy = {
            label: {
                "accuracy": round(c["correct"] / c["total"], 3) if c["total"] > 0 else 0,
                "correct": c["correct"],
                "total": c["total"],
            }
            for label, c in by_label_counts.items()
        }
 
        return {
            "by_section": metrics,
            "by_label_accuracy": by_label_accuracy,
            "global": {
                "min_relevance_score": min_relevance_score,
                "precision": round(gp, 3),
                "recall": round(gr, 3),
                "f1": round(gf1, 3),
                "details": global_counts,
            }
        }
 
    def grid_search(self) -> tuple[dict, list[dict]]:
        """
        Sweeps distance_threshold independently for summary/experience, keeps
        project fixed (no positive ground truth cases to optimize against).
        Returns (best_result, all_results).
        """
        results = []
 
        combos = itertools.product(
            self.EXPERIENCE_THRESHOLDS, self.SUMMARY_THRESHOLDS, self.MIN_RELEVANCE_SCORES
        )
        for exp_threshold, sum_threshold, min_rel in combos:
            search_config = {
                "summary": {
                    "distance_threshold": sum_threshold,
                    "min_results": self.FIXED_MIN_RESULTS,
                    "max_results": self.FIXED_MAX_RESULTS,
                },
                "experience": {
                    "distance_threshold": exp_threshold,
                    "min_results": self.FIXED_MIN_RESULTS,
                    "max_results": self.FIXED_MAX_RESULTS,
                },
                "project": {
                    "distance_threshold": self.PROJECT_THRESHOLD,
                    "min_results": self.FIXED_MIN_RESULTS,
                    "max_results": self.FIXED_MAX_RESULTS,
                },
            }
 
            metrics = self.evaluate_config(search_config, min_relevance_score=min_rel)
 
            results.append({
                "experience_threshold": exp_threshold,
                "summary_threshold": sum_threshold,
                "min_relevance_score": min_rel,
                "metrics": metrics,
            })
 
        best = max(results, key=lambda r: r["metrics"]["global"]["f1"])
        return best, results
 
    @staticmethod
    def print_results(results: list[dict]) -> None:
        print(f"{'exp_thr':>8} {'sum_thr':>8} {'min_rel':>8} | F1     P      R")
        for r in results:
            g = r["metrics"]["global"]
            print(f"{r['experience_threshold']:>8} {r['summary_threshold']:>8} "
                  f"{r['min_relevance_score']:>7}% -> F1={g['f1']:<6} P={g['precision']:<6} R={g['recall']}")
 
        best = max(results, key=lambda r: r["metrics"]["global"]["f1"])
        g = best["metrics"]["global"]
        print(f"\n🏆 MEILLEUR : exp_threshold={best['experience_threshold']}, "
              f"summary_threshold={best['summary_threshold']}, min_rel={best['min_relevance_score']}%")
        print(f"   F1={g['f1']}, P={g['precision']}, R={g['recall']}")
        print("\n   by_section:")
        for section, s in best["metrics"]["by_section"].items():
            print(f"     {section}: vp={s['vp']} fp={s['fp']} fn={s['fn']} "
                  f"precision={s['precision']} recall={s['recall']} f1={s['f1']}")
 
 
if __name__ == "__main__":
    runner = BenchmarkRunner()
    best_config, all_results = runner.grid_search()
    runner.print_results(all_results)
    # Sauvegarde
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    out_dir = f"benchmark/results/{timestamp}"
    os.makedirs(out_dir, exist_ok=True)
    with open(f"{out_dir}/grid_search.json", "w", encoding="utf-8") as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)
 