#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9544
NAME = "stage9544_terminal_pass_rejoin_preflight_contract_audit"
CONTRACT = ROOT / "runs/local/artifacts/stage9543_terminal_pass_rejoin_preflight_contract/terminal_pass_rejoin_preflight_contract.json"
TERMINAL_ROWS = ROOT / "runs/local/artifacts/stage9543_terminal_pass_rejoin_preflight_contract/terminal_pass_rejoin_candidate_rows.jsonl"
RESIDUAL_ROWS = ROOT / "runs/local/artifacts/stage9543_terminal_pass_rejoin_preflight_contract/residual_repair_route_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TERMINAL_PASS_REJOIN_PREFLIGHT_CONTRACT_AUDIT_STAGE9544.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def update_registry(summary: dict) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
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
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")


def enabled_losses(rows: list[dict]) -> Counter:
    return Counter(loss for row in rows for loss, enabled in (row.get("loss_mask") or {}).items() if enabled)


def main() -> None:
    contract = load_json(CONTRACT)
    terminal = load_jsonl(TERMINAL_ROWS)
    residual = load_jsonl(RESIDUAL_ROWS)
    failures: list[str] = []
    if contract.get("passed") is not True:
        failures.append("stage9543_contract_not_passed")
    if not terminal or not residual:
        failures.append("missing_terminal_or_residual_rows")

    terminal_splits = Counter(row.get("split") for row in terminal)
    residual_splits = Counter(row.get("split") for row in residual)
    terminal_losses = enabled_losses(terminal)
    residual_losses = enabled_losses(residual)
    terminal_authority = [row.get("row_id") for row in terminal if any((row.get("authority") or {}).values())]
    residual_authority = [row.get("row_id") for row in residual if any((row.get("authority") or {}).values())]
    terminal_leaks = [row.get("row_id") for row in terminal if any(key.startswith("effective_") or key.startswith("rejoin_") for key in (row.get("model_input") or {}))]
    residual_leaks = [row.get("row_id") for row in residual if any(key.startswith("effective_") or key.startswith("rejoin_") for key in (row.get("model_input") or {}))]
    if len(terminal) != 29 or terminal_splits != {"eval": 3, "strict_eval": 3, "train": 23}:
        failures.append("terminal_candidate_partition_mismatch")
    if len(residual) != 29 or residual_splits != {"eval": 3, "strict_eval": 3, "train": 23}:
        failures.append("residual_partition_mismatch")
    if terminal_losses or residual_losses:
        failures.append("enabled_losses_present")
    if terminal_authority or residual_authority:
        failures.append("authority_rows_present")
    if terminal_leaks or residual_leaks:
        failures.append("effective_or_rejoin_labels_in_model_input")
    if contract.get("future_probe_design", {}).get("execution_command_emitted") is not False:
        failures.append("execution_command_emitted")
    if contract.get("model_execution_authorized_next") or contract.get("decoder_ce_training_authorized_next") or contract.get("denoise_ce_training_authorized_next"):
        failures.append("future_authority_opened")

    passed = not failures
    metrics = {
        "passed": passed,
        "failures": failures,
        "contract": str(CONTRACT.relative_to(ROOT)),
        "terminal_rows": len(terminal),
        "residual_rows": len(residual),
        "terminal_split_counts": dict(sorted(terminal_splits.items())),
        "residual_split_counts": dict(sorted(residual_splits.items())),
        "terminal_enabled_losses": dict(sorted(terminal_losses.items())),
        "residual_enabled_losses": dict(sorted(residual_losses.items())),
        "terminal_authority_rows": terminal_authority,
        "residual_authority_rows": residual_authority,
        "terminal_leak_rows": terminal_leaks,
        "residual_leak_rows": residual_leaks,
        "execution_command_emitted": contract.get("future_probe_design", {}).get("execution_command_emitted"),
        "required_future_telemetry": contract.get("future_probe_design", {}).get("required_future_telemetry", []),
        "authority": dict(AUTHORITY_CLOSED),
        "model_execution_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "runtime_authorized_next": False,
        "promotion_ready": False,
    }
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": passed,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **metrics},
        "artifacts": {"contract": str(CONTRACT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Audited the terminal-pass rejoin preflight contract. It is partitioned, closed, and design-only; it cannot execute training by itself.",
        "next_best_step": "Build a separate explicit execution-authorization review only if terminal-pass rejoin probing is still desired; otherwise expand residual repair rows from Stage9543 residual route.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9544 Terminal-Pass Rejoin Preflight Contract Audit",
        "",
        f"Passed: `{passed}`",
        f"Terminal rows: `{len(terminal)}` `{dict(terminal_splits)}`",
        f"Residual rows: `{len(residual)}` `{dict(residual_splits)}`",
        f"Enabled losses: terminal `{dict(terminal_losses)}`, residual `{dict(residual_losses)}`",
        "",
        "This audit confirms the contract is design-only. A separate authorization review is required before any probe execution.",
        "",
    ]))
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": passed, "terminal": len(terminal), "residual": len(residual), "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
