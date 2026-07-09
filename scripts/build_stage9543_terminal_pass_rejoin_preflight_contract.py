#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from collections import Counter
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9543
NAME = "stage9543_terminal_pass_rejoin_preflight_contract"
SOURCE = ROOT / "runs/local/artifacts/stage9541_episode_obs_diag_closed_boundary_rejoin_gate_manifest/episode_obs_diag_closed_boundary_rejoin_gate_manifest.jsonl"
SOURCE_AUDIT = ROOT / "runs/summaries/stage9542_episode_obs_diag_closed_boundary_rejoin_gate_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage9543_terminal_pass_rejoin_preflight_contract"
TERMINAL_ROWS = OUT_DIR / "terminal_pass_rejoin_candidate_rows.jsonl"
RESIDUAL_ROWS = OUT_DIR / "residual_repair_route_rows.jsonl"
CONTRACT = OUT_DIR / "terminal_pass_rejoin_preflight_contract.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TERMINAL_PASS_REJOIN_PREFLIGHT_CONTRACT_STAGE9543.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

ALL_KNOWN_LOSSES = {
    "action_sequence_ce",
    "allowed_import_policy_ce",
    "blocked_import_policy_ce",
    "build_mode_ce",
    "decoder_ce",
    "denoise_ce",
    "edit_localization_ce",
    "episode_boundary_match_ce",
    "episode_failure_type_ce",
    "episode_repair_outcome_ce",
    "episode_step_value_mse",
    "episode_target_prefix_match_ce",
    "file_plan_ce",
    "patch_operator_ce",
    "repair_surface_ce",
    "repo_dependency_policy_ce",
    "runtime_reward",
    "suffix_choice_ce",
    "surface_role_ce",
    "symbol_binding_ce",
    "verifier_repair_ce",
}
REQUIRED_FUTURE_TELEMETRY = [
    "row_field_logits.jsonl",
    "row_field_losses.jsonl",
    "row_token_loss.jsonl",
    "eos_length_audit.json",
    "short_output_probe.json",
    "repetition_probe.json",
    "internal_leak_probe.json",
    "sample_generation_audit.json",
    "module_delta_norms.json",
    "failure_bucket_card.json",
    "cleanup_proof.json",
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


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


def closed_loss_mask(row: dict) -> dict[str, bool]:
    loss_mask = dict(row.get("loss_mask") or {})
    for loss in ALL_KNOWN_LOSSES:
        loss_mask[loss] = False
    return loss_mask


def clone_for_route(row: dict, prefix: str, idx: int, route: str) -> dict:
    out = copy.deepcopy(row)
    out["row_id"] = f"{prefix}_{idx:04d}"
    out["source_stage9541_row_id"] = row.get("row_id")
    out["route"] = route
    out["authority"] = dict(AUTHORITY_CLOSED)
    out["loss_mask"] = closed_loss_mask(out)
    training_candidate = dict(out.get("training_candidate") or {})
    training_candidate.update(
        {
            "stage9543_preflight_contract_only": True,
            "losses_closed_in_contract": True,
            "future_probe_candidate_only": route == "TERMINAL_PASS_REJOIN_CANDIDATE_ONLY",
            "residual_routed_to_repair_data": route == "ROUTE_RESIDUAL_TO_REPAIR_DATA",
            "model_execution_authorized_now": False,
            "decoder_ce_closed": True,
            "denoise_ce_closed": True,
            "runtime_reward_closed": True,
        }
    )
    out["training_candidate"] = training_candidate
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    rows = load_jsonl(SOURCE)
    source_audit = load_json(SOURCE_AUDIT)
    failures: list[str] = []
    if source_audit.get("passed") is not True:
        failures.append("stage9542_audit_not_passed")
    if not rows:
        failures.append("missing_source_rows")

    terminal: list[dict] = []
    residual: list[dict] = []
    for row in rows:
        gate = row.get("rejoin_gate") if isinstance(row.get("rejoin_gate"), dict) else {}
        if gate.get("would_allow_terminal_decode_rejoin_candidate") is True:
            terminal.append(clone_for_route(row, "stage9543_terminal_rejoin_candidate", len(terminal), "TERMINAL_PASS_REJOIN_CANDIDATE_ONLY"))
        elif gate.get("would_route_to_residual_repair_candidate") is True:
            residual.append(clone_for_route(row, "stage9543_residual_repair_route", len(residual), "ROUTE_RESIDUAL_TO_REPAIR_DATA"))
        else:
            failures.append("row_without_terminal_or_residual_route")

    terminal_split_counts = Counter(row.get("split") for row in terminal)
    residual_split_counts = Counter(row.get("split") for row in residual)
    terminal_enabled_losses = Counter(loss for row in terminal for loss, enabled in (row.get("loss_mask") or {}).items() if enabled)
    residual_enabled_losses = Counter(loss for row in residual for loss, enabled in (row.get("loss_mask") or {}).items() if enabled)
    leakage_rows = [row.get("row_id") for row in terminal + residual if any(key.startswith("effective_") or key.startswith("rejoin_") for key in (row.get("model_input") or {}))]
    authority_rows = [row.get("row_id") for row in terminal + residual if any((row.get("authority") or {}).values())]
    if len(terminal) != 29 or len(residual) != 29:
        failures.append("unexpected_terminal_or_residual_counts")
    if terminal_split_counts != {"eval": 3, "strict_eval": 3, "train": 23}:
        failures.append("unexpected_terminal_split_counts")
    if residual_split_counts != {"eval": 3, "strict_eval": 3, "train": 23}:
        failures.append("unexpected_residual_split_counts")
    if terminal_enabled_losses or residual_enabled_losses:
        failures.append("enabled_losses_present")
    if leakage_rows:
        failures.append("effective_or_rejoin_labels_in_model_input")
    if authority_rows:
        failures.append("authority_rows_present")

    write_jsonl(TERMINAL_ROWS, terminal)
    write_jsonl(RESIDUAL_ROWS, residual)
    contract = {
        "passed": not failures,
        "failures": failures,
        "source_manifest": str(SOURCE.relative_to(ROOT)),
        "source_audit": str(SOURCE_AUDIT.relative_to(ROOT)),
        "terminal_rows": str(TERMINAL_ROWS.relative_to(ROOT)),
        "residual_rows": str(RESIDUAL_ROWS.relative_to(ROOT)),
        "terminal_row_count": len(terminal),
        "residual_row_count": len(residual),
        "terminal_split_counts": dict(sorted(terminal_split_counts.items())),
        "residual_split_counts": dict(sorted(residual_split_counts.items())),
        "terminal_enabled_losses": dict(sorted(terminal_enabled_losses.items())),
        "residual_enabled_losses": dict(sorted(residual_enabled_losses.items())),
        "leakage_rows": leakage_rows,
        "authority_rows": authority_rows,
        "future_probe_design": {
            "design_only": True,
            "execution_command_emitted": False,
            "suggested_mode": "terminal_pass_rejoin_probe",
            "suggested_max_train_rows": 16,
            "suggested_max_eval_rows": 3,
            "suggested_max_strict_rows": 3,
            "suggested_max_steps": 8,
            "required_future_telemetry": REQUIRED_FUTURE_TELEMETRY,
            "block_if_residual_rows_included": True,
            "block_if_any_loss_enabled_without_fresh_authorization": True,
            "block_if_decoder_ce_requested": True,
            "block_if_runtime_or_gemma_requested": True,
        },
        "contract": {
            "contract_only_preflight_design": True,
            "terminal_candidates_separated_from_residual_repair_rows": True,
            "all_losses_closed_now": not terminal_enabled_losses and not residual_enabled_losses,
            "no_execution_command": True,
            "residual_rows_route_to_repair_data": True,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "model_execution_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "runtime_authorized_next": False,
        "promotion_ready": False,
    }
    CONTRACT.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": contract["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **contract},
        "artifacts": {
            "contract": str(CONTRACT.relative_to(ROOT)),
            "terminal_rows": str(TERMINAL_ROWS.relative_to(ROOT)),
            "residual_rows": str(RESIDUAL_ROWS.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Designed a contract-only terminal-pass rejoin preflight package. It separates terminal candidates from residual repair rows and emits no execution command.",
        "next_best_step": "Audit Stage9543, then decide between a separate execution-authorization review for terminal candidates or residual repair-data expansion. Do not execute from this contract directly.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9543 Terminal-Pass Rejoin Preflight Contract",
        "",
        f"Passed: `{contract['passed']}`",
        f"Terminal candidates: `{len(terminal)}` `{dict(terminal_split_counts)}`",
        f"Residual repair rows: `{len(residual)}` `{dict(residual_split_counts)}`",
        "",
        "This is design-only. No command is emitted, all losses are closed, and terminal-pass status is not execution authorization.",
        "",
    ]))
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": contract["passed"], "terminal": len(terminal), "residual": len(residual), "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
