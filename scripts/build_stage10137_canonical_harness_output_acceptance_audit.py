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
STAGE = 10137
NAME = "stage10137_canonical_harness_output_acceptance_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "canonical_harness_output_acceptance_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CANONICAL_HARNESS_OUTPUT_ACCEPTANCE_AUDIT_STAGE10137.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
HANDOFF = ROOT / "runs/local/artifacts/stage10081_canonical_harness_backend_handoff_bundle/canonical_harness_backend_handoff_bundle.json"
CHECKED = [
    "harness_run_id",
    "same_task_pack_as_gemma12b",
    "tool_trace_spans",
    "verifier_results",
    "patch_minimality_or_abstain_scores",
    "expert_maintainer_rubric_scores",
    "anti_cheat_cards",
]


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
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0) or 0)),
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _json_status(path: Path) -> str | None:
    if not path.exists() or path.suffix not in {".json", ".jsonl"}:
        return None
    if path.suffix == ".jsonl":
        text = _read_text(path).strip()
        return "empty_jsonl" if not text else "nonempty_jsonl"
    data = load_json(path)
    if isinstance(data, dict):
        status = data.get("status")
        if status is not None:
            return str(status)
    return None


def _artifact_state(path: Path, artifact_name: str) -> dict[str, Any]:
    exists = path.exists()
    text = _read_text(path) if exists else ""
    status = _json_status(path)
    if artifact_name == "harness_run_id":
        stub_like = (not exists) or ("pending_harness_run_id" in text) or (text.strip() in {"", "harness_run_id="})
    elif artifact_name == "tool_trace_spans":
        stub_like = (not exists) or status == "empty_jsonl" or text.strip() == ""
    elif artifact_name in {"same_task_pack_as_gemma12b", "verifier_results", "patch_minimality_or_abstain_scores"}:
        stub_like = (not exists) or (status is not None and status.startswith("pending_"))
    else:
        stub_like = (not exists) or (status is not None and status.startswith("pending_"))
    return {
        "path": display(path),
        "exists": exists,
        "status": status,
        "stub_like": stub_like,
    }


def build_audit() -> dict[str, Any]:
    handoff = load_json(HANDOFF)
    rows = [row for row in (handoff.get("handoff_cells") or []) if isinstance(row, dict)]
    failures: list[str] = []
    records: list[dict[str, Any]] = []
    for row in rows:
        artifact_paths = row.get("artifact_paths") if isinstance(row.get("artifact_paths"), dict) else {}
        states = {}
        for name in CHECKED:
            rel = str(artifact_paths.get(name) or "")
            path = ROOT / rel if rel else Path()
            states[name] = _artifact_state(path, name) if rel else {"path": rel, "exists": False, "status": None, "stub_like": True}
        pending = [name for name, state in states.items() if state["stub_like"]]
        records.append({
            "cell_key": row.get("cell_key"),
            "language_family": row.get("language_family"),
            "artifact_states": states,
            "acceptance_ready": not pending,
            "pending_artifacts": pending,
        })
    metrics = {
        "canonical_cells": len(records),
        "cells_acceptance_ready": sum(1 for row in records if row["acceptance_ready"]),
        "cells_still_stub_only": sum(1 for row in records if not row["acceptance_ready"]),
        "total_pending_artifacts": sum(len(row["pending_artifacts"]) for row in records),
    }
    if metrics["canonical_cells"] != 4:
        failures.append("canonical_cells_not_4")
    return {"passed": not failures, "failures": failures, "metrics": metrics, "records": records, "authority": dict(AUTHORITY_CLOSED)}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    audit = build_audit()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Hand the stage10081 canonical payload to the external runtime, write machine artifacts back through "
        "run_stage10081_canonical_harness_backend_adapter.py, then rerun this audit until every canonical cell replaces stub-like artifacts with real outputs."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit["metrics"], "failures": audit["failures"]},
        "artifacts": {"audit": display(AUDIT), "doc": display(DOC)},
        "decision": "Materialized the canonical harness output acceptance audit so the full-product runtime handoff can be validated mechanically once the external backend writes real artifacts.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage10137 Canonical Harness Output Acceptance Audit",
        "",
        f"Passed: `{summary['passed']}`",
        f"Canonical cells: `{audit['metrics']['canonical_cells']}`",
        f"Cells acceptance ready: `{audit['metrics']['cells_acceptance_ready']}`",
        f"Cells still stub only: `{audit['metrics']['cells_still_stub_only']}`",
        "",
        summary["decision"],
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": audit["metrics"], "failures": audit["failures"]}, indent=2, sort_keys=True))
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
