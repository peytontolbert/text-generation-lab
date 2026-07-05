#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8807
NAME = "stage8807_source_backed_decoder_target_materialization_audit"
MANIFEST = ROOT / "runs/local/artifacts/stage8806_source_backed_decoder_target_materialization_controls/source_backed_decoder_target_materialization_controls.jsonl"
TARGET_STORE = ROOT / "runs/local/artifacts/stage8806_source_backed_decoder_target_materialization_controls/source_backed_decoder_target_store.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SOURCE_BACKED_DECODER_TARGET_MATERIALIZATION_AUDIT_STAGE8807.md"
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
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    manifest = read_jsonl(MANIFEST)
    target_store = read_jsonl(TARGET_STORE)
    target_by_ref = {row.get("target_ref"): row for row in target_store}
    manifest_text = "\n".join(json.dumps(row, sort_keys=True) for row in manifest)
    materialized = [row for row in manifest if (row.get("materialization_status") or {}).get("source_backed_target_text_materialized") is True]
    blocked = [row for row in manifest if row not in materialized]
    missing_target_refs = []
    hash_mismatches = []
    for row in materialized:
        clean = row.get("clean_state") or {}
        ref = clean.get("decoder_target_ref")
        target = target_by_ref.get(ref)
        if target is None:
            missing_target_refs.append(row.get("row_id"))
            continue
        if clean.get("decoder_target_text_sha256") != target.get("decoder_text_sha256"):
            hash_mismatches.append(row.get("row_id"))
    hash_splits: dict[str, set[str]] = defaultdict(set)
    hash_refs: dict[str, list[str]] = defaultdict(list)
    for row in target_store:
        h = str(row.get("decoder_text_sha256") or "")
        hash_splits[h].add(str(row.get("split")))
        hash_refs[h].append(str(row.get("target_ref")))
    cross_split_duplicate_hashes = {h: sorted(splits) for h, splits in hash_splits.items() if len(splits) > 1}
    duplicate_hash_ref_count = sum(len(refs) for h, refs in hash_refs.items() if len(refs) > 1)
    target_text_copied = 0
    for target in target_store:
        text = str(target.get("decoder_text") or "")
        target_text_copied += int(bool(text) and text in manifest_text)
    metrics = {
        **AUTHORITY_CLOSED,
        "rows": len(manifest),
        "materialized_rows": len(materialized),
        "blocked_rows": len(blocked),
        "target_store_rows": len(target_store),
        "authority_rows": sum(int(any((row.get("authority") or {}).values())) for row in manifest),
        "target_store_authority_rows": sum(int(any((row.get("authority") or {}).values())) for row in target_store),
        "training_loss_rows": sum(int(any((row.get("loss_mask") or {}).values())) for row in manifest),
        "decoder_ce_eligible_now_rows": sum(int((row.get("clean_state") or {}).get("decoder_ce_eligible_now") is True) for row in manifest),
        "target_text_copied_to_manifest_rows": target_text_copied,
        "missing_target_ref_rows": len(missing_target_refs),
        "hash_mismatch_rows": len(hash_mismatches),
        "target_ref_unique_rows": len({row.get("target_ref") for row in target_store}),
        "target_hash_unique_rows": len(set(hash_splits)),
        "cross_split_duplicate_target_hashes": len(cross_split_duplicate_hashes),
        "cross_split_duplicate_target_ref_rows": duplicate_hash_ref_count,
        "target_store_split_counts": dict(sorted(Counter(row.get("split") for row in target_store).items())),
        "manifest_route_counts": dict(sorted(Counter(row.get("route") for row in manifest).items())),
        "future_ce_blockers": [
            "cross_split_duplicate_target_hashes_require_dedup_or_split_specific_materialization",
            "decoder_ce_loss_not_authorized",
            "tiny_pre_execution_audit_required",
            "explicit_execution_authorization_required",
        ],
        "missing_target_ref_examples": missing_target_refs[:20],
        "hash_mismatch_examples": hash_mismatches[:20],
    }
    failures = []
    expected_zero = [
        "authority_rows",
        "target_store_authority_rows",
        "training_loss_rows",
        "decoder_ce_eligible_now_rows",
        "target_text_copied_to_manifest_rows",
        "missing_target_ref_rows",
        "hash_mismatch_rows",
    ]
    for key in expected_zero:
        if metrics[key] != 0:
            failures.append(f"nonzero:{key}:{metrics[key]}")
    if metrics["rows"] != 504 or metrics["materialized_rows"] != 360 or metrics["blocked_rows"] != 144 or metrics["target_store_rows"] != 360:
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
            "audit_card": str((OUT_DIR / "target_materialization_audit_card.json").relative_to(ROOT)),
            "manifest": str(MANIFEST.relative_to(ROOT)),
            "target_store": str(TARGET_STORE.relative_to(ROOT)),
            "audit_script": "scripts/audit_stage8807_source_backed_decoder_target_materialization_controls.py",
        },
        "decision": "Target materialization controls passed leakage/authority audit; future CE remains blocked by split-dedup and explicit authorization." if not failures else "Target materialization controls failed audit.",
        "next_best_step": "Attach source-backed decoder target materialization controls to the central graph, then design split-deduped closed CE candidate selection without enabling CE.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "target_materialization_audit_card.json").write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8807 Source-Backed Decoder Target Materialization Audit",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Rows: `{metrics['rows']}`",
        f"Materialized rows: `{metrics['materialized_rows']}`",
        f"Blocked rows: `{metrics['blocked_rows']}`",
        f"Target-store rows: `{metrics['target_store_rows']}`",
        f"Target text copied to manifest rows: `{metrics['target_text_copied_to_manifest_rows']}`",
        f"CE eligible now rows: `{metrics['decoder_ce_eligible_now_rows']}`",
        f"Cross-split duplicate target hashes: `{metrics['cross_split_duplicate_target_hashes']}`",
        "",
        "The duplicate target hashes are not an authority failure here because CE remains closed, but they are an explicit future CE blocker until deduped or split-specific materialization is designed.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
