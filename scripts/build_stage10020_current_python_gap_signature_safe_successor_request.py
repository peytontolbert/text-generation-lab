#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10020
NAME = "stage10020_current_python_gap_signature_safe_successor_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST = OUT_DIR / "current_python_gap_signature_safe_successor_request.json"
MANIFEST = OUT_DIR / "edit_localization_manifest.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CURRENT_PYTHON_GAP_SIGNATURE_SAFE_SUCCESSOR_REQUEST_STAGE10020.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
BASE = ROOT / "runs/local/artifacts/stage10012_quarantined_blended_weak_language_execution_review/review_manifests/edit_localization.jsonl"
COMPARISON = ROOT / "runs/local/artifacts/stage10017_quarantined_same_manifest_comparison_audit/quarantined_same_manifest_comparison_rows.jsonl"


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


def row_label(row: dict[str, Any]) -> str:
    clean_state = row.get("clean_state") if isinstance(row.get("clean_state"), dict) else {}
    return str(clean_state.get("edit_localization") or "")


def replay_reason(row: dict[str, Any]) -> str:
    if (not bool(row.get("hundred_m_correct"))) and bool(row.get("gemma_correct")):
        return "python_gemma_advantage_current"
    return "python_both_wrong_current"


def build_request() -> dict[str, Any]:
    base_rows = load_jsonl(BASE)
    comparison_rows = load_jsonl(COMPARISON)
    python_losses = [
        row
        for row in comparison_rows
        if str(row.get("language_family") or "") == "python" and not bool(row.get("hundred_m_correct"))
    ]
    canonical_python_train_by_label: dict[str, dict[str, Any]] = {}
    for row in base_rows:
        if str(row.get("language_family") or "") != "python":
            continue
        if str(row.get("split") or "") != "train":
            continue
        label = row_label(row)
        if label and label not in canonical_python_train_by_label:
            canonical_python_train_by_label[label] = row

    replay_rows: list[dict[str, Any]] = []
    failures: list[str] = []
    for loss in python_losses:
        label = str(loss.get("expected_label") or "")
        canonical = canonical_python_train_by_label.get(label)
        if not isinstance(canonical, dict):
            failures.append(f"missing_canonical_python_train_label:{label}:{loss.get('row_id')}")
            continue
        cloned = deepcopy(canonical)
        cloned["row_id"] = f"{loss.get('row_id')}::train_gap_replay_signature_safe_python"
        cloned["split"] = "train"
        cloned["gap_replay_reason"] = replay_reason(loss)
        cloned["gap_replay_source_row_id"] = str(loss.get("row_id") or "")
        cloned["gap_replay_source_expected_label"] = label
        cloned["gap_replay_source_hundred_m_pred"] = str(loss.get("hundred_m_pred") or "")
        cloned["gap_replay_source_gemma_pred"] = str(loss.get("gemma_pred") or "")
        cloned["gap_replay_signature_strategy"] = "canonical_train_label_duplicate"
        replay_rows.append(cloned)

    rows = [*base_rows, *replay_rows]
    write_jsonl(MANIFEST, rows)

    language_counts = Counter(str(row.get("language_family") or "") for row in rows)
    split_counts = Counter(str(row.get("split") or "") for row in rows)
    gap_reason_counts = Counter(
        str(row.get("gap_replay_reason") or "") for row in rows if row.get("gap_replay_reason")
    )
    python_train_rows = [
        row for row in rows if str(row.get("language_family") or "") == "python" and str(row.get("split") or "") == "train"
    ]
    python_train_labels = sorted({row_label(row) for row in python_train_rows if row_label(row)})
    python_train_signatures = {
        json.dumps(row.get("input_state") if isinstance(row.get("input_state"), dict) else {}, sort_keys=True)
        for row in python_train_rows
    }
    metrics = {
        "rows": len(rows),
        "language_counts": dict(sorted(language_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "gap_replay_rows": len(replay_rows),
        "gap_replay_reason_counts": dict(sorted(gap_reason_counts.items())),
        "python_losses_current": len(python_losses),
        "python_train_rows": len(python_train_rows),
        "python_train_label_count": len(python_train_labels),
        "python_train_signature_count": len(python_train_signatures),
        "python_train_labels": python_train_labels,
    }
    if metrics["rows"] != 119:
        failures.append("rows_not_119")
    if split_counts.get("train") != 47:
        failures.append("train_rows_not_47")
    if language_counts.get("python") != 26:
        failures.append("python_rows_not_26")
    if metrics["gap_replay_rows"] != 7:
        failures.append("gap_replay_rows_not_7")
    if metrics["gap_replay_reason_counts"].get("python_gemma_advantage_current") != 1:
        failures.append("python_gemma_advantage_current_rows_not_1")
    if metrics["gap_replay_reason_counts"].get("python_both_wrong_current") != 6:
        failures.append("python_both_wrong_current_rows_not_6")
    if metrics["python_train_label_count"] != 5:
        failures.append("python_train_label_count_not_5")
    if metrics["python_train_signature_count"] != 5:
        failures.append("python_train_signature_count_not_5")
    return {"passed": not failures, "failures": failures, "metrics": metrics, "manifest": display(MANIFEST)}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_request()
    REQUEST.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Run the next direct 100M probe on this 119-row manifest; it preserves the current Python loss replay count "
        "while keeping the Python train bucket signature-safe under the multilingual readiness gate."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {"request": display(REQUEST), "manifest": display(MANIFEST), "doc": display(DOC)},
        "decision": "Materialized a signature-safe Python-gap successor manifest by replaying the current Python loss set as canonical train-label duplicates rather than introducing new evidence signatures that break multilingual readiness.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage10020 Current Python Gap Signature-Safe Successor Request",
                "",
                f"Passed: `{summary['passed']}`",
                f"Rows: `{built['metrics']['rows']}`",
                f"Python train signatures: `{built['metrics']['python_train_signature_count']}`",
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
    print(
        json.dumps(
            {
                "stage": STAGE,
                "passed": summary["passed"],
                "metrics": built["metrics"],
                "failures": built["failures"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
