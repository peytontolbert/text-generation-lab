#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9978
NAME = "stage9978_selective_gemma_advantage_recovery_packet"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKET = OUT_DIR / "selective_gemma_advantage_recovery_packet.json"
ROWS = OUT_DIR / "selective_gemma_advantage_recovery_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SELECTIVE_GEMMA_ADVANTAGE_RECOVERY_PACKET_STAGE9978.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

COMPARE = ROOT / "runs/local/artifacts/stage9973_blended_weak_language_same_manifest_comparison_audit/blended_weak_language_same_manifest_comparison_rows.jsonl"
MANIFEST = ROOT / "runs/local/artifacts/stage9964_blended_weak_language_execution_review/review_manifests/edit_localization.jsonl"
TARGET_LANGS = {"python", "c_cpp"}


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


def build_packet() -> dict[str, Any]:
    compare_rows = load_jsonl(COMPARE)
    manifest_rows = {str(row.get("row_id") or ""): row for row in load_jsonl(MANIFEST)}
    selected = [
        row for row in compare_rows
        if str(row.get("language_family") or "") in TARGET_LANGS
        and (not bool(row.get("hundred_m_correct")))
        and bool(row.get("gemma_correct"))
    ]
    failures: list[str] = []
    packet_rows: list[dict[str, Any]] = []
    for row in selected:
        row_id = str(row.get("row_id") or "")
        source = manifest_rows.get(row_id)
        if not isinstance(source, dict):
            failures.append(f"missing_manifest_row:{row_id}")
            continue
        enriched = dict(source)
        enriched["recovery_reason"] = "gemma_advantage_only"
        enriched["recovery_language_family"] = row.get("language_family")
        enriched["recovery_split"] = row.get("split")
        enriched["recovery_expected_label"] = row.get("expected_label")
        enriched["recovery_hundred_m_pred"] = row.get("hundred_m_pred")
        enriched["recovery_gemma_pred"] = row.get("gemma_pred")
        packet_rows.append(enriched)
    language_counts = Counter(str(row.get("recovery_language_family") or "") for row in packet_rows)
    split_counts = Counter(str(row.get("recovery_split") or "") for row in packet_rows)
    metrics = {
        "rows": len(packet_rows),
        "language_counts": dict(sorted(language_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
    }
    if metrics["rows"] != 11:
        failures.append("rows_not_11")
    if language_counts.get("python") != 6:
        failures.append("python_rows_not_6")
    if language_counts.get("c_cpp") != 5:
        failures.append("c_cpp_rows_not_5")
    return {"passed": not failures, "failures": failures, "metrics": metrics, "rows": packet_rows}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_packet()
    PACKET.write_text(json.dumps({"stage": STAGE, "name": NAME, "passed": built["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_jsonl(ROWS, built["rows"])
    next_step = "Blend this selective 11-row Gemma-advantage packet into the next edit-localization cycle instead of replaying the broader both-wrong loss bank."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {"packet": display(PACKET), "rows": display(ROWS), "doc": display(DOC)},
        "decision": "Materialized a selective recovery packet containing only python and c_cpp rows where Gemma was correct and the 100M was wrong on the real stage9973 comparison.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9978 Selective Gemma Advantage Recovery Packet",
        "",
        f"Passed: `{summary['passed']}`",
        f"Rows: `{built['metrics']['rows']}`",
        f"Language counts: `{built['metrics']['language_counts']}`",
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
