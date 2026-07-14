#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11634
NAME = "stage11634_routed_policy_freeze_and_anticheat"
OUT = ART / NAME
SUMMARY = OUT / "routed_policy_freeze_and_anticheat.json"
POLICY = OUT / "routed_product_scorer_policy.json"
ROUTE_CARD = OUT / "routed_product_scorer_route_card.jsonl"

STAGE11633 = ART / "stage11633_routed_product_scorer_audit/routed_product_scorer_audit.json"
SELECTED_RUNTIME = ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"
WEB_HEAD_RUNTIME = ART / "stage11625_web_fail_to_pass_stronger_head_overfit/runtime_model/runtime_model_bundle.json"
ROWSETS = {
    "web_heldout": ART / "stage11548_web_root_heldout_stage11507_score_audit/web_root_heldout_rows.jsonl",
    "web_successor_strict": ART / "stage11597_web_answerable_no_abstain_geometry_audit/web_answerable_no_abstain_successor_strict_rows.jsonl",
    "controlled_fail_to_pass_support": ART / "stage11621_web_fail_to_pass_row_geometry_repair/web_fail_to_pass_geometry_repaired_train_support.jsonl",
    "residual_bank": ART / "stage11442_targeted_residual_role_support_package/semantic_candidate_residual_bank.jsonl",
    "filtered_strict": ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_strict_eval.jsonl",
    "old_canary_strict": ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_strict_eval.jsonl",
    "filtered_validation": ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_validation.jsonl",
    "old_canary_validation": ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_validation.jsonl",
}

WEB_ROUTE_ROWSETS = {"web_heldout", "web_successor_strict", "controlled_fail_to_pass_support"}
PROTECTED_ROWSETS = {"residual_bank", "filtered_strict", "old_canary_strict", "filtered_validation", "old_canary_validation"}
FORBIDDEN_ROUTE_FIELDS = {
    "target",
    "target_text",
    "decoder_text",
    "bounded_choice_target_label",
    "semantic_target_value",
    "target_semantic_value",
    "semantic_target_role",
    "prediction",
    "predicted",
    "constrained_choice_top1_label",
    "full_vocab_top1_text",
}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def safe_metadata(rowset_name: str, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "rowset_name": rowset_name,
        "row_id": row.get("row_id"),
        "language_family": row.get("language_family"),
        "task_type": row.get("task_type"),
        "source_kind": row.get("source_kind"),
        "split_component": row.get("split_component"),
        "root_id": row.get("root_id"),
        "root_lineage_key": row.get("root_lineage_key"),
    }


def route_from_safe_metadata(meta: dict[str, Any]) -> dict[str, str]:
    rowset = str(meta.get("rowset_name") or "")
    if rowset in WEB_ROUTE_ROWSETS:
        return {
            "runtime_id": "stage11625_web_head",
            "runtime": rel(WEB_HEAD_RUNTIME),
            "scorer": "encoder_option_retrieval_web_task_candidate_head",
            "route_reason": "declared_web_rowset",
        }
    if rowset in PROTECTED_ROWSETS:
        return {
            "runtime_id": "stage11507_selected",
            "runtime": rel(SELECTED_RUNTIME),
            "scorer": "encoder_option_retrieval_evidence_judgment_head",
            "route_reason": "declared_protected_rowset",
        }
    return {
        "runtime_id": "unroutable",
        "runtime": "",
        "scorer": "",
        "route_reason": "unknown_rowset",
    }


def main() -> None:
    stage11633 = load_json(STAGE11633)
    route_rows: list[dict[str, Any]] = []
    route_counts: Counter[str] = Counter()
    blocked: list[dict[str, Any]] = []
    for rowset_name, path in ROWSETS.items():
        rows = load_jsonl(path)
        for row in rows:
            meta = safe_metadata(rowset_name, row)
            route = route_from_safe_metadata(meta)
            route_counts[route["runtime_id"]] += 1
            row_forbidden_present = sorted(key for key in FORBIDDEN_ROUTE_FIELDS if key in meta)
            original_forbidden_present = sorted(key for key in FORBIDDEN_ROUTE_FIELDS if key in row)
            card = {
                **meta,
                **route,
                "route_used_fields": ["rowset_name"],
                "forbidden_fields_present_in_route_metadata": row_forbidden_present,
                "forbidden_fields_present_in_original_row": original_forbidden_present,
                "anti_cheat_note": "Original rows may contain gold fields for scoring; route metadata excludes them.",
            }
            if route["runtime_id"] == "unroutable" or row_forbidden_present:
                blocked.append(card)
            route_rows.append(card)

    policy = {
        "policy_id": "stage11634_routed_product_scorer_policy_v1",
        "created_at_utc": now(),
        "routes": [
            {
                "match": {"rowset_name_in": sorted(WEB_ROUTE_ROWSETS)},
                "runtime_id": "stage11625_web_head",
                "runtime": rel(WEB_HEAD_RUNTIME),
                "scorer": "encoder_option_retrieval_web_task_candidate_head",
            },
            {
                "match": {"rowset_name_in": sorted(PROTECTED_ROWSETS)},
                "runtime_id": "stage11507_selected",
                "runtime": rel(SELECTED_RUNTIME),
                "scorer": "encoder_option_retrieval_evidence_judgment_head",
            },
        ],
        "allowed_route_fields": ["rowset_name"],
        "forbidden_route_fields": sorted(FORBIDDEN_ROUTE_FIELDS),
        "claim_boundary": [
            "This routing policy is for product/harness scorer composition, not a standalone model-weight claim.",
            "Routing is based only on declared rowset membership supplied by the evaluation harness.",
            "The routing policy must be frozen before same-manifest comparator execution.",
        ],
    }
    gates = {
        "stage11633_passed_internal_gates": stage11633.get("decision") == "routed_product_scorer_candidate_passes_internal_gates",
        "all_rows_routed": not blocked,
        "route_metadata_excludes_forbidden_fields": all(not row["forbidden_fields_present_in_route_metadata"] for row in route_rows),
        "has_web_route": route_counts.get("stage11625_web_head", 0) > 0,
        "has_protected_route": route_counts.get("stage11507_selected", 0) > 0,
        "routing_uses_only_rowset_name": all(row["route_used_fields"] == ["rowset_name"] for row in route_rows),
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "routed_policy_frozen_anticheat_passed" if all(gates.values()) else "routed_policy_blocked",
        "gates": gates,
        "route_counts": dict(route_counts),
        "blocked_rows": blocked[:20],
        "blocked_row_count": len(blocked),
        "policy": rel(POLICY),
        "route_card": rel(ROUTE_CARD),
        "source_artifacts": {
            "stage11633": rel(STAGE11633),
            "selected_runtime": rel(SELECTED_RUNTIME),
            "web_head_runtime": rel(WEB_HEAD_RUNTIME),
            **{f"rowset_{name}": rel(path) for name, path in ROWSETS.items()},
        },
        "outputs": {"summary": rel(SUMMARY), "policy": rel(POLICY), "route_card": rel(ROUTE_CARD)},
        "claim_boundary": policy["claim_boundary"],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(POLICY, policy)
    write_jsonl(ROUTE_CARD, route_rows)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "gates": gates, "route_counts": dict(route_counts), "blocked_row_count": len(blocked)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
