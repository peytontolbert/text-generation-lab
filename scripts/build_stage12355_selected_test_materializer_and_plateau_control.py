#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12355_selected_test_materializer_and_plateau_control"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
CURRENT_LEDGER = ROOT / "runs/summaries/stage12352_combined_train_support_ledger_v4.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ledger = read_json(CURRENT_LEDGER)
    control = {
        "stage": STAGE,
        "decision": "selected_test_materializer_contract_and_plateau_caps_ready",
        "training_allowed": False,
        "claim_boundary": "Control artifact only. No train-support, strict eval, Level-3, patch-trace, repair, or sealed eval row is admitted.",
        "current_ledger_ref": str(CURRENT_LEDGER),
        "current_train_support_rows": ledger.get("current_admitted_train_support_tasks"),
        "current_remaining_gap_to_500": ledger.get("remaining_gap_to_500"),
        "current_language_counts": ledger.get("language_counts"),
        "current_source_counts": ledger.get("source_counts"),
        "hard_separation": {
            "train_support_rows": "admitted bounded/structured support only; not proof of frontier or repair",
            "qc_candidates": "candidate records only; cannot count toward 500",
            "level3_closed_loop_rows": "must include state_before, action, observation/verifier, state_delta, stop/continue with same-source lineage",
            "repair_rows": "must prove buggy/failing and fixed/passing under same verifier",
            "sealed_eval_rows": "root-disjoint evaluation rows; not train-support",
        },
        "plateau_caps": {
            "web_selected_test_pass_rows_total_cap_for_500_push": 50,
            "current_web_selected_test_rows": (ledger.get("language_counts") or {}).get("web_js_ts_html", 0),
            "single_repo_family_cap_without_repair_grade_evidence": 5,
            "single_org_family_cap_without_repair_grade_evidence": 10,
            "open_swe_priority_qc_max_per_repo": 3,
            "web_stop_condition": "Stop Web mining after two consecutive PASS/PASS_TO_PASS-only batches with no FAIL_TO_PASS, no patch-effect proof, and no new repo family.",
        },
        "reusable_materializer_contract": {
            "required_config_sections": [
                "stage",
                "tasks",
                "option_template",
                "roots",
            ],
            "required_root_fields": [
                "root_id",
                "repo_family",
                "language_family",
                "repo_path",
                "focused_verifier_command",
                "stdout_path",
                "stderr_path",
                "source_files",
                "test_files",
                "selected_summary",
                "labels_by_task",
            ],
            "required_modules": [
                "config_loader",
                "evidence_adapter",
                "option_renderer",
                "row_renderer",
                "admission_gate",
                "summary_writer",
            ],
            "row_invariants": [
                "all stronger claims false: strict_eval_eligible/source_heldout_admissible/level3_admitted/patch_trace_admitted/repair_claim_admitted",
                "non-empty commit_sha",
                "non-empty source_hash_refs excluding dependency/vendor/generated paths",
                "non-empty full-length test_hash_refs excluding dependency/vendor/generated paths",
                "exactly three opaque options",
                "unique option labels",
                "exactly one semantic_id candidate_0",
                "bounded_choice_target_label == decoder_text == label for candidate_0",
                "input_text exposes only opaque option labels, not semantic ids or target values",
                "row_id and root_lineage_key globally stable",
                "missing evidence routes to blocked_rows, not partial admission",
            ],
            "known_pitfalls_to_eliminate": [
                "per-root copy-paste script drift",
                "executor-level blockers diverging from row-level blockers",
                "stdout_sha256::None or stderr_sha256::None evidence refs",
                "command_hash_only refs that are raw commands rather than hashes",
                "root_index modulo balancing without target-position audit",
                "dependency paths visible in source/test evidence",
                "PASS_TO_PASS selected-test support counted as repair proof",
                "silent skip of missing configured source/test files",
            ],
        },
        "next_source_priority": [
            "non-Web selected-test roots with local focused verifier proof",
            "Open-SWE QC candidates only after safe semantic extraction and deterministic admission",
            "repair-grade before/fail after/pass triples when same-source proof exists",
            "sealed transition slice construction separate from train-support ledger",
        ],
    }
    (OUT / "selected_test_materializer_and_plateau_control.json").write_text(json.dumps(control, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT / "SELECTED_TEST_MATERIALIZER_AND_PLATEAU_CONTROL_STAGE12355.md").write_text(
        "# Stage12355 Selected-Test Materializer And Plateau Control\n\n"
        "Freezes the reusable materializer contract and caps to prevent the 500-row push from becoming easy PASS/PASS_TO_PASS Web inflation.\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(control, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
