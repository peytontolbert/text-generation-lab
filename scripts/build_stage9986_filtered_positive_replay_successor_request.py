#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9986
NAME = "stage9986_filtered_positive_replay_successor_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST = OUT_DIR / "filtered_positive_replay_successor_request.json"
MANIFEST = OUT_DIR / "edit_localization_manifest.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "FILTERED_POSITIVE_REPLAY_SUCCESSOR_REQUEST_STAGE9986.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
BASE = ROOT / "runs/local/artifacts/stage9979_selective_gemma_advantage_successor_request/edit_localization_manifest.jsonl"
QUARANTINE = ROOT / "runs/local/artifacts/stage9985_mixed_replay_quarantine_recommendation/mixed_replay_quarantine_rows.jsonl"


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
    base_rows = load_jsonl(BASE)
    quarantine_ids = {str(row.get("row_id") or "") for row in load_jsonl(QUARANTINE)}
    filtered = [row for row in base_rows if str(row.get("row_id") or "") not in quarantine_ids]
    write_jsonl(MANIFEST, filtered)
    language_counts = Counter(str(row.get("language_family") or "") for row in filtered)
    split_counts = Counter(str(row.get("split") or "") for row in filtered)
    recovery_counts = Counter(str(row.get("recovery_reason") or "anchor") for row in filtered)
    failures: list[str] = []
    metrics = {
        "rows": len(filtered),
        "language_counts": dict(sorted(language_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "recovery_reason_counts": dict(sorted(recovery_counts.items())),
    }
    if metrics["rows"] != 117:
        failures.append("rows_not_117")
    if language_counts.get("python") != 22:
        failures.append("python_rows_not_22")
    if language_counts.get("c_cpp") != 29:
        failures.append("c_cpp_rows_not_29")
    if language_counts.get("rust") != 21:
        failures.append("rust_rows_not_21")
    if language_counts.get("web_js_ts_html") != 45:
        failures.append("web_rows_not_45")
    if recovery_counts.get("gemma_advantage_only") != 4:
        failures.append("gemma_advantage_only_rows_not_4")
    return {"passed": not failures, "failures": failures, "metrics": metrics, "manifest": display(MANIFEST)}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_request()
    REQUEST.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Run the next direct 100M edit-localization probe on this 124-row filtered manifest to test whether removing mixed-replay quarantine rows recovers python and c_cpp without hurting rust or web."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {"request": display(REQUEST), "manifest": display(MANIFEST), "doc": display(DOC)},
        "decision": "Materialized a filtered multilingual successor request that removes only the seven mixed-replay quarantine rows while keeping the four positive replay Gemma-advantage rows available for evaluation.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9986 Filtered Positive Replay Successor Request",
        "",
        f"Passed: `{summary['passed']}`",
        f"Rows: `{built['metrics']['rows']}`",
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
