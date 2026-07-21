#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12230_subagent_result_audit"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"


def load(path: str) -> dict[str, Any]:
    p = ROOT / path
    return json.loads(p.read_text()) if p.exists() else {}


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    s12227 = load("runs/summaries/stage12227_subagent_packet_control.json")
    s12229 = load("runs/summaries/stage12229_patch_trace_projection_qc.json")
    payload = {
        "stage": STAGE,
        "source_stage": "stage12227_subagent_packet_control",
        "decision": "subagent_round_complete_next_acquisition_required",
        "subagent_result_summary": {
            "comparable_fail_to_pass_patch_scout": {
                "external_candidates_found": 0,
                "controlled_fixture_candidates_found": 8,
                "decision": "use_only_as_curriculum_or_projection_path_test_not_source_heldout_progress",
            },
            "non_python_hydratable_patch_scout": {
                "accepted_candidates_found": 0,
                "decision": "current_stage12201_stage12217_non_python_pool_exhausted",
            },
            "patch_trace_schema_integrator": {
                "contract_implemented_as": [
                    "configs/schema/patch_trace_projection_record_v1.schema.json",
                    "scripts/build_stage12228_patch_trace_projection_rows.py",
                    "scripts/build_stage12229_patch_trace_projection_qc.py",
                ],
                "qc_result": s12229,
            },
        },
        "active_control": s12227,
        "blockers_remaining": [
            "external_comparable_fail_to_pass_patch_trace_supply_zero",
            "non_python_patch_trace_supply_zero",
            "projection_rows_training_disabled_until_supply_and_task_routing",
            "controlled_fixture_rows_need_separate_curriculum_labeling_if_used",
        ],
        "next_subagent_packets": [
            {
                "name": "external_repair_root_acquisition_scout",
                "objective": "Find new local or easily hydratable external repos/commits with comparable fail-before/pass-after selected verifier evidence across Python/C++/Rust/Web.",
                "hard_rejects": [
                    "test file absent before patch",
                    "syntax-only compile error",
                    "dependency/network/GPU required",
                    "verifier unrelated to changed files",
                    "build-only proof without runnable test or command output",
                ],
            },
            {
                "name": "controlled_fixture_projection_materializer",
                "objective": "Convert Stage12025 controlled fixtures into patch-trace projection rows marked controlled_curriculum_only, preserving language diversity without source-heldout claims.",
                "hard_rejects": [
                    "mix controlled fixtures into external patch-trace rollup",
                    "mark as strict_eval_or_source_heldout",
                    "enable training loss before separate curriculum gate",
                ],
            },
        ],
        "training_allowed": False,
        "claim_boundary": "Subagent round improved clarity and schema; it did not create enough external patch-trace data for training.",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / "subagent_result_audit.json", payload)
    write_json(SUMMARY, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
