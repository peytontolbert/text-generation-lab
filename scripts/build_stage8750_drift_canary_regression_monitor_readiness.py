#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from drift_canary_regression_monitor import evaluate_canaries

STAGE = 8750
NAME = "stage8750_drift_canary_regression_monitor_readiness"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "DRIFT_CANARY_REGRESSION_MONITOR_READINESS_STAGE8750.md"
BACKUP_ROOT = Path("/arxiv/agentkernel_recovery/stage8750_8751_drift_canary_regression_monitor")
AUTHORITY_CLOSED = {"model_execution_authorized_next": False, "decoder_ce_training_authorized_next": False, "denoise_ce_training_authorized_next": False, "runtime_authorized": False, "source_emission_authorized": False, "body_emission_authorized": False, "gemma_execution_authorized_next": False, "harness_execution_authorized_next": False, "scoring_authorized_next": False, "controller_complete_merge_authorized_next": False, "promotion_ready": False}
SAMPLE_CANARIES = [
    {"canary_id": "symbol_binding_guard", "baseline_score": 0.98, "current_score": 0.98, "min_score": 0.95, "max_allowed_drop": 0.02, "metric_card_present": True, "slice_tags": ["symbol_binding"]},
    {"canary_id": "decoder_validity_guard", "baseline_score": 0.80, "current_score": 0.70, "min_score": 0.78, "max_allowed_drop": 0.02, "metric_card_present": True, "slice_tags": ["decoder_validity"]},
]


def write_registry(card: dict) -> None:
    path = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
    registry = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"passed": True, "rows": []}
    rows = [row for row in registry.get("rows", []) if int(row.get("stage", -1)) != STAGE]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: int(row.get("stage", -1)))
    registry["rows"] = rows
    registry["passed"] = all(row.get("passed") is True for row in rows)
    registry["metrics"] = {**registry.get("metrics", {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": card["next_best_step"], "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    path.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def backup(paths: list[Path]) -> int:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    copied = 0
    for src in paths:
        if src.exists():
            dst = BACKUP_ROOT / src.relative_to(ROOT)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied += 1
    return copied


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    test = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/test_drift_canary_regression_monitor.py"], cwd=ROOT, text=True, capture_output=True, check=False)
    sample = evaluate_canaries(SAMPLE_CANARIES)
    sample_path = OUT_DIR / "drift_canary_sample_card.json"
    sample_path.write_text(json.dumps(sample, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failures: list[str] = []
    if test.returncode != 0:
        failures.append("unit_tests_failed")
    if sample["metrics"]["promotion_blocked"] is not True or sample["metrics"]["forgotten_skill_count"] != 1:
        failures.append("sample_regression_not_detected")
    card = {"stage": STAGE, "stage_name": NAME, "passed": not failures, "authority": AUTHORITY_CLOSED, "metrics": {**AUTHORITY_CLOSED, "sample_canaries": len(SAMPLE_CANARIES), "sample_promotion_blocked": sample["metrics"]["promotion_blocked"], "sample_forgotten_skill_count": sample["metrics"]["forgotten_skill_count"], "failures": failures}, "artifacts": {"sample_card": str(sample_path.relative_to(ROOT)), "backup_root": str(BACKUP_ROOT)}, "decision": "Drift canary regression monitor is ready as a deterministic promotion-blocking contract." if not failures else "Drift canary readiness failed.", "next_best_step": "Attach drift_canary_regression_monitor to the central graph, then run support-stack integration audit.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8750 Drift Canary Regression Monitor Readiness", "", f"Passed: `{card['passed']}`", "", "Recovered deterministic canary/regression monitor. It blocks promotion when old skill slices regress, locked-eval leakage appears, contamination appears, or metric cards are missing.", "", "Authority remains closed.", ""]), encoding="utf-8")
    card["metrics"]["backup_files_copied"] = backup([ROOT / "scripts/drift_canary_regression_monitor.py", ROOT / "tests/test_drift_canary_regression_monitor.py", SUMMARY, DOC, sample_path])
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_registry(card)
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
