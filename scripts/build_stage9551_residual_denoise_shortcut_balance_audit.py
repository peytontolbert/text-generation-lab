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
STAGE = 9551
NAME = "stage9551_residual_denoise_shortcut_balance_audit"
SOURCE_REAL = ROOT / "runs/local/artifacts/stage9545_residual_repair_route_manifest/residual_repair_route_manifest.jsonl"
SOURCE_DESIGN = ROOT / "runs/local/artifacts/stage9549_residual_denoise_design_examples/residual_denoise_design_examples.jsonl"
SOURCE_AUDIT = ROOT / "runs/summaries/stage9550_residual_denoise_design_examples_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage9551_residual_denoise_shortcut_balance_audit"
AUDIT = OUT_DIR / "residual_denoise_shortcut_balance_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESIDUAL_DENOISE_SHORTCUT_BALANCE_AUDIT_STAGE9551.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

TARGET_BUCKETS = {"REPAIR_PREFIX_ONLY", "REPAIR_PREFIX_AND_BOUNDARY"}
INTENDED_DISCRIMINATORS = {"obs_has_boundary_next_token_miss_reason", "obs_boundary_relation"}
FORBIDDEN_FEATURES = {"language_family", "split", "route", "objective_family", "source_kind"}


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


def real_bucket(row: dict) -> str:
    return str((row.get("residual_repair_route") or {}).get("repair_bucket"))


def design_bucket(row: dict) -> str:
    return str((row.get("target") or {}).get("repair_bucket"))


def normalize_rows(real_rows: list[dict], design_rows: list[dict]) -> list[dict]:
    rows = []
    for row in real_rows:
        bucket = real_bucket(row)
        if bucket in TARGET_BUCKETS:
            rows.append({"row_id": row.get("row_id"), "kind": "real", "language_family": row.get("language_family"), "split": row.get("split"), "route": row.get("route"), "objective_family": row.get("objective_family"), "model_input": row.get("model_input") or {}, "target_bucket": bucket, "loss_mask": row.get("loss_mask") or {}, "authority": row.get("authority") or {}})
    for row in design_rows:
        bucket = design_bucket(row)
        if bucket in TARGET_BUCKETS:
            rows.append({"row_id": row.get("row_id"), "kind": "design", "language_family": row.get("language_family"), "split": row.get("split"), "route": row.get("route"), "objective_family": row.get("objective_family"), "model_input": row.get("model_input") or {}, "target_bucket": bucket, "loss_mask": row.get("loss_mask") or {}, "authority": row.get("authority") or {}})
    return rows


def feature_exact(rows: list[dict], feature: str) -> float:
    groups: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        if feature in row:
            value = row.get(feature)
        else:
            value = (row.get("model_input") or {}).get(feature)
        groups[str(value)][row["target_bucket"]] += 1
    correct = sum(counter.most_common(1)[0][1] for counter in groups.values() if counter)
    return correct / len(rows) if rows else 0.0


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source_audit = load_json(SOURCE_AUDIT)
    real_rows = load_jsonl(SOURCE_REAL)
    design_rows = load_jsonl(SOURCE_DESIGN)
    rows = normalize_rows(real_rows, design_rows)
    failures: list[str] = []
    if source_audit.get("passed") is not True:
        failures.append("stage9550_audit_not_passed")
    if not rows:
        failures.append("missing_combined_rows")

    bucket_counts = Counter(row["target_bucket"] for row in rows)
    language_bucket_counts = Counter((row["language_family"], row["target_bucket"]) for row in rows)
    kind_counts = Counter(row["kind"] for row in rows)
    enabled_losses = Counter(loss for row in rows for loss, enabled in (row.get("loss_mask") or {}).items() if enabled)
    authority_rows = [row["row_id"] for row in rows if any((row.get("authority") or {}).values())]
    label_leak_rows = [row["row_id"] for row in rows if any(key in (row.get("model_input") or {}) for key in ["target_bucket", "target_repair_bucket", "repair_bucket", "failure_type", "effective_failure_type"])]
    forbidden_baselines = {feature: feature_exact(rows, feature) for feature in sorted(FORBIDDEN_FEATURES)}
    intended_baselines = {feature: feature_exact(rows, feature) for feature in sorted(INTENDED_DISCRIMINATORS)}
    strongest_forbidden = max(forbidden_baselines.values()) if forbidden_baselines else 0.0
    if len(rows) != 41:
        failures.append("unexpected_combined_row_count")
    for language in ["cpp", "python", "rust", "web_js_ts_html"]:
        for bucket in TARGET_BUCKETS:
            if language_bucket_counts[(language, bucket)] < 4:
                failures.append(f"language_bucket_under_4::{language}::{bucket}")
    if enabled_losses:
        failures.append("enabled_losses_present")
    if authority_rows:
        failures.append("authority_rows_present")
    if label_leak_rows:
        failures.append("label_leak_rows")
    if strongest_forbidden >= 0.80:
        failures.append("forbidden_single_feature_baseline_too_high")

    passed = not failures
    audit = {"passed": passed, "failures": failures, "real_source": str(SOURCE_REAL.relative_to(ROOT)), "design_source": str(SOURCE_DESIGN.relative_to(ROOT)), "rows": len(rows), "kind_counts": dict(sorted(kind_counts.items())), "bucket_counts": dict(sorted(bucket_counts.items())), "language_bucket_counts": {"|".join(k): v for k, v in sorted(language_bucket_counts.items())}, "enabled_losses": dict(sorted(enabled_losses.items())), "authority_rows": authority_rows, "label_leak_rows": label_leak_rows, "forbidden_single_feature_baselines": forbidden_baselines, "intended_observation_discriminator_baselines": intended_baselines, "strongest_forbidden_single_feature_baseline": strongest_forbidden, "authority": dict(AUTHORITY_CLOSED), "model_execution_authorized_next": False, "decoder_ce_training_authorized_next": False, "denoise_ce_training_authorized_next": False, "runtime_authorized_next": False, "promotion_ready": False}
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    summary = {"stage": STAGE, "stage_name": NAME, "name": NAME, "passed": passed, "authority": dict(AUTHORITY_CLOSED), "metrics": {**dict(AUTHORITY_CLOSED), **audit}, "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))}, "decision": "Audited combined residual-denoise rows for balance. Forbidden proxy baselines stay below gate; intended observation discriminators are recorded separately and are not treated as label leakage.", "next_best_step": "Build a no-execution residual-denoise authorization review card that requires Stage9551 plus telemetry before any tiny denoise probe.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join(["# Stage9551 Residual Denoise Shortcut Balance Audit", "", f"Passed: `{passed}`", f"Rows: `{len(rows)}`", f"Bucket counts: `{dict(bucket_counts)}`", f"Strongest forbidden baseline: `{strongest_forbidden}`", "", "Intended observation discriminators are recorded separately from forbidden metadata shortcuts.", ""]))
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": passed, "rows": len(rows), "strongest_forbidden": strongest_forbidden, "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
