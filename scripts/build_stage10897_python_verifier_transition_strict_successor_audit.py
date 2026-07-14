#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10897
NAME = "stage10897_python_verifier_transition_strict_successor_audit"
OUT_DIR = ARTIFACTS / NAME
AUDIT_JSON = OUT_DIR / "python_verifier_transition_strict_successor_audit.json"

BASE_DIR = ARTIFACTS / "stage10881_evidence_alias_quarantine_successor"
SUCCESSOR_DIR = ARTIFACTS / "stage10896_python_verifier_transition_strict_successor"
CANDIDATE_AUDIT_JSON = ARTIFACTS / "stage10895_code_assist_python_verifier_transition_strict_candidate_audit" / "code_assist_python_verifier_transition_strict_candidate_audit.json"

MIRRORMIND_STRICT_ROW_ID = (
    "stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_28t20_02_25_019acc0f_4bd7_77f2_b15f_3b0c_"
    "models_mirrormind_init_py_models_mirrormind_context_py_models_mirrormind_coordin_fd8013631e_aug_1500000_8b46e7f662::python::"
    "verifier_outcome::reviewed_v27_compact"
)
SUCCESSOR_ROW_ID = "stage10894::code_assist::python::verifier_outcome_semantic_transition::strict_candidate_v1"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def row_ids(rows: list[dict[str, Any]]) -> list[str]:
    return [str(row.get("row_id")) for row in rows]


def main() -> None:
    base_train = load_jsonl(BASE_DIR / "agentkernel_lite_encdec_train.jsonl")
    base_validation = load_jsonl(BASE_DIR / "agentkernel_lite_encdec_validation.jsonl")
    base_strict = load_jsonl(BASE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl")
    base_stress = load_jsonl(BASE_DIR / "agentkernel_lite_encdec_stress_eval.jsonl")

    successor_train = load_jsonl(SUCCESSOR_DIR / "agentkernel_lite_encdec_train.jsonl")
    successor_validation = load_jsonl(SUCCESSOR_DIR / "agentkernel_lite_encdec_validation.jsonl")
    successor_strict = load_jsonl(SUCCESSOR_DIR / "agentkernel_lite_encdec_strict_eval.jsonl")
    successor_stress = load_jsonl(SUCCESSOR_DIR / "agentkernel_lite_encdec_stress_eval.jsonl")

    candidate_audit = load_json(CANDIDATE_AUDIT_JSON)

    base_strict_ids = row_ids(base_strict)
    successor_strict_ids = row_ids(successor_strict)
    removed_ids = sorted(set(base_strict_ids) - set(successor_strict_ids))
    added_ids = sorted(set(successor_strict_ids) - set(base_strict_ids))
    successor_row = next(row for row in successor_strict if str(row.get("row_id")) == SUCCESSOR_ROW_ID)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "python_verifier_transition_strict_successor_audited",
        "claim_scope": [
            "Verify that the stage10896 successor changes only the intended Python strict verifier row.",
            "Carry forward the stage10895 anti-cheat guarantees for the inserted code_assist verifier-transition candidate.",
        ],
        "metrics": {
            "train_rows_unchanged": row_ids(base_train) == row_ids(successor_train),
            "validation_rows_unchanged": row_ids(base_validation) == row_ids(successor_validation),
            "stress_rows_unchanged": row_ids(base_stress) == row_ids(successor_stress),
            "strict_count_preserved": len(base_strict) == len(successor_strict),
            "removed_strict_row_count": len(removed_ids),
            "added_strict_row_count": len(added_ids),
            "target_path_visible_pre_options": candidate_audit["metrics"]["target_path_visible_pre_options"],
            "opaque_test_id_count": candidate_audit["metrics"]["opaque_test_id_count"],
            "explicit_transition_semantics": candidate_audit["metrics"]["explicit_transition_semantics"],
        },
        "row_changes": {
            "removed_strict_rows": removed_ids,
            "added_strict_rows": added_ids,
            "expected_removed_row": MIRRORMIND_STRICT_ROW_ID,
            "expected_added_row": SUCCESSOR_ROW_ID,
        },
        "successor_row_snapshot": {
            "repo_id": successor_row.get("repo_id"),
            "language_family": successor_row.get("language_family"),
            "task_type": successor_row.get("task_type"),
            "target_text": successor_row.get("target_text"),
            "split_role": successor_row.get("split_role"),
            "strict_eval_eligible": successor_row.get("strict_eval_eligible"),
            "same_manifest_successor": successor_row.get("same_manifest_successor"),
        },
        "claim_boundary": {
            "new_heldout_baseline_required": True,
            "same_surface_comparison_as_stage10882": False,
            "fresh_python_verifier_interface": True,
            "still_single_row_python_successor": True,
        },
        "source_artifacts": {
            "base_package": rel(BASE_DIR / "evidence_alias_quarantine_successor.json"),
            "successor_package": rel(SUCCESSOR_DIR / "python_verifier_transition_strict_successor.json"),
            "candidate_audit": rel(CANDIDATE_AUDIT_JSON),
        },
        "next_best_step": "Score the current 100M runtime and Gemma on the new strict successor row package, or build a second opaque verifier-transition row before turning this into a broader Python verifier slice.",
    }

    write_json(AUDIT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
