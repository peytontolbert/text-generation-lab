#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10834
NAME = "stage10834_residual_expansion_execution_packet"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "residual_expansion_execution_packet.json"
OUT_JSONL = OUT_DIR / "residual_expansion_targets.jsonl"

SUPPLY = ARTIFACTS / "stage10822_residual_lane_fresh_root_supply_manifest" / "residual_lane_fresh_root_supply_manifest.json"
SUPPLY_TARGETS = ARTIFACTS / "stage10822_residual_lane_fresh_root_supply_manifest" / "residual_lane_fresh_root_targets.jsonl"
SCORER_AUDIT = ARTIFACTS / "stage10830_evidence_role_probe_audit" / "evidence_role_probe_audit.json"
OPTION_REMAP_AUDIT = ARTIFACTS / "stage10832_current_runtime_option_value_remap_audit" / "current_runtime_option_value_remap_audit.json"
OPTION_SOURCE_AUDIT = ARTIFACTS / "stage10833_current_option_source_comparison_audit" / "current_option_source_comparison_audit.json"
PYTHON_REBUILD = ARTIFACTS / "stage10496_hf_local_verifier_geometry_rebuild_request" / "hf_local_verifier_geometry_rebuild_request.json"
RUST_BUILDER = ARTIFACTS / "stage10441_rust_evidence_citation_fresh_builder_request" / "rust_evidence_citation_fresh_builder_request.json"
PYTHON_PACKET = ARTIFACTS / "stage10493_python_verifier_fresh_review_packet_builder" / "python_verifier_fresh_review_packet_builder.json"


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


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    supply = load_json(SUPPLY)
    supply_targets = load_jsonl(SUPPLY_TARGETS)
    scorer_audit = load_json(SCORER_AUDIT)
    option_remap = load_json(OPTION_REMAP_AUDIT)
    option_source = load_json(OPTION_SOURCE_AUDIT)
    python_rebuild = load_json(PYTHON_REBUILD)
    rust_builder = load_json(RUST_BUILDER)
    python_packet = load_json(PYTHON_PACKET)

    python_targets = [
        row for row in supply_targets
        if row.get("lane") == "python_verifier_outcome"
    ]
    rust_targets = [
        row for row in supply_targets
        if row.get("lane") == "rust_evidence_citation"
    ]
    selected_rust_targets = [
        row for row in rust_targets
        if row.get("candidate_root_id") in {"tokenizers::bindings/node", "linux::rust", "candle::candle-transformers"}
    ]
    selected_rust_targets.sort(key=lambda row: (0 if row.get("candidate_root_id") == "tokenizers::bindings/node" else 1, -int(row.get("priority_score", 0))))

    packet_targets: list[dict[str, Any]] = []
    for row in python_targets:
        packet_targets.append(
            {
                "lane": "python_verifier_outcome",
                "priority": row.get("priority_order"),
                "root_id": row.get("candidate_root_id"),
                "repo_id": row.get("repo_id"),
                "status": row.get("status"),
                "usable_now_for_promotable_support": row.get("usable_now_for_promotable_support"),
                "selected_test_count": row.get("selected_test_count"),
                "executable_verifier_row_count": row.get("executable_verifier_row_count"),
                "gaps": row.get("gaps", []),
                "next_action": (
                    "package_as_train_support_now"
                    if row.get("usable_now_for_promotable_support")
                    else "rebuild_geometry_or_materialize_more"
                ),
            }
        )
    for row in selected_rust_targets:
        packet_targets.append(
            {
                "lane": "rust_evidence_citation",
                "priority": row.get("priority_score"),
                "root_id": row.get("candidate_root_id"),
                "repo_id": row.get("repo_id"),
                "status": row.get("status"),
                "review_ready_for_bundle_construction": row.get("status") == "review_ready_but_needs_anchor",
                "competition_geometries": row.get("competition_geometries", []),
                "required_builder_delta": row.get("required_builder_delta", []),
                "next_action": "materialize_anchor_and_review_packet",
            }
        )

    role_map_eval = ((option_remap.get("results") or {}).get("role_map_templated") or {})
    conditioned_eval = ((option_source.get("results") or {}).get("encoder_option_retrieval_conditioned") or {})
    raw_eval = ((option_remap.get("results") or {}).get("raw") or {})

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "residual_expansion_execution_packet_ready",
        "claim_scope": [
            "Freeze the latest negative scorer-audit evidence and convert the next honest v2.7 progress step into a concrete Python-plus-Rust residual expansion packet.",
            "Prioritize fresh-root geometry and anchor materialization over unsafe scorer hotfixes.",
            "Keep anti-cheat and promotion boundaries explicit so support expansion does not get misreported as a fresh multilingual win.",
        ],
        "current_frontier": {
            "strict_exact": ((scorer_audit.get("headline") or {}).get("new_strict_exact")),
            "eval_exact": ((scorer_audit.get("headline") or {}).get("new_eval_exact")),
            "strict_miss_set_unchanged": ((scorer_audit.get("headline") or {}).get("strict_miss_set_unchanged")),
            "strict_misses": ((scorer_audit.get("new_strict_eval") or {}).get("misses")),
        },
        "scorer_hotfix_audit": {
            "status": "exhausted_for_now",
            "raw_strict_exact": (((raw_eval.get("strict_eval") or {}).get("constrained_choice_top1_accuracy"))),
            "role_map_templated_strict_exact": (((role_map_eval.get("strict_eval") or {}).get("constrained_choice_top1_accuracy"))),
            "conditioned_option_retrieval_strict_exact": (((conditioned_eval.get("strict_eval") or {}).get("constrained_choice_top1_accuracy"))),
            "reason_not_to_patch": [
                "Role-map option remapping improved some eval evidence rows but collapsed strict evidence_citation to 0/4.",
                "Conditioned option retrieval catastrophically regressed the frontier and is not a safe scorer replacement.",
                "Task-role templating and dynamic productized remaps were effectively no-ops on the current stage10829 runtime.",
            ],
            "required_next_kind_of_fix": "fresh_root_data_and_deeper_retrieval_interface_work",
        },
        "python_lane": {
            "ready_now_support_root": supply["python_lane"]["immediately_qualified_reviewed_roots"],
            "ready_now_support_row_count": python_packet["summary"]["qualified_support_row_count"],
            "rebuild_required_root": python_rebuild["current_hf_local_status"]["bundle_id"],
            "rebuild_requirements": python_rebuild["rebuild_requirements"],
            "anti_cheat_gates": python_rebuild["anti_cheat_gates"]["new_required_checks"],
            "packet_decision": "use_stage10236_as_support_only_and_rebuild_hf_local_multitest_geometry",
        },
        "rust_lane": {
            "support_only_root": supply["rust_lane"]["support_only_reviewed_root"],
            "selected_builder_targets": [row["candidate_root_id"] for row in selected_rust_targets],
            "builder_success_condition": rust_builder["success_condition"],
            "builder_requirements": rust_builder["builder_requirements"],
            "packet_decision": "materialize_non_tokenizers_or_bindings_root_with_anchor_before_next_promotable_rust_claim",
        },
        "anti_cheat_and_promotion_gates": [
            "No same-root replay from the current strict overlay into train.",
            "No prompt may expose target path, gold test path, or gold support fact verbatim before the candidate set.",
            "Python verifier packets must have at least three plausible selected-test targets and pass prompt-target leak audit.",
            "Rust evidence packets must keep candidate_change_surface as a tempting visible negative while the gold support fact remains distinct from verifier_and_test_constraint.",
            "Every fresh root needs rubric, anti-cheat, and gold perspective review before scoring.",
            "Any promotion run must beat the current 22/24 canary with zero regressions.",
        ],
        "next_executable_work": [
            "Build the hf_local multitest verifier packet successor required by stage10496.",
            "Materialize review packets for tokenizers::bindings/node, linux::rust, and candle::candle-transformers with concrete verifier or selected-test anchors.",
            "Use stage10236 Python context-pack rows and flash-attn Rust rows only as train support in the next multilingual package.",
        ],
        "sources": {
            "fresh_root_supply_manifest": rel(SUPPLY),
            "fresh_root_targets": rel(SUPPLY_TARGETS),
            "latest_scorer_probe_audit": rel(SCORER_AUDIT),
            "option_remap_audit": rel(OPTION_REMAP_AUDIT),
            "option_source_audit": rel(OPTION_SOURCE_AUDIT),
            "python_rebuild_request": rel(PYTHON_REBUILD),
            "rust_builder_request": rel(RUST_BUILDER),
            "python_packet_audit": rel(PYTHON_PACKET),
        },
    }

    write_json(OUT_JSON, payload)
    write_jsonl(OUT_JSONL, packet_targets)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
