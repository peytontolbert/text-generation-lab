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
STAGE = 9505
NAME = "stage9505_episode_obs_diag_overlay_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9504_episode_obs_diag_overlay_manifest.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9504_episode_obs_diag_overlay_manifest/episode_obs_diag_overlay_manifest.jsonl"
CARD = ROOT / "runs/local/artifacts/stage9504_episode_obs_diag_overlay_manifest/episode_obs_diag_overlay_manifest_card.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage9505_episode_obs_diag_overlay_audit"
AUDIT = OUT_DIR / "episode_obs_diag_overlay_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_OBS_DIAG_OVERLAY_AUDIT_STAGE9505.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

EXPECTED_LOSSES = {
    "episode_failure_type_ce",
    "episode_repair_outcome_ce",
    "episode_step_value_mse",
}
FORBIDDEN_LOSSES = {
    "decoder_ce",
    "denoise_ce",
    "runtime_reward",
    "episode_boundary_match_ce",
    "episode_target_prefix_match_ce",
}
EFFECTIVE_KEYS = {
    "effective_boundary_match",
    "effective_target_prefix_match",
    "effective_failure_type",
    "effective_repair_outcome",
    "effective_step_value",
    "effective_step_passed",
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

    source_summary = load_json(SOURCE_SUMMARY)
    card = load_json(CARD)
    rows = load_jsonl(MANIFEST)
    failures: list[str] = []
    warnings: list[str] = []
    if source_summary.get("passed") is not True:
        failures.append("stage9504_summary_not_passed")
    if card.get("passed") is not True:
        failures.append("stage9504_card_not_passed")
    if len(rows) != 58:
        failures.append("unexpected_row_count")

    split_counts = Counter()
    loss_counts = Counter()
    forbidden_loss_rows: list[str] = []
    authority_rows: list[str] = []
    missing_effective_rows: list[str] = []
    effective_leak_rows: list[str] = []
    cell_counts = Counter()
    for row in rows:
        row_id = row.get("row_id")
        split_counts[row.get("split")] += 1
        if any((row.get("authority") or {}).values()):
            authority_rows.append(row_id)
        loss_mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        for loss_name, enabled in loss_mask.items():
            if enabled:
                loss_counts[loss_name] += 1
        if any(loss_mask.get(loss_name) for loss_name in FORBIDDEN_LOSSES):
            forbidden_loss_rows.append(row_id)
        effective = row.get("effective_verifier") if isinstance(row.get("effective_verifier"), dict) else {}
        if not EFFECTIVE_KEYS.issubset(effective) or any(effective.get(key) is None for key in EFFECTIVE_KEYS):
            missing_effective_rows.append(row_id)
        model_input = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        if any(key.startswith("effective_") for key in model_input):
            effective_leak_rows.append(row_id)
        cell_counts[f"prefix={effective.get('effective_target_prefix_match')}|outcome={effective.get('effective_repair_outcome')}"] += 1

    expected_loss_counts = {loss: len(rows) for loss in sorted(EXPECTED_LOSSES)}
    if dict(loss_counts) != expected_loss_counts:
        failures.append("unexpected_loss_counts")
    if forbidden_loss_rows:
        failures.append("forbidden_loss_rows")
    if authority_rows:
        failures.append("authority_rows_present")
    if missing_effective_rows:
        failures.append("missing_effective_verifier_rows")
    if effective_leak_rows:
        failures.append("effective_verifier_labels_in_model_input")
    if split_counts.get("eval", 0) < 2 or split_counts.get("strict_eval", 0) < 2:
        warnings.append("minimal_eval_strict_coverage_from_stage9472_source")

    audit = {
        "passed": not failures,
        "failures": failures,
        "warnings": warnings,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "expected_loss_counts": expected_loss_counts,
        "forbidden_loss_rows": forbidden_loss_rows,
        "authority_rows": authority_rows,
        "missing_effective_rows": missing_effective_rows,
        "effective_leak_rows": effective_leak_rows,
        "cell_counts": dict(sorted(cell_counts.items())),
        "contract_checks": {
            "only_expected_losses_enabled": dict(loss_counts) == expected_loss_counts,
            "forbidden_losses_closed": not forbidden_loss_rows,
            "effective_verifier_complete": not missing_effective_rows,
            "effective_verifier_outside_model_input": not effective_leak_rows,
            "authority_closed": not authority_rows,
            "decoder_ce_training_authorized_next": False,
            "denoise_ce_training_authorized_next": False,
            "runtime_authorized": False,
        },
        "decision": "Stage9504 is safe for a contract-only target-100M preflight as a tiny observation-diagnosis surface. It is not a decoder, runtime, or promotion step.",
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
        "next_best_step": "Run contract-only target-100M preflight for Stage9504 with max rows 56/1/1 and no decoder, denoise, runtime, checkpoint export, or promotion authority.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    DOC.write_text("\n".join([
        "# Stage9505 Episode Observation Diagnosis Overlay Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Rows: `{len(rows)}`",
        f"Split counts: `{dict(split_counts)}`",
        f"Loss counts: `{dict(loss_counts)}`",
        f"Warnings: `{warnings}`",
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

    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "rows": len(rows), "loss_counts": dict(loss_counts), "warnings": warnings, "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
