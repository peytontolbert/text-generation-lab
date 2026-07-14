#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10714
NAME = "stage10714_python_verifier_contrast_creation_queue"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "python_verifier_contrast_creation_queue.json"
QUEUE_JSONL = OUT_DIR / "python_verifier_contrast_tasks.jsonl"
RUN_SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

STRICT_ROWS = ROOT / "runs/local/artifacts/stage10709_rewritten_plus_reviewed_training_package_execution_repaired/strict_rows.jsonl"
GATE_JSON = ROOT / "runs/local/artifacts/stage10713_python_rust_residual_contrast_builder_or_quarantine_gate/python_rust_residual_contrast_builder_or_quarantine_gate.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    gate = load_json(GATE_JSON)
    strict_rows = load_jsonl(STRICT_ROWS)

    python_strict = [
        row for row in strict_rows
        if str(row.get("language_family") or "") == "python"
        and str(row.get("target_subtype") or row.get("task_type") or "") == "verifier_outcome"
    ]

    queue = []
    for row in python_strict:
        queue.append(
            {
                "task_id": f"{row['row_id']}::fresh_python_verifier_contrast",
                "priority": "highest",
                "language_family": "python",
                "target_subtype": "verifier_outcome",
                "source_row_id": row.get("row_id"),
                "repo_family": row.get("repo_family"),
                "strict_origin": True,
                "must_not_reuse_root": True,
                "creation_requirements": [
                    "Build fresh root-disjoint rows, not same-root permutations or replays.",
                    "Create explicit B-vs-C-vs-D verifier outcome contrasts.",
                    "Do not expose the gold test path before options.",
                    "Include multiple plausible test candidates where candidate_change_surface is tempting but wrong.",
                    "Keep prompt_target_leak false and preserve root split isolation.",
                ],
                "desired_labels": [
                    "FAIL_TARGETED_TEST_SELECTION",
                    "RETRIEVE_MORE",
                    "ABSTAIN_INSUFFICIENT_EVIDENCE",
                ],
                "reference_prompt_excerpt": str(row.get("prompt_text") or "")[:1200],
            }
        )

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "python_verifier_contrast_creation_queue_ready",
        "claim_scope": [
            "Translate the stage10713 no-go result into concrete Python verifier contrast creation tasks.",
            "Keep the queue root-disjoint from the current strict frontier.",
            "Make the next promotable residual step explicit instead of leaving it as an abstract recommendation.",
        ],
        "source_artifacts": {
            "strict_rows": display(STRICT_ROWS),
            "residual_gate": display(GATE_JSON),
        },
        "gates": {
            "python_probe_ready_now": ((gate.get("python_gate") or {}).get("probe_ready")),
            "rust_probe_ready_now": ((gate.get("rust_gate") or {}).get("probe_ready")),
            "joint_promotion_probe_ready_now": ((gate.get("promotion_gate") or {}).get("allow_joint_promotion_probe")),
        },
        "queue_counts": {
            "python_creation_tasks": len(queue),
        },
        "headline_findings": [
            "Stage10713 proved Python has zero promotable residual verifier contrast rows after strict/canary/comparison duplicates are removed.",
            "The next honest step is Python contrast creation from fresh roots, not another blended probe request.",
            "Rust can support limited diagnostic citation work, but Python remains the gating language for a joint promotable residual run.",
        ],
        "recommended_next_stage": "stage10715_fresh_python_verifier_contrast_builder",
        "outputs": {
            "summary_json": display(SUMMARY_JSON),
            "queue_jsonl": display(QUEUE_JSONL),
        },
    }

    write_jsonl(QUEUE_JSONL, queue)
    write_json(SUMMARY_JSON, summary)
    write_json(
        RUN_SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": summary["decision"],
            "summary_json": display(SUMMARY_JSON),
        },
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
