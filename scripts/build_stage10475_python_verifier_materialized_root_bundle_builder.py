#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10475
NAME = "stage10475_python_verifier_materialized_root_bundle_builder"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "python_verifier_materialized_root_bundle_builder.json"
ROOTS_JSONL = OUT_DIR / "python_verifier_materialized_root_manifest.jsonl"
ROWS_JSONL = OUT_DIR / "python_verifier_materialized_bounded_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

MATERIALIZATION_REQUEST = ROOT / "runs/local/artifacts/stage10472_python_verifier_fresh_root_materialization_request/python_verifier_fresh_root_materialization_request.json"
SUPPORT_ROWS_JSONL = ROOT / "runs/local/artifacts/stage10468_fresh_residual_root_support_package/fresh_residual_root_support_rows.jsonl"
SUPPORT_PACKAGE_JSON = ROOT / "runs/local/artifacts/stage10468_fresh_residual_root_support_package/fresh_residual_root_support_package.json"

PROMOTABLE_ROOTS = {
    "stage10236::localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_27t02_21_48_019bfd41_d2a6_7672_9873_81f8_src_code_assist_orchestrator_config_py_src_code_assist_orchestrator_context_pack_acd5ccc9c1_aug_1500000_8b46e7f662::python",
    "stage10300::localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_26t23_27_57_019bfca2_aa35_7502_b929_649a_src_code_assist_agents_hf_local_py_src_code_assist_agents_hf_local_planner_py_sr_3fb1ce61a2_aug_1500000_8b46e7f662::python",
}
HONESTY_ONLY_ROOTS = {
    "stage10110::localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_29t14_24_45_019d39fb_a380_7a30_8790_9d59_agent_kernel_improvement_py_agent_kernel_modeling_adapter_training_py_agent_kern_94b87c02df_aug_1500000_8b46e7f662::python_successor",
    "stage10110::localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_29t14_24_54_019d39fb_c43d_7e62_b055_b00b_agent_kernel_cycle_runner_py_agent_kernel_improvement_py_agent_kernel_learning_c_6a4dce0d0c_aug_1500000_8b46e7f662::python_successor",
}


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
    request = load_json(MATERIALIZATION_REQUEST)
    support_package = load_json(SUPPORT_PACKAGE_JSON)
    rows = [row for row in load_jsonl(SUPPORT_ROWS_JSONL) if str(row.get("language_family")) == "python"]

    rows_by_root: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        root_id = str(row.get("source_bundle_id") or row.get("source_root_id") or "")
        rows_by_root[root_id].append(row)

    root_manifest: list[dict[str, Any]] = []
    for root_id, root_rows in sorted(rows_by_root.items()):
        first = root_rows[0]
        task_counts = Counter(str(row.get("task_type") or "unknown") for row in root_rows)
        support_role = "promotable_disjoint_support_candidate" if root_id in PROMOTABLE_ROOTS else "abstention_honesty_support_only"
        root_manifest.append(
            {
                "root_id": root_id,
                "repo_id": str(first.get("repo_id") or "unknown"),
                "repo_family": str(first.get("repo_family") or first.get("repo_id") or "unknown"),
                "language_family": "python",
                "support_role": support_role,
                "materialization_status": "executable_rows_available",
                "row_count": len(root_rows),
                "task_type_counts": dict(sorted(task_counts.items())),
                "verifier_outcome_rows": int(task_counts.get("verifier_outcome", 0)),
                "selected_test_anchor": bool(first.get("selected_test_anchor")),
                "verifier_anchor": bool(first.get("verifier_anchor")),
                "strict_eval_eligible": False,
                "source_heldout_admissible": False,
                "claim_boundary": [
                    "Use only as train-side fresh-root support until new heldout roots are built from the same skill family.",
                    "Do not use these rows to upgrade the v2.7 strict headline directly.",
                ]
                if root_id in PROMOTABLE_ROOTS
                else [
                    "Successor rows preserve abstention honesty only.",
                    "Do not treat these rows as core verifier disambiguation evidence.",
                ],
            }
        )

    requested_roots = int(request["materialization_requirements"]["minimum_new_roots"])
    available_promotable_roots = sum(1 for row in root_manifest if row["support_role"] == "promotable_disjoint_support_candidate")

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "python_verifier_materialized_roots_built",
        "claim_scope": [
            "Materialize executable Python verifier support roots from the staged fresh-root supply.",
            "Show the current supply ceiling explicitly so later stages cannot confuse available executable roots with the larger requested target.",
        ],
        "source_artifacts": {
            "materialization_request": display(MATERIALIZATION_REQUEST),
            "support_package": display(SUPPORT_PACKAGE_JSON),
            "support_rows": display(SUPPORT_ROWS_JSONL),
        },
        "metrics": {
            "materialized_python_rows": len(rows),
            "materialized_root_count": len(root_manifest),
            "promotable_disjoint_root_count": available_promotable_roots,
            "honesty_only_root_count": sum(1 for row in root_manifest if row["support_role"] == "abstention_honesty_support_only"),
            "requested_promotable_root_count": requested_roots,
            "promotable_root_shortfall": max(requested_roots - available_promotable_roots, 0),
            "task_type_counts": dict(sorted(Counter(str(row.get("task_type") or "unknown") for row in rows).items())),
        },
        "support_package_contract": support_package.get("support_package_contract") or {},
        "next_best_step": [
            "Use the two code_assist roots as executable promotable support in the next combined post-plateau package.",
            "Keep the two agentkernel successor rows only as abstention-honesty support.",
            "Replenish at least four more disjoint Python verifier roots before treating the Python side as adequately scaled.",
        ],
        "outputs": {
            "root_manifest": display(ROOTS_JSONL),
            "bounded_rows": display(ROWS_JSONL),
        },
    }

    write_jsonl(ROOTS_JSONL, root_manifest)
    write_jsonl(ROWS_JSONL, rows)
    write_json(REQUEST_JSON, payload)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "request": display(REQUEST_JSON),
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
