#!/usr/bin/env python3
"""Merge Stage11955 clean records with Stage11957 counterfactual status support."""

from __future__ import annotations

import json
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11958
NAME = "stage11958_transition_5k_v1_augmented_package"
OUT = ART / NAME
SUMMARY = OUT / "transition_5k_v1_augmented_package.json"
RECORDS = OUT / "verified_transition_records_5k_v1_augmented.jsonl"
ROWS = OUT / "transition_projection_rows_5k_v1_augmented.jsonl"
TRAIN_MANIFEST = OUT / "transition_5k_v1_augmented_train_manifest.jsonl"

BASE_RECORDS = ART / "stage11955_transition_5k_v1_multisource_package/verified_transition_records_5k_v1.jsonl"
BASE_ROWS = ART / "stage11955_transition_5k_v1_multisource_package/transition_projection_rows_5k_v1.jsonl"
COUNTERFACTUAL_RECORDS = ART / "stage11957_transition_counterfactual_status_augmentation/counterfactual_transition_records.jsonl"
COUNTERFACTUAL_ROWS = ART / "stage11957_transition_counterfactual_status_augmentation/counterfactual_transition_projection_rows.jsonl"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def row_id(row: dict[str, Any]) -> str:
    return str(row.get("row_id") or row.get("record_id") or "")


def language_record(record: dict[str, Any]) -> str:
    return str((record.get("task_intent") or {}).get("language_family") or "unknown")


def verifier_status(record: dict[str, Any]) -> str:
    return str((record.get("verifier_result") or {}).get("verifier_status") or "UNKNOWN")


def root_id_record(record: dict[str, Any]) -> str:
    return str((record.get("task_intent") or {}).get("root_id") or record.get("source_lineage_ref") or "")


def root_id_row(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("root_lineage_key") or "")


def split_row(row: dict[str, Any]) -> str:
    return str(row.get("split") or row.get("package_split") or "train")


def main() -> None:
    base_records = read_jsonl(BASE_RECORDS)
    base_rows = read_jsonl(BASE_ROWS)
    cf_records = read_jsonl(COUNTERFACTUAL_RECORDS)
    cf_rows = read_jsonl(COUNTERFACTUAL_ROWS)

    records = base_records + cf_records
    rows = base_rows + cf_rows
    train_manifest = []
    for row in rows:
        out = dict(row)
        if out.get("stage11957_counterfactual_status_augmentation"):
            out["split"] = "train"
            out["package_split"] = "train"
            out["train_support_only"] = True
            out["strict_eval_eligible"] = False
            out["source_heldout_admissible"] = False
        train_manifest.append(out)

    duplicate_records = [rid for rid, count in Counter(row_id(record) for record in records).items() if count > 1]
    duplicate_rows = [rid for rid, count in Counter(row_id(row) for row in train_manifest).items() if count > 1]
    root_splits: dict[str, set[str]] = defaultdict(set)
    for row in train_manifest:
        root_splits[root_id_row(row)].add(split_row(row))
    split_violations = {root: sorted(splits) for root, splits in root_splits.items() if len(splits) > 1}

    pre_option_leaks: list[str] = []
    for row in train_manifest:
        gold = str((row.get("standalone_projection_source") or {}).get("gold_value") or "")
        if gold and len(gold) > 2 and gold not in {"CONTINUE", "ABSTAIN"}:
            before = str(row.get("prompt_text") or "").split("\nCANDIDATES\n", 1)[0]
            if gold in before:
                pre_option_leaks.append(row_id(row))

    base_root_ids = {root_id_record(record) for record in base_records}
    cf_root_ids = {root_id_record(record) for record in cf_records}
    independent_language_counts = Counter(language_record(record) for record in base_records)
    total_language_counts = Counter(language_record(record) for record in records)
    total_status_counts = Counter(verifier_status(record) for record in records)
    base_status_counts = Counter(verifier_status(record) for record in base_records)
    cf_status_counts = Counter(verifier_status(record) for record in cf_records)
    counts = {
        "base_records": len(base_records),
        "counterfactual_records": len(cf_records),
        "total_records": len(records),
        "base_rows": len(base_rows),
        "counterfactual_rows": len(cf_rows),
        "total_rows": len(train_manifest),
        "base_unique_roots": len(base_root_ids),
        "counterfactual_unique_roots": len(cf_root_ids),
        "independent_unique_roots": len(base_root_ids),
        "record_split_counts": dict(Counter(str(record.get("split") or "train") for record in records)),
        "row_split_counts": dict(Counter(split_row(row) for row in train_manifest)),
        "independent_language_record_counts": dict(independent_language_counts),
        "total_language_record_counts": dict(total_language_counts),
        "base_verifier_status_counts": dict(base_status_counts),
        "counterfactual_verifier_status_counts": dict(cf_status_counts),
        "total_verifier_status_counts": dict(total_status_counts),
        "transition_task_row_counts": dict(Counter(str(row.get("task_type")) for row in train_manifest)),
    }

    scale_ready = len(train_manifest) >= 5000 and len(records) >= 1250
    independent_root_ready = len(base_root_ids) >= 250
    independent_language_ready = min(independent_language_counts.get(lang, 0) for lang in ("c_cpp", "python", "rust", "web_js_ts_html")) >= 250
    passed_for_train_support_probe = scale_ready and not duplicate_records and not duplicate_rows and not split_violations and not pre_option_leaks
    passed_for_frontier_claim = passed_for_train_support_probe and independent_root_ready and independent_language_ready

    write_jsonl(RECORDS, records)
    write_jsonl(ROWS, train_manifest)
    write_jsonl(TRAIN_MANIFEST, train_manifest)
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "transition_5k_v1_augmented_train_support_ready_but_not_frontier_source_supply" if passed_for_train_support_probe else "transition_5k_v1_augmented_package_blocked",
        "passed_for_train_support_probe": passed_for_train_support_probe,
        "passed_for_frontier_source_claim": passed_for_frontier_claim,
        "counts": counts,
        "readiness": {
            "scale_ready": scale_ready,
            "independent_root_ready": independent_root_ready,
            "independent_language_ready": independent_language_ready,
            "minimum_independent_language_records": min(independent_language_counts.get(lang, 0) for lang in ("c_cpp", "python", "rust", "web_js_ts_html")),
        },
        "audits": {
            "duplicate_record_ids": duplicate_records[:20],
            "duplicate_record_id_count": len(duplicate_records),
            "duplicate_row_ids": duplicate_rows[:20],
            "duplicate_row_id_count": len(duplicate_rows),
            "root_split_violations": dict(list(split_violations.items())[:20]),
            "root_split_violation_count": len(split_violations),
            "pre_options_target_value_leaks": pre_option_leaks[:20],
            "pre_options_target_value_leak_count": len(pre_option_leaks),
        },
        "training_use": {
            "allowed": passed_for_train_support_probe,
            "recommended_scope": "diagnostic train-support probe for verifier-status and abstain/continue supervision",
            "not_allowed_claim": "Do not claim source-heldout or broad multilingual root-scale improvement from counterfactual rows.",
        },
        "source_artifacts": {
            "base_records": rel(BASE_RECORDS),
            "base_rows": rel(BASE_ROWS),
            "counterfactual_records": rel(COUNTERFACTUAL_RECORDS),
            "counterfactual_rows": rel(COUNTERFACTUAL_ROWS),
        },
        "outputs": {"summary": rel(SUMMARY), "records": rel(RECORDS), "rows": rel(ROWS), "train_manifest": rel(TRAIN_MANIFEST)},
    }
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "passed_for_train_support_probe": passed_for_train_support_probe, "passed_for_frontier_source_claim": passed_for_frontier_claim, "counts": counts, "readiness": artifact["readiness"], "audits": artifact["audits"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
