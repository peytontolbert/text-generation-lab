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
STAGE = 9545
NAME = "stage9545_residual_repair_route_manifest"
SOURCE = ROOT / "runs/local/artifacts/stage9543_terminal_pass_rejoin_preflight_contract/residual_repair_route_rows.jsonl"
SOURCE_AUDIT = ROOT / "runs/summaries/stage9544_terminal_pass_rejoin_preflight_contract_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage9545_residual_repair_route_manifest"
MANIFEST = OUT_DIR / "residual_repair_route_manifest.jsonl"
CARD = OUT_DIR / "residual_repair_route_manifest_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESIDUAL_REPAIR_ROUTE_MANIFEST_STAGE9545.md"
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


def repair_bucket(failure_type: str) -> str:
    parts = set(failure_type.split("+")) if failure_type else set()
    if "degenerate_repetition" in parts:
        return "REPAIR_PREFIX_BOUNDARY_REPETITION_UNTERMINATED"
    if "unterminated" in parts and "boundary_next_token_miss" in parts:
        return "REPAIR_PREFIX_BOUNDARY_UNTERMINATED"
    if "boundary_next_token_miss" in parts:
        return "REPAIR_PREFIX_AND_BOUNDARY"
    if "target_prefix_miss" in parts:
        return "REPAIR_PREFIX_ONLY"
    return "REPAIR_RESIDUAL_GENERAL"


def closed_loss_mask(row: dict) -> dict[str, bool]:
    loss_mask = dict(row.get("loss_mask") or {})
    for loss in ALL_KNOWN_LOSSES:
        loss_mask[loss] = False
    return loss_mask


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    rows = load_jsonl(SOURCE)
    source_audit = load_json(SOURCE_AUDIT)
    failures: list[str] = []
    if source_audit.get("passed") is not True:
        failures.append("stage9544_audit_not_passed")
    if not rows:
        failures.append("missing_source_rows")

    output_rows: list[dict] = []
    split_counts = Counter()
    bucket_counts = Counter()
    failure_type_counts = Counter()
    enabled_loss_counts = Counter()
    authority_rows: list[str] = []
    leakage_rows: list[str] = []
    terminal_rows: list[str] = []

    for idx, row in enumerate(rows):
        effective = row.get("effective_verifier") if isinstance(row.get("effective_verifier"), dict) else {}
        failure_type = str(effective.get("effective_failure_type") or "none")
        bucket = repair_bucket(failure_type)
        out = copy.deepcopy(row)
        out["row_id"] = f"stage9545_residual_repair_route_{idx:04d}"
        out["source_stage9543_row_id"] = row.get("row_id")
        out["objective_family"] = "residual_repair_route"
        out["route"] = "USE_FOR_RESIDUAL_REPAIR_DATA_CANDIDATE"
        out["residual_repair_route"] = {
            "route_stage": 9545,
            "repair_bucket": bucket,
            "failure_type": failure_type,
            "source": "stage9543_residual_repair_route_rows",
            "decoder_ce_authorized": False,
            "denoise_ce_authorized_now": False,
            "future_denoise_candidate_only": True,
        }
        out["authority"] = dict(AUTHORITY_CLOSED)
        out["loss_mask"] = closed_loss_mask(out)
        training_candidate = dict(out.get("training_candidate") or {})
        training_candidate.update(
            {
                "stage9545_residual_repair_route": True,
                "residual_repair_bucket": bucket,
                "losses_closed_in_route_manifest": True,
                "future_denoise_candidate_only": True,
                "model_execution_authorized_now": False,
                "decoder_ce_closed": True,
                "denoise_ce_closed": True,
                "runtime_reward_closed": True,
            }
        )
        out["training_candidate"] = training_candidate
        for loss, enabled in out["loss_mask"].items():
            if enabled:
                enabled_loss_counts[loss] += 1
        if any((out.get("authority") or {}).values()):
            authority_rows.append(out["row_id"])
        model_input = out.get("model_input") if isinstance(out.get("model_input"), dict) else {}
        if any(key.startswith("effective_") or key.startswith("rejoin_") or key.startswith("residual_repair_") for key in model_input):
            leakage_rows.append(out["row_id"])
        gate = out.get("rejoin_gate") if isinstance(out.get("rejoin_gate"), dict) else {}
        if gate.get("would_allow_terminal_decode_rejoin_candidate") is True:
            terminal_rows.append(out["row_id"])
        split_counts[out.get("split")] += 1
        bucket_counts[bucket] += 1
        failure_type_counts[failure_type] += 1
        output_rows.append(out)

    if len(output_rows) != 29:
        failures.append("unexpected_row_count")
    if split_counts != {"eval": 3, "strict_eval": 3, "train": 23}:
        failures.append("unexpected_split_counts")
    if enabled_loss_counts:
        failures.append("enabled_losses_present")
    if authority_rows:
        failures.append("authority_rows_present")
    if leakage_rows:
        failures.append("effective_rejoin_or_residual_labels_in_model_input")
    if terminal_rows:
        failures.append("terminal_rows_in_residual_route")

    MANIFEST.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in output_rows))
    card = {
        "passed": not failures,
        "failures": failures,
        "source_manifest": str(SOURCE.relative_to(ROOT)),
        "source_audit": str(SOURCE_AUDIT.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "rows": len(output_rows),
        "split_counts": dict(sorted(split_counts.items())),
        "bucket_counts": dict(sorted(bucket_counts.items())),
        "failure_type_counts": dict(sorted(failure_type_counts.items())),
        "enabled_loss_counts": dict(sorted(enabled_loss_counts.items())),
        "authority_rows": authority_rows,
        "leakage_rows": leakage_rows,
        "terminal_rows": terminal_rows,
        "contract": {
            "residual_only": True,
            "all_losses_closed": not enabled_loss_counts,
            "decoder_ce_closed": True,
            "denoise_ce_candidate_only": True,
            "effective_rejoin_and_residual_labels_outside_model_input": not leakage_rows,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "model_execution_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "runtime_authorized_next": False,
        "promotion_ready": False,
    }
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": card["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **card},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "card": str(CARD.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Routed Stage9543 residual rows into repair buckets with decoder CE, denoise CE, runtime, and execution still closed.",
        "next_best_step": "Audit Stage9545, then build a residual-denoise authorization review or add counterbalanced repair examples for the dominant REPAIR_PREFIX_ONLY and REPAIR_PREFIX_AND_BOUNDARY buckets.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9545 Residual Repair Route Manifest",
        "",
        f"Passed: `{card['passed']}`",
        f"Rows: `{len(output_rows)}`",
        f"Bucket counts: `{dict(bucket_counts)}`",
        "",
        "Residual rows are routed into repair buckets for future denoise-data design. All losses remain closed here; this manifest does not authorize execution or decoder CE.",
        "",
    ]))
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": card["passed"], "rows": len(output_rows), "bucket_counts": dict(bucket_counts), "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
