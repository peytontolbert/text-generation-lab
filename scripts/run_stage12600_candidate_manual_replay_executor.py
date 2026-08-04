#!/usr/bin/env python3
"""Stage12600 candidate execution-capable manual replay runner source.

This source contains the reviewable execution machinery for a later manual
trusted replay. Stage12600 itself does not execute replay: the public CLI rejects
--execute until an independent execution-capable source review and a separate
execution gate authorize a later run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
S12593 = ROOT / "runs/local/artifacts/stage12593_private_static_verifier_binding_sidecar"
S12594 = ROOT / "runs/local/artifacts/stage12594_trusted_external_causal_replay_runner_preflight"
S12595 = ROOT / "runs/local/artifacts/stage12595_trusted_replay_execution_handoff"
S12599 = ROOT / "runs/local/artifacts/stage12599_execution_gate_intake_preflight_only_blocked"
EXPECTED_STAGE12599_SUMMARY = "6a5ed072fc33aced1288ea43b300fe20c496c562dfa537ba1f6bebe316f89f8e"
EXPECTED_STAGE12599_POINTER = "2a34e0d27e891046fe3c389e355f0dbd5d3784b9b5d0c26b18dedde2f2e2530e"
EXPECTED_STAGE12599_GATE_INTAKE = "92de5529cc55773d0413f108e2d4683fa1f47efa04901b0b8087b14157ccde35"
EXPECTED_STAGE12594_GENERATION = "91d0cda6e9acdf2e09c4d04b7d8e00159351bedf1ef0e7f70c4912d48c34475d"
EXPECTED_STAGE12594_MANIFEST = "5f5353b63591f77433a6a0a01141211796906ef13c02c2569c48f65a59c5a856"
EXPECTED_STAGE12594_SNAPSHOT_CONTRACT = "17130ae5d936f9cbf0f5905a9a1b1f662de1a2f8fb718715e74b8b1ffd6463d2"
EXPECTED_STAGE12595_HANDOFF = "9b2b276ae0ac327ff02a9effa71ee0e59069be2a4e53c1e2100bc2ab9c4d2e75"
EXPECTED_STAGE12595_SLOTS = "8ddfdfb0872c8cb74a46f0041801bced7e674228d74af98b30ce7631afebe3a0"
EXPECTED_STAGE12593_BLUEPRINTS = "801c80cc8d8d51972bef4ecb6fdef8c2eadba9400590bd2724a152d211cd3944"
EXPECTED_STAGE12598_TRANSCRIPT = "00abcd7749987123c810b76e432f1983ab5dc8b72a6c19a78b24bdff534719f9"
FALSE_FIELDS = (
    "implementation_ready", "stage12595_allowed", "authorizes_execution",
    "execution_allowed", "execution_performed", "replay_trustworthy",
    "level_3_materialized", "training_admitted", "strict_eval_admitted", "sealed_eval_admitted",
    "strict_eval_eligible", "sealed_eval_eligible", "admission_allowed", "training_allowed",
    "ranking_allowed", "positive_stop",
)
REQUIRED_CONTROLS = (
    "load_stage12594_generation_and_verify_manifest_before_execution",
    "verify_stage12595_slots_hash_before_any_materialization",
    "verify_stage12598_source_review_transcript_before_any_materialization",
    "create_no_local_no_hardlinks_detached_snapshot",
    "rerun_namespace_manifest_match_before_material_read",
    "run_initial_patched_final_phases_inside_hardened_bwrap",
    "capture_full_pytest_phase_reports_and_raw_stream_digests",
    "assert_patched_only_changes_bound_production_path",
    "assert_final_reverts_to_initial_failure_fingerprint",
    "publish_private_raw_evidence_only_after_public_leak_scan",
)
STAGE12595_SLOT_CONTROLS = (
    "load_stage12594_generation_and_verify_manifest_before_execution",
    "create_no_local_no_hardlinks_detached_snapshot",
    "rerun_namespace_manifest_match_before_material_read",
    "run_initial_patched_final_phases_inside_hardened_bwrap",
    "capture_full_pytest_phase_reports_and_raw_stream_digests",
    "assert_patched_only_changes_bound_production_path",
    "assert_final_reverts_to_initial_failure_fingerprint",
    "publish_private_raw_evidence_only_after_public_leak_scan",
)
IMPLEMENTED_REVIEWABLE_FUNCTIONS = (
    "load_stage12594_snapshot_contract",
    "load_stage12595_manual_slots",
    "validate_production_path",
    "verify_patch_artifact",
    "build_execution_command_manifest",
    "create_detached_snapshot",
    "run_pytest_phase_inside_hardened_bwrap",
    "execute_reviewed_slot",
)
PHASES = ("initial", "patched", "final")
RESERVED_ENV = ("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "PYTHONHASHSEED", "NO_COLOR")


class GateError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def stable_hash(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GateError("json_object_required:" + path.name)
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise GateError(f"jsonl_object_required:{path.name}:{number}")
        rows.append(value)
    return rows


def no_claim_fields() -> dict[str, Any]:
    return {
        "implementation_ready": False,
        "stage12595_allowed": False,
        "authorizes_execution": False,
        "execution_allowed": False,
        "execution_performed": False,
        "replay_trustworthy": False,
        "level_3_materialized": False,
        "training_admitted": False,
        "strict_eval_admitted": False,
        "sealed_eval_admitted": False,
        "strict_eval_eligible": False,
        "sealed_eval_eligible": False,
        "admission_allowed": False,
        "training_allowed": False,
        "ranking_allowed": False,
        "positive_stop": False,
    }


def check_false(record: Mapping[str, Any], label: str) -> None:
    for field in FALSE_FIELDS:
        if field in record and record[field] is not False:
            raise GateError(f"{label}_gate_drift:{field}")


def require_authorized_execution_gate(gate: Mapping[str, Any]) -> None:
    if gate.get("independent_execution_capable_source_review_present") is not True:
        raise GateError("independent_execution_capable_source_review_required")
    if gate.get("reviewed_execution_capable_source_present") is not True:
        raise GateError("reviewed_execution_capable_source_required")
    if gate.get("execution_gate_granted") is not True:
        raise GateError("execution_gate_grant_required")
    if gate.get("execution_request_ready_count") != 2:
        raise GateError("exact_two_execution_requests_required")


def load_stage12599(root: Path = S12599) -> dict[str, Any]:
    summary = read_json(root / "summary.json")
    pointer = read_json(root / "digest_pointer.json")
    gate_intake = read_json(root / "private/execution_gate_intake.json")
    if stable_hash(summary) != EXPECTED_STAGE12599_SUMMARY:
        raise GateError("stage12599_summary_pin_drift")
    if stable_hash(pointer) != EXPECTED_STAGE12599_POINTER:
        raise GateError("stage12599_pointer_pin_drift")
    if stable_hash(gate_intake) != EXPECTED_STAGE12599_GATE_INTAKE:
        raise GateError("stage12599_gate_intake_pin_drift")
    if summary.get("decision") != "BLOCKED_EXECUTION_CAPABLE_SOURCE_REQUIRED":
        raise GateError("stage12599_decision_mismatch")
    if summary.get("execution_gate_granted") is not False:
        raise GateError("stage12599_gate_granted_drift")
    if summary.get("execution_request_ready_count") != 0:
        raise GateError("stage12599_execution_request_count_drift")
    if summary.get("stage12594_publication_generation_id") != EXPECTED_STAGE12594_GENERATION:
        raise GateError("stage12599_generation_drift")
    if summary.get("stage12594_publication_manifest_sha256") != EXPECTED_STAGE12594_MANIFEST:
        raise GateError("stage12599_manifest_drift")
    if summary.get("stage12595_slots_sha256") != EXPECTED_STAGE12595_SLOTS:
        raise GateError("stage12599_slots_drift")
    if summary.get("source_review_transcript_sha256") != EXPECTED_STAGE12598_TRANSCRIPT:
        raise GateError("stage12599_review_transcript_drift")
    for label, record in (("summary", summary), ("pointer", pointer), ("gate_intake", gate_intake)):
        check_false(record, "stage12599_" + label)
    return {"summary": summary, "pointer": pointer, "gate_intake": gate_intake}


def load_stage12594_snapshot_contract(root: Path = S12594) -> dict[str, Any]:
    manifest = read_json(root / "publication_manifest.json")
    snapshot = read_json(root / "private/pinned_snapshot_contract.json")
    blueprints = read_jsonl(S12593 / "nonexecuting_replay_blueprints.jsonl")
    if manifest.get("publication_generation_id") != EXPECTED_STAGE12594_GENERATION:
        raise GateError("stage12594_generation_drift")
    if manifest.get("manifest_sha256") != EXPECTED_STAGE12594_MANIFEST:
        raise GateError("stage12594_manifest_pin_drift")
    if stable_hash(snapshot) != EXPECTED_STAGE12594_SNAPSHOT_CONTRACT:
        raise GateError("stage12594_snapshot_contract_pin_drift")
    if stable_hash(blueprints) != EXPECTED_STAGE12593_BLUEPRINTS:
        raise GateError("stage12593_blueprint_pin_drift")
    if snapshot.get("binding_count") != 2 or len(snapshot.get("binding_snapshots", [])) != 2:
        raise GateError("stage12594_snapshot_binding_count_drift")
    if snapshot.get("snapshot_requirements", {}).get("clone_lifecycle") != "git_clone_no_local_no_hardlinks_detached_v1":
        raise GateError("stage12594_clone_lifecycle_drift")
    for label, record in (("manifest", manifest), ("snapshot", snapshot), *[(f"blueprint_{i}", row) for i, row in enumerate(blueprints, 1)]):
        check_false(record, "stage12594_" + label)
    return {"manifest": manifest, "snapshot": snapshot, "blueprints": blueprints}


def load_stage12595_manual_slots(root: Path = S12595) -> dict[str, Any]:
    handoff = read_json(root / "private/manual_replay_execution_handoff.json")
    slots = read_jsonl(root / "private/manual_replay_execution_slots.jsonl")
    if stable_hash(handoff) != EXPECTED_STAGE12595_HANDOFF:
        raise GateError("stage12595_handoff_pin_drift")
    if stable_hash(slots) != EXPECTED_STAGE12595_SLOTS:
        raise GateError("stage12595_slots_pin_drift")
    if handoff.get("manual_executor_review_required") is not True:
        raise GateError("stage12595_review_requirement_missing")
    if handoff.get("slot_count") != 2 or len(slots) != 2:
        raise GateError("stage12595_slot_count_drift")
    for ordinal, row in enumerate(slots, 1):
        if row.get("slot_ordinal") != ordinal:
            raise GateError("stage12595_slot_order_drift")
        if row.get("stage12594_publication_generation_id") != EXPECTED_STAGE12594_GENERATION:
            raise GateError("stage12595_generation_drift")
        if tuple(row.get("manual_executor_required_controls", ())) != STAGE12595_SLOT_CONTROLS:
            raise GateError("stage12595_required_controls_drift")
        validate_production_path(str(row.get("production_path")))
    for label, record in (("handoff", handoff), *[(f"slot_{i}", row) for i, row in enumerate(slots, 1)]):
        check_false(record, "stage12595_" + label)
    return {"handoff": handoff, "slots": slots}


def validate_production_path(value: str) -> str:
    if not isinstance(value, str):
        raise GateError("production_path_string_required")
    if value in ("", ".", ".."):
        raise GateError("production_path_empty_or_dot")
    if "\x00" in value or "\\" in value:
        raise GateError("production_path_forbidden_byte")
    if value.startswith("/") or value.endswith("/") or "//" in value:
        raise GateError("production_path_not_descriptor_safe")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise GateError("production_path_unsafe_component")
    return value


def verify_patch_artifact(slot: Mapping[str, Any], patch_path: Path) -> dict[str, Any]:
    if not patch_path.is_file():
        raise GateError("patch_artifact_regular_file_required")
    expected = slot.get("production_patch_sha256")
    actual = sha256_file(patch_path)
    if actual != expected:
        raise GateError("patch_artifact_digest_mismatch")
    return {
        "slot_ordinal": slot["slot_ordinal"],
        "production_path": validate_production_path(str(slot["production_path"])),
        "production_patch_sha256": actual,
    }


def build_phase_command(phase: str, node_ids: Sequence[str]) -> list[str]:
    if phase not in PHASES:
        raise GateError("unknown_phase:" + phase)
    if not node_ids:
        raise GateError("phase_node_ids_required")
    return [sys.executable, "-m", "pytest", "--json-report", "--json-report-file", f"reports/{phase}.json", *node_ids]


def build_bwrap_command(snapshot_root: Path, phase: str, node_ids: Sequence[str]) -> list[str]:
    command = build_phase_command(phase, node_ids)
    return [
        "bwrap", "--unshare-all", "--die-with-parent", "--new-session", "--clearenv",
        "--setenv", "PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1",
        "--setenv", "PYTHONHASHSEED", "0",
        "--setenv", "NO_COLOR", "1",
        "--ro-bind", "/usr", "/usr",
        "--ro-bind", "/bin", "/bin",
        "--ro-bind", "/lib", "/lib",
        "--ro-bind", "/lib64", "/lib64",
        "--dev", "/dev",
        "--proc", "/proc",
        "--tmpfs", "/tmp",
        "--bind", str(snapshot_root), str(snapshot_root),
        "--chdir", str(snapshot_root),
        *command,
    ]


def blueprint_for_slot(slot: Mapping[str, Any], blueprints: Iterable[Mapping[str, Any]]) -> Mapping[str, Any]:
    ref = "binding_" + str(slot["binding_payload_sha256"])[:24]
    for blueprint in blueprints:
        if blueprint.get("binding_ref") == ref:
            return blueprint
    raise GateError("stage12593_blueprint_for_slot_missing")


def blueprint_node_ids(blueprint: Mapping[str, Any]) -> list[str]:
    run_steps = [step for step in blueprint.get("protocol", []) if str(step.get("action", "")).startswith("run_")]
    if len(run_steps) != 3:
        raise GateError("stage12593_phase_count_drift")
    digest = run_steps[0].get("expected_node_ids_sha256")
    if any(step.get("expected_node_ids_sha256") != digest for step in run_steps):
        raise GateError("stage12593_phase_node_digest_drift")
    return ["@" + str(digest)]


def build_execution_command_manifest(
    stage12594: Mapping[str, Any],
    stage12595: Mapping[str, Any],
    patch_root: Path,
    evidence_root: Path,
) -> dict[str, Any]:
    rows = []
    for slot in stage12595["slots"]:
        patch_info = verify_patch_artifact(slot, patch_root / f"slot_{slot['slot_ordinal']}.patch")
        blueprint = blueprint_for_slot(slot, stage12594["blueprints"])
        node_ids = blueprint_node_ids(blueprint)
        rows.append({
            "slot_ordinal": slot["slot_ordinal"],
            "binding_payload_sha256": slot["binding_payload_sha256"],
            "before_commit_oid": slot["before_commit_oid"],
            "after_commit_oid": slot["after_commit_oid"],
            "production_path": patch_info["production_path"],
            "production_patch_sha256": patch_info["production_patch_sha256"],
            "namespace_input_manifest_sha256": slot["namespace_input_manifest_sha256"],
            "snapshot_lifecycle": "git_clone_no_local_no_hardlinks_detached_v1",
            "phase_sequence": list(PHASES),
            "phase_commands": {phase: build_bwrap_command(evidence_root / f"slot_{slot['slot_ordinal']}" / "snapshot", phase, node_ids)
                               for phase in PHASES},
        })
    return {
        "record_type": "stage12600_candidate_execution_command_manifest_v1",
        "stage12594_publication_generation_id": EXPECTED_STAGE12594_GENERATION,
        "stage12594_publication_manifest_sha256": EXPECTED_STAGE12594_MANIFEST,
        "stage12595_slots_sha256": EXPECTED_STAGE12595_SLOTS,
        "slot_count": len(rows),
        "slots": rows,
        "reserved_environment_keys": list(RESERVED_ENV),
    }


def run_command(argv: Sequence[str], cwd: Path | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(list(argv), cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def create_detached_snapshot(repository_root: Path, destination: Path, before_commit_oid: str) -> None:
    if destination.exists():
        raise GateError("snapshot_destination_must_not_exist")
    clone = run_command(["git", "clone", "--no-local", "--no-hardlinks", "--no-checkout", str(repository_root), str(destination)])
    if clone.returncode != 0:
        raise GateError("git_clone_failed")
    checkout = run_command(["git", "checkout", "--detach", before_commit_oid], cwd=destination)
    if checkout.returncode != 0:
        raise GateError("git_checkout_failed")


def write_raw_phase_evidence(evidence_dir: Path, phase: str, result: subprocess.CompletedProcess[bytes]) -> dict[str, Any]:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = evidence_dir / f"{phase}.stdout.raw"
    stderr_path = evidence_dir / f"{phase}.stderr.raw"
    stdout_path.write_bytes(result.stdout)
    stderr_path.write_bytes(result.stderr)
    return {
        "phase": phase,
        "returncode": result.returncode,
        "stdout_sha256": sha256_file(stdout_path),
        "stderr_sha256": sha256_file(stderr_path),
    }


def run_pytest_phase_inside_hardened_bwrap(snapshot_root: Path, phase: str, node_ids: Sequence[str], evidence_dir: Path) -> dict[str, Any]:
    result = run_command(build_bwrap_command(snapshot_root, phase, node_ids))
    return write_raw_phase_evidence(evidence_dir, phase, result)


def assert_final_reverts_initial(initial_digest: str, final_digest: str) -> None:
    if initial_digest != final_digest:
        raise GateError("final_filesystem_digest_mismatch")


def execute_reviewed_slot(
    slot: Mapping[str, Any],
    blueprint: Mapping[str, Any],
    repository_root: Path,
    patch_path: Path,
    evidence_root: Path,
    gate: Mapping[str, Any],
) -> dict[str, Any]:
    require_authorized_execution_gate(gate)
    patch_info = verify_patch_artifact(slot, patch_path)
    snapshot_root = evidence_root / f"slot_{slot['slot_ordinal']}" / "snapshot"
    create_detached_snapshot(repository_root, snapshot_root, str(slot["before_commit_oid"]))
    node_ids = blueprint_node_ids(blueprint)
    phases = [run_pytest_phase_inside_hardened_bwrap(snapshot_root, phase, node_ids, evidence_root / f"slot_{slot['slot_ordinal']}")
              for phase in PHASES]
    return {
        "record_type": "stage12600_candidate_reviewed_slot_execution_result_v1",
        "slot_ordinal": slot["slot_ordinal"],
        "production_path": patch_info["production_path"],
        "phase_reports": phases,
    }


def rerun_namespace_manifest_match(slot: Mapping[str, Any], snapshot_contract: Mapping[str, Any]) -> None:
    expected = slot.get("namespace_input_manifest_sha256")
    for binding in snapshot_contract.get("binding_snapshots", []):
        if binding.get("binding_payload_sha256") == slot.get("binding_payload_sha256"):
            if binding.get("namespace_input_manifest_sha256") != expected:
                raise GateError("namespace_manifest_match_failed")
            return
    raise GateError("namespace_binding_snapshot_missing")


def git_output(snapshot_root: Path, argv: Sequence[str]) -> bytes:
    result = run_command(["git", *argv], cwd=snapshot_root)
    if result.returncode != 0:
        raise GateError("git_command_failed:" + ":".join(argv[:2]))
    return result.stdout


def filesystem_state_digest(snapshot_root: Path) -> str:
    status = git_output(snapshot_root, ["status", "--porcelain=v2", "-z"])
    diff = git_output(snapshot_root, ["diff", "--binary", "HEAD"])
    cached = git_output(snapshot_root, ["diff", "--cached", "--binary", "HEAD"])
    return sha256_bytes(canonical_bytes({
        "status_porcelain_v2_z_sha256": sha256_bytes(status),
        "diff_binary_sha256": sha256_bytes(diff),
        "cached_diff_binary_sha256": sha256_bytes(cached),
    }))


def git_changed_paths(snapshot_root: Path) -> list[str]:
    output = git_output(snapshot_root, ["diff", "--name-only", "HEAD"])
    return sorted(path for path in output.decode("utf-8").splitlines() if path)


def apply_exact_production_patch(snapshot_root: Path, slot: Mapping[str, Any], patch_path: Path) -> None:
    verify_patch_artifact(slot, patch_path)
    result = run_command(["git", "apply", "--index", str(patch_path)], cwd=snapshot_root)
    if result.returncode != 0:
        raise GateError("git_apply_patch_failed")
    assert_patched_only_changes_bound_production_path(snapshot_root, slot)


def revert_exact_production_patch(snapshot_root: Path, slot: Mapping[str, Any], patch_path: Path) -> None:
    verify_patch_artifact(slot, patch_path)
    result = run_command(["git", "apply", "--reverse", "--index", str(patch_path)], cwd=snapshot_root)
    if result.returncode != 0:
        raise GateError("git_revert_patch_failed")
    if git_changed_paths(snapshot_root):
        raise GateError("revert_left_changed_paths")


def assert_patched_only_changes_bound_production_path(snapshot_root: Path, slot: Mapping[str, Any]) -> None:
    changed = git_changed_paths(snapshot_root)
    expected = validate_production_path(str(slot["production_path"]))
    if changed != [expected]:
        raise GateError("patched_state_not_bound_to_production_path")


def publish_private_raw_evidence_after_public_leak_scan(public_record: Mapping[str, Any], private_record: Mapping[str, Any]) -> dict[str, Any]:
    encoded = json.dumps(public_record, sort_keys=True, ensure_ascii=True)
    forbidden = ("/data/", "selector", "raw_stream", "stdout.raw", "stderr.raw", "before_commit_oid", "after_commit_oid", "production_path", "production_patch_sha256")
    for needle in forbidden:
        if needle in encoded:
            raise GateError("public_leak_before_private_evidence_publish:" + needle)
    return {
        "record_type": "stage12600_private_raw_evidence_publication_manifest_v1",
        "public_record_sha256": stable_hash(public_record),
        "private_record_sha256": stable_hash(private_record),
        "private_evidence_publishable": True,
    }


def execute_reviewed_slot(
    slot: Mapping[str, Any],
    blueprint: Mapping[str, Any],
    repository_root: Path,
    patch_path: Path,
    evidence_root: Path,
    gate: Mapping[str, Any],
    snapshot_contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    require_authorized_execution_gate(gate)
    snapshot_contract = snapshot_contract or load_stage12594_snapshot_contract()["snapshot"]
    rerun_namespace_manifest_match(slot, snapshot_contract)
    patch_info = verify_patch_artifact(slot, patch_path)
    slot_root = evidence_root / f"slot_{slot['slot_ordinal']}"
    snapshot_root = slot_root / "snapshot"
    create_detached_snapshot(repository_root, snapshot_root, str(slot["before_commit_oid"]))
    node_ids = blueprint_node_ids(blueprint)
    initial_digest = filesystem_state_digest(snapshot_root)
    initial = run_pytest_phase_inside_hardened_bwrap(snapshot_root, "initial", node_ids, slot_root)
    apply_exact_production_patch(snapshot_root, slot, patch_path)
    patched_only_digest = filesystem_state_digest(snapshot_root)
    patched = run_pytest_phase_inside_hardened_bwrap(snapshot_root, "patched", node_ids, slot_root)
    revert_exact_production_patch(snapshot_root, slot, patch_path)
    reverted_digest = filesystem_state_digest(snapshot_root)
    assert_final_reverts_initial(initial_digest, reverted_digest)
    final = run_pytest_phase_inside_hardened_bwrap(snapshot_root, "final", node_ids, slot_root)
    public_record = {
        "record_type": "stage12600_candidate_slot_public_execution_boundary_v1",
        "slot_ordinal": slot["slot_ordinal"],
        "phase_sequence": list(PHASES),
        "execution_performed": True,
        "replay_trustworthy": False,
        "level_3_materialized": False,
        "training_admitted": False,
    }
    private_record = {
        "record_type": "stage12600_candidate_reviewed_slot_execution_result_v1",
        "slot_ordinal": slot["slot_ordinal"],
        "production_path": patch_info["production_path"],
        "production_patch_sha256": patch_info["production_patch_sha256"],
        "initial_filesystem_state_digest": initial_digest,
        "patched_filesystem_state_digest": patched_only_digest,
        "reverted_filesystem_state_digest": reverted_digest,
        "phase_reports": [initial, patched, final],
    }
    private_record["private_publication_manifest"] = publish_private_raw_evidence_after_public_leak_scan(public_record, private_record)
    return private_record


IMPLEMENTED_REVIEWABLE_FUNCTIONS = (
    "load_stage12594_snapshot_contract",
    "load_stage12595_manual_slots",
    "validate_production_path",
    "verify_patch_artifact",
    "build_execution_command_manifest",
    "rerun_namespace_manifest_match",
    "create_detached_snapshot",
    "filesystem_state_digest",
    "apply_exact_production_patch",
    "assert_patched_only_changes_bound_production_path",
    "revert_exact_production_patch",
    "assert_final_reverts_initial",
    "publish_private_raw_evidence_after_public_leak_scan",
    "run_pytest_phase_inside_hardened_bwrap",
    "execute_reviewed_slot",
)


def build_candidate_source_descriptor(stage12599: Mapping[str, Any]) -> dict[str, Any]:
    stage12594 = load_stage12594_snapshot_contract()
    stage12595 = load_stage12595_manual_slots()
    return {
        "record_type": "stage12600_candidate_execution_capable_source_descriptor_v1",
        "stage12594_publication_generation_id": EXPECTED_STAGE12594_GENERATION,
        "stage12594_publication_manifest_sha256": EXPECTED_STAGE12594_MANIFEST,
        "stage12594_snapshot_contract_sha256": EXPECTED_STAGE12594_SNAPSHOT_CONTRACT,
        "stage12595_handoff_sha256": EXPECTED_STAGE12595_HANDOFF,
        "stage12595_slots_sha256": EXPECTED_STAGE12595_SLOTS,
        "stage12598_source_review_transcript_sha256": EXPECTED_STAGE12598_TRANSCRIPT,
        "stage12599_summary_sha256": EXPECTED_STAGE12599_SUMMARY,
        "stage12593_blueprints_sha256": EXPECTED_STAGE12593_BLUEPRINTS,
        "candidate_execution_capable_source_present": True,
        "candidate_execution_implementation_present": True,
        "reviewed_execution_capable_source_present": False,
        "independent_execution_capable_source_review_present": False,
        "execute_entrypoint_declared": True,
        "execute_path_enabled": False,
        "execution_gate_granted": False,
        "execution_request_ready_count": 0,
        "this_stage_runs_replay": False,
        "executor_command_manifest_present": False,
        "raw_replay_evidence_present": False,
        "manual_replay_slot_count": stage12599["summary"]["manual_replay_slot_count"],
        "candidate_manifest_slot_count": len(stage12595["slots"]),
        "required_phase_sequence": list(PHASES),
        "required_controls": list(REQUIRED_CONTROLS),
        "implemented_reviewable_functions": list(IMPLEMENTED_REVIEWABLE_FUNCTIONS),
        "patch_material_required_before_execution": True,
        "future_patch_digest_enforcement": "slot_patch_file_sha256_must_equal_stage12595_production_patch_sha256",
        "required_future_gate": "independent_execution_capable_source_review_before_execute_path_enablement",
        "stage12594_snapshot_binding_count": stage12594["snapshot"]["binding_count"],
        **no_claim_fields(),
    }


def describe(root: Path = S12599) -> dict[str, Any]:
    return build_candidate_source_descriptor(load_stage12599(root))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage12599-root", type=Path, default=S12599)
    parser.add_argument("--describe-only", action="store_true")
    parser.add_argument("--execute", action="store_true", help="always rejected pending independent source review")
    args = parser.parse_args()
    if args.execute:
        raise GateError("execution_disabled_pending_independent_execution_capable_source_review")
    if not args.describe_only:
        raise GateError("describe_only_flag_required")
    print(json.dumps(describe(args.stage12599_root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
