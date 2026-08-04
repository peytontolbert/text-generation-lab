#!/usr/bin/env python3
"""Stage12572 runtime over commitment-only and source-native projections."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12572_source_native_protected_root_preimage_reconstruction_census"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
SOURCES = {
    "commitment_projection": OUT / "stage12105_commitment_projection.json",
    "source_projection": OUT / "source_native_projection.json",
    "observer_matrix": OUT / "observer_matrix.json",
}
PINNED_SOURCE_FILE_SHA256 = {
    "source_projection": "d054b17acc0d6055355690120bdf410d03f3723416bc9f66e34f118fbba2e956",
}
PINNED_EVIDENCE_FILE_SHA256 = {
    "commitment_projection": "e8d0af7aca578fc3883c9ebba9b8bde2b899cb0e1df39062e45e4b19bb2add91",
    "observer_matrix": "5976b177c48fb0bccaf4803b762517f6afc6f92d425ae0daf6483936c27c1990",
}
PINNED_GENERATOR = {
    "identity": "stage12572_guarded_commitment_projection_generator_v2",
    "file_sha256": "f42375f36714e59dc390fb13498685e0e3e53434a3f4a6edf6473cc42c71d29a",
}
PINNED_ORIGINAL_SOURCE_SHA256 = {
    "stage11347": "b5e1d4fe5edfbd45d31989f97f5d5045e660f1dca17634ff3b9faa9b56932e73",
    "stage11353": "6d4ed3484b4ff914d914810681e8cef2847b9f2178d98002fccc105f0e354b8a",
    "stage11364": "0e8ed9288527a405475c0dcd8b70886771596fc62db5b0d39e012b89f55f259a",
    "stage11537": "dccc373df0617911076212d8b7c0bb567b0759a431f60a9c147f8434b184ac97",
    "stage11545": "6288ab5e83b8dbba6c43827246055b5aa5896685384e23c712377fdba490ae54",
    "stage11576": "b42c576a0cd952c34e94a8907b8b404954307aade8f367bacd4fe991d53e77d9",
    "stage11811": "b1296c7d299f5d46278a988ebd9ca526d1786c23c686a1c2782deb919df5065c",
}
CANONICAL_PROTECTED_ROOT_HASH_SET_SHA256 = "e85fc0827bfcd9e5819fbc862f060afe35617d00b2c67b77a7effbc811541deb"
IMMUTABLE_SOURCE_BRIDGE_ROOT_SET_SHA256 = "d7866db7e54ccb58a4146275c25e31dd68100496823747e8d0870f64d99b5b65"
DIGEST_RE = re.compile(r"^[0-9a-f]{64}\Z")
OID_RE = re.compile(r"^[0-9a-f]{40}\Z")
AUTHORITY_FIELDS = (
    "authorization_allowed", "admission_allowed", "training_allowed",
    "replay_allowed", "gpu_allowed", "execution_authorized", "root_credit",
    "repair_credit", "level3_credit", "strict_eval_eligible",
)
ZERO = {name: False for name in AUTHORITY_FIELDS}
SOURCE_ROW_FIELDS = {
    "bridge_id", "record_schema", "source_artifact_ids", "protected_root_hash",
    "constructor_arguments_sha256", "source_repo_path", "git_repo_family",
    "canonical_repo", "commit_oid", "files", "file_set_sha256",
}
OBSERVER_ROW_FIELDS = {"record_schema", "bridge_id", "repo_path", "tree_oid"}
FILE_FIELDS = {"path", "blob_oid", "content_sha256"}
SOURCE_SCHEMAS = {
    "stage11347_11353_git_revision_source_v1": "full_revision_prior_root",
    "stage11364_git_revision_source_v1": "full_revision_prior_root",
    "stage11537_git_revision_source_v1": "full_revision_prior_root",
    "stage11545_git_revision_source_v1": "full_revision_prior_root",
    "stage11576_source_v1": "stage11576_deterministic_constructor",
    "stage11811_fixed_snapshot_v1": "stage11811_fixed_git_snapshot",
}
EXPECTED_ARTIFACT_IDS = {
    "stage11347_11353_git_revision_source_v1": ["stage11347", "stage11353"],
    "stage11364_git_revision_source_v1": ["stage11364"],
    "stage11537_git_revision_source_v1": ["stage11537"],
    "stage11545_git_revision_source_v1": ["stage11545"],
    "stage11576_source_v1": ["stage11576"],
    "stage11811_fixed_snapshot_v1": ["stage11811"],
}
CANONICAL_REPOS = {
    "modelcontextprotocol_typescript_sdk": "https://github.com/modelcontextprotocol/typescript-sdk.git",
    "sourcebot": "https://github.com/sourcebot-dev/sourcebot.git",
    "openclaw_clawhub": "https://github.com/openclaw/clawhub.git",
    "openhands_openhands": "https://github.com/OpenHands/OpenHands.git",
    "llama_stack": "https://github.com/llamastack/llama-stack.git",
    "llm_memory_modules_at_scale": "https://github.com/peytontolbert/llm_memory_modules_at_scale.git",
}
FORBIDDEN_KEYS = {
    "stage12105_root_key", "gold", "gold_label", "gold_patch", "outcome",
    "reward", "target", "target_label", "target_text", "verifier_output",
    "verifier_outcome", "verifier_result", "independently_authorized",
}


def stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode()).hexdigest()


def file_sha256(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def json_document_sha256(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, indent=2, sort_keys=True) + "\n"
    return hashlib.sha256(payload.encode()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def leakage_reasons(value: Any, location: str = "$") -> list[str]:
    reasons: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            name = str(key).lower()
            if name in FORBIDDEN_KEYS:
                reasons.append(f"forbidden_field:{location}.{name}")
            reasons.extend(leakage_reasons(child, f"{location}.{name}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reasons.extend(leakage_reasons(child, f"{location}[{index}]"))
    return sorted(set(reasons))


def _pins_valid(
    supplied: Mapping[str, str | None] | None, expected: Mapping[str, str]
) -> bool:
    return (
        isinstance(supplied, Mapping) and set(supplied) == set(expected)
        and all(supplied.get(key) == value for key, value in expected.items())
    )


def _run_git(repo: Path, args: Sequence[str]) -> tuple[int, bytes, bytes]:
    env = os.environ.copy()
    env["GIT_NO_LAZY_FETCH"] = "1"
    env["GIT_ALTERNATE_OBJECT_DIRECTORIES"] = ""
    process = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, check=False, env=env
    )
    return process.returncode, process.stdout, process.stderr


def _git(
    runner: Callable[[Path, Sequence[str]], tuple[int, bytes, bytes]],
    repo: Path, args: Sequence[str],
) -> tuple[int, bytes]:
    code, stdout, _ = runner(repo, args)
    return code, stdout


def _git_text(runner, repo: Path, args: Sequence[str]) -> str | None:
    code, stdout = _git(runner, repo, args)
    return stdout.decode().strip() if code == 0 else None


def verify_git_observation(
    observer: Mapping[str, Any], source: Mapping[str, Any],
    *, runner: Callable[[Path, Sequence[str]], tuple[int, bytes, bytes]] = _run_git,
) -> list[str]:
    blockers: list[str] = []
    if set(observer) != OBSERVER_ROW_FIELDS:
        blockers.append("observer_schema_not_exact")
    if set(source) != SOURCE_ROW_FIELDS:
        blockers.append("source_schema_not_exact")
    if leakage_reasons(observer) or leakage_reasons(source):
        blockers.append("forbidden_projection_leakage")
    if blockers:
        return sorted(set(blockers))
    if observer["record_schema"] != "stage12572_git_object_observation_v2":
        blockers.append("unexpected_observer_schema")
    if source["record_schema"] not in SOURCE_SCHEMAS:
        blockers.append("unexpected_source_schema")
    if source.get("source_artifact_ids") != EXPECTED_ARTIFACT_IDS.get(source.get("record_schema")):
        blockers.append("source_artifact_ids_mismatch")
    source_core = {key: value for key, value in source.items() if key != "bridge_id"}
    if source["bridge_id"] != stable_hash(source_core):
        blockers.append("source_bridge_id_mismatch")
    if observer["bridge_id"] != source["bridge_id"]:
        blockers.append("cross_root_join")
    if source["file_set_sha256"] != stable_hash(source["files"]):
        blockers.append("source_file_set_digest_mismatch")
    family = source.get("git_repo_family")
    expected_remote = CANONICAL_REPOS.get(family)
    if source.get("canonical_repo") != expected_remote:
        blockers.append("pinned_canonical_repo_mismatch")
    repo_value = observer.get("repo_path")
    repo = Path(repo_value) if isinstance(repo_value, str) else Path("/")
    source_repo_value = source.get("source_repo_path")
    source_repo = Path(source_repo_value) if isinstance(source_repo_value, str) else Path("/")
    if (not isinstance(source_repo_value, str) or not source_repo.is_absolute()
            or not source_repo.resolve().is_relative_to(repo.resolve())):
        blockers.append("source_repo_not_within_observer_repo")
    commit, tree = source.get("commit_oid"), observer.get("tree_oid")
    files = source.get("files")
    if not isinstance(repo_value, str) or not repo.is_absolute():
        blockers.append("repo_path_invalid")
    if OID_RE.fullmatch(str(commit or "")) is None:
        blockers.append("commit_oid_invalid")
    if OID_RE.fullmatch(str(tree or "")) is None:
        blockers.append("tree_oid_invalid")
    if not isinstance(files, list) or not files:
        blockers.append("source_files_missing")
        files = []
    if blockers:
        return sorted(set(blockers))
    if _git_text(runner, repo, ["remote", "get-url", "origin"]) != expected_remote:
        blockers.append("remote_origin_consistency_mismatch")
    if _git_text(runner, repo, ["config", "--local", "--get", "extensions.partialClone"]):
        blockers.append("partial_clone_forbidden")
    code, promisor = _git(runner, repo, ["config", "--local", "--get-regexp", r"^remote\..*\.promisor$"])
    if code == 0 and promisor.strip():
        blockers.append("promisor_remote_forbidden")
    alternate_path = _git_text(runner, repo, ["rev-parse", "--git-path", "objects/info/alternates"])
    if alternate_path and Path(alternate_path).is_file() and Path(alternate_path).read_bytes().strip():
        blockers.append("object_alternates_forbidden")
    code, commit_bytes = _git(runner, repo, ["cat-file", "commit", commit])
    if code != 0:
        blockers.append("commit_object_missing")
    else:
        calculated = hashlib.sha1(
            f"commit {len(commit_bytes)}\0".encode() + commit_bytes
        ).hexdigest()
        if calculated != commit:
            blockers.append("commit_object_oid_mismatch")
        first = commit_bytes.split(b"\n", 1)[0]
        if first != f"tree {tree}".encode():
            blockers.append("commit_tree_binding_mismatch")
    code, tree_bytes = _git(runner, repo, ["cat-file", "tree", tree])
    if code != 0:
        blockers.append("tree_object_missing")
    elif hashlib.sha1(f"tree {len(tree_bytes)}\0".encode() + tree_bytes).hexdigest() != tree:
        blockers.append("tree_object_oid_mismatch")
    seen: set[str] = set()
    for item in files:
        if not isinstance(item, Mapping) or set(item) != FILE_FIELDS:
            blockers.append("file_schema_not_exact")
            continue
        path, blob, content_sha = item.get("path"), item.get("blob_oid"), item.get("content_sha256")
        pure = PurePosixPath(path) if isinstance(path, str) else PurePosixPath("..")
        if (
            not isinstance(path, str) or not path or pure.is_absolute()
            or ".." in pure.parts or path in seen
        ):
            blockers.append("duplicate_or_invalid_path")
            continue
        seen.add(path)
        if OID_RE.fullmatch(str(blob or "")) is None or DIGEST_RE.fullmatch(str(content_sha or "")) is None:
            blockers.append("invalid_blob_or_content_digest")
            continue
        code, listing = _git(runner, repo, ["ls-tree", "-z", commit, "--", path])
        expected = f"100644 blob {blob}\t{path}\0".encode()
        if code != 0 or listing != expected:
            blockers.append("path_blob_binding_mismatch")
            continue
        code, content = _git(runner, repo, ["cat-file", "blob", blob])
        if code != 0:
            blockers.append("blob_object_missing")
            continue
        if hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest() != blob:
            blockers.append("blob_byte_oid_mismatch")
        if hashlib.sha256(content).hexdigest() != content_sha:
            blockers.append("blob_byte_sha256_mismatch")
    return sorted(set(blockers))


def build_census(
    commitment: Mapping[str, Any], source_projection: Mapping[str, Any],
    observer_matrix: Mapping[str, Any], *,
    source_file_sha256: Mapping[str, str | None] | None,
    evidence_file_sha256: Mapping[str, str | None] | None,
    runner: Callable[[Path, Sequence[str]], tuple[int, bytes, bytes]] = _run_git,
) -> dict[str, Any]:
    blockers: list[str] = []
    if not _pins_valid(source_file_sha256, PINNED_SOURCE_FILE_SHA256):
        blockers.append("source_pins_missing_extra_or_mismatched")
    if not _pins_valid(evidence_file_sha256, PINNED_EVIDENCE_FILE_SHA256):
        blockers.append("evidence_pins_missing_extra_or_mismatched")
    if json_document_sha256(source_projection) != PINNED_SOURCE_FILE_SHA256["source_projection"]:
        blockers.append("source_projection_content_digest_mismatch")
    if json_document_sha256(commitment) != PINNED_EVIDENCE_FILE_SHA256["commitment_projection"]:
        blockers.append("commitment_projection_content_digest_mismatch")
    if json_document_sha256(observer_matrix) != PINNED_EVIDENCE_FILE_SHA256["observer_matrix"]:
        blockers.append("observer_matrix_content_digest_mismatch")
    if leakage_reasons([commitment, source_projection, observer_matrix]):
        blockers.append("forbidden_projection_leakage")
    if set(commitment) != {
        "record_type", "protected_root_count", "protected_root_hashes",
        "protected_root_hash_set_sha256",
    } or commitment.get("record_type") != "stage12572_stage12105_commitment_projection_v2":
        blockers.append("commitment_projection_schema_not_exact")
    roots = commitment.get("protected_root_hashes")
    roots = roots if isinstance(roots, list) else []
    if (
        len(roots) != 25 or len(set(roots)) != 25
        or any(DIGEST_RE.fullmatch(str(root)) is None for root in roots)
        or roots != sorted(roots)
        or commitment.get("protected_root_count") != 25
        or commitment.get("protected_root_hash_set_sha256") != stable_hash(roots)
        or stable_hash(roots) != CANONICAL_PROTECTED_ROOT_HASH_SET_SHA256
    ):
        blockers.append("commitment_root_set_invalid")
    if set(source_projection) != {
        "record_type", "generator", "pinned_original_source_sha256", "rows"
    } or source_projection.get("record_type") != "stage12572_source_native_projection_v2":
        blockers.append("source_projection_schema_not_exact")
    if source_projection.get("generator") != PINNED_GENERATOR:
        blockers.append("guarded_generator_identity_mismatch")
    if source_projection.get("pinned_original_source_sha256") != PINNED_ORIGINAL_SOURCE_SHA256:
        blockers.append("original_source_pin_set_mismatch")
    sources = source_projection.get("rows")
    sources = sources if isinstance(sources, list) else []
    observers = observer_matrix.get("rows")
    observers = observers if isinstance(observers, list) else []
    if set(observer_matrix) != {"record_type", "rows"} or observer_matrix.get("record_type") != "stage12572_observer_matrix_v4":
        blockers.append("observer_matrix_schema_not_exact")
    source_by_root: dict[str, list[Mapping[str, Any]]] = {}
    source_by_bridge: dict[str, list[Mapping[str, Any]]] = {}
    observer_by_bridge: dict[str, list[Mapping[str, Any]]] = {}
    for row in sources:
        if isinstance(row, Mapping):
            source_by_root.setdefault(str(row.get("protected_root_hash") or ""), []).append(row)
            source_by_bridge.setdefault(str(row.get("bridge_id") or ""), []).append(row)
        else:
            blockers.append("unexpected_source_row")
    for row in observers:
        if isinstance(row, Mapping):
            observer_by_bridge.setdefault(str(row.get("bridge_id") or ""), []).append(row)
        else:
            blockers.append("unexpected_observer_row")
    bridge_roots = sorted(source_by_root)
    if (
        len(sources) != 17 or len(source_by_root) != 17 or len(source_by_bridge) != 17
        or len(observers) != 17 or len(observer_by_bridge) != 17
        or set(source_by_bridge) != set(observer_by_bridge)
        or not set(source_by_root).issubset(set(roots))
        or stable_hash(bridge_roots) != IMMUTABLE_SOURCE_BRIDGE_ROOT_SET_SHA256
        or any(len(rows_for_root) != 1 for rows_for_root in source_by_root.values())
        or any(len(rows_for_root) != 1 for rows_for_root in source_by_bridge.values())
        or any(len(rows_for_root) != 1 for rows_for_root in observer_by_bridge.values())
    ):
        blockers.append("bridge_root_set_missing_extra_or_duplicate")
    invalid = 0
    for bridge_id in sorted(set(source_by_bridge) & set(observer_by_bridge)):
        if len(source_by_bridge[bridge_id]) != 1 or len(observer_by_bridge[bridge_id]) != 1:
            invalid += 1
            continue
        errors = verify_git_observation(
            observer_by_bridge[bridge_id][0], source_by_bridge[bridge_id][0], runner=runner
        )
        if errors:
            invalid += 1
    if invalid:
        blockers.append("invalid_source_join_or_git_observation")
    integrity = not blockers
    kind_counts = {
        "full_revision_prior_root": 0,
        "stage11576_deterministic_constructor": 0,
        "stage11811_fixed_git_snapshot": 0,
    }
    rows_out = []
    for root in roots:
        source = source_by_root.get(root, [None])[0] if integrity and len(source_by_root.get(root, [])) == 1 else None
        kind = SOURCE_SCHEMAS.get(source.get("record_schema")) if source else None
        if kind:
            kind_counts[kind] += 1
        body = {
            "opaque_stage12105_root_identity_sha256": root,
            "committed_root_identity_verified": True,
            "immutable_source_bridge": kind is not None,
            "proof_status": ("immutable_source_bridge_verified_unauthed" if kind
                             else "preimage_commitment_historical_binding_missing"),
            "bridge_kind": kind,
            "source_join_sha256": stable_hash(source) if source else None,
            **ZERO,
        }
        rows_out.append({**body, "census_row_sha256": stable_hash(body)})
    bridge_count = sum(row["immutable_source_bridge"] for row in rows_out)
    authorized_count = sum(row["authorization_allowed"] for row in rows_out)
    partition_valid = (
        len(rows_out) == 25 and bridge_count == 17
        and len(rows_out) - bridge_count == 8 and authorized_count == 0
        and kind_counts == {
            "full_revision_prior_root": 5,
            "stage11576_deterministic_constructor": 11,
            "stage11811_fixed_git_snapshot": 1,
        }
    )
    if not partition_valid:
        blockers.append("expected_partition_not_reproduced")
    body = {
        "stage": STAGE,
        "record_type": "stage12572_source_native_committed_root_identity_census_v5",
        "decision": "verified" if not blockers else "blocked",
        "canonical_protected_root_count": len(roots),
        "canonical_protected_root_hash_set_sha256": stable_hash(roots),
        "immutable_source_bridge_root_set_sha256": stable_hash(bridge_roots),
        "committed_root_identity_verified_count": len(rows_out),
        "immutable_source_bridge_count": bridge_count,
        "immutable_source_bridge_kind_counts": kind_counts,
        "historical_binding_missing_count": len(rows_out) - bridge_count,
        "independently_authorized_count": authorized_count,
        "invalid_observer_record_count": invalid,
        "census_rows": rows_out,
        "census_row_set_sha256": stable_hash(sorted(row["census_row_sha256"] for row in rows_out)),
        "source_file_sha256": dict(sorted((source_file_sha256 or {}).items())),
        "evidence_file_sha256": dict(sorted((evidence_file_sha256 or {}).items())),
        "protected_content_emitted": False,
        "runtime_plaintext_preimages_read": False,
        "outcomes_gold_target_or_verifier_read": False,
        "blocking_reasons": sorted(set(blockers)),
        "non_authorizing_conditions": ["independent_source_authority_absent"],
        **ZERO,
    }
    return {**body, "summary_record_sha256": stable_hash(body)}


def build() -> dict[str, Any]:
    return build_census(
        read_json(SOURCES["commitment_projection"]),
        read_json(SOURCES["source_projection"]),
        read_json(SOURCES["observer_matrix"]),
        source_file_sha256={"source_projection": file_sha256(SOURCES["source_projection"])},
        evidence_file_sha256={
            "commitment_projection": file_sha256(SOURCES["commitment_projection"]),
            "observer_matrix": file_sha256(SOURCES["observer_matrix"]),
        },
    )


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main() -> int:
    result = build()
    write_json(OUT / "source_native_preimage_reconstruction_census.json", result)
    write_json(OUT / "summary.json", result)
    write_json(SUMMARY, result)
    print(json.dumps({key: result[key] for key in (
        "committed_root_identity_verified_count", "immutable_source_bridge_count",
        "historical_binding_missing_count", "independently_authorized_count",
        "invalid_observer_record_count",
    )}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
