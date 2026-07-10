#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9956
NAME = "stage9956_v27_current_blocker_ledger"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
LEDGER = OUT_DIR / "v27_current_blocker_ledger.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "V27_CURRENT_BLOCKER_LEDGER_STAGE9956.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

WEIGHTED_FINISH = ROOT / "runs/local/artifacts/stage9935_v27_finish_gate/v27_finish_gate.json"
WEIGHTED_BOUNDARY = ROOT / "runs/local/artifacts/stage9939_v27_completion_boundary/v27_completion_boundary.json"
WEIGHTED_MATRIX = ROOT / "runs/local/artifacts/stage9942_weighted_winner_claim_readiness_matrix_refresh/weighted_winner_claim_readiness_matrix_refresh.json"
BLENDED_PREFLIGHT = ROOT / "runs/local/artifacts/stage9946_web_targeted_blended_target100m_contract_preflight/web_targeted_blended_target100m_contract_preflight_audit.json"
BLENDED_READINESS = ROOT / "runs/local/artifacts/stage9949_web_targeted_blended_execution_readiness_gate/web_targeted_blended_execution_readiness.json"
BLENDED_100M_ACCEPT = ROOT / "runs/local/artifacts/stage9951_blended_edit_localization_output_acceptance_audit/blended_edit_localization_output_acceptance_audit.json"
BLENDED_GEMMA_REQUEST = ROOT / "runs/local/artifacts/stage9952_blended_edit_localization_gemma_request/blended_edit_localization_gemma_queue.json"
BLENDED_COMPARE_GATE = ROOT / "runs/local/artifacts/stage9954_blended_edit_localization_same_manifest_comparison_gate/blended_edit_localization_same_manifest_comparison_gate.json"
BLENDED_HANDOFF = ROOT / "runs/local/artifacts/stage9955_blended_same_manifest_execution_handoff_bundle/blended_same_manifest_execution_handoff_bundle.json"

LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": summary["next_best_step"],
    })
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_ledger() -> dict[str, Any]:
    finish = load_json(WEIGHTED_FINISH)
    boundary = load_json(WEIGHTED_BOUNDARY)
    matrix = load_json(WEIGHTED_MATRIX)
    preflight = load_json(BLENDED_PREFLIGHT)
    readiness = load_json(BLENDED_READINESS)
    accept_100m = load_json(BLENDED_100M_ACCEPT)
    gemma_queue = load_json(BLENDED_GEMMA_REQUEST)
    compare_gate = load_json(BLENDED_COMPARE_GATE)
    handoff = load_json(BLENDED_HANDOFF)
    failures: list[str] = []

    finish_rows = {str(row.get("language_family") or ""): row for row in (finish.get("language_rows") or []) if isinstance(row, dict)}
    boundary_rows = {str(row.get("language_family") or ""): row for row in (boundary.get("language_rows") or []) if isinstance(row, dict)}
    matrix_rows = {str(row.get("language_family") or ""): row for row in (matrix.get("language_rows") or []) if isinstance(row, dict)}
    queue_entries = [row for row in (gemma_queue.get("queue_entries") or []) if isinstance(row, dict)]

    language_rows: list[dict[str, Any]] = []
    for lang in LANGS:
        finish_row = finish_rows.get(lang)
        boundary_row = boundary_rows.get(lang)
        matrix_row = matrix_rows.get(lang)
        if not isinstance(finish_row, dict):
            failures.append(f"missing_finish_row:{lang}")
            continue
        if not isinstance(boundary_row, dict):
            failures.append(f"missing_boundary_row:{lang}")
            continue
        if not isinstance(matrix_row, dict):
            failures.append(f"missing_matrix_row:{lang}")
            continue
        language_rows.append({
            "language_family": lang,
            "standalone_same_surface_win": finish_row.get("standalone_same_surface_win"),
            "standalone_strict_exact_100m": finish_row.get("standalone_strict_exact_100m"),
            "standalone_strict_exact_gemma": finish_row.get("standalone_strict_exact_gemma"),
            "pending_human_signoff_tasks": matrix_row.get("pending_signoff_tasks"),
            "prompt_label_exposure_hardened": matrix_row.get("prompt_label_exposure_hardened"),
            "narrow_machine_supported_claim": matrix_row.get("narrow_machine_supported_claim"),
            "harness_handoff_ready": finish_row.get("harness_backend_handoff_ready"),
            "harness_acceptance_ready": boundary_row.get("harness_acceptance_ready"),
            "remaining_blockers": list(dict.fromkeys([
                *(matrix_row.get("remaining_claim_gaps") or []),
                *(boundary_row.get("remaining_blockers") or []),
            ])),
        })

    narrow_blended_path = {
        "target_surface": "edit_localization",
        "target_scope": "same_manifest_blended_edit_localization_only",
        "preflight_passed": preflight.get("passed") is True,
        "execution_readiness_passed": readiness.get("passed") is True,
        "hundred_m_output_acceptance_ready_now": bool((accept_100m.get("metrics") or {}).get("acceptance_ready")),
        "gemma_queue_entries": len(queue_entries),
        "gemma_ready_when_authorized": bool(queue_entries and queue_entries[0].get("ready_for_gemma_when_authorized") is True),
        "same_manifest_comparison_gate_passed": compare_gate.get("passed") is True,
        "dual_execution_handoff_ready": bool((handoff.get("handoff_bundle") or {}).get("handoff_status") == "ready_for_explicit_dual_execution_authorization"),
        "expected_rows": (accept_100m.get("blend_invariants") or {}).get("expected_rows"),
        "expected_web_rows": (accept_100m.get("blend_invariants") or {}).get("expected_web_rows"),
        "remaining_blockers": [
            "explicit_stage9950_100m_execution_authorization",
            "explicit_stage9953_gemma_execution_authorization",
            "stage9950_outputs_not_present_yet",
            "stage9953_outputs_not_present_yet",
            "same_manifest_comparison_not_executed_yet",
        ],
    }

    metrics = {
        "languages_required": len(LANGS),
        "languages_with_standalone_win": sum(1 for row in language_rows if row["standalone_same_surface_win"]),
        "total_pending_human_signoff_tasks": sum(int(row.get("pending_human_signoff_tasks") or 0) for row in language_rows),
        "languages_with_harness_handoff_ready": sum(1 for row in language_rows if row["harness_handoff_ready"]),
        "languages_with_harness_acceptance_ready": sum(1 for row in language_rows if row["harness_acceptance_ready"]),
        "narrow_blended_path_fully_packaged_locally": all([
            narrow_blended_path["preflight_passed"],
            narrow_blended_path["execution_readiness_passed"],
            narrow_blended_path["gemma_ready_when_authorized"],
            narrow_blended_path["same_manifest_comparison_gate_passed"],
            narrow_blended_path["dual_execution_handoff_ready"],
            narrow_blended_path["expected_rows"] == 72,
            narrow_blended_path["expected_web_rows"] == 27,
        ]),
        "objective_complete": False,
    }

    if metrics["languages_required"] != 4:
        failures.append("languages_required_not_4")
    if metrics["languages_with_standalone_win"] != 4:
        failures.append("languages_with_standalone_win_not_4")
    if metrics["total_pending_human_signoff_tasks"] != 8:
        failures.append("total_pending_human_signoff_tasks_not_8")
    if metrics["languages_with_harness_handoff_ready"] != 4:
        failures.append("languages_with_harness_handoff_ready_not_4")
    if metrics["languages_with_harness_acceptance_ready"] != 0:
        failures.append("languages_with_harness_acceptance_ready_not_0")
    if metrics["narrow_blended_path_fully_packaged_locally"] is not True:
        failures.append("narrow_blended_path_not_fully_packaged_locally")

    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "language_rows": language_rows,
        "narrow_blended_path": narrow_blended_path,
        "completion_boundary": {
            "already_packaged_locally": [
                "weighted_four_language_same_surface_frontier",
                "weighted_review_packet_refresh_and_readiness_matrix",
                "blended_stage9950_100m_execution_path",
                "matching_stage9953_gemma_request_path",
                "same_manifest_comparison_gate_and_handoff_bundle",
            ],
            "still_requires_real_execution_or_external_input": [
                "8_human_signoff_tasks",
                "4_full_product_harness_backend_executions",
                "stage9950_100m_execution",
                "matching_stage9953_gemma_execution",
                "same_manifest_comparison_after_real_outputs",
            ],
            "claim_rule": "Do not claim the 100M beats Gemma on the blended path until both real outputs exist and the stage9954 same-manifest gate conditions are satisfied.",
        },
        "evidence_paths": {
            "weighted_finish_gate": display(WEIGHTED_FINISH),
            "weighted_completion_boundary": display(WEIGHTED_BOUNDARY),
            "weighted_claim_matrix": display(WEIGHTED_MATRIX),
            "blended_preflight": display(BLENDED_PREFLIGHT),
            "blended_readiness": display(BLENDED_READINESS),
            "blended_100m_acceptance": display(BLENDED_100M_ACCEPT),
            "blended_gemma_request": display(BLENDED_GEMMA_REQUEST),
            "blended_compare_gate": display(BLENDED_COMPARE_GATE),
            "blended_handoff_bundle": display(BLENDED_HANDOFF),
        },
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_ledger()
    LEDGER.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "If execution is explicitly authorized, use the stage9955 handoff bundle to run the narrow blended 100M and Gemma comparison path; in parallel, complete the 8 human signoff tasks and obtain the 4 external harness outputs needed for the full objective."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {"ledger": display(LEDGER), "doc": display(DOC)},
        "decision": "Refreshed the current v2.7 blocker ledger so the repo now distinguishes the fully packaged local narrow blended comparison path from the still-missing real executions, human signoff, and external harness outputs.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9956 V27 Current Blocker Ledger",
        "",
        f"Passed: `{summary['passed']}`",
        f"Languages with standalone win: `{built['metrics']['languages_with_standalone_win']}`",
        f"Pending human signoff tasks: `{built['metrics']['total_pending_human_signoff_tasks']}`",
        f"Languages with harness handoff ready: `{built['metrics']['languages_with_harness_handoff_ready']}`",
        f"Narrow blended path fully packaged locally: `{built['metrics']['narrow_blended_path_fully_packaged_locally']}`",
        "",
        summary["decision"],
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "metrics": built["metrics"],
        "failures": built["failures"],
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
