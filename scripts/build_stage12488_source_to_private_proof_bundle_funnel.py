#!/usr/bin/env python3
"""Stage12488 source-to-private-proof-bundle funnel and expansion queue.

This stage is a public-safe control artifact. It quantifies how existing raw
source/adaptor inventories narrow into Stage12468-compatible private proof
bundle work items, then emits a prioritized expansion queue. It never trains,
admits, executes, hydrates, replays, or emits raw/private values.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12488_source_to_private_proof_bundle_funnel"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY_OUT = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12468 = "stage12468_non_bears_patch_effect_private_return_validator"

INPUT_JSON = {
    "stage12237": ROOT / "runs/summaries/stage12237_current_training_control_board.json",
    "stage12248": ROOT / "runs/summaries/stage12248_root_supply_discrepancy_audit.json",
    "stage12294": ROOT / "runs/summaries/stage12294_patch_task_source_adapter_atlas.json",
    "stage12406": ROOT / "runs/summaries/stage12406_transition_source_expansion_preflight.json",
    "stage12445": ROOT / "runs/summaries/stage12445_adapter_execution_return_ingest_and_level3_gate.json",
    "stage12449": ROOT / "runs/summaries/stage12449_external_repair_trace_fail_to_pass_projection.json",
    "stage12450": ROOT / "runs/summaries/stage12450_post_stage12449_level3_supply_control_board.json",
    "stage12453": ROOT / "runs/summaries/stage12453_direct_level3_source_hierarchy_and_next_lanes.json",
    "stage12459": ROOT / "runs/summaries/stage12459_external_comparable_patch_effect_source_preflight.json",
    "stage12468": ROOT / "runs/summaries/stage12468_non_bears_patch_effect_private_return_validator.json",
    "stage12469": ROOT / "runs/summaries/stage12469_non_bears_private_proof_return_work_order.json",
    "stage12472": ROOT / "runs/summaries/stage12472_locator_augmented_non_bears_work_order.json",
    "stage12482": ROOT / "runs/summaries/stage12482_external_repair_proof_source_suitability_audit.json",
    "stage12483": ROOT / "runs/summaries/stage12483_private_proof_bundle_acquisition_work_order.json",
    "stage12486": ROOT / "runs/summaries/stage12486_private_evidence_fill_work_order_validator.json",
    "stage12487": ROOT / "runs/summaries/stage12487_private_proof_bundle_fill_runner_skeleton.json",
}
INPUT_JSONL = {
    "stage12406_candidates": ROOT / "runs/local/artifacts/stage12406_transition_source_expansion_preflight/source_adapter_candidates.jsonl",
    "stage12459_lane_worklist": ROOT / "runs/local/artifacts/stage12459_external_comparable_patch_effect_source_preflight/public_lane_ref_worklist.jsonl",
    "stage12469_work_items": ROOT / "runs/local/artifacts/stage12469_non_bears_private_proof_return_work_order/private_return_work_items.jsonl",
    "stage12472_locator_augmented": ROOT / "runs/local/artifacts/stage12472_locator_augmented_non_bears_work_order/locator_augmented_work_items.jsonl",
    "stage12482_suitability": ROOT / "runs/local/artifacts/stage12482_external_repair_proof_source_suitability_audit/proof_source_suitability_records.jsonl",
    "stage12483_work_items": ROOT / "runs/local/artifacts/stage12483_private_proof_bundle_acquisition_work_order/private_proof_bundle_work_items_ref.jsonl",
    "stage12486_requirements": ROOT / "runs/local/artifacts/stage12486_private_evidence_fill_work_order_validator/private_evidence_row_requirements_ref.jsonl",
    "stage12487_checklist": ROOT / "runs/local/artifacts/stage12487_private_proof_bundle_fill_runner_skeleton/private_execution_checklist_rows_ref.jsonl",
}

FUNNEL_OUT = OUT_DIR / "source_to_private_proof_bundle_funnel.json"
QUEUE_OUT = OUT_DIR / "prioritized_private_proof_bundle_expansion_queue.jsonl"
COUNTERS_OUT = OUT_DIR / "funnel_counters.json"
GUARDRAIL_OUT = OUT_DIR / "guardrail_scan.json"
LOCAL_SUMMARY_OUT = OUT_DIR / "summary.json"

EXPECTED_STATUS_FAMILY = "external_comparable_fail_to_pass"
EXPECTED_GAP = 15
FALSE_GUARDS = {
    "training_allowed": False,
    "admission_allowed": False,
    "packaging_allowed": False,
    "execution_performed_by_stage": False,
    "hydration_performed_by_stage": False,
    "replay_performed_by_stage": False,
    "network_performed_by_stage": False,
}
ZERO_GUARDS = {
    "external_comparable_repair_credit_count": 0,
    "emitted_training_rows": 0,
    "sealed_eval_rows": 0,
}
FORBIDDEN_PUBLIC_KEYS = {
    "body",
    "cmd",
    "command",
    "commands",
    "commit",
    "commit_sha",
    "content",
    "diff",
    "file_content",
    "file_path",
    "patch",
    "patch_body",
    "path",
    "paths",
    "raw",
    "raw_content",
    "raw_text",
    "repo",
    "repo_id",
    "repo_name",
    "repository",
    "sha",
    "source",
    "source_text",
    "stderr",
    "stdout",
    "text",
    "uri",
    "uris",
    "url",
    "urls",
}
PUBLIC_SAFE_KEY_RE = re.compile(
    r"(hash|hashes|ref|refs|id|ids|stage|schema|slot|slots|status|family|"
    r"lane|guardrail|issue|reason|count|policy|allowed|proof|return|artifact|"
    r"locator|candidate|context|label|input|excluded|request|contract|pending|"
    r"file|work|order|bundle|inventory|category|credit|authority|queue|"
    r"funnel|class|classification|priority|rank|bucket|usable|support|"
    r"metadata|fixture|logistics|transition|verifier|repair|summary|target)",
    re.IGNORECASE,
)
RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:git clone|git apply|pytest\s|python -c|bash -|sh -|curl\s|"
    r"stdout|stderr|traceback|terminal output|command output)\b|"
    r"\b[0-9a-f]{40}\b",
    re.IGNORECASE | re.MULTILINE,
)


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:n]


def read_json(path: Path) -> tuple[dict[str, Any], Counter[str]]:
    issues: Counter[str] = Counter()
    if not path.exists():
        issues[f"{path.name}_missing"] += 1
        return {}, issues
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        issues[f"{path.name}_invalid_json"] += 1
        return {}, issues
    if not isinstance(value, dict):
        issues[f"{path.name}_not_object"] += 1
        return {}, issues
    return value, issues


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], Counter[str]]:
    rows: list[dict[str, Any]] = []
    issues: Counter[str] = Counter()
    if not path.exists():
        issues[f"{path.name}_missing"] += 1
        return rows, issues
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                issues["invalid_jsonl_row"] += 1
                continue
            if not isinstance(value, dict):
                issues["jsonl_row_not_object"] += 1
                continue
            value["_stage12488_input_line_no"] = line_no
            rows.append(value)
    return rows, issues


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def public_scan(value: Any, label: str = "stage12488") -> list[str]:
    issues: list[str] = []
    leaf = label.rsplit(".", 1)[-1].split("[", 1)[0].lower()
    if leaf in FORBIDDEN_PUBLIC_KEYS and not PUBLIC_SAFE_KEY_RE.search(label):
        issues.append(f"{label}:forbidden_public_key")
    if isinstance(value, str):
        if RAW_LEAK_RE.search(value):
            issues.append(f"{label}:raw_content_pattern:{stable_hash(value)}")
    elif isinstance(value, dict):
        for key, child in value.items():
            issues.extend(public_scan(child, f"{label}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            issues.extend(public_scan(child, f"{label}[{index}]"))
    return issues


def counter_dict(counter: Counter[str]) -> dict[str, int]:
    return dict(sorted(counter.items()))


def sum_nested_ints(value: dict[str, Any], keys: list[str]) -> int:
    total = 0
    for key in keys:
        candidate = value.get(key)
        if isinstance(candidate, int):
            total += candidate
    return total


def bucket_score(bucket: str | None) -> int:
    if bucket == "250-plus":
        return 250
    if bucket == "75-plus":
        return 75
    if bucket == "25-74":
        return 25
    if bucket == "10-24":
        return 10
    if bucket == "5-9":
        return 5
    if bucket == "2-4":
        return 2
    if bucket == "1":
        return 1
    return 0


def queue_item(
    *,
    rank: int,
    lane_class: str,
    lane_label: str,
    current_count: int,
    potential_count_bucket: str,
    target_use: str,
    source_stage_refs: list[str],
    required_action: str,
    blocker_codes: list[str],
    can_produce_stage12468_bundle: bool,
) -> dict[str, Any]:
    return {
        "record_type": "stage12488_prioritized_expansion_queue_item_v1",
        "queue_item_ref_hash": stable_hash(
            {
                "rank": rank,
                "lane_class": lane_class,
                "lane_label": lane_label,
                "current_count": current_count,
                "bucket": potential_count_bucket,
            }
        ),
        "rank": rank,
        "classification": lane_class,
        "lane_label": lane_label,
        "current_public_safe_item_count": current_count,
        "potential_candidate_count_bucket": potential_count_bucket,
        "target_use": target_use,
        "source_stage_refs": source_stage_refs,
        "required_next_action": required_action,
        "blocker_codes": blocker_codes,
        "can_produce_stage12468_compatible_private_proof_bundle_if_private_evidence_acquired": can_produce_stage12468_bundle,
        "target_validator_stage": STAGE12468,
        "requested_status_family": EXPECTED_STATUS_FAMILY,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
    }


def main() -> int:
    summaries: dict[str, dict[str, Any]] = {}
    json_issues: Counter[str] = Counter()
    for label, path in INPUT_JSON.items():
        summaries[label], issues = read_json(path)
        json_issues.update({f"{label}:{key}": count for key, count in issues.items()})

    rows: dict[str, list[dict[str, Any]]] = {}
    jsonl_issues: Counter[str] = Counter()
    for label, path in INPUT_JSONL.items():
        rows[label], issues = read_jsonl(path)
        jsonl_issues.update({f"{label}:{key}": count for key, count in issues.items()})

    source_family_counts = Counter(
        row.get("source_family", "unknown_or_missing") for row in rows["stage12406_candidates"]
    )
    source_tier_counts = Counter(
        row.get("candidate_proof_tier_now", row.get("proof_tier_candidate", "unknown_or_missing"))
        for row in rows["stage12406_candidates"]
    )
    supervision_counts = Counter(
        row.get("supervision_strength_now", "unknown_or_missing")
        for row in rows["stage12406_candidates"]
    )
    stage12469_language_counts = Counter(
        row.get("language_family_label", "unknown_or_missing")
        for row in rows["stage12469_work_items"]
    )
    stage12472_language_counts = Counter(
        row.get("language_family_label", "unknown_or_missing")
        for row in rows["stage12472_locator_augmented"]
    )
    stage12483_language_hash_counts = Counter(
        row.get("language_family_label_hash", "unknown_or_missing")
        for row in rows["stage12483_work_items"]
    )
    stage12482_suitability_counts = Counter(
        row.get("suitability", "unknown_or_missing")
        for row in rows["stage12482_suitability"]
    )

    stage12459_lanes = summaries["stage12459"].get("source_lane_inventory")
    if not isinstance(stage12459_lanes, list):
        stage12459_lanes = []
    can_hydrate_lanes = [
        lane for lane in stage12459_lanes
        if isinstance(lane, dict) and lane.get("can_satisfy_external_repair_credit_if_hydrated") is True
    ]
    rejected_lane_inventory = summaries["stage12459"].get("rejected_lane_inventory")
    if not isinstance(rejected_lane_inventory, list):
        rejected_lane_inventory = []

    stage12453_cards = summaries["stage12453"].get("source_cards")
    if not isinstance(stage12453_cards, list):
        stage12453_cards = []
    source_card_class_counts: Counter[str] = Counter()
    level3_transition_support_count = 0
    controlled_fixture_count = 0
    selected_test_verifier_observation_count = 0
    for card in stage12453_cards:
        if not isinstance(card, dict):
            continue
        stage_class = str(card.get("stage_class", "unknown_or_missing"))
        row_count = int(card.get("row_count", 0)) if isinstance(card.get("row_count"), int) else 0
        if "controlled" in stage_class:
            source_card_class_counts["controlled_fixtures"] += row_count
            controlled_fixture_count += row_count
        elif "normalized_verifier_observation" in stage_class or "verifier_observation_miner" in stage_class:
            source_card_class_counts["selected_test_verifier_observations"] += row_count
            selected_test_verifier_observation_count += row_count
        elif card.get("source_role") == "direct_priority":
            source_card_class_counts["level3_transition_support"] += row_count
            level3_transition_support_count += row_count
        else:
            source_card_class_counts["auxiliary_or_derivative"] += row_count

    stage12445_transition_support_count = int(
        summaries["stage12450"].get("stage12445_validated_level3_candidate_delta", 0)
    )
    selected_test_verifier_observation_count += int(
        summaries["stage12450"].get("selected_test_verifier_observation_validated_delta", 0)
    )
    controlled_fixture_count += int(
        summaries["stage12237"]
        .get("lane_control", {})
        .get("controlled_fixture_curriculum", {})
        .get("available_qc_projection_rows", 0)
    )

    root_supply_headline = summaries["stage12248"].get("headline", {})
    raw_events_seen = int(root_supply_headline.get("raw_session_events_seen_by_stage12200", 0))
    source_candidate_total = int(summaries["stage12406"].get("total_source_candidates", len(rows["stage12406_candidates"])))
    estimated_candidate_records_total = int(
        summaries["stage12406"].get("estimated_candidate_records_total", source_candidate_total)
    )
    stage12469_request_count = int(summaries["stage12469"].get("request_count", len(rows["stage12469_work_items"])))
    stage12472_locator_count = int(
        summaries["stage12472"].get("locator_augmented_work_item_count", len(rows["stage12472_locator_augmented"]))
    )
    stage12483_work_item_count = int(
        summaries["stage12483"].get("proof_bundle_work_item_count", len(rows["stage12483_work_items"]))
    )
    stage12486_requirement_count = int(
        summaries["stage12486"].get("row_requirement_count", len(rows["stage12486_requirements"]))
    )
    stage12487_checklist_count = int(
        summaries["stage12487"].get("checklist_row_count", len(rows["stage12487_checklist"]))
    )
    accepted_stage12468 = int(summaries["stage12468"].get("validator_complete_return_count", 0))

    comparable_fail_to_pass_current = {
        "stage12459_hydratable_lane_count": len(can_hydrate_lanes),
        "stage12469_private_return_request_count": stage12469_request_count,
        "stage12472_locator_augmented_actionable_count": stage12472_locator_count,
        "stage12483_private_proof_bundle_work_item_count": stage12483_work_item_count,
        "stage12486_private_evidence_requirement_count": stage12486_requirement_count,
        "stage12487_private_executor_checklist_count": stage12487_checklist_count,
        "stage12468_validator_complete_return_count": accepted_stage12468,
    }
    locator_only_count = stage12472_locator_count + int(
        summaries["stage12472"].get("blocked_work_item_count", 0)
    )
    unusable_metadata_count = sum_nested_ints(
        summaries["stage12406"].get("proof_tier_counts", {}),
        ["quarantine"],
    ) + sum(
        int(row.get("candidate_count", 0))
        for row in rows["stage12482_suitability"]
        if row.get("suitability") in {"not_suitable", "no_accepted_returns", "blocked_locator_sidecar_not_proof_bundle"}
        and isinstance(row.get("candidate_count", 0), int)
    )

    funnel = {
        "stage": STAGE,
        "record_type": "stage12488_source_to_private_proof_bundle_funnel_v1",
        "claim_boundary": "Public-safe funnel only. No training, admission, execution, hydration, replay, raw/private value emission, packaging, or repair credit.",
        "target_validator_stage": STAGE12468,
        "requested_status_family": EXPECTED_STATUS_FAMILY,
        "funnel_counts": {
            "raw_session_events_seen_by_stage12200": raw_events_seen,
            "estimated_candidate_records_total": estimated_candidate_records_total,
            "stage12406_source_adapter_candidate_count": source_candidate_total,
            "stage12459_public_lane_count": len(stage12459_lanes),
            "stage12459_hydratable_external_repair_lane_count": len(can_hydrate_lanes),
            "stage12469_private_return_request_count": stage12469_request_count,
            "stage12472_locator_augmented_actionable_count": stage12472_locator_count,
            "stage12483_private_proof_bundle_work_item_count": stage12483_work_item_count,
            "stage12486_private_evidence_requirement_count": stage12486_requirement_count,
            "stage12487_private_executor_checklist_count": stage12487_checklist_count,
            "stage12468_validator_complete_return_count": accepted_stage12468,
            "stage12468_external_repair_credit_count": 0,
            "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
        },
        "classification_counts": {
            "comparable_fail_to_pass_repair_proof": comparable_fail_to_pass_current,
            "level3_transition_support": {
                "stage12445_validated_level3_transition_support_count": stage12445_transition_support_count,
                "stage12453_direct_transition_support_count": level3_transition_support_count,
            },
            "selected_test_verifier_observations": {
                "selected_test_or_normalized_verifier_observation_count": selected_test_verifier_observation_count,
                "stage12450_selected_test_validated_delta": summaries["stage12450"].get(
                    "selected_test_verifier_observation_validated_delta", 0
                ),
            },
            "locator_only_logistics": {
                "stage12472_locator_or_blocked_locator_work_item_count": locator_only_count,
                "locator_augmented_actionable_count": stage12472_locator_count,
                "locator_blocked_count": summaries["stage12472"].get("blocked_work_item_count", 0),
            },
            "controlled_fixtures": {
                "controlled_fixture_or_curriculum_count": controlled_fixture_count,
            },
            "unusable_metadata": {
                "stage12406_quarantine_plus_stage12482_unsuitable_count": unusable_metadata_count,
                "stage12482_suitability_counts": counter_dict(stage12482_suitability_counts),
            },
        },
        "source_family_counts": counter_dict(source_family_counts),
        "source_proof_tier_counts": counter_dict(source_tier_counts),
        "source_supervision_strength_counts": counter_dict(supervision_counts),
        "stage12453_source_card_class_counts": counter_dict(source_card_class_counts),
        "stage12469_language_counts": counter_dict(stage12469_language_counts),
        "stage12472_language_counts": counter_dict(stage12472_language_counts),
        "stage12483_language_label_hash_counts": counter_dict(stage12483_language_hash_counts),
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }

    queue = [
        queue_item(
            rank=1,
            lane_class="comparable_fail_to_pass_repair_proof",
            lane_label="locator_augmented_trace_transition_private_bundle_fill",
            current_count=stage12472_locator_count,
            potential_count_bucket="5-9",
            target_use="produce_stage12468_compatible_private_return_candidates",
            source_stage_refs=[
                "stage12472_locator_augmented_non_bears_work_order",
                "stage12483_private_proof_bundle_acquisition_work_order",
                "stage12486_private_evidence_fill_work_order_validator",
                "stage12487_private_proof_bundle_fill_runner_skeleton",
            ],
            required_action="fill_real_private_proof_bundles_for_existing_locator_augmented_items_then_rerun_stage12485_and_stage12468",
            blocker_codes=["private_input_file_missing", "stage12481_missing_required_proof_slots"],
            can_produce_stage12468_bundle=True,
        ),
        queue_item(
            rank=2,
            lane_class="comparable_fail_to_pass_repair_proof",
            lane_label="stage12459_hydratable_external_repair_lanes",
            current_count=len(can_hydrate_lanes),
            potential_count_bucket="10-24",
            target_use="expand_private_proof_bundle_candidates_before_validation",
            source_stage_refs=[
                "stage12459_external_comparable_patch_effect_source_preflight",
                "stage12460_external_comparable_patch_effect_private_proof_slot_materialization_request",
                "stage12461_external_patch_effect_return_validator",
            ],
            required_action="materialize_private_proof_slots_only_for_lanes_marked_can_satisfy_external_repair_credit_if_hydrated",
            blocker_codes=["private_proof_slots_missing", "validator_complete_return_count_zero"],
            can_produce_stage12468_bundle=True,
        ),
        queue_item(
            rank=3,
            lane_class="comparable_fail_to_pass_repair_proof",
            lane_label="non_bears_private_return_request_backlog",
            current_count=stage12469_request_count,
            potential_count_bucket="10-24",
            target_use="recover_additional_locator_bindings_or_private_context_refs",
            source_stage_refs=[
                "stage12469_non_bears_private_proof_return_work_order",
                "stage12471_private_source_locator_index_preflight",
                "stage12472_locator_augmented_non_bears_work_order",
            ],
            required_action="expand_private_locator index coverage for the thirteen blocked request items without treating locators as proof",
            blocker_codes=["no_public_locator_ref_for_work_item", "locator_is_logistics_not_evidence"],
            can_produce_stage12468_bundle=True,
        ),
        queue_item(
            rank=4,
            lane_class="level3_transition_support",
            lane_label="direct_level3_transition_support_not_external_credit",
            current_count=stage12445_transition_support_count + level3_transition_support_count,
            potential_count_bucket="75-plus",
            target_use="support_transition_training_qc_only_not_external_repair_credit",
            source_stage_refs=[
                "stage12445_adapter_execution_return_ingest_and_level3_gate",
                "stage12453_direct_level3_source_hierarchy_and_next_lanes",
            ],
            required_action="keep as Level-3 transition support unless same-source fail-to-pass patch-effect proof is added",
            blocker_codes=["not_external_patch_effect_credit", "selected_or_transition_support_boundary"],
            can_produce_stage12468_bundle=False,
        ),
        queue_item(
            rank=5,
            lane_class="selected_test_verifier_observations",
            lane_label="selected_test_and_normalized_verifier_observation_support",
            current_count=selected_test_verifier_observation_count,
            potential_count_bucket="75-plus",
            target_use="verifier_status_auxiliary_or_join_candidate_only",
            source_stage_refs=[
                "stage12216_normalized_verifier_observation_dataset",
                "stage12450_post_stage12449_level3_supply_control_board",
                "stage12453_direct_level3_source_hierarchy_and_next_lanes",
                "stage12456_selected_test_return_proof_depth_audit",
            ],
            required_action="join only when same-source patch effect tuple exists; otherwise keep as verifier observation",
            blocker_codes=["selected_test_observation_without_patch_effect", "no_external_repair_credit"],
            can_produce_stage12468_bundle=False,
        ),
        queue_item(
            rank=6,
            lane_class="controlled_fixtures",
            lane_label="controlled_fixture_curriculum",
            current_count=controlled_fixture_count,
            potential_count_bucket="25-74",
            target_use="controlled_curriculum_or_protocol_smoke_only",
            source_stage_refs=[
                "stage12237_current_training_control_board",
                "stage12453_direct_level3_source_hierarchy_and_next_lanes",
            ],
            required_action="do not count toward external comparable repair floor",
            blocker_codes=["controlled_fixture_not_external_repair_proof"],
            can_produce_stage12468_bundle=False,
        ),
        queue_item(
            rank=7,
            lane_class="locator_only_logistics",
            lane_label="locator_sidecars_without_evidence",
            current_count=locator_only_count,
            potential_count_bucket="10-24",
            target_use="executor_logistics_only",
            source_stage_refs=[
                "stage12471_private_source_locator_index_preflight",
                "stage12472_locator_augmented_non_bears_work_order",
                "stage12481_private_return_materialization_attempt",
            ],
            required_action="use only to route private executor; require real proof slots before validator",
            blocker_codes=["locator_only_bundle_rejected", "not_proof"],
            can_produce_stage12468_bundle=False,
        ),
        queue_item(
            rank=8,
            lane_class="unusable_metadata",
            lane_label="metadata_only_or_unsuitable_sources",
            current_count=unusable_metadata_count,
            potential_count_bucket="250-plus",
            target_use="drop_atlas_or_retarget_only",
            source_stage_refs=[
                "stage12406_transition_source_expansion_preflight",
                "stage12482_external_repair_proof_source_suitability_audit",
            ],
            required_action="drop from repair-credit funnel unless new same-source before-fail after-pass proof is acquired",
            blocker_codes=["metadata_only", "quarantine", "not_stage12468_suitable"],
            can_produce_stage12468_bundle=False,
        ),
    ]
    queue.sort(
        key=lambda item: (
            not item["can_produce_stage12468_compatible_private_proof_bundle_if_private_evidence_acquired"],
            item["rank"],
            -bucket_score(item["potential_candidate_count_bucket"]),
        )
    )
    for index, item in enumerate(queue, 1):
        item["rank"] = index

    counters = {
        "stage": STAGE,
        "record_type": "stage12488_funnel_counters_v1",
        "json_input_issue_counts": counter_dict(json_issues),
        "jsonl_input_issue_counts": counter_dict(jsonl_issues),
        "raw_session_events_to_stage12406_candidate_ratio": {
            "numerator_stage12406_candidates": source_candidate_total,
            "denominator_raw_session_events": raw_events_seen,
        },
        "stage12406_to_stage12483_work_item_ratio": {
            "numerator_stage12483_work_items": stage12483_work_item_count,
            "denominator_stage12406_candidates": source_candidate_total,
        },
        "stage12483_to_stage12468_complete_ratio": {
            "numerator_stage12468_complete_returns": accepted_stage12468,
            "denominator_stage12483_work_items": stage12483_work_item_count,
        },
        "stage12468_gap": EXPECTED_GAP,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }

    summary = {
        "stage": STAGE,
        "record_type": "stage12488_source_to_private_proof_bundle_funnel_summary_v1",
        "decision": "prioritized_expansion_queue_ready_zero_credit_no_execution",
        "claim_boundary": "Quantifies public-safe source funnel and emits expansion queue only. It does not train, admit, execute, hydrate, replay, package, or emit raw/private values.",
        "target_validator_stage": STAGE12468,
        "source_stage_refs": list(INPUT_JSON.keys()) + list(INPUT_JSONL.keys()),
        "raw_session_events_seen_by_stage12200": raw_events_seen,
        "source_adapter_candidate_count": source_candidate_total,
        "estimated_candidate_records_total": estimated_candidate_records_total,
        "current_stage12468_compatible_private_proof_bundle_work_item_count": stage12483_work_item_count,
        "current_stage12468_validator_complete_return_count": accepted_stage12468,
        "stage12472_locator_augmented_actionable_count": stage12472_locator_count,
        "prioritized_queue_item_count": len(queue),
        "stage12468_capable_queue_item_count": sum(
            1 for item in queue
            if item["can_produce_stage12468_compatible_private_proof_bundle_if_private_evidence_acquired"]
        ),
        "classification_count_keys": list(funnel["classification_counts"].keys()),
        "next_execution_target": "run_stage12485_after_private_proof_bundle_evidence_rows_exist_or_execute_rank_1_private_bundle_fill_outside_public_stage",
        "next_public_stage_target": "stage12489_rank1_private_bundle_fill_postrun_or_stage12468_validator_rerun",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
        "artifact_refs": {
            "funnel": "stage12488_source_to_private_proof_bundle_funnel_json",
            "queue": "stage12488_prioritized_private_proof_bundle_expansion_queue_jsonl",
            "counters": "stage12488_funnel_counters_json",
            "guardrail_scan": "stage12488_guardrail_scan_json",
            "summary": "stage12488_summary_json",
        },
        "input_artifact_hashes": {
            **{label: file_hash(path) for label, path in INPUT_JSON.items()},
            **{label: file_hash(path) for label, path in INPUT_JSONL.items()},
        },
    }

    payload = {"summary": summary, "funnel": funnel, "queue": queue, "counters": counters}
    issues = public_scan(payload)
    guard = {
        "stage": STAGE,
        "record_type": "stage12488_guardrail_scan_v1",
        "scan_passed": not issues,
        "raw_leak_count": len(issues),
        "issue_hashes": [stable_hash(issue) for issue in issues[:50]],
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
    }
    if issues:
        summary["decision"] = "blocked_public_guardrail_scan_failed_zero_credit"
        queue = []
    summary["guardrail_scan_passed"] = guard["scan_passed"]
    summary["raw_leak_count"] = guard["raw_leak_count"]
    summary["schema_issue_count"] = sum(json_issues.values()) + sum(jsonl_issues.values())
    summary["summary_hash"] = stable_hash(
        {
            "decision": summary["decision"],
            "queue": len(queue),
            "work_items": stage12483_work_item_count,
            "complete": accepted_stage12468,
            "raw": guard["raw_leak_count"],
        }
    )

    write_json(FUNNEL_OUT, funnel)
    write_jsonl(QUEUE_OUT, queue)
    write_json(COUNTERS_OUT, counters)
    write_json(GUARDRAIL_OUT, guard)
    write_json(LOCAL_SUMMARY_OUT, summary)
    write_json(SUMMARY_OUT, summary)

    print(
        json.dumps(
            {
                "stage": STAGE,
                "decision": summary["decision"],
                "source_adapter_candidate_count": source_candidate_total,
                "stage12483_private_proof_bundle_work_item_count": stage12483_work_item_count,
                "stage12468_validator_complete_return_count": accepted_stage12468,
                "stage12468_capable_queue_item_count": summary["stage12468_capable_queue_item_count"],
                "prioritized_queue_item_count": len(queue),
                "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
                "guardrail_scan_passed": summary["guardrail_scan_passed"],
                "raw_leak_count": summary["raw_leak_count"],
                "training_allowed": False,
                "admission_allowed": False,
                "next_execution_target": summary["next_execution_target"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
