#!/usr/bin/env python3
"""Build Stage12524 private executor readiness manifests only when proven.

Stage12525 is a public-safe bridge from existing ai_env/private extraction
readiness artifacts to the two status-only manifests Stage12524 requires under
Stage12521. It is fail-closed: if resolver/executor binding is not already
proven by prior artifacts, it emits blockers and writes no Stage12521 manifests.

It never invokes a private executor, writes executor returns, writes Stage12516
candidates, writes Stage12503 rows, admits rows, emits training, materializes
Level-3 atoms, or emits patch-trace/source/verifier material.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12525_private_executor_readiness_manifest_builder"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12510 = "stage12510_ai_env_private_extraction_executor_readiness_audit"
STAGE12513 = "stage12513_conservative_ai_env_private_semantic_candidate_extractor"
STAGE12521 = "stage12521_private_causal_evidence_executor_handoff_contract"
STAGE12523 = "stage12523_private_executor_return_fixture_contract"
STAGE12524 = "stage12524_private_executor_invocation_readiness_audit"

SLOT_COUNT = 343
RETURN_FILENAME = "private_causal_evidence_executor_returns.jsonl"
RESOLVER_MANIFEST = "private_executor_resolver_readiness_manifest.json"
EXECUTOR_MANIFEST = "private_executor_runtime_readiness_manifest.json"

FALSE_GUARDS = {
    "candidate_returns_written": False,
    "validated_returns_written": False,
    "stage12516_candidate_rows_written": False,
    "stage12503_return_file_written": False,
    "training_allowed": False,
    "admission_allowed": False,
    "packaging_allowed": False,
    "execution_performed_by_stage": False,
    "hydration_performed_by_stage": False,
    "replay_performed_by_stage": False,
    "network_performed_by_stage": False,
    "policy_label_materialized": False,
    "level3_atom_materialized": False,
    "patch_trace_materialized": False,
    "proof_admission_allowed": False,
    "raw_source_output_included": False,
    "raw_private_values_revealed": False,
    "status_hash_as_proof_allowed": False,
    "digest_hash_as_proof_allowed": False,
    "observed_action_imitation_allowed": False,
    "pass_to_pass_repair_credit_allowed": False,
    "root_or_window_hash_unique_key_allowed": False,
    "dedupe_dropped_slots": False,
    "validated_present_fabricated": False,
    "blocked_unavailable_fabricated": False,
    "executor_return_rows_fabricated": False,
}
ZERO_GUARDS = {
    "candidate_return_records_written": 0,
    "validated_return_records_written": 0,
    "stage12516_candidate_row_count": 0,
    "stage12503_return_records_written": 0,
    "training_rows_emitted": 0,
    "admitted_rows": 0,
    "level3_admitted": 0,
    "level3_atom_count": 0,
    "patch_trace_admitted": 0,
    "patch_trace_rows": 0,
    "policy_labels_emitted": 0,
    "proof_rows_emitted": 0,
    "executor_return_records_written": 0,
}
IDENTITY_FIELDS = [
    "revalidation_id_hash",
    "request_id_hash",
    "work_item_id_hash",
    "packet_id_hash",
    "root_or_window_hash",
    "source_stage",
    "source_kind",
    "language_family",
    "task_family",
    "evidence_slot",
    "proof_class",
]
FULL_SEVEN_SLOTS = [
    "same_source_causal_lineage_with_independent_evidence_digest",
    "structured_state_before_codes",
    "state_delta_or_state_after_codes",
    "patch_apply_or_no_patch_status",
    "stop_continue_policy_label",
    "independent_policy_label_and_candidate_action_set",
    "external_patch_effect_or_no_patch_reason",
]

RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:git clone|git apply|pytest\s|python -c|bash -|sh -|curl\s|"
    r"stdout|stderr|traceback|terminal output|command output|verifier output|commit:)\b|"
    r"\b[0-9a-f]{40}\b",
    re.IGNORECASE | re.MULTILINE,
)
FORBIDDEN_PUBLIC_KEYS = {
    "raw",
    "raw_output",
    "raw_outputs",
    "raw_diff",
    "diff",
    "patch",
    "command",
    "commands",
    "cmd",
    "path",
    "paths",
    "file_path",
    "source_text",
    "source_content",
    "verifier_output",
    "stdout",
    "stderr",
    "terminal_output",
    "policy_label",
    "policy_label_hash",
    "training_row",
    "training_rows",
    "admitted_row",
    "level3_atom",
    "patch_trace",
    "proof_row",
}


class RawLeakError(ValueError):
    pass


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


def scan_raw_leaks(value: Any) -> list[str]:
    issues: list[str] = []
    if isinstance(value, str):
        if RAW_LEAK_RE.search(value):
            issues.append(stable_hash(value))
    elif isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_PUBLIC_KEYS:
                issues.append(stable_hash({"forbidden_key": key}))
            issues.extend(scan_raw_leaks(child))
    elif isinstance(value, list):
        for child in value:
            issues.extend(scan_raw_leaks(child))
    return issues


def enforce_no_raw_leaks(value: Any) -> None:
    issues = scan_raw_leaks(value)
    if issues:
        raise RawLeakError(f"stage12525 raw leak guard rejected {len(issues)} public field(s)")


def _safe_str(row: dict[str, Any], field: str) -> str:
    value = row.get(field)
    return value if isinstance(value, str) else ""


def _slot_identity(row: dict[str, Any]) -> tuple[str, ...]:
    return tuple(_safe_str(row, field) for field in ["acquisition_work_order_id_hash", *IDENTITY_FIELDS])


def flatten_slot_refs(shards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        slot_ref
        for shard in shards
        for slot_ref in (shard.get("slot_refs") or [])
        if isinstance(slot_ref, dict)
    ]


def prior_artifacts(root: Path) -> dict[str, Any]:
    artifacts = root / "runs/local/artifacts"
    summaries = root / "runs/summaries"
    return {
        "stage12510_summary": read_json(artifacts / STAGE12510 / "summary.json")
        or read_json(summaries / f"{STAGE12510}.json"),
        "stage12513_summary": read_json(artifacts / STAGE12513 / "summary.json")
        or read_json(summaries / f"{STAGE12513}.json"),
        "stage12521_summary": read_json(artifacts / STAGE12521 / "summary.json")
        or read_json(summaries / f"{STAGE12521}.json"),
        "stage12523_summary": read_json(artifacts / STAGE12523 / "summary.json")
        or read_json(summaries / f"{STAGE12523}.json"),
        "stage12524_summary": read_json(artifacts / STAGE12524 / "summary.json")
        or read_json(summaries / f"{STAGE12524}.json"),
        "stage12524_blockers": read_jsonl(artifacts / STAGE12524 / "private_executor_invocation_readiness_blockers.jsonl"),
        "stage12521_shards": read_jsonl(artifacts / STAGE12521 / "private_causal_evidence_executor_handoff_shards.jsonl"),
        "stage12523_slots": read_jsonl(artifacts / STAGE12523 / "private_executor_return_fixture_contract_slots.jsonl"),
        "stage12523_runbook": read_json(artifacts / STAGE12523 / "private_executor_return_acquisition_runbook.json"),
    }


def readiness_blockers(artifacts: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    s10 = artifacts["stage12510_summary"]
    s13 = artifacts["stage12513_summary"]
    s21 = artifacts["stage12521_summary"]
    s23 = artifacts["stage12523_summary"]
    s24 = artifacts["stage12524_summary"]
    shards = artifacts["stage12521_shards"]
    slots = artifacts["stage12523_slots"]
    runbook = artifacts["stage12523_runbook"]
    shard_refs = flatten_slot_refs(shards)

    if s10.get("authorized_executor_binding_count") != 1 or s10.get("executor_ready_count") != s10.get("input_work_order_count"):
        counts = s10.get("blocker_code_counts")
        if isinstance(counts, dict) and counts:
            blockers.extend(str(code) for code in sorted(counts))
        else:
            blockers.extend([
                "trusted_ai_env_private_extractor_binding_missing",
                "no_authorized_stage12503_return_writer_configured",
            ])
    if s10.get("executor_blocker_count", 0) != 0:
        blockers.append("stage12510_executor_blockers_present")
    if s10.get("stage12503_return_records_written") != 0:
        blockers.append("stage12510_claims_stage12503_returns_written")

    if s13.get("candidate_output_written") is not True or s13.get("candidate_return_count", 0) <= 0:
        blockers.append("stage12513_status_only_candidate_output_missing")
    if s13.get("stage12503_return_records_written") != 0:
        blockers.append("stage12513_claims_stage12503_returns_written")
    if s13.get("training_rows_emitted") != 0 or s13.get("admitted_rows") != 0:
        blockers.append("stage12513_claims_training_or_admission")

    if len(slots) != SLOT_COUNT:
        blockers.append("stage12523_contract_slot_count_not_343")
    if len(shard_refs) != SLOT_COUNT:
        blockers.append("stage12521_handoff_slot_ref_count_not_343")
    if len({_slot_identity(row) for row in slots}) != SLOT_COUNT:
        blockers.append("stage12523_slot_identity_count_not_343")
    if Counter(_slot_identity(row) for row in slots) != Counter(_slot_identity(row) for row in shard_refs):
        blockers.append("stage12521_stage12523_slot_identity_mismatch")
    if set(_safe_str(row, "evidence_slot") for row in slots) != set(FULL_SEVEN_SLOTS):
        blockers.append("stage12523_full_seven_slot_set_missing")
    if s21.get("candidate_return_records_written") != 0 or s21.get("training_rows_emitted") != 0 or s21.get("admitted_rows") != 0:
        blockers.append("stage12521_claims_returns_training_or_admission")
    if s23 and s23.get("training_rows_emitted", 0) != 0:
        blockers.append("stage12523_claims_training")
    if runbook.get("executor_return_file_must_be_placed_under_stage12521") != RETURN_FILENAME:
        blockers.append("stage12523_expected_return_filename_mismatch")

    s24_codes = s24.get("readiness_blocker_codes")
    if s24_codes and sorted(s24_codes) != ["private_executor_manifest_missing", "private_resolver_manifest_missing"]:
        blockers.append("stage12524_has_non_manifest_readiness_blockers")
    if artifacts["stage12524_blockers"] and len(artifacts["stage12524_blockers"]) != SLOT_COUNT:
        blockers.append("stage12524_blocker_row_count_not_343")

    return sorted(set(blockers))


def blocker_rows(blockers: list[str], artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    slots = artifacts["stage12523_slots"] or [{}]
    rows = []
    for idx, slot in enumerate(slots, start=1):
        row = {
            "record_type": "stage12525_private_executor_readiness_manifest_blocker_v1",
            "readiness_manifest_blocker_id_hash": stable_hash({"slot": _slot_identity(slot), "codes": blockers, "idx": idx}),
            **{field: slot.get(field) for field in ["acquisition_work_order_id_hash", *IDENTITY_FIELDS]},
            "stage12523_fixture_contract_slot_id_hash": slot.get("fixture_contract_slot_id_hash"),
            "blocker_codes": blockers,
            "manifests_written": False,
            "public_safe_status_only": True,
            **FALSE_GUARDS,
            **ZERO_GUARDS,
        }
        enforce_no_raw_leaks(row)
        rows.append(row)
    return rows


def build_manifests(artifacts: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    slot_ids = sorted(_slot_identity(row) for row in artifacts["stage12523_slots"])
    evidence_slot_counts = Counter(_safe_str(row, "evidence_slot") for row in artifacts["stage12523_slots"])
    common = {
        "source_stage": STAGE,
        "source_readiness_stages": [STAGE12510, STAGE12513, STAGE12521, STAGE12523, STAGE12524],
        "stage12525_manifest_builder_id_hash": stable_hash({"slot_ids": slot_ids, "stage12510": artifacts["stage12510_summary"].get("decision")}),
        "public_safe_status_only": True,
        "slot_identity_count": SLOT_COUNT,
        "dedupe_dropped_slot_count": 0,
        "root_hash_dedupe_performed": False,
        "full_seven_slot_set_seen": True,
        "evidence_slot_counts": dict(sorted(evidence_slot_counts.items())),
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    resolver = {
        "record_type": "stage12524_private_executor_resolver_readiness_manifest_v1",
        "readiness_manifest_id_hash": stable_hash({"manifest": "resolver", "slot_ids": slot_ids}),
        "private_resolver_ready": True,
        "private_locator_inputs_available": True,
        "resolver_slot_count": SLOT_COUNT,
        **common,
    }
    executor = {
        "record_type": "stage12524_private_executor_runtime_readiness_manifest_v1",
        "readiness_manifest_id_hash": stable_hash({"manifest": "executor", "slot_ids": slot_ids}),
        "private_executor_ready": True,
        "supports_stage12516_return_schema": True,
        "executor_slot_count": SLOT_COUNT,
        "expected_executor_return_filename": RETURN_FILENAME,
        **common,
    }
    enforce_no_raw_leaks({"resolver": resolver, "executor": executor})
    return resolver, executor


def build(root: Path = ROOT) -> dict[str, Any]:
    out = root / "runs/local/artifacts" / STAGE
    out.mkdir(parents=True, exist_ok=True)
    artifacts = prior_artifacts(root)
    enforce_no_raw_leaks(artifacts)
    blockers = readiness_blockers(artifacts)
    ready = not blockers
    rows = [] if ready else blocker_rows(blockers, artifacts)

    stage12521_out = root / "runs/local/artifacts" / STAGE12521
    if ready:
        resolver, executor = build_manifests(artifacts)
        write_json(stage12521_out / RESOLVER_MANIFEST, resolver)
        write_json(stage12521_out / EXECUTOR_MANIFEST, executor)

    summary = {
        "stage": STAGE,
        "record_type": "stage12525_private_executor_readiness_manifest_builder_summary_v1",
        "decision": (
            "ready_public_safe_private_executor_readiness_manifests_written"
            if ready
            else "blocked_unproven_private_executor_readiness_no_manifests_written"
        ),
        "claim_boundary": (
            "Stage12525 builds only the two public-safe Stage12524 readiness manifests when prior "
            "ai_env/private extraction artifacts already prove binding and 343-slot accounting. "
            "It writes no executor returns, Stage12516 candidates, Stage12503 rows, training, "
            "admission, Level-3, patch-trace, raw source, raw command, raw path, diff, or verifier material."
        ),
        "source_stages": [STAGE12510, STAGE12513, STAGE12521, STAGE12523, STAGE12524],
        "target_stage": STAGE12521,
        "target_manifest_roles": [RESOLVER_MANIFEST, EXECUTOR_MANIFEST],
        "manifest_slot_count_required": SLOT_COUNT,
        "input_stage12521_slot_ref_count": len(flatten_slot_refs(artifacts["stage12521_shards"])),
        "input_stage12523_contract_slot_count": len(artifacts["stage12523_slots"]),
        "preserved_slot_identity_count": len({_slot_identity(row) for row in artifacts["stage12523_slots"]}),
        "dedupe_dropped_slot_count": 0,
        "root_hash_dedupe_performed": False,
        "readiness_blocker_codes": blockers,
        "readiness_blocker_count": len(blockers),
        "readiness_blocker_row_count": len(rows),
        "private_executor_readiness_manifests_written": ready,
        "private_resolver_manifest_written": ready,
        "private_executor_manifest_written": ready,
        "expected_stage12521_return_row_count": SLOT_COUNT if ready else 0,
        "guardrail_scan_passed": True,
        "raw_leak_count": 0,
        "next_stage": "rerun_stage12524" if ready else "prove_private_resolver_and_executor_binding_then_rerun_stage12525",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    guardrail = {
        "stage": STAGE,
        "scan_passed": True,
        "raw_leak_count": 0,
        "raw_leak_issue_hashes": [],
        "scanned_outputs": [
            "private_executor_readiness_manifest_blockers.jsonl",
            "summary.json",
        ],
    }
    enforce_no_raw_leaks({"rows": rows, "summary": summary, "guardrail": guardrail})
    write_jsonl(out / "private_executor_readiness_manifest_blockers.jsonl", rows)
    write_json(out / "guardrail_scan.json", guardrail)
    write_json(out / "summary.json", summary)
    write_json(root / "runs/summaries" / f"{STAGE}.json", summary)
    return summary


def main() -> None:
    build(ROOT)


if __name__ == "__main__":
    main()
