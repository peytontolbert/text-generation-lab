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
STAGE = 9547
NAME = "stage9547_residual_denoise_counterbalance_queue"
SOURCE = ROOT / "runs/local/artifacts/stage9545_residual_repair_route_manifest/residual_repair_route_manifest.jsonl"
SOURCE_AUDIT = ROOT / "runs/summaries/stage9546_residual_repair_route_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage9547_residual_denoise_counterbalance_queue"
QUEUE = OUT_DIR / "residual_denoise_counterbalance_queue.jsonl"
CARD = OUT_DIR / "residual_denoise_counterbalance_queue_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESIDUAL_DENOISE_COUNTERBALANCE_QUEUE_STAGE9547.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

LANGUAGES = ["cpp", "python", "rust", "web_js_ts_html"]
TARGET_BUCKETS = ["REPAIR_PREFIX_ONLY", "REPAIR_PREFIX_AND_BOUNDARY"]
TARGET_PER_LANGUAGE_BUCKET = 4
SPLIT_SEQUENCE = ["train", "train", "eval", "strict_eval"]


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


def discriminators(bucket: str) -> dict[str, object]:
    if bucket == "REPAIR_PREFIX_ONLY":
        return {
            "obs_has_target_prefix_miss_reason": True,
            "obs_has_boundary_next_token_miss_reason": False,
            "obs_boundary_relation": "boundary_match",
            "obs_prefix_relation": "prefix_miss",
            "minimal_discriminator": "prefix_miss_without_boundary_miss",
        }
    return {
        "obs_has_target_prefix_miss_reason": True,
        "obs_has_boundary_next_token_miss_reason": True,
        "obs_boundary_relation": "boundary_miss",
        "obs_prefix_relation": "prefix_miss",
        "minimal_discriminator": "boundary_next_token_miss_in_addition_to_prefix_miss",
    }


def queue_row(idx: int, language: str, bucket: str, split: str, current_count: int) -> dict:
    return {
        "row_id": f"stage9547_counterbalance_request_{idx:04d}",
        "route": "QUEUE_RESIDUAL_DENOISE_COUNTERBALANCE_CONSTRUCTION",
        "objective_family": "residual_denoise_counterbalance_design",
        "language_family": language,
        "split": split,
        "target_repair_bucket": bucket,
        "current_language_bucket_count": current_count,
        "target_language_bucket_count": TARGET_PER_LANGUAGE_BUCKET,
        "needed_count_reason": "language_bucket_counterbalance_for_residual_denoise_design",
        "minimal_discriminating_features": discriminators(bucket),
        "forbidden_shortcut_features": [
            "repair_bucket_visible_in_model_input",
            "effective_failure_type_visible_in_model_input",
            "rejoin_gate_visible_in_model_input",
            "language_only_bucket_prediction",
            "split_only_bucket_prediction",
        ],
        "loss_mask": {
            "decoder_ce": False,
            "denoise_ce": False,
            "runtime_reward": False,
            "episode_failure_type_ce": False,
            "episode_repair_outcome_ce": False,
            "episode_step_value_mse": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "training_candidate": {
            "stage9547_counterbalance_queue_only": True,
            "construction_required_before_training": True,
            "model_execution_authorized_now": False,
            "decoder_ce_closed": True,
            "denoise_ce_closed": True,
            "runtime_reward_closed": True,
        },
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    rows = load_jsonl(SOURCE)
    source_audit = load_json(SOURCE_AUDIT)
    failures: list[str] = []
    if source_audit.get("passed") is not True:
        failures.append("stage9546_audit_not_passed")
    if not rows:
        failures.append("missing_source_rows")

    counts = Counter((row.get("language_family"), (row.get("residual_repair_route") or {}).get("repair_bucket")) for row in rows)
    queue: list[dict] = []
    split_cursor: defaultdict[tuple[str, str], int] = defaultdict(int)
    for language in LANGUAGES:
        for bucket in TARGET_BUCKETS:
            current = counts[(language, bucket)]
            missing = max(0, TARGET_PER_LANGUAGE_BUCKET - current)
            for _ in range(missing):
                key = (language, bucket)
                split = SPLIT_SEQUENCE[split_cursor[key] % len(SPLIT_SEQUENCE)]
                split_cursor[key] += 1
                queue.append(queue_row(len(queue), language, bucket, split, current))

    queue_counts = Counter((row["language_family"], row["target_repair_bucket"]) for row in queue)
    split_counts = Counter(row["split"] for row in queue)
    target_bucket_counts = Counter(row["target_repair_bucket"] for row in queue)
    enabled_losses = Counter(loss for row in queue for loss, enabled in (row.get("loss_mask") or {}).items() if enabled)
    authority_rows = [row["row_id"] for row in queue if any((row.get("authority") or {}).values())]
    if len(queue) != 15:
        failures.append("unexpected_queue_size")
    if enabled_losses:
        failures.append("enabled_losses_present")
    if authority_rows:
        failures.append("authority_rows_present")
    if target_bucket_counts.get("REPAIR_PREFIX_ONLY") != 8 or target_bucket_counts.get("REPAIR_PREFIX_AND_BOUNDARY") != 7:
        failures.append("unexpected_target_bucket_queue_counts")

    write_jsonl(QUEUE, queue)
    card = {
        "passed": not failures,
        "failures": failures,
        "source_manifest": str(SOURCE.relative_to(ROOT)),
        "source_audit": str(SOURCE_AUDIT.relative_to(ROOT)),
        "queue": str(QUEUE.relative_to(ROOT)),
        "source_rows": len(rows),
        "queue_rows": len(queue),
        "source_language_bucket_counts": {f"{language}|{bucket}": counts[(language, bucket)] for language in LANGUAGES for bucket in TARGET_BUCKETS},
        "queue_language_bucket_counts": {"|".join(k): v for k, v in sorted(queue_counts.items())},
        "queue_split_counts": dict(sorted(split_counts.items())),
        "queue_target_bucket_counts": dict(sorted(target_bucket_counts.items())),
        "enabled_losses": dict(sorted(enabled_losses.items())),
        "authority_rows": authority_rows,
        "contract": {
            "queue_only": True,
            "target_per_language_bucket": TARGET_PER_LANGUAGE_BUCKET,
            "dominant_buckets_counterbalanced": TARGET_BUCKETS,
            "all_losses_closed": not enabled_losses,
            "construction_required_before_training": True,
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
        "artifacts": {"queue": str(QUEUE.relative_to(ROOT)), "card": str(CARD.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Queued counterbalanced residual-denoise construction requests for missing language/bucket cells in REPAIR_PREFIX_ONLY and REPAIR_PREFIX_AND_BOUNDARY.",
        "next_best_step": "Audit Stage9547, then materialize the queued counterbalance rows before any denoise execution authorization.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9547 Residual Denoise Counterbalance Queue",
        "",
        f"Passed: `{card['passed']}`",
        f"Queue rows: `{len(queue)}`",
        f"Queue target buckets: `{dict(target_bucket_counts)}`",
        f"Queue splits: `{dict(split_counts)}`",
        "",
        "This is a construction queue, not training data. It specifies missing contrast rows needed before residual denoise authorization.",
        "",
    ]))
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": card["passed"], "queue_rows": len(queue), "target_bucket_counts": dict(target_bucket_counts), "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
