#!/usr/bin/env python3
"""Build source-proven maintenance-language and small-diff rows from Git history."""

from __future__ import annotations

import argparse
import collections
import ctypes
import difflib
import errno
import hashlib
import importlib.util
import json
import os
import re
import stat
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12689_source_backed_maintenance_history_corpus"
DEFAULT_SOURCE_ROOT = Path("/arxiv/repositories")
DEFAULT_OUT = ROOT / "runs/local/artifacts" / STAGE
DEFAULT_SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
MASK = "<MASKED_EXACT_GIT_SPAN>"
ARTIFACT_SCHEMA_VERSION = 1

MAX_REPOS = 601
MAX_COMMITS_PER_REPO = 96
MAX_ROWS = 500
DEFAULT_CAPACITY_EVIDENCE = {
    "accepted_repositories": 525,
    "largest_component_capacity": 6_430,
    "positive_capacity_components": 53,
    "total_buildable_rows": 7_202,
}
MAX_ROWS_PER_REPO = 100
MAX_BLOB_BYTES = 128_000
MAX_TARGET_CHARS = 2_048
MAX_CHANGED_LINES = 48
CONTEXT_LINES = 12

AUTHORITY = {
    "implementation_ready": False,
    "level_3_materialized": False,
    "model_execution_authorized": False,
    "replay_trustworthy": False,
    "sealed_eval_admitted": False,
    "strict_eval_admitted": False,
    "training_admitted": False,
    "training_allowed": False,
    "training_run_allowed": False,
}
EXCLUDED_PARTS = frozenset({
    ".git", ".hg", ".svn", "build", "dist", "generated", "node_modules",
    "site-packages", "third_party", "vendor", "vendors",
})
EXCLUDED_SUFFIXES = (
    ".lock", ".min.js", ".min.css", ".map", ".pb.go", "_pb2.py",
    "_pb2_grpc.py", ".generated.py",
)
PLACEHOLDER_RE = re.compile(r"\b(?:TODO|FIXME|TBD|PLACEHOLDER)\b", re.IGNORECASE)
OID_RE = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
EMAIL_RE = re.compile(r"(?<![\w.+-])[\w.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![\w.-])")
ADMIN_TRAILER_RE = re.compile(
    r"^(?:signed-off-by|co-authored-by|reviewed-by|acked-by|change-id)\s*:",
    re.IGNORECASE,
)
BOT_RE = re.compile(
    r"(?:\bdependabot\b|\brenovate(?:\[bot\])?\b|\bgithub-actions\[bot\]\b|\b[^\s]+\[bot\]\b|\bbot\b)",
    re.IGNORECASE,
)
SECRET_ASSIGNMENT_RE = re.compile(
    r"\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|password|passwd|private[_-]?key|secret)\s*[:=]\s*\S+",
    re.IGNORECASE,
)
SENSITIVE_MARKER_RE = re.compile(
    r"\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|bearer|password|passwd|private[_-]?key|secret|token)\b",
    re.IGNORECASE,
)
URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
BEARER_RE = re.compile(r"\bbearer\s+[A-Za-z0-9._~+/-]+=*", re.IGNORECASE)
AUTOMATION_RE = re.compile(
    r"(?:\bautomation\b|\bautomated\b|\bdependabot\b|\brenovate\b|\brelease-please\b|"
    r"\bgithub-actions\b|\bsnyk\b|\bcopilot\b|\b[^\s]+\[bot\]\b|\bbot\b)",
    re.IGNORECASE,
)
MAINTENANCE_ACTION_VERBS = frozenset({
    "add", "address", "allow", "avoid", "correct", "enforce", "extend", "fix",
    "guard", "handle", "implement", "improve", "prevent", "preserve", "refactor",
    "reject", "remove", "repair", "resolve", "restore", "support", "tighten", "validate",
})
GENERIC_IDENTIFIER_TOKENS = frozenset({
    "behavior", "change", "changes", "code", "file", "files", "issue", "maintenance",
    "misc", "module", "project", "repository", "test", "tests", "update", "version",
})


def _load_stage12687():
    path = ROOT / "scripts/build_stage12687_source_backed_python_foundational_corpus.py"
    spec = importlib.util.spec_from_file_location("stage12687_history_dependency", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("stage12687_dependency_unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


S87 = _load_stage12687()
stable = S87.stable
sha256_bytes = S87.sha256_bytes
git = S87.git
sanitize_origin = S87.sanitize_origin
contains_high_confidence_secret = S87.contains_high_confidence_secret
generated_content = S87.generated_content
secure_atomic_write = S87.secure_atomic_write
open_directory_nofollow = S87.open_directory_nofollow
file_sha256 = S87.file_sha256
UnionFind = S87.UnionFind


class Stage12689Error(RuntimeError):
    pass


@dataclass(frozen=True)
class Change:
    commit_oid: str
    parent_oid: str
    commit_tree_oid: str
    parent_tree_oid: str
    path: str
    parent_blob_oid: str
    child_blob_oid: str
    parent_data: bytes
    child_data: bytes
    message: str
    old_start: int
    old_end: int
    new_start: int
    new_end: int
    patch_fingerprint: str


@dataclass
class Snapshot:
    local_path: Path
    repo_key: str
    origin_url: str
    revision: str
    changes: list[Change]
    lineage_keys: tuple[str, ...]
    component_objects: tuple[tuple[str, str], ...]
    component_key: str = ""
    split: str = ""


def verify_object_oid(oid: str, object_type: str, data: bytes) -> bool:
    framed = f"{object_type} {len(data)}\0".encode("ascii") + data
    if len(oid) == 40:
        return hashlib.sha1(framed).hexdigest() == oid
    if len(oid) == 64:
        return hashlib.sha256(framed).hexdigest() == oid
    return False


def read_verified_object(repo: Path, oid: str, object_type: str) -> bytes:
    if not OID_RE.fullmatch(oid):
        raise Stage12689Error("invalid_object_oid")
    try:
        actual_type = git(repo, "cat-file", "-t", oid).decode("ascii").strip()
        data = git(repo, "cat-file", object_type, oid, timeout=120)
    except (S87.Stage12687Error, UnicodeDecodeError) as exc:
        raise Stage12689Error(f"missing_or_unreadable_{object_type}") from exc
    if actual_type != object_type or not verify_object_oid(oid, object_type, data):
        raise Stage12689Error(f"{object_type}_identity_mismatch")
    return data


def parse_commit(data: bytes, *, require_single_parent: bool = True) -> tuple[str, str, str]:
    try:
        headers, message_bytes = data.split(b"\n\n", 1)
        header_lines = headers.decode("utf-8").splitlines()
        message = message_bytes.decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise Stage12689Error("malformed_or_non_utf8_commit") from exc
    trees = [line[5:] for line in header_lines if line.startswith("tree ")]
    parents = [line[7:] for line in header_lines if line.startswith("parent ")]
    if len(trees) != 1 or (require_single_parent and len(parents) != 1):
        raise Stage12689Error("root_or_merge_commit")
    if not require_single_parent and len(parents) > 1:
        raise Stage12689Error("merge_parent_commit")
    if not OID_RE.fullmatch(trees[0]) or any(not OID_RE.fullmatch(parent) for parent in parents):
        raise Stage12689Error("invalid_commit_reference")
    return trees[0], parents[0] if parents else "", message


def path_allowed(path: str) -> bool:
    if (
        not path or path.startswith("/") or "\\" in path or path.endswith("/")
        or any(unicodedata.category(character).startswith("C") for character in path)
    ):
        return False
    parts = path.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return False
    lowered = tuple(part.lower() for part in parts)
    if EXCLUDED_PARTS.intersection(lowered):
        return False
    lower = path.lower()
    return not lower.endswith(EXCLUDED_SUFFIXES) and not any(
        token in lower for token in ("/fixtures/", "/snapshots/", "/migrations/")
    )


def clean_maintenance_subject(message: str, forbidden_input: str) -> tuple[int, int] | None:
    lines = message.splitlines()
    if (
        contains_high_confidence_secret(message.encode("utf-8"))
        or SECRET_ASSIGNMENT_RE.search(message)
        or SENSITIVE_MARKER_RE.search(message)
        or URL_RE.search(message)
        or BEARER_RE.search(message)
        or EMAIL_RE.search(message)
        or BOT_RE.search(message)
        or AUTOMATION_RE.search(message)
        or any(ADMIN_TRAILER_RE.match(line) for line in lines)
    ):
        return None
    subject = lines[0] if lines else ""
    if not (20 <= len(subject) <= 512) or not subject.strip() or PLACEHOLDER_RE.search(subject):
        return None
    lowered = " ".join(subject.casefold().split())
    if re.match(r"^(?:merge|revert)\b", lowered):
        return None
    if re.match(r"^(?:wip|chore)(?:\b|[(:])", lowered):
        return None
    if re.match(r"^(?:bump|upgrade)\b", lowered) or re.match(r"^(?:version bump|release v?\d)", lowered):
        return None
    if re.match(r"^update\s+(?:dependencies|dependency|deps|[\w@./-]+)\s+(?:to|from)\s+v?\d", lowered):
        return None
    if re.fullmatch(
        r"(?:update files?|misc(?:ellaneous)? changes?|bump version|wip|chore(?::.*)?|"
        r"(?:minor |code )?(?:cleanup|clean up)(?: changes?)?)",
        lowered.rstrip("."),
    ):
        return None
    words = re.findall(r"[A-Za-z]+", subject)
    stop_words = {"a", "an", "and", "for", "in", "of", "on", "the", "to", "with"}
    meaningful = [word for word in words if len(word) >= 2 and word.casefold() not in stop_words]
    if len(meaningful) < 4:
        return None
    subject_tokens = {
        token.casefold() for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", subject)
    }
    if not subject_tokens.intersection(MAINTENANCE_ACTION_VERBS):
        return None
    evidence_tokens = {
        token.casefold() for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", forbidden_input)
    }
    identifier_tokens = {
        token for token in subject_tokens.intersection(evidence_tokens)
        if len(token) >= 4
        and token not in stop_words
        and token not in GENERIC_IDENTIFIER_TOKENS
        and token not in MAINTENANCE_ACTION_VERBS
    }
    if not identifier_tokens:
        return None
    if normalized(subject) in normalized(forbidden_input):
        return None
    return 0, len(subject)


def parse_ls_tree_object_identities(data: bytes) -> tuple[tuple[str, str], ...]:
    identities: set[tuple[str, str]] = set()
    for record in data.split(b"\0"):
        if not record:
            continue
        try:
            raw_header, _raw_path = record.split(b"\t", 1)
            raw_mode, raw_type, raw_oid = raw_header.split()
            int(raw_mode, 8)
            object_type = raw_type.decode("ascii")
            oid = raw_oid.decode("ascii")
        except (ValueError, UnicodeDecodeError) as exc:
            raise Stage12689Error("malformed_head_ls_tree_record") from exc
        if not object_type or not OID_RE.fullmatch(oid):
            raise Stage12689Error("invalid_head_ls_tree_identity")
        identities.add((object_type, oid))
    if not identities:
        raise Stage12689Error("empty_head_ls_tree_identity_set")
    return tuple(sorted(identities))


def safe_text_blob(data: bytes) -> str | None:
    if not data or len(data) > MAX_BLOB_BYTES or b"\x00" in data:
        return None
    if data.startswith(b"version https://git-lfs.github.com/spec/v1"):
        return None
    if contains_high_confidence_secret(data) or generated_content(data):
        return None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if MASK in text:
        return None
    return text


def parse_single_path_change(data: bytes) -> str:
    fields = data.split(b"\0")
    if fields and fields[-1] == b"":
        fields.pop()
    if len(fields) != 2 or fields[0] not in {b"M"}:
        raise Stage12689Error("not_one_modified_file")
    try:
        path = fields[1].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Stage12689Error("non_utf8_change_path") from exc
    if not path_allowed(path):
        raise Stage12689Error("excluded_change_path")
    return path


def resolve_blob(repo: Path, revision: str, path: str) -> tuple[str, bytes]:
    try:
        oid = git(repo, "rev-parse", "--verify", f"{revision}:{path}").decode("ascii").strip()
    except (S87.Stage12687Error, UnicodeDecodeError) as exc:
        raise Stage12689Error("missing_changed_blob") from exc
    return oid, read_verified_object(repo, oid, "blob")


def single_hunk(parent_text: str, child_text: str) -> tuple[int, int, int, int] | None:
    parent_lines = parent_text.splitlines(keepends=True)
    child_lines = child_text.splitlines(keepends=True)
    changes = [
        opcode for opcode in difflib.SequenceMatcher(None, parent_lines, child_lines, autojunk=False).get_opcodes()
        if opcode[0] != "equal"
    ]
    if len(changes) != 1:
        return None
    tag, old_start, old_end, new_start, new_end = changes[0]
    if tag not in {"replace", "insert"} or new_start == new_end:
        return None
    changed_lines = (old_end - old_start) + (new_end - new_start)
    target = "".join(child_lines[new_start:new_end])
    if changed_lines > MAX_CHANGED_LINES or not target.strip() or len(target) > MAX_TARGET_CHARS:
        return None
    reconstructed = parent_lines[:old_start] + child_lines[new_start:new_end] + parent_lines[old_end:]
    if reconstructed != child_lines:
        raise Stage12689Error("diff_reconstruction_failure")
    return old_start, old_end, new_start, new_end


def normalized(value: str) -> str:
    return "".join(value.split()).casefold()


def patch_fingerprint(parent_text: str, child_text: str, hunk: tuple[int, int, int, int]) -> str:
    old_start, old_end, new_start, new_end = hunk
    parent_lines = parent_text.splitlines(keepends=True)
    child_lines = child_text.splitlines(keepends=True)
    return stable([
        "localized_patch_v1",
        normalized("".join(parent_lines[old_start:old_end])),
        normalized("".join(child_lines[new_start:new_end])),
    ])


def read_change(repo: Path, commit_oid: str) -> Change:
    commit_data = read_verified_object(repo, commit_oid, "commit")
    commit_tree_oid, parent_oid, message = parse_commit(commit_data)
    parent_data = read_verified_object(repo, parent_oid, "commit")
    parent_tree_oid, _grandparent_oid, _parent_message = parse_commit(
        parent_data, require_single_parent=False,
    )
    read_verified_object(repo, commit_tree_oid, "tree")
    read_verified_object(repo, parent_tree_oid, "tree")
    try:
        raw_change = git(
            repo, "diff-tree", "--no-commit-id", "--name-status", "--no-renames", "-r", "-z",
            parent_oid, commit_oid,
        )
    except S87.Stage12687Error as exc:
        raise Stage12689Error("diff_tree_failed") from exc
    path = parse_single_path_change(raw_change)
    parent_blob_oid, parent_blob = resolve_blob(repo, parent_oid, path)
    child_blob_oid, child_blob = resolve_blob(repo, commit_oid, path)
    parent_text, child_text = safe_text_blob(parent_blob), safe_text_blob(child_blob)
    if parent_text is None or child_text is None:
        raise Stage12689Error("unsafe_or_nontext_blob")
    hunk = single_hunk(parent_text, child_text)
    if hunk is None:
        raise Stage12689Error("not_small_single_textual_hunk")
    return Change(
        commit_oid=commit_oid, parent_oid=parent_oid,
        commit_tree_oid=commit_tree_oid, parent_tree_oid=parent_tree_oid,
        path=path, parent_blob_oid=parent_blob_oid, child_blob_oid=child_blob_oid,
        parent_data=parent_blob, child_data=child_blob, message=message,
        old_start=hunk[0], old_end=hunk[1], new_start=hunk[2], new_end=hunk[3],
        patch_fingerprint=patch_fingerprint(parent_text, child_text, hunk),
    )


def discover_repositories(source_root: Path, max_repos: int) -> tuple[list[Snapshot], collections.Counter[str]]:
    snapshots: list[Snapshot] = []
    counters: collections.Counter[str] = collections.Counter()
    for repo in sorted((item for item in source_root.iterdir() if item.is_dir()), key=lambda item: item.name):
        if len(snapshots) >= max_repos:
            break
        counters["repository_directories_seen"] += 1
        if not (repo / ".git").exists():
            counters["without_git"] += 1
            continue
        try:
            if git(repo, "rev-parse", "--is-shallow-repository").decode("ascii").strip() != "false":
                counters["shallow_repository"] += 1
                continue
            revision = git(repo, "rev-parse", "--verify", "HEAD^{commit}").decode("ascii").strip().lower()
            origin = sanitize_origin(git(repo, "config", "--get", "remote.origin.url").decode("utf-8"))
            commit_oids = git(
                repo, "rev-list", "--topo-order", f"--max-count={MAX_COMMITS_PER_REPO}", revision,
            ).decode("ascii").splitlines()
            roots = git(repo, "rev-list", "--max-parents=0", revision).decode("ascii").splitlines()
            remotes = git(repo, "remote", "-v").decode("utf-8").splitlines()
            head_commit_data = read_verified_object(repo, revision, "commit")
            head_tree_oid = next(
                line[5:].decode("ascii")
                for line in head_commit_data.splitlines()
                if line.startswith(b"tree ")
            )
            read_verified_object(repo, head_tree_oid, "tree")
            head_objects = parse_ls_tree_object_identities(
                git(repo, "ls-tree", "-r", "-t", "-z", revision)
            )
        except (S87.Stage12687Error, UnicodeDecodeError):
            counters["git_metadata_failure"] += 1
            continue
        except (Stage12689Error, StopIteration):
            counters["head_identity_failure"] += 1
            continue
        if not origin or not OID_RE.fullmatch(revision):
            counters["unpinned_or_origin_missing"] += 1
            continue
        changes: list[Change] = []
        ancestry: set[str] = set()
        for commit_oid in commit_oids:
            if not OID_RE.fullmatch(commit_oid):
                counters["invalid_history_oid"] += 1
                continue
            ancestry.add(commit_oid)
            try:
                changes.append(read_change(repo, commit_oid))
            except Stage12689Error as exc:
                counters[str(exc)] += 1
        if not changes:
            counters["without_eligible_history"] += 1
            continue
        repo_key = stable([origin, revision])
        lineage = {
            *(f"root:{oid}" for oid in roots if OID_RE.fullmatch(oid)),
            *(f"commit:{oid}" for oid in ancestry),
            *(
                f"remote:{url}" for line in remotes
                for fields in [line.split()]
                for url in [sanitize_origin(fields[1] if len(fields) >= 2 else "")]
                if url
            ),
        }
        component_objects = head_objects
        snapshots.append(Snapshot(
            local_path=repo, repo_key=repo_key, origin_url=origin, revision=revision,
            changes=changes, lineage_keys=tuple(sorted(lineage)), component_objects=component_objects,
        ))
        counters["repositories_accepted"] += 1
        counters["eligible_changes"] += len(changes)
    return snapshots, counters


def assign_components(snapshots: list[Snapshot]) -> None:
    union = UnionFind(snapshot.repo_key for snapshot in snapshots)
    owners: dict[tuple[str, str], str] = {}
    lineage_owners: dict[str, str] = {}
    for snapshot in snapshots:
        for blob in snapshot.component_objects:
            union.union(snapshot.repo_key, owners.setdefault(blob, snapshot.repo_key))
        for key in snapshot.lineage_keys:
            union.union(snapshot.repo_key, lineage_owners.setdefault(key, snapshot.repo_key))
    members: dict[str, list[str]] = collections.defaultdict(list)
    for snapshot in snapshots:
        members[union.find(snapshot.repo_key)].append(snapshot.repo_key)
    component_for = {
        member: stable(sorted(group)) for group in members.values() for member in group
    }
    for snapshot in snapshots:
        snapshot.component_key = component_for[snapshot.repo_key]
        bucket = int(snapshot.component_key[:8], 16) % 20
        snapshot.split = "train" if bucket < 16 else "eval" if bucket < 18 else "strict_eval"


def bounded_change_excerpt(change: Change) -> str:
    parent = change.parent_data.decode("utf-8").splitlines()
    child = change.child_data.decode("utf-8").splitlines()
    old = parent[change.old_start:change.old_end]
    new = child[change.new_start:change.new_end]
    return "\n".join([*(f"- {line}" for line in old), *(f"+ {line}" for line in new)])


def message_span(message: str, forbidden_input: str) -> tuple[int, int] | None:
    return clean_maintenance_subject(message, forbidden_input)


def common_provenance(snapshot: Snapshot, change: Change) -> dict[str, Any]:
    return {
        "source_stage": STAGE,
        "origin_url": snapshot.origin_url,
        "revision": snapshot.revision,
        "repository_key_sha256": snapshot.repo_key,
        "content_component_sha256": snapshot.component_key,
        "commit_git_oid": change.commit_oid,
        "parent_commit_git_oid": change.parent_oid,
        "commit_tree_git_oid": change.commit_tree_oid,
        "parent_tree_git_oid": change.parent_tree_oid,
        "repository_relative_path": change.path,
        "parent_git_blob_oid": change.parent_blob_oid,
        "child_git_blob_oid": change.child_blob_oid,
        "parent_file_sha256": sha256_bytes(change.parent_data),
        "child_file_sha256": sha256_bytes(change.child_data),
        "patch_fingerprint_sha256": change.patch_fingerprint,
        "git_object_identity_verified": True,
        "small_single_file_textual_hunk_verified": True,
    }


def make_row(
    snapshot: Snapshot, change: Change, objective: str, input_text: str, target: str,
    proof_fields: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    if not target.strip() or PLACEHOLDER_RE.search(target) or input_text.count(MASK) != 1:
        return None
    if target in input_text or normalized(target) in normalized(input_text):
        return None
    target_sha = sha256_bytes(target.encode("utf-8"))
    row_id = "stage12689_" + stable([
        snapshot.repo_key, change.commit_oid, objective, target_sha,
    ])[:24]
    provenance = common_provenance(snapshot, change)
    provenance.update(proof_fields)
    provenance["target_sha256"] = target_sha
    row = {
        "row_id": row_id,
        "split": snapshot.split,
        "language_family": "repository_history",
        "objective_family": objective,
        "input_text": input_text,
        "target": {"decoder_text": target},
        "loss_mask": {"decoder_ce": True},
        "source_provenance": provenance,
        "authority": dict(AUTHORITY),
    }
    proof = {
        "row_id": row_id,
        "row_sha256": stable(row),
        "model_input_sha256": sha256_bytes(input_text.encode("utf-8")),
        "target_sha256": target_sha,
        "split": snapshot.split,
        "objective_family": objective,
        "repository_key_sha256": snapshot.repo_key,
        "content_component_sha256": snapshot.component_key,
        "commit_git_oid": change.commit_oid,
        "patch_fingerprint_sha256": change.patch_fingerprint,
        "target_absent_from_input": True,
        "normalized_target_absent_from_input": True,
        "model_input_target_mutation_independent": True,
        "exact_reconstruction_verified": True,
        "training_admitted": False,
        "strict_eval_admitted": False,
        "sealed_eval_admitted": False,
    }
    return row, proof


def build_maintenance_row(snapshot: Snapshot, change: Change) -> tuple[dict[str, Any], dict[str, Any]] | None:
    excerpt = bounded_change_excerpt(change)
    prefix = f"changed_file: {change.path}\n<PARENT_TO_CHILD_CHANGE>\n{excerpt}\n</PARENT_TO_CHILD_CHANGE>\n"
    exact_subject_evidence = f"{change.path}\n{excerpt}"
    span = message_span(change.message, exact_subject_evidence)
    if span is None:
        return None
    start, end = span
    target = change.message[start:end]
    input_text = prefix + f"<COMMIT_SUBJECT>\n{MASK}\n</COMMIT_SUBJECT>"
    expected = prefix + f"<COMMIT_SUBJECT>\n{target}\n</COMMIT_SUBJECT>"
    if input_text.replace(MASK, target, 1) != expected:
        raise Stage12689Error("commit_subject_reconstruction_failure")
    return make_row(snapshot, change, "maintenance_commit_message_span_completion", input_text, target, {
        "commit_message_sha256": sha256_bytes(change.message.encode("utf-8")),
        "message_body_rendered": False,
        "subject_span_start_char": start,
        "subject_span_end_char": end,
        "commit_subject_exact_reinsertion_verified": True,
    })


def build_small_diff_row(snapshot: Snapshot, change: Change) -> tuple[dict[str, Any], dict[str, Any]] | None:
    parent = change.parent_data.decode("utf-8").splitlines(keepends=True)
    child = change.child_data.decode("utf-8").splitlines(keepends=True)
    left = max(0, change.new_start - CONTEXT_LINES)
    right = min(len(child), change.new_end + CONTEXT_LINES)
    target = "".join(child[change.new_start:change.new_end])
    child_before = "".join(child[left:change.new_start])
    child_after = "".join(child[change.new_end:right])
    parent_hunk = "".join(parent[change.old_start:change.old_end])
    input_text = (
        f"repository_relative_path: {change.path}\n"
        f"<PARENT_HUNK>\n{parent_hunk}</PARENT_HUNK>\n"
        f"<CHILD_CONTEXT>\n{child_before}{MASK}{child_after}</CHILD_CONTEXT>"
    )
    expected = (
        f"repository_relative_path: {change.path}\n"
        f"<PARENT_HUNK>\n{parent_hunk}</PARENT_HUNK>\n"
        f"<CHILD_CONTEXT>\n{''.join(child[left:right])}</CHILD_CONTEXT>"
    )
    if input_text.replace(MASK, target, 1) != expected:
        raise Stage12689Error("child_context_reconstruction_failure")
    return make_row(snapshot, change, "small_diff_exact_child_hunk_completion", input_text, target, {
        "parent_hunk_start_line": change.old_start,
        "parent_hunk_end_line": change.old_end,
        "child_hunk_start_line": change.new_start,
        "child_hunk_end_line": change.new_end,
        "child_context_start_line": left,
        "child_context_end_line": right,
        "child_context_exact_reinsertion_verified": True,
    })


def estimate_component_row_capacities(
    snapshots: list[Snapshot], counters: collections.Counter[str],
) -> dict[str, int]:
    for snapshot in snapshots:
        snapshot.split = "capacity_estimation"
    capacities: collections.Counter[str] = collections.Counter()
    patch_owners: dict[str, str] = {}
    patch_row_counts: collections.Counter[str] = collections.Counter()
    row_hashes: set[str] = set()
    input_hashes: set[str] = set()
    repo_rows: collections.Counter[str] = collections.Counter()
    for snapshot in sorted(snapshots, key=lambda item: (item.component_key, item.repo_key)):
        for change in snapshot.changes:
            if repo_rows[snapshot.repo_key] >= MAX_ROWS_PER_REPO:
                break
            prior_component = patch_owners.setdefault(
                change.patch_fingerprint, snapshot.component_key,
            )
            if prior_component != snapshot.component_key:
                counters["capacity_cross_component_patch_fingerprint_quarantined"] += 1
                continue
            if patch_row_counts[change.patch_fingerprint] >= 2:
                counters["capacity_duplicate_patch_objectives_quarantined"] += 1
                continue
            for builder in (build_maintenance_row, build_small_diff_row):
                if repo_rows[snapshot.repo_key] >= MAX_ROWS_PER_REPO:
                    break
                built = builder(snapshot, change)
                if built is None:
                    counters[f"capacity_{builder.__name__}_rejected"] += 1
                    continue
                _row, proof = built
                if proof["row_sha256"] in row_hashes or proof["model_input_sha256"] in input_hashes:
                    counters["capacity_duplicate_row_or_input_quarantined"] += 1
                    continue
                row_hashes.add(proof["row_sha256"])
                input_hashes.add(proof["model_input_sha256"])
                capacities[snapshot.component_key] += 1
                repo_rows[snapshot.repo_key] += 1
                patch_row_counts[change.patch_fingerprint] += 1
    return dict(sorted(capacities.items()))


def choose_component_subset(
    capacities: Mapping[str, int], target: int,
) -> tuple[str, ...] | None:
    if target <= 0:
        return ()
    states: dict[int, tuple[int, tuple[str, ...]]] = {0: (0, ())}
    for component_key, capacity in sorted(capacities.items()):
        if capacity <= 0:
            continue
        updated = dict(states)
        for covered, (actual, selected) in states.items():
            new_covered = min(target, covered + capacity)
            candidate = (actual + capacity, selected + (component_key,))
            prior = updated.get(new_covered)
            if prior is None or candidate < prior:
                updated[new_covered] = candidate
        states = updated
    result = states.get(target)
    return None if result is None else result[1]


def allocate_components_by_capacity(
    snapshots: list[Snapshot], capacities: Mapping[str, int], split_caps: Mapping[str, int],
) -> dict[str, str]:
    required = {split: int(split_caps[split]) for split in ("train", "eval", "strict_eval")}
    if sum(capacities.values()) < sum(required.values()):
        raise Stage12689Error("requested_split_caps_unfilled")
    remaining = dict(capacities)
    assignments: dict[str, str] = {}
    for split in ("strict_eval", "eval"):
        selected = choose_component_subset(remaining, required[split])
        if selected is None:
            raise Stage12689Error("requested_split_caps_unfilled")
        for component_key in selected:
            assignments[component_key] = split
            remaining.pop(component_key)
    if sum(remaining.values()) < required["train"]:
        raise Stage12689Error("requested_split_caps_unfilled")
    for component_key in remaining:
        assignments[component_key] = "train"
    for snapshot in snapshots:
        snapshot.split = assignments.get(snapshot.component_key, "train")
    assigned_capacity = collections.Counter()
    for component_key, capacity in capacities.items():
        assigned_capacity[assignments[component_key]] += capacity
    if any(assigned_capacity[split] < required[split] for split in required):
        raise Stage12689Error("requested_split_caps_unfilled")
    return dict(sorted(assignments.items()))


def write_json_atomic(path: Path, value: Any) -> None:
    secure_atomic_write(
        path,
        (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("ascii"),
        mode=0o644,
    )


def write_jsonl_atomic(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    data = b"".join(
        json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii") + b"\n"
        for row in rows
    )
    secure_atomic_write(path, data, mode=0o600)


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("ascii")


def jsonl_bytes(rows: Iterable[Mapping[str, Any]]) -> bytes:
    return b"".join(
        json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii") + b"\n"
        for row in rows
    )


@dataclass(frozen=True)
class ArtifactIdentity:
    device: int
    inode: int
    size: int
    sha256: str


@dataclass(frozen=True)
class PreparedRelease:
    rows: list[dict[str, Any]]
    proofs: list[dict[str, Any]]
    catalog: list[dict[str, Any]]
    public_payloads: dict[str, bytes]
    summary: dict[str, Any]


def sha256_open_fd(fd: int) -> str:
    digest = hashlib.sha256()
    os.lseek(fd, 0, os.SEEK_SET)
    while True:
        chunk = os.read(fd, 1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
    os.lseek(fd, 0, os.SEEK_SET)
    return digest.hexdigest()


def secure_write_at(directory_fd: int, name: str, data: bytes, *, mode: int) -> ArtifactIdentity:
    if not name or "/" in name or "\\" in name or name in {".", ".."}:
        raise Stage12689Error("invalid_generation_entry_name")
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(name, flags, mode, dir_fd=directory_fd)
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode):
            raise Stage12689Error("generation_entry_not_regular")
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise Stage12689Error("generation_entry_short_write")
            view = view[written:]
        os.fchmod(fd, mode)
        os.fsync(fd)
        finalized = os.fstat(fd)
        digest = sha256_open_fd(fd)
        if finalized.st_size != len(data):
            raise Stage12689Error("generation_entry_size_mismatch")
        return ArtifactIdentity(
            device=finalized.st_dev,
            inode=finalized.st_ino,
            size=finalized.st_size,
            sha256=digest,
        )
    finally:
        os.close(fd)


def create_directory_at(parent_fd: int, name: str, *, mode: int) -> int:
    if not name or "/" in name or "\\" in name or name in {".", ".."}:
        raise Stage12689Error("invalid_generation_directory_name")
    os.mkdir(name, mode, dir_fd=parent_fd)
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    return os.open(name, flags, dir_fd=parent_fd)


def revalidate_directory_identity(path: Path, directory_fd: int) -> None:
    opened = os.fstat(directory_fd)
    current = os.stat(path, follow_symlinks=False)
    if (
        not stat.S_ISDIR(opened.st_mode)
        or not stat.S_ISDIR(current.st_mode)
        or (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino)
    ):
        raise Stage12689Error("publication_parent_inode_changed")


def revalidate_directory_entry(parent_fd: int, name: str, directory_fd: int) -> tuple[int, int]:
    opened = os.fstat(directory_fd)
    current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    if (
        not stat.S_ISDIR(opened.st_mode)
        or not stat.S_ISDIR(current.st_mode)
        or (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino)
    ):
        raise Stage12689Error("pending_generation_inode_changed")
    return opened.st_dev, opened.st_ino


def verify_published_generation(
    parent_fd: int,
    entry_name: str,
    expected_identity: tuple[int, int],
    required_artifacts: Mapping[str, ArtifactIdentity],
    *,
    phase: str,
) -> None:
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        named_directory = os.stat(entry_name, dir_fd=parent_fd, follow_symlinks=False)
        generation_fd = os.open(entry_name, directory_flags, dir_fd=parent_fd)
    except OSError as exc:
        raise Stage12689Error(f"{phase}_generation_entry_unavailable") from exc
    try:
        opened_directory = os.fstat(generation_fd)
        if (
            not stat.S_ISDIR(named_directory.st_mode)
            or (named_directory.st_dev, named_directory.st_ino) != expected_identity
            or (opened_directory.st_dev, opened_directory.st_ino) != expected_identity
        ):
            raise Stage12689Error(f"{phase}_generation_inode_mismatch")
        if set(os.listdir(generation_fd)) != set(required_artifacts):
            raise Stage12689Error(f"{phase}_generation_entry_set_mismatch")
        artifact_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        for name, expected in sorted(required_artifacts.items()):
            artifact_fd: int | None = None
            try:
                named_before = os.stat(name, dir_fd=generation_fd, follow_symlinks=False)
                artifact_fd = os.open(name, artifact_flags, dir_fd=generation_fd)
                opened = os.fstat(artifact_fd)
                digest = sha256_open_fd(artifact_fd)
                named_after = os.stat(name, dir_fd=generation_fd, follow_symlinks=False)
            except OSError as exc:
                raise Stage12689Error(f"{phase}_generation_required_artifact_missing:{name}") from exc
            finally:
                if artifact_fd is not None:
                    os.close(artifact_fd)
            expected_file_identity = (expected.device, expected.inode)
            if (
                not stat.S_ISREG(named_before.st_mode)
                or not stat.S_ISREG(opened.st_mode)
                or not stat.S_ISREG(named_after.st_mode)
                or (named_before.st_dev, named_before.st_ino) != expected_file_identity
                or (opened.st_dev, opened.st_ino) != expected_file_identity
                or (named_after.st_dev, named_after.st_ino) != expected_file_identity
                or named_before.st_size != expected.size
                or opened.st_size != expected.size
                or named_after.st_size != expected.size
                or digest != expected.sha256
            ):
                raise Stage12689Error(f"{phase}_generation_artifact_identity_mismatch:{name}")
    finally:
        os.close(generation_fd)


def rename_directory_noreplace(parent_fd: int, source_name: str, destination_name: str) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise Stage12689Error("renameat2_noreplace_unavailable")
    renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    renameat2.restype = ctypes.c_int
    result = renameat2(
        parent_fd, source_name.encode("utf-8"),
        parent_fd, destination_name.encode("utf-8"),
        1,
    )
    if result == 0:
        return
    error = ctypes.get_errno()
    if error == errno.EEXIST:
        raise FileExistsError(error, os.strerror(error), destination_name)
    raise OSError(error, os.strerror(error), destination_name)


def cross_split_overlap_count(proofs: Iterable[Mapping[str, Any]], key: str) -> int:
    splits_by_identity: dict[str, set[str]] = collections.defaultdict(set)
    for proof in proofs:
        splits_by_identity[str(proof[key])].add(str(proof["split"]))
    return sum(len(splits) > 1 for splits in splits_by_identity.values())


def require_zero_finalized_overlaps(proofs: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    proof_rows = list(proofs)
    overlaps = {
        "repository": cross_split_overlap_count(proof_rows, "repository_key_sha256"),
        "component": cross_split_overlap_count(proof_rows, "content_component_sha256"),
        "patch": cross_split_overlap_count(proof_rows, "patch_fingerprint_sha256"),
    }
    nonzero = {key: value for key, value in overlaps.items() if value}
    if nonzero:
        raise Stage12689Error(f"finalized_cross_split_overlap:{nonzero}")
    return overlaps


def release_generation_id(
    artifact_payloads: Mapping[str, bytes], strict_eval_commitment_sha256: str,
) -> str:
    artifact_hashes = sorted(
        (name, sha256_bytes(payload)) for name, payload in artifact_payloads.items()
    )
    return stable([
        "stage12689_generation_v2_public_release_contract",
        ARTIFACT_SCHEMA_VERSION,
        artifact_hashes,
        strict_eval_commitment_sha256,
    ])[:24]


def prepare_release(
    source_root: Path, *, max_repos: int, max_rows: int,
) -> PreparedRelease:
    if max_rows < 10 or max_rows % 10 != 0:
        raise Stage12689Error(
            f"invalid_max_rows_release_geometry:required_minimum=10:required_divisor=10:actual={max_rows}"
        )
    if not source_root.is_dir():
        raise Stage12689Error(f"source_root_missing:{source_root}")
    snapshots, counters = discover_repositories(source_root, max_repos)
    if not snapshots:
        raise Stage12689Error("no_eligible_repositories")
    assign_components(snapshots)
    split_caps = {
        "train": max_rows * 8 // 10,
        "eval": max_rows // 10,
        "strict_eval": max_rows - (max_rows * 8 // 10) - (max_rows // 10),
    }
    component_capacities = estimate_component_row_capacities(snapshots, counters)
    allocate_components_by_capacity(snapshots, component_capacities, split_caps)
    rows: list[dict[str, Any]] = []
    proofs: list[dict[str, Any]] = []
    catalogs: list[dict[str, Any]] = []
    patch_owners: dict[str, str] = {}
    patch_row_counts: collections.Counter[str] = collections.Counter()
    row_hashes: set[str] = set()
    input_hashes: set[str] = set()
    repo_rows: collections.Counter[str] = collections.Counter()
    split_counts: collections.Counter[str] = collections.Counter()
    for snapshot in sorted(snapshots, key=lambda item: (item.component_key, item.repo_key)):
        catalogs.append({
            "repository_key_sha256": snapshot.repo_key,
            "origin_url": snapshot.origin_url,
            "revision": snapshot.revision,
            "content_component_sha256": snapshot.component_key,
            "split": snapshot.split,
            "eligible_change_count": len(snapshot.changes),
            "lineage_key_sha256s": [sha256_bytes(key.encode("utf-8")) for key in snapshot.lineage_keys],
            "head_ls_tree_object_identity_count": len(snapshot.component_objects),
            "head_ls_tree_object_identity_set_sha256": stable(snapshot.component_objects),
            "component_identity_contract": "all_recursive_head_ls_tree_entries_object_type_and_oid_v1",
            "component_identity_exclusions": [],
        })
        for change in snapshot.changes:
            if repo_rows[snapshot.repo_key] >= MAX_ROWS_PER_REPO:
                break
            prior_component = patch_owners.setdefault(change.patch_fingerprint, snapshot.component_key)
            if prior_component != snapshot.component_key:
                counters["cross_component_patch_fingerprint_quarantined"] += 1
                continue
            if split_counts[snapshot.split] >= split_caps[snapshot.split]:
                continue
            if patch_row_counts[change.patch_fingerprint] >= 2:
                counters["duplicate_patch_objectives_quarantined"] += 1
                continue
            for builder in (build_maintenance_row, build_small_diff_row):
                if (
                    split_counts[snapshot.split] >= split_caps[snapshot.split]
                    or repo_rows[snapshot.repo_key] >= MAX_ROWS_PER_REPO
                ):
                    break
                built = builder(snapshot, change)
                if built is None:
                    counters[f"{builder.__name__}_rejected"] += 1
                    continue
                row, proof = built
                if proof["row_sha256"] in row_hashes or proof["model_input_sha256"] in input_hashes:
                    counters["duplicate_row_or_input_quarantined"] += 1
                    continue
                row_hashes.add(proof["row_sha256"])
                input_hashes.add(proof["model_input_sha256"])
                rows.append(row)
                proofs.append(proof)
                repo_rows[snapshot.repo_key] += 1
                split_counts[snapshot.split] += 1
                patch_row_counts[change.patch_fingerprint] += 1
    actual_split_counts = {
        split: split_counts[split] for split in ("train", "eval", "strict_eval")
    }
    if actual_split_counts != split_caps or len(rows) != max_rows:
        raise Stage12689Error("requested_split_caps_unfilled")
    train_eval = [row for row in rows if row["split"] != "strict_eval"]
    train_eval_proofs = [proof for proof in proofs if proof["split"] != "strict_eval"]
    train_eval_catalog = [entry for entry in catalogs if entry["split"] != "strict_eval"]
    strict_proofs = [proof for proof in proofs if proof["split"] == "strict_eval"]
    materialized_objective_counts = collections.Counter(
        row["objective_family"] for row in train_eval
    )
    materialized_repository_keys = {
        proof["repository_key_sha256"] for proof in train_eval_proofs
    }
    materialized_component_keys = {
        proof["content_component_sha256"] for proof in train_eval_proofs
    }
    finalized_overlaps = require_zero_finalized_overlaps(proofs)
    strict_eval_commitment_sha256 = stable(
        sorted(proof["row_sha256"] for proof in strict_proofs)
    )
    artifacts = {
        "maintenance_history_train_eval_manifest.jsonl": train_eval,
        "train_eval_source_provenance_ledger.jsonl": train_eval_proofs,
        "train_eval_source_catalog.jsonl": train_eval_catalog,
    }
    artifact_payloads = {name: jsonl_bytes(values) for name, values in artifacts.items()}
    generation_id = release_generation_id(
        artifact_payloads, strict_eval_commitment_sha256,
    )
    artifact_contract = {
        name: {
            "relative_path": f"private/{generation_id}/{name}",
            "rows": len(artifacts[name]),
            "sha256": sha256_bytes(data),
        }
        for name, data in artifact_payloads.items()
    }
    summary = {
        "stage": STAGE,
        "generation_id": generation_id,
        "generation_relative_path": f"private/{generation_id}",
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "decision": "SOURCE_BACKED_MAINTENANCE_HISTORY_CORPUS_MATERIALIZED_REVIEW_REQUIRED",
        "objectives": [
            "maintenance_commit_message_span_completion",
            "small_diff_exact_child_hunk_completion",
        ],
        "materialized_repository_snapshots": len(train_eval_catalog),
        "materialized_content_components": len(materialized_component_keys),
        "component_identity_contract": "all_recursive_head_ls_tree_entries_object_type_and_oid_v1",
        "component_identity_exclusions": [],
        "capacity_estimation_contract": (
            "buildable_objectives_after_patch_input_row_and_repository_caps_v1"
        ),
        "split_allocation_contract": "whole_component_exact_80_10_10_row_caps_v1",
        "materialized_repositories_contributing_rows": len(materialized_repository_keys),
        "materialized_model_row_count": len(train_eval),
        "reserved_unmaterialized_strict_row_count": len(strict_proofs),
        "strict_eval_commitment_sha256": strict_eval_commitment_sha256,
        "objective_counts": dict(sorted(materialized_objective_counts.items())),
        "materialized_patch_fingerprint_count": len({
            proof["patch_fingerprint_sha256"] for proof in train_eval_proofs
        }),
        "cross_split_repository_overlap": finalized_overlaps["repository"],
        "cross_split_component_overlap": finalized_overlaps["component"],
        "cross_split_patch_fingerprint_overlap": finalized_overlaps["patch"],
        "target_or_normalized_target_in_input_rows": 0,
        "materialized_exact_reconstruction_verified_rows": len(train_eval),
        "materialized_model_input_target_mutation_independent_rows": len(train_eval),
        "artifact_contract": artifact_contract,
        "training_eligible_rows": 0,
        "unresolved_knowledge_lanes": [
            "api_and_symbol_reference_prediction",
            "doc_code_test_relationships",
            "test_file_association",
            "compact_machine_verifier_summaries",
        ],
        "release_blockers": [
            "independent_semantic_and_leakage_review_required",
            "tokenizer_bound_context_and_target_audit_required",
            "repository_wide_history_completeness_audit_required",
            "limited_history_window_requires_overlap_review",
            "near_duplicate_patch_and_message_audit_required",
        ],
        "history_scan_max_commits_per_repository": MAX_COMMITS_PER_REPO,
        "history_scan_complete": False,
        "authoritative_summary_relative_path": f"private/{generation_id}/summary.json",
        "summary_mirrors_are_authoritative": False,
        "authority": dict(AUTHORITY),
    }
    return PreparedRelease(
        rows=rows,
        proofs=proofs,
        catalog=catalogs,
        public_payloads=artifact_payloads,
        summary=summary,
    )


def _publish_prepared_release(
    output_dir: Path,
    summary_path: Path,
    prepared: PreparedRelease,
) -> dict[str, Any]:
    summary = prepared.summary
    generation_id = summary["generation_id"]
    artifact_payloads = prepared.public_payloads
    private_root = output_dir / "private"
    private_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if private_root.is_symlink() or private_root.resolve() != private_root.absolute():
        raise Stage12689Error("symlinked_private_root")
    os.chmod(private_root, 0o700)
    pending_name = f".pending-{generation_id}-{os.getpid()}"
    generation_name = generation_id
    private_fd = open_directory_nofollow(private_root)
    revalidate_directory_identity(private_root, private_fd)
    pending_fd = create_directory_at(private_fd, pending_name, mode=0o700)
    artifact_identities = {
        name: secure_write_at(pending_fd, name, data, mode=0o400)
        for name, data in artifact_payloads.items()
    }
    try:
        summary_identity = secure_write_at(
            pending_fd, "summary.json", json_bytes(summary), mode=0o400,
        )
        required_artifacts = dict(artifact_identities)
        required_artifacts["summary.json"] = summary_identity
        os.fchmod(pending_fd, 0o500)
        os.fsync(pending_fd)
        revalidate_directory_identity(private_root, private_fd)
        pending_identity = revalidate_directory_entry(private_fd, pending_name, pending_fd)
        verify_published_generation(
            private_fd,
            pending_name,
            pending_identity,
            required_artifacts,
            phase="pending",
        )
        try:
            rename_directory_noreplace(private_fd, pending_name, generation_name)
        except FileExistsError as exc:
            raise Stage12689Error(f"immutable_generation_exists:{generation_id}") from exc
        verify_published_generation(
            private_fd,
            generation_name,
            pending_identity,
            required_artifacts,
            phase="published",
        )
        os.fsync(private_fd)
    finally:
        os.close(pending_fd)
        os.close(private_fd)
    write_json_atomic(summary_path, summary)
    write_json_atomic(output_dir / "summary.json", summary)
    return summary


def build(
    source_root: Path, output_dir: Path, summary_path: Path, *, max_repos: int, max_rows: int,
) -> dict[str, Any]:
    prepared = prepare_release(source_root, max_repos=max_repos, max_rows=max_rows)
    return _publish_prepared_release(output_dir, summary_path, prepared)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--summary-path", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--max-repos", type=int, default=MAX_REPOS)
    parser.add_argument("--max-rows", type=int, default=MAX_ROWS)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.max_repos <= 0:
        raise SystemExit("max-repos must be positive")
    if args.max_rows < 10 or args.max_rows % 10 != 0:
        raise SystemExit("max-rows must be at least 10 and divisible by 10")
    print(json.dumps(build(
        args.source_root.resolve(), args.output_dir.resolve(), args.summary_path.resolve(),
        max_repos=args.max_repos, max_rows=args.max_rows,
    ), indent=2, sort_keys=True))
