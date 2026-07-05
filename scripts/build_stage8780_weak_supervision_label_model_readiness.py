#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from weak_supervision_label_model import label_model_card

STAGE = 8780
NAME = "stage8780_weak_supervision_label_model_readiness"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "WEAK_SUPERVISION_LABEL_MODEL_READINESS_STAGE8780.md"
AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}
ROWS = [
    {"row_id": "agree", "votes": [{"source": "verifier", "label": "CORRECT_PRIOR", "confidence": 0.95}, {"source": "static_analysis", "label": "CORRECT_PRIOR", "confidence": 0.9}]},
    {"row_id": "review", "votes": [{"source": "teacher", "label": "COPY_PRIOR", "confidence": 0.7}, {"source": "teacher", "label": "RETRIEVE_MORE", "confidence": 0.69}]},
    {"row_id": "abstain", "votes": [{"source": "verifier", "label": "CORRECT_PRIOR", "confidence": 1.0, "locked_eval_source": True}]},
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    test = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "tests/test_weak_supervision_label_model.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    sample = label_model_card(ROWS)
    sample_path = OUT_DIR / "weak_supervision_label_model_sample_card.json"
    sample_path.write_text(json.dumps(sample, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failures = []
    if test.returncode != 0:
        failures.append("unit_tests_failed")
    if sample["metrics"]["accepted_shadow_rows"] != 1:
        failures.append("sample_accept_count_wrong")
    if sample["metrics"]["review_rows"] != 1:
        failures.append("sample_review_count_wrong")
    if sample["metrics"]["abstain_rows"] != 1:
        failures.append("sample_abstain_count_wrong")
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "sample_rows": len(ROWS),
            "accepted_shadow_rows": sample["metrics"]["accepted_shadow_rows"],
            "review_rows": sample["metrics"]["review_rows"],
            "abstain_rows": sample["metrics"]["abstain_rows"],
            "authority_rows": sample["metrics"]["authority_rows"],
            "failures": failures,
        },
        "artifacts": {
            "sample_card": str(sample_path.relative_to(ROOT)),
            "module": "scripts/weak_supervision_label_model.py",
            "tests": "tests/test_weak_supervision_label_model.py",
        },
        "decision": (
            "Weak supervision label model is ready as a shadow-only combiner for heuristic, judge, verifier, teacher, and ranker votes."
            if not failures
            else "Weak supervision label model readiness failed."
        ),
        "next_best_step": "Recover knowledge_graph_memory_store, then latency_resource_observability.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage8780 Weak Supervision Label Model Readiness",
                "",
                f"Passed: `{card['passed']}`",
                "",
                "Recovered a deterministic weak-label combiner for verifier, static-analysis, rubric-judge, teacher, retrieval-ranker, and heuristic votes.",
                "",
                "It emits shadow labels, confidence, margin, conflicts, contaminated-vote ignores, and review/abstain routes.",
                "",
                "Authority remains closed. Weak labels do not authorize training, decoder CE, runtime, source/body emission, or promotion.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
