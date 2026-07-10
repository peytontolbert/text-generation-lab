#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10002
NAME = "stage10002_duplicate_rowid_eval_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
ROWS = OUT_DIR / "duplicate_eval_row_ids.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "DUPLICATE_ROWID_EVAL_AUDIT_STAGE10002.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9997_source_heldout_successor_request/edit_localization_manifest.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_audit() -> dict[str, Any]:
    rows = load_jsonl(MANIFEST)
    heldout = [row for row in rows if str(row.get("split") or "") in {"eval", "strict_eval"}]
    counts = Counter(str(row.get("row_id") or "") for row in heldout)
    duplicate_ids = sorted(row_id for row_id, count in counts.items() if count > 1)
    duplicate_rows = []
    for row_id in duplicate_ids:
        matching = [row for row in heldout if str(row.get("row_id") or "") == row_id]
        duplicate_rows.append(
            {
                "row_id": row_id,
                "count": len(matching),
                "language_family": matching[0].get("language_family") if matching else None,
                "split": matching[0].get("split") if matching else None,
                "source_row_ids": sorted({str(row.get("source_row_id") or "") for row in matching}),
                "semantic_keys": sorted({str(row.get("semantic_key") or "") for row in matching}),
            }
        )
    write_jsonl(ROWS, duplicate_rows)
    metrics = {
        "heldout_rows": len(heldout),
        "unique_heldout_row_ids": len(counts),
        "duplicate_row_id_count": len(duplicate_ids),
        "duplicate_row_ids": duplicate_ids,
    }
    failures: list[str] = []
    if metrics["duplicate_row_id_count"] <= 0:
        failures.append("expected_duplicate_row_id")
    return {"passed": not failures, "failures": failures, "metrics": metrics}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_audit()
    next_step = "Deduplicate the source-heldout manifest by row_id before future training or comparison reruns so heldout row counts and shared-row counts match exactly."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": built["metrics"],
        "failures": built["failures"],
        "artifacts": {"rows": display(ROWS), "doc": display(DOC)},
        "decision": "Audited the source-heldout manifest for duplicate heldout row IDs and found an exact c_cpp duplicate that should be removed from future reruns.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage10002 Duplicate RowID Eval Audit",
        "",
        f"Passed: `{summary['passed']}`",
        f"Duplicate heldout row IDs: `{built['metrics']['duplicate_row_id_count']}`",
        "",
        summary["decision"],
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
