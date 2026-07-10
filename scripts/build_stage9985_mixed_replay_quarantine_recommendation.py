#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9985
NAME = "stage9985_mixed_replay_quarantine_recommendation"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "mixed_replay_quarantine_recommendation.json"
ROWS = OUT_DIR / "mixed_replay_quarantine_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "MIXED_REPLAY_QUARANTINE_RECOMMENDATION_STAGE9985.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE = ROOT / "runs/local/artifacts/stage9983_gemma_advantage_row_review_packets/gemma_advantage_row_review_packets.jsonl"


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


def build_recommendation() -> dict[str, Any]:
    source_rows = load_jsonl(SOURCE)
    recommended: list[dict[str, Any]] = []
    failures: list[str] = []
    for row in source_rows:
        role = str(row.get("counterfactual_role") or "")
        if role != "mixed_replay":
            continue
        recommended.append(
            {
                **row,
                "recommended_action": "quarantine_from_training_and_headline_eval",
                "why": [
                    "mixed_replay counterfactual rows were added specifically to test decoy and contradictory evidence handling",
                    "all mixed_replay Gemma-advantage rows remained wrong after selective replay",
                    "reusing unresolved mixed_replay rows as ordinary positive training targets risks teaching the model to imitate ambiguous or shortcut-driven answers",
                ],
            }
        )
    counts = Counter(str(row.get("language_family") or "") for row in recommended)
    metrics = {
        "recommended_quarantine_rows": len(recommended),
        "language_counts": dict(sorted(counts.items())),
    }
    if metrics["recommended_quarantine_rows"] != 7:
        failures.append("recommended_quarantine_rows_not_7")
    if counts.get("python") != 4:
        failures.append("python_quarantine_rows_not_4")
    if counts.get("c_cpp") != 3:
        failures.append("c_cpp_quarantine_rows_not_3")
    return {"passed": not failures, "failures": failures, "metrics": metrics, "rows": recommended}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_recommendation()
    AUDIT.write_text(json.dumps({"stage": STAGE, "name": NAME, "passed": built["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_jsonl(ROWS, built["rows"])
    next_step = "Use this quarantine recommendation to build the next filtered multilingual successor manifest with mixed-replay decoy rows removed, then rerun the 100M probe."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {"audit": display(AUDIT), "rows": display(ROWS), "doc": display(DOC)},
        "decision": "Recommended quarantining the seven mixed-replay Gemma-advantage rows from training and headline eval reuse until human review decides whether they are valid abstention or shortcut-audit items.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9985 Mixed Replay Quarantine Recommendation",
        "",
        f"Passed: `{summary['passed']}`",
        f"Recommended quarantine rows: `{built['metrics']['recommended_quarantine_rows']}`",
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
