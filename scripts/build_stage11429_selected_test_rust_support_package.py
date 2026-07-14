#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11429
NAME = "stage11429_selected_test_rust_support_package"
OUT = ART / NAME
SUMMARY = OUT / "selected_test_rust_support_package.json"
TRAIN = OUT / "agentkernel_lite_encdec_train.jsonl"
VALIDATION = OUT / "agentkernel_lite_encdec_validation.jsonl"
STRICT = OUT / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS = OUT / "agentkernel_lite_encdec_stress_eval.jsonl"
ADDED = OUT / "added_selected_test_rust_support_rows.jsonl"
AUDIT = OUT / "selected_test_rust_support_package_audit.json"

BASE = ART / "stage11422_rust_verifier_support_diagnostic_package"
BASE_TRAIN = BASE / "agentkernel_lite_encdec_train.jsonl"
BASE_VALIDATION = BASE / "agentkernel_lite_encdec_validation.jsonl"
BASE_STRICT = BASE / "agentkernel_lite_encdec_strict_eval.jsonl"
BASE_STRESS = BASE / "agentkernel_lite_encdec_stress_eval.jsonl"
RUST_ROWS = ART / "stage11428_codex_rs_selected_test_support_rows/codex_rs_selected_test_support_rows.jsonl"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def root_key(row: dict[str, Any]) -> str:
    return str(row.get("root_lineage_key") or row.get("root_id") or row.get("source_root_id") or row.get("row_id"))


def row_id(row: dict[str, Any]) -> str:
    return str(row.get("row_id"))


def counts_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key, "unknown")) for row in rows).items()))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    base_train = read_jsonl(BASE_TRAIN)
    validation = read_jsonl(BASE_VALIDATION)
    strict = read_jsonl(BASE_STRICT)
    stress = read_jsonl(BASE_STRESS)
    rust_rows = read_jsonl(RUST_ROWS)

    existing_ids = {row_id(row) for row in base_train}
    added_rows = [row for row in rust_rows if row_id(row) not in existing_ids]
    train = base_train + added_rows

    train_roots = {root_key(row) for row in train}
    val_roots = {root_key(row) for row in validation}
    strict_roots = {root_key(row) for row in strict}
    stress_roots = {root_key(row) for row in stress}
    added_roots = {root_key(row) for row in added_rows}
    added_repos = {str(row.get("repo_family")) for row in added_rows}
    root_overlap = {
        "added_validation": sorted(added_roots & val_roots),
        "added_strict": sorted(added_roots & strict_roots),
        "added_stress": sorted(added_roots & stress_roots),
        "train_validation": sorted(train_roots & val_roots),
        "train_strict": sorted(train_roots & strict_roots),
        "train_stress": sorted(train_roots & stress_roots),
    }
    row_dupes = [item for item, count in Counter(row_id(row) for row in train).items() if count > 1]
    selected_test_contract_ok = bool(added_rows) and all(
        row.get("language_family") == "rust"
        and row.get("train_support_only")
        and not row.get("strict_eval_eligible")
        and row.get("selected_test_anchor_present") is True
        and row.get("build_verifier_only") is False
        and (row.get("anti_cheat") or {}).get("source_text_materialized")
        and (row.get("anti_cheat") or {}).get("target_label_not_visible_before_options")
        and (row.get("anti_cheat") or {}).get("actual_verifier_log_attached")
        and (row.get("anti_cheat") or {}).get("selected_test_anchor_present")
        for row in added_rows
    )
    audit = {
        "rows": {
            "base_train": len(base_train),
            "added_selected_test_rust_support": len(added_rows),
            "train": len(train),
            "validation": len(validation),
            "strict": len(strict),
            "stress": len(stress),
        },
        "roots": {
            "added_selected_test_rust_support": len(added_roots),
            "added_repo_families": len(added_repos),
        },
        "by_split_language": {
            "train": counts_by(train, "language_family"),
            "validation": counts_by(validation, "language_family"),
            "strict": counts_by(strict, "language_family"),
            "stress": counts_by(stress, "language_family"),
        },
        "added_by_repo_family": counts_by(added_rows, "repo_family"),
        "added_by_target": counts_by(added_rows, "semantic_target_value"),
        "root_overlap": root_overlap,
        "row_id_duplicates": row_dupes,
        "selected_test_contract_ok": selected_test_contract_ok,
    }
    passed = (
        selected_test_contract_ok
        and not row_dupes
        and not root_overlap["added_validation"]
        and not root_overlap["added_strict"]
        and not root_overlap["added_stress"]
        and len(added_roots) >= 5
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": passed,
        "decision": "selected_test_rust_support_package_ready" if passed else "selected_test_rust_support_package_failed_gate",
        "counts": audit["rows"],
        "added_selected_test_rust_support": audit["roots"],
        "quality_gate": {
            "selected_test_contract_ok": selected_test_contract_ok,
            "row_id_duplicates": len(row_dupes),
            "added_root_overlap_with_validation": len(root_overlap["added_validation"]),
            "added_root_overlap_with_strict": len(root_overlap["added_strict"]),
            "added_root_overlap_with_stress": len(root_overlap["added_stress"]),
            "minimum_selected_test_roots_met": len(added_roots) >= 5,
            "diagnostic_package_ready": passed,
            "promotable_selected_test_package": False,
        },
        "limitations": [
            "Added selected-test rows come from one repo family, codex-rs, so this is diagnostic support rather than broad Rust heldout proof.",
            "Validation, strict, and stress splits are inherited unchanged.",
        ],
        "recommended_next_action": "Run one diagnostic probe only if needed, then audit clean strict, validation, reserved residuals, and Rust evidence slices.",
        "source_artifacts": {
            "base_package": rel(BASE / "rust_verifier_support_diagnostic_package.json"),
            "selected_test_rust_rows": rel(RUST_ROWS),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "audit": rel(AUDIT),
            "train_rows_jsonl": rel(TRAIN),
            "validation_rows_jsonl": rel(VALIDATION),
            "strict_rows_jsonl": rel(STRICT),
            "stress_rows_jsonl": rel(STRESS),
            "added_rows_jsonl": rel(ADDED),
        },
    }
    write_jsonl(TRAIN, train)
    write_jsonl(VALIDATION, validation)
    write_jsonl(STRICT, strict)
    write_jsonl(STRESS, stress)
    write_jsonl(ADDED, added_rows)
    write_json(AUDIT, audit)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(summary["counts"], indent=2, sort_keys=True))
    print(json.dumps(summary["quality_gate"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
