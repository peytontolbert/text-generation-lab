#!/usr/bin/env python3
"""Build a fail-closed replay request for one source-native Open-SWE row.

Trace commands and exits are candidate evidence only.  This stage performs no
checkout, patch application, verifier execution, admission, or causal proof.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12549_minijinja_external_patch_effect_replay_request"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
SOURCE_BINDING_OUT = OUT / "source_native_candidate_binding.json"
REQUEST_OUT = OUT / "minijinja_external_patch_effect_replay_request.json"
OVERLAP_OUT = OUT / "locked_manifest_overlap_audit.json"

SOURCE = Path(
    "/arxiv/datasets/nvidia--Open-SWE-Traces/data/"
    "minimax_m25_openhands_trajectories/train-00000-of-00020.parquet"
)
TARGET = {
    "instance_id": "mitsuhiko__minijinja-565",
    "trajectory_id": "5804ceba-a46e-4885-bb8d-428dd67c4a94",
    "repo": "mitsuhiko/minijinja",
    "language": "rust",
}
VERIFIER = "cargo test --package minijinja -- test_slice_and_index --nocapture"
EXPECTED_BEFORE_EXIT = 101
EXPECTED_AFTER_EXIT = 0

LOCKED_MANIFESTS = (
    ROOT / "runs/local/artifacts/stage8672_locked_benchmark_pack_manifest/locked_benchmark_packs.jsonl",
    ROOT / "runs/local/artifacts/stage9718_locked_multilingual_acceptance_evidence_ledger/locked_multilingual_acceptance_evidence_ledger.json",
    ROOT / "runs/local/artifacts/stage12105_sealed_transition_candidate_atlas/sealed_transition_candidate_rows.jsonl",
)

DIFF_HEADER_RE = re.compile(r"(?m)^diff --git a/(.+?) b/(.+?)$")
DIFF_HUNK_RE = re.compile(r"(?m)^@@ .+ @@")
EXIT_RE = re.compile(r"Command finished with exit code (\d+)", re.I)
TEST_PATH_RE = re.compile(r"(^|/)(tests?|testing|fixtures?)(/|$)|(?:^|/)test_[^/]+|_test\.", re.I)
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40,64}$", re.I)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return sha256_text(payload)


def file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def is_real_diff(diff: Any) -> bool:
    return isinstance(diff, str) and bool(DIFF_HEADER_RE.search(diff) and DIFF_HUNK_RE.search(diff))


def changed_paths(diff: str) -> list[str]:
    return sorted({path for pair in DIFF_HEADER_RE.findall(diff) for path in pair})


def _read_rows(path: Path) -> tuple[list[tuple[int, int, int, dict[str, Any]]], list[str]]:
    if not path.is_file():
        return [], ["source_parquet_missing"]
    try:
        import pyarrow.parquet as pq  # type: ignore
    except ImportError:
        return [], ["pyarrow_unavailable"]
    try:
        parquet = pq.ParquetFile(path)
        found: list[tuple[int, int, int, dict[str, Any]]] = []
        global_index = 0
        for group_index in range(parquet.num_row_groups):
            rows = parquet.read_row_group(group_index).to_pylist()
            for in_group_index, row in enumerate(rows):
                if all(row.get(key) == value for key, value in TARGET.items()):
                    found.append((global_index, group_index, in_group_index, row))
                global_index += 1
        return found, []
    except Exception as exc:  # fail closed without exposing raw row content
        return [], [f"source_parquet_read_error:{type(exc).__name__}"]


def _synthetic_matches(rows: list[dict[str, Any]]) -> list[tuple[int, int, int, dict[str, Any]]]:
    return [
        (index, 0, index, row)
        for index, row in enumerate(rows)
        if all(row.get(key) == value for key, value in TARGET.items())
    ]


def _tool_command(turn: dict[str, Any]) -> str | None:
    calls = turn.get("tool_calls")
    if not isinstance(calls, list):
        return None
    for call in calls:
        function = call.get("function") if isinstance(call, dict) else None
        if not isinstance(function, dict):
            continue
        arguments = function.get("arguments")
        try:
            parsed = json.loads(arguments) if isinstance(arguments, str) else arguments
        except json.JSONDecodeError:
            continue
        command = parsed.get("command") if isinstance(parsed, dict) else None
        if isinstance(command, str) and "cargo test" in command and "test_slice_and_index" in command:
            return command
    return None


def canonical_verifier(command: str) -> str:
    command = command.strip()
    if "&&" in command:
        command = command.rsplit("&&", 1)[1].strip()
    command = re.sub(r"\s+2>&1\s*$", "", command).strip()
    return " ".join(command.split())


def verifier_observations(trajectory: Any) -> list[dict[str, Any]]:
    if not isinstance(trajectory, list):
        return []
    observations: list[dict[str, Any]] = []
    for index, turn in enumerate(trajectory[:-1]):
        if not isinstance(turn, dict):
            continue
        command = _tool_command(turn)
        response = trajectory[index + 1]
        if command is None or not isinstance(response, dict) or response.get("role") != "tool":
            continue
        content = response.get("content")
        exits = EXIT_RE.findall(content) if isinstance(content, str) else []
        observations.append(
            {
                "command_event_index": index,
                "output_event_index": index + 1,
                "command": canonical_verifier(command),
                "exit_code": int(exits[-1]) if exits else None,
                "output_sha256": sha256_text(content) if isinstance(content, str) else None,
            }
        )
    return observations


def test_fixture_locator(trajectory: Any) -> dict[str, Any] | None:
    if not isinstance(trajectory, list):
        return None
    for index, turn in enumerate(trajectory):
        content = turn.get("content") if isinstance(turn, dict) else None
        if not isinstance(content, str) or "diff --git a/minijinja/tests/test_value.rs" not in content:
            continue
        diff = content.split("[The command completed", 1)[0].rstrip() + "\n"
        if is_real_diff(diff) and "fn test_slice_and_index" in diff:
            return {
                "source_event_index": index,
                "test_path": "minijinja/tests/test_value.rs",
                "candidate_test_diff_sha256": sha256_text(diff),
                "candidate_test_diff_chars": len(diff),
                "raw_test_diff_emitted": False,
            }
    return None


def source_candidate(matches: list[tuple[int, int, int, dict[str, Any]]], source_path: Path) -> tuple[dict[str, Any], list[str]]:
    reasons: list[str] = []
    if len(matches) != 1:
        reasons.append("source_row_match_count_not_one")
        return {}, reasons
    row_index, group_index, in_group_index, row = matches[0]
    diff = row.get("model_patch")
    if not is_real_diff(diff):
        reasons.append("source_model_patch_missing_or_not_real_diff")
        diff = ""
    paths = changed_paths(diff)
    if not paths or any(TEST_PATH_RE.search(path) for path in paths):
        reasons.append("model_patch_path_set_empty_or_modifies_tests")

    observations = verifier_observations(row.get("trajectory"))
    before = next((item for item in observations if item["exit_code"] == EXPECTED_BEFORE_EXIT), None)
    after = next(
        (item for item in observations if before and item["command_event_index"] > before["command_event_index"] and item["exit_code"] == EXPECTED_AFTER_EXIT),
        None,
    )
    if before is None or after is None:
        reasons.append("candidate_before_after_exit_pair_missing")
    elif before["command"] != VERIFIER or after["command"] != VERIFIER or before["command"] != after["command"]:
        reasons.append("candidate_verifier_identity_mismatch")

    fixture = test_fixture_locator(row.get("trajectory"))
    if fixture is None:
        reasons.append("candidate_test_fixture_locator_missing")
    else:
        reasons.append("candidate_authored_or_nonbaseline_verifier")

    base_commit = row.get("base_commit") or row.get("base_commit_sha") or row.get("checkout_before_commit")
    if not isinstance(base_commit, str) or not FULL_SHA_RE.fullmatch(base_commit):
        reasons.append("source_native_base_commit_missing")

    native_identity = {
        "dataset_file": str(source_path),
        "dataset_file_sha256": file_sha256(source_path),
        "row_index_zero_based": row_index,
        "row_group_index_zero_based": group_index,
        "row_index_within_group_zero_based": in_group_index,
        **{key: row.get(key) for key in ("instance_id", "trajectory_id", "repo", "language")},
        "base_commit": base_commit,
    }
    return {
        "record_type": "stage12549_source_native_candidate_binding_v1",
        "source_native_identity": native_identity,
        "source_native_row_identity_sha256": stable_hash(native_identity),
        "source_row_sha256": stable_hash(row),
        "model_patch": {
            "sha256": sha256_text(diff) if diff else None,
            "character_count": len(diff),
            "changed_paths": paths,
            "raw_diff_emitted": False,
        },
        "verifier_identity": {"command": VERIFIER, "sha256": sha256_text(VERIFIER)},
        "candidate_observed_before": before,
        "candidate_observed_after": after,
        "candidate_test_fixture": fixture,
        "trace_evidence_class": "candidate_trace_co_occurrence_only",
        "causal_proof": False,
    }, reasons


def _manifest_values(value: Any, output: set[str]) -> None:
    if isinstance(value, dict):
        for child in value.values():
            _manifest_values(child, output)
    elif isinstance(value, list):
        for child in value:
            _manifest_values(child, output)
    elif isinstance(value, (str, int)):
        output.add(str(value))


def locked_overlap_audit(binding: dict[str, Any], paths: Iterable[Path]) -> tuple[dict[str, Any], list[str]]:
    loaded: list[str] = []
    missing: list[str] = []
    values: set[str] = set()
    for path in paths:
        if not path.is_file():
            missing.append(str(path))
            continue
        loaded.append(str(path))
        try:
            if path.suffix == ".jsonl":
                objects = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            else:
                objects = [json.loads(path.read_text(encoding="utf-8"))]
            _manifest_values(objects, values)
        except (OSError, json.JSONDecodeError):
            missing.append(str(path))
    identity = binding.get("source_native_identity", {})
    candidate_keys = sorted(
        str(value) for value in (
            identity.get("instance_id"), identity.get("trajectory_id"), identity.get("repo"),
            binding.get("source_native_row_identity_sha256"), binding.get("model_patch", {}).get("sha256"),
            binding.get("verifier_identity", {}).get("sha256"),
        ) if value
    )
    intersection = sorted(set(candidate_keys) & values)
    source_universe_covered = any(
        "open_swe_protected_identity_universe" in Path(path).name
        for path in loaded
    )
    overlap_resolved = bool(loaded) and not missing and source_universe_covered
    audit = {
        "record_type": "stage12549_locked_manifest_overlap_audit_v2",
        "loaded_manifests": loaded,
        "missing_manifests": missing,
        "candidate_keys_audited": candidate_keys,
        "intersection": intersection,
        "source_universe": "open_swe_traces",
        "authoritative_source_universe_covered": source_universe_covered,
        "overlap_resolved": overlap_resolved,
        "overlap_clear": overlap_resolved and not intersection,
    }
    reasons = []
    if missing or not loaded:
        reasons.append("locked_manifest_set_incomplete")
    if not source_universe_covered:
        reasons.append("authoritative_open_swe_protected_universe_missing")
    if intersection:
        reasons.append("locked_manifest_overlap_detected")
    return audit, reasons


def build_request(
    source_path: Path = SOURCE,
    *,
    rows: list[dict[str, Any]] | None = None,
    manifest_paths: Iterable[Path] = LOCKED_MANIFESTS,
    fresh_replay: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source_exists = source_path.is_file()
    matches, read_reasons = _read_rows(source_path) if rows is None else (_synthetic_matches(rows) if source_exists else [], [] if source_exists else ["source_parquet_missing"])
    binding, binding_reasons = source_candidate(matches, source_path)
    overlap, overlap_reasons = locked_overlap_audit(binding, manifest_paths)

    replay = fresh_replay or {}
    required_replay_fields = (
        "fresh_checkout_created", "checkout_before_full_commit_sha", "checkout_before_clean",
        "test_tree_before_sha256", "test_tree_after_patch_sha256", "test_tree_after_revert_sha256",
        "applied_model_patch_sha256", "model_patch_applied_explicitly",
        "before_verifier_command", "before_exit_code", "after_verifier_command", "after_exit_code",
        "model_patch_reverted_explicitly", "revert_verifier_command", "revert_exit_code",
        "environment_capture_sha256", "cargo_lock_before_sha256", "cargo_lock_after_sha256",
    )
    missing_replay = [name for name in required_replay_fields if name not in replay]
    replay_valid = bool(replay) and not missing_replay and all((
        replay.get("fresh_checkout_created") is True,
        replay.get("checkout_before_clean") is True,
        bool(FULL_SHA_RE.fullmatch(str(replay.get("checkout_before_full_commit_sha", "")))),
        replay.get("applied_model_patch_sha256") == binding.get("model_patch", {}).get("sha256"),
        replay.get("model_patch_applied_explicitly") is True,
        replay.get("model_patch_reverted_explicitly") is True,
        replay.get("before_verifier_command") == VERIFIER,
        replay.get("after_verifier_command") == VERIFIER,
        replay.get("revert_verifier_command") == VERIFIER,
        replay.get("before_exit_code") == EXPECTED_BEFORE_EXIT,
        replay.get("after_exit_code") == EXPECTED_AFTER_EXIT,
        replay.get("revert_exit_code") == EXPECTED_BEFORE_EXIT,
        all(FULL_SHA_RE.fullmatch(str(replay.get(name, ""))) for name in (
            "test_tree_before_sha256", "test_tree_after_patch_sha256", "test_tree_after_revert_sha256",
            "environment_capture_sha256", "cargo_lock_before_sha256", "cargo_lock_after_sha256",
            "applied_model_patch_sha256",
        )),
        replay.get("test_tree_before_sha256") == replay.get("test_tree_after_patch_sha256") == replay.get("test_tree_after_revert_sha256"),
        replay.get("cargo_lock_before_sha256") == replay.get("cargo_lock_after_sha256"),
        replay.get("checkout_before_full_commit_sha") == binding.get("source_native_identity", {}).get("base_commit"),
    ))
    replay_claim_shape_valid = replay_valid
    replay_valid = False
    reasons = read_reasons + binding_reasons + overlap_reasons
    source_replayable = not read_reasons and not binding_reasons and not overlap_reasons
    if fresh_replay:
        reasons.append("content_addressed_executor_evidence_not_verified")
    elif source_replayable:
        reasons.append("fresh_controlled_replay_not_present_or_invalid")

    request_status = "blocked_pending_fresh_controlled_replay" if source_replayable else "rejected_not_replayable"
    request = {
        "record_type": "stage12549_minijinja_external_patch_effect_replay_request_v1",
        "request_status": request_status,
        "source_native_row_match_count": len(matches),
        "source_binding_valid": source_replayable,
        "source_binding": binding,
        "candidate_evidence": {
            "before_observed_exit": EXPECTED_BEFORE_EXIT,
            "after_observed_exit": EXPECTED_AFTER_EXIT,
            "classification": "candidate_only_not_causal_proof",
            "trace_co_occurrence_proves_patch_effect": False,
        },
        "execution_contract": {
            "network_checkout_allowed": False,
            "require_fresh_local_checkout": True,
            "require_full_checkout_before_commit_binding": True,
            "require_clean_checkout_before": True,
            "candidate_authored_test_or_verifier_allowed": False,
            "require_verifier_present_at_immutable_baseline": True,
            "hash_test_tree_before_patch_after_patch_and_after_revert": True,
            "require_identical_test_tree_hashes": True,
            "apply_model_patch_explicitly": True,
            "run_exact_verifier_before_apply_after_apply_and_after_revert": True,
            "exact_verifier": VERIFIER,
            "required_exit_sequence": [EXPECTED_BEFORE_EXIT, EXPECTED_AFTER_EXIT, EXPECTED_BEFORE_EXIT],
            "revert_model_patch_explicitly": True,
            "capture_environment": ["os", "arch", "rustc_-vV", "cargo_-V", "env_allowlist", "git_status", "git_head"],
            "require_locked_manifest_overlap_audit": True,
            "require_locked_cargo_manifest_unchanged": True,
            "required_return_fields": list(required_replay_fields),
        },
        "locked_manifest_overlap_audit": overlap,
        "fresh_replay_supplied": bool(fresh_replay),
        "fresh_replay_claim_shape_valid": replay_claim_shape_valid,
        "fresh_replay_valid": replay_valid,
        "blocking_reasons": sorted(set(reasons)),
        "training_allowed": False,
        "admission_allowed": False,
        "root_credit": False,
        "repair_credit": False,
        "causal_proof": False,
    }
    return {"request": request, "binding": binding, "overlap": overlap}


def main() -> int:
    result = build_request()
    write_json(SOURCE_BINDING_OUT, result["binding"])
    write_json(REQUEST_OUT, result["request"])
    write_json(OVERLAP_OUT, result["overlap"])
    request = result["request"]
    summary = {
        "stage": STAGE,
        "decision": request["request_status"],
        "source_candidate_rows_matched": request["source_native_row_match_count"],
        "replayable_source_candidate_count": 1 if request["source_binding_valid"] else 0,
        "replay_requests_emitted": 1 if request["request_status"] == "blocked_pending_fresh_controlled_replay" else 0,
        "fresh_replays_observed": 0,
        "candidate_before_exit_101_count": 1 if request["source_binding_valid"] else 0,
        "candidate_after_exit_0_count": 1 if request["source_binding_valid"] else 0,
        "accepted_causal_roots": 0,
        "training_allowed": False,
        "admission_allowed": False,
        "root_credit": False,
        "trace_co_occurrence_claimed_as_proof": False,
        "blocking_reasons": request["blocking_reasons"],
        "artifacts": {
            "source_binding": str(SOURCE_BINDING_OUT.relative_to(ROOT)),
            "replay_request": str(REQUEST_OUT.relative_to(ROOT)),
            "locked_manifest_overlap_audit": str(OVERLAP_OUT.relative_to(ROOT)),
        },
    }
    write_json(SUMMARY, summary)
    print(SUMMARY.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
