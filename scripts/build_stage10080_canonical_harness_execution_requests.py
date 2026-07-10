#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10080
NAME = "stage10080_canonical_harness_execution_requests"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUESTS = OUT_DIR / "canonical_harness_execution_requests.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CANONICAL_HARNESS_EXECUTION_REQUESTS_STAGE10080.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

PLAN = ROOT / "runs/local/artifacts/stage10079_canonical_harness_runner_plan/canonical_harness_runner_plan.json"
TASK_PACKS = ROOT / "runs/local/artifacts/stage9685_locked_multilingual_task_pack_skeleton/v27_locked_multilingual_task_pack_skeleton.json"


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


def _load_stage10079_module():
    path = ROOT / "scripts" / "build_stage10079_canonical_harness_runner_plan.py"
    spec = importlib.util.spec_from_file_location("stage10079_dependency", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _ensure_plan() -> dict[str, Any]:
    plan = load_json(PLAN)
    if plan.get("passed") is True:
        return plan
    module = _load_stage10079_module()
    built = module.build_plan()
    PLAN.parent.mkdir(parents=True, exist_ok=True)
    PLAN.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return built


def _task_pack_index() -> dict[tuple[str, str, str], dict[str, Any]]:
    packs = load_json(TASK_PACKS).get("benchmark_packs") or []
    return {
        (str(pack.get("mode") or ""), str(pack.get("language_family") or ""), str(pack.get("skill_area") or "")): pack
        for pack in packs if isinstance(pack, dict)
    }


def _write_cell_request(packet_dir: Path, payload: dict[str, Any]) -> str:
    path = packet_dir / "harness_execution_request.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return display(path)


def build_requests() -> dict[str, Any]:
    plan = _ensure_plan()
    if plan.get("passed") is not True:
        return {
            "passed": False,
            "failures": ["stage10079_not_passed"],
            "metrics": {
                "canonical_requests": 0,
                "request_files_written": 0,
                "cells_ready_for_backend_adapter": 0,
            },
            "requests": [],
            "authority": dict(AUTHORITY_CLOSED),
        }
    task_pack_index = _task_pack_index()
    failures: list[str] = []
    rows: list[dict[str, Any]] = []

    for cell in plan.get("cell_plans") or []:
        if not isinstance(cell, dict):
            continue
        task_pack = task_pack_index.get(("full_product_harness", str(cell.get("language_family") or ""), str(cell.get("skill_area") or "")))
        if not isinstance(task_pack, dict):
            failures.append(f"missing_task_pack:{cell.get('cell_key')}")
            continue
        paths = cell.get("artifact_paths") if isinstance(cell.get("artifact_paths"), dict) else {}
        packet_dir = ROOT / str(paths.get("packet_dir") or "")
        request = {
            "cell_key": cell.get("cell_key"),
            "task_pack_id": task_pack.get("task_pack_id"),
            "source_id": task_pack.get("source_id"),
            "lineage_hash": task_pack.get("lineage_hash"),
            "mode": task_pack.get("mode"),
            "language_family": task_pack.get("language_family"),
            "skill_area": task_pack.get("skill_area"),
            "slice_tags": list(task_pack.get("slice_tags") or []),
            "thresholds": dict(task_pack.get("thresholds") or {}),
            "anti_cheat_requirements": list(task_pack.get("anti_cheat_requirements") or []),
            "required_evidence": list(task_pack.get("required_evidence") or []),
            "artifact_paths": dict(paths),
            "support_modules": dict(cell.get("support_modules") or {}),
            "standalone_proxy_frontier": dict(cell.get("standalone_proxy_frontier") or {}),
            "request_status": "awaiting_real_harness_backend_adapter",
            "backend_requirements": [
                "load_locked_task_pack_without_training_contamination",
                "execute_same_task_pack_for_100m_and_gemma12b_against_canonical_stage10086_proxy_frontier",
                "capture_tool_trace_spans",
                "score_verifier_results",
                "score_patch_minimality_or_abstain",
                "write_only_to_reserved_packet_artifact_paths",
            ],
            "authority": dict(AUTHORITY_CLOSED),
        }
        request["request_path"] = _write_cell_request(packet_dir, request)
        rows.append(request)

    metrics = {
        "canonical_requests": len(rows),
        "request_files_written": sum(1 for row in rows if row.get("request_path")),
        "cells_ready_for_backend_adapter": sum(1 for row in rows if row.get("request_status") == "awaiting_real_harness_backend_adapter"),
        "task_packs_resolved": len(rows),
    }
    if metrics["canonical_requests"] != 4:
        failures.append("canonical_requests_not_4")
    if metrics["request_files_written"] != 4:
        failures.append("request_files_written_not_4")
    if metrics["cells_ready_for_backend_adapter"] != 4:
        failures.append("cells_ready_for_backend_adapter_not_4")
    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "requests": rows,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_requests()
    REQUESTS.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Point the external full-product backend at the four canonical harness_execution_request.json files so it can populate the reserved artifact slots on the same locked task packs that stage10086 already won in standalone form."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"]},
        "artifacts": {"requests": display(REQUESTS), "doc": display(DOC)},
        "decision": "Materialized per-cell canonical harness execution requests that bind the external backend to the stage10086 standalone winner and the existing reserved full-product artifact paths.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage10080 Canonical Harness Execution Requests",
        "",
        f"Passed: `{summary['passed']}`",
        f"Canonical requests: `{summary['metrics']['canonical_requests']}`",
        f"Request files written: `{summary['metrics']['request_files_written']}`",
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
