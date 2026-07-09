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
STAGE = 9509
NAME = "stage9509_episode_obs_diag_overlay_wide_eval_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9508_episode_obs_diag_overlay_wide_eval_manifest.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9508_episode_obs_diag_overlay_wide_eval_manifest/episode_obs_diag_overlay_wide_eval_manifest.jsonl"
CARD = ROOT / "runs/local/artifacts/stage9508_episode_obs_diag_overlay_wide_eval_manifest/episode_obs_diag_overlay_wide_eval_manifest_card.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage9509_episode_obs_diag_overlay_wide_eval_audit"
AUDIT = OUT_DIR / "episode_obs_diag_overlay_wide_eval_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_OBS_DIAG_OVERLAY_WIDE_EVAL_AUDIT_STAGE9509.md"
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
        failures.append("stage9508_summary_not_passed")
    if card.get("passed") is not True:
        failures.append("stage9508_card_not_passed")
    if len(rows) != 58:
        failures.append("unexpected_row_count")

    split_counts = Counter(row.get("split") for row in rows)
    loss_counts = Counter()
    split_cell_counts = Counter()
    forbidden_rows: list[str] = []
    authority_rows: list[str] = []
    effective_leak_rows: list[str] = []
    for row in rows:
        row_id = row.get("row_id")
        loss_mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        for key, enabled in loss_mask.items():
            if enabled:
                loss_counts[key] += 1
        if any(loss_mask.get(key) for key in FORBIDDEN_LOSSES):
            forbidden_rows.append(row_id)
        if any((row.get("authority") or {}).values()):
            authority_rows.append(row_id)
        model_input = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        if any(key.startswith("effective_") for key in model_input):
            effective_leak_rows.append(row_id)
        effective = row.get("effective_verifier") if isinstance(row.get("effective_verifier"), dict) else {}
        split_cell_counts[f"{row.get('split')}::prefix={effective.get('effective_target_prefix_match')}|outcome={effective.get('effective_repair_outcome')}"] += 1

    if dict(loss_counts) != EXPECTED_LOSSES:
        failures.append("unexpected_loss_counts")
    if split_counts != {"eval": 6, "strict_eval": 6, "train": 46}:
        failures.append("unexpected_split_counts")
    if any(count != 3 for key, count in split_cell_counts.items() if key.startswith("eval::") or key.startswith("strict_eval::")):
        failures.append("eval_strict_cell_imbalance")
    if forbidden_rows:
        failures.append("forbidden_loss_rows")
    if authority_rows:
        failures.append("authority_rows_present")
    if effective_leak_rows:
        failures.append("effective_verifier_labels_in_model_input")

    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "split_cell_counts": dict(sorted(split_cell_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "forbidden_loss_rows": forbidden_rows,
        "authority_rows": authority_rows,
        "effective_leak_rows": effective_leak_rows,
        "decision": "Wide-eval observation-diagnosis overlay manifest is ready for contract-only target-100M preflight.",
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
        "next_best_step": "Run contract-only target-100M preflight for Stage9508 with max rows 46/6/6 and no decoder, denoise, runtime, checkpoint export, or promotion authority.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9509 Episode Observation Diagnosis Overlay Wide-Eval Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Rows: `{len(rows)}`",
        f"Split counts: `{dict(split_counts)}`",
        f"Loss counts: `{dict(loss_counts)}`",
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
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "rows": len(rows), "split_counts": dict(split_counts), "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
