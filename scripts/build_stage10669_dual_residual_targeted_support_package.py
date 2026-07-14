#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10669
NAME = "stage10669_dual_residual_targeted_support_package"
OUT_DIR = ARTIFACTS / NAME
PACKAGE_JSON = OUT_DIR / "dual_residual_targeted_support_package.json"
TRAIN_JSONL = OUT_DIR / "train_rows.jsonl"
VALIDATION_JSONL = OUT_DIR / "validation_rows.jsonl"
STRICT_JSONL = OUT_DIR / "strict_rows.jsonl"
STRESS_JSONL = OUT_DIR / "stress_rows.jsonl"

BASE_TRAIN = ARTIFACTS / "stage10420_reviewed_multilingual_v27_manifest_package/agentkernel_lite_encdec_train.jsonl"
BASE_VALIDATION = ARTIFACTS / "stage10420_reviewed_multilingual_v27_manifest_package/agentkernel_lite_encdec_validation.jsonl"
BASE_STRICT = ARTIFACTS / "stage10420_reviewed_multilingual_v27_manifest_package/agentkernel_lite_encdec_strict_eval.jsonl"
BASE_STRESS = ARTIFACTS / "stage10420_reviewed_multilingual_v27_manifest_package/agentkernel_lite_encdec_stress_eval.jsonl"

PYTHON_ROWS = ARTIFACTS / "stage10475_python_verifier_materialized_root_bundle_builder/python_verifier_materialized_bounded_rows.jsonl"
PYTHON_ROOTS = ARTIFACTS / "stage10475_python_verifier_materialized_root_bundle_builder/python_verifier_materialized_root_manifest.jsonl"
RUST_ROWS = ARTIFACTS / "stage10663_rust_flash_attn_executable_support_audit/rust_flash_attn_executable_support_rows.jsonl"
RUST_AUDIT = ARTIFACTS / "stage10663_rust_flash_attn_executable_support_audit/rust_flash_attn_executable_support_audit.json"


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


def annotate(rows: list[dict[str, Any]], source_kind: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        updated = json.loads(json.dumps(row))
        updated["package_source_kind"] = source_kind
        updated["support_package_stage"] = STAGE
        out.append(updated)
    return out


def main() -> None:
    base_train = annotate(load_jsonl(BASE_TRAIN), "reviewed_base_train")
    base_validation = annotate(load_jsonl(BASE_VALIDATION), "reviewed_base_validation")
    base_strict = annotate(load_jsonl(BASE_STRICT), "reviewed_base_strict")
    base_stress = annotate(load_jsonl(BASE_STRESS), "reviewed_base_stress")

    python_root_manifest = load_jsonl(PYTHON_ROOTS)
    promotable_python_roots = {
        str(row.get("root_id") or "")
        for row in python_root_manifest
        if str(row.get("support_role") or "") == "promotable_disjoint_support_candidate"
    }

    python_rows_all = annotate(load_jsonl(PYTHON_ROWS), "targeted_python_verifier_support")
    python_rows = [row for row in python_rows_all if row_root_id(row) in promotable_python_roots]
    rust_rows = annotate(load_jsonl(RUST_ROWS), "targeted_rust_flash_support")
    rust_audit = load_json(RUST_AUDIT)

    reserved_roots = {row_root_id(row) for row in [*base_validation, *base_strict, *base_stress]}
    support_rows: list[dict[str, Any]] = []
    excluded_rows: list[dict[str, Any]] = []
    for row in [*python_rows, *rust_rows]:
        if row_root_id(row) in reserved_roots:
            excluded = dict(row)
            excluded["exclusion_reason"] = "root_overlaps_validation_or_strict_or_stress"
            excluded_rows.append(excluded)
            continue
        support_rows.append(row)

    train_rows = [*base_train, *support_rows]

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "dual_residual_targeted_support_package_ready",
        "claim_scope": [
            "Build a narrower fresh-root training package aimed directly at the two remaining reviewed v2.7 miss families.",
            "Keep the reviewed validation and strict paths unchanged while swapping broad support for targeted executable Python verifier and Rust flash-attn support.",
        ],
        "sources": {
            "base_train": rel(BASE_TRAIN),
            "base_validation": rel(BASE_VALIDATION),
            "base_strict": rel(BASE_STRICT),
            "python_materialized_rows": rel(PYTHON_ROWS),
            "python_materialized_roots": rel(PYTHON_ROOTS),
            "rust_flash_rows": rel(RUST_ROWS),
            "rust_flash_audit": rel(RUST_AUDIT),
        },
        "metrics": {
            "base_train_rows": len(base_train),
            "targeted_support_rows": len(support_rows),
            "excluded_support_rows": len(excluded_rows),
            "final_train_rows": len(train_rows),
            "validation_rows": len(base_validation),
            "strict_rows": len(base_strict),
            "stress_rows": len(base_stress),
            "train_language_counts": dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in train_rows).items())),
            "train_source_kind_counts": dict(sorted(Counter(str(row.get("package_source_kind") or "unknown") for row in train_rows).items())),
        },
        "targeted_roots": {
            "python_promotable_roots": sorted(promotable_python_roots),
            "rust_support_root": sorted({row_root_id(row) for row in rust_rows}),
            "rust_support_claim_boundary": rust_audit.get("claim_boundary"),
        },
        "required_honesty_gates": [
            "validation and strict rows remain unchanged from the reviewed v2.7 package",
            "only promotable_disjoint_support_candidate Python roots are admitted from the Python materialized inventory",
            "flash-attn remains train-support only and cannot by itself justify a stronger Rust headline claim",
            "overlapping support roots are excluded automatically",
        ],
        "next_best_step": "run a targeted standalone probe from this package and check whether the Python verifier miss flips without regressing the Rust/web/c_cpp strict slices",
        "outputs": {
            "train_rows": rel(TRAIN_JSONL),
            "validation_rows": rel(VALIDATION_JSONL),
            "strict_rows": rel(STRICT_JSONL),
            "stress_rows": rel(STRESS_JSONL),
        },
        "excluded_support_rows": excluded_rows,
    }

    write_jsonl(TRAIN_JSONL, train_rows)
    write_jsonl(VALIDATION_JSONL, base_validation)
    write_jsonl(STRICT_JSONL, base_strict)
    write_jsonl(STRESS_JSONL, base_stress)
    write_json(PACKAGE_JSON, payload)
    print(PACKAGE_JSON)


if __name__ == "__main__":
    main()
