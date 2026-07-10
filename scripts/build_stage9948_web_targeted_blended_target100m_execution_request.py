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
STAGE = 9948
NAME = "stage9948_web_targeted_blended_target100m_execution_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST = OUT_DIR / "web_targeted_blended_target100m_execution_request.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "WEB_TARGETED_BLENDED_TARGET100M_EXECUTION_REQUEST_STAGE9948.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TICKET = ROOT / "runs/local/artifacts/stage9947_web_targeted_blended_structured_execution_review/web_targeted_blended_structured_execution_review_inactive.json"
AUDIT_9946 = ROOT / "runs/local/artifacts/stage9946_web_targeted_blended_target100m_contract_preflight/web_targeted_blended_target100m_contract_preflight_audit.json"

REQUIRED_RUN_ARTIFACTS = [
    "probe_contract_audit.json",
    "loss_by_step.jsonl",
    "eval_loss_by_checkpoint.jsonl",
    "row_field_logits.jsonl",
    "row_field_losses.jsonl",
    "row_gradient_norms.jsonl",
    "activation_summary.jsonl",
    "feature_ablation_attribution.jsonl",
    "activation_patch_recovery.jsonl",
    "row_dynamics_history.jsonl",
    "field_exact_by_cell.json",
    "field_label_vocabs.json",
    "structured_confusion_matrix.json",
    "module_delta_norms.json",
    "failure_bucket_card.json",
    "cleanup_proof.json",
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
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _request_path(surface: str) -> Path:
    return OUT_DIR / "surface_requests" / f"{surface}.json"


def _surface_request(card: dict[str, Any], command: list[str], stage9946_row: dict[str, Any]) -> dict[str, Any]:
    manifest = str(card.get("manifest") or "")
    output_dir = ""
    run_id = ""
    for index, token in enumerate(command):
        if token == "--output-dir" and index + 1 < len(command):
            output_dir = str(command[index + 1])
        if token == "--run-id" and index + 1 < len(command):
            run_id = str(command[index + 1])
    req = {
        "surface": card.get("surface"),
        "request_status": "awaiting_explicit_execution_authorization",
        "manifest": manifest,
        "rows": card.get("rows"),
        "split_counts": dict(card.get("split_counts") or {}),
        "language_counts": dict(card.get("language_counts") or {}),
        "expected_loss": card.get("expected_loss"),
        "output_dir": output_dir,
        "run_id": run_id,
        "command": command,
        "required_runtime_artifacts": list(REQUIRED_RUN_ARTIFACTS),
        "required_contract_invariants": {
            "source_stage9946_contract_passed": bool(stage9946_row.get("contract_passed") is True),
            "source_stage9946_model_execution_attempted": bool(stage9946_row.get("model_execution_attempted")),
            "source_stage9946_unsafe_loss_rows": stage9946_row.get("unsafe_loss_rows"),
            "source_stage9946_missing_required_contract_artifacts": list(stage9946_row.get("missing_required_contract_artifacts") or []),
        },
        "authority": dict(AUTHORITY_CLOSED),
    }
    return req


def build_request() -> dict[str, Any]:
    ticket = load_json(TICKET)
    audit_9946 = load_json(AUDIT_9946)
    failures: list[str] = []

    if ticket.get("ticket_status") != "DESIGN_ONLY_INACTIVE":
        failures.append("stage9947_ticket_not_inactive")
    if ticket.get("execution_authorized_now") is not False:
        failures.append("stage9947_execution_authorized_now")
    if audit_9946.get("passed") is not True:
        failures.append("stage9946_not_passed")

    surface_cards = [row for row in (ticket.get("surface_cards") or []) if isinstance(row, dict)]
    surface_commands = ticket.get("surface_commands") if isinstance(ticket.get("surface_commands"), dict) else {}
    stage9946_rows = {
        str(row.get("surface") or ""): row
        for row in (audit_9946.get("surface_results") or [])
        if isinstance(row, dict)
    }

    rows: list[dict[str, Any]] = []
    for card in surface_cards:
        surface = str(card.get("surface") or "")
        command = surface_commands.get(surface)
        stage9946_row = stage9946_rows.get(surface)
        if not isinstance(command, list):
            failures.append(f"missing_surface_command:{surface}")
            continue
        if not isinstance(stage9946_row, dict):
            failures.append(f"missing_stage9946_surface:{surface}")
            continue
        req = _surface_request(card, [str(item) for item in command], stage9946_row)
        _request_path(surface).parent.mkdir(parents=True, exist_ok=True)
        _request_path(surface).write_text(json.dumps(req, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        rows.append({**req, "request_path": display(_request_path(surface))})

    metrics = {
        "surface_requests": len(rows),
        "surface_request_files_written": sum(1 for row in rows if row.get("request_path")),
        "edit_localization_rows": next((int(row.get("rows") or 0) for row in rows if row.get("surface") == "edit_localization"), 0),
        "edit_localization_web_rows": next((int((row.get("language_counts") or {}).get("web_js_ts_html", 0)) for row in rows if row.get("surface") == "edit_localization"), 0),
        "awaiting_authorization_surfaces": sum(1 for row in rows if row.get("request_status") == "awaiting_explicit_execution_authorization"),
    }
    if metrics["surface_requests"] != 4:
        failures.append("surface_requests_not_4")
    if metrics["surface_request_files_written"] != 4:
        failures.append("surface_request_files_written_not_4")
    if metrics["edit_localization_rows"] != 72:
        failures.append("edit_localization_rows_not_72")
    if metrics["edit_localization_web_rows"] != 27:
        failures.append("edit_localization_web_rows_not_27")
    if metrics["awaiting_authorization_surfaces"] != 4:
        failures.append("awaiting_authorization_surfaces_not_4")

    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "source_artifacts": {
            "ticket": display(TICKET),
            "contract_preflight_audit": display(AUDIT_9946),
        },
        "execution_constraints": {
            "execution_authorized_now": False,
            "model_execution_authorized_now": False,
            "decoder_ce_training_authorized_now": False,
            "requires_explicit_execution_authorization": True,
            "requires_stage9947_ticket": True,
            "requires_stage9946_contract_artifacts": True,
        },
        "surface_requests": rows,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_request()
    REQUEST.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Use the four surface request files from Stage9948 when explicitly authorizing one blended target-100M structured probe series, so execution stays pinned to the Stage9945 web-recovered mix and Stage9946 contract-validated manifests."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {
            "request": display(REQUEST),
            "surface_request_dir": display(OUT_DIR / "surface_requests"),
            "doc": display(DOC),
        },
        "decision": "Materialized the concrete next-run request for the blended multilingual target-100M structured probe, with per-surface commands, required artifacts, and invariants that preserve the targeted web edit-localization refresh.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9948 Web-Targeted Blended Target100M Execution Request",
        "",
        f"Passed: `{summary['passed']}`",
        f"Surface requests: `{built['metrics']['surface_requests']}`",
        f"Edit-localization rows: `{built['metrics']['edit_localization_rows']}`",
        f"Web edit-localization rows: `{built['metrics']['edit_localization_web_rows']}`",
        "",
        summary["decision"],
        "",
        "This is still request-only. It does not authorize or run model execution.",
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
