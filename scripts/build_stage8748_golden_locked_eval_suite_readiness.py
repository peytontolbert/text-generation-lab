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
from golden_locked_eval_suite import validate_suite

STAGE = 8748
NAME = "stage8748_golden_locked_eval_suite_readiness"
SOURCE = ROOT / "runs/summaries/stage8672_locked_benchmark_pack_manifest.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "GOLDEN_LOCKED_EVAL_SUITE_READINESS_STAGE8748.md"
BACKUP_ROOT = Path("/arxiv/agentkernel_recovery/stage8748_8749_golden_locked_eval_suite")
AUTHORITY_CLOSED = {"model_execution_authorized_next": False, "decoder_ce_training_authorized_next": False, "denoise_ce_training_authorized_next": False, "runtime_authorized": False, "source_emission_authorized": False, "body_emission_authorized": False, "gemma_execution_authorized_next": False, "harness_execution_authorized_next": False, "scoring_authorized_next": False, "controller_complete_merge_authorized_next": False, "promotion_ready": False}


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
    test = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/test_golden_locked_eval_suite.py"], cwd=ROOT, text=True, capture_output=True, check=False)
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    suite = validate_suite(source.get("benchmark_packs", []))
    suite_path = OUT_DIR / "golden_locked_eval_suite_card.json"
    suite_path.write_text(json.dumps(suite, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failures: list[str] = []
    if test.returncode != 0:
        failures.append("unit_tests_failed")
    if not suite.get("passed"):
        failures.append("suite_validation_failed")
    if suite["metrics"]["train_eligible_packs"] != 0:
        failures.append("train_eligible_locked_pack")
    card = {"stage": STAGE, "stage_name": NAME, "passed": not failures, "authority": AUTHORITY_CLOSED, "metrics": {**AUTHORITY_CLOSED, **suite["metrics"], "failures": failures}, "artifacts": {"suite_card": str(suite_path.relative_to(ROOT)), "source_manifest": str(SOURCE.relative_to(ROOT)), "backup_root": str(BACKUP_ROOT)}, "locked_source_ids": suite["locked_source_ids"], "decision": "Golden locked eval suite helper is ready; locked source IDs are promotion-only and blocked from training builders." if not failures else "Golden locked eval suite readiness failed.", "next_best_step": "Attach golden_locked_eval_suite to the central graph, then recover drift canary regression monitor.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8748 Golden Locked Eval Suite Readiness", "", f"Passed: `{card['passed']}`", "", "Recovered locked eval helper over Stage8672 benchmark packs. These packs are promotion-only and never train-eligible.", "", "Authority remains closed.", ""]), encoding="utf-8")
    card["metrics"]["backup_files_copied"] = backup([ROOT / "scripts/golden_locked_eval_suite.py", ROOT / "tests/test_golden_locked_eval_suite.py", SOURCE, SUMMARY, DOC, suite_path])
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_registry(card)
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
