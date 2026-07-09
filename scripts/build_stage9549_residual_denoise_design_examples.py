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
STAGE = 9549
NAME = "stage9549_residual_denoise_design_examples"
QUEUE = ROOT / "runs/local/artifacts/stage9547_residual_denoise_counterbalance_queue/residual_denoise_counterbalance_queue.jsonl"
SOURCE_RESIDUAL = ROOT / "runs/local/artifacts/stage9545_residual_repair_route_manifest/residual_repair_route_manifest.jsonl"
SOURCE_AUDIT = ROOT / "runs/summaries/stage9548_residual_denoise_counterbalance_queue_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage9549_residual_denoise_design_examples"
EXAMPLES = OUT_DIR / "residual_denoise_design_examples.jsonl"
CARD = OUT_DIR / "residual_denoise_design_examples_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESIDUAL_DENOISE_DESIGN_EXAMPLES_STAGE9549.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

ALL_KNOWN_LOSSES = {
    "decoder_ce", "denoise_ce", "runtime_reward", "episode_failure_type_ce", "episode_repair_outcome_ce", "episode_step_value_mse",
    "suffix_choice_ce", "verifier_repair_ce", "action_sequence_ce", "patch_operator_ce", "edit_localization_ce",
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
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")


def target_failure_type(bucket: str) -> str:
    if bucket == "REPAIR_PREFIX_ONLY":
        return "not_exact+target_prefix_miss"
    return "not_exact+target_prefix_miss+boundary_next_token_miss"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    queue = load_jsonl(QUEUE)
    source_rows = load_jsonl(SOURCE_RESIDUAL)
    source_audit = load_json(SOURCE_AUDIT)
    failures: list[str] = []
    if source_audit.get("passed") is not True:
        failures.append("stage9548_audit_not_passed")
    if not queue:
        failures.append("missing_queue_rows")

    examples: list[dict] = []
    for idx, req in enumerate(queue):
        bucket = str(req.get("target_repair_bucket"))
        features = dict(req.get("minimal_discriminating_features") or {})
        model_input = {
            "residual_denoise_design_phase": True,
            "language_family": req.get("language_family"),
            "obs_prefix_relation": features.get("obs_prefix_relation"),
            "obs_boundary_relation": features.get("obs_boundary_relation"),
            "obs_has_target_prefix_miss_reason": features.get("obs_has_target_prefix_miss_reason"),
            "obs_has_boundary_next_token_miss_reason": features.get("obs_has_boundary_next_token_miss_reason"),
            "obs_has_not_exact_reason": True,
            "obs_short_or_junk": False,
            "literal_prefix_redacted": True,
            "counterbalance_design_example": True,
        }
        examples.append(
            {
                "row_id": f"stage9549_residual_denoise_design_{idx:04d}",
                "source_stage9547_queue_row_id": req.get("row_id"),
                "split": req.get("split"),
                "language_family": req.get("language_family"),
                "objective_family": "residual_denoise_design_example",
                "route": "KEEP_RESIDUAL_DENOISE_DESIGN_EXAMPLE_NOT_TRAINABLE",
                "model_input": model_input,
                "target": {
                    "repair_bucket": bucket,
                    "failure_type": target_failure_type(bucket),
                    "target_authority": "design_only_not_training_label",
                },
                "loss_mask": {loss: False for loss in ALL_KNOWN_LOSSES},
                "authority": dict(AUTHORITY_CLOSED),
                "training_candidate": {
                    "stage9549_design_example_only": True,
                    "materialized_from_counterbalance_queue": True,
                    "training_authorized_now": False,
                    "model_execution_authorized_now": False,
                    "decoder_ce_closed": True,
                    "denoise_ce_closed": True,
                    "runtime_reward_closed": True,
                },
            }
        )

    example_counts = Counter((row["language_family"], row["target"]["repair_bucket"]) for row in examples)
    source_counts = Counter((row.get("language_family"), (row.get("residual_repair_route") or {}).get("repair_bucket")) for row in source_rows)
    combined_counts = Counter(source_counts)
    combined_counts.update(example_counts)
    enabled_losses = Counter(loss for row in examples for loss, enabled in row["loss_mask"].items() if enabled)
    authority_rows = [row["row_id"] for row in examples if any((row.get("authority") or {}).values())]
    label_leak_rows = [row["row_id"] for row in examples if any(key in row["model_input"] for key in ["target_repair_bucket", "repair_bucket", "failure_type", "effective_failure_type"])]
    if len(examples) != 15:
        failures.append("unexpected_example_count")
    if enabled_losses:
        failures.append("enabled_losses_present")
    if authority_rows:
        failures.append("authority_rows_present")
    if label_leak_rows:
        failures.append("target_label_leaked_into_model_input")
    for language in ["cpp", "python", "rust", "web_js_ts_html"]:
        for bucket in ["REPAIR_PREFIX_ONLY", "REPAIR_PREFIX_AND_BOUNDARY"]:
            if combined_counts[(language, bucket)] < 4:
                failures.append(f"combined_count_under_target::{language}::{bucket}")

    EXAMPLES.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in examples))
    card = {
        "passed": not failures,
        "failures": failures,
        "queue": str(QUEUE.relative_to(ROOT)),
        "source_residual": str(SOURCE_RESIDUAL.relative_to(ROOT)),
        "examples": str(EXAMPLES.relative_to(ROOT)),
        "example_rows": len(examples),
        "example_language_bucket_counts": {"|".join(k): v for k, v in sorted(example_counts.items())},
        "combined_language_bucket_counts": {"|".join(k): v for k, v in sorted(combined_counts.items()) if k[1] in {"REPAIR_PREFIX_ONLY", "REPAIR_PREFIX_AND_BOUNDARY"}},
        "enabled_losses": dict(sorted(enabled_losses.items())),
        "authority_rows": authority_rows,
        "label_leak_rows": label_leak_rows,
        "authority": dict(AUTHORITY_CLOSED),
        "model_execution_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "runtime_authorized_next": False,
        "promotion_ready": False,
    }
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    summary = {"stage": STAGE, "stage_name": NAME, "name": NAME, "passed": card["passed"], "authority": dict(AUTHORITY_CLOSED), "metrics": {**dict(AUTHORITY_CLOSED), **card}, "artifacts": {"examples": str(EXAMPLES.relative_to(ROOT)), "card": str(CARD.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))}, "decision": "Materialized non-authorized residual-denoise design examples from the Stage9547 queue.", "next_best_step": "Audit Stage9549 for label leakage, closed losses, and combined language/bucket coverage before shortcut-balance evaluation.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join(["# Stage9549 Residual Denoise Design Examples", "", f"Passed: `{card['passed']}`", f"Example rows: `{len(examples)}`", "", "These examples are design-only and non-authorized. They materialize missing residual denoise contrast cells without opening losses.", ""]))
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": card["passed"], "examples": len(examples), "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
