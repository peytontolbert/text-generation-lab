#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10484
NAME = "stage10484_partitioned_residual_support_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKAGE_JSON = OUT_DIR / "partitioned_residual_support_package.json"
PYTHON_ROWS_JSONL = OUT_DIR / "promotable_python_verifier_rows.jsonl"
RUST_ROWS_JSONL = OUT_DIR / "diagnostic_rust_citation_rows.jsonl"
HONESTY_JSONL = OUT_DIR / "honesty_metadata_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

FRESH_SUPPORT_ROWS = ROOT / "runs/local/artifacts/stage10468_fresh_residual_root_support_package/fresh_residual_root_support_rows.jsonl"
SUCCESSOR_MANIFEST = ROOT / "runs/local/artifacts/stage10410_ai_adjudicated_successor_salvage/real_session_successor_adjudicated_manifest.jsonl"
PYTHON_BUILDER = ROOT / "runs/local/artifacts/stage10466_python_verifier_fresh_root_builder/python_verifier_fresh_root_builder.json"
RUST_BUILDER = ROOT / "runs/local/artifacts/stage10467_rust_citation_fresh_root_builder/rust_citation_fresh_root_builder.json"
QUEUE_JSON = ROOT / "runs/local/artifacts/stage10444_repaired_v27_disjoint_residual_queue/repaired_v27_disjoint_residual_queue.json"

HONESTY_ROW_IDS = {
    "stage10110::localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_29t14_24_45_019d39fb_a380_7a30_8790_9d59_agent_kernel_improvement_py_agent_kernel_modeling_adapter_training_py_agent_kern_94b87c02df_aug_1500000_8b46e7f662::python_implementation_vs_implementation",
    "stage10110::localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_29t14_24_54_019d39fb_c43d_7e62_b055_b00b_agent_kernel_cycle_runner_py_agent_kernel_improvement_py_agent_kernel_learning_c_6a4dce0d0c_aug_1500000_8b46e7f662::python_implementation_vs_implementation",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def main() -> None:
    all_rows = load_jsonl(FRESH_SUPPORT_ROWS)
    successor_rows = [row for row in load_jsonl(SUCCESSOR_MANIFEST) if str(row.get("row_id") or "") in HONESTY_ROW_IDS]
    python_builder = load_json(PYTHON_BUILDER)
    rust_builder = load_json(RUST_BUILDER)
    queue = load_json(QUEUE_JSON)

    python_rows = [
        row for row in all_rows
        if str(row.get("language_family") or "") == "python"
        and str(row.get("task_type") or "") == "verifier_outcome"
        and str(((row.get("support_provenance") or {}).get("support_role") or "")) == "promotable_disjoint_support_candidate"
    ]
    rust_rows = [
        row for row in all_rows
        if str(row.get("language_family") or "") == "rust"
        and str(row.get("task_type") or "") == "evidence_citation"
        and str(((row.get("support_provenance") or {}).get("support_role") or "")) == "diagnostic_train_support_only"
    ]

    python_rows.sort(key=lambda row: str(row.get("row_id") or ""))
    rust_rows.sort(key=lambda row: str(row.get("row_id") or ""))
    successor_rows.sort(key=lambda row: str(row.get("row_id") or ""))

    write_jsonl(PYTHON_ROWS_JSONL, python_rows)
    write_jsonl(RUST_ROWS_JSONL, rust_rows)
    write_jsonl(HONESTY_JSONL, successor_rows)

    python_target = next(target for target in queue["targets"] if target["language_family"] == "python")
    rust_target = next(target for target in queue["targets"] if target["language_family"] == "rust")

    package = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(python_rows) and bool(rust_rows),
        "decision": "partitioned_residual_support_package_ready",
        "claim_scope": [
            "Partition the repaired-v2.7 residual support into promotable Python verifier rows, diagnostic Rust citation rows, and honesty-only metadata rows.",
            "Prevent the next residual run from accidentally treating diagnostic Rust support or successor honesty rows as promotable evidence.",
        ],
        "source_artifacts": {
            "fresh_support_rows": display(FRESH_SUPPORT_ROWS),
            "successor_manifest": display(SUCCESSOR_MANIFEST),
            "python_builder": display(PYTHON_BUILDER),
            "rust_builder": display(RUST_BUILDER),
            "residual_queue": display(QUEUE_JSON),
        },
        "lanes": {
            "promotable_python_verifier": {
                "rows": len(python_rows),
                "row_ids": [str(row.get("row_id") or "") for row in python_rows],
                "source_bundle_counts": count_by(python_rows, "source_bundle_id"),
                "task_counts": count_by(python_rows, "task_type"),
                "target_residual": python_target,
                "claim_boundary": [
                    "This lane is the only promotable train-support component in the package.",
                    "Rows must remain root-disjoint from the current MirrorMind strict root.",
                    "Any future promotion still requires fresh-root success, not just repaired-overlay movement.",
                ],
            },
            "diagnostic_rust_citation": {
                "rows": len(rust_rows),
                "row_ids": [str(row.get("row_id") or "") for row in rust_rows],
                "source_bundle_counts": count_by(rust_rows, "source_bundle_id"),
                "task_counts": count_by(rust_rows, "task_type"),
                "target_residual": rust_target,
                "claim_boundary": [
                    "This lane is diagnostic support only.",
                    "Rows cannot justify a fresh-root Rust promotion because the exact E-vs-F disjoint contrast is still missing.",
                    "Tokenizers same-surface rows must remain excluded from train.",
                ],
            },
            "honesty_metadata_only": {
                "rows": len(successor_rows),
                "row_ids": [str(row.get("row_id") or "") for row in successor_rows],
                "claim_boundary": [
                    "These rows are metadata only and are not executable bounded-choice trainer rows yet.",
                    "They exist to preserve abstention and anti-overclaim context, not to drive score movement directly.",
                ],
            },
        },
        "builder_contracts": {
            "python": python_builder["target_package_contract"],
            "rust": rust_builder["target_package_contract"],
        },
        "required_honesty_gates": [
            "Only the Python verifier lane may be used for a promotable residual-support run.",
            "Rust diagnostic rows must be declared non-promotable in any execution request.",
            "Successor honesty rows must remain outside executable train manifests until converted to bounded trainer rows.",
            "No current strict overlay row is copied into any train lane.",
        ],
        "outputs": {
            "package_json": display(PACKAGE_JSON),
            "promotable_python_rows": display(PYTHON_ROWS_JSONL),
            "diagnostic_rust_rows": display(RUST_ROWS_JSONL),
            "honesty_metadata_rows": display(HONESTY_JSONL),
        },
    }

    write_json(PACKAGE_JSON, package)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": package["passed"],
            "decision": package["decision"],
            "package": display(PACKAGE_JSON),
        },
    )
    print(json.dumps(package, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
