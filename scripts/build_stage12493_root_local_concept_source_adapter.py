#!/usr/bin/env python3
"""Root-local source adapter queue for Stage12492 concept work items.

Stage12493 binds reviewed concept materialization work items to safe candidate
source records. It does not admit training rows. It deliberately fails closed
until a later materializer supplies root-local state, independent labels,
candidate actions, and anti-shortcut review.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12493_root_local_concept_source_adapter"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12492 = "stage12492_root_local_concept_materialization_queue"
WORK_ITEMS = ROOT / "runs/local/artifacts" / STAGE12492 / "root_local_concept_materialization_work_items.jsonl"
STAGE12492_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12492}.json"

STAGE12295_LEDGER = ROOT / "runs/local/artifacts/stage12295_transition_function_ledger/transition_function_ledger.jsonl"
STAGE12205_RECORDS = (
    ROOT
    / "runs/local/artifacts/stage12205_authoritative_verifier_log_level3_joiner/"
    "authoritative_level3_episode_records.jsonl"
)
STAGE12210_RECORDS = (
    ROOT
    / "runs/local/artifacts/stage12210_controlled_triple_level3_joiner/"
    "controlled_triple_level3_records.jsonl"
)
STAGE12320_ROWS = (
    ROOT
    / "runs/local/artifacts/stage12320_event_local_semantic_review_admission/"
    "event_local_observation_train_support_admitted_rows.jsonl"
)
STAGE12441_REPS = (
    ROOT
    / "runs/local/artifacts/stage12441_embedding_transition_candidate_expansion_gate/"
    "candidate_embedding_representative_priority_records.jsonl"
)
STAGE12416_ROWS = (
    ROOT
    / "runs/local/artifacts/stage12416_direct_verifier_log_train_support_canonicalizer/"
    "direct_verifier_log_train_support_rows.jsonl"
)
STAGE12417_ROWS = (
    ROOT
    / "runs/local/artifacts/stage12417_combined_train_support_ledger_v16/"
    "combined_train_support_rows_v16.jsonl"
)

LANGUAGE_FAMILIES = ["python", "rust", "c_cpp", "web_js_ts_html"]
ROOTS_PER_WORK_ITEM = 8
MAX_PER_SOURCE_FAMILY = 4
GLOBAL_SOURCE_FAMILY_CAP = 8

RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:git clone|git apply|pytest\s|python -c|bash -|sh -|curl\s|"
    r"stdout|stderr|traceback|terminal output|command output)\b|"
    r"\b[0-9a-f]{40}\b",
    re.IGNORECASE | re.MULTILINE,
)

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
    "training_rows_emitted": 0,
    "admitted_rows": 0,
    "reviewed_train_support_rows": 0,
    "proof_grade_repair_rows": 0,
    "external_repair_credit_count": 0,
    "sealed_eval_rows": 0,
}

UNRESOLVED_FIELDS = [
    "state_before_codes",
    "candidate_action_set_hash",
    "independent_policy_label_hash",
    "state_delta_codes",
    "stop_continue_label_hash",
    "renderer_contract_hash",
    "anti_shortcut_audit_hash",
]


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def scan(value: Any) -> list[str]:
    issues: list[str] = []
    if isinstance(value, str):
        if RAW_LEAK_RE.search(value):
            issues.append(stable_hash(value))
    elif isinstance(value, dict):
        for child in value.values():
            issues.extend(scan(child))
    elif isinstance(value, list):
        for child in value:
            issues.extend(scan(child))
    return issues


def normalize_language(value: Any, fallback_index: int) -> str:
    text = str(value or "").lower()
    if text in LANGUAGE_FAMILIES:
        return text
    if "rust" in text:
        return "rust"
    if "web" in text or "js" in text or "ts" in text:
        return "web_js_ts_html"
    if "c_cpp" in text or "cpp" in text or "c++" in text:
        return "c_cpp"
    if "python" in text or "py" in text:
        return "python"
    return LANGUAGE_FAMILIES[fallback_index % len(LANGUAGE_FAMILIES)]


def source_family_hash(row: dict[str, Any]) -> str:
    if row.get("repo_family_hash"):
        return str(row["repo_family_hash"])
    refs = row.get("source_refs") if isinstance(row.get("source_refs"), dict) else {}
    if refs.get("source_file_hash_compat"):
        return stable_hash({"source_file": refs["source_file_hash_compat"]})
    if refs.get("chat_id_hash"):
        return stable_hash({"chat": refs["chat_id_hash"]})
    lineage = row.get("lineage") if isinstance(row.get("lineage"), dict) else {}
    if lineage.get("root_lineage_key"):
        return stable_hash({"lineage": lineage["root_lineage_key"]})
    return stable_hash(row)


def root_lineage_hash(row: dict[str, Any]) -> str:
    if row.get("root_lineage_key_hash"):
        return str(row["root_lineage_key_hash"])
    lineage = row.get("lineage") if isinstance(row.get("lineage"), dict) else {}
    if lineage.get("root_lineage_key"):
        return stable_hash({"root_lineage": lineage["root_lineage_key"]})
    refs = row.get("source_refs") if isinstance(row.get("source_refs"), dict) else {}
    if refs.get("task_window_id"):
        return stable_hash({"task_window": refs["task_window_id"]})
    return stable_hash({"row": row.get("row_id") or row.get("transition_id") or row})


def candidate_id(row: dict[str, Any]) -> str:
    return str(row.get("row_id") or row.get("transition_id") or row.get("candidate_id_hash") or stable_hash(row))



def adapt_stage12205(row: dict[str, Any], index: int) -> dict[str, Any]:
    action_set = row.get("candidate_action_set") if isinstance(row.get("candidate_action_set"), dict) else {}
    state_update = row.get("state_update") if isinstance(row.get("state_update"), dict) else {}
    stop_decision = row.get("stop_decision") if isinstance(row.get("stop_decision"), dict) else {}
    observation = row.get("observation") if isinstance(row.get("observation"), dict) else {}
    command_result = row.get("command_result") if isinstance(row.get("command_result"), dict) else {}
    projection_permissions = row.get("projection_permissions") if isinstance(row.get("projection_permissions"), list) else []
    task_family = "transition_verifier_transition"
    if "transition_next_action" in projection_permissions:
        task_family = "transition_next_action"
    return {
        "source_stage": "stage12205_authoritative_verifier_log_level3_joiner",
        "source_record_ref_hash": stable_hash({"stage": "stage12205", "id": candidate_id(row)}),
        "source_record_kind": "direct_authoritative_verifier_observation_source",
        "language_family": normalize_language(row.get("language"), index),
        "task_family": task_family,
        "source_family_hash": stable_hash({"repo_family": row.get("repo_family"), "source_stage": row.get("source_stage")}),
        "root_lineage_key_hash": stable_hash({"root_id": row.get("root_id"), "episode_id": row.get("episode_id")}),
        "transition_function_key_hash": stable_hash(
            {
                "verifier_transition": row.get("verifier_transition"),
                "state_update_type": state_update.get("state_update_type"),
                "stop": stop_decision.get("continue_or_stop"),
                "task_family": task_family,
            }
        ),
        "candidate_action_set_hash": stable_hash(action_set),
        "state_before_ref_hash": stable_hash(action_set.get("state_id") or row.get("episode_id") or candidate_id(row)),
        "observation_ref_hash": stable_hash(
            {
                "command_result_id": command_result.get("command_result_id"),
                "observation_id": observation.get("observation_id"),
                "verifier_status": row.get("verifier_status"),
                "verifier_transition": row.get("verifier_transition"),
            }
        ),
        "source_limitations": [
            "direct_verifier_observation_not_reexecuted_here",
            "observed_action_candidate_present_requires_independent_policy_review",
            "train_support_only_not_strict_eval",
        ],
    }


def adapt_stage12210(row: dict[str, Any], index: int) -> dict[str, Any]:
    adapted = adapt_stage12205(row, index)
    adapted.update(
        {
            "source_stage": "stage12210_controlled_triple_level3_joiner",
            "source_record_ref_hash": stable_hash({"stage": "stage12210", "id": candidate_id(row)}),
            "source_record_kind": "controlled_triple_fail_to_pass_source",
            "source_limitations": [
                "controlled_fixture_not_external_repair_credit",
                "observed_action_candidate_present_requires_independent_policy_review",
                "semantic_mutation_depth_review_required",
            ],
        }
    )
    return adapted

def adapt_stage12295(row: dict[str, Any], index: int) -> dict[str, Any]:
    families = row.get("task_family_candidates") if isinstance(row.get("task_family_candidates"), list) else []
    task_family = str(families[0] if families else "transition_next_action")
    return {
        "source_stage": "stage12295_transition_function_ledger",
        "source_record_ref_hash": stable_hash({"stage": "stage12295", "id": candidate_id(row)}),
        "source_record_kind": "paired_action_observation_weak_policy_source",
        "language_family": normalize_language(row.get("language_family"), index),
        "task_family": task_family,
        "source_family_hash": source_family_hash(row),
        "root_lineage_key_hash": root_lineage_hash(row),
        "transition_function_key_hash": stable_hash({"task_family": task_family, "source": candidate_id(row)}),
        "candidate_action_set_hash": row.get("candidate_action_set_hash"),
        "state_before_ref_hash": stable_hash(row.get("state_before_ref") or candidate_id(row)),
        "observation_ref_hash": stable_hash(row.get("observation_ref") or candidate_id(row)),
        "source_limitations": [
            "observed_action_imitation_risk",
            "policy_label_not_independent",
            "state_delta_not_materialized",
        ],
    }


def adapt_stage12320(row: dict[str, Any], index: int) -> dict[str, Any]:
    target = row.get("target_only") if isinstance(row.get("target_only"), dict) else {}
    return {
        "source_stage": "stage12320_event_local_semantic_review_admission",
        "source_record_ref_hash": stable_hash({"stage": "stage12320", "id": candidate_id(row)}),
        "source_record_kind": "event_local_observation_status_source",
        "language_family": normalize_language(row.get("language_family"), index),
        "task_family": str(row.get("task_family") or "event_local_transition_observation"),
        "source_family_hash": source_family_hash(row),
        "root_lineage_key_hash": root_lineage_hash(row),
        "transition_function_key_hash": stable_hash(target.get("transition_function_key") or candidate_id(row)),
        "candidate_action_set_hash": stable_hash(row.get("model_input_view", {}).get("candidate_action_set", {})),
        "state_before_ref_hash": stable_hash(row.get("model_input_view", {}).get("state_before_summary_codes", [])),
        "observation_ref_hash": stable_hash(
            {
                "patch_apply_status": target.get("patch_apply_status"),
                "verifier_status_class": target.get("verifier_status_class"),
                "semantic_rule_id": target.get("semantic_rule_id"),
            }
        ),
        "source_limitations": [
            "target_hidden_observation_only",
            "not_next_action_policy",
            "not_patch_trace_repair_proof",
        ],
    }



def adapt_stage12416(row: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "source_stage": "stage12416_direct_verifier_log_train_support_canonicalizer",
        "source_record_ref_hash": stable_hash({"stage": "stage12416", "id": candidate_id(row)}),
        "source_record_kind": "direct_verifier_log_bounded_train_support_source",
        "language_family": normalize_language(row.get("language_family"), index),
        "task_family": str(row.get("task_projection") or "transition_verifier_transition"),
        "source_family_hash": stable_hash({"repo_family_hash": row.get("repo_family_hash"), "source_stage": row.get("source_stage")}),
        "root_lineage_key_hash": str(row.get("root_lineage_key_hash") or stable_hash(row.get("root_id"))),
        "transition_function_key_hash": stable_hash(
            {
                "task_projection": row.get("task_projection"),
                "verifier_status": row.get("verifier_status"),
                "verifier_output_class": row.get("verifier_output_class"),
            }
        ),
        "candidate_action_set_hash": stable_hash(row.get("opaque_options", [])),
        "state_before_ref_hash": stable_hash(
            {
                "episode": row.get("episode_id_hash"),
                "source_or_test": row.get("source_or_test_hash"),
            }
        ),
        "observation_ref_hash": stable_hash(
            {
                "command_result": row.get("command_result_id_hash"),
                "observation": row.get("observation_id_hash"),
                "state_update": row.get("state_update_id_hash"),
                "stop": row.get("stop_decision_id_hash"),
            }
        ),
        "source_limitations": [
            "bounded_train_support_only",
            "target_label_not_reused_as_independent_policy_label",
            "not_patch_trace_repair_proof",
        ],
    }


def adapt_stage12417(row: dict[str, Any], index: int) -> dict[str, Any]:
    refs = row.get("source_refs") if isinstance(row.get("source_refs"), dict) else {}
    admission = row.get("admission") if isinstance(row.get("admission"), dict) else {}
    return {
        "source_stage": "stage12417_combined_train_support_ledger_v16",
        "source_record_ref_hash": stable_hash({"stage": "stage12417", "id": candidate_id(row)}),
        "source_record_kind": "combined_train_support_source",
        "language_family": normalize_language(row.get("language_family"), index),
        "task_family": str(row.get("task_family") or "transition_next_action"),
        "source_family_hash": stable_hash({"repo_family": row.get("repo_family"), "source_stage": row.get("source_stage")}),
        "root_lineage_key_hash": stable_hash({"root_id": row.get("root_id"), "source_root": refs.get("source_root_id")}),
        "transition_function_key_hash": stable_hash({"task_family": row.get("task_family"), "source_row": row.get("source_row_id")}),
        "candidate_action_set_hash": stable_hash(row.get("opaque_options", [])),
        "state_before_ref_hash": stable_hash({"source_refs": refs, "stage": row.get("stage")}),
        "observation_ref_hash": stable_hash(
            {
                "loss_mask": row.get("loss_mask"),
                "admission_reason": admission.get("reason"),
            }
        ),
        "source_limitations": [
            "combined_support_may_include_selected_test_template_rows",
            "exclude_collapsed_rows_until_task_specific_review",
            "not_strict_or_source_heldout",
        ],
    }

def adapt_stage12441(row: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "source_stage": "stage12441_embedding_transition_candidate_expansion_gate",
        "source_record_ref_hash": stable_hash({"stage": "stage12441", "id": candidate_id(row)}),
        "source_record_kind": "embedding_diversity_priority_source",
        "language_family": normalize_language(row.get("language_family"), index),
        "task_family": "transition_next_action",
        "source_family_hash": source_family_hash(row),
        "root_lineage_key_hash": root_lineage_hash(row),
        "transition_function_key_hash": str(row.get("transition_function_key_hash") or stable_hash(row)),
        "candidate_action_set_hash": row.get("candidate_action_set_hash"),
        "state_before_ref_hash": stable_hash({"embedding_feature_set_hash": row.get("embedding_feature_set_hash")}),
        "observation_ref_hash": stable_hash({"priority_bucket": row.get("priority_bucket")}),
        "source_limitations": [
            "embedding_priority_is_not_label",
            "blocked_reason_hashes_only",
            "requires_root_local_materialization",
        ],
    }


def collect_sources() -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for i, row in enumerate(read_jsonl(STAGE12205_RECORDS)):
        sources.append(adapt_stage12205(row, i))
    for i, row in enumerate(read_jsonl(STAGE12210_RECORDS)):
        sources.append(adapt_stage12210(row, i))
    for i, row in enumerate(read_jsonl(STAGE12416_ROWS)):
        sources.append(adapt_stage12416(row, i))
    for i, row in enumerate(read_jsonl(STAGE12417_ROWS)):
        sources.append(adapt_stage12417(row, i))
    for i, row in enumerate(read_jsonl(STAGE12295_LEDGER)):
        sources.append(adapt_stage12295(row, i))
    for i, row in enumerate(read_jsonl(STAGE12320_ROWS)):
        sources.append(adapt_stage12320(row, i))
    for i, row in enumerate(read_jsonl(STAGE12441_REPS)):
        sources.append(adapt_stage12441(row, i))
    return sources


def select_for_work_item(
    work_item: dict[str, Any],
    sources: list[dict[str, Any]],
    global_source_counts: Counter[str],
) -> list[dict[str, Any]]:
    task_family = str(work_item.get("task_family") or "")
    exact = [row for row in sources if row["task_family"] == task_family]
    if len(exact) < ROOTS_PER_WORK_ITEM:
        # Event-local records are useful as observation support for all policy families,
        # but remain explicitly blocked from direct train admission here.
        exact.extend(row for row in sources if row["task_family"] == "event_local_transition_observation")

    selected: list[dict[str, Any]] = []
    used_roots: set[str] = set()
    source_counts: Counter[str] = Counter()
    projected_global_source_counts = Counter(global_source_counts)
    language_counts: Counter[str] = Counter()
    for row in exact:
        root_key = row["root_lineage_key_hash"]
        source_key = row["source_family_hash"]
        language = row["language_family"]
        if root_key in used_roots:
            continue
        if source_counts[source_key] >= MAX_PER_SOURCE_FAMILY:
            continue
        if projected_global_source_counts[source_key] >= GLOBAL_SOURCE_FAMILY_CAP:
            continue
        if language_counts[language] >= 2:
            continue
        selected.append(row)
        used_roots.add(root_key)
        source_counts[source_key] += 1
        projected_global_source_counts[source_key] += 1
        language_counts[language] += 1
        if len(selected) >= ROOTS_PER_WORK_ITEM:
            break
    return selected


def materialization_candidate(work_item: dict[str, Any], source: dict[str, Any], rank: int) -> dict[str, Any]:
    return {
        "record_type": "stage12493_root_local_source_candidate_v1",
        "candidate_id_hash": stable_hash(
            {
                "work_item": work_item.get("work_item_id_hash"),
                "source": source["source_record_ref_hash"],
                "rank": rank,
            }
        ),
        "work_item_id_hash": work_item.get("work_item_id_hash"),
        "source_proposal_id_hash": work_item.get("source_proposal_id_hash"),
        "source_record_ref_hash": source["source_record_ref_hash"],
        "source_stage": source["source_stage"],
        "source_record_kind": source["source_record_kind"],
        "language_family": source["language_family"],
        "task_family": work_item.get("task_family"),
        "source_task_family": source["task_family"],
        "source_family_hash": source["source_family_hash"],
        "root_lineage_key_hash": source["root_lineage_key_hash"],
        "transition_function_key_hash": work_item.get("transition_function_key_hash")
        or source["transition_function_key_hash"],
        "candidate_action_set_source_hash": source.get("candidate_action_set_hash"),
        "state_before_ref_hash": source.get("state_before_ref_hash"),
        "observation_ref_hash": source.get("observation_ref_hash"),
        "source_limitations": sorted(set(source["source_limitations"])),
        "unresolved_required_fields": UNRESOLVED_FIELDS,
        "required_next_private_or_semantic_reviews": [
            "root_local_source_record_reopen_or_trace_join",
            "independent_policy_label_review",
            "candidate_action_set_rewrite_without_observed_action_leak",
            "state_delta_review",
            "anti_shortcut_renderer_review",
        ],
        "claim_boundary": {
            "source_adapter_candidate": True,
            "reviewed_train_support": False,
            "proof_grade_repair": False,
        },
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    work_items = read_jsonl(WORK_ITEMS)
    stage12492_summary = read_json(STAGE12492_SUMMARY)
    sources = collect_sources()

    records: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []
    global_source_counts: Counter[str] = Counter()
    for work_item in work_items:
        selected = select_for_work_item(work_item, sources, global_source_counts)
        for rank, source in enumerate(selected, 1):
            records.append(materialization_candidate(work_item, source, rank))
            global_source_counts[source["source_family_hash"]] += 1
        coverage_rows.append(
            {
                "record_type": "stage12493_work_item_coverage_v1",
                "work_item_id_hash": work_item.get("work_item_id_hash"),
                "task_family": work_item.get("task_family"),
                "target_root_count": work_item.get("target_root_count"),
                "candidate_source_records": len(selected),
                "language_counts": dict(sorted(Counter(row["language_family"] for row in selected).items())),
                "source_stage_counts": dict(sorted(Counter(row["source_stage"] for row in selected).items())),
                **FALSE_GUARDS,
                **ZERO_GUARDS,
            }
        )

    language_counts = Counter(row["language_family"] for row in records)
    task_counts = Counter(row["task_family"] for row in records)
    source_stage_counts = Counter(row["source_stage"] for row in records)
    source_family_counts = Counter(row["source_family_hash"] for row in records)
    max_source_family_share = (
        max(source_family_counts.values()) / len(records) if records else 0.0
    )
    issue_hashes = scan({"records": records, "coverage": coverage_rows})
    guardrail = {
        "stage": STAGE,
        "scan_passed": not issue_hashes,
        "raw_leak_count": len(issue_hashes),
        "issue_hashes": issue_hashes[:80],
    }
    summary = {
        "stage": STAGE,
        "record_type": "stage12493_root_local_concept_source_adapter_summary_v1",
        "decision": "root_local_source_candidates_ready_training_blocked"
        if records and guardrail["scan_passed"]
        else "blocked_empty_or_guardrail_failed",
        "source_stage_refs": [
            STAGE12492,
            "stage12205_authoritative_verifier_log_level3_joiner",
            "stage12210_controlled_triple_level3_joiner",
            "stage12416_direct_verifier_log_train_support_canonicalizer",
            "stage12417_combined_train_support_ledger_v16",
            "stage12295_transition_function_ledger",
            "stage12320_event_local_semantic_review_admission",
            "stage12441_embedding_transition_candidate_expansion_gate",
        ],
        "stage12492_work_item_count": stage12492_summary.get("work_item_count", len(work_items)),
        "source_pool_count": len(sources),
        "source_candidate_count": len(records),
        "work_item_coverage_count": len(coverage_rows),
        "work_items_with_full_target_root_count": sum(
            1
            for row in coverage_rows
            if row["candidate_source_records"] >= int(row.get("target_root_count") or ROOTS_PER_WORK_ITEM)
        ),
        "target_root_count_floor": stage12492_summary.get("target_root_count_floor"),
        "target_row_floor": stage12492_summary.get("target_row_floor"),
        "language_counts": dict(sorted(language_counts.items())),
        "task_family_counts": dict(sorted(task_counts.items())),
        "source_stage_counts": dict(sorted(source_stage_counts.items())),
        "max_source_family_share": round(max_source_family_share, 4),
        "unresolved_required_fields": UNRESOLVED_FIELDS,
        "next_stage": "stage12494_root_local_source_record_materializer",
        "raw_leak_count": guardrail["raw_leak_count"],
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "summary_hash": stable_hash(
            {
                "records": len(records),
                "language_counts": dict(language_counts),
                "task_counts": dict(task_counts),
            }
        ),
    }

    write_jsonl(OUT / "root_local_source_candidate_records.jsonl", records)
    write_jsonl(OUT / "work_item_source_coverage.jsonl", coverage_rows)
    write_json(OUT / "guardrail_scan.json", guardrail)
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY, summary)


if __name__ == "__main__":
    main()
