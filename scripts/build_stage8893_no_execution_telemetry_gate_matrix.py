#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8893
NAME = "stage8893_no_execution_telemetry_gate_matrix"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "NO_EXECUTION_TELEMETRY_GATE_MATRIX_STAGE8893.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"

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

MATRIX = {
    "curriculum_compiler_loss_gate": {
        "test_file": "tests/test_curriculum_compiler.py",
        "markers": [
            "test_compiler_blocks_decoder_and_denoise_by_default",
            "test_compiler_allows_decoder_when_explicit",
            "test_compiler_requires_recovered_gate_status_when_enabled",
            'loss_counts"]["decoder_ce"] == 0',
            'loss_counts"]["denoise_ce"] == 0',
        ],
    },
    "native_probe_preflight_gate": {
        "test_file": "tests/test_native_probe_preflight_gate.py",
        "markers": [
            "test_preflight_accepts_closed_tiny_structured_plan",
            "test_preflight_rejects_missing_artifact_gate",
            "test_preflight_rejects_decoder_weight_for_structured_mode",
            "test_preflight_rejects_large_caps_and_unsafe_cleanup",
            "test_preflight_rejects_output_outside_runs_local",
            "denoise_ce_training_authorized_next",
        ],
    },
    "model_output_packet_telemetry_contract": {
        "test_file": "tests/test_model_output_packet_telemetry_contract_builder.py",
        "markers": [
            "test_contract_rows_require_packet_checks_and_telemetry",
            "test_contract_card_remains_closed_and_complete",
            "REQUIRED_PACKET_FIELDS",
            "REQUIRED_CHECKS",
            "REQUIRED_TELEMETRY",
            "forbidden_visible_rows",
        ],
    },
    "model_output_capture_preflight_audit": {
        "test_file": "tests/test_model_output_capture_preflight_audit.py",
        "markers": [
            "test_capture_preflight_audit_passes_closed_design",
            "test_capture_preflight_audit_catches_execution_authority",
            "execution_allowed_rows",
            "authority_open_rows",
        ],
    },
    "closed_bounded_decoder_ce_gate": {
        "test_file": "tests/test_bounded_decoder_ce_package_gate_builder.py",
        "markers": [
            "test_candidate_arg_still_keeps_decoder_ce_closed",
            "test_retrieve_more_is_blocked_not_candidate",
            "test_missing_gate_status_is_hard_blocker",
            "decoder_ce_eligible_now",
            'loss_mask"]["decoder_ce"] is False',
        ],
    },
    "source_backed_decoder_target_materialization": {
        "test_file": "tests/test_source_backed_decoder_target_materialization_builder.py",
        "markers": [
            "test_materializes_target_store_without_putting_text_in_manifest",
            "test_blocked_rows_do_not_get_target_store_entries",
            "test_card_counts_materialized_rows_and_closed_authority",
            "target_text not in str(row)",
            "decoder_ce_eligible_now_rows",
        ],
    },
    "output_repair_denoise_controls": {
        "test_file": "tests/test_output_repair_denoise_controls_builder.py",
        "markers": [
            "test_repair_candidate_keeps_denoise_ce_closed",
            "test_abstain_blocks_denoise_candidate",
            "test_no_raw_text_flags_visible",
            "denoise_ce_eligible_now",
            'loss_mask"]["denoise_ce"] is False',
        ],
    },
    "verifier_guided_repair_target_materialization": {
        "test_file": "tests/test_verifier_guided_repair_target_materialization_builder.py",
        "markers": [
            "test_verifier_guided_materialization_keeps_targets_out_of_manifest",
            "test_verifier_guided_materialization_card_closes_authority_and_losses",
            "denoise_ce_eligible_now_rows",
            "runtime_verifier_execution_eligible_now_rows",
            "target_text_copied_to_manifest_rows",
        ],
    },
    "authority_ticket_and_inactive_execution": {
        "test_file": "tests/test_stage888x_inactive_authority_tickets.py",
        "markers": [
            "test_stage8890_inactive_ticket_cannot_execute_or_train",
            "test_metadata_inventory_inactive_ticket_reads_nothing_and_protects_arxiv",
            "test_stage8889_summary_and_registry_frontier_remains_closed",
            "compute_decoder_ce",
            "compute_denoise_ce",
            "allowed_operations"]
    },
}

SOURCE_SUMMARIES = [
    ROOT / "runs/summaries/stage8891_no_execution_control_plane_regression_audit.json",
    ROOT / "runs/summaries/stage8873_verifier_guided_repair_target_materialization_audit.json",
    ROOT / "runs/summaries/stage8809_registry_spine_reconciliation_after_target_materialization.json",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def check_file_markers(rel: str, markers: list[str]) -> dict[str, Any]:
    path = ROOT / rel
    if not path.exists():
        return {"test_file": rel, "passed": False, "missing_markers": markers, "exists": False}
    text = path.read_text(encoding="utf-8")
    missing = [marker for marker in markers if marker not in text]
    return {"test_file": rel, "passed": not missing, "missing_markers": missing, "exists": True}


def build_matrix_audit(registry: dict[str, Any], summaries: list[dict[str, Any]]) -> dict[str, Any]:
    matrix_checks = []
    failures: list[str] = []
    for gate_name, spec in MATRIX.items():
        check = check_file_markers(spec["test_file"], spec["markers"])
        check["gate_name"] = gate_name
        matrix_checks.append(check)
        if not check["passed"]:
            failures.append(f"missing_matrix_markers:{gate_name}:{','.join(check['missing_markers'])}")
    for path, summary in zip(SOURCE_SUMMARIES, summaries):
        if not path.exists():
            failures.append(f"missing_source_summary:{path.relative_to(ROOT)}")
        elif summary.get("passed") is not True:
            failures.append(f"failed_source_summary:{summary.get('stage_name')}")
        elif any((summary.get("authority") or {}).values()):
            failures.append(f"authority_open_source_summary:{summary.get('stage_name')}")
    authority_counts = (registry.get("metrics") or {}).get("authority_counts") or {}
    if any(authority_counts.get(key, 0) != 0 for key in AUTHORITY_CLOSED):
        failures.append("registry_authority_counts_nonzero")
    latest_stage = (registry.get("metrics") or {}).get("latest_stage")
    if latest_stage not in {8891, 8892, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest_stage}")
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "failures": failures,
            "matrix_gate_count": len(MATRIX),
            "matrix_gates_passing": sum(1 for check in matrix_checks if check["passed"]),
            "source_summaries_checked": len(SOURCE_SUMMARIES),
            "registry_latest_stage_before_update": latest_stage,
            "registry_authority_counts_zero": not any(authority_counts.get(key, 0) != 0 for key in AUTHORITY_CLOSED),
            "model_execution_authorized_now": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
        },
        "matrix_checks": matrix_checks,
        "source_summaries": [str(path.relative_to(ROOT)) for path in SOURCE_SUMMARIES],
        "decision": "No-execution telemetry/gate matrix passed. Closed compiler, preflight, packet telemetry, decoder, denoise, verifier-target, and inactive-ticket gates have concrete regression markers." if not failures else "No-execution telemetry/gate matrix failed.",
        "next_best_step": "Keep Stage8890 reserved for explicit future one-run authorization. Continue no-execution hardening only if adding new gates; otherwise choose a deliberate authorization or inventory branch.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def main() -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    summaries = [load_json(path) for path in SOURCE_SUMMARIES]
    card = build_matrix_audit(registry, summaries)
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8893 No-Execution Telemetry Gate Matrix",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This stage hardens no-execution telemetry and gate coverage by checking concrete regression markers across:",
        "",
        *[f"- `{name}` -> `{spec['test_file']}`" for name, spec in MATRIX.items()],
        "",
        "It opens no model execution, training, decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, mining, checkpoint export, controller merge, or promotion.",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": card["passed"],
        "path": str(SUMMARY),
        "authority": AUTHORITY_CLOSED,
        "next_best_step": card["next_best_step"],
    })
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = card["passed"]
    registry["metrics"] = {
        **registry.get("metrics", {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": card["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8893 No-Execution Telemetry Gate Matrix"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8893 verifies concrete regression markers across the no-execution telemetry/gate matrix: curriculum compiler loss masks, native probe preflight, packet telemetry, capture preflight, bounded decoder CE, source-backed target materialization, output-repair denoise controls, verifier-guided repair targets, and inactive authority tickets.",
            "",
            "This is hardening only. It opens no execution, training, decoder CE, denoise CE, runtime, mining, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, or promotion.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
