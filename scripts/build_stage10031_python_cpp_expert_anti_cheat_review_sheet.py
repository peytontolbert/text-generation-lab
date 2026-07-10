#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10031
NAME = "stage10031_python_cpp_expert_anti_cheat_review_sheet"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SHEET = OUT_DIR / "python_cpp_expert_anti_cheat_review_sheet.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PYTHON_CPP_EXPERT_ANTI_CHEAT_REVIEW_SHEET_STAGE10031.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
ROWS = ROOT / "runs/local/artifacts/stage10029_python_cpp_heldout_review_packet/python_cpp_heldout_review_rows.jsonl"

CHECKS = [
    "Is there exactly one justified answer from the visible evidence?",
    "Does any field ordering, option naming, or decoy wording leak the label?",
    "Would an expert maintainer choose abstain or request more evidence instead of the forced label?",
    "Does the row remain valid under source-root independence and anti-cheat review?",
    "Should this row seed fresh independent heldout roots for the same failure family?",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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


def build_sheet() -> dict[str, Any]:
    rows = load_jsonl(ROWS)
    counts = Counter(str(row.get("review_outcome_bucket") or "") for row in rows)
    review_rows = []
    for row in rows:
        review_rows.append(
            {
                "row_id": row.get("row_id"),
                "language_family": row.get("language_family"),
                "expected_label": row.get("expected_label"),
                "review_outcome_bucket": row.get("review_outcome_bucket"),
                "counterfactual_root_row_id": row.get("counterfactual_root_row_id"),
                "counterfactual_role": row.get("counterfactual_role"),
                "model_preds": {
                    "hundred_m": row.get("hundred_m_pred"),
                    "gemma": row.get("gemma_pred"),
                },
                "required_checks": list(CHECKS),
            }
        )
    failures: list[str] = []
    if len(review_rows) != 13:
        failures.append("review_rows_not_13")
    if counts.get("both_wrong") != 8:
        failures.append("both_wrong_rows_not_8")
    sheet = {
        "passed": not failures,
        "failures": failures,
        "metrics": {
            "rows": len(review_rows),
            "outcome_counts": dict(sorted(counts.items())),
            "required_checks_per_row": len(CHECKS),
        },
        "review_rows": review_rows,
        "review_policy": {
            "blind_to_gold_when_possible": True,
            "attach_expert_maintainer_judgment": True,
            "attach_anti_cheat_notes": True,
            "flag_rows_needing_abstain_or_fresh_root_rebuild": True,
        },
    }
    return sheet


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_sheet()
    SHEET.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Use this review sheet during expert-maintainer and anti-cheat adjudication of the unresolved Python and c_cpp heldout rows before constructing fresh independent roots."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {"sheet": display(SHEET), "doc": display(DOC)},
        "decision": "Materialized the expert-maintainer and anti-cheat review sheet for the unresolved Python and c_cpp heldout rows so evaluation quality can be improved without drifting back into replay-driven training fixes.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage10031 Python Cpp Expert Anti Cheat Review Sheet",
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
