#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10892
NAME = "stage10892_residual_root_inventory_successor"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "residual_root_inventory_successor.json"
ROOTS_JSONL = OUT_DIR / "current_residual_roots.jsonl"

PY_QUEUE_ADMISSION = ARTIFACTS / "stage10813_python_queue_aligned_admission" / "review_packets" / "stage10236__localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_27t02_21_48_019bfd41_d2a6_7672_9873_81f8_src_code_assist_orchestrator_config_py_src_code_assist_orchestrator_context_pack_acd5ccc9c1_aug_1500000_8b46e7f662__python"
PY_GEOMETRY_AUDIT = ARTIFACTS / "stage10855_python_verifier_geometry_materialization_audit" / "python_verifier_geometry_materialization_audit.json"
PY_GEOMETRY_PACKET = ARTIFACTS / "stage10854_python_verifier_geometry_materialization_repair" / "review_packets" / "agentkernel__localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_29t14_24_54_019d39fb_c43d_7e62_b055_b00b_agent_kernel_cycle_runner_py_agent_kernel_improvement_py_agent_kernel_learning_c_6a4dce0d0c_aug_1500000_8b46e7f662"
PY_SECOND_JSON = ARTIFACTS / "stage10863_agentkernel_second_python_verifier_materialization" / "agentkernel_second_python_verifier_materialization.json"
PY_SECOND_PACKET = ARTIFACTS / "stage10863_agentkernel_second_python_verifier_materialization" / "review_packets" / "agentkernel__localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_24t22_32_18_019d21fa_350b_7401_bd0e_c83e_agent_kernel_config_py_agent_kernel_cycle_runner_py_agent_kernel_improvement_py__28d49f6b85_aug_1500000_8b46e7f662"
RUST_LINUX_PACKET = ARTIFACTS / "stage10674_rust_fresh_review_packet_scaffolds" / "review_packets" / "linux__rust"
RUST_DATASETS_PACKET = ARTIFACTS / "stage10686_candle_datasets_ai_adjudication" / "review_packets" / "candle__candle-datasets"
RUST_FLASH_JSON = ARTIFACTS / "stage10883_flash_attn_alias_safe_successor_package" / "flash_attn_alias_safe_successor_package.json"
RUST_BINDINGS_HONESTY = ARTIFACTS / "stage10886_tokenizers_bindings_node_honesty_audit" / "tokenizers_bindings_node_honesty_audit.json"
RUST_BINDINGS_BLOCKER = ARTIFACTS / "stage10887_tokenizers_bindings_node_recovery_blocker.py"
POSTRUN_JSON = ARTIFACTS / "stage10891_flash_attn_alias_safe_postrun_audit" / "flash_attn_alias_safe_postrun_audit.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def packet_status(packet_dir: Path, *, bundle_file: str, admission_scope: str, residual_family: str, headline_eligible: bool, note: str, missing_fields: list[str]) -> dict[str, Any]:
    bundle = load_json(packet_dir / bundle_file)
    anti = load_json(packet_dir / "anti_cheat_review_card.json")
    gold = load_json(packet_dir / "perspective_gold_adjudication.json")
    return {
        "bundle_id": str(bundle.get("bundle_id") or bundle.get("root_id") or packet_dir.name),
        "packet_dir": rel(packet_dir),
        "repo_id": str(bundle.get("repo_id") or packet_dir.name.split("__", 1)[0]),
        "language_family": str(bundle.get("language_family") or "unknown"),
        "selected_test_count": len(bundle.get("selected_tests") or []),
        "visible_evidence_keys": sorted((bundle.get("maintainer_visible_evidence") or {}).keys()),
        "anti_cheat_status": anti.get("status"),
        "gold_status": gold.get("status"),
        "admission_scope": admission_scope,
        "residual_family": residual_family,
        "headline_eligible": headline_eligible,
        "note": note,
        "missing_fields": missing_fields,
    }


def main() -> None:
    py_geometry = load_json(PY_GEOMETRY_AUDIT)
    py_second = load_json(PY_SECOND_JSON)
    rust_flash = load_json(RUST_FLASH_JSON)
    rust_bindings = load_json(RUST_BINDINGS_HONESTY)
    postrun = load_json(POSTRUN_JSON)

    roots = [
        packet_status(
            PY_QUEUE_ADMISSION,
            bundle_file="fresh_python_bundle_preview.json",
            admission_scope="train_support_only",
            residual_family="python_verifier_outcome",
            headline_eligible=False,
            note="queue-aligned code_assist verifier root remains admitted support with 4 reviewed selected tests",
            missing_fields=[
                "fresh strict-heldout verifier-transition evaluation row",
                "test-transition labels beyond file-choice semantics",
            ],
        ),
        packet_status(
            PY_GEOMETRY_PACKET,
            bundle_file="fresh_python_bundle_preview.json",
            admission_scope="train_support_only",
            residual_family="python_verifier_outcome",
            headline_eligible=False,
            note=py_geometry["decision"],
            missing_fields=[
                "harder follow-up root without selected-test name priors",
                "strict-heldout verifier-transition row with visible test/transition target",
            ],
        ),
        {
            "bundle_id": py_second["bundle_id"],
            "packet_dir": py_second["packet_dir"],
            "repo_id": py_second["repo_id"],
            "language_family": py_second["language_family"],
            "selected_test_count": py_second["selected_test_count"],
            "visible_evidence_keys": sorted(load_json(PY_SECOND_PACKET / "materialized_preview.json").get("maintainer_visible_evidence", {}).keys()),
            "anti_cheat_status": load_json(PY_SECOND_PACKET / "anti_cheat_review_card.json").get("status"),
            "gold_status": load_json(PY_SECOND_PACKET / "expert_maintainer_rubric_review.json").get("status"),
            "admission_scope": "train_support_only",
            "residual_family": "python_verifier_outcome",
            "headline_eligible": False,
            "note": py_second["decision"],
            "missing_fields": [
                "singleton verifier-transition target instead of abstention-oriented support",
                "fresh strict-heldout verifier-transition evaluation row",
            ],
        },
        packet_status(
            RUST_LINUX_PACKET,
            bundle_file="fresh_rust_bundle_preview.json",
            admission_scope="train_support_only",
            residual_family="rust_evidence_citation",
            headline_eligible=False,
            note="linux rust root remains admitted support only",
            missing_fields=[
                "fresh heldout E/F evidence-role counterpart",
                "selected-test anchored non-overlap Rust evaluation root",
            ],
        ),
        packet_status(
            RUST_DATASETS_PACKET,
            bundle_file="fresh_rust_bundle_preview.json",
            admission_scope="train_support_only",
            residual_family="rust_evidence_citation",
            headline_eligible=False,
            note="candle-datasets remains the strongest admitted non-tokenizers Rust support root",
            missing_fields=[
                "fresh heldout E/F evidence-role counterpart",
                "second non-tokenizers anchored Rust evaluation root",
            ],
        ),
        {
            "bundle_id": "stage10413::candle::candle-flash-attn::rust",
            "packet_dir": rel(ARTIFACTS / "stage10883_flash_attn_alias_safe_successor_package"),
            "repo_id": "candle",
            "language_family": "rust",
            "selected_test_count": 1,
            "visible_evidence_keys": [
                "algorithmic_background_reference",
                "candidate_change_surface",
                "nearby_definition_or_usage_context",
                "symptom_or_call_path_analogue",
                "verifier_and_test_constraint",
            ],
            "anti_cheat_status": "completed",
            "gold_status": "completed",
            "admission_scope": "train_support_only",
            "residual_family": "rust_evidence_citation",
            "headline_eligible": False,
            "note": rust_flash["decision"],
            "missing_fields": [
                "strict-heldout replenishment root",
                "less abstention-heavy Rust evidence target",
            ],
        },
        {
            "bundle_id": "stage10885::tokenizers::bindings-node::rust",
            "packet_dir": rel(ARTIFACTS / "stage10885_tokenizers_bindings_node_preview"),
            "repo_id": "tokenizers",
            "language_family": "rust",
            "selected_test_count": 1,
            "visible_evidence_keys": [],
            "anti_cheat_status": "preview_only",
            "gold_status": "not_adjudicated",
            "admission_scope": "blocked",
            "residual_family": "rust_evidence_citation",
            "headline_eligible": False,
            "note": rust_bindings["decision"],
            "missing_fields": [
                "failure-specific verifier anchor",
                "localization-identifying call-path evidence",
                "heldout-grade human-identifiable singleton answer",
            ],
        },
    ]

    admitted = [row for row in roots if row["admission_scope"] == "train_support_only"]
    blocked = [row for row in roots if row["admission_scope"] != "train_support_only"]

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "current_residual_root_inventory_refreshed_after_python_and_rust_repairs",
        "headline_findings": [
            "The live residual support inventory is stronger than the old admission boundary showed: Python now has three train-support roots, and Rust has three admitted train-support roots plus one blocked heldout preview.",
            "The multilingual heldout frontier still does not move because none of these roots directly creates a fresh strict-heldout verifier-transition or Rust E/F evidence-role row.",
            "The postrun probe confirms the remaining blocker geometry exactly: one Python strict verifier miss and evidence-family misses below strict.",
        ],
        "counts": {
            "admitted_root_count": len(admitted),
            "blocked_root_count": len(blocked),
            "admitted_python": sum(1 for row in admitted if row["language_family"] == "python"),
            "admitted_rust": sum(1 for row in admitted if row["language_family"] == "rust"),
        },
        "heldout_frontier_context": {
            "strict_accuracy": postrun["metrics"]["postrun_strict_accuracy"],
            "strict_miss_count": postrun["metrics"]["strict_miss_count"],
            "strict_miss_rows": postrun["strict_misses"],
            "eval_miss_rows": postrun["eval_misses"],
        },
        "admitted_roots": admitted,
        "blocked_roots": blocked,
        "next_best_step": "Use this refreshed inventory to build the first fresh strict-heldout Python verifier-transition candidate queue, then build a separate Rust E/F heldout replenishment path instead of another preservation probe.",
        "source_artifacts": {
            "python_geometry_audit": rel(PY_GEOMETRY_AUDIT),
            "python_second_materialization": rel(PY_SECOND_JSON),
            "rust_flash_attn_successor": rel(RUST_FLASH_JSON),
            "rust_bindings_honesty": rel(RUST_BINDINGS_HONESTY),
            "postrun_audit": rel(POSTRUN_JSON),
        },
    }

    write_jsonl(ROOTS_JSONL, roots)
    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
