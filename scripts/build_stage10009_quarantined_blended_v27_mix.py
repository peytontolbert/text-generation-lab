#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10009
NAME = "stage10009_quarantined_blended_v27_mix"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
QUARANTINED = OUT_DIR / "quarantined_blended_structured_state.jsonl"
AUDIT = OUT_DIR / "quarantined_blended_v27_mix_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "QUARANTINED_BLENDED_V27_MIX_STAGE10009.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

SOURCE_BLEND = ROOT / "runs/local/artifacts/stage9945_web_targeted_blended_structured_mix/web_targeted_blended_structured_state.jsonl"
SOURCE_BLEND_SUMMARY = ROOT / "runs/summaries/stage9945_web_targeted_blended_structured_mix.json"
GEMMA_ADV_ROWS = ROOT / "runs/local/artifacts/stage9982_gemma_advantage_review_packet/gemma_advantage_review_rows.jsonl"
SIGNOFF_WORKBOOK = ROOT / "runs/summaries/stage9984_gemma_advantage_row_signoff_workbook.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
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


def normalize_review_row_id(row_id: str) -> str:
    return row_id.replace("stage9961_", "", 1) if row_id.startswith("stage9961_") else row_id


def unresolved_review_rows(rows: list[dict[str, Any]]) -> tuple[set[str], set[str]]:
    raw_ids = {str(row.get("row_id") or "") for row in rows if row.get("row_id")}
    normalized_ids = {normalize_review_row_id(row_id) for row_id in raw_ids}
    return raw_ids, normalized_ids


def count_rows(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "unknown") for row in rows).items()))


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": dict(AUTHORITY_CLOSED),
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


def build_quarantined_mix() -> dict[str, Any]:
    source_rows = read_jsonl(SOURCE_BLEND)
    review_rows = read_jsonl(GEMMA_ADV_ROWS)
    workbook = load_json(SIGNOFF_WORKBOOK)
    source_summary = load_json(SOURCE_BLEND_SUMMARY)
    failures: list[str] = []

    raw_review_ids, normalized_review_ids = unresolved_review_rows(review_rows)
    quarantined_rows: list[dict[str, Any]] = []
    removed_rows: list[dict[str, Any]] = []
    removed_ids: list[str] = []

    for row in source_rows:
        row_id = str(row.get("row_id") or "")
        if row_id in raw_review_ids or row_id in normalized_review_ids:
            removed_rows.append(row)
            removed_ids.append(row_id)
        else:
            quarantined_rows.append(row)

    write_jsonl(QUARANTINED, quarantined_rows)

    removed_language_counts = count_rows(removed_rows, "language_family")
    removed_split_counts = count_rows(removed_rows, "split")
    removed_skill_counts = count_rows(removed_rows, "source_skill_area")
    remaining_language_counts = count_rows(quarantined_rows, "language_family")
    remaining_split_counts = count_rows(quarantined_rows, "split")
    remaining_skill_counts = count_rows(quarantined_rows, "source_skill_area")
    remaining_loss_counts = count_rows(quarantined_rows, "expected_enabled_loss")

    metrics = {
        "source_blended_rows": len(source_rows),
        "review_packet_rows": len(review_rows),
        "review_signoff_tasks": int((workbook.get("metrics") or {}).get("signoff_tasks") or 0),
        "review_rows_raw_ids": len(raw_review_ids),
        "review_rows_normalized_ids": len(normalized_review_ids),
        "rows_removed_from_active_blend": len(removed_rows),
        "rows_remaining_after_quarantine": len(quarantined_rows),
        "removed_row_ids": removed_ids,
        "removed_language_counts": removed_language_counts,
        "removed_split_counts": removed_split_counts,
        "removed_skill_counts": removed_skill_counts,
        "remaining_language_counts": remaining_language_counts,
        "remaining_split_counts": remaining_split_counts,
        "remaining_skill_counts": remaining_skill_counts,
        "remaining_loss_counts": remaining_loss_counts,
        "source_blended_overall_beats_gemma": bool((source_summary.get("metrics") or {}).get("blended_overall_beats_gemma")),
    }

    if metrics["source_blended_rows"] != 404:
        failures.append("source_blended_rows_not_404")
    if metrics["review_packet_rows"] != 11:
        failures.append("review_packet_rows_not_11")
    if metrics["review_signoff_tasks"] != 22:
        failures.append("review_signoff_tasks_not_22")
    if metrics["rows_removed_from_active_blend"] != 8:
        failures.append("rows_removed_from_active_blend_not_8")
    if metrics["rows_remaining_after_quarantine"] != 396:
        failures.append("rows_remaining_after_quarantine_not_396")
    if metrics["removed_language_counts"] != {"c_cpp": 3, "python": 5}:
        failures.append("removed_language_counts_unexpected")
    if metrics["removed_split_counts"] != {"eval": 3, "strict_eval": 5}:
        failures.append("removed_split_counts_unexpected")
    if metrics["removed_skill_counts"] != {"edit_localization": 8}:
        failures.append("removed_skill_counts_unexpected")

    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "quarantine_policy": {
            "rule": "remove unresolved Gemma-advantage rows from the active blended v2.7 mix until row-level human signoff decides keep, abstain-relabel, or quarantine permanently",
            "source_blend": display(SOURCE_BLEND),
            "review_packet": display(GEMMA_ADV_ROWS),
            "signoff_workbook": display(SIGNOFF_WORKBOOK),
            "quarantined_successor": display(QUARANTINED),
        },
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_quarantined_mix()
    AUDIT.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Use this quarantined 396-row successor as the default blended v2.7 training/eval mix until the 22 open Gemma-advantage signoff tasks resolve whether each removed row should be kept, abstention-relabeled, or permanently excluded."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {
            "quarantined_blend": display(QUARANTINED),
            "audit": display(AUDIT),
            "doc": display(DOC),
        },
        "decision": "Built a quarantined successor to the active blended v2.7 structured mix so unresolved Gemma-advantage edit-localization eval rows stop influencing training or multilingual reporting until human review closes them.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage10009 Quarantined Blended V2.7 Mix",
                "",
                f"Passed: `{summary['passed']}`",
                f"Source blended rows: `{built['metrics']['source_blended_rows']}`",
                f"Rows removed from active blend: `{built['metrics']['rows_removed_from_active_blend']}`",
                f"Rows remaining after quarantine: `{built['metrics']['rows_remaining_after_quarantine']}`",
                f"Removed language counts: `{built['metrics']['removed_language_counts']}`",
                f"Removed split counts: `{built['metrics']['removed_split_counts']}`",
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
