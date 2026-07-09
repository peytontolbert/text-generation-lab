#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9512
NAME = "stage9512_episode_obs_diag_eval_error_attribution"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9511_episode_obs_diag_overlay_wide_eval_probe_audit.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9508_episode_obs_diag_overlay_wide_eval_manifest/episode_obs_diag_overlay_wide_eval_manifest.jsonl"
LOGITS = ROOT / "runs/local/artifacts/stage9511_episode_obs_diag_overlay_wide_eval_target_100m_probe/row_field_logits.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts/stage9512_episode_obs_diag_eval_error_attribution"
ATTRIBUTION = OUT_DIR / "episode_obs_diag_eval_error_attribution.json"
REPAIR_QUEUE = OUT_DIR / "episode_obs_diag_repair_queue.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_OBS_DIAG_EVAL_ERROR_ATTRIBUTION_STAGE9512.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


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
    manifest_rows = {row.get("row_id"): row for row in load_jsonl(MANIFEST)}
    logits = load_jsonl(LOGITS)
    failures: list[str] = []
    if source.get("passed") is not False or source.get("metrics", {}).get("safety_passed") is not True:
        failures.append("stage9511_not_safe_quality_failure")
    wrong = [row for row in logits if row.get("correct") is False]
    if not wrong:
        failures.append("missing_wrong_rows")

    wrong_by_row: dict[str, list[dict]] = defaultdict(list)
    for row in wrong:
        wrong_by_row[row.get("row_id")].append(row)

    queue_rows: list[dict] = []
    field_confusions = Counter()
    row_failure_counts = Counter()
    high_conf_wrong = [row for row in wrong if row.get("high_confidence_wrong")]
    for row_id, errors in sorted(wrong_by_row.items()):
        source_row = manifest_rows.get(row_id, {})
        effective = source_row.get("effective_verifier") if isinstance(source_row.get("effective_verifier"), dict) else {}
        language = (errors[0].get("cell_key") or "").split("::", 1)[0]
        discriminators = {
            "effective_boundary_match": effective.get("effective_boundary_match"),
            "effective_target_prefix_match": effective.get("effective_target_prefix_match"),
            "effective_failure_type": effective.get("effective_failure_type"),
            "effective_repair_outcome": effective.get("effective_repair_outcome"),
            "effective_step_value": effective.get("effective_step_value"),
            "effective_step_passed": effective.get("effective_step_passed"),
        }
        for err in errors:
            field_confusions[f"{err.get('field')}::{err.get('target')}=>{err.get('pred')}"] += 1
        row_failure_counts[language] += len(errors)
        queue_rows.append({
            "repair_queue_id": f"stage9512_eval_error_{len(queue_rows):04d}",
            "source_stage9508_row_id": row_id,
            "split": "eval",
            "language_family": language,
            "wrong_fields": [
                {
                    "field": err.get("field"),
                    "target": err.get("target"),
                    "pred": err.get("pred"),
                    "confidence": err.get("confidence"),
                    "margin": err.get("margin"),
                    "high_confidence_wrong": err.get("high_confidence_wrong"),
                }
                for err in errors
            ],
            "minimal_discriminating_features": discriminators,
            "recommended_patch": "construct_counterbalanced_neighbors_with_same_language_and_prefix_bucket_but_opposite_success_residual_and_boundary_miss_status",
            "forbidden_shortcut_features": ["split", "row_id", "source_stage_ids", "effective_*_inside_model_input"],
            "authority": dict(AUTHORITY_CLOSED),
        })

    REPAIR_QUEUE.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in queue_rows))
    attribution = {
        "passed": not failures,
        "failures": failures,
        "source_stage": "stage9511_episode_obs_diag_overlay_wide_eval_probe_audit",
        "wrong_field_rows": len(wrong),
        "wrong_source_rows": len(wrong_by_row),
        "high_confidence_wrong_rows": len(high_conf_wrong),
        "field_confusions": dict(sorted(field_confusions.items())),
        "row_failure_counts_by_language": dict(sorted(row_failure_counts.items())),
        "repair_queue": str(REPAIR_QUEUE.relative_to(ROOT)),
        "repair_queue_rows": len(queue_rows),
        "diagnosis": "Eval failures are high-confidence, not uncertainty. Add counterbalanced C++ residual-vs-success rows and Python boundary-miss failure-type rows before another widened probe.",
        "authority": dict(AUTHORITY_CLOSED),
        "model_execution_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "promotion_ready": False,
    }
    ATTRIBUTION.write_text(json.dumps(attribution, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": attribution["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **attribution},
        "artifacts": {"attribution": str(ATTRIBUTION.relative_to(ROOT)), "repair_queue": str(REPAIR_QUEUE.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": attribution["diagnosis"],
        "next_best_step": "Build Stage9513 counterbalanced observation-diagnosis repair rows from the Stage9512 queue before another target-100M execution.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9512 Episode Observation Diagnosis Eval Error Attribution",
        "",
        f"Passed: `{attribution['passed']}`",
        f"Wrong field rows: `{len(wrong)}`",
        f"Wrong source rows: `{len(wrong_by_row)}`",
        f"High-confidence wrong rows: `{len(high_conf_wrong)}`",
        f"Repair queue rows: `{len(queue_rows)}`",
        "",
        attribution["diagnosis"],
        "",
    ]))
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": attribution["passed"], "wrong_field_rows": len(wrong), "wrong_source_rows": len(wrong_by_row), "repair_queue_rows": len(queue_rows), "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
