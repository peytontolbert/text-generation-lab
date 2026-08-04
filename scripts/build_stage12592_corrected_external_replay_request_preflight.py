#!/usr/bin/env python3
"""Build the corrected, non-executing Stage12592 external replay preflight."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12592_corrected_external_replay_request_preflight"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
PRIVATE_REPOSITORY_BASE = Path("/arxiv/repositories")
PRIVATE_AUTHORITY_INPUT = ROOT / "runs/local/private/stage12592/verifier_binding_authority.jsonl"

INPUTS = {
    "stage12591_universe": ROOT / "runs/local/artifacts/stage12591_external_source_native_causal_replay_microbatch_preflight/static_universe.jsonl",
    "stage12591_exclusions": ROOT / "runs/local/artifacts/stage12591_external_source_native_causal_replay_microbatch_preflight/preflight_exclusions.jsonl",
    "stage12547_ledger": ROOT / "runs/local/artifacts/stage12547_authoritative_independent_root_ledger/authoritative_independent_root_ledger.jsonl",
    "stage12547_implementation": ROOT / "scripts/build_stage12547_authoritative_independent_root_ledger.py",
    "future_eval_denylist": ROOT / "configs/software_maintainer/future_eval_identity_denylist_v1.json",
}

BUCKETS = ("rust_cpp", "python", "js_ts_jvm")
READINESS_FLOOR = 4
RESERVE_TARGET = 8
REQUEST_TARGET = 12
TEST_MARKER = re.compile(r"(^|/)(test|tests|spec|specs)(/|_)|\.(test|spec)\.", re.I)
HEX64 = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_PUBLIC_KEYS = re.compile(
    r"(^|_)(commit_subject|goal|expected_outcome|patch_summary|result|outcome|admission|training_row|rank|score|model_row)($|_)"
)
CLEANLINESS_COMPONENTS = (
    "tracked", "untracked", "ignored", "submodules", "index", "symlinks",
    "modes", "lockfiles", "generated_state",
)
ORDERED_EVENTS = (
    "focused_verifier_fail",
    "apply_production_only_patch",
    "identical_focused_verifier_pass",
    "revert_production_patch",
    "identical_focused_verifier_fail_after_revert",
)


class GateError(RuntimeError):
    pass


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return sha256_bytes(encoded)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise GateError(f"non_object_jsonl:{path.name}:{number}")
            rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), sort_keys=True) + "\n")


def load_stage12547_identity_function():
    """Use Stage12547's implementation rather than recreating its namespace."""
    path = INPUTS["stage12547_implementation"]
    spec = importlib.util.spec_from_file_location("stage12547_identity_namespace", path)
    if spec is None or spec.loader is None:
        raise GateError("stage12547_identity_implementation_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.identity_tokens


def stage12547_identity_tokens(row: dict[str, Any]) -> tuple[list[str], list[str]]:
    return load_stage12547_identity_function()(row)


def readiness(counts: Mapping[str, int], distinct_repos: int) -> tuple[bool, dict[str, int]]:
    deficits = {f"{bucket}_floor_deficit": max(0, READINESS_FLOOR - int(counts.get(bucket, 0))) for bucket in BUCKETS}
    deficits["distinct_repo_floor_deficit"] = max(0, REQUEST_TARGET - distinct_repos)
    return not any(deficits.values()), deficits


def production_only_plan(changed_paths: Sequence[str], selected_paths: Sequence[str]) -> dict[str, Any]:
    changed = sorted(set(changed_paths))
    selected = sorted(set(selected_paths))
    test_changes = sorted(path for path in changed if TEST_MARKER.search(path))
    selected_test_changes = sorted(path for path in selected if TEST_MARKER.search(path))
    production = sorted(path for path in changed if path not in test_changes)
    accepted = bool(production) and selected == production and not selected_test_changes
    return {
        "accepted": accepted,
        "full_commit_allowed": not test_changes,
        "changed_test_file_count": len(test_changes),
        "selected_test_file_count": len(selected_test_changes),
        "selected_production_file_count": len(selected),
        "test_tree_freeze_required": True,
        "test_tree_hash_checkpoints": ["before", "fail", "pass", "revert"],
    }


def validate_verifier_binding(row: Mapping[str, Any]) -> list[str]:
    missing: list[str] = []
    argv = row.get("command_argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(value, str) and value for value in argv):
        missing.append("executable_focused_command")
    for field in ("selector", "environment_identity", "authoritative_source_ref"):
        if not isinstance(row.get(field), str) or not row[field]:
            missing.append(field)
    if row.get("dependency_ready") is not True:
        missing.append("dependency_ready")
    if row.get("offline_ready") is not True:
        missing.append("offline_ready")
    return missing


def validate_cleanliness_attestation(row: Mapping[str, Any]) -> list[str]:
    missing = [name for name in CLEANLINESS_COMPONENTS if row.get(name) is not True]
    if not isinstance(row.get("attested_at_utc"), str) or not row["attested_at_utc"]:
        missing.append("attested_at_utc")
    if row.get("immediate_pre_execution_revalidation_required") is not True:
        missing.append("immediate_pre_execution_revalidation_required")
    return missing


def public_key_leaks(value: Any, prefix: str = "") -> list[str]:
    leaks: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if FORBIDDEN_PUBLIC_KEYS.search(str(key)):
                leaks.append(path)
            leaks.extend(public_key_leaks(nested, path))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            leaks.extend(public_key_leaks(nested, f"{prefix}[{index}]"))
    return leaks


def sanitized_manifest_row(candidate: Mapping[str, Any]) -> dict[str, Any]:
    row = {
        "record_type": "stage12592_sanitized_pre_outcome_selection_v1",
        "candidate_ref": str(candidate["candidate_id"]),
        "bucket": str(candidate["bucket"]),
        "repo_ref": str(candidate["repo_executor_ref"]),
        "source_ref": str(candidate["source_evidence_ref"]),
        "changed_file_count": int(candidate["changed_file_count"]),
        "production_file_count": int(candidate["changed_production_file_count"]),
        "test_file_count": int(candidate["changed_test_file_count"]),
        "structure_key": [
            int(candidate["changed_file_count"]),
            -int(candidate["changed_production_file_count"]),
            str(candidate["repo_executor_ref"]),
            str(candidate["candidate_id"]),
        ],
        "verifier_binding_ref": "binding_" + stable_hash(candidate["candidate_id"])[:24],
        "cleanliness_attestation_ref_required": "cleanliness_" + stable_hash(candidate["repo_executor_ref"])[:24],
        "training_allowed": False,
    }
    leaks = public_key_leaks(row)
    if leaks:
        raise GateError("sanitized_manifest_forbidden_fields:" + ",".join(leaks))
    return row


def deterministic_balanced_selection(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    used_repos: set[str] = set()
    for bucket in BUCKETS:
        lane = sorted((dict(row) for row in rows if row.get("bucket") == bucket), key=lambda row: tuple(row["structure_key"]))
        for row in lane:
            repo = str(row["repo_ref"])
            if repo in used_repos:
                continue
            selected.append(row)
            used_repos.add(repo)
            if sum(item["bucket"] == bucket for item in selected) == READINESS_FLOOR:
                break
    return selected


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ("git", "-C", str(repo), *args), text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False, timeout=30,
    )
    if result.returncode:
        raise GateError("repo_metadata_unavailable")
    return result.stdout.rstrip("\n")


def protected_namespace() -> tuple[set[str], dict[str, set[str]]]:
    ledger_values: set[str] = set()
    for row in read_jsonl(INPUTS["stage12547_ledger"]):
        roots, lineages = stage12547_identity_tokens(row)
        ledger_values.update(roots)
        ledger_values.update(lineages)
        if row.get("canonical_identity"):
            ledger_values.add("canonical:" + str(row["canonical_identity"]))
        if row.get("repo_family_hash") not in (None, "", "unknown"):
            ledger_values.add("repo_family_hash:" + str(row["repo_family_hash"]))
    deny = json.loads(INPUTS["future_eval_denylist"].read_text(encoding="utf-8"))["deny"]
    deny_values = {str(key): {str(value) for value in values} for key, values in deny.items()}
    return ledger_values, deny_values


def resolve_identity(candidate: Mapping[str, Any], ledger_values: set[str], deny: Mapping[str, set[str]]) -> tuple[str, list[str]]:
    repo_name = str(candidate.get("repo_family") or "")
    repo = PRIVATE_REPOSITORY_BASE / repo_name
    try:
        if not repo_name or not repo.is_dir() or git(repo, "rev-parse", "--is-inside-work-tree") != "true":
            raise GateError("repo_metadata_unavailable")
        source_path = str(repo.resolve())
        after = git(repo, "rev-parse", "HEAD")
        # Stage12591 pins opaque SHA-256 digests; metadata must resolve back to the same namespace.
        expected_after = str(candidate.get("lineage", {}).get("after_commit_sha256") or "")
        if not HEX64.fullmatch(expected_after) or sha256_bytes(after.encode()) != expected_after:
            raise GateError("stage12591_commit_identity_drift")
        parent = git(repo, "show", "-s", "--format=%P", after).split()
        if len(parent) != 1:
            raise GateError("non_single_parent_identity")
        raw_tokens = {"root:" + after, "root:" + parent[0], "lineage:" + after, "lineage:" + parent[0]}
        overlaps = sorted(raw_tokens & ledger_values)
        if repo_name in deny.get("repo_family", set()) or source_path in deny.get("source_path", set()):
            overlaps.append("future_denylist_repo_or_path")
        if ({after, parent[0]} & deny.get("root_identity", set())):
            overlaps.append("future_denylist_root_identity")
        return ("protected" if overlaps else "resolved_clear"), overlaps
    except (GateError, OSError, subprocess.SubprocessError):
        return "unknown", ["unknown_identity_resolution"]


def authority_by_candidate() -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(PRIVATE_AUTHORITY_INPUT):
        candidate_ref = str(row.get("candidate_ref") or "")
        if candidate_ref and not validate_verifier_binding(row):
            output[candidate_ref] = row
    return output


def build() -> dict[str, Any]:
    universe = read_jsonl(INPUTS["stage12591_universe"])
    manifest = [sanitized_manifest_row(row) for row in universe]
    manifest.sort(key=lambda row: (BUCKETS.index(row["bucket"]), tuple(row["structure_key"])))
    manifest_hash = stable_hash(manifest)
    selected = deterministic_balanced_selection(manifest)
    selected_counts = Counter(row["bucket"] for row in selected)
    selected_ready, selection_deficits = readiness(selected_counts, len({row["repo_ref"] for row in selected}))

    ledger_values, deny = protected_namespace()
    source_by_id = {str(row["candidate_id"]): row for row in universe}
    authority = authority_by_candidate()
    sidecar_rows: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    request_rows: list[dict[str, Any]] = []
    blocker_counts: Counter[str] = Counter()

    for row in selected:
        candidate_ref = row["candidate_ref"]
        source = source_by_id[candidate_ref]
        identity_status, identity_reasons = resolve_identity(source, ledger_values, deny)
        blockers: list[str] = []
        if identity_status == "unknown":
            blockers.append("unknown_protected_namespace_identity")
        elif identity_status == "protected":
            blockers.append("protected_namespace_overlap")
        binding = authority.get(candidate_ref)
        if binding is None:
            blockers.append("authoritative_verifier_binding_unavailable")
        else:
            private_row = {
                **binding,
                "record_type": "stage12592_private_verifier_binding_v1",
                "binding_ref": row["verifier_binding_ref"],
                "candidate_ref": candidate_ref,
                "training_allowed": False,
            }
            sidecar_rows.append(private_row)
        if blockers:
            blocker_counts.update(blockers)
            exclusions.append({
                "record_type": "stage12592_preflight_exclusion_v1",
                "candidate_ref": candidate_ref,
                "bucket": row["bucket"],
                "repo_ref": row["repo_ref"],
                "blockers": sorted(blockers),
                "identity_resolution": identity_status,
                "identity_reason_refs": ["identity_reason_" + stable_hash(reason)[:16] for reason in identity_reasons],
                "training_allowed": False,
            })
            continue
        request_rows.append({
            "record_type": "stage12592_external_replay_request_v1",
            "candidate_ref": candidate_ref,
            "bucket": row["bucket"],
            "repo_ref": row["repo_ref"],
            "selection_manifest_ref": "manifest_" + manifest_hash[:24],
            "verifier_binding_ref": row["verifier_binding_ref"],
            "cleanliness_attestation_ref_required": row["cleanliness_attestation_ref_required"],
            "production_only_patch_required": True,
            "zero_test_mutation_required": True,
            "immutable_test_tree_hash_checkpoints": ["before", "fail", "pass", "revert"],
            "identical_verifier_identity_required": ["command", "selector", "environment"],
            "ordered_events": list(ORDERED_EVENTS),
            "immediate_cleanliness_revalidation_required": True,
            "training_allowed": False,
        })

    # The batch is atomic: no request is emitted unless all 12 selected rows prove every gate.
    if not selected_ready or len(request_rows) != REQUEST_TARGET:
        if not selected_ready:
            blocker_counts["readiness_floor_not_met"] += 1
        if len(request_rows) != REQUEST_TARGET:
            blocker_counts["balanced_batch_not_fully_proven"] += REQUEST_TARGET - len(request_rows)
        request_rows = []

    contract = {
        "stage": STAGE,
        "record_type": "stage12592_corrected_external_replay_contract_v1",
        "execution_performed": False,
        "training_allowed": False,
        "readiness_floor_per_bucket": READINESS_FLOOR,
        "reserve_target_per_bucket": RESERVE_TARGET,
        "reserve_target_is_blocking": False,
        "balanced_request_target": {bucket: READINESS_FLOOR for bucket in BUCKETS},
        "distinct_repo_floor": REQUEST_TARGET,
        "one_candidate_per_repo": True,
        "full_commit_with_test_changes_allowed": False,
        "production_only_patch_required": True,
        "zero_test_mutation_required": True,
        "immutable_test_tree_hash_checkpoints": ["before", "fail", "pass", "revert"],
        "identical_verifier_identity_required": ["command", "selector", "environment"],
        "ordered_events": list(ORDERED_EVENTS),
        "private_verifier_binding_required_fields": [
            "command_argv", "selector", "environment_identity", "dependency_ready",
            "offline_ready", "authoritative_source_ref",
        ],
        "public_verifier_material": "opaque_binding_refs_only",
        "cleanliness_attestation_required_components": list(CLEANLINESS_COMPONENTS),
        "cleanliness_attestation_timestamp_required": True,
        "immediate_pre_execution_revalidation_required": True,
        "current_cleanliness_guaranteed": False,
        "forbidden_row_classes": ["execution", "admission", "training", "ranking", "model"],
    }
    deficits = {
        **selection_deficits,
        "request_count_deficit": REQUEST_TARGET - len(request_rows),
        "authoritative_verifier_binding_deficit": sum(
            row["candidate_ref"] not in authority for row in selected
        ),
        "identity_resolution_deficit": sum(
            "unknown_protected_namespace_identity" in row["blockers"] for row in exclusions
        ),
    }
    summary = {
        "stage": STAGE,
        "record_type": "stage12592_preflight_summary_v1",
        "decision": "request_ready" if len(request_rows) == REQUEST_TARGET else "blocked_exact_deficits_reported",
        "execution_performed": False,
        "training_allowed": False,
        "source_universe_count": len(universe),
        "sanitized_manifest_count": len(manifest),
        "selection_manifest_ref": "manifest_" + manifest_hash[:24],
        "selection_manifest_sha256": manifest_hash,
        "selected_preflight_count": len(selected),
        "selected_bucket_counts": {bucket: selected_counts.get(bucket, 0) for bucket in BUCKETS},
        "reserve_target_counts": {bucket: RESERVE_TARGET for bucket in BUCKETS},
        "reserve_target_nonblocking": True,
        "request_ready_ids": [row["candidate_ref"] for row in request_rows],
        "request_ready_count": len(request_rows),
        "blocker_histogram": dict(sorted(blocker_counts.items())),
        "exact_deficits": deficits,
        "private_verifier_sidecar_ref": "private_sidecar_" + stable_hash(sidecar_rows)[:24],
        "private_verifier_binding_count": len(sidecar_rows),
        "public_records_contain_opaque_verifier_refs_only": True,
        "no_authority": not bool(authority),
    }

    write_jsonl(OUT / "sanitized_pre_outcome_selection_manifest.jsonl", manifest)
    write_jsonl(OUT / "preflight_exclusions.jsonl", exclusions)
    write_jsonl(OUT / "external_replay_requests.jsonl", request_rows)
    write_jsonl(OUT / "private/verifier_binding_sidecar.jsonl", sidecar_rows)
    write_json(OUT / "request_contract.json", contract)
    write_json(OUT / "exact_deficits.json", deficits)
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY, summary)
    return summary


def main() -> int:
    summary = build()
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
