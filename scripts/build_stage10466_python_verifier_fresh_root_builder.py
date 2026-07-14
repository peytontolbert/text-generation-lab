#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10466
NAME = "stage10466_python_verifier_fresh_root_builder"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "python_verifier_fresh_root_builder.json"
TARGETS_JSONL = OUT_DIR / "python_verifier_fresh_root_targets.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

QUEUE_JSON = ROOT / "runs/local/artifacts/stage10444_repaired_v27_disjoint_residual_queue/repaired_v27_disjoint_residual_queue.json"
ATLAS_JSON = ROOT / "runs/local/artifacts/stage10445_python_disjoint_root_candidate_atlas/python_disjoint_root_candidate_atlas.json"
ROWS_JSONL = ROOT / "runs/local/artifacts/stage10445_python_disjoint_root_candidate_atlas/python_disjoint_root_candidate_rows.jsonl"
SUPPLY_INVENTORY = ROOT / "runs/local/artifacts/stage10463_python_verifier_fresh_root_inventory/python_verifier_fresh_root_inventory.json"
PACKAGE_REQUEST = ROOT / "runs/local/artifacts/stage10465_fresh_residual_root_package_and_probe_request/fresh_residual_root_package_and_probe_request.json"


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
    queue = load_json(QUEUE_JSON)
    atlas = load_json(ATLAS_JSON)
    inventory = load_json(SUPPLY_INVENTORY)
    package_request = load_json(PACKAGE_REQUEST)
    rows = load_jsonl(ROWS_JSONL)

    target = next(row for row in queue["targets"] if row["language_family"] == "python")

    ranked_support = [
        row for row in rows
        if row.get("recommendation") == "best_disjoint_python_support_candidate"
    ]
    ranked_support.sort(key=lambda row: (-int(row.get("priority_score", 0)), str(row.get("bundle_id"))))

    honesty_support = [
        row for row in rows
        if row.get("recommendation") == "abstention_or_successor_support_only"
    ]
    honesty_support.sort(key=lambda row: (-int(row.get("priority_score", 0)), str(row.get("bundle_id"))))

    builder_targets: list[dict[str, Any]] = []
    for order, row in enumerate(ranked_support, start=1):
        builder_targets.append(
            {
                "priority_order": order,
                "support_role": "promotable_disjoint_support_candidate",
                "bundle_id": row["bundle_id"],
                "candidate_root_id": row["candidate_root_id"],
                "repo_id": row["repo_id"],
                "repo_family": row["repo_family"],
                "selected_tests_count": row["selected_tests_count"],
                "candidate_path_count": row["candidate_path_count"],
                "required_task_shape": [
                    "verifier_outcome",
                    "multiple plausible test-file options",
                    "selected-test anchor present",
                    "close sibling wrong target remains tempting",
                ],
                "claim_boundary": [
                    "Use as root-disjoint train support only until a fresh heldout root from the same family exists.",
                    "Do not merge with same-family MirrorMind support in the same promotion packet.",
                ],
            }
        )

    for row in honesty_support:
        builder_targets.append(
            {
                "priority_order": len(builder_targets) + 1,
                "support_role": "abstention_honesty_support_only",
                "bundle_id": row["bundle_id"],
                "candidate_root_id": row["candidate_root_id"],
                "repo_id": row["repo_id"],
                "repo_family": row["repo_family"],
                "selected_tests_count": row["selected_tests_count"],
                "candidate_path_count": row["candidate_path_count"],
                "required_task_shape": [
                    "abstention_or_implementation_vs_implementation_only",
                ],
                "claim_boundary": [
                    "Do not use these successor rows as the core verifier disambiguation curriculum.",
                    "Use only to preserve abstention honesty and non-overconfident behavior.",
                ],
            }
        )

    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "python_verifier_fresh_root_builder_ready",
        "claim_scope": [
            "Materialize the next root-disjoint Python verifier builder targets for the repaired-v2.7 residual plateau.",
            "Prioritize code_assist-rooted disjoint support for promotable progress and keep successor rows strictly as honesty support.",
        ],
        "source_artifacts": {
            "residual_queue": display(QUEUE_JSON),
            "python_disjoint_atlas": display(ATLAS_JSON),
            "python_candidate_rows": display(ROWS_JSONL),
            "python_supply_inventory": display(SUPPLY_INVENTORY),
            "fresh_residual_package_request": display(PACKAGE_REQUEST),
        },
        "current_residual_target": target,
        "support_inventory_summary": {
            "promotable_disjoint_candidates": len(ranked_support),
            "honesty_only_candidates": len(honesty_support),
            "minimum_new_roots_required": inventory["builder_requirements"][0],
        },
        "builder_requirements": inventory["builder_requirements"],
        "target_package_contract": {
            "must_be_root_disjoint": True,
            "must_not_reuse_current_mirrormind_strict_root": True,
            "must_keep_same_family_support_separate": True,
            "must_prefer_code_assist_selected_test_anchors": True,
            "must_report_repo_family_balance": ["code_assist", "agentkernel_successor_honesty_only"],
        },
        "recommended_next_stage": "stage10468_fresh_residual_root_support_package",
        "targets_jsonl": display(TARGETS_JSONL),
    }

    write_jsonl(TARGETS_JSONL, builder_targets)
    write_json(REQUEST_JSON, request)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": request["decision"],
            "targets": display(TARGETS_JSONL),
        },
    )
    print(json.dumps(request, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
