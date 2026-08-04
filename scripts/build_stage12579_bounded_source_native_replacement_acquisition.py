#!/usr/bin/env python3
"""Build the fail-closed Stage12579 source acquisition request ledger."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12579_bounded_source_native_replacement_acquisition"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
STAGE12578 = ROOT / "runs/local/artifacts/stage12578_prospective_source_acquisition_and_structural_preoutcome_seal/summary.json"
STAGE12578_FILE_SHA256 = "d8b00d28a435bcff653b31a4f609bd457b807fd06cfdda0f91740f7a0b26e22f"
STAGE12578_RECORD_SHA256 = "3c9e0d8696c70b172ebc3119b1600563aedfa4bd1a1d8fe706b804179fd5592b"

UNIVERSE_SOURCES = {
    "active_protected": ROOT / "runs/local/artifacts/stage12554_authority_inventory_and_overlap_gate/protected_swe_bench_verified_manifest.json",
    "legacy_protected": ROOT / "runs/local/artifacts/stage12560_protected_namespace_deny_sidecars/hashed_namespace_sidecars.json",
    "sealed_transition": ROOT / "runs/local/artifacts/stage12105_sealed_transition_candidate_atlas/sealed_transition_candidate_rows.jsonl",
    "locked_benchmark": ROOT / "runs/local/artifacts/stage8672_locked_benchmark_pack_manifest/locked_benchmark_packs.jsonl",
    "locked_acceptance": ROOT / "runs/local/artifacts/stage9718_locked_multilingual_acceptance_evidence_ledger/locked_multilingual_acceptance_evidence_ledger.json",
    "scratchpad_exclusions": ROOT / "runs/local/artifacts/stage12037_scratchpad_contamination_exclusion_audit/scratchpad_excluded_keys.jsonl",
    "training_exclusions": ROOT / "runs/local/artifacts/stage12040_training_data_scratchpad_contamination_gate/training_scratchpad_excluded_keys.jsonl",
    "train_families": ROOT / "runs/local/artifacts/stage10706_rewritten_plus_reviewed_multilingual_training_package_honest_strict/rewritten_plus_reviewed_multilingual_training_package_honest_strict.json",
    "transition_train": ROOT / "runs/local/artifacts/stage11897_transition_record_projection_rows/transition_projection_rows.jsonl",
    "open_swe_protected": ROOT / "runs/local/artifacts/stage12568_open_swe_source_lineage_adapter/trajectory_source_bindings.jsonl",
    "reserved12107": ROOT / "runs/local/artifacts/stage12107_fresh_sealed_transition_root_materializer/fresh_sealed_transition_materialization_work_items.jsonl",
    "reserved12118": ROOT / "runs/local/artifacts/stage12118_maintainer_400_pilot_checkout_probe_request/pilot_checkout_probe_targets.jsonl",
}
UNIVERSE_PINS = {
    "active_protected": "50e52154348d471c0d6407e466b3bffce4a197fbe81cce6db122ef22c4bcb5c5",
    "legacy_protected": "f1448cfe374558be29015572f81b07be82ce044756db603072bbb3230fb4b89c",
    "sealed_transition": "dbaf3800b987bb8607c8cd2ddb0ddcbf2011e6be9b2f4c0a41847013b86dddd2",
    "locked_benchmark": "a6cce0dabed78c240037a0ef7d06fb739e7dd9b835ca57686d49d66bff84a570",
    "locked_acceptance": "e19c6b80eb3881d1ceef55dfbc414f12d9a4a1e3b7e7e1e62ab11dc27d2c470f",
    "scratchpad_exclusions": "633d36b0c7c6eabd03ea188cbd75251c2453b4950c745fcf1ce65fcb9c36aab3",
    "training_exclusions": "c48652ada5ca6f23eae8da456d7af16eae4913cf106ddea033359a6ff46261ff",
    "train_families": "ed98291c3e2a2a6919274004b16e5998f2eef23f4526ee5c8281b136683a7762",
    "transition_train": "7ce8c030d429d948d3805e836d9e6522bcd0320252cfcb27b59475d8c1cb64bc",
    "open_swe_protected": "dab856c947426dcc128acd7bb0c1731f98a6bd9d6ab5cd6eb7be8d8271150b0a",
    "reserved12107": "e2e900ad050f4f083a612afea29ebc88890f0fda4c3d59277ebcea05242abe02",
    "reserved12118": "2de3486ef058a8f27ca602a18b852d46ace194135db4aa4eef630f16363a9f45",
}
STRATA = (
    "transition_candidate_selection", "transition_continue_or_stop",
    "transition_next_action", "transition_verifier_transition",
)
DENY_FIELDS = (
    "training_allowed", "evaluation_allowed", "admission_allowed", "clearance_granted",
    "root_credit", "repair_credit", "level3_credit", "protected_clearance",
    "use_clearance", "execution_authorized", "gpu_allowed", "replay_allowed",
    "strict_eval_eligible",
)
ZERO = {field: False for field in DENY_FIELDS}
FORBIDDEN_KEYS = {
    "accuracy", "correct", "correctness", "gold", "gold_label", "loss", "metric",
    "metrics", "model_score", "outcome", "prediction", "reward", "score", "scores",
    "target_label", "verifier_outcome", "verifier_result",
}
HEX40 = re.compile(r"^[0-9a-f]{40}$")
SOURCE_SUFFIXES = (".rs", ".js", ".jsx", ".ts", ".tsx", ".py", ".c", ".cc", ".cpp", ".h", ".hpp")
IDENTITY_KEYS = {
    "artifact_hash", "base_commit", "candidate_id", "cell_key", "dataset_id",
    "exclusion_key", "file", "ids", "instance_id", "lineage_hash", "path",
    "repo", "repo_family", "repo_family_key_normalized", "repo_id", "repo_url",
    "repo_family_counts", "repo_label_hashes", "source_qualified_pack_hashes",
    "source_qualified_root_hashes", "root_id", "root_lineage_key", "row_id",
    "source_id", "source_ids", "source_path", "task_pack_id", "work_item_id",
}
FAMILY_KEYS = {
    "candidate_id", "dataset_id", "instance_id", "repo", "repo_family",
    "repo_family_key_normalized", "repo_id", "repo_url", "root_id", "source_id",
    "source_ids", "task_pack_id", "work_item_id",
}
HISTORICAL_FAMILY_ALIASES = (
    "bddy_website", "bddy_app", "bddy_desktop", "bddy_api", "bddyio", "bddy-api", "bddy",
    "repository_library", "tokenizers", "agentkernel", "candle", "transformers", "sphinx",
    "django", "onnxruntime", "parametergolf", "perftree", "mcp", "mcpagent",
    "lastmileaimcpagent", "openclaw",
)
FAMILY_ALIAS_GROUPS = (
    frozenset({"mcp", "modelcontextprotocol"}),
    frozenset({"mcpagent", "lastmileaimcpagent"}),
    frozenset({"perftree"}),
    frozenset({"openclaw"}),
)
LANGUAGE_QUOTAS = {"rust": 4, "web_js_ts_html": 4}


class AllowlistedSource(tuple):
    """Immutable source request without import-time dataclass module lookup."""

    __slots__ = ()

    def __new__(
        cls,
        source_id: str,
        canonical_remote: str,
        requested_commit: str | None,
        checkout: str,
        language: str = "rust",
        source_path: str | None = None,
    ):
        return tuple.__new__(
            cls,
            (source_id, canonical_remote, requested_commit, checkout, language, source_path),
        )

    source_id = property(lambda self: self[0])
    canonical_remote = property(lambda self: self[1])
    requested_commit = property(lambda self: self[2])
    checkout = property(lambda self: self[3])
    language = property(lambda self: self[4])
    source_path = property(lambda self: self[5])


def asdict(row: AllowlistedSource) -> dict[str, Any]:
    return {
        "source_id": row.source_id,
        "canonical_remote": row.canonical_remote,
        "requested_commit": row.requested_commit,
        "checkout": row.checkout,
        "language": row.language,
        "source_path": row.source_path,
    }


CANONICAL_ALLOWLIST = (
    AllowlistedSource("serde", "https://github.com/serde-rs/serde", "a866b336f14aa57a07f0d0be9f8762746e64ecb4", "/data/repositories/serde"),
    AllowlistedSource("clap", "https://github.com/clap-rs/clap", "ac5fda6a799e4c640d671edd1111d4a5e723dc1a", "/data/repositories/clap"),
    AllowlistedSource("petgraph", "https://github.com/petgraph/petgraph", "162903562ce5b00cdba390a0d9c1bb80f1c75bf5", "/data/repositories/petgraph"),
    AllowlistedSource("indexmap", "https://github.com/indexmap-rs/indexmap", "0e68f8a3605f56c79d2ed84bff5908ee1dcd8a95", "/data/repositories/indexmap"),
    AllowlistedSource("lodash", "https://github.com/lodash/lodash", None, "/data/repositories/lodash", "web_js_ts_html"),
    AllowlistedSource("chalk", "https://github.com/chalk/chalk", None, "/data/repositories/chalk", "web_js_ts_html"),
    AllowlistedSource("pnpm", "https://github.com/pnpm/pnpm", None, "/data/repositories/pnpm", "web_js_ts_html"),
    AllowlistedSource("ms", "https://github.com/vercel/ms", None, "/data/repositories/ms", "web_js_ts_html"),
)
ALLOWLIST = CANONICAL_ALLOWLIST


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


ALLOWLIST_SHA256 = stable_hash([asdict(row) for row in CANONICAL_ALLOWLIST])


def file_sha256(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def normalize_remote(value: Any) -> str:
    raw = str(value or "").strip()
    if raw.startswith("git@github.com:"):
        raw = "https://github.com/" + raw[len("git@github.com:"):]
    if raw.startswith("ssh://git@github.com/"):
        raw = "https://github.com/" + raw[len("ssh://git@github.com/"):]
    parsed = urlparse(raw)
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if parsed.scheme != "https" or (parsed.hostname or "").lower() != "github.com" or len(parts) != 2:
        raise ValueError("noncanonical_or_placeholder_remote")
    owner, repo = parts
    repo = repo[:-4] if repo.lower().endswith(".git") else repo
    if not owner or not repo:
        raise ValueError("noncanonical_or_placeholder_remote")
    return f"https://github.com/{owner.lower()}/{repo.lower()}"


def normalize_identity(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower().replace("localgitsnapshot", ""))


def family_aliases(value: Any) -> set[str]:
    raw = str(value or "").strip()
    aliases = {normalize_identity(raw)}
    try:
        owner_repo = normalize_remote(raw).removeprefix("https://github.com/")
        owner, repo = owner_repo.split("/", 1)
        aliases.update({normalize_identity(repo), normalize_identity(owner_repo), normalize_identity(owner + repo)})
    except ValueError:
        pass
    aliases.discard("")
    for group in FAMILY_ALIAS_GROUPS:
        if aliases & group:
            aliases.update(group)
    return aliases


def forbidden_paths(value: Any, prefix: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            path = f"{prefix}.{key}"
            if str(key).lower() in FORBIDDEN_KEYS:
                found.append(path)
            found.extend(forbidden_paths(child, path))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            found.extend(forbidden_paths(child, f"{prefix}[{index}]"))
    return found


def _selected_values(value: Any, keys: set[str], active: bool = False) -> Iterable[str]:
    if isinstance(value, Mapping):
        if active:
            yield from (str(key) for key in value)
        for key, child in value.items():
            yield from _selected_values(child, keys, active or str(key).lower() in keys)
    elif isinstance(value, list):
        for child in value:
            yield from _selected_values(child, keys, active)
    elif active and isinstance(value, (str, int)) and str(value).strip():
        yield str(value)


def _read_records(path: Path) -> Any:
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return json.loads(path.read_text(encoding="utf-8"))


def _closure_digest(value: Mapping[str, Any]) -> str | None:
    tokens = value.get("tokens")
    families = value.get("family_aliases")
    counts = value.get("projection_counts")
    blockers = value.get("blocking_reasons")
    if not isinstance(tokens, (set, list, tuple)) or not isinstance(families, (set, list, tuple)):
        return None
    if not isinstance(counts, Mapping) or not isinstance(blockers, (list, tuple)):
        return None
    payload = {
        "artifact_count": value.get("artifact_count"),
        "all_pins_valid": value.get("all_pins_valid"),
        "projection_counts": dict(counts),
        "normalized_token_count": value.get("normalized_token_count"),
        "normalized_token_set_sha256": value.get("normalized_token_set_sha256"),
        "family_alias_count": value.get("family_alias_count"),
        "family_alias_set_sha256": value.get("family_alias_set_sha256"),
        "tokens": sorted(str(item) for item in tokens),
        "family_aliases": sorted(str(item) for item in families),
        "complete": value.get("complete"),
        "blocking_reasons": sorted(str(item) for item in blockers),
    }
    return stable_hash(payload)


def build_authority_closure(
    *, file_digests: Mapping[str, str | None] | None = None,
    records: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    actual_digests = {name: file_sha256(path) for name, path in UNIVERSE_SOURCES.items()}
    supplied_digests = dict(file_digests) if file_digests is not None else actual_digests
    blockers = [
        f"authority_pin_mismatch:{name}"
        for name, pin in UNIVERSE_PINS.items()
        if actual_digests.get(name) != pin or supplied_digests.get(name) != pin
    ]
    if file_digests is not None and supplied_digests != actual_digests:
        blockers.append("caller_file_digest_override_non_authoritative")
    if records is not None:
        blockers.append("injected_authority_records_non_authoritative")
        if forbidden_paths(records):
            blockers.append("injected_authority_records_forbidden_fields")

    tokens: set[str] = set()
    families = {alias for value in HISTORICAL_FAMILY_ALIASES for alias in family_aliases(value)}
    counts: dict[str, int] = {}
    for name, path in UNIVERSE_SOURCES.items():
        try:
            value = _read_records(path)
            projected = {normalize_identity(item) for item in _selected_values(value, IDENTITY_KEYS)} - {""}
            family_projected = {
                alias for item in _selected_values(value, FAMILY_KEYS) for alias in family_aliases(item)
            }
        except (OSError, ValueError, json.JSONDecodeError):
            projected = set()
            family_projected = set()
        counts[name] = len(projected)
        tokens.update(projected)
        families.update(family_projected)
        if not projected:
            blockers.append(f"authority_projection_empty:{name}")
    blockers.append("stage12578_authority_closure_incomplete")
    body = {
        "artifact_count": len(UNIVERSE_SOURCES),
        "all_pins_valid": not any(reason.startswith("authority_pin_mismatch:") for reason in blockers),
        "projection_counts": counts,
        "normalized_token_count": len(tokens),
        "normalized_token_set_sha256": stable_hash(sorted(tokens)),
        "family_alias_count": len(families),
        "family_alias_set_sha256": stable_hash(sorted(families)),
        "tokens": tokens,
        "family_aliases": families,
        "complete": False,
        "blocking_reasons": sorted(set(blockers)),
    }
    return {**body, "canonical_reconstruction_sha256": _closure_digest(body)}


def validate_allowlist(rows: Sequence[AllowlistedSource]) -> list[str]:
    blockers: list[str] = []
    if tuple(rows) != CANONICAL_ALLOWLIST or stable_hash([asdict(row) for row in rows]) != ALLOWLIST_SHA256:
        blockers.append("caller_allowlist_override_rejected")
    if Counter(row.language for row in rows) != Counter(LANGUAGE_QUOTAS):
        blockers.append("request_language_quota_mismatch")
    if len(rows) != 8:
        blockers.append("request_slot_count_not_exactly_eight")
    aliases: list[str] = []
    checkouts: list[str] = []
    for row in rows:
        try:
            remote = normalize_remote(row.canonical_remote)
        except ValueError as exc:
            blockers.append(f"{row.source_id}:{exc}")
            continue
        if remote != row.canonical_remote:
            blockers.append(f"{row.source_id}:noncanonical_remote")
        if row.language == "rust" and not HEX40.fullmatch(str(row.requested_commit or "")):
            blockers.append(f"{row.source_id}:moving_ref_placeholder_or_noncanonical_pin")
        if row.language == "web_js_ts_html" and row.requested_commit is not None:
            blockers.append(f"{row.source_id}:unverified_web_commit_pin_rejected")
        aliases.extend((normalize_identity(remote), normalize_identity(row.source_id)))
        checkouts.append(str(Path(row.checkout).resolve()))
    if len(aliases) != len(set(aliases)) or len(checkouts) != len(set(checkouts)):
        blockers.append("duplicate_allowlist_alias_or_checkout")
    return sorted(set(blockers))


def web_family_key(row: AllowlistedSource) -> str:
    return normalize_identity(normalize_remote(row.canonical_remote).rsplit("/", 1)[-1])


def validate_independent_web_quota(
    rows: Sequence[AllowlistedSource],
    authority_family_aliases: Iterable[str],
) -> list[str]:
    authority = set(authority_family_aliases)
    web = [row for row in rows if row.language == "web_js_ts_html"]
    eligible = [row for row in web if not (family_aliases(row.canonical_remote) | family_aliases(row.source_id)) & authority]
    blockers = []
    if len(eligible) != LANGUAGE_QUOTAS["web_js_ts_html"]:
        blockers.append("independent_web_request_quota_not_met")
    keys = [web_family_key(row) for row in eligible]
    if len(keys) != len(set(keys)):
        blockers.append("independent_web_request_families_not_pairwise_distinct")
    return blockers


def acquisition_request(
    row: AllowlistedSource,
    authority_family_aliases: Iterable[str] = (),
) -> dict[str, Any]:
    authority_overlap = bool(
        (family_aliases(row.canonical_remote) | family_aliases(row.source_id))
        & set(authority_family_aliases)
    )
    commit_present = bool(row.requested_commit and HEX40.fullmatch(row.requested_commit))
    commands: list[list[str]] = []
    if commit_present:
        commands = [
            ["git", "clone", "--no-checkout", "--filter=blob:none", row.canonical_remote, row.checkout],
            ["git", "-C", row.checkout, "fetch", "--depth=1", "origin", str(row.requested_commit)],
            ["git", "-C", row.checkout, "checkout", "--detach", str(row.requested_commit)],
        ]
    reasons = ["preoutcome_commit_authority_absent"]
    if authority_overlap:
        reasons.append("family_normalized_authority_overlap")
    if commit_present:
        reasons.append("requested_commit_diagnostic_self_attested")
        provenance = "diagnostic_self_attested"
    else:
        reasons.extend(("independent_commit_pin_missing", "acquisition_needed_independent_commit_pin"))
        provenance = "missing_independent_commit_pin"
    body = {
        "request_id": "acq_" + stable_hash(asdict(row))[:20],
        **asdict(row),
        "requested_ref_kind": "full_commit_oid_only" if commit_present else "independent_full_commit_oid_required",
        "requested_commit_provenance": provenance,
        "requested_commit_authoritative": False,
        "preoutcome_authority": False,
        "authority_family_overlap": authority_overlap,
        "independent_web_quota_eligible": row.language == "web_js_ts_html" and not authority_overlap,
        "reason_codes": sorted(reasons),
        "commands": commands,
        "execution_eligible": commit_present and not authority_overlap,
        "explicit_operator_execution_required": True,
        "network_command_executed": False,
        "cargo_or_npm_cache_accepted_as_provenance": False,
        "candidate": False,
        **ZERO,
    }
    return {**body, "request_sha256": stable_hash(body)}


def _git(repo: Path, *args: str, binary: bool = False) -> str | bytes:
    result = subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
    return result.stdout if binary else result.stdout.decode().strip()


def inspect_checkout(row: AllowlistedSource) -> dict[str, Any]:
    if not row.requested_commit or not HEX40.fullmatch(row.requested_commit):
        raise ValueError("independent_commit_pin_missing")
    repo = Path(row.checkout)
    if not repo.is_dir() or str(_git(repo, "rev-parse", "--is-inside-work-tree")) != "true":
        raise ValueError("source_native_git_checkout_absent")
    remote = normalize_remote(_git(repo, "remote", "get-url", "origin"))
    commit = str(_git(repo, "rev-parse", "HEAD^{commit}"))
    tree = str(_git(repo, "rev-parse", "HEAD^{tree}"))
    if remote != row.canonical_remote:
        raise ValueError("canonical_remote_mismatch")
    if commit != row.requested_commit or not HEX40.fullmatch(commit):
        raise ValueError("exact_requested_commit_mismatch")
    if not HEX40.fullmatch(tree):
        raise ValueError("malformed_tree_oid")
    if str(_git(repo, "status", "--porcelain=v1", "--untracked-files=all")):
        raise ValueError("dirty_tree")
    raw = bytes(_git(repo, "ls-tree", "-r", "-z", commit, binary=True))
    entries = []
    for item in raw.rstrip(b"\0").split(b"\0") if raw else []:
        prefix, path_bytes = item.split(b"\t", 1)
        mode, kind, oid = prefix.decode().split()
        path = path_bytes.decode()
        if kind == "blob" and mode in {"100644", "100755"}:
            entries.append((path, oid))
    source = [(path, oid) for path, oid in entries if path.lower().endswith(SOURCE_SUFFIXES)]
    tests = [(path, oid) for path, oid in source if any(part.startswith("test") for part in path.lower().split("/"))]
    if not source or not tests:
        raise ValueError("tracked_source_or_test_blobs_missing")
    if len(source) > 4096:
        raise ValueError("bounded_source_blob_limit_exceeded")
    blob_rows = []
    total = 0
    for path, oid in source:
        content = bytes(_git(repo, "cat-file", "blob", oid, binary=True))
        total += len(content)
        if total > 32 * 1024 * 1024:
            raise ValueError("bounded_source_bytes_limit_exceeded")
        blob_rows.append({"path": path, "blob_oid": oid, "content_sha256": hashlib.sha256(content).hexdigest()})
    diff = str(_git(repo, "diff-tree", "--root", "--no-commit-id", "--name-only", "-r", commit)).splitlines()
    diff_source = [path for path in diff if path.lower().endswith(SOURCE_SUFFIXES)]
    diff_tests = [path for path in diff_source if any(part.startswith("test") for part in path.lower().split("/"))]
    evidence_ready = bool(diff_source and diff_tests)
    identity_tokens = {
        normalize_identity(value)
        for value in [remote, row.source_id, commit, tree, *[item for pair in source for item in pair]]
    } - {""}
    candidate_families = family_aliases(remote) | family_aliases(row.source_id)
    body = {
        "source_id": row.source_id, "canonical_remote": remote, "requested_commit": commit,
        "tree_oid": tree, "tracked_source_blob_count": len(source),
        "tracked_test_blob_count": len(tests), "tracked_source_bytes": total,
        "tracked_blob_set_sha256": stable_hash(blob_rows), "clean_committed_content": True,
        "task_diff_evidence_ready": evidence_ready, "task_diff_path_set_sha256": stable_hash(sorted(diff)),
        "preoutcome_four_stratum_binding_ready": evidence_ready,
        "preoutcome_stratum_bindings": {
            stratum: stable_hash([remote, commit, tree, stable_hash(blob_rows), stable_hash(sorted(diff)), stratum])
            for stratum in STRATA
        } if evidence_ready else {},
        "identity_tokens": identity_tokens,
        "family_aliases": candidate_families,
    }
    hashable = {**body, "identity_tokens": sorted(identity_tokens), "family_aliases": sorted(candidate_families)}
    return {**body, "observation_sha256": stable_hash(hashable)}


def observation_mutation_reasons(observations: Sequence[Mapping[str, Any]]) -> list[str]:
    if len(observations) != 3:
        return ["three_checkout_observations_required"]
    if len({item.get("observation_sha256") for item in observations}) != 1:
        return ["source_mutated_during_validation", "source_mutated_before_emission"]
    return []


def canonical_request_artifact() -> dict[str, Any]:
    authority = build_authority_closure()
    requests = [acquisition_request(row, authority["family_aliases"]) for row in CANONICAL_ALLOWLIST]
    return {
        "request_count": len(requests),
        "request_quota_by_language": dict(Counter(row.language for row in CANONICAL_ALLOWLIST)),
        "requests": requests,
        "network_clone_performed": False,
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def execute_acquisition(
    request_sha256: str,
    *,
    enabled: bool = False,
    request_artifact: Path | None = None,
    receipt_path: Path | None = None,
) -> dict[str, Any]:
    if not enabled:
        raise PermissionError("acquisition_executor_disabled")
    artifact = json.loads((request_artifact or OUT / "acquisition_requests.json").read_text(encoding="utf-8"))
    if artifact != canonical_request_artifact():
        raise ValueError("generated_request_artifact_mismatch")
    matches = [row for row in artifact["requests"] if row.get("request_sha256") == request_sha256]
    if len(matches) != 1:
        raise ValueError("exact_generated_request_hash_required")
    request = matches[0]
    body = {key: value for key, value in request.items() if key != "request_sha256"}
    if stable_hash(body) != request_sha256:
        raise ValueError("request_hash_integrity_failure")
    if request.get("execution_eligible") is not True or not request.get("commands"):
        raise PermissionError("request_missing_independent_executable_commit_pin")
    if Path(str(request["checkout"])).exists():
        raise FileExistsError("checkout_path_already_exists")

    started = datetime.now(timezone.utc).isoformat()
    command_results: list[dict[str, Any]] = []
    failure: subprocess.CalledProcessError | None = None
    for command in request["commands"]:
        try:
            completed = subprocess.run(command, check=True)
            command_results.append({"command": command, "returncode": completed.returncode, "succeeded": True})
        except subprocess.CalledProcessError as exc:
            command_results.append({"command": command, "returncode": exc.returncode, "succeeded": False})
            failure = exc
            break
    receipt = {
        "record_type": "stage12579_acquisition_execution_receipt_v1",
        "request_sha256": request_sha256,
        "request_id": request["request_id"],
        "started_at_utc": started,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "execution_enabled": True,
        "execution_occurred": bool(command_results),
        "network_command_executed": bool(command_results),
        "command_count_planned": len(request["commands"]),
        "command_count_attempted": len(command_results),
        "command_count_succeeded": sum(item["succeeded"] for item in command_results),
        "status": "failed" if failure else "completed",
        "command_results": command_results,
    }
    receipt = {**receipt, "receipt_sha256": stable_hash(receipt)}
    write_json(receipt_path or OUT / "execution_receipt.json", receipt)
    if failure is not None:
        raise failure
    return receipt


def build_stage(
    *,
    allowlist: Sequence[AllowlistedSource] = CANONICAL_ALLOWLIST,
    stage12578_digest: str | None = None,
    stage12578_record: Mapping[str, Any] | None = None,
    closure: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    blockers = validate_allowlist(allowlist)

    canonical_stage12578_digest = file_sha256(STAGE12578)
    canonical_stage12578 = json.loads(STAGE12578.read_text(encoding="utf-8"))
    supplied_digest = stage12578_digest if stage12578_digest is not None else canonical_stage12578_digest
    record_injected = stage12578_record is not None
    supplied_record = stage12578_record if record_injected else canonical_stage12578
    record_forbidden = forbidden_paths(supplied_record) if record_injected else []
    exact_stage12578_binding = (
        canonical_stage12578_digest == STAGE12578_FILE_SHA256
        and supplied_digest == canonical_stage12578_digest
        and isinstance(supplied_record, Mapping)
        and stable_hash(dict(supplied_record)) == stable_hash(canonical_stage12578)
        and not record_forbidden
    )
    if not exact_stage12578_binding:
        blockers.append("stage12578_caller_record_non_authoritative")
    if record_forbidden:
        blockers.append("stage12578_injected_record_forbidden_fields")
    if canonical_stage12578.get("summary_record_sha256") != STAGE12578_RECORD_SHA256:
        blockers.append("stage12578_pin_or_record_mismatch")
    if canonical_stage12578.get("stage") != "stage12578_prospective_source_acquisition_and_structural_preoutcome_seal":
        blockers.append("stage12578_identity_mismatch")

    authority = build_authority_closure()
    canonical_closure_digest = authority["canonical_reconstruction_sha256"]
    closure_injected = closure is not None
    supplied_closure_digest = _closure_digest(closure) if isinstance(closure, Mapping) else None
    closure_forbidden = forbidden_paths(closure) if closure_injected else []
    exact_closure_binding = (
        not closure_injected
        or (
            supplied_closure_digest == canonical_closure_digest
            and closure.get("canonical_reconstruction_sha256") == canonical_closure_digest
            and not closure_forbidden
        )
    )
    if not exact_closure_binding:
        blockers.append("caller_authority_closure_non_authoritative")
    if closure_forbidden:
        blockers.append("caller_authority_closure_forbidden_fields")
    blockers.extend(authority["blocking_reasons"])
    blockers.append("authority_closure_incomplete")

    requests = [
        acquisition_request(row, authority["family_aliases"])
        for row in CANONICAL_ALLOWLIST
    ]
    if len(requests) != 8 or Counter(row["language"] for row in requests) != Counter(LANGUAGE_QUOTAS):
        blockers.append("canonical_request_quota_invariant_failed")
    blockers.extend(validate_independent_web_quota(CANONICAL_ALLOWLIST, authority["family_aliases"]))
    for request in requests:
        blockers.extend(f"{request['source_id']}:{reason}" for reason in request["reason_codes"])

    diagnostics: list[dict[str, Any]] = []
    closure_tokens = set(authority["tokens"])
    closure_families = set(authority["family_aliases"])
    for row, request in zip(CANONICAL_ALLOWLIST, requests, strict=True):
        base = {
            "source_id": row.source_id, "language": row.language, "candidate": False,
            "preoutcome_authority": False, **ZERO,
        }
        if row.requested_commit is None:
            diagnostics.append({**base, "reason_codes": request["reason_codes"]})
            continue
        if not Path(row.checkout).is_dir():
            diagnostics.append({**base, "reason_codes": sorted({"source_native_git_checkout_absent", *request["reason_codes"]})})
            blockers.append(f"source_native_git_checkout_absent:{row.source_id}")
            continue
        try:
            first = inspect_checkout(row)
            second = inspect_checkout(row)
            third = inspect_checkout(row)
        except (OSError, ValueError, subprocess.CalledProcessError) as exc:
            diagnostics.append({**base, "reason_codes": [f"checkout_validation_failed:{exc}"]})
            blockers.append(f"checkout_validation_failed:{row.source_id}:{exc}")
            continue
        reasons = list(request["reason_codes"])
        reasons.extend(observation_mutation_reasons((first, second, third)))
        if first["identity_tokens"] & closure_tokens:
            reasons.append("full_normalized_authority_overlap")
        if first["family_aliases"] & closure_families:
            reasons.append("family_normalized_authority_overlap")
        reasons.append("authority_closure_incomplete")
        if not exact_stage12578_binding:
            reasons.append("stage12578_binding_non_authoritative")
        if not exact_closure_binding:
            reasons.append("authority_closure_binding_non_authoritative")
        if first["task_diff_evidence_ready"] is not True:
            reasons.append("task_diff_evidence_not_ready")
        if first["preoutcome_four_stratum_binding_ready"] is not True:
            reasons.append("preoutcome_four_stratum_binding_not_ready")
        public = {key: value for key, value in first.items() if key not in {"identity_tokens", "family_aliases"}}
        reasons = sorted(set(reasons))
        diagnostics.append({**public, **base, "reason_codes": reasons})
        blockers.extend(f"{row.source_id}:{reason}" for reason in reasons)

    blockers = sorted(set(blockers))
    body = {
        "stage": STAGE,
        "record_type": "stage12579_bounded_source_native_replacement_acquisition_v2",
        "decision": "blocked_fail_closed_zero_credit",
        "stage12578_file_sha256": canonical_stage12578_digest,
        "stage12578_record_sha256": canonical_stage12578.get("summary_record_sha256"),
        "stage12578_record_injected": record_injected,
        "exact_canonical_stage12578_binding": exact_stage12578_binding,
        "immutable_allowlist_sha256": ALLOWLIST_SHA256,
        "immutable_allowlist_count": len(CANONICAL_ALLOWLIST),
        "caller_allowlist_override_used": tuple(allowlist) != CANONICAL_ALLOWLIST,
        "required_request_quota_by_language": LANGUAGE_QUOTAS,
        "authority_artifact_count": authority["artifact_count"],
        "authority_all_pins_valid": authority["all_pins_valid"],
        "authority_closure_complete": False,
        "authority_closure_injected": closure_injected,
        "exact_canonical_authority_binding": exact_closure_binding,
        "canonical_authority_reconstruction_sha256": canonical_closure_digest,
        "normalized_authority_token_count": authority["normalized_token_count"],
        "normalized_authority_token_set_sha256": authority["normalized_token_set_sha256"],
        "normalized_authority_family_count": authority["family_alias_count"],
        "normalized_authority_family_set_sha256": authority["family_alias_set_sha256"],
        "input_policy": "pinned_file_identity_and_provenance_only_no_injected_or_outcome_selection",
        "forbidden_outcome_metric_verifier_correctness_fields_read_for_selection": [],
        "cargo_or_npm_cache_accepted_as_git_provenance": False,
        "network_clone_performed": False,
        "execution_performed": False,
        "execution_receipt_emitted": False,
        "candidate_count": 0, "candidates": [],
        "diagnostic_count": len(diagnostics), "diagnostics": diagnostics,
        "acquisition_request_count": len(requests), "acquisition_requests": requests,
        "acquisition_request_count_by_language": dict(Counter(row["language"] for row in requests)),
        "independent_web_request_quota_count": sum(
            row["independent_web_quota_eligible"] for row in requests
        ),
        "required_transition_strata": list(STRATA),
        "training_performed": False, "evaluation_performed": False, "admission_performed": False,
        "blocking_reasons": blockers,
        **ZERO,
    }
    return {**body, "summary_record_sha256": stable_hash(body)}


def write_artifacts(result: Mapping[str, Any]) -> None:
    request_artifact = {
        "request_count": result["acquisition_request_count"],
        "request_quota_by_language": result["acquisition_request_count_by_language"],
        "requests": result["acquisition_requests"],
        "network_clone_performed": False,
    }
    write_json(OUT / "readiness.json", result)
    write_json(OUT / "acquisition_requests.json", request_artifact)
    write_json(OUT / "candidates.json", {"candidate_count": 0, "candidates": [], **ZERO})
    write_json(OUT / "exact_blockers.json", {"blocking_reasons": result["blocking_reasons"]})
    write_json(OUT / "summary.json", result)
    write_json(SUMMARY, result)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-request-sha256")
    parser.add_argument("--enable-acquisition-execution", action="store_true")
    parser.add_argument("--execution-receipt", type=Path)
    args = parser.parse_args()
    if args.execute_request_sha256:
        receipt = execute_acquisition(
            args.execute_request_sha256,
            enabled=args.enable_acquisition_execution,
            receipt_path=args.execution_receipt,
        )
        print(json.dumps(receipt, sort_keys=True))
        return 0
    if args.enable_acquisition_execution:
        parser.error("--enable-acquisition-execution requires --execute-request-sha256")
    result = build_stage()
    write_artifacts(result)
    print(json.dumps({key: result[key] for key in ("decision", "candidate_count", "acquisition_request_count", "blocking_reasons")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
