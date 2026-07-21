#!/usr/bin/env python3
"""Audit Stage12445 selected-test return proof depth.

This stage does not admit or train. It reprojects current public-safe return
rows from the named source records, replaces vague proof strings with
deterministic depth classes, and emits hash/class/count-only artifacts.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12456_selected_test_return_proof_depth_audit"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

RETURN_FILE = (
    ROOT
    / "runs/local/artifacts/stage12445_adapter_execution_return_ingest_and_level3_gate"
    / "returns/selected_test_transition_root_batch_non_web_first.return.jsonl"
)
STAGE12203_ROWS = (
    ROOT
    / "runs/local/artifacts/stage12203_controlled_selected_verifier_replay"
    / "level3_episode_records.jsonl"
)
STAGE12203_COMMAND_RESULTS = (
    ROOT
    / "runs/local/artifacts/stage12203_controlled_selected_verifier_replay"
    / "command_results.jsonl"
)
STAGE12207_ROWS = (
    ROOT
    / "runs/local/artifacts/stage12207_no_install_selected_test_log_level3_joiner"
    / "no_install_selected_test_level3_records.jsonl"
)
STAGE12215_ROWS = (
    ROOT
    / "runs/local/artifacts/stage12215_hydratable_selected_verifier_reexecution"
    / "level3_reexecution_records.jsonl"
)
STAGE12205_ROWS = (
    ROOT
    / "runs/local/artifacts/stage12205_authoritative_verifier_log_level3_joiner"
    / "authoritative_level3_episode_records.jsonl"
)

SUMMARY_INPUTS = {
    "stage12452_summary": (
        ROOT
        / "runs/local/artifacts/stage12452_direct_selected_test_execution_return_projection"
        / "summary.json"
    ),
    "stage12454_summary": (
        ROOT
        / "runs/local/artifacts/stage12454_stage12205_nonweb_authoritative_log_return_append"
        / "summary.json"
    ),
    "stage12455_summary": (
        ROOT
        / "runs/local/artifacts/stage12455_stage12205_wrapper_admission_audit"
        / "summary.json"
    ),
}

TARGET_REQUEST_HASH = "ac183215a709860587488958"
PLACEHOLDER_PROOFS = {"proven", "pass", "passed", "clear", "valid", "true", "yes"}

ZERO_AUTHORITY = {
    "training_allowed": False,
    "admission_allowed": False,
    "execution_allowed": False,
    "execution_performed_by_stage": False,
    "emitted_training_rows": 0,
    "sealed_eval_rows_emitted": 0,
}

FORBIDDEN_PUBLIC_KEYS = {
    "path",
    "paths",
    "url",
    "urls",
    "uri",
    "command",
    "command_text",
    "commands",
    "stdout",
    "stderr",
    "output",
    "outputs",
    "diff",
    "patch",
    "patch_body",
    "raw",
    "raw_text",
    "trace",
    "trace_text",
    "private_locator",
    "source_text",
    "source_path",
}
ALLOWED_KEY_CONTEXT_RE = re.compile(
    r"(policy|emitted|forbidden|required|slot|slots|schema|hash|hashes|ref|refs|"
    r"class|status|proof|reason|contract|request|count|scan|supply|stage|artifact|depth|summary)",
    re.I,
)
RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:Traceback \(most recent call last\)|stdout:|stderr:|stack trace|"
    r"terminal output:|command output:|git clone\s+\S|git apply\s+\S|"
    r"curl\s+\S|bash -|sh -|python -c)\b",
    re.I | re.M,
)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} is not a JSON object")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path.name}:{line_number} is not a JSON object")
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


def scan_public(label: str, value: Any) -> list[str]:
    issues: list[str] = []
    leaf = label.rsplit(".", 1)[-1].split("[", 1)[0].lower()
    if leaf in FORBIDDEN_PUBLIC_KEYS and not ALLOWED_KEY_CONTEXT_RE.search(label):
        issues.append(f"{label}:forbidden_public_key")
    if isinstance(value, str):
        if RAW_LEAK_RE.search(value):
            issues.append(f"{label}:raw_public_leak:{stable_hash(value)}")
    elif isinstance(value, dict):
        for key, child in value.items():
            issues.extend(scan_public(f"{label}.{key}", child))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            issues.extend(scan_public(f"{label}[{index}]", child))
    return issues


def add_scripts_to_path() -> None:
    scripts_dir = str(ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)


def status_class(row: dict[str, Any]) -> str:
    return str(row.get("verifier_status") or row.get("verifier_transition") or "unknown")


def command_result_from_direct(
    row: dict[str, Any], command_results_by_id: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    embedded = row.get("command_result")
    if isinstance(embedded, dict):
        return embedded
    observed = row.get("observed_action")
    command_result_id = ""
    if isinstance(observed, dict):
        command_result_id = str(observed.get("command_result_id") or "")
    return command_results_by_id.get(command_result_id, {})


def observed_action_is_candidate_member(row: dict[str, Any]) -> bool:
    candidate_set = row.get("candidate_action_set")
    observed = row.get("observed_action")
    if not isinstance(candidate_set, dict) or not isinstance(observed, dict):
        return False
    observed_id = str(observed.get("action_id") or "")
    chosen_id = str(candidate_set.get("chosen_action_id") or "")
    if observed_id and observed_id == chosen_id:
        return True
    action_ids = candidate_set.get("action_ids")
    if isinstance(action_ids, list) and observed_id in {str(item) for item in action_ids}:
        return True
    actions = candidate_set.get("candidate_actions")
    if isinstance(actions, list):
        return any(
            isinstance(action, dict) and str(action.get("action_id") or "") == observed_id
            for action in actions
        )
    return False


def chosen_role_class(row: dict[str, Any]) -> str:
    actions = row.get("candidate_action_set", {}).get("candidate_actions", [])
    if isinstance(actions, list):
        for action in actions:
            if isinstance(action, dict) and action.get("is_chosen") is True:
                return str(action.get("role") or action.get("semantic_role") or "unknown")
    return "unknown"


def projection_permissions_present(row: dict[str, Any]) -> bool:
    permissions = row.get("projection_permissions")
    if isinstance(permissions, list):
        return {
            "transition_verifier_transition",
            "transition_continue_or_stop",
        }.issubset({str(item) for item in permissions})
    if isinstance(permissions, dict):
        return (
            permissions.get("may_project_verifier_transition") is True
            and permissions.get("may_project_continue_or_stop") is True
        )
    return False


def source_lineage_marker(row: dict[str, Any], input_stage: str) -> dict[str, str]:
    material = {
        "input_stage": input_stage,
        "episode_id": row.get("episode_id"),
        "root_id": row.get("root_id"),
        "repo_family": row.get("repo_family") or row.get("repo_id"),
        "root_lineage_key": row.get("root_lineage_key"),
    }
    return {
        "source_record_ref_hash": stable_hash(["source_record", material]),
        "source_record_class": input_stage,
    }


def repair_credit_class(row: dict[str, Any], matched: dict[str, Any] | None) -> str:
    if row.get("observation_status_class") != "FAIL_TO_PASS":
        return "not_repair_credit_transition_observation"
    if not matched:
        return "no_patch_transition_observation"
    source_row = matched["source_record"]
    source_extra = source_row.get("source_extra") if isinstance(source_row.get("source_extra"), dict) else {}
    source_stage = str(source_row.get("source_stage") or "")
    mutation_markers = {
        "controlled_fixture_train_support_only",
        "controlled_triple",
        "patch_effect",
        "source_file_mutated",
    }
    if source_stage in {
        "stage12003_cpp_real_source_fail_to_pass_mutations",
        "stage12025_controlled_fail_to_pass_expansion_rows",
    }:
        return "controlled_or_mutation_transition_support"
    if any(marker in source_extra for marker in mutation_markers):
        return "controlled_or_mutation_transition_support"
    return "no_patch_transition_observation"


def external_repair_credit_class(row: dict[str, Any], matched: dict[str, Any] | None) -> str:
    if row.get("observation_status_class") != "FAIL_TO_PASS":
        return "not_applicable"
    if not matched:
        return "no_external_comparable_repair_proof"
    source_row = matched["source_record"]
    source_extra = source_row.get("source_extra") if isinstance(source_row.get("source_extra"), dict) else {}
    if source_extra.get("external_comparable_repair") is True and source_extra.get("patch_effect") is True:
        return "external_comparable_repair_patch_effect_proven"
    return "no_external_comparable_repair_proof"


def load_reprojected_index() -> tuple[dict[str, dict[str, Any]], Counter[str]]:
    add_scripts_to_path()
    import build_stage12452_direct_selected_test_execution_return_projection as s52
    import build_stage12454_stage12205_nonweb_authoritative_log_return_append as s54

    request52, issues52 = s52.target_request()
    request54, issues54 = s54.target_request()
    index: dict[str, dict[str, Any]] = {}
    counters: Counter[str] = Counter()
    counters.update({f"stage12452_binding_issue:{issue}": 1 for issue in issues52})
    counters.update({f"stage12454_binding_issue:{issue}": 1 for issue in issues54})

    command_rows = read_jsonl(STAGE12203_COMMAND_RESULTS)
    command_results_by_id = {
        str(row.get("command_result_id")): row
        for row in command_rows
        if row.get("command_result_id")
    }
    direct_inputs = {
        "stage12203_controlled_selected_verifier_replay": read_jsonl(STAGE12203_ROWS),
        "stage12207_no_install_selected_test_log_level3_joiner": read_jsonl(STAGE12207_ROWS),
        "stage12215_hydratable_selected_verifier_reexecution": read_jsonl(STAGE12215_ROWS),
    }
    for input_stage, rows in direct_inputs.items():
        for source_row in rows:
            if request52 is None:
                continue
            command = command_result_from_direct(source_row, command_results_by_id)
            projected = s52.build_return_row(source_row, input_stage, request52, command)
            row_hash = str(projected.get("return_row_hash") or "")
            marker = source_lineage_marker(source_row, input_stage)
            index[row_hash] = {
                "projected_row": projected,
                "source_record": source_row,
                "input_stage": input_stage,
                **marker,
            }
            counters[f"candidate_source_records:{input_stage}"] += 1

    for source_row in read_jsonl(STAGE12205_ROWS):
        if request54 is None:
            continue
        projected = s54.build_return_row(source_row, request54)
        row_hash = str(projected.get("return_row_hash") or "")
        marker = source_lineage_marker(source_row, "stage12205_authoritative_verifier_log_level3_joiner")
        index[row_hash] = {
            "projected_row": projected,
            "source_record": source_row,
            "input_stage": "stage12205_authoritative_verifier_log_level3_joiner",
            **marker,
        }
        counters["candidate_source_records:stage12205_authoritative_verifier_log_level3_joiner"] += 1
    return index, counters


def placeholder_fields(row: dict[str, Any]) -> list[str]:
    fields = []
    for field in (
        "same_source_lineage_proof",
        "verifier_relevance_proof",
        "policy_label_independence_proof",
        "causal_verifier_linkage",
    ):
        if str(row.get(field) or "").strip().lower() in PLACEHOLDER_PROOFS:
            fields.append(field)
    return fields


def classify_depths(row: dict[str, Any], matched: dict[str, Any] | None) -> dict[str, str]:
    if not matched:
        return {
            "same_source_lineage_depth": "placeholder_only_no_source_reprojection_match",
            "verifier_relevance_depth": "placeholder_only_no_source_reprojection_match",
            "policy_label_independence_depth": "placeholder_only_no_source_reprojection_match",
            "causal_linkage_depth": "placeholder_only_no_source_reprojection_match",
            "state_delta_depth": "return_codes_only_no_source_reprojection_match",
            "stop_continue_depth": "return_label_only_no_source_reprojection_match",
        }

    source_row = matched["source_record"]
    projected = matched["projected_row"]
    exact = projected == row
    command = (
        source_row.get("command_result")
        if isinstance(source_row.get("command_result"), dict)
        else {}
    )
    if not command:
        command = projected.get("observed_action_digest") and {"projected_digest_present": True}
    anti_cheat = source_row.get("anti_cheat") if isinstance(source_row.get("anti_cheat"), dict) else {}
    candidate_semantics = row.get("candidate_action_set_semantics")
    candidate_bound = observed_action_is_candidate_member(source_row)
    if isinstance(candidate_semantics, dict):
        candidate_bound = candidate_bound or candidate_semantics.get("observed_action_member_status") == "present"
    policy_bound = (
        row.get("observed_action_imitation_status") == "observed_but_independently_validated"
        and str(row.get("non_imitation_policy_action_label") or "").startswith("derive_transition_label")
        and bool(row.get("counterfactual_action_set"))
        and anti_cheat.get("target_not_promotable_eval") is True
    )
    verifier_bound = (
        candidate_bound
        and projection_permissions_present(source_row)
        and chosen_role_class(source_row)
        in {
            "run_selected_verifier",
            "run_selected_verifier_before_or_after_patch",
            "PASS_CURRENT_STATE",
            "FAIL_CURRENT_STATE",
            "ENV_BLOCKED",
            "FAIL_TO_PASS",
            "PASS_CURRENT_BUILD_AND_RUN",
        }
    )
    status_recomputed = projected.get("observation_status_class") == row.get("observation_status_class")
    state_recomputed = (
        projected.get("state_delta_codes") == row.get("state_delta_codes")
        and projected.get("state_after_summary_codes") == row.get("state_after_summary_codes")
    )
    stop_recomputed = projected.get("stop_continue_label") == row.get("stop_continue_label")

    return {
        "same_source_lineage_depth": (
            "source_record_reprojection_exact_lineage_hash_match"
            if exact
            else "source_record_reprojection_hash_match_field_drift"
        ),
        "verifier_relevance_depth": (
            "source_candidate_selected_verifier_command_bound"
            if verifier_bound and command
            else "source_record_present_verifier_binding_partial"
        ),
        "policy_label_independence_depth": (
            "metadata_derived_label_with_counterfactuals_non_eval_bound"
            if policy_bound
            else "source_record_present_policy_independence_partial"
        ),
        "causal_linkage_depth": (
            "source_execution_result_to_status_reprojection_exact"
            if exact and status_recomputed and command
            else "source_record_present_causal_linkage_partial"
        ),
        "state_delta_depth": (
            "source_status_to_state_delta_codes_recomputed_exact"
            if state_recomputed
            else "source_record_present_state_delta_partial"
        ),
        "stop_continue_depth": (
            "source_stop_decision_or_status_rule_recomputed_exact"
            if stop_recomputed
            else "source_record_present_stop_continue_partial"
        ),
    }


def depth_is_source_backed(depths: dict[str, str]) -> bool:
    blocked_markers = (
        "placeholder_only",
        "return_codes_only",
        "return_label_only",
        "partial",
        "field_drift",
    )
    return not any(
        any(marker in value for marker in blocked_markers) for value in depths.values()
    )


def build_artifacts() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    return_rows = read_jsonl(RETURN_FILE)
    reprojected_index, source_counters = load_reprojected_index()
    summaries = {name: read_json(path) for name, path in SUMMARY_INPUTS.items()}

    records: list[dict[str, Any]] = []
    depth_counts: dict[str, Counter[str]] = {
        "same_source_lineage_depth": Counter(),
        "verifier_relevance_depth": Counter(),
        "policy_label_independence_depth": Counter(),
        "causal_linkage_depth": Counter(),
        "state_delta_depth": Counter(),
        "stop_continue_depth": Counter(),
        "repair_credit_class": Counter(),
    }
    source_stage_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    language_counts: Counter[str] = Counter()
    placeholder_counts: Counter[str] = Counter()
    source_match_counts: Counter[str] = Counter()
    issue_counts: Counter[str] = Counter()
    external_repair_credit_counts: Counter[str] = Counter()

    seen_hashes: set[str] = set()
    for idx, row in enumerate(return_rows, start=1):
        row_hash = str(row.get("return_row_hash") or stable_hash(["missing_return_hash", idx, row]))
        matched = reprojected_index.get(row_hash)
        projected_exact = bool(matched and matched.get("projected_row") == row)
        if row_hash in seen_hashes:
            issue_counts["duplicate_return_row_hash"] += 1
        seen_hashes.add(row_hash)

        placeholders = placeholder_fields(row)
        placeholder_counts.update(placeholders)
        depths = classify_depths(row, matched)
        repair_class = repair_credit_class(row, matched)
        external_class = external_repair_credit_class(row, matched)
        external_repair_credit_counts[external_class] += 1

        if matched is None:
            source_match_class = "no_source_reprojection_match"
            issue_counts["source_reprojection_match_missing"] += 1
        elif projected_exact:
            source_match_class = "source_reprojection_exact"
        else:
            source_match_class = "source_reprojection_hash_match_field_drift"
            issue_counts["source_reprojection_field_drift"] += 1
        source_match_counts[source_match_class] += 1
        if not depth_is_source_backed(depths):
            issue_counts["row_has_non_source_backed_or_partial_depth"] += 1
        if row.get("source_execution_request_id_hash") != TARGET_REQUEST_HASH:
            issue_counts["target_request_hash_mismatch"] += 1
        if row.get("training_eligible") is not False or row.get("strict_eval_eligible") is not False:
            issue_counts["training_or_eval_flag_not_false"] += 1
        if row.get("observation_status_class") == "FAIL_TO_PASS" and external_class != "external_comparable_repair_patch_effect_proven":
            issue_counts["fail_to_pass_has_no_external_repair_credit"] += 1

        for key, value in depths.items():
            depth_counts[key][value] += 1
        depth_counts["repair_credit_class"][repair_class] += 1
        source_stage_counts[str(row.get("source_stage") or "unknown")] += 1
        status_counts[str(row.get("observation_status_class") or "unknown")] += 1
        language_counts[str(row.get("language_family") or "unknown")] += 1

        record = {
            "row_ref_hash": stable_hash(["row_ref", idx, row_hash]),
            "return_row_hash": row_hash,
            "source_match_class": source_match_class,
            "source_record_ref_hash": matched.get("source_record_ref_hash") if matched else "missing",
            "source_stage": row.get("source_stage"),
            "language_family": row.get("language_family"),
            "observation_status_class": row.get("observation_status_class"),
            "placeholder_proof_fields": placeholders,
            "same_source_lineage_depth": depths["same_source_lineage_depth"],
            "verifier_relevance_depth": depths["verifier_relevance_depth"],
            "policy_label_independence_depth": depths["policy_label_independence_depth"],
            "causal_linkage_depth": depths["causal_linkage_depth"],
            "state_delta_depth": depths["state_delta_depth"],
            "stop_continue_depth": depths["stop_continue_depth"],
            "repair_credit_class": repair_class,
            "external_repair_credit_class": external_class,
            "training_eligible": False,
            "strict_eval_eligible": False,
            "issue_codes": sorted(
                {
                    code
                    for code, present in {
                        "source_reprojection_match_missing": matched is None,
                        "source_reprojection_field_drift": matched is not None and not projected_exact,
                        "non_source_backed_or_partial_depth": not depth_is_source_backed(depths),
                        "fail_to_pass_no_external_repair_credit": row.get("observation_status_class") == "FAIL_TO_PASS"
                        and external_class != "external_comparable_repair_patch_effect_proven",
                    }.items()
                    if present
                }
            ),
        }
        records.append(record)

    all_rows_source_backed_depth = bool(return_rows) and all(
        depth_is_source_backed(
            {
                "same_source_lineage_depth": record["same_source_lineage_depth"],
                "verifier_relevance_depth": record["verifier_relevance_depth"],
                "policy_label_independence_depth": record["policy_label_independence_depth"],
                "causal_linkage_depth": record["causal_linkage_depth"],
                "state_delta_depth": record["state_delta_depth"],
                "stop_continue_depth": record["stop_continue_depth"],
            }
        )
        for record in records
    )
    external_repair_credit_allowed = (
        external_repair_credit_counts.get("external_comparable_repair_patch_effect_proven", 0)
        == status_counts.get("FAIL_TO_PASS", 0)
        and status_counts.get("FAIL_TO_PASS", 0) > 0
    )
    transition_support_packaging_allowed = all_rows_source_backed_depth
    training_packaging_allowed = False

    summary = {
        "stage": STAGE,
        "record_type": "selected_test_return_proof_depth_audit_public_safe_v1",
        "decision": (
            "proof_depth_source_backed_for_transition_support_only"
            if transition_support_packaging_allowed
            else "transition_support_packaging_blocked_pending_non_placeholder_source_backed_depth"
        ),
        **ZERO_AUTHORITY,
        "return_row_count": len(return_rows),
        "row_audit_record_count": len(records),
        "all_rows_source_backed_depth": all_rows_source_backed_depth,
        "packaging_allowed": False,
        "transition_support_packaging_allowed": transition_support_packaging_allowed,
        "training_packaging_allowed": training_packaging_allowed,
        "external_repair_credit_allowed": external_repair_credit_allowed,
        "external_repair_credit_count": external_repair_credit_counts.get(
            "external_comparable_repair_patch_effect_proven", 0
        ),
        "source_match_counts": dict(sorted(source_match_counts.items())),
        "source_stage_counts": dict(sorted(source_stage_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "observation_status_counts": dict(sorted(status_counts.items())),
        "placeholder_proof_counts": dict(sorted(placeholder_counts.items())),
        "depth_counts": {
            key: dict(sorted(counter.items())) for key, counter in sorted(depth_counts.items())
        },
        "repair_credit_class_counts": dict(sorted(depth_counts["repair_credit_class"].items())),
        "external_repair_credit_class_counts": dict(sorted(external_repair_credit_counts.items())),
        "issue_counts": dict(sorted(issue_counts.items())),
        "source_candidate_record_counts": dict(sorted(source_counters.items())),
        "input_fingerprints": {
            "selected_test_return_file_sha256_24": file_hash(RETURN_FILE),
            "stage12203_records_sha256_24": file_hash(STAGE12203_ROWS),
            "stage12203_command_results_sha256_24": file_hash(STAGE12203_COMMAND_RESULTS),
            "stage12207_records_sha256_24": file_hash(STAGE12207_ROWS),
            "stage12215_records_sha256_24": file_hash(STAGE12215_ROWS),
            "stage12205_records_sha256_24": file_hash(STAGE12205_ROWS),
            **{
                f"{name}_sha256_24": file_hash(path)
                for name, path in sorted(SUMMARY_INPUTS.items())
            },
        },
        "upstream_summary_counts": {
            "stage12452_projected_return_row_count": summaries["stage12452_summary"].get(
                "projected_return_row_count"
            ),
            "stage12454_appended_return_row_count": summaries["stage12454_summary"].get(
                "appended_return_row_count"
            ),
            "stage12455_return_row_count": summaries["stage12455_summary"].get("return_row_count"),
            "stage12455_placeholder_total": sum(
                int(value)
                for value in (
                    summaries["stage12455_summary"].get("proof_placeholder_counts") or {}
                ).values()
            ),
        },
        "claim_boundary": (
            "Rows are deterministic Level-3 selected-verifier transition support only. "
            "This stage emits no training rows, grants no admission, and grants no external "
            "FAIL_TO_PASS repair credit without external comparable patch-effect proof."
        ),
        "next_stage_recommendation": (
            "Stage12457 should package these 40 rows only as public-safe Level-3 verifier-transition "
            "support, keep training/admission disabled, and exclude external repair credit unless a "
            "separate patch-effect proof audit validates comparable external repairs."
        ),
        "guardrail_scan": {},
        "guardrail_scan_passed": False,
        "raw_leak_count": 0,
        "schema_issue_count": 0,
        "summary_hash": "pending",
    }
    scan_issues = scan_public("summary", summary) + scan_public("row_audit_records", records)
    summary["guardrail_scan"] = {
        "scan_passed": not scan_issues,
        "issue_count": len(set(scan_issues)),
        "issues": sorted(set(scan_issues)),
        "raw_leak_count": len(
            {issue for issue in scan_issues if "raw_public_leak" in issue or "forbidden_public_key" in issue}
        ),
        "scan_scope": "stage12456_public_safe_hash_class_count_artifacts",
    }
    summary["guardrail_scan_passed"] = summary["guardrail_scan"]["scan_passed"]
    summary["raw_leak_count"] = summary["guardrail_scan"]["raw_leak_count"]
    if not summary["guardrail_scan_passed"]:
        summary["transition_support_packaging_allowed"] = False
    summary["packaging_allowed"] = False
    summary["training_packaging_allowed"] = False
    summary["summary_hash"] = stable_hash({k: v for k, v in summary.items() if k != "summary_hash"})
    return summary, records


def main() -> None:
    summary, records = build_artifacts()
    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT / "row_audit_records.jsonl", records)
    write_json(OUT / "summary.json", summary)
    write_json(OUT / f"{STAGE}.json", summary)
    write_json(SUMMARY, summary)
    print(
        json.dumps(
            {
                "stage": summary["stage"],
                "decision": summary["decision"],
                "return_row_count": summary["return_row_count"],
                "source_match_counts": summary["source_match_counts"],
                "placeholder_proof_counts": summary["placeholder_proof_counts"],
                "repair_credit_class_counts": summary["repair_credit_class_counts"],
                "packaging_allowed": summary["packaging_allowed"],
                "transition_support_packaging_allowed": summary["transition_support_packaging_allowed"],
                "training_packaging_allowed": summary["training_packaging_allowed"],
                "external_repair_credit_allowed": summary["external_repair_credit_allowed"],
                "guardrail_scan_passed": summary["guardrail_scan_passed"],
                "raw_leak_count": summary["raw_leak_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
