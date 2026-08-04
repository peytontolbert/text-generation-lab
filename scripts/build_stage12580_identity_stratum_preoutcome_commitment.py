#!/usr/bin/env python3
"""Construct an unpublished, zero-authority identity/stratum preimage."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12580_identity_stratum_preoutcome_commitment"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
STAGE12579 = ROOT / "runs/local/artifacts/stage12579_bounded_source_native_replacement_acquisition/acquisition_requests.json"
STAGE12579_FILE_SHA256 = "5e74ea058e780dd4b945a894d4c2dce232345148fd6f676657631e7c170ae072"
EXPECTED_REQUEST_HASHES = (
    "9faeeadf4e3cb8ab72180c3b08f6df8da5eed7c848a2f8b2a6dd801bc56f4536",
    "703a085d0f6d6ec41d7213fa743940800079476e22012bcf0aaa99b92947e53c",
    "d18c848270ca71ebbc3bba08ac3ee5e9f56116b56fc55a3c124e79a3fa488870",
    "7fefa185c4902987b6e1bb890a3a86aed6cccd71c0ce66080b5565e4a1457b02",
    "2ab3941a532329abdea65ee18c84889470fb7c867222499e2cbba8069d6a7e07",
    "3a3c85676a8f8d8d04ca0ebb90dabba9ae498b7cc04defbd44bdda91c8ced7e4",
    "3a27bd1ac0ad1f4315181fa532c5fbb99caff1083c6c8f414c19f38d42cde1f0",
    "a11580489c08a9793a0b0c4deeba1f70f2755b2e0f0d78db5ffa6dff78ef15a7",
)
QUOTA_ITEMS = (("rust", 4), ("web_js_ts_html", 4))
STRATA = (
    "transition_candidate_selection",
    "transition_continue_or_stop",
    "transition_next_action",
    "transition_verifier_transition",
)
EXPECTED_IDENTITIES = (
    ("serde", "https://github.com/serde-rs/serde", "rust"),
    ("clap", "https://github.com/clap-rs/clap", "rust"),
    ("petgraph", "https://github.com/petgraph/petgraph", "rust"),
    ("indexmap", "https://github.com/indexmap-rs/indexmap", "rust"),
    ("lodash", "https://github.com/lodash/lodash", "web_js_ts_html"),
    ("chalk", "https://github.com/chalk/chalk", "web_js_ts_html"),
    ("pnpm", "https://github.com/pnpm/pnpm", "web_js_ts_html"),
    ("ms", "https://github.com/vercel/ms", "web_js_ts_html"),
)
COMMITMENT_DOMAIN = "agentkernel.stage12580.identity-four-stratum-local-preimage"
MANIFEST_DOMAIN = "agentkernel.stage12580.ordered-sanitized-identity-manifest"
OPAQUE_ID_DOMAIN = "agentkernel.stage12580.opaque-candidate-id"
VERSION = "2"
DOMAIN_SEPARATION_SALT = "9ff17a454f5f3e0c90311c3356bacc06a4a55b816a1f476c174ad818702ee607"
CHRONOLOGY_BLOCKERS = (
    "commitment_not_externally_published",
    "preoutcome_chronology_unproven",
    "trusted_timestamp_absent",
)
DENY_FIELDS = (
    "acquisition_execution_allowed", "execution_authorized", "network_clone_performed",
    "candidate", "preoutcome_authority", "requested_commit_authoritative",
    "training_allowed", "evaluation_allowed", "admission_allowed", "clearance_granted",
    "root_credit", "repair_credit", "level3_credit", "protected_clearance",
    "use_clearance", "replay_allowed", "strict_eval_eligible", "gpu_allowed",
)
ZERO = {key: False for key in DENY_FIELDS}
OUTCOME_KEYS = {
    "accuracy", "correct", "correctness", "gold", "gold_label", "loss", "metric",
    "metrics", "model_score", "outcome", "prediction", "reward", "score", "scores",
    "target_label", "test_outcome", "test_result", "verifier_outcome", "verifier_result",
}
FORBIDDEN_PREIMAGE_KEYS = OUTCOME_KEYS | {
    "blob", "blob_oid", "checkout", "commands", "commit", "commit_oid",
    "intended_acquisition_path", "path", "primary_stratum", "reason_codes",
    "request_id", "request_sha256", "requested_commit", "tree", "tree_oid",
}
ROW_KEYS = {
    "ordinal", "source_id", "opaque_candidate_id", "canonical_remote", "language",
    "required_transition_strata",
}
HEX40 = re.compile(r"^[0-9a-f]{40}$")


def quota() -> dict[str, int]:
    return dict(QUOTA_ITEMS)


def stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def forbidden_paths(value: Any, keys: set[str], prefix: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            path = f"{prefix}.{key}"
            if str(key).lower() in keys:
                found.append(path)
            found.extend(forbidden_paths(child, keys, path))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            found.extend(forbidden_paths(child, keys, f"{prefix}[{index}]"))
    return found


def aliases(source_id: Any, remote: Any) -> set[str]:
    parsed = urlparse(str(remote))
    parts = parsed.path.strip("/").split("/")
    if parsed.scheme != "https" or parsed.hostname != "github.com" or len(parts) != 2:
        return set()
    owner, repo = parts
    if repo.endswith(".git") or str(remote) != f"https://github.com/{owner.lower()}/{repo.lower()}":
        return set()
    norm = lambda value: re.sub(r"[^a-z0-9]", "", str(value).lower())
    return {norm(source_id), norm(repo), norm(owner + repo)} - {""}


def sanitize(requests: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ordinal, request in enumerate(requests):
        identity = {
            "source_id": request.get("source_id"),
            "canonical_remote": request.get("canonical_remote"),
            "language": request.get("language"),
        }
        opaque = stable_hash({"domain": OPAQUE_ID_DOMAIN, "version": VERSION, **identity})[:24]
        rows.append({
            "ordinal": ordinal,
            "source_id": identity["source_id"],
            "opaque_candidate_id": f"opaque_{opaque}",
            "canonical_remote": identity["canonical_remote"],
            "language": identity["language"],
            "required_transition_strata": list(STRATA),
        })
    return rows


def construct_preimages(requests: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    rows = sanitize(requests)
    manifest = {"domain": MANIFEST_DOMAIN, "version": VERSION, "rows": rows}
    commitment = {
        "domain": COMMITMENT_DOMAIN,
        "version": VERSION,
        "domain_separation": {
            "salt_hex": DOMAIN_SEPARATION_SALT,
            "role": "domain_separation_only_not_chronology_or_issuance_proof",
        },
        "rows": rows,
    }
    return manifest, commitment


def _validate_record(record: Any) -> tuple[list[str], list[Mapping[str, Any]], list[str], int]:
    blockers: list[str] = []
    if not isinstance(record, Mapping):
        return ["stage12579_record_not_object"], [], [], 0
    requests = record.get("requests") if isinstance(record.get("requests"), list) else []
    if not isinstance(record.get("requests"), list):
        blockers.append("stage12579_requests_missing")
    if forbidden_paths(record, OUTCOME_KEYS):
        blockers.append("outcome_field_present")
    if len(requests) != 8 or record.get("request_count") != 8:
        blockers.append("request_count_not_exactly_eight")

    reconstructed: list[str] = []
    identities: list[tuple[Any, Any, Any]] = []
    family_sets: list[set[str]] = []
    paths: list[Any] = []
    rust_oid_count = 0
    typed_requests: list[Mapping[str, Any]] = []
    for index, row in enumerate(requests):
        if not isinstance(row, Mapping):
            blockers.append(f"malformed_request:{index}")
            continue
        typed_requests.append(row)
        digest = stable_hash({key: value for key, value in row.items() if key != "request_sha256"})
        reconstructed.append(digest)
        if row.get("request_sha256") != digest:
            blockers.append(f"request_hash_mismatch:{index}")
        identity = (row.get("source_id"), row.get("canonical_remote"), row.get("language"))
        identities.append(identity)
        family = aliases(identity[0], identity[1])
        family_sets.append(family)
        if not family:
            blockers.append(f"noncanonical_identity:{index}")
        paths.append(row.get("checkout"))
        if row.get("candidate") is not False or row.get("preoutcome_authority") is not False or row.get("requested_commit_authoritative") is not False:
            blockers.append(f"nonzero_candidate_or_authority:{index}")
        if any(row.get(field) is not False for field in DENY_FIELDS[6:]):
            blockers.append(f"nonzero_credit_or_grant:{index}")
        if row.get("language") == "rust" and HEX40.fullmatch(str(row.get("requested_commit") or "")):
            rust_oid_count += 1
    if tuple(reconstructed) != EXPECTED_REQUEST_HASHES:
        blockers.append("request_hash_sequence_mismatch")
    if tuple(identities) != EXPECTED_IDENTITIES:
        blockers.append("request_order_or_identity_mismatch")
    if dict(Counter(item[2] for item in identities)) != quota() or record.get("request_quota_by_language") != quota():
        blockers.append("request_quota_missing_or_mismatch")
    for left in range(len(family_sets)):
        for right in range(left + 1, len(family_sets)):
            if family_sets[left] & family_sets[right]:
                blockers.append("duplicate_or_overlapping_family_alias")
    if len({item[0] for item in identities}) != len(identities) or len(set(paths)) != len(paths):
        blockers.append("duplicate_identity_or_acquisition_path")
    if rust_oid_count != 4:
        blockers.append("rust_diagnostic_commit_oid_count_mismatch")
    return sorted(set(blockers)), typed_requests, reconstructed, rust_oid_count


def _assemble(record: Any, observed_digest: str | None, *, canonical_bytes_bound: bool) -> dict[str, Any]:
    structural_blockers, requests, reconstructed, rust_oid_count = _validate_record(record)
    if observed_digest != STAGE12579_FILE_SHA256:
        structural_blockers.append("stage12579_file_pin_mismatch")
    if not canonical_bytes_bound:
        structural_blockers.append("detached_record_noncanonical")
    structural_blockers = sorted(set(structural_blockers))
    manifest_preimage, commitment_preimage = construct_preimages(requests)
    preimage_forbidden = forbidden_paths(commitment_preimage, FORBIDDEN_PREIMAGE_KEYS)
    rows = commitment_preimage["rows"]
    if any(set(row) != ROW_KEYS for row in rows) or preimage_forbidden:
        structural_blockers.append("commitment_preimage_allowlist_violation")
    structural_blockers = sorted(set(structural_blockers))
    local_valid = not structural_blockers
    if not local_valid:
        manifest_preimage = {"domain": MANIFEST_DOMAIN, "version": VERSION, "rows": []}
        commitment_preimage = None
        rows = []
    manifest_hash = stable_hash(manifest_preimage) if local_valid else None
    root_hash = stable_hash(commitment_preimage) if local_valid else None
    routing = [{
        "ordinal": index,
        "opaque_candidate_id": row["opaque_candidate_id"],
        "primary_stratum": STRATA[index % len(STRATA)],
        "authoritative": False,
        "committed": False,
    } for index, row in enumerate(rows)]
    blockers = sorted(set(structural_blockers) | set(CHRONOLOGY_BLOCKERS))
    audit = {
        "stage12579_bytes_read_once": canonical_bytes_bound,
        "sha256_and_json_parse_share_same_bytes": canonical_bytes_bound,
        "stage12579_file_sha256": observed_digest,
        "stage12579_file_pin_valid": observed_digest == STAGE12579_FILE_SHA256,
        "reconstructed_request_sha256": reconstructed,
        "request_hashes_valid": tuple(reconstructed) == EXPECTED_REQUEST_HASHES,
        "audit_metadata_in_commitment_preimage": False,
        "rust_diagnostic_commit_oid_count_observed": rust_oid_count,
        "rust_diagnostic_commit_oids_in_commitment_preimage": [],
        "rust_diagnostic_commit_oids_explicitly_excluded": local_valid and rust_oid_count == 4,
        "requested_commit_tree_blob_commands_reason_codes_path_absent": local_valid and not preimage_forbidden,
        "commitment_preimage_forbidden_paths": preimage_forbidden,
    }
    body = {
        "stage": STAGE,
        "record_type": "stage12580_identity_stratum_preoutcome_commitment_v2",
        "decision": "local_identity_preimage_constructed_unpublished_zero_credit",
        "local_identity_preimage_constructed": local_valid,
        "commitment_valid": False,
        "preoutcome_chronology_proven": False,
        "externally_published": False,
        "trusted_timestamp": False,
        "commitment_root_sha256": root_hash,
        "ordered_manifest_sha256": manifest_hash,
        "commitment_preimage": commitment_preimage,
        "ordered_manifest": rows,
        "primary_stratum_routing_metadata": routing,
        "primary_stratum_routing_authoritative": False,
        "primary_stratum_routing_committed": False,
        "request_count": len(rows),
        "request_quota_by_language": quota() if local_valid else {},
        "pairwise_family_disjoint": local_valid,
        "audit_only_stage12579_validation": audit,
        "blocking_reasons": blockers,
        **ZERO,
    }
    return {**body, "summary_record_sha256": stable_hash(body)}


def _build_from_canonical_bytes(raw: bytes) -> dict[str, Any]:
    digest = hashlib.sha256(raw).hexdigest()
    try:
        record = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        record = None
    return _assemble(record, digest, canonical_bytes_bound=True)


def build_from_record(record: Any, claimed_digest: str | None = None, **_overrides: Any) -> dict[str, Any]:
    """Hostile-test surface; detached inputs can never produce a valid preimage."""
    return _assemble(record, claimed_digest, canonical_bytes_bound=False)


def build_stage(*, request_artifact: Any = None, observed_file_sha256: str | None = None,
                issuance: Any = None, nonce: Any = None, salt: Any = None) -> dict[str, Any]:
    if any(value is not None for value in (request_artifact, observed_file_sha256, issuance, nonce, salt)):
        result = build_from_record(request_artifact, observed_file_sha256)
        reasons = sorted(set(result["blocking_reasons"]) | {"caller_override_noncanonical"})
        body = {key: value for key, value in result.items() if key != "summary_record_sha256"}
        body["blocking_reasons"] = reasons
        return {**body, "summary_record_sha256": stable_hash(body)}
    try:
        raw = STAGE12579.read_bytes()
    except OSError:
        raw = b""
    return _build_from_canonical_bytes(raw)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_artifacts(result: Mapping[str, Any]) -> None:
    manifest = {
        "domain": MANIFEST_DOMAIN,
        "version": VERSION,
        "ordered_manifest_sha256": result["ordered_manifest_sha256"],
        "rows": result["ordered_manifest"],
        "externally_published": False,
        "trusted_timestamp": False,
        **ZERO,
    }
    write_json(OUT / "ordered_identity_stratum_manifest.json", manifest)
    write_json(OUT / "identity_stratum_commitment.json", result)
    write_json(OUT / "summary.json", result)
    write_json(SUMMARY, result)


def main() -> int:
    result = build_stage()
    write_artifacts(result)
    print(json.dumps({key: result[key] for key in (
        "decision", "local_identity_preimage_constructed", "commitment_valid",
        "commitment_root_sha256", "ordered_manifest_sha256", "blocking_reasons",
    )}, sort_keys=True))
    return 0 if result["local_identity_preimage_constructed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
