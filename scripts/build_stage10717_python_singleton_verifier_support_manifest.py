#!/usr/bin/env python3
"""Normalize promotable-disjoint Python verifier support into current format."""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
STAGE = 10717
NAME = "stage10717_python_singleton_verifier_support_manifest"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME

STAGE10475_ROOTS = (
    ROOT
    / "runs/local/artifacts/stage10475_python_verifier_materialized_root_bundle_builder/python_verifier_materialized_root_manifest.jsonl"
)
STAGE10475_ROWS = (
    ROOT
    / "runs/local/artifacts/stage10475_python_verifier_materialized_root_bundle_builder/python_verifier_materialized_bounded_rows.jsonl"
)
STAGE10501_ROWS = (
    ROOT
    / "runs/local/artifacts/stage10501_hf_local_repaired_compact_bounded_projection/hf_local_repaired_compact_bounded_rows.jsonl"
)
STAGE10501_SUMMARY = (
    ROOT
    / "runs/local/artifacts/stage10501_hf_local_repaired_compact_bounded_projection/hf_local_repaired_compact_bounded_projection.json"
)
STAGE10500_AUDIT = (
    ROOT
    / "runs/local/artifacts/stage10500_hf_local_multitest_repair_audit/hf_local_multitest_repair_audit.json"
)
STAGE10709_PACKAGE = (
    ROOT
    / "runs/local/artifacts/stage10709_rewritten_plus_reviewed_training_package_execution_repaired"
)

SUMMARY_JSON = OUT_DIR / "python_singleton_verifier_support_manifest.json"
ROOTS_JSONL = OUT_DIR / "python_singleton_verifier_root_manifest.jsonl"
ROWS_JSONL = OUT_DIR / "python_singleton_verifier_support_rows.jsonl"
TRAIN_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"

CONTEXT_PACK_ROOT = (
    "stage10236::localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_27t02_21_48_019bfd41_d2a6_7672_9873_81f8_"
    "src_code_assist_orchestrator_config_py_src_code_assist_orchestrator_context_pack_acd5ccc9c1_aug_1500000_8b46e7f662::python"
)
HF_LOCAL_ROOT = (
    "stage10300::localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_26t23_27_57_019bfca2_aa35_7502_b929_649a_"
    "src_code_assist_agents_hf_local_py_src_code_assist_agents_hf_local_planner_py_sr_3fb1ce61a2_aug_1500000_8b46e7f662::python"
)


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


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def current_stage10709_roots() -> set[str]:
    roots: set[str] = set()
    for name in ("train_rows.jsonl", "validation_rows.jsonl", "strict_rows.jsonl", "canary_rows.jsonl", "eval_rows.jsonl"):
        path = STAGE10709_PACKAGE / name
        if not path.exists():
            continue
        for row in load_jsonl(path):
            root_id = str(row.get("source_root_id") or row.get("root_id") or "")
            if root_id:
                roots.add(root_id)
    return roots


def normalize_root_record(row: dict[str, Any], *, current_roots: set[str]) -> dict[str, Any]:
    root_id = str(row["root_id"])
    repo_id = "code_assist" if root_id.startswith("stage10236::") or root_id.startswith("stage10300::") else str(row.get("repo_id") or "unknown")
    return {
        "record_type": "python_singleton_verifier_support_root",
        "root_id": root_id,
        "repo_id": repo_id,
        "repo_family": repo_id,
        "language_family": "python",
        "task_types": ["verifier_outcome"],
        "selected_test_anchor": True,
        "verifier_anchor": True,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "train_support_only": True,
        "split": "train",
        "split_role": "train_support",
        "same_surface_eval_admissible": False,
        "current_stage10709_overlap": root_id in current_roots,
        "support_role": row.get("support_role"),
        "claim_boundary": row.get("claim_boundary") or [],
        "row_count": row.get("row_count"),
        "verifier_outcome_rows": row.get("verifier_outcome_rows"),
    }


def with_common_fields(row: dict[str, Any], *, source_root_id: str) -> dict[str, Any]:
    out = dict(row)
    out["source_root_id"] = source_root_id
    out["source_bundle_id"] = source_root_id
    out["repo_id"] = "code_assist"
    out["repo_family"] = "code_assist"
    out["language_family"] = "python"
    out["task_type"] = "verifier_outcome"
    out["split"] = "train"
    out["split_role"] = "train_support"
    out["train_support_only"] = True
    out["strict_eval_eligible"] = False
    out["source_heldout_admissible"] = False
    out["selected_test_anchor"] = True
    out["verifier_anchor"] = True
    out["package_split"] = "train"
    out["package_source_kind"] = "python_singleton_verifier_support"
    anti_cheat = dict(out.get("anti_cheat") or {})
    anti_cheat["current_support_manifest_v1"] = True
    anti_cheat["same_surface_eval_admissible"] = False
    out["anti_cheat"] = anti_cheat
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    current_roots = current_stage10709_roots()
    root_rows = load_jsonl(STAGE10475_ROOTS)
    bounded_rows = load_jsonl(STAGE10475_ROWS)
    hf_local_rows = load_jsonl(STAGE10501_ROWS)
    hf_local_summary = load_json(STAGE10501_SUMMARY)
    hf_local_audit = load_json(STAGE10500_AUDIT)

    root_manifest = [
        normalize_root_record(row, current_roots=current_roots)
        for row in root_rows
        if str(row.get("root_id") or "") in {CONTEXT_PACK_ROOT, HF_LOCAL_ROOT}
    ]

    support_rows: list[dict[str, Any]] = []

    for row in bounded_rows:
        if str(row.get("row_id") or "").startswith(CONTEXT_PACK_ROOT) and str(row.get("task_type") or "") == "verifier_outcome":
            normalized = with_common_fields(row, source_root_id=CONTEXT_PACK_ROOT)
            normalized["support_contract"] = {
                "support_origin": "stage10475_context_pack_materialized_root",
                "singleton_verifier_target": True,
                "permutation_variant_count": 1,
            }
            support_rows.append(normalized)

    for row in hf_local_rows:
        if str(row.get("task_type") or "") != "verifier_outcome":
            continue
        normalized = with_common_fields(row, source_root_id=HF_LOCAL_ROOT)
        normalized["support_contract"] = {
            "support_origin": "stage10501_hf_local_repaired_projection",
            "singleton_verifier_target": True,
            "permutation_variant_count": int((hf_local_summary.get("summary") or {}).get("verifier_variant_count") or 0),
            "repair_audit_passed": bool(hf_local_audit.get("passed")),
        }
        support_rows.append(normalized)

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "singleton_python_verifier_support_available",
        "claim_boundary": [
            "This stage packages root-disjoint singleton Python verifier support into the current train-support format.",
            "These roots are train-side support only and must not be used to upgrade the strict v2.7 headline directly.",
            "This stage reduces the real Python promotion blocker by restoring current access to known honest singleton verifier families.",
        ],
        "inputs": {
            "stage10475_root_manifest": str(STAGE10475_ROOTS.relative_to(ROOT)),
            "stage10475_bounded_rows": str(STAGE10475_ROWS.relative_to(ROOT)),
            "stage10501_rows": str(STAGE10501_ROWS.relative_to(ROOT)),
            "stage10500_audit": str(STAGE10500_AUDIT.relative_to(ROOT)),
        },
        "metrics": {
            "root_count": len(root_manifest),
            "support_row_count": len(support_rows),
            "rows_by_root": dict(sorted(Counter(str(row["source_root_id"]) for row in support_rows).items())),
            "current_stage10709_overlap_roots": sum(1 for row in root_manifest if row["current_stage10709_overlap"]),
            "hf_local_repair_audit_passed": bool(hf_local_audit.get("passed")),
        },
        "next_best_step": (
            "Merge these rows into the next execution-repaired training package and treat them as the singleton Python verifier lane. "
            "In parallel, keep mining more disjoint Python verifier roots because two roots are still not enough to call the lane scaled."
        ),
        "outputs": {
            "summary_json": str(SUMMARY_JSON.relative_to(ROOT)),
            "root_manifest": str(ROOTS_JSONL.relative_to(ROOT)),
            "support_rows": str(ROWS_JSONL.relative_to(ROOT)),
            "train_rows": str(TRAIN_JSONL.relative_to(ROOT)),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(ROOTS_JSONL, root_manifest)
    write_jsonl(ROWS_JSONL, support_rows)
    write_jsonl(TRAIN_JSONL, support_rows)
    write_jsonl(VALIDATION_JSONL, [])
    write_jsonl(STRICT_JSONL, [])
    write_jsonl(STRESS_JSONL, [])


if __name__ == "__main__":
    main()
