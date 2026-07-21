#!/usr/bin/env python3
"""Build Stage12444 adapter execution request manifest.

This stage turns Stage12442/12443 requests into executable work manifests for
private reviewers/adapters. It does not execute, admit, or emit training rows.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12444_adapter_execution_request_manifest"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12442 = "stage12442_representative_private_review_and_source_adapter_expansion_request"
STAGE12443 = "stage12443_representative_private_review_packet_preflight"
STAGE12413 = "stage12413_open_swe_level3_proof_gap_replay_manifest"

STAGE12442_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12442}.json"
STAGE12443_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12443}.json"
STAGE12442_OUT = ROOT / "runs/local/artifacts" / STAGE12442
STAGE12443_OUT = ROOT / "runs/local/artifacts" / STAGE12443
STAGE12413_OUT = ROOT / "runs/local/artifacts" / STAGE12413

SOURCE_ADAPTER_REQUESTS = STAGE12442_OUT / "source_adapter_expansion_request.json"
ADAPTER_GAP_TARGETS = STAGE12442_OUT / "adapter_gap_targets.json"
REPRESENTATIVE_MANIFEST = STAGE12442_OUT / "representative_private_review_packet_manifest.jsonl"
STAGE12413_REPLAY = STAGE12413_OUT / "open_swe_stage12414_replay_micro_pilot_requests.jsonl"

ZERO_COUNTERS: dict[str, bool | int] = {
    "training_allowed": False,
    "admission_allowed": False,
    "execution_allowed": False,
    "execution_performed_by_stage": False,
    "emitted_training_rows": 0,
    "admitted_rows": 0,
    "countable_new_rows": 0,
    "level3_candidate_count": 0,
    "level4_candidate_count": 0,
    "patch_trace_candidate_count": 0,
    "sealed_eval_rows_emitted": 0,
}

OPTIONAL_RETURN_PROPERTIES = [
    "schema_name",
    "source_execution_request_id_hash",
    "request_kind",
    "return_row_hash",
    "slot_status",
    "provided_slots",
    "source_stage",
    "stage12413_request_hash",
    "stage12413_row_ref_hash",
    "stage12413_instance_ref_hash",
    "stage12413_source_record_ref_hash",
    "stage12413_trajectory_ref_hash",
    "stage12413_dataset_file_hash",
    "benchmark_material_status",
    "eval_contamination_status",
    "strict_eval_eligible",
    "training_eligible",
]

REQUIRED_RETURN_SLOTS = [
    "root_id_hash",
    "source_root_label_hash",
    "repo_family_hash",
    "language_family",
    "split_group_id_hash",
    "root_lineage_key_hash",
    "ordered_event_refs_hash",
    "state_before_summary_codes",
    "candidate_action_set_semantics",
    "observed_action_digest",
    "policy_action_label",
    "non_imitation_policy_action_label",
    "observed_action_imitation_status",
    "counterfactual_action_set",
    "policy_label_independence_proof",
    "policy_label_independence_status",
    "observation_status_class",
    "verifier_identity_hash",
    "verifier_relevance_proof",
    "same_source_lineage_proof",
    "patch_application_or_no_patch_reason",
    "causal_verifier_linkage",
    "state_delta_codes",
    "state_after_summary_codes",
    "stop_continue_label",
    "protected_overlap_check",
    "leakage_check",
]

ADMISSION_REQUIRED_SLOTS = [
    "same_source_lineage_proof",
    "verifier_relevance_proof",
    "non_imitation_policy_action_label",
    "observed_action_imitation_status",
    "policy_label_independence_proof",
    "policy_label_independence_status",
    "counterfactual_action_set",
    "state_delta_codes",
    "state_after_summary_codes",
    "stop_continue_label",
    "protected_overlap_check",
    "leakage_check",
]

RAW_CONTENT_POLICY = {
    "public_artifacts_raw_values_emitted": False,
    "public_artifacts_paths_commands_outputs_diffs_patches_sources_emitted": False,
    "executor_may_use_private_raw_refs": True,
    "executor_return_public_schema_hash_only": True,
    "admission_requires_separate_ingest_gate": True,
}

FORBIDDEN_KEYS = {
    "path", "paths", "url", "urls", "uri", "command", "command_text", "commands",
    "stdout", "stderr", "output", "outputs", "diff", "patch", "patch_body", "source",
    "source_text", "private_locator", "raw", "raw_text", "trace", "trace_text", "issue_body",
}
ALLOWED_KEY_CONTEXT_RE = re.compile(r"(policy|emitted|forbidden|required|slot|slots|schema|hash|hashes|ref|refs|class|status|proof|reason|contract|request)", re.I)
RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:stdout:|stderr:|terminal output:|command output:|git clone\s+\S|git apply\s+\S|python -c|bash -)\b",
    re.I | re.M,
)
OVERCLAIM_RE = re.compile(r"\b(?:admitted|training row|trainable|accepted row|verified repair|level-3 complete|level3 complete|patch-trace complete|execution succeeded|tests passed)\b", re.I)
ALLOWED_OVERCLAIM_CONTEXT_RE = re.compile(r"(false|zero|none|blocked|request|required|future|must not|not |no |fail.closed|fail-closed|policy|guardrail|schema|contract|separate ingest)", re.I)


def read_json(path: Path) -> Any:
    if not path.exists():
        return {} if path.suffix == ".json" else []
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
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


def scan(label: str, value: Any) -> list[str]:
    issues: list[str] = []
    leaf = label.rsplit('.', 1)[-1].split('[', 1)[0].lower()
    if leaf in FORBIDDEN_KEYS and not ALLOWED_KEY_CONTEXT_RE.search(label):
        issues.append(f"{label}:forbidden_public_key")
    if isinstance(value, str):
        if RAW_LEAK_RE.search(value):
            issues.append(f"{label}:raw_leak:{stable_hash(value)}")
        for match in OVERCLAIM_RE.finditer(value):
            context = value[max(0, match.start() - 80): min(len(value), match.end() + 80)]
            if not ALLOWED_OVERCLAIM_CONTEXT_RE.search(context):
                issues.append(f"{label}:overclaim:{stable_hash(context)}")
    elif isinstance(value, dict):
        for key, child in value.items():
            issues.extend(scan(f"{label}.{key}", child))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            issues.extend(scan(f"{label}[{index}]", child))
    return issues


def build_requests(adapter_requests: list[dict[str, Any]], representatives: list[dict[str, Any]], open_swe_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    requests: list[dict[str, Any]] = []
    for adapter in adapter_requests:
        adapter_id = str(adapter.get("adapter_request_id") or "unknown_adapter")
        return_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", adapter_id).strip("_") or "unknown_adapter"
        requests.append({
            "execution_request_id_hash": stable_hash({"adapter": adapter_id}),
            "adapter_request_id": adapter_id,
            "request_kind": "source_adapter_materialization",
            "requested_candidate_floor": int(adapter.get("target_candidate_floor") or 0),
            "requested_distinct_repo_floor": int(adapter.get("target_distinct_repo_floor") or 0),
            "requested_language_floor": adapter.get("target_language_floor") or {},
            "acceptance_schema": adapter.get("acceptance_schema"),
            "split_policy": adapter.get("split_policy"),
            "verifier_oracle_requirement": adapter.get("verifier_oracle_requirement"),
            "anti_leak_policy": adapter.get("anti_leak_policy"),
            "required_return_slots": REQUIRED_RETURN_SLOTS,
            "admission_required_slots": ADMISSION_REQUIRED_SLOTS,
            "expected_return_path": f"runs/local/artifacts/stage12445_adapter_execution_return_ingest_and_level3_gate/returns/{return_stem}.return.jsonl",
            "expected_return_schema": "adapter_executor_return_public_safe_v1",
            "execution_performed_by_stage": False,
            "training_allowed": False,
            "admission_allowed": False,
        })
    requests.append({
        "execution_request_id_hash": stable_hash({"representative_private_review": len(representatives)}),
        "adapter_request_id": "representative_private_semantic_review_batch_10",
        "request_kind": "private_semantic_review",
        "requested_candidate_floor": len(representatives),
        "requested_distinct_repo_floor": len({row.get("repo_family_hash") for row in representatives}),
        "requested_language_floor": dict(Counter(str(row.get("language_family")) for row in representatives)),
        "acceptance_schema": "representative_private_review_return_v2",
        "split_policy": "representative_only_no_cluster_member_propagation",
        "verifier_oracle_requirement": "private reviewer must prove verifier relevance and causal linkage from raw refs",
        "anti_leak_policy": "public return hash/status/classes only",
        "required_return_slots": REQUIRED_RETURN_SLOTS,
        "admission_required_slots": ADMISSION_REQUIRED_SLOTS,
        "expected_return_path": "runs/local/artifacts/stage12445_adapter_execution_return_ingest_and_level3_gate/returns/representative_private_semantic_review_batch_10.return.jsonl",
        "expected_return_schema": "adapter_executor_return_public_safe_v1",
        "execution_performed_by_stage": False,
        "training_allowed": False,
        "admission_allowed": False,
    })
    open_swe_batch: list[dict[str, Any]] = []
    for index, row in enumerate(open_swe_rows[:20], 1):
        row_hashes = row.get("row_hashes") if isinstance(row.get("row_hashes"), dict) else {}
        batch_row = {
            "execution_request_id_hash": stable_hash({"open_swe_micro": index, "request_hash": row.get("request_hash"), "row_hashes": row_hashes}),
            "request_kind": "open_swe_authoritative_replay_micro_pilot",
            "source_stage": STAGE12413,
            "source_request_hash": stable_hash(row),
            "stage12413_request_hash": row.get("request_hash"),
            "stage12413_row_ref_hash": row_hashes.get("row_ref_hash"),
            "stage12413_instance_ref_hash": row_hashes.get("instance_ref_hash"),
            "stage12413_source_record_ref_hash": row_hashes.get("source_record_ref_hash"),
            "stage12413_trajectory_ref_hash": row_hashes.get("trajectory_ref_hash"),
            "stage12413_dataset_file_hash": row_hashes.get("dataset_file_hash"),
            "benchmark_material_status": "benchmark_or_trace_material_quarantined_until_contamination_gate",
            "eval_contamination_status": "unknown_blocked_until_separate_gate",
            "strict_eval_eligible": False,
            "training_eligible": False,
            "expected_return_path": f"runs/local/artifacts/stage12445_adapter_execution_return_ingest_and_level3_gate/returns/open_swe_micro_{index}.return.jsonl",
            "expected_return_schema": "adapter_executor_return_public_safe_v1",
            "required_return_slots": REQUIRED_RETURN_SLOTS,
            "admission_required_slots": ADMISSION_REQUIRED_SLOTS,
            "execution_performed_by_stage": False,
            "training_allowed": False,
            "admission_allowed": False,
        }
        open_swe_batch.append(batch_row)
    return requests, open_swe_batch


def build_artifact() -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], dict[str, Any], dict[str, Any]]:
    stage12442 = read_json(STAGE12442_SUMMARY)
    stage12443 = read_json(STAGE12443_SUMMARY)
    adapter_requests = read_json(SOURCE_ADAPTER_REQUESTS)
    if not isinstance(adapter_requests, list):
        adapter_requests = []
    gap_targets = read_json(ADAPTER_GAP_TARGETS)
    if not isinstance(gap_targets, dict):
        gap_targets = {}
    representatives = read_jsonl(REPRESENTATIVE_MANIFEST)
    open_swe_rows = read_jsonl(STAGE12413_REPLAY)
    requests, open_swe_batch = build_requests(adapter_requests, representatives, open_swe_rows)

    requested_by_kind = Counter(str(row.get("request_kind")) for row in requests + open_swe_batch)
    requested_candidate_floor_total = sum(int(row.get("requested_candidate_floor") or 0) for row in requests if row.get("request_kind") != "private_semantic_review")
    schema_issues: list[str] = []
    for row in requests + open_swe_batch:
        missing = [
            slot
            for slot in [
                "execution_request_id_hash",
                "request_kind",
                "required_return_slots",
                "admission_required_slots",
                "expected_return_path",
                "expected_return_schema",
            ]
            if not row.get(slot)
        ]
        if missing:
            schema_issues.append(f"request_missing_{stable_hash(row)}:{','.join(missing)}")
        if row.get("execution_performed_by_stage") is not False or row.get("training_allowed") is not False or row.get("admission_allowed") is not False:
            schema_issues.append(f"request_gate_violation_{stable_hash(row)}")
    expected_paths = [str(row.get("expected_return_path")) for row in requests + open_swe_batch]
    duplicate_paths = [path for path, count in Counter(expected_paths).items() if count > 1]
    if duplicate_paths:
        schema_issues.extend(f"duplicate_expected_return_path:{stable_hash(path)}" for path in duplicate_paths)

    executor_return_schema = {
        "schema_name": "adapter_executor_return_public_safe_v1",
        "required_return_slots": REQUIRED_RETURN_SLOTS,
        "admission_required_slots": ADMISSION_REQUIRED_SLOTS,
        "public_value_policy": "hashes_enums_counts_status_classes_only",
        "raw_private_values_allowed_in_public_return": False,
        "level3_counting_allowed_in_return_stage": False,
        "allowed_properties": sorted(set(REQUIRED_RETURN_SLOTS) | set(OPTIONAL_RETURN_PROPERTIES)),
        "required_properties": sorted(set(REQUIRED_RETURN_SLOTS) | {"source_execution_request_id_hash", "request_kind", "schema_name"}),
        "additional_properties_allowed": False,
        "per_slot_required_status": "proven",
        "field_validators": {
            "counterfactual_action_set": {"type": "array", "min_items": 2, "reject_values": ["unknown", "claimed", "claimed_only", "n/a", "none", "placeholder"]},
            "state_delta_codes": {"type": "array", "min_items": 1, "reject_values": ["unknown", "claimed", "claimed_only", "n/a", "none", "placeholder"]},
            "state_after_summary_codes": {"type": "array", "min_items": 1, "reject_values": ["unknown", "claimed", "claimed_only", "n/a", "none", "placeholder"]},
            "non_imitation_policy_action_label": {"type": "string", "reject_values": ["unknown", "claimed", "claimed_only", "n/a", "none", "placeholder"]},
        },
        "required_status_enums": {
            "same_source_lineage_proof": ["proven"],
            "verifier_relevance_proof": ["proven"],
            "policy_label_independence_status": ["proven_independent_not_observed_action_imitation"],
            "observed_action_imitation_status": ["not_imitation", "observed_but_independently_validated"],
            "causal_verifier_linkage": ["proven"],
            "protected_overlap_check": ["pass"],
            "leakage_check": ["pass"],
        },
        "reject_unknown_or_claimed_only_values": True,
        "non_empty_hash_fields_required": [
            "root_id_hash",
            "source_root_label_hash",
            "repo_family_hash",
            "split_group_id_hash",
            "root_lineage_key_hash",
            "ordered_event_refs_hash",
            "verifier_identity_hash",
        ],
    }
    admission_gate_contract = {
        "gate_name": "stage12445_adapter_execution_return_ingest_and_level3_gate_required",
        "can_increase_level3_candidate_count": True,
        "only_if_all_admission_required_slots_present": True,
        "reject_observed_action_imitation": True,
        "reject_policy_label_equals_observed_action_without_independent_counterfactual_proof": True,
        "require_per_slot_proof_status_proven": True,
        "reject_patch_verifier_copresence_without_causality": True,
        "reject_similarity_or_representative_membership_as_proof": True,
        "reject_raw_public_leakage": True,
    }
    external_contract = {
        "contract_name": "stage12444_external_adapter_materialization_contract_v1",
        "source_adapters_requested": [row.get("adapter_request_id") for row in adapter_requests],
        "adapter_request_count": len(adapter_requests),
        "representative_review_request_count": len(representatives),
        "open_swe_micro_pilot_request_count": len(open_swe_batch),
        "required_return_schema_hash": stable_hash(executor_return_schema),
        "admission_gate_contract_hash": stable_hash(admission_gate_contract),
    }
    artifact = {
        "stage": STAGE,
        "record_type": "adapter_execution_request_manifest_public_safe_v1",
        "decision": "adapter_execution_request_ready_no_execution_no_admission",
        **ZERO_COUNTERS,
        "source_fingerprints": {
            "stage12442_summary_sha256_24": file_hash(STAGE12442_SUMMARY),
            "stage12443_summary_sha256_24": file_hash(STAGE12443_SUMMARY),
            "source_adapter_request_sha256_24": file_hash(SOURCE_ADAPTER_REQUESTS),
            "representative_manifest_sha256_24": file_hash(REPRESENTATIVE_MANIFEST),
            "stage12413_replay_request_sha256_24": file_hash(STAGE12413_REPLAY),
        },
        "source_stage_gate_status": {
            "stage12442_guardrail_passed": stage12442.get("guardrail_scan_passed") is True,
            "stage12442_training_blocked": stage12442.get("training_allowed") is False,
            "stage12442_admission_blocked": stage12442.get("admission_allowed") is False,
            "stage12443_guardrail_passed": stage12443.get("guardrail_scan_passed") is True,
            "stage12443_private_review_ready_zero": int(stage12443.get("private_review_packet_ready_count", -1)) == 0,
        },
        "execution_request_count": len(requests) + len(open_swe_batch),
        "adapter_execution_request_count": len(adapter_requests),
        "requested_candidate_floor_total": requested_candidate_floor_total,
        "requested_candidate_floor_semantics": "aspirational_request_floor_not_demonstrated_supply_not_training_count",
        "demonstrated_accepted_row_floor": 0,
        "adapter_feasibility_evidence_attached": False,
        "requested_representative_private_review_rows": len(representatives),
        "requested_open_swe_micro_pilot_rows": len(open_swe_batch),
        "requested_external_repair_rows": 75,
        "requested_selected_test_transition_rows": 100,
        "requested_web_joiner_rows": 50,
        "requested_distinct_repo_floor": 120,
        "requested_language_floor": stage12442.get("target_language_floor") or {},
        "requested_by_kind": dict(sorted(requested_by_kind.items())),
        "schema_issue_count": len(schema_issues),
        "schema_issues": schema_issues,
        "raw_content_policy": RAW_CONTENT_POLICY,
        "executor_return_schema_path": "runs/local/artifacts/stage12444_adapter_execution_request_manifest/executor_return_schema.json",
        "admission_gate_contract_path": "runs/local/artifacts/stage12444_adapter_execution_request_manifest/admission_gate_contract.json",
        "adapter_execution_requests_path": "runs/local/artifacts/stage12444_adapter_execution_request_manifest/adapter_execution_requests.jsonl",
        "open_swe_authoritative_replay_batch_path": "runs/local/artifacts/stage12444_adapter_execution_request_manifest/open_swe_authoritative_replay_batch.jsonl",
        "expected_return_manifest_path": "runs/local/artifacts/stage12444_adapter_execution_request_manifest/expected_return_manifest.jsonl",
        "claim_boundary": "execution/materialization request only; this stage performs no execution and cannot emit admitted, Level-3, patch-trace, eval, or training rows",
        "next_stage_recommendation": "stage12445_adapter_execution_return_ingest_and_level3_gate",
        "summary_hash": "pending",
    }
    payloads = {
        "main": artifact,
        "adapter_execution_requests": requests,
        "open_swe_authoritative_replay_batch": open_swe_batch,
        "external_adapter_materialization_contract": external_contract,
        "executor_return_schema": executor_return_schema,
        "admission_gate_contract": admission_gate_contract,
    }
    issues = list(schema_issues)
    for name, payload in payloads.items():
        issues.extend(scan(name, payload))
    for key, expected in ZERO_COUNTERS.items():
        if artifact.get(key) != expected:
            issues.append(f"zero_counter_mismatch:{key}")
    if not all(artifact["source_stage_gate_status"].values()):
        issues.append("source_stage_gate_status_not_all_true")
    guardrail = {
        "scan_passed": not issues,
        "issue_count": len(set(issues)),
        "issues": sorted(set(issues)),
        "raw_leak_count": len({issue for issue in issues if ":raw_leak:" in issue or ":forbidden_public_key" in issue}),
        "overclaim_count": len({issue for issue in issues if ":overclaim:" in issue}),
        "scan_scope": "stage12444_public_safe_execution_request_manifest",
    }
    artifact["guardrail_scan"] = guardrail
    artifact["guardrail_scan_passed"] = guardrail["scan_passed"]
    artifact["raw_leak_count"] = guardrail["raw_leak_count"]
    artifact["overclaim_count"] = guardrail["overclaim_count"]
    artifact["summary_hash"] = stable_hash({k: v for k, v in artifact.items() if k != "summary_hash"})
    return artifact, requests, open_swe_batch, external_contract, executor_return_schema, admission_gate_contract


def main() -> None:
    artifact, requests, open_swe_batch, external_contract, executor_return_schema, admission_gate_contract = build_artifact()
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / f"{STAGE}.json", artifact)
    write_json(OUT / "summary.json", artifact)
    write_json(SUMMARY, artifact)
    expected_returns = [
        {
            "execution_request_id_hash": row["execution_request_id_hash"],
            "request_kind": row["request_kind"],
            "expected_return_path": row.get("expected_return_path"),
            "expected_return_schema": row.get("expected_return_schema"),
            "training_allowed": False,
            "admission_allowed": False,
        }
        for row in requests + open_swe_batch
    ]
    write_jsonl(OUT / "adapter_execution_requests.jsonl", requests)
    write_jsonl(OUT / "open_swe_authoritative_replay_batch.jsonl", open_swe_batch)
    write_jsonl(OUT / "expected_return_manifest.jsonl", expected_returns)
    write_json(OUT / "external_adapter_materialization_contract.json", external_contract)
    write_json(OUT / "executor_return_schema.json", executor_return_schema)
    write_json(OUT / "admission_gate_contract.json", admission_gate_contract)
    write_json(OUT / "guardrail_scan.json", artifact["guardrail_scan"])
    print(json.dumps({
        "stage": artifact["stage"],
        "decision": artifact["decision"],
        "execution_request_count": artifact["execution_request_count"],
        "requested_candidate_floor_total": artifact["requested_candidate_floor_total"],
        "requested_open_swe_micro_pilot_rows": artifact["requested_open_swe_micro_pilot_rows"],
        "requested_representative_private_review_rows": artifact["requested_representative_private_review_rows"],
        "training_allowed": artifact["training_allowed"],
        "admission_allowed": artifact["admission_allowed"],
        "execution_performed_by_stage": artifact["execution_performed_by_stage"],
        "level3_candidate_count": artifact["level3_candidate_count"],
        "guardrail_scan_passed": artifact["guardrail_scan_passed"],
        "raw_leak_count": artifact["raw_leak_count"],
        "overclaim_count": artifact["overclaim_count"],
        "schema_issue_count": artifact["schema_issue_count"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
