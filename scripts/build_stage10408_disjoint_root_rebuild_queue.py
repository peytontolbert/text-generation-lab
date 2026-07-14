#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10408
NAME = "stage10408_disjoint_root_rebuild_queue"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
QUEUE = OUT_DIR / "disjoint_root_rebuild_queue.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

FRONTIER = ROOT / "runs/local/artifacts/stage10407_current_frontier_promotability_audit/current_frontier_promotability_audit.json"
PY_CPP_REVIEW_BASE = ROOT / "runs/local/artifacts/stage10120_true_source_backed_maintainer_root_bundle_review_packets/review_packets"
RUST_REVIEW_BASE = ROOT / "runs/local/artifacts/stage10127_true_source_backed_rust_review_packets_and_signoff/review_packets"
WEB_REPLENISHMENT = ROOT / "runs/local/artifacts/stage10176_code_assist_web_replenishment_bundle/code_assist_web_replenishment_bundle.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def review_status(base: Path) -> dict[str, Any]:
    rubric = load_json(base / "expert_maintainer_rubric_review.json")
    anti = load_json(base / "anti_cheat_review_card.json")
    gold = load_json(base / "perspective_gold_adjudication.json")
    return {
        "bundle_id": rubric.get("bundle_id") or anti.get("bundle_id") or gold.get("bundle_id"),
        "language_family": rubric.get("language_family") or anti.get("language_family") or gold.get("language_family"),
        "bundle_valid_for_eval": rubric.get("bundle_valid_for_eval"),
        "admissible_for_same_surface_comparison": anti.get("admissible_for_same_surface_comparison"),
        "gold_ready_for_eval": gold.get("bundle_gold_ready_for_eval"),
        "decision_rationale": rubric.get("decision_rationale") or anti.get("decision_rationale") or gold.get("decision_rationale"),
        "dir": base.name,
    }


def collect_reviews(base: Path) -> list[dict[str, Any]]:
    rows = []
    for d in sorted(p for p in base.iterdir() if p.is_dir()):
        rows.append(review_status(d))
    return rows


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)

    frontier = load_json(FRONTIER)
    py_cpp_rows = collect_reviews(PY_CPP_REVIEW_BASE)
    rust_rows = collect_reviews(RUST_REVIEW_BASE)
    web_bundle = load_json(WEB_REPLENISHMENT)

    admitted_bundle_ids = set()
    for family in ("python_extra_bundle", "c_cpp_extra_bundle", "rust_candle_nn_bundle", "rust_candle_examples_bundle", "web_replenishment_bundle"):
        bundle = ((frontier.get("refreshed_replenishment_inventory") or {}).get(family) or {})
        if bundle.get("bundle_id"):
            admitted_bundle_ids.add(bundle["bundle_id"])

    admitted_frontier_ids = {
        "stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_26t00_55_44_019abda8_c0d8_7803_8a77_1e0f_scripts_universe_build_py_64d2cf209b_aug_1500000_8b46e7f662::python",
        "stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_28t20_02_25_019acc0f_4bd7_77f2_b15f_3b0c_models_mirrormind_init_py_models_mirrormind_context_py_models_mirrormind_coordin_fd8013631e_aug_1500000_8b46e7f662::python",
        "stage10119::localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_26t17_53_18_019d2b47_7d2d_7622_8e05_3513_agent_kernel_modeling_ssm_kernels_src_selective_scan_cpp_agent_kernel_modeling_w_5511e7fec6_aug_1500000_8b46e7f662::c_cpp",
        "stage10119::localsess_parametergolf_sessseed_codex_sessions_rollout_2026_03_28t16_56_21_019d3560_1014_7761_9ea7_5638_parameter_golf_records_track_10min_16mb_2026_03_26_statespace_causalmachine_cuda_a018ca0b43_aug_1500000_8b46e7f662::c_cpp",
        "stage10126::candle::candle-core::rust",
        "stage10126::tokenizers::tokenizers::rust",
        "stage10119::localsess_bddy_website_sessseed_codex_sessions_rollout_2025_11_24t23_41_47_019ab83e_b023_7553_a34c_b93e_src_main_js_index_html_440e122a0f_aug_1500000_8b46e7f662::web_js_ts_html",
        "stage10119::localsess_bddy_website_sessseed_codex_sessions_rollout_2025_11_28t14_11_27_019acacd_f95c_7802_9bfe_7232_index_html_f0be60dc44_aug_1500000_8b46e7f662::web_js_ts_html",
    }

    py_extra_invalid = [
        row for row in py_cpp_rows
        if row["language_family"] == "python" and row["bundle_id"] not in admitted_frontier_ids and not row["bundle_valid_for_eval"]
    ]
    cpp_extra_invalid = [
        row for row in py_cpp_rows
        if row["language_family"] == "c_cpp" and row["bundle_id"] not in admitted_frontier_ids and not row["bundle_valid_for_eval"]
    ]
    rust_extra_invalid = [
        row for row in rust_rows
        if row["bundle_id"] not in admitted_frontier_ids and not row["bundle_valid_for_eval"]
    ]

    queue = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "depends_on": {
            "frontier_promotability_audit": display(FRONTIER),
        },
        "current_headline": {
            "same_frontier_hundred_m_accuracy": ((frontier.get("current_frontier") or {}).get("accuracy")),
            "same_frontier_gemma_accuracy": ((frontier.get("current_same_frontier_gemma_comparison") or {}).get("gemma_accuracy")),
            "same_frontier_delta": ((frontier.get("current_same_frontier_gemma_comparison") or {}).get("delta_hundred_m_minus_gemma")),
        },
        "disjoint_root_rebuild_priority": [
            {
                "language_family": "python",
                "status": "fresh_root_required",
                "why": "No extra valid non-frontier Python root exists in the reviewed inventory; the only extra Python bundle is completed-invalid.",
                "invalid_inventory_bundle_ids": [row["bundle_id"] for row in py_extra_invalid],
                "recommended_builder_shape": "fresh true-source-backed maintainer root with selected tests and explicit verifier/test-constraint evidence",
            },
            {
                "language_family": "c_cpp",
                "status": "fresh_root_required",
                "why": "No extra valid non-frontier C/C++ root exists in the reviewed inventory; all extra non-frontier C/C++ bundles are completed-invalid.",
                "invalid_inventory_bundle_ids": [row["bundle_id"] for row in cpp_extra_invalid],
                "recommended_builder_shape": "fresh true-source-backed maintainer root with separated implementation vs benchmark/script candidates and explicit verifier/test-constraint evidence",
            },
            {
                "language_family": "rust",
                "status": "fresh_root_required",
                "why": "Current extra reviewed Rust bundles are invalid; only the two current frontier Rust roots are admitted.",
                "invalid_inventory_bundle_ids": [row["bundle_id"] for row in rust_extra_invalid],
                "recommended_builder_shape": "fresh true-source-backed Rust root with selected tests or equally strong verifier anchors and a candidate set that avoids shortcut-prone example-only surfaces",
            },
            {
                "language_family": "web_js_ts_html",
                "status": "aux_support_available_but_second_pure_root_missing",
                "why": "A mixed-language code_assist web replenishment root is admitted and can support training, but it does not substitute for a second pure web maintainer root.",
                "admitted_aux_bundle_id": web_bundle.get("bundle_id"),
                "admitted_aux_claim_boundary": web_bundle.get("claim_boundary"),
                "recommended_builder_shape": "fresh web-focused root with concrete frontend/backend evidence and at least one selected verifier target, avoiding reliance on a Python-backend-only explanation",
            },
        ],
        "execution_queue": [
            {
                "stage_name_suggestion": "stage10409_fresh_python_disjoint_root_builder",
                "language_family": "python",
                "goal": "Create at least one new valid non-frontier Python maintainer root bundle that can support rebuilding the recovered citation/verifier gains.",
            },
            {
                "stage_name_suggestion": "stage10410_fresh_c_cpp_disjoint_root_builder",
                "language_family": "c_cpp",
                "goal": "Create at least one new valid non-frontier C/C++ maintainer root bundle that can support rebuilding the recovered citation gains.",
            },
            {
                "stage_name_suggestion": "stage10411_fresh_rust_disjoint_root_builder",
                "language_family": "rust",
                "goal": "Create at least one new valid non-frontier Rust maintainer root bundle beyond candle-core and tokenizers.",
            },
            {
                "stage_name_suggestion": "stage10412_pure_web_disjoint_root_builder",
                "language_family": "web_js_ts_html",
                "goal": "Create at least one pure web maintainer root bundle to supplement the admitted mixed-language code_assist web root.",
            },
        ],
        "claim_boundary": [
            "This queue does not itself prove a promotable win; it identifies the missing fresh roots required to rebuild the current same-frontier gains honestly.",
            "Any rebuilt result should retire same-surface diagnostic support rows from the claim path.",
        ],
    }

    QUEUE.write_text(json.dumps(queue, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(
        json.dumps(
            {
                "stage": STAGE,
                "passed": True,
                "artifact": display(QUEUE),
                "execution_queue": queue["execution_queue"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"stage": STAGE, "passed": True, "artifact": display(QUEUE)}, indent=2))


if __name__ == "__main__":
    main()
