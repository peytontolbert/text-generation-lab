#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10665
NAME = "stage10665_reviewed_v27_refreshed_support_package"
OUT_DIR = ARTIFACTS / NAME
PACKAGE_JSON = OUT_DIR / "reviewed_v27_refreshed_support_package.json"
TRAIN_JSONL = OUT_DIR / "train_rows.jsonl"
VALIDATION_JSONL = OUT_DIR / "validation_rows.jsonl"
STRICT_JSONL = OUT_DIR / "strict_rows.jsonl"
STRESS_JSONL = OUT_DIR / "stress_rows.jsonl"
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"

BASE_PACKAGE = ARTIFACTS / "stage10420_reviewed_multilingual_v27_manifest_package/reviewed_multilingual_v27_manifest_package.json"
BASE_TRAIN = ARTIFACTS / "stage10420_reviewed_multilingual_v27_manifest_package/agentkernel_lite_encdec_train.jsonl"
BASE_VALIDATION = ARTIFACTS / "stage10420_reviewed_multilingual_v27_manifest_package/agentkernel_lite_encdec_validation.jsonl"
BASE_STRICT = ARTIFACTS / "stage10420_reviewed_multilingual_v27_manifest_package/agentkernel_lite_encdec_strict_eval.jsonl"
BASE_STRESS = ARTIFACTS / "stage10420_reviewed_multilingual_v27_manifest_package/agentkernel_lite_encdec_stress_eval.jsonl"
BASE_ROOTS = ARTIFACTS / "stage10420_reviewed_multilingual_v27_manifest_package/reviewed_multilingual_v27_root_manifest.jsonl"

PYTHON_SUPPORT = ARTIFACTS / "stage10327_python_mirrormind_replenishment_execution_request/python_mirrormind_replenishment_train_rows.jsonl"
RUST_FLASH_SUPPORT = ARTIFACTS / "stage10663_rust_flash_attn_executable_support_audit/rust_flash_attn_executable_support_rows.jsonl"
RUST_CANDLE_SUPPORT = ARTIFACTS / "stage10476_rust_citation_materialized_root_bundle_builder/rust_citation_materialized_bounded_rows.jsonl"
SUPPLY_ATLAS = ARTIFACTS / "stage10662_reviewed_source_supply_upgrade_atlas/reviewed_source_supply_upgrade_atlas.json"
RUST_REFRESH = ARTIFACTS / "stage10664_rust_materialization_inventory_refresh/rust_materialization_inventory_refresh.json"


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


def row_root_id(row: dict[str, Any]) -> str:
    return str(row.get("source_root_id") or row.get("source_bundle_id") or "unknown")


def package_source_kind(row: dict[str, Any], source_kind: str) -> dict[str, Any]:
    updated = json.loads(json.dumps(row))
    updated["package_source_kind"] = source_kind
    updated["support_package_stage"] = STAGE
    return updated


def main() -> None:
    base_package = load_json(BASE_PACKAGE)
    base_train = [package_source_kind(row, "reviewed_base_train") for row in load_jsonl(BASE_TRAIN)]
    base_validation = [package_source_kind(row, "reviewed_base_validation") for row in load_jsonl(BASE_VALIDATION)]
    base_strict = [package_source_kind(row, "reviewed_base_strict") for row in load_jsonl(BASE_STRICT)]
    base_stress = [package_source_kind(row, "reviewed_base_stress") for row in load_jsonl(BASE_STRESS)]
    base_root_rows = load_jsonl(BASE_ROOTS)

    python_support = [package_source_kind(row, "fresh_python_support") for row in load_jsonl(PYTHON_SUPPORT)]
    rust_flash_support = [package_source_kind(row, "fresh_rust_flash_support") for row in load_jsonl(RUST_FLASH_SUPPORT)]
    rust_candle_support = [package_source_kind(row, "fresh_rust_candle_support") for row in load_jsonl(RUST_CANDLE_SUPPORT)]

    support_atlas = load_json(SUPPLY_ATLAS)
    rust_refresh = load_json(RUST_REFRESH)

    reserved_eval_roots = {row_root_id(row) for row in [*base_validation, *base_strict, *base_stress]}
    overlap_filtered_support: list[dict[str, Any]] = []
    excluded_support_rows: list[dict[str, Any]] = []
    for row in [*python_support, *rust_flash_support, *rust_candle_support]:
        if row_root_id(row) in reserved_eval_roots:
            excluded = dict(row)
            excluded["exclusion_reason"] = "root_overlaps_validation_or_strict_or_stress"
            excluded_support_rows.append(excluded)
            continue
        overlap_filtered_support.append(row)

    support_rows = overlap_filtered_support
    refreshed_train = [*base_train, *support_rows]

    train_roots = {row_root_id(row) for row in refreshed_train}
    validation_roots = {row_root_id(row) for row in base_validation}
    strict_roots = {row_root_id(row) for row in base_strict}
    stress_roots = {row_root_id(row) for row in base_stress}

    split_violations = {
        "train_validation_overlap": sorted(train_roots & validation_roots),
        "train_strict_overlap": sorted(train_roots & strict_roots),
        "train_stress_overlap": sorted(train_roots & stress_roots),
        "validation_strict_overlap": sorted(validation_roots & strict_roots),
    }

    support_row_counts = {
        "python_support_rows": len(python_support),
        "rust_flash_support_rows": len(rust_flash_support),
        "rust_candle_support_rows": len(rust_candle_support),
    }

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": not any(split_violations.values()),
        "decision": "reviewed_v27_refreshed_support_package_ready",
        "source_package": rel(BASE_PACKAGE),
        "sources": {
            "base_train": rel(BASE_TRAIN),
            "base_validation": rel(BASE_VALIDATION),
            "base_strict": rel(BASE_STRICT),
            "base_stress": rel(BASE_STRESS),
            "python_support": rel(PYTHON_SUPPORT),
            "rust_flash_support": rel(RUST_FLASH_SUPPORT),
            "rust_candle_support": rel(RUST_CANDLE_SUPPORT),
            "source_supply_upgrade_atlas": rel(SUPPLY_ATLAS),
            "rust_materialization_refresh": rel(RUST_REFRESH),
        },
        "claim_scope": [
            "Refresh the reviewed v2.7 multilingual package with train-support-only Python and Rust additions while preserving the original eval/strict/stress boundaries.",
            "Turn the upgraded Rust support state into an executable training package without widening the promotable same-manifest claim path.",
        ],
        "metrics": {
            "base_train_rows": len(base_train),
            "refreshed_train_rows": len(refreshed_train),
            "validation_rows": len(base_validation),
            "strict_rows": len(base_strict),
            "stress_rows": len(base_stress),
            "support_row_counts": support_row_counts,
            "excluded_support_rows": len(excluded_support_rows),
            "train_language_counts": dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in refreshed_train).items())),
            "train_source_kind_counts": dict(sorted(Counter(str(row.get("package_source_kind") or "unknown") for row in refreshed_train).items())),
            "strict_language_counts": dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in base_strict).items())),
            "train_root_count": len(train_roots),
            "validation_root_count": len(validation_roots),
            "strict_root_count": len(strict_roots),
            "stress_root_count": len(stress_roots),
        },
        "support_root_summary": {
            "upgraded_rust_support_roots": (rust_refresh.get("refreshed_state") or {}).get("executable_support_roots_now"),
            "remaining_rust_builder_targets": (rust_refresh.get("refreshed_state") or {}).get("remaining_builder_targets"),
            "web_source_heldout_gap_still_open": (support_atlas.get("verdict") or {}).get("web_gap_is_currently_in_repo_source_exhaustion"),
            "excluded_support_roots_due_to_split_overlap": sorted({row_root_id(row) for row in excluded_support_rows}),
        },
        "split_violations": split_violations,
        "excluded_support_rows": excluded_support_rows,
        "required_honesty_gates": [
            "validation, strict, and stress rows remain byte-for-byte inherited from the reviewed v2.7 package",
            "all added support rows stay train-support only and do not change the promotable strict path directly",
            "repo-overlap web stress rows remain excluded from train, validation, and strict splits",
            "flash-attn remains support-only and abstention-heavy, not a headline Rust localization proof",
            "support rows whose roots collide with validation, strict, or stress are automatically excluded from train",
            "candle-core remains auxiliary Rust support and does not count as the fresh non-tokenizers residual fix claim",
        ],
        "next_best_step": "build the next standalone probe request from this refreshed support package, then require separate post-run canary and strict-slice audits before any headline claim changes",
        "outputs": {
            "train_rows": rel(TRAIN_JSONL),
            "validation_rows": rel(VALIDATION_JSONL),
            "strict_rows": rel(STRICT_JSONL),
            "stress_rows": rel(STRESS_JSONL),
        },
        "base_package_metrics_reference": {
            "base_package_stage": base_package.get("stage"),
            "base_package_name": base_package.get("stage_name"),
        },
    }

    write_jsonl(TRAIN_JSONL, refreshed_train)
    write_jsonl(VALIDATION_JSONL, base_validation)
    write_jsonl(STRICT_JSONL, base_strict)
    write_jsonl(STRESS_JSONL, base_stress)
    write_json(PACKAGE_JSON, payload)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": payload["passed"],
            "decision": payload["decision"],
            "package": rel(PACKAGE_JSON),
        },
    )
    print(PACKAGE_JSON)


if __name__ == "__main__":
    main()
