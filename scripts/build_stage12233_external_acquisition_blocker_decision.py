#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12233_external_acquisition_blocker_decision"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"


def load(path: str) -> dict[str, Any]:
    p = ROOT / path
    return json.loads(p.read_text()) if p.exists() else {}


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    s12229 = load("runs/summaries/stage12229_patch_trace_projection_qc.json")
    s12232 = load("runs/summaries/stage12232_controlled_fixture_projection_qc.json")
    payload = {
        "stage": STAGE,
        "decision": "external_repair_data_acquisition_required_before_training",
        "implemented_this_pass": {
            "external_patch_trace_projection_qc": s12229,
            "controlled_fixture_projection_qc": s12232,
        },
        "subagent_result": {
            "external_repair_root_acquisition_scout": "0 accepted candidates; current artifacts do not contain comparable external behavior fail-before/pass-after patch roots under strict gates.",
            "controlled_fixture_projection_materializer": "40 QC-passing controlled curriculum rows exist across Python/C++/Rust/Web, training disabled.",
        },
        "hard_training_blockers": [
            "external_comparable_fail_to_pass_patch_trace_rows_zero",
            "non_python_external_patch_trace_rows_zero",
            "controlled_fixture_rows_are_synthetic_curriculum_only",
            "no_trainer_task_routing_for_patch_trace_projection_families_yet",
        ],
        "next_required_source_acquisition_contract": {
            "per_row_required": [
                "repo_family",
                "language_family",
                "before_ref",
                "after_ref",
                "patch_diff_ref",
                "same_selected_verifier_command",
                "before_command_output_behavior_failure",
                "before_plus_patch_command_output_pass",
                "after_command_output_pass",
                "patch_apply_check_output",
                "verifier_touches_changed_source_or_test",
            ],
            "hard_rejects": [
                "test_added_before_missing",
                "syntax_only_compile_error",
                "dependency_or_network_or_gpu_required",
                "weak_anchor_or_unrelated_verifier",
                "build_only_without_runnable_verifier",
            ],
            "minimum_before_training": {
                "external_rows": 25,
                "non_python_rows": 10,
                "fail_to_pass_rows": 15,
                "repo_family_cap_fraction": 0.2,
            },
        },
        "training_allowed": False,
        "claim_boundary": "The data plumbing improved, but the model should not train on this patch-trace lane until external comparable repair supply is acquired and admitted.",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / "external_acquisition_blocker_decision.json", payload)
    write_json(SUMMARY, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
