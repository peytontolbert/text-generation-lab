#!/usr/bin/env python3
"""Commit the current replay pilot before any verifier outcome is observed."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12562_pre_outcome_candidate_commitment"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
SOURCES = {
    "ready": ROOT / "runs/local/artifacts/stage12556_local_checkout_readiness_census/checkout_object_ready.jsonl",
    "authority": ROOT / "runs/local/artifacts/stage12554_authority_inventory_and_overlap_gate/resolved_authority_fields.jsonl",
    "task_bindings": ROOT / "runs/local/artifacts/stage12555_swe_rebench_identity_adapter/exact_task_authority_bindings.jsonl",
    "checkout_summary": ROOT / "runs/summaries/stage12556_local_checkout_readiness_census.json",
    "preflight_summary": ROOT / "runs/summaries/stage12557_private_train_replay_pilot.json",
    "scope_gate": ROOT / "runs/summaries/stage12561_active_protected_scope_gate.json",
    "frontier_decision": ROOT / "runs/summaries/stage11509_preservation_strengthened_frontier_promotion_decision.json",
    "runtime_bundle": ROOT / "runs/local/artifacts/stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json",
    "runtime_weights": ROOT / "runs/local/artifacts/stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/model_state.pt",
}
EXPECTED_WEIGHTS_SHA256 = "8bc717e1b3f7cf8321262d1a70f4ee86489a6fb10e6ae3f16eb6646f72b3ad37"
ZERO = {"admission_allowed": False, "training_allowed": False, "replay_allowed": False,
        "root_credit": False, "repair_credit": False, "level3_credit": False,
        "strict_eval_eligible": False, "gpu_allowed": False}


def file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build(ready: list[dict[str, Any]], preflight: dict[str, Any], scope: dict[str, Any],
          runtime_bundle: dict[str, Any], source_hashes: dict[str, str | None], *, created_at_utc: str) -> dict[str, Any]:
    candidate_ids = [str(row.get("candidate_id") or "") for row in ready]
    task_keys = [row.get("task_key") for row in ready]
    blockers: list[str] = []
    if not ready or any(not item for item in candidate_ids) or len(candidate_ids) != len(set(candidate_ids)):
        blockers.append("candidate_list_empty_missing_or_duplicate")
    if preflight.get("executed_count") != 0 or preflight.get("level3_count_increment") != 0:
        blockers.append("replay_outcome_already_present")
    if scope.get("active_scope_clearance") is not False or scope.get("sandbox_progression_allowed") is not False:
        blockers.append("scope_gate_expected_fail_closed_state_missing")
    if runtime_bundle.get("weights_sha256") != EXPECTED_WEIGHTS_SHA256:
        blockers.append("selected_model_identity_unresolved_or_changed")
    if source_hashes.get("runtime_weights") != EXPECTED_WEIGHTS_SHA256:
        blockers.append("selected_model_weights_digest_mismatch")
    if any(value is None for value in source_hashes.values()):
        blockers.append("commitment_source_missing")

    payload = {
        "schema": "pre_outcome_candidate_commitment_v1",
        "candidate_ids": sorted(candidate_ids),
        "task_keys": sorted(task_keys, key=lambda item: json.dumps(item, sort_keys=True)),
        "selected_model": {"runtime_stage": 11507, "scorer": "encoder_option_retrieval_evidence_judgment_head",
                           "weights_sha256": EXPECTED_WEIGHTS_SHA256},
        "selection_algorithm": "all_stage12556_exact_checkout_object_ready_train_rows_sorted_by_candidate_id",
        "allowed_selection_features": ["policy_split_train", "exact_authority_join", "checkout_object_closure", "verifier_contract_presence"],
        "forbidden_selection_features": ["verifier_exit", "test_output", "patch_effect", "reward", "model_prediction", "protected_target", "gold_patch"],
        "source_sha256": dict(sorted(source_hashes.items())),
    }
    commitment_valid = not blockers
    return {
        "record_type": "stage12562_pre_outcome_candidate_commitment_v1",
        "created_at_utc": created_at_utc,
        "commitment_sha256": stable_hash(payload),
        "commitment_payload": payload,
        "candidate_count": len(candidate_ids),
        "pre_outcome_commitment_valid": commitment_valid,
        "blocking_reasons": sorted(set(blockers)),
        "execution_authorized": False,
        "legacy_deny_gate_still_required": True,
        **ZERO,
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    source_hashes = {name: file_sha256(path) for name, path in SOURCES.items()}
    existing = read_json(SUMMARY) if SUMMARY.is_file() else {}
    created = str(existing.get("created_at_utc") or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"))
    result = build(read_jsonl(SOURCES["ready"]), read_json(SOURCES["preflight_summary"]),
                   read_json(SOURCES["scope_gate"]), read_json(SOURCES["runtime_bundle"]),
                   source_hashes, created_at_utc=created)
    write_json(OUT / "candidate_commitment.json", result)
    write_json(OUT / "summary.json", result)
    write_json(SUMMARY, result)
    print(json.dumps({key: result[key] for key in ("candidate_count", "pre_outcome_commitment_valid", "commitment_sha256", "blocking_reasons", "execution_authorized")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
