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
STAGE = 9546
NAME = "stage9546_residual_repair_route_audit"
SOURCE = ROOT / "runs/local/artifacts/stage9545_residual_repair_route_manifest/residual_repair_route_manifest.jsonl"
SOURCE_CARD = ROOT / "runs/local/artifacts/stage9545_residual_repair_route_manifest/residual_repair_route_manifest_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESIDUAL_REPAIR_ROUTE_AUDIT_STAGE9546.md"
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
    rows = load_jsonl(SOURCE)
    card = load_json(SOURCE_CARD)
    failures: list[str] = []
    if card.get("passed") is not True:
        failures.append("stage9545_card_not_passed")
    if not rows:
        failures.append("missing_stage9545_rows")

    split_counts = Counter(row.get("split") for row in rows)
    bucket_counts = Counter((row.get("residual_repair_route") or {}).get("repair_bucket") for row in rows)
    enabled_losses = Counter(loss for row in rows for loss, enabled in (row.get("loss_mask") or {}).items() if enabled)
    authority_rows = [row.get("row_id") for row in rows if any((row.get("authority") or {}).values())]
    leakage_rows = [row.get("row_id") for row in rows if any(key.startswith("effective_") or key.startswith("rejoin_") or key.startswith("residual_repair_") for key in (row.get("model_input") or {}))]
    terminal_rows = [row.get("row_id") for row in rows if (row.get("rejoin_gate") or {}).get("would_allow_terminal_decode_rejoin_candidate") is True]
    if len(rows) != 29:
        failures.append("unexpected_row_count")
    if split_counts != {"eval": 3, "strict_eval": 3, "train": 23}:
        failures.append("unexpected_split_counts")
    if enabled_losses:
        failures.append("enabled_losses_present")
    if authority_rows:
        failures.append("authority_rows_present")
    if leakage_rows:
        failures.append("effective_rejoin_or_residual_labels_in_model_input")
    if terminal_rows:
        failures.append("terminal_rows_present")
    if bucket_counts.get("REPAIR_PREFIX_ONLY") != 16 or bucket_counts.get("REPAIR_PREFIX_AND_BOUNDARY") != 10:
        failures.append("dominant_bucket_counts_unexpected")

    passed = not failures
    metrics = {
        "passed": passed,
        "failures": failures,
        "source_manifest": str(SOURCE.relative_to(ROOT)),
        "source_card": str(SOURCE_CARD.relative_to(ROOT)),
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "bucket_counts": dict(sorted(bucket_counts.items())),
        "enabled_losses": dict(sorted(enabled_losses.items())),
        "authority_rows": authority_rows,
        "leakage_rows": leakage_rows,
        "terminal_rows": terminal_rows,
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
        "artifacts": {"source_manifest": str(SOURCE.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Audited residual repair routing: 29 residual rows are bucketed safely with all losses and execution authority closed.",
        "next_best_step": "Create counterbalanced residual-denoise design rows for REPAIR_PREFIX_ONLY and REPAIR_PREFIX_AND_BOUNDARY before any denoise execution authorization.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9546 Residual Repair Route Audit",
        "",
        f"Passed: `{passed}`",
        f"Rows: `{len(rows)}`",
        f"Bucket counts: `{dict(bucket_counts)}`",
        f"Enabled losses: `{dict(enabled_losses)}`",
        "",
        "Residual routing is safe but not trainable yet. The next step is counterbalanced denoise-design rows for the dominant residual buckets.",
        "",
    ]))
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": passed, "rows": len(rows), "bucket_counts": dict(bucket_counts), "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
