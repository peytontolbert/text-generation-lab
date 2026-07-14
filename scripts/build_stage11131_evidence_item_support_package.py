#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11131
NAME = "stage11131_evidence_item_support_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "evidence_item_support_package.json"
TRAIN_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"
ADDED_ROWS_JSONL = OUT_DIR / "added_evidence_item_option_rows.jsonl"

BASE_PACKAGE = ARTIFACTS / "stage11114_fresh_family_support_package_with_trainable_admitted_evidence"
BASE_TRAIN = BASE_PACKAGE / "agentkernel_lite_encdec_train.jsonl"
BASE_VALIDATION = BASE_PACKAGE / "agentkernel_lite_encdec_validation.jsonl"
BASE_STRICT = BASE_PACKAGE / "agentkernel_lite_encdec_strict_eval.jsonl"
BASE_STRESS = BASE_PACKAGE / "agentkernel_lite_encdec_stress_eval.jsonl"
BASE_ADDED = BASE_PACKAGE / "added_admitted_evidence_rows_trainable.jsonl"
BASE_SUMMARY = BASE_PACKAGE / "fresh_family_support_package_with_trainable_admitted_evidence.json"
REWRITE_ROWS = ARTIFACTS / "stage11130_evidence_item_option_rewrite" / "evidence_item_option_rows.jsonl"
REWRITE_SUMMARY = ARTIFACTS / "stage11130_evidence_item_option_rewrite" / "evidence_item_option_rewrite.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def source_base_id(row_id: str) -> str:
    return row_id.replace("::evidence_item_options_v1", "")


def main() -> None:
    base_summary = load_json(BASE_SUMMARY)
    rewrite_summary = load_json(REWRITE_SUMMARY)
    base_train = load_jsonl(BASE_TRAIN)
    validation = load_jsonl(BASE_VALIDATION)
    strict = load_jsonl(BASE_STRICT)
    stress = load_jsonl(BASE_STRESS)
    base_added = load_jsonl(BASE_ADDED)
    rewritten = load_jsonl(REWRITE_ROWS)

    replaced_ids = {str(row.get("row_id") or "") for row in base_added}
    rewritten_source_ids = {source_base_id(str(row.get("row_id") or "")) for row in rewritten}
    if replaced_ids != rewritten_source_ids:
        missing = sorted(replaced_ids - rewritten_source_ids)[:10]
        extra = sorted(rewritten_source_ids - replaced_ids)[:10]
        raise SystemExit(f"rewrite/source id mismatch missing={missing} extra={extra}")

    train_without_old = [row for row in base_train if str(row.get("row_id") or "") not in replaced_ids]
    train = train_without_old + rewritten

    strict_ids = {str(row.get("row_id") or "") for row in strict}
    validation_ids = {str(row.get("row_id") or "") for row in validation}
    support_ids = {str(row.get("row_id") or "") for row in rewritten}
    support_roots = {str(row.get("source_root_id") or "") for row in rewritten if row.get("source_root_id")}
    strict_roots = {str(row.get("source_root_id") or "") for row in strict if row.get("source_root_id")}
    validation_roots = {str(row.get("source_root_id") or "") for row in validation if row.get("source_root_id")}

    role_names = {"candidate_change_surface", "verifier_and_test_constraint", "symptom_or_call_path_analogue", "nearby_definition_or_usage_context"}
    support_prompt_role_leaks = [row.get("row_id") for row in rewritten if any(role in str(row.get("prompt_text") or "") for role in role_names)]
    support_option_role_leaks = [row.get("row_id") for row in rewritten if any(role in json.dumps(row.get("opaque_options") or [], sort_keys=True) for role in role_names)]

    metrics = {
        "base_train_rows": len(base_train),
        "train_rows_after": len(train),
        "old_role_name_rows_replaced": len(replaced_ids),
        "evidence_item_rows_added": len(rewritten),
        "validation_rows_unchanged": len(validation),
        "strict_rows_unchanged": len(strict),
        "stress_rows_unchanged": len(stress),
        "support_row_overlap_strict": sorted(support_ids & strict_ids),
        "support_row_overlap_validation": sorted(support_ids & validation_ids),
        "support_source_root_overlap_strict": sorted(support_roots & strict_roots),
        "support_source_root_overlap_validation": sorted(support_roots & validation_roots),
        "support_prompt_role_leak_rows": support_prompt_role_leaks,
        "support_option_role_leak_rows": support_option_role_leaks,
        "by_language_added": rewrite_summary.get("metrics", {}).get("by_language"),
        "by_repo_family_added": rewrite_summary.get("metrics", {}).get("by_repo_family"),
        "target_label_counts_added": rewrite_summary.get("metrics", {}).get("target_label_counts"),
    }
    passed = (
        len(train) == len(base_train)
        and not metrics["support_row_overlap_strict"]
        and not metrics["support_row_overlap_validation"]
        and not metrics["support_source_root_overlap_strict"]
        and not metrics["support_source_root_overlap_validation"]
        and not support_prompt_role_leaks
        and not support_option_role_leaks
    )

    write_jsonl(TRAIN_JSONL, train)
    write_jsonl(VALIDATION_JSONL, validation)
    write_jsonl(STRICT_JSONL, strict)
    write_jsonl(STRESS_JSONL, stress)
    write_jsonl(ADDED_ROWS_JSONL, rewritten)

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": passed,
        "decision": "evidence_item_support_package_ready" if passed else "evidence_item_support_package_blocked",
        "claim_scope": [
            "Replace stage11114 role-name evidence support rows with evidence-item option rows while keeping validation and strict unchanged.",
            "Make the next probe test visible evidence descriptions instead of semantic role alias memorization.",
        ],
        "source_artifacts": {
            "base_package": rel(BASE_SUMMARY),
            "base_added_rows": rel(BASE_ADDED),
            "rewrite_summary": rel(REWRITE_SUMMARY),
            "rewrite_rows": rel(REWRITE_ROWS),
        },
        "base_package_metrics": base_summary.get("metrics"),
        "metrics": metrics,
        "next_best_step": "Run one encoder_option_retrieval probe from this package and audit strict/validation/reserved before considering further training.",
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "train_jsonl": rel(TRAIN_JSONL),
            "validation_jsonl": rel(VALIDATION_JSONL),
            "strict_jsonl": rel(STRICT_JSONL),
            "stress_jsonl": rel(STRESS_JSONL),
            "added_rows_jsonl": rel(ADDED_ROWS_JSONL),
        },
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
