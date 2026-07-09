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
STAGE = 9514
NAME = "stage9514_episode_obs_diag_counterbalance_repair_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9513_episode_obs_diag_counterbalance_repair_manifest.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9513_episode_obs_diag_counterbalance_repair_manifest/episode_obs_diag_counterbalance_repair_manifest.jsonl"
CARD = ROOT / "runs/local/artifacts/stage9513_episode_obs_diag_counterbalance_repair_manifest/episode_obs_diag_counterbalance_repair_manifest_card.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage9514_episode_obs_diag_counterbalance_repair_audit"
AUDIT = OUT_DIR / "episode_obs_diag_counterbalance_repair_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_OBS_DIAG_COUNTERBALANCE_REPAIR_AUDIT_STAGE9514.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

EXPECTED_LOSSES = {
    "episode_failure_type_ce": 58,
    "episode_repair_outcome_ce": 58,
    "episode_step_value_mse": 58,
}
FORBIDDEN_LOSSES = {
    "decoder_ce",
    "denoise_ce",
    "runtime_reward",
    "episode_boundary_match_ce",
    "episode_target_prefix_match_ce",
}
REQUIRED_OBS_KEYS = {
    "obs_diag_evidence_version",
    "obs_prefix_relation",
    "obs_boundary_relation",
    "obs_boundary_rank_bucket",
    "obs_residual_reason_count",
    "obs_has_not_exact_reason",
    "obs_has_target_prefix_miss_reason",
    "obs_has_boundary_next_token_miss_reason",
    "obs_short_or_junk",
    "obs_degenerate_repetition",
    "obs_stopped_on_eos",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    card = load_json(CARD)
    rows = load_jsonl(MANIFEST)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9513_summary_not_passed")
    if card.get("passed") is not True:
        failures.append("stage9513_card_not_passed")
    if len(rows) != 58:
        failures.append("unexpected_row_count")

    split_counts = Counter()
    loss_counts = Counter()
    authority_rows: list[str] = []
    forbidden_loss_rows: list[str] = []
    effective_leak_rows: list[str] = []
    missing_obs_rows: list[str] = []
    repair_focus_rows: list[str] = []
    obs_value_counts = Counter()
    for row in rows:
        row_id = row.get("row_id")
        split_counts[row.get("split")] += 1
        if any((row.get("authority") or {}).values()):
            authority_rows.append(row_id)
        loss_mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        for loss, enabled in loss_mask.items():
            if enabled:
                loss_counts[loss] += 1
        if any(loss_mask.get(loss) for loss in FORBIDDEN_LOSSES):
            forbidden_loss_rows.append(row_id)
        model_input = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        if any(key.startswith("effective_") for key in model_input):
            effective_leak_rows.append(row_id)
        if not REQUIRED_OBS_KEYS.issubset(model_input):
            missing_obs_rows.append(row_id)
        if model_input.get("obs_diag_repair_focus_source") is True:
            repair_focus_rows.append(row_id)
        for key in ["obs_prefix_relation", "obs_boundary_relation", "obs_boundary_rank_bucket", "obs_residual_reason_count"]:
            obs_value_counts[f"{key}::{model_input.get(key)}"] += 1

    if dict(loss_counts) != EXPECTED_LOSSES:
        failures.append("unexpected_loss_counts")
    if split_counts != {"eval": 6, "strict_eval": 6, "train": 46}:
        failures.append("unexpected_split_counts")
    if authority_rows:
        failures.append("authority_rows_present")
    if forbidden_loss_rows:
        failures.append("forbidden_loss_rows")
    if effective_leak_rows:
        failures.append("effective_verifier_labels_in_model_input")
    if missing_obs_rows:
        failures.append("missing_primitive_observation_features")
    if len(repair_focus_rows) != 2:
        failures.append("unexpected_repair_focus_rows")

    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "authority_rows": authority_rows,
        "forbidden_loss_rows": forbidden_loss_rows,
        "effective_leak_rows": effective_leak_rows,
        "missing_obs_rows": missing_obs_rows,
        "repair_focus_rows": repair_focus_rows,
        "obs_value_counts": dict(sorted(obs_value_counts.items())),
        "decision": "Stage9513 is preflight-ready: primitive observation evidence is visible, effective labels remain external, and only diagnosis losses are enabled.",
        "authority": dict(AUTHORITY_CLOSED),
        "model_execution_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "promotion_ready": False,
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": audit["decision"],
        "next_best_step": "Run contract-only target-100M preflight for Stage9513 with max rows 46/6/6 and no decoder, denoise, runtime, checkpoint export, or promotion authority.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9514 Episode Observation Diagnosis Counterbalance Repair Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Rows: `{len(rows)}`",
        f"Split counts: `{dict(split_counts)}`",
        f"Loss counts: `{dict(loss_counts)}`",
        f"Repair focus rows: `{repair_focus_rows}`",
        "",
        audit["decision"],
        "",
    ]))
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "rows": len(rows), "repair_focus_rows": len(repair_focus_rows), "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
