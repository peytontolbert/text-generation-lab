#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
HANDOFF = ARTIFACTS / "stage10657_repaired_headline_harness_handoff_bundle/repaired_headline_harness_handoff_bundle.json"
WRITEBACK_REPAIR = ARTIFACTS / "stage10660_repaired_headline_harness_writeback_repair/reviewed_v28_harness_writeback_repair.json"
RUNTIME_ROOT = ARTIFACTS / "stage10138_canonical_harness_local_runtime"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._") or "cell"


def accuracy(rows: list[dict[str, Any]], key: str = "correct") -> float:
    return (sum(1 for row in rows if bool(row.get(key))) / len(rows)) if rows else 0.0


def main() -> None:
    handoff = load_json(HANDOFF)
    writeback = load_json(WRITEBACK_REPAIR)
    handoff_cells = [row for row in (handoff.get("handoff_cells") or []) if isinstance(row, dict)]
    writeback_cells = {
        str(row.get("cell_key") or ""): row for row in (writeback.get("repaired_runs") or []) if isinstance(row, dict)
    }

    per_cell: list[dict[str, Any]] = []
    all_100m: list[dict[str, Any]] = []
    all_gemma: list[dict[str, Any]] = []
    language_counter: Counter[str] = Counter()
    for cell in handoff_cells:
        cell_key = str(cell.get("cell_key") or "")
        language_family = str(cell.get("language_family") or "")
        runtime_dir = RUNTIME_ROOT / slug(cell_key)
        hundred_m_rows = load_jsonl(runtime_dir / "hundred_m/predictions.jsonl")
        gemma_rows = load_jsonl(runtime_dir / "gemma/rows.jsonl")
        writeback_row = writeback_cells.get(cell_key, {})

        all_100m.extend(hundred_m_rows)
        all_gemma.extend(gemma_rows)
        language_counter[language_family] += 1

        per_cell.append(
            {
                "cell_key": cell_key,
                "language_family": language_family,
                "row_count": len(hundred_m_rows),
                "hundred_m_accuracy": accuracy(hundred_m_rows),
                "gemma_accuracy": accuracy(gemma_rows),
                "delta": accuracy(hundred_m_rows) - accuracy(gemma_rows),
                "runtime_dir": display(runtime_dir),
                "packet_dir": ((writeback_row.get("result") or {}).get("writes") or [{}])[0].get("packet_dir"),
                "writeback_completed": bool((writeback_row.get("result") or {}).get("written_runs")),
            }
        )

    per_language: dict[str, dict[str, Any]] = {}
    for language_family in sorted(language_counter):
        hundred_m_rows = [row for row in all_100m if f"::{language_family}::" in str(row.get("row_id") or "")]
        gemma_rows = [row for row in all_gemma if f"::{language_family}::" in str(row.get("row_id") or "")]
        per_language[language_family] = {
            "row_count": len(hundred_m_rows),
            "hundred_m_accuracy": accuracy(hundred_m_rows),
            "gemma_accuracy": accuracy(gemma_rows),
            "delta": accuracy(hundred_m_rows) - accuracy(gemma_rows),
        }

    payload = {
        "stage": 10659,
        "stage_name": "stage10659_repaired_headline_harness_result_audit",
        "passed": bool(writeback.get("passed")) and bool(per_cell),
        "metrics": {
            "cells": len(per_cell),
            "total_rows": len(all_100m),
            "hundred_m_accuracy": accuracy(all_100m),
            "gemma_accuracy": accuracy(all_gemma),
            "delta": accuracy(all_100m) - accuracy(all_gemma),
            "writeback_repaired_cells": sum(1 for row in per_cell if row.get("writeback_completed")),
        },
        "per_language": per_language,
        "per_cell": per_cell,
        "claim_boundary": [
            "This audit covers only the repaired same-manifest 24-row headline harness path.",
            "The four formerly shortcut-prone evidence_citation rows use opaque evidence IDs.",
            "This shows whether the recovered harness path preserves the cleaned headline advantage, not a source-heldout upgrade.",
        ],
        "writeback_repair_source": display(WRITEBACK_REPAIR),
        "handoff_source": display(HANDOFF),
    }

    out_dir = ARTIFACTS / "stage10659_repaired_headline_harness_result_audit"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "repaired_headline_harness_result_audit.json", payload)
    print(out_dir / "repaired_headline_harness_result_audit.json")


if __name__ == "__main__":
    main()
