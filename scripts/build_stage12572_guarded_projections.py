#!/usr/bin/env python3
"""Private guarded projection of plaintext lineage into public commitments."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "runs/local/artifacts"
OUT = BASE / "stage12572_source_native_protected_root_preimage_reconstruction_census"
RICH_STAGE12105 = BASE / "stage12105_sealed_transition_candidate_atlas/sealed_transition_candidate_rows.jsonl"
OUTPUT_SUFFIX = os.environ.get("STAGE12572_OUTPUT_SUFFIX", "")
OUTPUT_NAMES = {
    "commitment": f"stage12105_commitment_projection{OUTPUT_SUFFIX}.json",
    "source": f"source_native_projection{OUTPUT_SUFFIX}.json",
    "observer": f"observer_matrix{OUTPUT_SUFFIX}.json",
}
SOURCE_PATHS = {
    "stage11347": BASE / "stage11347_web_static_verifier_maintainer_rows/web_static_verifier_root_bundles.jsonl",
    "stage11353": BASE / "stage11353_web_verifier_execution_evidence/web_verifier_execution_evidence.json",
    "stage11364": BASE / "stage11364_web_sourcebot_executed_support_rows/web_sourcebot_executed_support_bundles.jsonl",
    "stage11537": BASE / "stage11537_openclaw_extra_web_gold_support_rows/openclaw_extra_web_gold_packets.jsonl",
    "stage11545": BASE / "stage11545_openclaw_more_web_gold_train_rows/openclaw_more_web_gold_train_packets.jsonl",
    "stage11576": BASE / "stage11576_web_fresh_source_candidate_atlas/web_fresh_source_candidate_roots.jsonl",
    "stage11811": BASE / "stage11811_llm_memory_python_support_rows/llm_memory_python_support_rows.jsonl",
}
EXPECTED_INPUT_SHA256 = {
    "stage12105": "dbaf3800b987bb8607c8cd2ddb0ddcbf2011e6be9b2f4c0a41847013b86dddd2",
    "stage11347": "b5e1d4fe5edfbd45d31989f97f5d5045e660f1dca17634ff3b9faa9b56932e73",
    "stage11353": "6d4ed3484b4ff914d914810681e8cef2847b9f2178d98002fccc105f0e354b8a",
    "stage11364": "0e8ed9288527a405475c0dcd8b70886771596fc62db5b0d39e012b89f55f259a",
    "stage11537": "dccc373df0617911076212d8b7c0bb567b0759a431f60a9c147f8434b184ac97",
    "stage11545": "6288ab5e83b8dbba6c43827246055b5aa5896685384e23c712377fdba490ae54",
    "stage11576": "b42c576a0cd952c34e94a8907b8b404954307aade8f367bacd4fe991d53e77d9",
    "stage11811": "b1296c7d299f5d46278a988ebd9ca526d1786c23c686a1c2782deb919df5065c",
}
CANONICAL_REPOS = {
    "modelcontextprotocol_typescript_sdk": "https://github.com/modelcontextprotocol/typescript-sdk.git",
    "sourcebot": "https://github.com/sourcebot-dev/sourcebot.git",
    "openclaw_clawhub": "https://github.com/openclaw/clawhub.git",
    "openhands_openhands": "https://github.com/OpenHands/OpenHands.git",
    "llama_stack": "https://github.com/llamastack/llama-stack.git",
    "llm_memory_modules_at_scale": "https://github.com/peytontolbert/llm_memory_modules_at_scale.git",
}
PINNED_COMMITS = {
    "openhands_openhands": "e3d9abfd014ffd4283d03071fdb88c1c8edc77f6",
    "llama_stack": "8f4c431370fdd566dd7a04910b737ced7e6d5ffe",
    "llm_memory_modules_at_scale": "ad6f5ea441bb5c948cabcfe8ec9799b5f5b27b1c",
}
GENERATOR_IDENTITY = "stage12572_guarded_commitment_projection_generator_v2"


def stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode()).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def git(repo: Path, *args: str, binary: bool = False) -> bytes | str:
    env = os.environ.copy()
    env["GIT_NO_LAZY_FETCH"] = "1"
    env["GIT_ALTERNATE_OBJECT_DIRECTORIES"] = ""
    result = subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, env=env
    ).stdout
    return result if binary else result.decode().strip()


def observe(
    source_repo: Path, canonical_repo: str, commit: str,
    source_paths: list[str], declared_sha256: dict[str, str],
) -> tuple[str, str, list[dict[str, str]]]:
    top = Path(str(git(source_repo, "rev-parse", "--show-toplevel")))
    if git(top, "remote", "get-url", "origin") != canonical_repo:
        raise ValueError("canonical remote mismatch")
    commit = str(git(top, "rev-parse", f"{commit}^{{commit}}"))
    tree = str(git(top, "rev-parse", f"{commit}^{{tree}}"))
    if len(source_paths) != len(set(source_paths)):
        raise ValueError("duplicate source paths")
    files: list[dict[str, str]] = []
    for source_path in source_paths:
        relative_from_subdir = (source_repo / source_path).resolve().relative_to(
            top.resolve()
        ).as_posix()
        candidates = list(dict.fromkeys([relative_from_subdir, source_path]))
        matches: list[tuple[str, str]] = []
        for candidate in candidates:
            listing = git(top, "ls-tree", "-z", commit, "--", candidate, binary=True)
            if not listing:
                continue
            prefix, listed_path = listing[:-1].split(b"\t", 1)
            mode, kind, blob = prefix.decode().split()
            if kind == "blob" and listed_path.decode() == candidate:
                matches.append((candidate, blob))
        if len(matches) != 1:
            raise ValueError(f"missing or ambiguous Git path: {source_path}")
        path, blob = matches[0]
        content = git(top, "cat-file", "blob", blob, binary=True)
        content_sha = hashlib.sha256(content).hexdigest()
        if source_path in declared_sha256 and declared_sha256[source_path] != content_sha:
            raise ValueError(f"declared source hash mismatch: {source_path}")
        calculated_blob = hashlib.sha1(
            f"blob {len(content)}\0".encode() + content
        ).hexdigest()
        if calculated_blob != blob:
            raise ValueError(f"blob byte mismatch: {source_path}")
        files.append({
            "path": path, "blob_oid": blob, "content_sha256": content_sha
        })
    return str(top), tree, sorted(files, key=lambda item: item["path"])


if file_sha256(RICH_STAGE12105) != EXPECTED_INPUT_SHA256["stage12105"]:
    raise SystemExit("pinned Stage12105 input changed")
for name, path in SOURCE_PATHS.items():
    if file_sha256(path) != EXPECTED_INPUT_SHA256[name]:
        raise SystemExit(f"pinned source changed: {name}")

root_keys = sorted({
    row["stage12105_root_key"] for row in jsonl(RICH_STAGE12105)
})
protected_hashes = sorted(stable_hash(["stage12105", key]) for key in root_keys)
commitment = {
    "record_type": "stage12572_stage12105_commitment_projection_v2",
    "protected_root_count": len(protected_hashes),
    "protected_root_hashes": protected_hashes,
    "protected_root_hash_set_sha256": stable_hash(protected_hashes),
}
source_rows: list[dict[str, Any]] = []
observer_rows: list[dict[str, Any]] = []


def add(
    schema: str, artifact_ids: list[str], root_key: str, args: dict[str, Any],
    source_repo_path: str, git_family: str, commit: str,
    paths: list[str], declared: dict[str, str] | None = None,
) -> None:
    canonical = CANONICAL_REPOS[git_family]
    top, tree, files = observe(
        Path(source_repo_path), canonical, commit, paths, declared or {}
    )
    core = {
        "record_schema": schema,
        "source_artifact_ids": artifact_ids,
        "protected_root_hash": stable_hash(["stage12105", root_key]),
        "constructor_arguments_sha256": stable_hash(args),
        "source_repo_path": source_repo_path,
        "git_repo_family": git_family,
        "canonical_repo": canonical,
        "commit_oid": commit,
        "files": files,
        "file_set_sha256": stable_hash(files),
    }
    bridge_id = stable_hash(core)
    source_rows.append({"bridge_id": bridge_id, **core})
    observer_rows.append({
        "record_schema": "stage12572_git_object_observation_v2",
        "bridge_id": bridge_id, "repo_path": top, "tree_oid": tree,
    })


stage11347 = jsonl(SOURCE_PATHS["stage11347"])
mcp = next(row for row in stage11347 if row["root_id"] == "stage11347::mcp_stdio_transport_lifecycle")
stage11353 = json.loads(SOURCE_PATHS["stage11353"].read_text())
execution = stage11353["by_root"]["mcp_stdio_transport_lifecycle"]["attempt"]
mcp_args = {
    "stage11347": {
        "root_id": mcp["root_id"], "root_lineage_key": mcp["root_lineage_key"],
        "git_head": mcp["git_head"], "git_repo_family": mcp["git_repo_family"],
        "repo_family": mcp["repo_family"], "repo_path": mcp["repo_path"],
        "selected_source_path": mcp["selected_source_path"],
        "selected_test_path": mcp["selected_test_path"],
    },
    "stage11353": {
        "source_record_key": "mcp_stdio_transport_lifecycle",
        "command": execution["cmd"], "cwd": execution["cwd"],
    },
}
add(
    "stage11347_11353_git_revision_source_v1", ["stage11347", "stage11353"],
    mcp["root_lineage_key"] + "::executed_verifier_stage11353", mcp_args,
    mcp["repo_path"], mcp["git_repo_family"], mcp["git_head"],
    [mcp["selected_source_path"], mcp["selected_test_path"]],
)


def revision_args(row: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    sources = [
        path for path in (
            row.get("selected_source_path"), row.get("source_path"),
            row.get("secondary_source_path"),
        ) if path
    ]
    test_path = row.get("selected_test_path") or row.get("test_path")
    return ({
        "root_id": row["root_id"], "root_lineage_key": row.get("root_lineage_key"),
        "git_head": row["git_head"], "git_repo_family": row["git_repo_family"],
        "repo_family": row["repo_family"], "repo_path": row["repo_path"],
        "source_paths": sources, "test_path": test_path,
    }, [*sources, test_path])


protected_set = set(protected_hashes)
for row in jsonl(SOURCE_PATHS["stage11364"]):
    root_key = row.get("root_lineage_key")
    if stable_hash(["stage12105", root_key]) not in protected_set:
        continue
    args, paths = revision_args(row)
    add("stage11364_git_revision_source_v1", ["stage11364"], root_key, args,
        row["repo_path"], row["git_repo_family"], row["git_head"], paths)
for row in jsonl(SOURCE_PATHS["stage11537"]):
    root_key = f"{row['git_repo_family']}::{row['git_head']}::{row['root_id']}::stage11537"
    if stable_hash(["stage12105", root_key]) not in protected_set:
        continue
    args, paths = revision_args(row)
    add("stage11537_git_revision_source_v1", ["stage11537"], root_key, args,
        row["repo_path"], row["git_repo_family"], row["git_head"], paths)
for row in jsonl(SOURCE_PATHS["stage11545"]):
    if stable_hash(["stage12105", row["root_id"]]) not in protected_set:
        continue
    args, paths = revision_args(row)
    add("stage11545_git_revision_source_v1", ["stage11545"], row["root_id"], args,
        row["repo_path"], row["git_repo_family"], row["git_head"], paths)
for row in jsonl(SOURCE_PATHS["stage11576"]):
    if stable_hash(["stage12105", row["root_id"]]) not in protected_set:
        continue
    args = {
        "root_id": row["root_id"], "git_repo_family": row["git_repo_family"],
        "repo_family": row["repo_family"], "repo_path": row["repo_path"],
        "selected_verifier_path": row["selected_verifier_path_proposal"],
        "selected_verifier_sha256": row["selected_verifier_sha256"],
        "candidate_change_surface_paths": row["candidate_change_surface_paths"],
        "candidate_change_surface_sha256": row["candidate_change_surface_sha256"],
        "lane": row["lane"],
    }
    paths = [row["selected_verifier_path_proposal"], *row["candidate_change_surface_paths"]]
    declared = dict(row["candidate_change_surface_sha256"])
    declared[row["selected_verifier_path_proposal"]] = row["selected_verifier_sha256"]
    add("stage11576_source_v1", ["stage11576"], row["root_id"], args,
        row["repo_path"], row["git_repo_family"],
        PINNED_COMMITS[row["git_repo_family"]], paths, declared)
stage11811 = jsonl(SOURCE_PATHS["stage11811"])[0]
entries = [
    {"kind": item["kind"], "path": item["path"], "sha256": item["sha256"]}
    for item in stage11811["evidence_ledger"]
    if item["kind"] in {
        "implementation_source", "selected_test_anchor", "nearby_source_distractor"
    }
]
args = {
    "root_lineage_key": stage11811["root_lineage_key"],
    "source_snapshot_id": stage11811["source_snapshot_id"],
    "source_entries": entries,
}
add(
    "stage11811_fixed_snapshot_v1", ["stage11811"],
    stage11811["root_lineage_key"], args,
    "/data/parametergolf/helpful_repos/llm_memory_modules_at_scale",
    "llm_memory_modules_at_scale", PINNED_COMMITS["llm_memory_modules_at_scale"],
    [item["path"] for item in entries],
    {item["path"]: item["sha256"] for item in entries},
)
generator = {
    "identity": GENERATOR_IDENTITY,
    "file_sha256": file_sha256(Path(__file__)),
}
source_projection = {
    "record_type": "stage12572_source_native_projection_v2",
    "generator": generator,
    "pinned_original_source_sha256": {
        key: value for key, value in EXPECTED_INPUT_SHA256.items()
        if key != "stage12105"
    },
    "rows": sorted(source_rows, key=lambda row: row["protected_root_hash"]),
}
observer = {
    "record_type": "stage12572_observer_matrix_v4",
    "rows": sorted(observer_rows, key=lambda row: row["bridge_id"]),
}
values = {
    "commitment": commitment, "source": source_projection, "observer": observer
}
for key, value in values.items():
    path = OUT / OUTPUT_NAMES[key]
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    print(path.name, file_sha256(path))
