#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9982
NAME = "stage9982_gemma_advantage_review_packet"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKET = OUT_DIR / "gemma_advantage_review_packet.json"
ROWS = OUT_DIR / "gemma_advantage_review_rows.jsonl"
DOC = ROOT / "docs" / "GEMMA_ADVANTAGE_REVIEW_PACKET_STAGE9982.md"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

MANIFEST = ROOT / "runs/local/artifacts/stage9979_selective_gemma_advantage_successor_request/edit_localization_manifest.jsonl"
LOGITS = ROOT / "runs/local/artifacts/stage9980_selective_gemma_advantage_target100m_probe/edit_localization_probe/row_field_logits.jsonl"


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


def build_packet() -> dict[str, Any]:
    manifest_rows = {
        str(row.get("row_id")): row
        for row in load_jsonl(MANIFEST)
        if str(row.get("recovery_reason") or "") == "gemma_advantage_only"
    }
    logits_by_id = {str(row.get("row_id")): row for row in load_jsonl(LOGITS)}
    review_rows: list[dict[str, Any]] = []
    failures: list[str] = []
    for row_id, row in sorted(manifest_rows.items()):
        logits = logits_by_id.get(row_id)
        if not isinstance(logits, dict):
            failures.append(f"missing_logits:{row_id}")
            continue
        top_k = logits.get("top_k") if isinstance(logits.get("top_k"), list) else []
        review_rows.append(
            {
                "row_id": row_id,
                "language_family": row.get("language_family"),
                "split": row.get("split"),
                "recovery_reason": row.get("recovery_reason"),
                "source_stage": row.get("source_stage"),
                "surface": row.get("surface"),
                "task_observation": ((row.get("input_state") or {}).get("task_observation")),
                "visible_locality_evidence": ((row.get("input_state") or {}).get("visible_locality_evidence")),
                "candidate_choices": ((row.get("input_state") or {}).get("candidate_choices")),
                "target": logits.get("target"),
                "pred": logits.get("pred"),
                "correct": bool(logits.get("correct")),
                "confidence": float(logits.get("confidence") or 0.0),
                "margin": float(logits.get("margin") or 0.0),
                "top_k": top_k,
                "review_recommendation": "expert_identifiability_and_anti_cheat_review_required",
            }
        )
    language_counts = Counter(str(row.get("language_family") or "") for row in review_rows)
    split_counts = Counter(str(row.get("split") or "") for row in review_rows)
    incorrect_rows = sum(1 for row in review_rows if not bool(row.get("correct")))
    metrics = {
        "rows": len(review_rows),
        "language_counts": dict(sorted(language_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "incorrect_rows": incorrect_rows,
    }
    if metrics["rows"] != 11:
        failures.append("rows_not_11")
    if language_counts.get("python") != 6:
        failures.append("python_rows_not_6")
    if language_counts.get("c_cpp") != 5:
        failures.append("c_cpp_rows_not_5")
    if incorrect_rows != len(review_rows):
        failures.append("expected_all_rows_incorrect")
    return {"passed": not failures, "failures": failures, "metrics": metrics, "rows": review_rows}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    packet = build_packet()
    PACKET.write_text(
        json.dumps(
            {
                "stage": STAGE,
                "name": NAME,
                "passed": packet["passed"],
                "metrics": packet["metrics"],
                "failures": packet["failures"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    write_jsonl(ROWS, packet["rows"])
    next_step = (
        "Review these 11 rows as expert-maintainer and anti-cheat candidates before reusing them for training; "
        "they stayed 0/11 correct after selective replay, so they are currently better treated as evaluation-risk rows "
        "than as ordinary positive recovery examples."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": packet["passed"],
        "metrics": {**packet["metrics"], "failures": packet["failures"]},
        "artifacts": {"packet": display(PACKET), "rows": display(ROWS), "doc": display(DOC)},
        "decision": (
            "Materialized a focused expert-review packet for the 11 python and c_cpp Gemma-advantage rows that stayed wrong "
            "after the stage9980 selective replay run."
        ),
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9982 Gemma Advantage Review Packet",
                "",
                f"Passed: `{summary['passed']}`",
                f"Rows: `{packet['metrics']['rows']}`",
                f"Decision: {summary['decision']}",
                "",
                f"Next: {next_step}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "failures": packet["failures"]}, indent=2, sort_keys=True))
    if packet["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
