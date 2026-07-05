#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from memory_retrieval_evaluator import evaluate_memories

STAGE = 8772
NAME = "stage8772_memory_retrieval_evaluator_readiness"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "MEMORY_RETRIEVAL_EVALUATOR_READINESS_STAGE8772.md"
AUTHORITY_CLOSED = {"model_execution_authorized_next": False, "decoder_ce_training_authorized_next": False, "denoise_ce_training_authorized_next": False, "runtime_authorized": False, "source_emission_authorized": False, "body_emission_authorized": False, "gemma_execution_authorized_next": False, "harness_execution_authorized_next": False, "scoring_authorized_next": False, "controller_complete_merge_authorized_next": False, "promotion_ready": False}
MEMORIES = [
    {"memory_id": "pass", "relevance_score": 0.9, "staleness_days": 5, "source_id": "src"},
    {"memory_id": "review", "relevance_score": 0.2, "staleness_days": 10, "source_id": "src"},
    {"memory_id": "block", "relevance_score": 0.9, "source_id": "src", "locked_eval_source": True},
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    test = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/test_memory_retrieval_evaluator.py"], cwd=ROOT, text=True, capture_output=True, check=False)
    sample = evaluate_memories(MEMORIES)
    sample_path = OUT_DIR / "memory_retrieval_evaluator_sample_card.json"
    sample_path.write_text(json.dumps(sample, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failures=[]
    if test.returncode != 0:
        failures.append("unit_tests_failed")
    if sample["metrics"]["pass_memories"] != 1 or sample["metrics"]["review_memories"] != 1 or sample["metrics"]["blocked_memories"] != 1:
        failures.append("sample_route_counts_wrong")
    card={"stage": STAGE, "stage_name": NAME, "passed": not failures, "authority": AUTHORITY_CLOSED, "metrics": {**AUTHORITY_CLOSED, "sample_memories": len(MEMORIES), "pass_memories": sample["metrics"]["pass_memories"], "review_memories": sample["metrics"]["review_memories"], "blocked_memories": sample["metrics"]["blocked_memories"], "failures": failures}, "artifacts": {"sample_card": str(sample_path.relative_to(ROOT)), "module": "scripts/memory_retrieval_evaluator.py", "tests": "tests/test_memory_retrieval_evaluator.py"}, "decision": "Memory retrieval evaluator is ready as a no-execution quality/staleness/contamination gate for reusable memories and skills." if not failures else "Memory retrieval evaluator readiness failed.", "next_best_step": "Attach memory_retrieval_evaluator to central graph when commit/reconcile path is clear; attach memory_retrieval_evaluator to central graph, then recover cost_budget_scheduler or source-backed patch operator.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8772 Memory Retrieval Evaluator Readiness", "", f"Passed: `{card['passed']}`", "", "Recovered a no-execution gate for retrieved memories: relevance, staleness, duplicate memory, lineage, contamination, and skill reuse score.", "", "Authority remains closed. This does not mine traces, promote skills, train, score, run runtime, or authorize memory writes.", ""]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)

if __name__ == "__main__":
    main()
