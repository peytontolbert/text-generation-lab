#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11584
NAME = "stage11584_web_objective_readiness_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_objective_readiness_audit.json"

STAGE11582 = SUMMARIES / "stage11582_web_verifier_attached_postrun_audit.json"
STAGE11580_ROWS = ART / "stage11580_web_verifier_attached_admission_package/web_verifier_attached_rows.jsonl"
TRAINING_LOOP = ROOT / "legacy_src/agentkernel_lite/training_loop.py"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    audit = load_json(STAGE11582)
    rows = load_jsonl(STAGE11580_ROWS)
    loop_text = TRAINING_LOOP.read_text(encoding="utf-8")
    train_rows = [row for row in rows if row.get("trainable_now")]
    contrast_coverage = {
        "current_contrast_function_present": "_bounded_choice_contrast_spec" in loop_text,
        "current_contrast_evidence_only": 'if _prompt_perspective(row) != "evidence_citation":' in loop_text,
        "current_contrast_candidate_verifier_only": '"candidate_change_surface"' in loop_text and '"verifier_and_test_constraint"' in loop_text,
        "non_evidence_contrast_supported": False,
        "same_root_listwise_supported": False,
    }
    train_task_counts = Counter(str(row.get("task_type")) for row in train_rows)
    non_evidence_rows = sum(count for task, count in train_task_counts.items() if task != "evidence_citation")
    blocker_reasons = []
    if audit.get("decision") != "promote_if_all_gates_pass":
        blocker_reasons.append("stage11581_postrun_failed_promotion_gates")
    if contrast_coverage["current_contrast_evidence_only"] and non_evidence_rows:
        blocker_reasons.append("trainer_contrast_does_not_cover_non_evidence_web_tasks")
    if not contrast_coverage["same_root_listwise_supported"]:
        blocker_reasons.append("same_root_candidate_listwise_objective_missing")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "objective_change_required_before_more_web_training",
        "stage11582_negative_result": {
            "decision": audit.get("decision"),
            "filtered_strict": audit.get("results", {}).get("filtered_strict", {}),
            "old_canary_strict": audit.get("results", {}).get("old_canary_strict", {}),
            "residual_bank": audit.get("results", {}).get("residual_bank", {}),
            "web_heldout": audit.get("results", {}).get("web_heldout", {}),
            "web_successor_strict": audit.get("results", {}).get("web_successor_strict", {}),
        },
        "train_package_shape": {
            "train_rows": len(train_rows),
            "train_task_counts": dict(train_task_counts),
            "non_evidence_train_rows": non_evidence_rows,
            "evidence_train_rows": train_task_counts.get("evidence_citation", 0),
            "train_lane_counts": dict(Counter(str(row.get("lane")) for row in train_rows)),
        },
        "trainer_objective_coverage": contrast_coverage,
        "blocker_reasons": blocker_reasons,
        "required_trainer_changes": [
            {
                "name": "task_aware_contrast_specs",
                "description": "Generalize contrast specs beyond evidence_citation to symptom, minimal_fix, verifier_outcome, alternative, and abstention rows.",
                "examples": [
                    "symptom_localization: candidate_change_surface > symptom_or_call_path_distractor when selected source is exercised",
                    "minimal_fix_selection: minimal/local edit surface > broad unrelated utility/config surface",
                    "verifier_outcome: selected verifier/test constraint > insufficiency when passing focused log exists",
                    "abstention_insufficient_evidence: answer_with_visible_evidence > abstain when focused verifier log exists",
                ],
            },
            {
                "name": "same_root_listwise_candidate_loss",
                "description": "Score all options within a root/perspective as a candidate set, not independent short label CE rows.",
            },
            {
                "name": "promotion_metric_feedback",
                "description": "Postrun scoring must include protected canaries, residual bank, Web heldout, and Web successor strict before any promotion.",
            },
        ],
        "next_recommended_stage": "stage11585_web_task_aware_contrast_trainer_patch_or_readiness",
        "claim_boundary": [
            "This is an objective-readiness audit, not a model score.",
            "Stage11581 is diagnostic-only and should not be promoted.",
            "More Web training with the same CE-only/non-evidence objective is likely to repeat the regression.",
        ],
        "source_artifacts": {
            "stage11582": rel(STAGE11582),
            "stage11580_rows": rel(STAGE11580_ROWS),
            "training_loop": rel(TRAINING_LOOP),
        },
        "outputs": {"summary": rel(SUMMARY)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "blocker_reasons": blocker_reasons, "required_trainer_changes": summary["required_trainer_changes"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
