#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10030
NAME = "stage10030_python_cpp_fresh_root_replenishment_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST = OUT_DIR / "python_cpp_fresh_root_replenishment_request.json"
ROWS = OUT_DIR / "python_cpp_fresh_root_replenishment_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PYTHON_CPP_FRESH_ROOT_REPLENISHMENT_REQUEST_STAGE10030.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
COMPARISON = ROOT / "runs/local/artifacts/stage10029_python_cpp_heldout_review_packet/python_cpp_heldout_review_rows.jsonl"


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
    rows = load_jsonl(COMPARISON)
    target_rows = [
        row
        for row in rows
        if row.get("review_outcome_bucket") in {"both_wrong", "gemma_only_correct"}
    ]
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in target_rows:
        grouped[(str(row.get("language_family") or ""), str(row.get("expected_label") or ""))].append(row)

    requests: list[dict[str, Any]] = []
    for (language, label), group_rows in sorted(grouped.items()):
        bucket_counts = Counter(str(row.get("review_outcome_bucket") or "") for row in group_rows)
        example_roles = sorted({str(row.get("counterfactual_role") or "") for row in group_rows})
        root_ids = sorted({str(row.get("counterfactual_root_row_id") or "") for row in group_rows})
        requests.append(
            {
                "language_family": language,
                "target_label": label,
                "blocked_rows": len(group_rows),
                "blocked_outcome_counts": dict(sorted(bucket_counts.items())),
                "example_counterfactual_roles": example_roles,
                "root_case_ids": root_ids,
                "requested_fresh_independent_roots": max(3, len(root_ids)),
                "required_constraints": [
                    "new source_root not present in any current train or heldout manifest",
                    "same visible-evidence surface contract as deduped heldout comparison",
                    "expert-maintainer identifiability review required before promotion",
                    "anti-cheat scan required for target-label literals and train-root overlap",
                ],
            }
        )

    counts = Counter(str(row.get("language_family") or "") for row in target_rows)
    failures: list[str] = []
    if counts.get("python") != 3:
        failures.append("python_unresolved_rows_not_3")
    if counts.get("c_cpp") != 6:
        failures.append("c_cpp_unresolved_rows_not_6")
    if len(requests) != 6:
        failures.append("fresh_root_request_groups_not_6")

    packet = {
        "passed": not failures,
        "failures": failures,
        "metrics": {
            "rows": len(target_rows),
            "language_counts": dict(sorted(counts.items())),
            "request_group_count": len(requests),
            "requests_by_language": {
                language: sum(1 for request in requests if request["language_family"] == language)
                for language in sorted({request["language_family"] for request in requests})
            },
        },
        "requests": requests,
        "policy": {
            "do_not_replay_existing_heldout_rows_into_train": True,
            "require_fresh_independent_roots": True,
            "require_expert_review": True,
            "require_eval_hacking_audit": True,
        },
    }
    write_jsonl(ROWS, target_rows)
    return packet


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_request()
    REQUEST.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Construct fresh independent Python and c_cpp heldout roots for these unresolved label patterns, then rerun the same-manifest 100M-versus-Gemma comparison on the replenished heldout set."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {"request": display(REQUEST), "rows": display(ROWS), "doc": display(DOC)},
        "decision": "Materialized the fresh-root replenishment request for unresolved Python and c_cpp heldout cells so future improvement work expands independent heldout coverage instead of replaying the current evaluation rows.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage10030 Python Cpp Fresh Root Replenishment Request",
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
