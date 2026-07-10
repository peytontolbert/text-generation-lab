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
STAGE = 10081
NAME = "stage10081_canonical_harness_backend_handoff_bundle"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
BUNDLE = OUT_DIR / "canonical_harness_backend_handoff_bundle.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CANONICAL_HARNESS_BACKEND_HANDOFF_BUNDLE_STAGE10081.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

REQUESTS = ROOT / "runs/local/artifacts/stage10080_canonical_harness_execution_requests/canonical_harness_execution_requests.json"


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


def _load_stage10080_module():
    path = ROOT / "scripts" / "build_stage10080_canonical_harness_execution_requests.py"
    spec = importlib.util.spec_from_file_location("stage10080_dependency", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _ensure_requests() -> dict[str, Any]:
    requests = load_json(REQUESTS)
    if requests.get("passed") is True:
        return requests
    module = _load_stage10080_module()
    built = module.build_requests()
    REQUESTS.parent.mkdir(parents=True, exist_ok=True)
    REQUESTS.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return built


def _runtime_contract(path_str: str) -> dict[str, Any]:
    packet_dir = ROOT / path_str
    contract = packet_dir / "harness_runtime_contract.json"
    return load_json(contract) if contract.exists() else {}


def _write_cell_bundle(packet_dir: Path, payload: dict[str, Any]) -> str:
    path = packet_dir / "harness_backend_handoff_bundle.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return display(path)


def build_bundle() -> dict[str, Any]:
    requests = _ensure_requests().get("requests") or []
    failures: list[str] = []
    rows: list[dict[str, Any]] = []
    for row in requests:
        if not isinstance(row, dict):
            continue
        packet_dir_rel = str((row.get("artifact_paths") or {}).get("packet_dir") or "")
        if not packet_dir_rel:
            failures.append(f"missing_packet_dir:{row.get('cell_key')}")
            continue
        runtime = _runtime_contract(packet_dir_rel)
        if not runtime:
            failures.append(f"missing_runtime_contract:{row.get('cell_key')}")
            continue
        payload = {
            "cell_key": row.get("cell_key"),
            "task_pack_id": row.get("task_pack_id"),
            "source_id": row.get("source_id"),
            "lineage_hash": row.get("lineage_hash"),
            "language_family": row.get("language_family"),
            "skill_area": row.get("skill_area"),
            "handoff_status": "ready_for_external_backend_adapter",
            "why_external_backend_is_required": [
                "locked_task_pack_contains_only_metadata_and_threshold_contracts",
                "no_prompt_or_repo_payload_is_present_in_this_repo_for_full_product_execution",
                "same_task_pack_runtime_must_be_supplied_by_the_external_harness_backend",
            ],
            "backend_must_supply": [
                "same_task_pack_runtime_payload_for_100m_and_gemma12b",
                "tool_trace_spans_capture",
                "verifier_results_capture",
                "patch_minimality_or_abstain_capture",
                "writeback_to_reserved_packet_artifact_paths_only",
            ],
            "required_artifacts": list(row.get("required_evidence") or []),
            "artifact_paths": dict(row.get("artifact_paths") or {}),
            "anti_cheat_requirements": list(row.get("anti_cheat_requirements") or []),
            "thresholds": dict(row.get("thresholds") or {}),
            "standalone_proxy_frontier": dict(row.get("standalone_proxy_frontier") or {}),
            "runtime_contract": runtime,
            "authority": dict(AUTHORITY_CLOSED),
        }
        payload["handoff_bundle_path"] = _write_cell_bundle(ROOT / packet_dir_rel, payload)
        rows.append(payload)

    metrics = {
        "canonical_handoff_cells": len(rows),
        "handoff_bundles_written": sum(1 for row in rows if row.get("handoff_bundle_path")),
        "cells_requiring_external_backend": sum(1 for row in rows if row.get("handoff_status") == "ready_for_external_backend_adapter"),
        "cells_with_canonical_100m_better_proxy": sum(1 for row in rows if str((row.get("standalone_proxy_frontier") or {}).get("strict_verdict") or "") == "100m_better"),
    }
    if metrics["canonical_handoff_cells"] != 4:
        failures.append("canonical_handoff_cells_not_4")
    if metrics["handoff_bundles_written"] != 4:
        failures.append("handoff_bundles_written_not_4")
    if metrics["cells_requiring_external_backend"] != 4:
        failures.append("cells_requiring_external_backend_not_4")
    if metrics["cells_with_canonical_100m_better_proxy"] != 4:
        failures.append("cells_with_canonical_100m_better_proxy_not_4")
    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "handoff_cells": rows,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_bundle()
    BUNDLE.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Hand the four canonical harness_backend_handoff_bundle.json files to the external full-product runtime so it can execute the same locked task pack for 100M and Gemma12b and write back only to the reserved artifact paths."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"]},
        "artifacts": {"bundle": display(BUNDLE), "doc": display(DOC)},
        "decision": "Materialized canonical backend handoff bundles proving the remaining full-product gap is external runtime execution while keeping the handoff aligned with the stage10072 standalone multilingual win.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage10081 Canonical Harness Backend Handoff Bundle",
        "",
        f"Passed: `{summary['passed']}`",
        f"Canonical handoff cells: `{summary['metrics']['canonical_handoff_cells']}`",
        f"Handoff bundles written: `{summary['metrics']['handoff_bundles_written']}`",
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
