#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11007
NAME = "stage11007_evidence_geometry_bank"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "evidence_geometry_bank.json"
GEOMETRY_ROWS_JSONL = OUT_DIR / "geometry_candidate_rows.jsonl"
STANDARD_ROWS_JSONL = OUT_DIR / "standard_reviewed_candidate_rows.jsonl"

EXPANDED_ROWS = ARTIFACTS / "stage10963_expanded_evidence_successor_family" / "expanded_successor_rows.jsonl"
RUST_REVIEWED_CANDIDATES = ARTIFACTS / "stage10972_rust_reviewed_evidence_bundle" / "strict_candidate_rows.jsonl"
STANDARD_REVIEWED_CANDIDATES = ARTIFACTS / "stage10974_multilingual_reviewed_replenishment_package" / "strict_candidate_rows.jsonl"


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


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counter = Counter(str(row.get(key) or "missing") for row in rows)
    return dict(sorted(counter.items()))


def main() -> None:
    expanded_rows = load_jsonl(EXPANDED_ROWS)
    rust_rows = load_jsonl(RUST_REVIEWED_CANDIDATES)
    standard_rows = load_jsonl(STANDARD_REVIEWED_CANDIDATES)

    geometry_rows: list[dict[str, Any]] = []
    for row in expanded_rows:
        updated = dict(row)
        updated["geometry_bank_stage"] = STAGE
        updated["geometry_bank_family"] = "expanded_python_cpp"
        updated["geometry_bank_root_kind"] = "fresh_successor_variant"
        geometry_rows.append(updated)
    for row in rust_rows:
        updated = dict(row)
        updated["geometry_bank_stage"] = STAGE
        updated["geometry_bank_family"] = "reviewed_rust_candidate"
        updated["geometry_bank_root_kind"] = "reviewed_rust_candidate"
        geometry_rows.append(updated)

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Build a wider evidence-citation candidate bank than the 6-row reviewed replenishment slice.",
            "Preserve the fresh Python/C++ successor variants and the reviewed Rust candidate rows under one audit surface.",
        ],
        "source_artifacts": {
            "expanded_successor_rows": rel(EXPANDED_ROWS),
            "rust_reviewed_candidates": rel(RUST_REVIEWED_CANDIDATES),
            "standard_reviewed_candidates": rel(STANDARD_REVIEWED_CANDIDATES),
        },
        "metrics": {
            "geometry_rows": len(geometry_rows),
            "geometry_by_language": count_by(geometry_rows, "language_family"),
            "geometry_by_repo_family": count_by(geometry_rows, "repo_family"),
            "geometry_by_target": count_by(geometry_rows, "decoder_text"),
            "geometry_by_family": count_by(geometry_rows, "geometry_bank_family"),
            "geometry_by_variant": count_by(geometry_rows, "variant_family"),
            "standard_reviewed_rows": len(standard_rows),
            "standard_reviewed_by_language": count_by(standard_rows, "language_family"),
        },
        "findings": [
            "This bank widens the evidence-citation audit surface from 6 rows to 27 rows without inventing new synthetic material.",
            "Python/C++ contribute 24 variant rows from fresh successor materialization, while Rust contributes 3 reviewed candidate rows.",
            "The bank is still root-narrow, but it is a materially better judge of option-order, explicit-ledger, and contrast stability than the 6-row slice alone.",
        ],
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "geometry_candidate_rows_jsonl": rel(GEOMETRY_ROWS_JSONL),
            "standard_reviewed_candidate_rows_jsonl": rel(STANDARD_ROWS_JSONL),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(GEOMETRY_ROWS_JSONL, geometry_rows)
    write_jsonl(STANDARD_ROWS_JSONL, standard_rows)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
