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
STAGE = 9557
NAME = "stage9557_combined_residual_denoise_manifest_audit"
MANIFEST = ROOT / "runs/local/artifacts/stage9556_combined_residual_denoise_manifest/combined_residual_denoise_manifest.jsonl"
CARD = ROOT / "runs/local/artifacts/stage9556_combined_residual_denoise_manifest/combined_residual_denoise_manifest_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "COMBINED_RESIDUAL_DENOISE_MANIFEST_AUDIT_STAGE9557.md"
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
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")


def main() -> None:
    rows = load_jsonl(MANIFEST)
    card = load_json(CARD)
    failures: list[str] = []
    if card.get("passed") is not True:
        failures.append("stage9556_card_not_passed")
    if not rows:
        failures.append("missing_manifest_rows")
    route_counts = Counter(row.get("route") for row in rows)
    bucket_counts = Counter(str((row.get("target") or {}).get("repair_bucket")) for row in rows)
    enabled_losses = Counter(loss for row in rows for loss, enabled in (row.get("loss_mask") or {}).items() if enabled)
    authority_rows = [row.get("row_id") for row in rows if any((row.get("authority") or {}).values())]
    leakage_rows = [row.get("row_id") for row in rows if any(key in (row.get("model_input") or {}) for key in ["target", "repair_bucket", "target_repair_bucket", "failure_type", "effective_failure_type", "residual_denoise_contract"])]
    candidate_rows = [row.get("row_id") for row in rows if (row.get("residual_denoise_contract") or {}).get("candidate_for_future_denoise_ce")]
    holdout_rows = [row.get("row_id") for row in rows if (row.get("residual_denoise_contract") or {}).get("rare_holdout")]
    if len(rows) != 44:
        failures.append("unexpected_row_count")
    if len(candidate_rows) != 41 or len(holdout_rows) != 3:
        failures.append("candidate_holdout_count_mismatch")
    if enabled_losses:
        failures.append("enabled_losses_present")
    if authority_rows:
        failures.append("authority_rows_present")
    if leakage_rows:
        failures.append("target_or_contract_leaked_into_model_input")
    passed = not failures
    metrics = {"passed": passed, "failures": failures, "manifest": str(MANIFEST.relative_to(ROOT)), "rows": len(rows), "candidate_rows": len(candidate_rows), "rare_holdout_rows": len(holdout_rows), "route_counts": dict(sorted(route_counts.items())), "bucket_counts": dict(sorted(bucket_counts.items())), "enabled_losses": dict(sorted(enabled_losses.items())), "authority_rows": authority_rows, "leakage_rows": leakage_rows, "authority": dict(AUTHORITY_CLOSED), "model_execution_authorized_next": False, "decoder_ce_training_authorized_next": False, "denoise_ce_training_authorized_next": False, "runtime_authorized": False, "promotion_ready": False}
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    summary = {"stage": STAGE, "stage_name": NAME, "name": NAME, "passed": passed, "authority": dict(AUTHORITY_CLOSED), "metrics": {**dict(AUTHORITY_CLOSED), **metrics}, "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))}, "decision": "Audited the combined residual-denoise manifest: all losses are closed, target labels stay outside model_input, and rare residuals are held out.", "next_best_step": "Run Stage9558 contract-only manifest preflight with denoise CE still closed until explicit authorization.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join(["# Stage9557 Combined Residual Denoise Manifest Audit", "", f"Passed: `{passed}`", f"Rows: `{len(rows)}`", f"Candidate rows: `{len(candidate_rows)}`", f"Enabled losses: `{dict(enabled_losses)}`", "", "The manifest is safe for contract-only preflight, not execution.", ""]))
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": passed, "rows": len(rows), "candidate_rows": len(candidate_rows), "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
