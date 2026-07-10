#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10029
NAME = "stage10029_python_cpp_heldout_review_packet"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKET = OUT_DIR / "python_cpp_heldout_review_packet.json"
ROWS = OUT_DIR / "python_cpp_heldout_review_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PYTHON_CPP_HELDOUT_REVIEW_PACKET_STAGE10029.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
COMPARISON = ROOT / "runs/local/artifacts/stage10028_deduped_source_heldout_same_manifest_comparison_audit/deduped_source_heldout_same_manifest_comparison_rows.jsonl"


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
    rows = load_jsonl(COMPARISON)
    selected = [row for row in rows if str(row.get("language_family") or "") in {"python", "c_cpp"}]
    counts = Counter(str(row.get("language_family") or "") for row in selected)
    outcome_counts = Counter()
    by_language_outcome: dict[str, Counter[str]] = {"python": Counter(), "c_cpp": Counter()}
    for row in selected:
        hm = bool(row.get("hundred_m_correct"))
        gm = bool(row.get("gemma_correct"))
        if hm and gm:
            outcome = "both_correct"
        elif hm and not gm:
            outcome = "100m_only_correct"
        elif gm and not hm:
            outcome = "gemma_only_correct"
        else:
            outcome = "both_wrong"
        row["review_outcome_bucket"] = outcome
        outcome_counts[outcome] += 1
        by_language_outcome[str(row.get("language_family"))][outcome] += 1
    failures: list[str] = []
    if counts.get("python") != 5:
        failures.append("python_review_rows_not_5")
    if counts.get("c_cpp") != 8:
        failures.append("c_cpp_review_rows_not_8")
    packet = {
        "passed": not failures,
        "failures": failures,
        "metrics": {
            "rows": len(selected),
            "language_counts": dict(sorted(counts.items())),
            "outcome_counts": dict(sorted(outcome_counts.items())),
            "by_language_outcome": {key: dict(sorted(value.items())) for key, value in sorted(by_language_outcome.items())},
        },
        "review_focus": [
            "Verify label identifiability for the heldout Python and c_cpp rows under expert-maintainer review.",
            "Look for any row-construction artifacts that could still advantage either model despite source-heldout filtering.",
            "Use the unresolved rows to drive fresh independent root construction instead of replay.",
        ],
    }
    write_jsonl(ROWS, selected)
    return packet


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_packet()
    PACKET.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Run expert review on these Python and c_cpp heldout rows, then build fresh independent roots for the unresolved patterns rather than replaying them into train."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {"packet": display(PACKET), "rows": display(ROWS), "doc": display(DOC)},
        "decision": "Materialized the deduped source-heldout Python and c_cpp review packet so the tied or weakly-supported heldout cells can go through expert review and fresh-root replenishment instead of replay-based training fixes.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage10029 Python Cpp Heldout Review Packet",
                "",
                f"Passed: `{summary['passed']}`",
                f"Rows: `{built['metrics']['rows']}`",
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
