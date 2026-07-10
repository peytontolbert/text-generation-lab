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
STAGE = 9972
NAME = "stage9972_blended_weak_language_output_acceptance_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "blended_weak_language_output_acceptance_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BLENDED_WEAK_LANGUAGE_OUTPUT_ACCEPTANCE_AUDIT_STAGE9972.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
CANDIDATE = ROOT / "runs/local/artifacts/stage9967_blended_weak_language_execution_readiness_gate/first_surface_execution_candidate_edit_localization.json"
REQUEST = ROOT / "runs/local/artifacts/stage9966_blended_weak_language_target100m_execution_request/surface_requests/edit_localization.json"


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


def _artifact_state(output_dir: Path, artifact_name: str) -> dict[str, Any]:
    path = output_dir / artifact_name
    exists = path.exists()
    status = _json_status(path)
    text = _read_text(path)
    stub_like = (not exists) or status == "empty_jsonl" or text.strip() == ""
    if artifact_name.endswith(".json") and exists and status is None:
        stub_like = False
    return {
        "path": display(path),
        "exists": exists,
        "status": status,
        "stub_like": stub_like,
    }


def build_audit() -> dict[str, Any]:
    candidate = load_json(CANDIDATE)
    request = load_json(REQUEST)
    failures: list[str] = []

    if candidate.get("selected_surface") != "edit_localization":
        failures.append("candidate_surface_not_edit_localization")
    if request.get("surface") != "edit_localization":
        failures.append("request_surface_not_edit_localization")

    output_dir = ROOT / str(candidate.get("future_output_dir") or "")
    required_runtime_artifacts = list(request.get("required_runtime_artifacts") or [])
    artifact_states = {name: _artifact_state(output_dir, name) for name in required_runtime_artifacts}
    pending = [name for name, state in artifact_states.items() if state["stub_like"]]

    invariants = {
        "expected_rows": request.get("rows"),
        "expected_python_rows": (request.get("language_counts") or {}).get("python"),
        "expected_c_cpp_rows": (request.get("language_counts") or {}).get("c_cpp"),
        "expected_web_rows": (request.get("language_counts") or {}).get("web_js_ts_html"),
        "expected_split_counts": dict(request.get("split_counts") or {}),
        "candidate_weak_language_recovery_preserved": ((candidate.get("blend_invariants") or {}).get("stage9961_weak_language_recovery_preserved") is True),
        "candidate_targeted_web_refresh_preserved": ((candidate.get("blend_invariants") or {}).get("stage9944_targeted_web_refresh_preserved") is True),
        "candidate_request_status": (candidate.get("blend_invariants") or {}).get("request_status"),
    }
    if invariants["expected_rows"] != 120:
        failures.append("expected_rows_not_120")
    if invariants["expected_python_rows"] != 24:
        failures.append("expected_python_rows_not_24")
    if invariants["expected_c_cpp_rows"] != 30:
        failures.append("expected_c_cpp_rows_not_30")
    if invariants["expected_web_rows"] != 45:
        failures.append("expected_web_rows_not_45")
    if invariants["candidate_weak_language_recovery_preserved"] is not True:
        failures.append("candidate_weak_language_recovery_not_preserved")
    if invariants["candidate_targeted_web_refresh_preserved"] is not True:
        failures.append("candidate_targeted_web_refresh_not_preserved")
    if invariants["candidate_request_status"] != "awaiting_explicit_execution_authorization":
        failures.append("candidate_request_status_not_waiting_authorization")

    metrics = {
        "required_runtime_artifacts": len(required_runtime_artifacts),
        "artifacts_present": sum(1 for state in artifact_states.values() if state["exists"]),
        "artifacts_pending": len(pending),
        "acceptance_ready": not pending,
        "future_output_dir_exists": output_dir.exists(),
        "expected_rows": invariants["expected_rows"],
        "expected_python_rows": invariants["expected_python_rows"],
        "expected_c_cpp_rows": invariants["expected_c_cpp_rows"],
        "expected_web_rows": invariants["expected_web_rows"],
    }
    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "future_run": {
            "future_stage": candidate.get("future_stage"),
            "future_run_id": candidate.get("future_run_id"),
            "future_output_dir": display(output_dir),
            "selected_surface": candidate.get("selected_surface"),
        },
        "blend_invariants": invariants,
        "artifact_states": artifact_states,
        "pending_artifacts": pending,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    audit = build_audit()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Rerun this audit after Stage9965 execution writes outputs; acceptance requires the future output dir to exist and every required runtime artifact to become non-stub while preserving the blended 120-row / 24-python / 30-c_cpp / 45-web edit-localization contract."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit["metrics"], "failures": audit["failures"]},
        "artifacts": {"audit": display(AUDIT), "doc": display(DOC)},
        "decision": "Materialized a post-run acceptance audit for the weak-language successor target-100M execution candidate so future Stage9965 outputs can be checked against the required artifact set and the preserved python/c_cpp/web recovery invariants.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9972 Blended Weak-Language Output Acceptance Audit",
        "",
        f"Passed: `{summary['passed']}`",
        f"Required runtime artifacts: `{audit['metrics']['required_runtime_artifacts']}`",
        f"Artifacts present now: `{audit['metrics']['artifacts_present']}`",
        f"Artifacts pending now: `{audit['metrics']['artifacts_pending']}`",
        f"Acceptance ready now: `{audit['metrics']['acceptance_ready']}`",
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
        "metrics": audit["metrics"],
        "failures": audit["failures"],
    }, indent=2, sort_keys=True))
    if audit["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
