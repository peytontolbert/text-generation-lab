#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from verifier_guided_repair_target_materialization_builder import (  # noqa: E402
    AUTHORITY_CLOSED,
    build_card,
    build_materialization_controls,
    read_jsonl,
    write_jsonl,
)

STAGE = 8872
NAME = "stage8872_verifier_guided_repair_target_materialization_controls"
SOURCE = ROOT / "runs/local/artifacts/stage8788_source_backed_verifier_repair_candidate_manifest/source_backed_verifier_repair_candidate_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "VERIFIER_GUIDED_REPAIR_TARGET_MATERIALIZATION_CONTROLS_STAGE8872.md"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    test = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "tests/test_verifier_guided_repair_target_materialization_builder.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    manifest, target_store = build_materialization_controls(read_jsonl(SOURCE))
    manifest_path = OUT_DIR / "verifier_guided_repair_target_materialization_controls.jsonl"
    target_store_path = OUT_DIR / "verifier_guided_repair_target_store.jsonl"
    card_path = OUT_DIR / "verifier_guided_repair_target_materialization_card.json"
    write_jsonl(manifest_path, manifest)
    write_jsonl(target_store_path, target_store)
    metrics = build_card(manifest, target_store)
    failures: list[str] = []
    if test.returncode != 0:
        failures.append("unit_tests_failed")
    expected = {
        "rows": 648,
        "materialized_rows": 648,
        "blocked_rows": 0,
        "target_store_rows": 648,
        "authority_rows": 0,
        "target_store_authority_rows": 0,
        "training_loss_rows": 0,
        "denoise_ce_eligible_now_rows": 0,
        "runtime_verifier_execution_eligible_now_rows": 0,
        "target_text_visible_in_manifest_rows": 0,
        "target_text_copied_to_manifest_rows": 0,
        "over_cap_target_store_rows": 0,
        "empty_target_store_rows": 0,
        "internal_token_target_store_rows": 0,
        "html_target_store_rows": 0,
        "repetition_target_store_rows": 0,
    }
    for key, value in expected.items():
        if metrics.get(key) != value:
            failures.append(f"metric_mismatch:{key}:{metrics.get(key)}!={value}")
    if metrics["gate_status"].get("complete_gate_status_rows") != metrics["rows"]:
        failures.append("incomplete_gate_status")
    if metrics["target_ref_unique_rows"] != metrics["target_store_rows"]:
        failures.append("target_ref_not_unique")
    metrics["failures"] = failures
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {**AUTHORITY_CLOSED, **metrics},
        "artifacts": {
            "manifest": str(manifest_path.relative_to(ROOT)),
            "target_store": str(target_store_path.relative_to(ROOT)),
            "card": str(card_path.relative_to(ROOT)),
            "source_manifest": str(SOURCE.relative_to(ROOT)),
            "builder": "scripts/verifier_guided_repair_target_materialization_builder.py",
            "tests": "tests/test_verifier_guided_repair_target_materialization_builder.py",
        },
        "decision": "Materialized verifier-guided repair targets into a separate target store while keeping manifest/model input target-text-free and denoise/runtime closed." if not failures else "Verifier-guided repair target materialization controls failed.",
        "next_best_step": "Audit verifier-guided repair target materialization controls before any denoise CE or runtime verifier loop is considered.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    card_path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8872 Verifier-Guided Repair Target Materialization Controls",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Rows: `{metrics['rows']}`",
        f"Materialized rows: `{metrics['materialized_rows']}`",
        f"Target-store rows: `{metrics['target_store_rows']}`",
        f"Denoise CE eligible now rows: `{metrics['denoise_ce_eligible_now_rows']}`",
        f"Runtime verifier execution eligible now rows: `{metrics['runtime_verifier_execution_eligible_now_rows']}`",
        f"Training loss rows: `{metrics['training_loss_rows']}`",
        f"Authority rows: `{metrics['authority_rows']}`",
        "",
        "Verifier repair target text is stored only in the target-store artifact. The model-visible manifest carries target refs, hashes, and lengths only. Denoise CE, runtime, decoder CE, source/body emission, Gemma, harness, scoring, and promotion remain closed.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
