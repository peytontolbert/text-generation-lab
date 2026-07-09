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
STAGE = 9548
NAME = "stage9548_residual_denoise_counterbalance_queue_audit"
QUEUE = ROOT / "runs/local/artifacts/stage9547_residual_denoise_counterbalance_queue/residual_denoise_counterbalance_queue.jsonl"
CARD = ROOT / "runs/local/artifacts/stage9547_residual_denoise_counterbalance_queue/residual_denoise_counterbalance_queue_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESIDUAL_DENOISE_COUNTERBALANCE_QUEUE_AUDIT_STAGE9548.md"
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


def main() -> None:
    rows = load_jsonl(QUEUE)
    card = load_json(CARD)
    failures: list[str] = []
    if card.get("passed") is not True:
        failures.append("stage9547_card_not_passed")
    if not rows:
        failures.append("missing_queue_rows")
    bucket_counts = Counter(row.get("target_repair_bucket") for row in rows)
    split_counts = Counter(row.get("split") for row in rows)
    language_bucket_counts = Counter((row.get("language_family"), row.get("target_repair_bucket")) for row in rows)
    enabled_losses = Counter(loss for row in rows for loss, enabled in (row.get("loss_mask") or {}).items() if enabled)
    authority_rows = [row.get("row_id") for row in rows if any((row.get("authority") or {}).values())]
    missing_discriminators = [row.get("row_id") for row in rows if not (row.get("minimal_discriminating_features") or {}).get("minimal_discriminator")]
    if len(rows) != 15:
        failures.append("unexpected_queue_row_count")
    if bucket_counts.get("REPAIR_PREFIX_ONLY") != 8 or bucket_counts.get("REPAIR_PREFIX_AND_BOUNDARY") != 7:
        failures.append("unexpected_bucket_counts")
    if enabled_losses:
        failures.append("enabled_losses_present")
    if authority_rows:
        failures.append("authority_rows_present")
    if missing_discriminators:
        failures.append("missing_minimal_discriminators")
    for language in ["cpp", "python", "rust", "web_js_ts_html"]:
        if (language, "REPAIR_PREFIX_ONLY") not in language_bucket_counts and (language, "REPAIR_PREFIX_AND_BOUNDARY") not in language_bucket_counts:
            failures.append(f"missing_language_queue::{language}")
    passed = not failures
    metrics = {
        "passed": passed,
        "failures": failures,
        "queue": str(QUEUE.relative_to(ROOT)),
        "source_card": str(CARD.relative_to(ROOT)),
        "queue_rows": len(rows),
        "bucket_counts": dict(sorted(bucket_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "language_bucket_counts": {"|".join(k): v for k, v in sorted(language_bucket_counts.items())},
        "enabled_losses": dict(sorted(enabled_losses.items())),
        "authority_rows": authority_rows,
        "missing_discriminators": missing_discriminators,
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
        "artifacts": {"queue": str(QUEUE.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Audited the residual-denoise counterbalance queue. It is queue-only and closes all execution/training authority.",
        "next_best_step": "Materialize Stage9547 queued counterbalance rows as non-authorized residual-denoise design examples, then audit shortcut balance before denoise execution authorization.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9548 Residual Denoise Counterbalance Queue Audit",
        "",
        f"Passed: `{passed}`",
        f"Queue rows: `{len(rows)}`",
        f"Bucket counts: `{dict(bucket_counts)}`",
        f"Enabled losses: `{dict(enabled_losses)}`",
        "",
        "The queue is safe and non-authorizing. Materialization and shortcut audit must happen before denoise execution authorization.",
        "",
    ]))
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": passed, "queue_rows": len(rows), "bucket_counts": dict(bucket_counts), "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
