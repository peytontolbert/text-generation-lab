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
STAGE = 10079
NAME = "stage10079_canonical_harness_runner_plan"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PLAN = OUT_DIR / "canonical_harness_runner_plan.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CANONICAL_HARNESS_RUNNER_PLAN_STAGE10079.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

SOURCE_PACKETS = ROOT / "runs/local/artifacts/stage9756_full_product_harness_review_packets/full_product_harness_review_packets.jsonl"
COMPARISON = ROOT / "runs/local/artifacts/stage10072_canonical_label_aligned_same_manifest_comparison_audit/canonical_label_aligned_same_manifest_comparison_audit.json"
READINESS = ROOT / "runs/local/artifacts/stage10075_canonical_label_aligned_claim_readiness_matrix/canonical_label_aligned_claim_readiness_matrix.json"
BOUNDARY = ROOT / "runs/local/artifacts/stage10078_canonical_v27_completion_boundary/canonical_v27_completion_boundary.json"

LANGUAGE_ORDER = ["python", "rust", "c_cpp", "web_js_ts_html"]
TARGET_CELLS = {
    f"full_product_harness::{language}::edit_localization"
    for language in LANGUAGE_ORDER
}
SUPPORT_MODULES = {
    "golden_locked_eval_suite": ROOT / "scripts/golden_locked_eval_suite.py",
    "traced_eval_observability": ROOT / "scripts/traced_eval_observability.py",
    "patch_minimality_complexity_meter": ROOT / "scripts/patch_minimality_complexity_meter.py",
    "semantic_equivalence_metamorphic_verifier": ROOT / "scripts/semantic_equivalence_metamorphic_verifier.py",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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


def support_module_status() -> dict[str, dict[str, Any]]:
    return {
        name: {
            "path": display(path),
            "present": path.exists(),
        }
        for name, path in SUPPORT_MODULES.items()
    }


def _runner_steps() -> list[str]:
    return [
        "load_canonical_harness_proxy_packet",
        "verify_stage10072_same_manifest_win_and_stage10078_completion_boundary",
        "record_real_harness_run_id_only_after_execution",
        "capture_same_task_pack_artifacts_for_100m_and_gemma_on_identical_task_pack",
        "collect_tool_trace_spans_from_full_product_run",
        "collect_verifier_results_and_patch_minimality_or_abstain_scores",
        "attach_human_rubric_and_cell_specific_anti_cheat_after_machine_artifacts_are_real",
    ]


def _write_json(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return display(path)


def _runtime_contract_payload(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "cell_key": plan.get("cell_key"),
        "proxy_standalone_cell_key": plan.get("proxy_standalone_cell_key"),
        "language_family": plan.get("language_family"),
        "skill_area": plan.get("skill_area"),
        "runner_mode": "dry_run_contract_only",
        "executable_now": False,
        "runtime_integration_ready": True,
        "remaining_machine_gap": plan.get("remaining_machine_gap"),
        "remaining_human_gates": list(plan.get("remaining_human_gates") or []),
        "required_artifacts": list(plan.get("required_artifacts") or []),
        "artifact_paths": dict(plan.get("artifact_paths") or {}),
        "runner_steps": list(plan.get("runner_steps") or []),
        "support_modules": support_module_status(),
        "standalone_proxy_frontier": dict(plan.get("standalone_proxy_frontier") or {}),
        "authority": dict(AUTHORITY_CLOSED),
    }


def _packet_index() -> dict[str, dict[str, Any]]:
    rows = [
        row for row in load_jsonl(SOURCE_PACKETS)
        if str(row.get("cell_key") or "") in TARGET_CELLS
    ]
    return {str(row.get("cell_key") or ""): row for row in rows}


def build_plan() -> dict[str, Any]:
    packets = _packet_index()
    comparison = load_json(COMPARISON)
    readiness = load_json(READINESS)
    boundary = load_json(BOUNDARY)
    failures: list[str] = []
    support = support_module_status()

    per_language = ((comparison.get("metrics") or {}).get("per_language") or {})
    readiness_rows = {
        str(row.get("language_family") or ""): row
        for row in (readiness.get("rows") or [])
        if isinstance(row, dict)
    }
    boundary_rows = {
        str(row.get("language_family") or ""): row
        for row in (boundary.get("language_rows") or [])
        if isinstance(row, dict)
    }

    if comparison.get("passed") is not True:
        failures.append("stage10072_not_passed")
    if readiness.get("passed") is not True:
        failures.append("stage10075_not_passed")
    if boundary.get("passed") is not True:
        failures.append("stage10078_not_passed")

    cell_plans: list[dict[str, Any]] = []
    for language in LANGUAGE_ORDER:
        cell_key = f"full_product_harness::{language}::edit_localization"
        packet = packets.get(cell_key)
        compare = per_language.get(language)
        ready = readiness_rows.get(language)
        boundary_row = boundary_rows.get(language)
        if not isinstance(packet, dict):
            failures.append(f"missing_harness_packet:{cell_key}")
            continue
        if not isinstance(compare, dict):
            failures.append(f"missing_comparison_language:{language}")
            continue
        if not isinstance(ready, dict):
            failures.append(f"missing_readiness_language:{language}")
            continue
        if not isinstance(boundary_row, dict):
            failures.append(f"missing_boundary_language:{language}")
            continue
        paths = packet.get("review_packet_paths") if isinstance(packet.get("review_packet_paths"), dict) else {}
        required_paths = {
            key: str(paths.get(key) or "")
            for key in [
                "packet_dir",
                "harness_run_id",
                "same_task_pack_as_gemma12b",
                "tool_trace_spans",
                "verifier_results",
                "patch_minimality_or_abstain_scores",
                "expert_maintainer_rubric_scores",
                "anti_cheat_cards",
            ]
        }
        missing_paths = [key for key, rel in required_paths.items() if not rel]
        if missing_paths:
            failures.append(f"missing_packet_paths:{cell_key}:{','.join(missing_paths)}")
            continue
        existing_stub_status = {key: (ROOT / rel).exists() for key, rel in required_paths.items() if key != "packet_dir"}
        if not all(existing_stub_status.values()):
            failures.append(f"missing_stub_file:{cell_key}")
        plan = {
            "cell_key": cell_key,
            "proxy_standalone_cell_key": f"standalone_100m_weights::{language}::edit_localization",
            "language_family": language,
            "skill_area": "edit_localization",
            "runner_surface_status": "dry_run_contract_ready_real_harness_runtime_still_missing",
            "required_artifacts": list(packet.get("harness_execution_template", {}).get("required_artifacts") or []),
            "artifact_paths": required_paths,
            "existing_stub_status": existing_stub_status,
            "standalone_proxy_frontier": {
                "strict_exact_100m": compare.get("hundred_m_exact"),
                "strict_exact_gemma": compare.get("gemma_exact"),
                "strict_verdict": compare.get("verdict"),
                "rows": compare.get("rows"),
                "same_surface_comparison_stage": 10072,
                "same_surface_shortcut_audit_stage": 10068,
                "claim_readiness_stage": 10075,
                "completion_boundary_stage": 10078,
            },
            "remaining_machine_gap": "real_full_product_harness_runtime_integration_and_capture",
            "remaining_human_gates": [
                "expert_maintainer_rubric_scores",
                "anti_cheat_cards",
            ],
            "standalone_signoff_state": {
                "expert_review_attached": ready.get("expert_review_attached") is True,
                "anti_cheat_card_attached": ready.get("anti_cheat_card_attached") is True,
                "human_signoff_completed": ready.get("human_signoff_completed") is True,
                "standalone_same_surface_win": boundary_row.get("standalone_same_surface_win") is True,
                "standalone_human_signoff_tasks_remaining": boundary_row.get("standalone_human_signoff_tasks_remaining"),
            },
            "runner_steps": _runner_steps(),
            "support_modules": support,
        }
        packet_dir = ROOT / required_paths["packet_dir"]
        plan["runner_plan_path"] = _write_json(packet_dir / "harness_runner_plan.json", plan)
        plan["runtime_contract_path"] = _write_json(packet_dir / "harness_runtime_contract.json", _runtime_contract_payload(plan))
        cell_plans.append(plan)

    metrics = {
        "canonical_harness_proxy_cells": len(cell_plans),
        "cell_plans_written": sum(1 for row in cell_plans if row.get("runner_plan_path")),
        "runtime_contracts_written": sum(1 for row in cell_plans if row.get("runtime_contract_path")),
        "cells_with_all_stub_paths_present": sum(1 for row in cell_plans if all((row.get("existing_stub_status") or {}).values())),
        "cells_with_canonical_100m_better_proxy": sum(1 for row in cell_plans if str((row.get("standalone_proxy_frontier") or {}).get("strict_verdict") or "") == "100m_better"),
    }
    if metrics["canonical_harness_proxy_cells"] != 4:
        failures.append("canonical_harness_proxy_cells_not_4")
    if metrics["cell_plans_written"] != 4:
        failures.append("cell_plans_written_not_4")
    if metrics["runtime_contracts_written"] != 4:
        failures.append("runtime_contracts_written_not_4")
    if metrics["cells_with_all_stub_paths_present"] != 4:
        failures.append("cells_with_all_stub_paths_present_not_4")
    if metrics["cells_with_canonical_100m_better_proxy"] != 4:
        failures.append("cells_with_canonical_100m_better_proxy_not_4")

    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "cell_plans": cell_plans,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_plan()
    PLAN.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Use the four canonical harness_runner_plan.json files to drive the external full-product backend on the same locked task packs, because the proxy frontier is now aligned to stage10072 and the remaining gap is only real runtime execution."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"]},
        "artifacts": {"plan": display(PLAN), "doc": display(DOC)},
        "decision": "Refreshed the four full-product harness runtime contracts so they now proxy to the canonical stage10072 same-manifest winner instead of the stale weighted frontier while preserving the same reserved artifact slots for external execution.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage10079 Canonical Harness Runner Plan",
        "",
        f"Passed: `{summary['passed']}`",
        f"Canonical harness proxy cells: `{summary['metrics']['canonical_harness_proxy_cells']}`",
        f"Runtime contracts written: `{summary['metrics']['runtime_contracts_written']}`",
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
