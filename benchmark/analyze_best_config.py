# benchmark/analyze_best_config.py
from benchmark.runner import BenchmarkRunner
from app.generation.cv_json_builder import SEARCH_CONFIG
import json

runner = BenchmarkRunner()

best_threshold = 0.8
best_min_rel = 60.0

test_cfg = {}
for k, v in SEARCH_CONFIG.items():
    test_cfg[k] = {**v, "distance_threshold": best_threshold, "min_results": 0, "max_results": 1}

metrics = runner.evaluate_config(test_cfg, best_min_rel)

print("=== GLOBAL ===")
print(json.dumps(metrics["global"], indent=2))

print("\n=== PAR LABEL ===")
for label, stats in metrics["by_label_accuracy"].items():
    print(f"{label:15s} → accuracy: {stats['accuracy']:.1%}  ({stats['correct']}/{stats['total']})")

print("\n=== PAR SECTION ===")
for section, stats in metrics["by_section"].items():
    print(f"{section:25s} → P={stats['precision']}, R={stats['recall']}, F1={stats['f1']}")