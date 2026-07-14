#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11058
NAME = "stage11058_explicit_ledger_conflict_materialization_request"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "explicit_ledger_conflict_materialization_request.json"
READY_ROWS_JSONL = OUT_DIR / "ready_request_rows.jsonl"
DISCOVERY_ROWS_JSONL = OUT_DIR / "source_discovery_rows.jsonl"

WORK_ITEMS_JSONL = ARTIFACTS / "stage11057_explicit_ledger_conflict_replenishment_request" / "work_items.jsonl"
PYTHON_ROOT_MANIFEST = ARTIFACTS / "stage10813_python_queue_aligned_admission" / "python_queue_aligned_root_manifest.jsonl"
SEED_QUEUE_JSONL = ARTIFACTS / "stage10763_multilingual_root_admission_seed_manifest" / "first_wave_materialization_queue.jsonl"
REVIEWED_ATLAS_JSON = ARTIFACTS / "stage10417_multilingual_reviewed_scaling_atlas" / "multilingual_reviewed_scaling_atlas.json"
EXPLICIT_LEDGER_ROWS = ARTIFACTS / "stage10938_explicit_verifier_ledger_strict_candidates" / "strict_candidate_rows.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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


def find_work_item(work_items: list[dict[str, Any]], target_family: str) -> dict[str, Any]:
    for item in work_items:
        if str(item.get("target_family") or "") == target_family:
            return item
    raise KeyError(f"missing work item for target_family={target_family}")


def review_entry_by_bundle(reviewed_bundles: list[dict[str, Any]], bundle_id: str) -> dict[str, Any]:
    for entry in reviewed_bundles:
        if str(entry.get("bundle_id") or "") == bundle_id:
            return entry
    raise KeyError(f"missing reviewed bundle {bundle_id}")


def root_entry_by_id(root_entries: list[dict[str, Any]], root_id: str) -> dict[str, Any]:
    for entry in root_entries:
        if str(entry.get("root_id") or "") == root_id:
            return entry
    raise KeyError(f"missing root entry {root_id}")


def seed_entry_by_root(seed_entries: list[dict[str, Any]], root_id: str) -> dict[str, Any]:
    for entry in seed_entries:
        if str(entry.get("root_id") or "") == root_id:
            return entry
    raise KeyError(f"missing seed entry {root_id}")


def strict_candidate_by_repo(strict_candidates: list[dict[str, Any]], repo_family: str) -> dict[str, Any]:
    for row in strict_candidates:
        if str(row.get("repo_family") or "") == repo_family:
            return row
    raise KeyError(f"missing strict candidate for repo_family={repo_family}")


def packet_ref_from_review(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_kind": "reviewed_bundle",
        "bundle_id": entry.get("bundle_id"),
        "repo_family": entry.get("repo_id"),
        "language_family": entry.get("language_family"),
        "packet_dir": entry.get("packet_dir"),
        "selected_tests_count": entry.get("selected_tests_count"),
        "visible_evidence_keys": list(entry.get("visible_evidence_keys") or []),
        "selected_tests": list(entry.get("selected_tests") or []),
    }


def packet_ref_from_root(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_kind": "reviewed_root_manifest",
        "root_id": entry.get("root_id"),
        "bundle_id": entry.get("bundle_id"),
        "repo_family": entry.get("repo_family"),
        "language_family": entry.get("language_family"),
        "packet_dir": entry.get("packet_dir"),
        "selected_tests_count": entry.get("selected_tests_count"),
        "visible_evidence_keys": list(entry.get("visible_evidence_keys") or []),
    }


def packet_ref_from_seed(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_kind": "seed_queue_root",
        "root_id": entry.get("root_id"),
        "repo_family": entry.get("repo_family"),
        "repo_id": entry.get("repo_id"),
        "language_family": entry.get("language_family"),
        "quality_tier": entry.get("quality_tier"),
        "source_family_id": entry.get("source_family_id"),
        "verifier_id": entry.get("verifier_id"),
    }


def candidate_ref(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_kind": "strict_candidate_row",
        "row_id": row.get("row_id"),
        "repo_family": row.get("repo_family"),
        "language_family": row.get("language_family"),
        "task_type": row.get("task_type"),
        "split_role": row.get("split_role"),
        "source_bundle_id": row.get("source_bundle_id"),
        "anti_cheat": dict(row.get("anti_cheat") or {}),
    }


def make_ready_row(
    work_item: dict[str, Any],
    packet_refs: list[dict[str, Any]],
    candidate_refs: list[dict[str, Any]],
    root_count_override: int | None = None,
    row_count_override: int | None = None,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    resolved_root_count = root_count_override if root_count_override is not None else len(packet_refs)
    resolved_row_count = row_count_override if row_count_override is not None else len(candidate_refs)
    required_roots = int(work_item.get("required_new_roots") or 0)
    required_rows = int(work_item.get("required_new_rows") or 0)
    return {
        "priority": work_item.get("priority"),
        "lane": work_item.get("lane"),
        "target_family": work_item.get("target_family"),
        "objective": work_item.get("objective"),
        "why_now": work_item.get("why_now"),
        "acceptance_requirements": list(work_item.get("acceptance_requirements") or []),
        "packet_refs": packet_refs,
        "candidate_refs": candidate_refs,
        "resolved_root_count": resolved_root_count,
        "resolved_row_count": resolved_row_count,
        "required_new_roots": required_roots,
        "required_new_rows": required_rows,
        "root_gap_remaining": max(0, required_roots - resolved_root_count),
        "row_gap_remaining": max(0, required_rows - resolved_row_count),
        "status": "partial_ready" if resolved_root_count < required_roots or resolved_row_count < required_rows else "ready_now",
        "notes": notes or [],
    }


def make_discovery_row(work_item: dict[str, Any], reason: str, recommended_sources: list[str]) -> dict[str, Any]:
    return {
        "priority": work_item.get("priority"),
        "lane": work_item.get("lane"),
        "target_family": work_item.get("target_family"),
        "objective": work_item.get("objective"),
        "required_new_roots": work_item.get("required_new_roots"),
        "required_new_rows": work_item.get("required_new_rows"),
        "reason": reason,
        "recommended_sources": recommended_sources,
        "acceptance_requirements": list(work_item.get("acceptance_requirements") or []),
        "evidence": list(work_item.get("evidence") or []),
    }


def main() -> None:
    work_items = load_jsonl(WORK_ITEMS_JSONL)
    python_root_manifest = load_jsonl(PYTHON_ROOT_MANIFEST)
    seed_queue = load_jsonl(SEED_QUEUE_JSONL)
    reviewed_atlas = load_json(REVIEWED_ATLAS_JSON)
    strict_candidates = load_jsonl(EXPLICIT_LEDGER_ROWS)

    reviewed_bundles = list(
        reviewed_atlas.get("admitted_bundle_rows")
        or reviewed_atlas.get("admitted_bundles")
        or []
    )

    ready_rows: list[dict[str, Any]] = []
    discovery_rows: list[dict[str, Any]] = []

    py_context = root_entry_by_id(
        python_root_manifest,
        "stage10236::localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_27t02_21_48_019bfd41_d2a6_7672_9873_81f8_src_code_assist_orchestrator_config_py_src_code_assist_orchestrator_context_pack_acd5ccc9c1_aug_1500000_8b46e7f662::python",
    )
    py_hf_local = root_entry_by_id(
        python_root_manifest,
        "stage10300::localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_26t23_27_57_019bfca2_aa35_7502_b929_649a_src_code_assist_agents_hf_local_py_src_code_assist_agents_hf_local_planner_py_sr_3fb1ce61a2_aug_1500000_8b46e7f662::python",
    )
    python_verifier_item = find_work_item(work_items, "code_assist_hf_local")
    ready_rows.append(
        make_ready_row(
            python_verifier_item,
            packet_refs=[packet_ref_from_root(py_context), packet_ref_from_root(py_hf_local)],
            candidate_refs=[],
            root_count_override=2,
            row_count_override=2,
            notes=[
                "Two fully reviewed code_assist roots are ready and already back the stage10894 and stage10900 verifier-transition strict candidates.",
                "This lane is source-real but still root-thin relative to the requested 8-root expansion target.",
            ],
        )
    )
    discovery_rows.append(
        make_discovery_row(
            python_verifier_item,
            reason="Only two reviewed code_assist verifier roots are bound today; six more independent verifier-transition roots are still needed.",
            recommended_sources=[
                rel(PYTHON_ROOT_MANIFEST),
                "runs/local/artifacts/stage10894_code_assist_python_verifier_transition_strict_candidate/strict_candidate_rows.jsonl",
                "runs/local/artifacts/stage10900_code_assist_hf_local_python_verifier_transition_strict_candidate/strict_candidate_rows.jsonl",
            ],
        )
    )

    agentkernel_review = review_entry_by_bundle(
        reviewed_bundles,
        "stage10119::localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_26t17_53_18_019d2b47_7d2d_7622_8e05_3513_agent_kernel_modeling_ssm_kernels_src_selective_scan_cpp_agent_kernel_modeling_w_5511e7fec6_aug_1500000_8b46e7f662::c_cpp",
    )
    agentkernel_candidate = strict_candidate_by_repo(strict_candidates, "agentkernel")
    agentkernel_item = find_work_item(work_items, "cpp_agentkernel_counterfamily")
    ready_rows.append(
        make_ready_row(
            agentkernel_item,
            packet_refs=[packet_ref_from_review(agentkernel_review)],
            candidate_refs=[candidate_ref(agentkernel_candidate)],
            root_count_override=1,
            row_count_override=1,
            notes=[
                "The reviewed stage10119 agentkernel C/C++ bundle is the correct counterfamily source and already has explicit selected tests.",
                "The stage10938 strict candidate provides one concrete explicit-ledger successor row, but additional independent C/C++ roots are still missing.",
            ],
        )
    )
    discovery_rows.append(
        make_discovery_row(
            agentkernel_item,
            reason="Only one reviewed agentkernel C/C++ bundle is currently bound; three more independent counterfamily roots are needed before this lane is honestly broad enough.",
            recommended_sources=[
                rel(REVIEWED_ATLAS_JSON),
                rel(EXPLICIT_LEDGER_ROWS),
                "runs/local/artifacts/stage10120_true_source_backed_maintainer_root_bundle_review_packets/review_packets",
            ],
        )
    )

    repo_lib_review_1 = review_entry_by_bundle(
        reviewed_bundles,
        "stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_26t00_55_44_019abda8_c0d8_7803_8a77_1e0f_scripts_universe_build_py_64d2cf209b_aug_1500000_8b46e7f662::python",
    )
    repo_lib_review_2 = review_entry_by_bundle(
        reviewed_bundles,
        "stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_28t20_02_25_019acc0f_4bd7_77f2_b15f_3b0c_models_mirrormind_init_py_models_mirrormind_context_py_models_mirrormind_coordin_fd8013631e_aug_1500000_8b46e7f662::python",
    )
    repo_lib_seed_1 = seed_entry_by_root(
        seed_queue,
        "audited::lcp_pack_1_10000000_localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_30t00_31_53_019d3c_7917fe7d0c::q48",
    )
    repo_lib_seed_2 = seed_entry_by_root(
        seed_queue,
        "audited::lcp_pack_1_5000000_localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_30t00_31_53_019d3c_a76597fc52::q18",
    )
    repo_lib_candidate = strict_candidate_by_repo(strict_candidates, "repository_library")
    repo_lib_item = find_work_item(work_items, "python_repository_library_reviewed_next")
    ready_rows.append(
        make_ready_row(
            repo_lib_item,
            packet_refs=[
                packet_ref_from_review(repo_lib_review_1),
                packet_ref_from_review(repo_lib_review_2),
                packet_ref_from_seed(repo_lib_seed_1),
                packet_ref_from_seed(repo_lib_seed_2),
            ],
            candidate_refs=[candidate_ref(repo_lib_candidate)],
            root_count_override=4,
            row_count_override=1,
            notes=[
                "This lane has the cleanest mixed supply: two reviewed repository_library bundles plus two audited long-context seeds.",
                "The root target is met, but explicit-ledger successor row count is still thin and should be expanded from fresh roots instead of replaying the same reviewed packets.",
            ],
        )
    )
    discovery_rows.append(
        make_discovery_row(
            repo_lib_item,
            reason="Root coverage is sufficient for immediate materialization, but the lane still needs more fresh explicit-ledger rows to reach the requested row count without same-surface reuse.",
            recommended_sources=[
                rel(SEED_QUEUE_JSONL),
                rel(REVIEWED_ATLAS_JSON),
                rel(EXPLICIT_LEDGER_ROWS),
            ],
        )
    )

    rust_item = find_work_item(work_items, "rust_non_tokenizers_non_alias")
    rust_seed_ids = [
        "audited::lcp_pack_1_10000000_localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_30t00_31_53_019d3c_7917fe7d0c::q14",
        "audited::lcp_pack_1_10000000_localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_30t00_31_53_019d3c_7917fe7d0c::q27",
        "audited::lcp_pack_1_10000000_localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_30t00_31_53_019d3c_7917fe7d0c::q43",
        "audited::lcp_pack_1_8500000_localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_30t00_31_53_019d3c_314d88e084::q14",
        "audited::lcp_pack_1_8500000_localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_30t00_31_53_019d3c_314d88e084::q32",
        "audited::lcp_pack_1_8500000_localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_30t00_31_53_019d3c_314d88e084::q53",
    ]
    ready_rows.append(
        make_ready_row(
            rust_item,
            packet_refs=[packet_ref_from_seed(seed_entry_by_root(seed_queue, root_id)) for root_id in rust_seed_ids],
            candidate_refs=[],
            root_count_override=6,
            row_count_override=0,
            notes=[
                "This lane now has enough distinct seed roots to start honest materialization outside tokenizers-only reuse.",
                "The six ready seeds span tokenizers, dbt-core, and chroma across two audited packs, which is materially better than replaying the quarantined tokenizers row.",
            ],
        )
    )
    discovery_rows.append(
        make_discovery_row(
            rust_item,
            reason="Seed-root coverage is sufficient, but no fresh explicit-ledger Rust successor rows are materialized yet.",
            recommended_sources=[
                rel(SEED_QUEUE_JSONL),
                rel(REVIEWED_ATLAS_JSON),
                "runs/local/artifacts/stage10127_true_source_backed_rust_review_packets_and_signoff/review_packets",
            ],
        )
    )

    parametergolf_review = review_entry_by_bundle(
        reviewed_bundles,
        "stage10119::localsess_parametergolf_sessseed_codex_sessions_rollout_2026_03_28t16_56_21_019d3560_1014_7761_9ea7_5638_parameter_golf_records_track_10min_16mb_2026_03_26_statespace_causalmachine_cuda_a018ca0b43_aug_1500000_8b46e7f662::c_cpp",
    )
    parametergolf_seed_ids = [
        "audited::lcp_pack_1_10000000_localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_30t00_31_53_019d3c_7917fe7d0c::q2",
        "audited::lcp_pack_1_10000000_localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_30t00_31_53_019d3c_7917fe7d0c::q45",
        "audited::lcp_pack_1_10000000_localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_30t00_31_53_019d3c_7917fe7d0c::q69",
    ]
    parametergolf_candidate = strict_candidate_by_repo(strict_candidates, "parametergolf")
    parametergolf_item = find_work_item(work_items, "parametergolf_verifier_transition")
    ready_rows.append(
        make_ready_row(
            parametergolf_item,
            packet_refs=[packet_ref_from_review(parametergolf_review)] + [packet_ref_from_seed(seed_entry_by_root(seed_queue, root_id)) for root_id in parametergolf_seed_ids],
            candidate_refs=[candidate_ref(parametergolf_candidate)],
            root_count_override=4,
            row_count_override=1,
            notes=[
                "The root target is already met here with one reviewed parametergolf bundle plus three audited seed roots.",
                "What remains is verifier-transition row materialization quality, not root discovery.",
            ],
        )
    )
    discovery_rows.append(
        make_discovery_row(
            parametergolf_item,
            reason="This lane is ready for direct materialization, but only one explicit-ledger successor row exists today.",
            recommended_sources=[
                rel(SEED_QUEUE_JSONL),
                rel(REVIEWED_ATLAS_JSON),
                rel(EXPLICIT_LEDGER_ROWS),
            ],
        )
    )

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "explicit_ledger_conflict_materialization_request_bound_to_real_supply",
        "claim_scope": [
            "Bind the abstract stage11057 replenishment request to real reviewed bundles, admitted roots, and audited seed roots already present in local artifacts.",
            "Separate lanes that are ready for immediate materialization from lanes that still require additional root discovery before they can be expanded honestly.",
        ],
        "source_artifacts": {
            "work_items": rel(WORK_ITEMS_JSONL),
            "python_root_manifest": rel(PYTHON_ROOT_MANIFEST),
            "seed_queue": rel(SEED_QUEUE_JSONL),
            "reviewed_atlas": rel(REVIEWED_ATLAS_JSON),
            "explicit_ledger_candidates": rel(EXPLICIT_LEDGER_ROWS),
        },
        "metrics": {
            "ready_request_count": len(ready_rows),
            "source_discovery_count": len(discovery_rows),
            "ready_now_count": sum(1 for row in ready_rows if row.get("status") == "ready_now"),
            "partial_ready_count": sum(1 for row in ready_rows if row.get("status") == "partial_ready"),
            "resolved_root_total": sum(int(row.get("resolved_root_count") or 0) for row in ready_rows),
            "resolved_row_total": sum(int(row.get("resolved_row_count") or 0) for row in ready_rows),
            "remaining_root_gap_total": sum(int(row.get("root_gap_remaining") or 0) for row in ready_rows),
            "remaining_row_gap_total": sum(int(row.get("row_gap_remaining") or 0) for row in ready_rows),
        },
        "headline_findings": [
            "Python repository_library, Rust seed-root replenishment, and C/C++ parametergolf verifier-transition all have enough real source supply to move from abstract request to executable materialization work.",
            "The agentkernel counterfamily and code_assist verifier-transition lanes are still root-thin: they have valid anchor packets, but not enough independent roots yet for an honest broad replenishment claim.",
            "This turns the current frontier from a vague queue into a concrete split between ready-now materialization work and source-discovery debt.",
        ],
        "next_best_step": [
            "Materialize fresh rows first for the ready-now lanes: repository_library, Rust non-tokenizers/non-alias, and parametergolf verifier-transition.",
            "In parallel, mine additional independent code_assist verifier-transition and agentkernel counterfamily roots before the next promotion-style probe.",
        ],
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "ready_request_rows_jsonl": rel(READY_ROWS_JSONL),
            "source_discovery_rows_jsonl": rel(DISCOVERY_ROWS_JSONL),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(READY_ROWS_JSONL, ready_rows)
    write_jsonl(DISCOVERY_ROWS_JSONL, discovery_rows)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
