#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9997
NAME = "stage9997_source_heldout_successor_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "edit_localization_manifest.jsonl"
REQUEST = OUT_DIR / "source_heldout_successor_request.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SOURCE_HELDOUT_SUCCESSOR_REQUEST_STAGE9997.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
BASE = ROOT / "runs/local/artifacts/stage9986_filtered_positive_replay_successor_request/edit_localization_manifest.jsonl"


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
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "next_best_step": summary["next_best_step"],
        }
    )
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
    base_rows = load_jsonl(BASE)
    train_sources = {str(row.get("source_row_id") or "") for row in base_rows if row.get("split") == "train"}
    kept_rows: list[dict[str, Any]] = []
    removed_eval_rows: list[dict[str, Any]] = []
    for row in base_rows:
        split = str(row.get("split") or "")
        source_row_id = str(row.get("source_row_id") or "")
        if split in {"eval", "strict_eval"} and source_row_id in train_sources:
            removed_eval_rows.append(row)
            continue
        kept_rows.append(row)
    write_jsonl(MANIFEST, kept_rows)
    metrics = {
        "rows": len(kept_rows),
        "split_counts": dict(sorted(Counter(str(row.get("split") or "") for row in kept_rows).items())),
        "language_counts": dict(sorted(Counter(str(row.get("language_family") or "") for row in kept_rows).items())),
        "removed_eval_rows": len(removed_eval_rows),
        "removed_eval_by_language": dict(sorted(Counter(str(row.get("language_family") or "") for row in removed_eval_rows).items())),
        "removed_eval_by_role": dict(sorted(Counter(str(row.get("counterfactual_role") or "") for row in removed_eval_rows).items())),
    }
    failures: list[str] = []
    if metrics["removed_eval_rows"] <= 0:
        failures.append("expected_removed_eval_rows")
    return {"passed": not failures, "failures": failures, "metrics": metrics}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_request()
    REQUEST.write_text(json.dumps({"stage": STAGE, "name": NAME, "passed": built["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Use this successor manifest for the next honest 100M and Gemma reruns, then replenish Python and c_cpp heldout eval roots with fresh independent sources instead of replay copies."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": built["metrics"],
        "failures": built["failures"],
        "artifacts": {"request": display(REQUEST), "manifest": display(MANIFEST), "doc": display(DOC)},
        "decision": "Materialized a source-heldout successor manifest that removes eval rows whose source roots already appear in train.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9997 Source-Heldout Successor Request",
                "",
                f"Passed: `{summary['passed']}`",
                f"Rows kept: `{built['metrics']['rows']}`",
                f"Eval rows removed: `{built['metrics']['removed_eval_rows']}`",
                "",
                summary["decision"],
                "",
                f"Next: {next_step}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
