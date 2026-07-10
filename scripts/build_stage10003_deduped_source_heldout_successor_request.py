#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10003
NAME = "stage10003_deduped_source_heldout_successor_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "edit_localization_manifest.jsonl"
REQUEST = OUT_DIR / "deduped_source_heldout_successor_request.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "DEDUPED_SOURCE_HELDOUT_SUCCESSOR_REQUEST_STAGE10003.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
BASE = ROOT / "runs/local/artifacts/stage9997_source_heldout_successor_request/edit_localization_manifest.jsonl"


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


def build_request() -> dict[str, Any]:
    rows = load_jsonl(BASE)
    kept: list[dict[str, Any]] = []
    seen_eval_ids: set[str] = set()
    removed: list[dict[str, Any]] = []
    for row in rows:
        split = str(row.get("split") or "")
        row_id = str(row.get("row_id") or "")
        if split in {"eval", "strict_eval"}:
            if row_id in seen_eval_ids:
                removed.append(row)
                continue
            seen_eval_ids.add(row_id)
        kept.append(row)
    write_jsonl(MANIFEST, kept)
    metrics = {
        "rows": len(kept),
        "split_counts": dict(sorted(Counter(str(row.get("split") or "") for row in kept).items())),
        "language_counts": dict(sorted(Counter(str(row.get("language_family") or "") for row in kept).items())),
        "removed_duplicate_eval_rows": len(removed),
    }
    failures: list[str] = []
    if metrics["removed_duplicate_eval_rows"] != 1:
        failures.append("expected_one_removed_duplicate_eval_row")
    return {"passed": not failures, "failures": failures, "metrics": metrics}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_request()
    REQUEST.write_text(json.dumps({"stage": STAGE, "name": NAME, "passed": built["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Use this deduplicated source-heldout manifest for future reruns so heldout row counts, unique row IDs, and comparison coverage all match without implicit collapsing."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": built["metrics"],
        "failures": built["failures"],
        "artifacts": {"request": display(REQUEST), "manifest": display(MANIFEST), "doc": display(DOC)},
        "decision": "Materialized a deduplicated source-heldout successor manifest that removes the single duplicate heldout row ID from stage9997.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage10003 Deduped Source-Heldout Successor Request",
        "",
        f"Passed: `{summary['passed']}`",
        f"Rows kept: `{built['metrics']['rows']}`",
        f"Removed duplicate eval rows: `{built['metrics']['removed_duplicate_eval_rows']}`",
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
