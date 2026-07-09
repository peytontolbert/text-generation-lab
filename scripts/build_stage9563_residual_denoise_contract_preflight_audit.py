#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9563
NAME = "stage9563_residual_denoise_contract_preflight_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9562_residual_denoise_execution_authorization_review.json"
COMMAND_JSON = ROOT / "runs/local/artifacts/stage9562_residual_denoise_execution_authorization_review/residual_denoise_tiny_probe_commands.json"
CONTRACT_OUTPUT_DIR = ROOT / "runs/local/artifacts/stage9563_residual_denoise_target_100m_contract_preflight/denoise_repair_probe"
CONTRACT_AUDIT = CONTRACT_OUTPUT_DIR / "probe_contract_audit.json"
CLEANUP_DRY_RUN = CONTRACT_OUTPUT_DIR / "cleanup_dry_run.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "residual_denoise_contract_preflight_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESIDUAL_DENOISE_CONTRACT_PREFLIGHT_AUDIT_STAGE9563.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

AUTHORITY_NEXT = dict(AUTHORITY_CLOSED)
AUTHORITY_NEXT["model_execution_authorized_next"] = True
AUTHORITY_NEXT["denoise_ce_training_authorized_next"] = True


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [
        row
        for row in registry.get("rows", [])
        if row.get("stage") != STAGE and row.get("stage_name") != NAME
    ]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": summary["authority"],
            "next_best_step": summary["next_best_step"],
        }
    )
    authority_counts = {key: 0 for key in AUTHORITY_CLOSED}
    for row in rows:
        auth = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        for key in authority_counts:
            authority_counts[key] += int(bool(auth.get(key, False)))
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
        "authority_counts": authority_counts,
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)

    source = load_json(SOURCE_SUMMARY)
    command_payload = load_json(COMMAND_JSON)
    contract_command = command_payload.get("contract_command") if isinstance(command_payload.get("contract_command"), list) else []
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9562_not_passed")
    if not contract_command:
        failures.append("missing_contract_command")
    if "--contract-only" not in contract_command:
        failures.append("contract_command_missing_contract_only")
    if "--execution-authorized-for-recovery-probe" in contract_command:
        failures.append("contract_command_contains_execution_authorization")

    completed = None
    if not failures:
        completed = subprocess.run(contract_command, cwd=ROOT, text=True, capture_output=True, check=False)
        if completed.returncode != 0:
            failures.append("contract_command_failed")

    contract = load_json(CONTRACT_AUDIT)
    cleanup = load_json(CLEANUP_DRY_RUN)
    if not contract:
        failures.append("missing_probe_contract_audit")
    if contract and contract.get("passed") is not True:
        failures.append("probe_contract_not_passed")
    if contract and contract.get("mode") != "denoise_repair_probe":
        failures.append("contract_mode_not_denoise_repair_probe")
    if contract and contract.get("probe_scale") != "target_100m":
        failures.append("contract_probe_scale_not_target_100m")
    loss_counts = contract.get("loss_counts") or {}
    if loss_counts.get("denoise_ce") != 41:
        failures.append("denoise_loss_count_not_41")
    forbidden_loss_counts = {key: value for key, value in loss_counts.items() if value and key != "denoise_ce"}
    if forbidden_loss_counts:
        failures.append("forbidden_loss_counts_present")
    if contract and contract.get("authority_rows") != 0:
        failures.append("authority_rows_present")
    if contract and contract.get("unsafe_loss_rows") != 0:
        failures.append("unsafe_loss_rows_present")
    if contract and contract.get("model_execution_attempted") is not False:
        failures.append("contract_attempted_model_execution")
    if contract and contract.get("final_checkpoint_export_disabled") is not True:
        failures.append("final_checkpoint_export_not_disabled")
    if contract and contract.get("final_model_save_skipped") is not True:
        failures.append("final_model_save_not_skipped")
    if not cleanup:
        failures.append("missing_cleanup_dry_run")
    if cleanup and cleanup.get("dry_run") is not True:
        failures.append("cleanup_dry_run_not_dry")
    if cleanup and "/arxiv" in str(cleanup.get("output_dir")):
        failures.append("cleanup_output_dir_points_to_arxiv")
    tokenizer = contract.get("tokenizer_contract") or {}
    if tokenizer.get("byte_fallback_used_when_unset") is not False:
        failures.append("target_100m_tokenizer_not_locked")
    implementation = contract.get("implementation_contract") or {}
    if (implementation.get("target_implementation_guard") or {}).get("allowed_for_recovered_100m_target") is not True:
        failures.append("implementation_guard_not_passed")

    passed = not failures
    authority = AUTHORITY_NEXT if passed else dict(AUTHORITY_CLOSED)
    audit = {
        "passed": passed,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "command_json": str(COMMAND_JSON.relative_to(ROOT)),
        "contract_output_dir": str(CONTRACT_OUTPUT_DIR.relative_to(ROOT)),
        "contract_returncode": None if completed is None else completed.returncode,
        "contract_stdout_tail": "" if completed is None else completed.stdout[-4000:],
        "contract_stderr_tail": "" if completed is None else completed.stderr[-4000:],
        "probe_contract_audit": str(CONTRACT_AUDIT.relative_to(ROOT)) if CONTRACT_AUDIT.exists() else None,
        "cleanup_dry_run": str(CLEANUP_DRY_RUN.relative_to(ROOT)) if CLEANUP_DRY_RUN.exists() else None,
        "rows": contract.get("rows"),
        "split_counts": contract.get("split_counts"),
        "loss_counts": loss_counts,
        "allowed_losses": contract.get("allowed_losses"),
        "unsafe_loss_rows": contract.get("unsafe_loss_rows"),
        "authority_rows": contract.get("authority_rows"),
        "probe_scale": contract.get("probe_scale"),
        "implementation": contract.get("implementation"),
        "model_execution_attempted": contract.get("model_execution_attempted"),
        "next_model_execution_authorized": bool(authority.get("model_execution_authorized_next")),
        "next_denoise_ce_training_authorized": bool(authority.get("denoise_ce_training_authorized_next")),
        "decoder_ce_training_authorized_next": False,
        "runtime_authorized": False,
        "promotion_ready": False,
        "authority": authority,
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": passed,
        "authority": authority,
        "metrics": {**{key: bool(authority.get(key, False)) for key in AUTHORITY_CLOSED}, **audit},
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "contract": str(CONTRACT_AUDIT.relative_to(ROOT)) if CONTRACT_AUDIT.exists() else None,
            "cleanup_dry_run": str(CLEANUP_DRY_RUN.relative_to(ROOT)) if CLEANUP_DRY_RUN.exists() else None,
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Ran the residual-denoise target_100M trainer contract-only preflight under trellis. If passed, the next tiny probe may execute the Stage9562 future execution command.",
        "next_best_step": "If Stage9563 passed, execute Stage9564 actual tiny residual-denoise target_100M probe under trellis, then audit generation quality and residual repair exactness.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9563 Residual Denoise Contract Preflight Audit",
                "",
                f"Passed: `{passed}`",
                f"Rows: `{contract.get('rows')}`",
                f"Loss counts: `{loss_counts}`",
                f"Next model execution authorized: `{bool(authority.get('model_execution_authorized_next'))}`",
                f"Next denoise CE authorized: `{bool(authority.get('denoise_ce_training_authorized_next'))}`",
                "",
                "This stage ran only the trainer contract preflight with `--contract-only`; it did not train the model.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": passed, "rows": contract.get("rows"), "loss_counts": loss_counts, "failures": failures}, indent=2, sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
