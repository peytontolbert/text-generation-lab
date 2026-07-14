#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10477
NAME = "stage10477_post_plateau_fresh_root_support_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKAGE_JSON = OUT_DIR / "post_plateau_fresh_root_support_package.json"
ROWS_JSONL = OUT_DIR / "post_plateau_fresh_root_support_rows.jsonl"
ROOTS_JSONL = OUT_DIR / "post_plateau_fresh_root_support_roots.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

PYTHON_JSON = ROOT / "runs/local/artifacts/stage10475_python_verifier_materialized_root_bundle_builder/python_verifier_materialized_root_bundle_builder.json"
PYTHON_ROWS = ROOT / "runs/local/artifacts/stage10475_python_verifier_materialized_root_bundle_builder/python_verifier_materialized_bounded_rows.jsonl"
PYTHON_ROOTS = ROOT / "runs/local/artifacts/stage10475_python_verifier_materialized_root_bundle_builder/python_verifier_materialized_root_manifest.jsonl"
RUST_JSON = ROOT / "runs/local/artifacts/stage10476_rust_citation_materialized_root_bundle_builder/rust_citation_materialized_root_bundle_builder.json"
RUST_ROWS = ROOT / "runs/local/artifacts/stage10476_rust_citation_materialized_root_bundle_builder/rust_citation_materialized_bounded_rows.jsonl"
RUST_ROOTS = ROOT / "runs/local/artifacts/stage10476_rust_citation_materialized_root_bundle_builder/rust_citation_materialized_root_manifest.jsonl"
EXECUTION_PATH = ROOT / "runs/local/artifacts/stage10474_post_plateau_fresh_root_execution_path_request/post_plateau_fresh_root_execution_path_request.json"


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


def main() -> None:
    python_summary = load_json(PYTHON_JSON)
    rust_summary = load_json(RUST_JSON)
    execution_path = load_json(EXECUTION_PATH)
    python_rows = load_jsonl(PYTHON_ROWS)
    rust_rows = load_jsonl(RUST_ROWS)
    python_roots = load_jsonl(PYTHON_ROOTS)
    rust_roots = load_jsonl(RUST_ROOTS)

    rows = python_rows + rust_rows
    roots = python_roots + rust_roots

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "post_plateau_support_package_materialized",
        "claim_scope": [
            "Combine the currently executable Python and Rust fresh-root support into one post-plateau train-side package.",
            "Keep promotable disjoint support, diagnostic support, and honesty-only support separated in metadata so the next probe can enforce the gate honestly.",
        ],
        "source_artifacts": {
            "execution_path": display(EXECUTION_PATH),
            "python_materialized_builder": display(PYTHON_JSON),
            "rust_materialized_builder": display(RUST_JSON),
        },
        "metrics": {
            "support_row_count": len(rows),
            "support_root_count": len(roots),
            "row_language_counts": dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in rows).items())),
            "row_task_type_counts": dict(sorted(Counter(str(row.get("task_type") or "unknown") for row in rows).items())),
            "root_support_role_counts": dict(sorted(Counter(str(row.get("support_role") or "unknown") for row in roots).items())),
        },
        "claim_boundaries": [
            "This package is train-side support only and cannot upgrade the strict headline by itself.",
            "Python has promotable disjoint executable support; Rust currently has auxiliary executable support plus pending reviewed/fresh roots outside this package.",
            "Any next probe must still satisfy the stage10461 promotion gate and the stage10474 execution-path constraints.",
        ],
        "recommended_next_stage": "stage10478_post_plateau_fresh_root_probe_request",
        "required_probe_gates": execution_path["promotion_gate"]["required_for_future_promotion"],
        "outputs": {
            "support_rows": display(ROWS_JSONL),
            "support_roots": display(ROOTS_JSONL),
        },
    }

    write_jsonl(ROWS_JSONL, rows)
    write_jsonl(ROOTS_JSONL, roots)
    write_json(PACKAGE_JSON, payload)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "request": display(PACKAGE_JSON),
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
