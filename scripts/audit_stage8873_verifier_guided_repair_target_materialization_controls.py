#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8873
NAME = "stage8873_verifier_guided_repair_target_materialization_audit"
MANIFEST = ROOT / "runs/local/artifacts/stage8872_verifier_guided_repair_target_materialization_controls/verifier_guided_repair_target_materialization_controls.jsonl"
TARGET_STORE = ROOT / "runs/local/artifacts/stage8872_verifier_guided_repair_target_materialization_controls/verifier_guided_repair_target_store.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "VERIFIER_GUIDED_REPAIR_TARGET_MATERIALIZATION_AUDIT_STAGE8873.md"
AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = read_jsonl(MANIFEST)
    target_store = read_jsonl(TARGET_STORE)
    target_by_ref = {row.get("target_ref"): row for row in target_store}
    manifest_text = "\n".join(json.dumps(row, sort_keys=True) for row in manifest)
    materialized = [row for row in manifest if (row.get("materialization_status") or {}).get("verifier_guided_target_text_materialized") is True]
    missing_refs = []
    hash_mismatches = []
    for row in materialized:
        clean = row.get("clean_state") or {}
        ref = clean.get("repair_target_ref")
        target = target_by_ref.get(ref)
        if target is None:
            missing_refs.append(row.get("row_id"))
            continue
        if clean.get("repair_target_text_sha256") != target.get("decoder_text_sha256"):
            hash_mismatches.append(row.get("row_id"))
    target_text_copied = 0
    hash_splits: dict[str, set[str]] = defaultdict(set)
    for target in target_store:
        text = str(target.get("decoder_text") or "")
        target_text_copied += int(bool(text) and text in manifest_text)
        hash_splits[str(target.get("decoder_text_sha256") or "")].add(str(target.get("split")))
    metrics = {
        **AUTHORITY_CLOSED,
        "rows": len(manifest),
        "materialized_rows": len(materialized),
        "blocked_rows": len(manifest) - len(materialized),
        "target_store_rows": len(target_store),
        "authority_rows": sum(int(any((row.get("authority") or {}).values())) for row in manifest),
        "target_store_authority_rows": sum(int(any((row.get("authority") or {}).values())) for row in target_store),
        "training_loss_rows": sum(int(any((row.get("loss_mask") or {}).values())) for row in manifest),
        "denoise_ce_eligible_now_rows": sum(int((row.get("clean_state") or {}).get("denoise_ce_eligible_now") is True) for row in manifest),
        "runtime_verifier_execution_eligible_now_rows": sum(int((row.get("clean_state") or {}).get("runtime_verifier_execution_eligible_now") is True) for row in manifest),
        "target_text_copied_to_manifest_rows": target_text_copied,
        "missing_target_ref_rows": len(missing_refs),
        "hash_mismatch_rows": len(hash_mismatches),
        "target_ref_unique_rows": len({row.get("target_ref") for row in target_store}),
        "target_hash_unique_rows": len(hash_splits),
        "cross_split_duplicate_target_hashes": sum(1 for splits in hash_splits.values() if len(splits) > 1),
        "target_store_split_counts": dict(sorted(Counter(row.get("split") for row in target_store).items())),
        "manifest_route_counts": dict(sorted(Counter(row.get("route") for row in manifest).items())),
        "future_denoise_blockers": [
            "denoise_ce_loss_not_authorized",
            "runtime_verifier_execution_not_authorized",
            "repair_denoise_loss_mask_runtime_assertions_required",
            "tiny_pre_execution_audit_required",
            "explicit_execution_authorization_required",
        ],
        "missing_target_ref_examples": missing_refs[:20],
        "hash_mismatch_examples": hash_mismatches[:20],
    }
    failures = []
    for key in [
        "authority_rows",
        "target_store_authority_rows",
        "training_loss_rows",
        "denoise_ce_eligible_now_rows",
        "runtime_verifier_execution_eligible_now_rows",
        "target_text_copied_to_manifest_rows",
        "missing_target_ref_rows",
        "hash_mismatch_rows",
    ]:
        if metrics[key] != 0:
            failures.append(f"nonzero:{key}:{metrics[key]}")
    if metrics["rows"] != 648 or metrics["materialized_rows"] != 648 or metrics["target_store_rows"] != 648:
        failures.append("unexpected_row_counts")
    if metrics["target_ref_unique_rows"] != metrics["target_store_rows"]:
        failures.append("target_ref_not_unique")
    metrics["failures"] = failures
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "artifacts": {
            "audit_card": str((OUT_DIR / "verifier_guided_repair_target_materialization_audit_card.json").relative_to(ROOT)),
            "manifest": str(MANIFEST.relative_to(ROOT)),
            "target_store": str(TARGET_STORE.relative_to(ROOT)),
            "audit_script": "scripts/audit_stage8873_verifier_guided_repair_target_materialization_controls.py",
        },
        "decision": "Verifier-guided repair target materialization passed leakage/authority audit; denoise CE and runtime verifier execution remain closed." if not failures else "Verifier-guided repair target materialization failed audit.",
        "next_best_step": "Attach verifier-guided repair target materialization controls to the central graph, then continue with eval/strict unique target materialization or packet-schema blockers.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "verifier_guided_repair_target_materialization_audit_card.json").write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8873 Verifier-Guided Repair Target Materialization Audit",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Rows: `{metrics['rows']}`",
        f"Materialized rows: `{metrics['materialized_rows']}`",
        f"Target-store rows: `{metrics['target_store_rows']}`",
        f"Target text copied to manifest rows: `{metrics['target_text_copied_to_manifest_rows']}`",
        f"Denoise CE eligible now rows: `{metrics['denoise_ce_eligible_now_rows']}`",
        f"Runtime verifier execution eligible now rows: `{metrics['runtime_verifier_execution_eligible_now_rows']}`",
        "",
        "This audit verifies target refs/hash wiring and confirms repair target text remains out of model-visible manifests. Future denoise/runtime work is still blocked by explicit gates.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
