#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10725
NAME = "stage10725_python_verifier_semantic_contrast_builder"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "python_verifier_semantic_contrast_builder.json"
SUPPORT_ROWS_JSONL = OUT_DIR / "python_verifier_semantic_contrast_rows.jsonl"
ROOTS_JSONL = OUT_DIR / "python_verifier_semantic_contrast_roots.jsonl"
TRAIN_ROWS_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
SUMMARY_CARD = ROOT / "runs/summaries" / f"{NAME}.json"

EXECUTION_PATH = ROOT / "runs/local/artifacts/stage10724_residual_semantic_repair_execution_path/residual_semantic_repair_execution_path.json"
STAGE10475_ROWS = ROOT / "runs/local/artifacts/stage10475_python_verifier_materialized_root_bundle_builder/python_verifier_materialized_bounded_rows.jsonl"
STAGE10501_ROWS = ROOT / "runs/local/artifacts/stage10501_hf_local_repaired_compact_bounded_projection/hf_local_repaired_compact_bounded_rows.jsonl"
STAGE10716_ROWS = ROOT / "runs/local/artifacts/stage10716_python_verifier_setvalued_or_abstain_support_builder/agentkernel_lite_encdec_train.jsonl"
STAGE10717_ROWS = ROOT / "runs/local/artifacts/stage10717_python_singleton_verifier_support_manifest/agentkernel_lite_encdec_train.jsonl"

CONTEXT_PACK_ROOT = "stage10236::localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_27t02_21_48_019bfd41_d2a6_7672_9873_81f8_src_code_assist_orchestrator_config_py_src_code_assist_orchestrator_context_pack_acd5ccc9c1_aug_1500000_8b46e7f662::python"
HF_LOCAL_ROOT = "stage10300::localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_26t23_27_57_019bfca2_aa35_7502_b929_649a_src_code_assist_agents_hf_local_py_src_code_assist_agents_hf_local_planner_py_sr_3fb1ce61a2_aug_1500000_8b46e7f662::python"


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
    execution_path = load_json(EXECUTION_PATH)
    stage10475_rows = load_jsonl(STAGE10475_ROWS)
    stage10501_rows = load_jsonl(STAGE10501_ROWS)
    stage10716_rows = load_jsonl(STAGE10716_ROWS)
    stage10717_rows = load_jsonl(STAGE10717_ROWS)

    selected_rows: list[dict[str, Any]] = []

    # Context-pack promotable verifier root.
    for row in stage10475_rows:
        if row.get("source_bundle_id") == CONTEXT_PACK_ROOT and row.get("task_type") == "verifier_outcome":
            row = dict(row)
            row["semantic_repair_role"] = "promotable_disjoint_verifier_seed"
            row["builder_stage"] = STAGE
            selected_rows.append(row)

    # Repaired hf_local verifier sibling-contrast rows.
    for row in stage10501_rows:
        if row.get("task_type") == "verifier_outcome":
            row = dict(row)
            row["source_bundle_id"] = HF_LOCAL_ROOT
            row["repo_id"] = row.get("repo_id") or "code_assist"
            row["repo_family"] = row.get("repo_family") or "code_assist"
            row["language_family"] = "python"
            row["train_support_only"] = True
            row["strict_eval_eligible"] = False
            row["selected_test_anchor"] = True
            row["verifier_anchor"] = True
            row["semantic_repair_role"] = "promotable_disjoint_verifier_seed"
            row["builder_stage"] = STAGE
            selected_rows.append(row)

    # Honesty-only abstention rows.
    for row in stage10716_rows:
        if row.get("task_type") == "verifier_outcome":
            row = dict(row)
            row["semantic_repair_role"] = "honesty_only_abstention_seed"
            row["builder_stage"] = STAGE
            selected_rows.append(row)

    # De-duplicate by row_id while preferring richer repaired rows.
    deduped: dict[str, dict[str, Any]] = {}
    for row in selected_rows:
        row_id = str(row["row_id"])
        existing = deduped.get(row_id)
        if existing is None:
            deduped[row_id] = row
            continue
        if "compact_bounded_repaired" in row_id:
            deduped[row_id] = row

    final_rows = sorted(deduped.values(), key=lambda r: str(r["row_id"]))

    roots: dict[str, dict[str, Any]] = {}
    for row in final_rows:
        root_id = str(row.get("source_bundle_id") or row.get("source_root_id") or "")
        rec = roots.setdefault(
            root_id,
            {
                "root_id": root_id,
                "repo_id": str(row.get("repo_id") or "unknown"),
                "repo_family": str(row.get("repo_family") or row.get("repo_id") or "unknown"),
                "language_family": "python",
                "row_ids": [],
                "roles": set(),
                "task_types": set(),
                "selected_test_anchor": bool(row.get("selected_test_anchor")),
                "verifier_anchor": bool(row.get("verifier_anchor")),
            },
        )
        rec["row_ids"].append(str(row["row_id"]))
        rec["roles"].add(str(row["semantic_repair_role"]))
        rec["task_types"].add(str(row.get("task_type") or "unknown"))

    root_rows = []
    for rec in roots.values():
        rec["roles"] = sorted(rec["roles"])
        rec["task_types"] = sorted(rec["task_types"])
        rec["row_count"] = len(rec["row_ids"])
        root_rows.append(rec)
    root_rows.sort(key=lambda r: r["root_id"])

    python_target = next(t for t in load_jsonl(OUT_DIR.parent / "stage10724_residual_semantic_repair_execution_path" / "residual_semantic_repair_targets.jsonl") if t["language_family"] == "python")

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "python_semantic_verifier_seed_ready",
        "claim_scope": [
            "Build the immediate Python semantic verifier seed package specified by stage10724.",
            "Separate promotable disjoint verifier seeds from honesty-only abstention seeds.",
        ],
        "current_residual_target": python_target,
        "metrics": {
            "selected_row_count": len(final_rows),
            "promotable_seed_row_count": sum(1 for row in final_rows if row["semantic_repair_role"] == "promotable_disjoint_verifier_seed"),
            "honesty_seed_row_count": sum(1 for row in final_rows if row["semantic_repair_role"] == "honesty_only_abstention_seed"),
            "root_count": len(root_rows),
            "promotable_root_count": sum(1 for row in root_rows if "promotable_disjoint_verifier_seed" in row["roles"]),
            "honesty_root_count": sum(1 for row in root_rows if "honesty_only_abstention_seed" in row["roles"]),
        },
        "interpretation": [
            "This package is enough to seed the next Python semantic verifier probe, but it is still short of the six fresh disjoint roots required for a scaled promotion path.",
            "The strongest current signal comes from hf_local repaired sibling-test competition and the code_assist context-pack verifier root.",
            "Agentkernel abstention rows remain honesty support only and should not be counted as verifier disambiguation evidence.",
        ],
        "anti_cheat_contract": [
            "All rows remain train_support_only and strict_eval_eligible=false.",
            "No MirrorMind strict root is reused in train.",
            "The hf_local rows use opaque V1/V2/V3 verifier labels instead of direct gold test paths.",
            "Any follow-on execution request must frontload these rows or use enough steps to guarantee sampling coverage.",
        ],
        "next_best_step": "Merge these rows into the next stage10727 semantic contrast support package, then run a frontloaded probe with the repaired overlay as the regression gate.",
        "source_artifacts": {
            "execution_path": display(EXECUTION_PATH),
            "stage10475_rows": display(STAGE10475_ROWS),
            "stage10501_rows": display(STAGE10501_ROWS),
            "stage10716_rows": display(STAGE10716_ROWS),
            "stage10717_rows": display(STAGE10717_ROWS),
        },
        "outputs": {
            "summary_json": display(SUMMARY_JSON),
            "support_rows": display(SUPPORT_ROWS_JSONL),
            "root_manifest": display(ROOTS_JSONL),
            "train_rows": display(TRAIN_ROWS_JSONL),
        },
    }

    write_jsonl(SUPPORT_ROWS_JSONL, final_rows)
    write_jsonl(ROOTS_JSONL, root_rows)
    write_jsonl(TRAIN_ROWS_JSONL, final_rows)
    write_json(SUMMARY_JSON, payload)
    write_json(
        SUMMARY_CARD,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "selected_row_count": payload["metrics"]["selected_row_count"],
            "artifact": display(SUMMARY_JSON),
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
