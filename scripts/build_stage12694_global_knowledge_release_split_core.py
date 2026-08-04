#!/usr/bin/env python3
"""Bounded, publication-free global split planning for knowledge stages 12687-12699."""

from __future__ import annotations

import collections
import hashlib
import itertools
import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit

STAGE = "stage12694_global_knowledge_release_split_core"
STAGE_SCHEMAS = {
    12687: 4,
    12688: 4,
    12689: 1,
    12690: 3,
    12691: 2,
    12692: 1,
    12698: 1,
    12699: 1,
}
STAGE_LEDGER_COMMITMENT_FIELDS = {
    12687: ("row_sha256", "model_example_sha256", "target_sha256"),
    12688: (
        "row_sha256",
        "encoder_input_sha256",
        "model_example_sha256",
        "target_sha256",
    ),
    12689: ("row_sha256", "model_input_sha256", "target_sha256"),
    12690: ("row_sha256", "model_input_sha256"),
    12691: ("row_sha256", "model_input_sha256", "target_sha256"),
    12692: ("row_sha256", "model_input_sha256"),
    12698: ("row_sha256", "model_input_sha256", "target_sha256"),
    12699: ("row_sha256", "model_input_sha256", "target_sha256"),
}
SUPPORTED_STAGES = frozenset(STAGE_SCHEMAS)
SPLITS = ("train", "eval", "strict_eval")
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

_SHA1_OR_SHA256 = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_UPPER_PLACEHOLDER = re.compile(r"(?:[A-Z][A-Z0-9_]*_)?PLACEHOLDER")
_ANSWER_TEMPLATE = re.compile(
    r"(?is)(?:correct\s+)?answer\s*:\s*(?:<missing>|<answer>|PLACEHOLDER)?"
)
_STUB_TARGET = re.compile(
    r"(?is)^\s*(?:pass|\.\.\.|todo|tbd|<fill(?:ed)?>|raise\s+NotImplementedError(?:\([^)]*\))?)\s*;?\s*$"
)


class Stage12694Error(RuntimeError):
    pass


@dataclass(frozen=True)
class StageArtifacts:
    """Already-loaded immutable artifact records; this core performs no file I/O."""

    stage: int
    schema_version: int
    rows: tuple[Mapping[str, Any], ...]
    ledger: tuple[Mapping[str, Any], ...]
    catalog: tuple[Mapping[str, Any], ...]
    catalog_commitment_sha256: str | None = None
    ledger_commitment_sha256: str | None = None


@dataclass(frozen=True)
class _NormalizedRow:
    stage: int
    row_id: str
    source_split: str
    repository_node: str
    input_sha256: str
    input_target_sha256: str
    semantic_sha256s: tuple[str, ...]
    source_evidence: tuple[str, ...]
    candidate_evidence: tuple[str, ...]
    patch_evidence: tuple[str, ...]
    atomic_weak_evidence: tuple[str, ...]
    input_reasons: tuple[str, ...]
    target_reasons: tuple[str, ...]


class UnionFind:
    def __init__(self, keys: Iterable[str]) -> None:
        self.parent = {key: key for key in keys}

    def find(self, key: str) -> str:
        root = key
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[key] != key:
            key, self.parent[key] = self.parent[key], root
        return root

    def union(self, left: str, right: str) -> None:
        left, right = self.find(left), self.find(right)
        if left != right:
            keep, merge = sorted((left, right))
            self.parent[merge] = keep


def stable(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _records_commitment(records: Sequence[Mapping[str, Any]]) -> str:
    return stable(list(records))


def canonical_origin(raw: Any) -> str:
    """Canonicalize recorded origin metadata without treating it as identity."""

    if not isinstance(raw, str):
        return ""
    value = raw.strip()
    if not value or "\x00" in value or "\n" in value:
        return ""
    if value.startswith("git@") and ":" in value:
        host, path = value[4:].split(":", 1)
        value = f"ssh://git@{host}/{path}"
    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.hostname:
        return ""
    scheme = parsed.scheme.lower()
    host = parsed.hostname.lower()
    port = f":{parsed.port}" if parsed.port else ""
    user = f"{parsed.username}@" if parsed.username else ""
    path = re.sub(r"/+", "/", parsed.path).rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    return urlunsplit((scheme, user + host + port, path, "", ""))


def placeholder_rejection_reason(text: Any, *, target: bool = False) -> str | None:
    if not isinstance(text, str) or not text.strip():
        return "empty_text"
    if "\x00" in text:
        return "nul_text"
    stripped = text.strip()
    if _UPPER_PLACEHOLDER.fullmatch(stripped):
        return "unresolved_uppercase_placeholder"
    if _ANSWER_TEMPLATE.fullmatch(stripped):
        return "unresolved_answer_marker"
    if target and _STUB_TARGET.fullmatch(stripped):
        return "stub_target"
    return None


def _walk_values(value: Any, prefix: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(value, Mapping):
        for key in sorted(value):
            name = f"{prefix}.{key}" if prefix else str(key)
            yield from _walk_values(value[key], name)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _walk_values(item, prefix)
    else:
        yield prefix.rsplit(".", 1)[-1], value


def _hex_values(record: Mapping[str, Any], predicate) -> set[str]:
    values: set[str] = set()
    for key, value in _walk_values(record):
        if predicate(key) and isinstance(value, str) and _SHA1_OR_SHA256.fullmatch(value):
            values.add(value)
    return values


def _require_fields(record: Mapping[str, Any], fields: Iterable[str], reason: str) -> None:
    if any(field not in record for field in fields):
        raise Stage12694Error(reason)


def _validate_digest_fields(record: Mapping[str, Any]) -> None:
    git_names = {
        "revision",
        "tree_oid",
        "git_tree_oid",
        "head_commit_git_oid",
        "commit_git_oid",
        "parent_commit_git_oid",
        "commit_tree_git_oid",
        "parent_tree_git_oid",
        "target_object_oid",
    }
    for key, value in _walk_values(record):
        is_sha256 = key.endswith("sha256")
        is_git_identity = (
            key in git_names
            or key.endswith("_git_oid")
            or key.endswith("_git_oids")
            or key.endswith("_blob_oid")
            or key.endswith("_blob_oids")
            or key.endswith("_tree_oid")
            or key.endswith("_tree_oids")
        )
        if not is_sha256 and not is_git_identity:
            continue
        if not isinstance(value, str):
            raise Stage12694Error("digest_identity_field_must_be_string")
        if is_sha256:
            if value and not _SHA256.fullmatch(value):
                raise Stage12694Error("invalid_sha256_field")
        else:
            if (
                key == "revision"
                and not _SHA1_OR_SHA256.fullmatch(value)
            ) or (
                key != "revision"
                and value
                and not _SHA1_OR_SHA256.fullmatch(value)
            ):
                raise Stage12694Error("invalid_git_object_id_field")


def _repository_evidence(record: Mapping[str, Any]) -> tuple[set[str], set[str]]:
    strong_names = {
        "revision", "commit_oid", "parent_commit_oid", "child_commit_oid",
        "tree_oid", "git_tree_oid", "head_commit_git_oid",
        "commit_git_oid", "parent_commit_git_oid", "commit_tree_git_oid",
        "parent_tree_git_oid", "root_commit_git_oids", "tree_git_oids",
        "content_component_sha256",
    }
    strong = _hex_values(record, lambda key: key in strong_names)
    objects = _hex_values(
        record,
        lambda key: "git_blob_oid" in key or key.endswith(("git_blob_oids", "_object_oid", "_object_oids")),
    )
    files = _hex_values(record, lambda key: key.endswith(("file_sha256", "file_sha256s")))
    return ({f"strong:{value}" for value in strong},
            {f"object:{value}" for value in objects} | {f"file:{value}" for value in files})


def _repo_key(record: Mapping[str, Any]) -> str:
    value = record.get("repository_key_sha256", record.get("repo_key"))
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise Stage12694Error("repository_identity_missing")
    return value


def _row_target(row: Mapping[str, Any]) -> str:
    target = row.get("target")
    if isinstance(target, Mapping):
        target = target.get("decoder_text")
    if not isinstance(target, str):
        raise Stage12694Error("row_target_missing")
    return target


def _proof_evidence(proof: Mapping[str, Any], row: Mapping[str, Any]) -> tuple[
    str, str, tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...],
    tuple[str, ...],
]:
    input_text = row.get("input_text")
    if not isinstance(input_text, str):
        raise Stage12694Error("row_input_missing")
    target = _row_target(row)
    computed_input_sha = hashlib.sha256(input_text.encode("utf-8")).hexdigest()
    recorded_input_sha = proof.get("model_input_sha256")
    if recorded_input_sha is not None and recorded_input_sha != computed_input_sha:
        raise Stage12694Error("model_input_commitment_mismatch")
    input_sha = computed_input_sha
    target_sha = hashlib.sha256(target.encode("utf-8")).hexdigest()
    pair_sha = stable([input_sha, target_sha])
    provenance = row.get("source_provenance")
    if not isinstance(provenance, Mapping):
        raise Stage12694Error("row_source_provenance_missing")
    evidence = {"proof": proof, "provenance": provenance}
    semantic = _hex_values(
        evidence,
        lambda key: "semantic" in key and key.endswith("sha256"),
    )
    candidates = _hex_values(
        evidence,
        lambda key: "candidate" in key and "sha256" in key,
    )
    patches = _hex_values(
        evidence,
        lambda key: "patch" in key and "sha256" in key,
    )
    _, atomic_weak = _repository_evidence(evidence)
    explicit_source = _hex_values(
        evidence,
        lambda key: (
            ("source_window" in key or "definition_evidence" in key
             or "occurrence_proof" in key)
            and key.endswith("sha256")
        ),
    )
    if not explicit_source:
        file_values = sorted(_hex_values(
            evidence, lambda key: key.endswith(("file_sha256", "file_sha256s"))
        ))
        location = {
            key: value for key, value in proof.items()
            if key.endswith(("_path", "_start_byte", "_end_byte"))
            and isinstance(value, (str, int))
        }
        if file_values:
            explicit_source.add(stable(["source_location_v1", file_values, location]))
    return (
        input_sha,
        pair_sha,
        tuple(sorted(semantic)),
        tuple(sorted(explicit_source)),
        tuple(sorted(candidates)),
        tuple(sorted(patches)),
        tuple(sorted(atomic_weak)),
    )


def _validate_input(item: StageArtifacts) -> None:
    if item.stage not in STAGE_SCHEMAS or item.schema_version != STAGE_SCHEMAS[item.stage]:
        raise Stage12694Error("unsupported_stage_or_schema")
    if not item.rows or not item.ledger or not item.catalog:
        raise Stage12694Error("rows_ledger_and_catalog_required")
    if not item.catalog_commitment_sha256 or not item.ledger_commitment_sha256:
        raise Stage12694Error("catalog_and_ledger_commitments_required")
    if item.catalog_commitment_sha256 != _records_commitment(item.catalog):
        raise Stage12694Error("catalog_commitment_mismatch")
    if item.ledger_commitment_sha256 != _records_commitment(item.ledger):
        raise Stage12694Error("ledger_commitment_mismatch")
    for record in (*item.rows, *item.ledger, *item.catalog):
        _validate_digest_fields(record)
    row_ids = [row.get("row_id") for row in item.rows]
    proof_ids = [proof.get("row_id") for proof in item.ledger]
    if any(not isinstance(value, str) or not value for value in row_ids + proof_ids):
        raise Stage12694Error("row_id_missing")
    if len(set(row_ids)) != len(row_ids) or len(set(proof_ids)) != len(proof_ids):
        raise Stage12694Error("duplicate_row_id_within_artifact")
    if set(row_ids) != set(proof_ids):
        raise Stage12694Error("row_ledger_identity_mismatch")
    catalog_repos: dict[str, tuple[str, str | None, str]] = {}
    for record in item.catalog:
        _require_fields(
            record,
            ("repository_key_sha256", "content_component_sha256", "revision"),
            "catalog_required_fields_missing",
        )
        repo = _repo_key(record)
        component = record["content_component_sha256"]
        if not isinstance(component, str) or not _SHA256.fullmatch(component):
            raise Stage12694Error("catalog_component_identity_invalid")
        split = record.get("split")
        if split is not None and split not in SPLITS:
            raise Stage12694Error("invalid_catalog_split")
        identity = (component, split, record["revision"])
        if repo in catalog_repos and catalog_repos[repo] != identity:
            raise Stage12694Error("catalog_repository_identity_conflict")
        catalog_repos[repo] = identity

    proofs = {proof["row_id"]: proof for proof in item.ledger}
    model_field = "encoder_input_sha256" if item.stage == 12688 else "model_input_sha256"
    for row in item.rows:
        _require_fields(
            row,
            ("row_id", "split", "objective_family", "input_text", "target", "source_provenance"),
            "row_required_fields_missing",
        )
        proof = proofs[row["row_id"]]
        ledger_identity_fields = [
            "row_id", "row_sha256", "split",
            "repository_key_sha256", "content_component_sha256",
            *STAGE_LEDGER_COMMITMENT_FIELDS[item.stage],
        ]
        if item.stage != 12687:
            ledger_identity_fields.append("objective_family")
        _require_fields(
            proof,
            ledger_identity_fields,
            "ledger_required_fields_missing",
        )
        repo = _repo_key(proof)
        if repo not in catalog_repos:
            raise Stage12694Error("ledger_repository_absent_from_catalog")
        if row["split"] != proof["split"]:
            raise Stage12694Error("row_ledger_identity_mismatch")
        proof_objective = proof.get("objective_family")
        if (
            (item.stage == 12687 and proof_objective is not None
             and proof_objective != row["objective_family"])
            or (item.stage != 12687
                and proof_objective != row["objective_family"])
        ):
            raise Stage12694Error("row_ledger_identity_mismatch")
        catalog_component, catalog_split, catalog_revision = catalog_repos[repo]
        if proof["content_component_sha256"] != catalog_component:
            raise Stage12694Error("ledger_catalog_component_mismatch")
        if catalog_split is not None and proof["split"] != catalog_split:
            raise Stage12694Error("ledger_catalog_split_mismatch")
        provenance = row["source_provenance"]
        if not isinstance(provenance, Mapping):
            raise Stage12694Error("row_source_provenance_missing")
        _require_fields(
            provenance,
            ("repository_key_sha256", "content_component_sha256", "revision"),
            "row_source_provenance_identity_fields_missing",
        )
        expected_provenance = {
            "repository_key_sha256": repo,
            "content_component_sha256": catalog_component,
            "revision": catalog_revision,
        }
        for field, expected in expected_provenance.items():
            if field in provenance and provenance[field] != expected:
                raise Stage12694Error("row_provenance_ledger_identity_mismatch")
            if field in proof and proof[field] != expected:
                raise Stage12694Error("ledger_catalog_identity_mismatch")
        if proof["row_sha256"] != stable(row):
            raise Stage12694Error("row_commitment_mismatch")
        input_text = row["input_text"]
        target = _row_target(row)
        input_sha = hashlib.sha256(input_text.encode("utf-8")).hexdigest()
        if item.stage != 12687:
            if proof.get(model_field) != input_sha:
                raise Stage12694Error("model_input_commitment_mismatch")
        if item.stage in {12687, 12688}:
            if proof.get("model_example_sha256") != stable([input_text, target]):
                raise Stage12694Error("model_example_commitment_mismatch")
        if item.stage in {12687, 12688, 12689, 12691, 12698, 12699}:
            target_sha = hashlib.sha256(target.encode("utf-8")).hexdigest()
            if proof.get("target_sha256") != target_sha:
                raise Stage12694Error("target_commitment_mismatch")


def _build_components(
    inputs: Sequence[StageArtifacts],
) -> tuple[UnionFind, dict[str, dict[str, Any]], dict[str, set[str]], dict[str, set[str]]]:
    repositories: dict[str, dict[str, Any]] = {}
    strong_by_node: dict[str, set[str]] = collections.defaultdict(set)
    weak_by_node: dict[str, set[str]] = collections.defaultdict(set)
    for item in inputs:
        records = list(item.catalog) + list(item.ledger)
        for record in records:
            repo = _repo_key(record)
            node = f"stage{item.stage}:{repo}"
            metadata = repositories.setdefault(node, {"origins": set()})
            origin = canonical_origin(record.get("origin_url"))
            if origin:
                metadata["origins"].add(origin)
            strong, weak = _repository_evidence(record)
            strong_by_node[node].update(strong)
            weak_by_node[node].update(weak)
    if not repositories:
        raise Stage12694Error("no_repository_records")
    union = UnionFind(repositories)
    strong_owners: dict[str, list[str]] = collections.defaultdict(list)
    for node, tokens in strong_by_node.items():
        for token in tokens:
            strong_owners[token].append(node)
    for owners in strong_owners.values():
        for node in sorted(owners)[1:]:
            union.union(sorted(owners)[0], node)

    return union, repositories, strong_by_node, weak_by_node


def _conflicting_atomic_weak_tokens(
    rows: Sequence[_NormalizedRow],
    row_components: Mapping[str, str],
) -> set[str]:
    """Return atomic file/blob tokens owned by distinct strong components."""

    owners: dict[str, set[str]] = collections.defaultdict(set)
    for row in rows:
        row_ref = f"stage{row.stage}:{row.row_id}"
        for token in row.atomic_weak_evidence:
            owners[token].add(row_components[row_ref])
    return {
        token for token, components in owners.items()
        if len(components) > 1
    }


def _evidence_reasons(
    stage: int,
    objective: str,
    *,
    strong_lineage: bool,
    semantic: Sequence[str],
    source: Sequence[str],
    candidates: Sequence[str],
    patches: Sequence[str],
    atomic_weak: Sequence[str],
) -> tuple[str, ...]:
    reasons = []
    if not strong_lineage:
        reasons.append("missing_strong_lineage_evidence")
    if not atomic_weak:
        reasons.append("missing_applicable_atomic_file_or_blob_evidence")
    if stage == 12689:
        if not patches:
            reasons.append("missing_patch_evidence")
    elif not source:
        reasons.append("missing_source_evidence")
    if stage in {12687, 12688, 12692} and not semantic:
        reasons.append("missing_semantic_evidence")
    if stage == 12690 and not candidates:
        reasons.append("missing_candidate_evidence")
    if (
        stage in {12691, 12692}
        and ("doc" in objective or "target_resolution" in objective)
        and not candidates
    ):
        reasons.append("missing_candidate_evidence")
    return tuple(sorted(reasons))


def _normalize_rows(
    inputs: Sequence[StageArtifacts],
    union: UnionFind,
    strong_by_node: Mapping[str, set[str]],
) -> tuple[list[_NormalizedRow], dict[str, str]]:
    normalized: list[_NormalizedRow] = []
    row_components: dict[str, str] = {}
    for item in sorted(inputs, key=lambda value: value.stage):
        proofs = {proof["row_id"]: proof for proof in item.ledger}
        for row in sorted(item.rows, key=lambda value: str(value["row_id"])):
            proof = proofs[row["row_id"]]
            repo = _repo_key(proof)
            node = f"stage{item.stage}:{repo}"
            if node not in union.parent:
                raise Stage12694Error("ledger_repository_absent_from_component_graph")
            source_split = row.get("split", proof.get("split"))
            if source_split not in SPLITS:
                raise Stage12694Error("invalid_source_split")
            (
                input_sha, pair_sha, semantic, source, candidates, patches,
                atomic_weak,
            ) = _proof_evidence(proof, row)
            input_reason = placeholder_rejection_reason(row.get("input_text"))
            target_reason = placeholder_rejection_reason(_row_target(row), target=True)
            key = f"stage{item.stage}:{row['row_id']}"
            component = union.find(node)
            input_reasons = list(_evidence_reasons(
                item.stage,
                str(row["objective_family"]),
                strong_lineage=bool(strong_by_node.get(node)),
                semantic=semantic,
                source=source,
                candidates=candidates,
                patches=patches,
                atomic_weak=atomic_weak,
            ))
            if input_reason:
                input_reasons.append(input_reason)
            row_components[key] = component
            normalized.append(_NormalizedRow(
                item.stage, str(row["row_id"]), source_split, node, input_sha,
                pair_sha, semantic, source, candidates, patches, atomic_weak,
                tuple(sorted(set(input_reasons))),
                (target_reason,) if target_reason else (),
            ))
    return normalized, row_components


def _pre_assignment_quarantine(
    rows: Sequence[_NormalizedRow],
    row_components: Mapping[str, str],
    conflicting_atomic_weak_tokens: set[str],
) -> tuple[list[_NormalizedRow], list[dict[str, Any]]]:
    exact_fields = {
        "duplicate_encoder_input": lambda row: (row.input_sha256,),
    }
    cross_component_fields = {
        "duplicate_source_evidence": lambda row: row.source_evidence,
        "duplicate_candidate_evidence": lambda row: row.candidate_evidence,
        "duplicate_patch_evidence": lambda row: row.patch_evidence,
    }
    reasons: dict[str, set[str]] = collections.defaultdict(set)
    keys = {id(row): f"stage{row.stage}:{row.row_id}" for row in rows}
    for row in rows:
        reasons[keys[id(row)]].update(row.input_reasons)
        if conflicting_atomic_weak_tokens.intersection(row.atomic_weak_evidence):
            reasons[keys[id(row)]].add("conflicting_atomic_weak_evidence")
    for reason, getter in exact_fields.items():
        owners: dict[str, list[_NormalizedRow]] = collections.defaultdict(list)
        for row in rows:
            for value in getter(row):
                owners[value].append(row)
        for duplicates in owners.values():
            if len(duplicates) > 1:
                for row in duplicates:
                    reasons[keys[id(row)]].add(reason)
    for reason, getter in cross_component_fields.items():
        owners: dict[str, list[_NormalizedRow]] = collections.defaultdict(list)
        for row in rows:
            for value in getter(row):
                owners[value].append(row)
        for duplicates in owners.values():
            components = {row_components[keys[id(row)]] for row in duplicates}
            if len(components) > 1:
                for row in duplicates:
                    reasons[keys[id(row)]].add(reason)
    retained = [row for row in rows if not reasons[keys[id(row)]]]
    report = [
        {"row_ref": key, "reasons": sorted(value)}
        for key, value in sorted(reasons.items()) if value
    ]
    return retained, report


def _direct_weak_quarantine_report(
    rows: Sequence[_NormalizedRow],
    conflicting_atomic_weak_tokens: set[str],
) -> dict[str, Any]:
    by_stage: collections.Counter[str] = collections.Counter()
    row_count = 0
    for row in rows:
        if conflicting_atomic_weak_tokens.intersection(row.atomic_weak_evidence):
            by_stage[str(row.stage)] += 1
            row_count += 1
    return {
        "row_count": row_count,
        "row_count_by_stage": dict(sorted(by_stage.items())),
        "conflicting_atomic_token_count": len(conflicting_atomic_weak_tokens),
        "quarantine_reason": "conflicting_atomic_weak_evidence",
    }


def _post_assignment_target_quarantine(
    rows: Sequence[_NormalizedRow],
) -> tuple[list[_NormalizedRow], list[dict[str, Any]]]:
    reasons: dict[str, set[str]] = collections.defaultdict(set)
    keys = {id(row): f"stage{row.stage}:{row.row_id}" for row in rows}
    for row in rows:
        reasons[keys[id(row)]].update(row.target_reasons)
    for reason, getter in (
        ("duplicate_input_target", lambda row: (row.input_target_sha256,)),
        ("duplicate_semantic_evidence", lambda row: row.semantic_sha256s),
    ):
        owners: dict[str, list[_NormalizedRow]] = collections.defaultdict(list)
        for row in rows:
            for value in getter(row):
                owners[value].append(row)
        for duplicates in owners.values():
            if len(duplicates) > 1:
                for row in duplicates:
                    reasons[keys[id(row)]].add(reason)
    retained = [row for row in rows if not reasons[keys[id(row)]]]
    report = [
        {"row_ref": key, "reasons": sorted(value), "phase": "post_assignment_target"}
        for key, value in sorted(reasons.items()) if value
    ]
    return retained, report


def _choose_cover(capacities: Mapping[str, int], required: int) -> tuple[str, ...]:
    if required == 0:
        return ()
    ordered = sorted(capacities.items(), key=lambda item: (item[1], item[0]))
    if sum(value for _, value in ordered) < required:
        raise Stage12694Error("requested_split_caps_unfilled")
    max_capacity = max(value for _, value in ordered)
    limit = required + max_capacity - 1
    states: dict[int, tuple[str, ...]] = {0: ()}
    for component, capacity in ordered:
        additions = {}
        for total, selected in states.items():
            new_total = min(limit, total + capacity)
            candidate = selected + (component,)
            current = states.get(new_total, additions.get(new_total))
            if current is None or candidate < current:
                additions[new_total] = candidate
        for total, selected in additions.items():
            current = states.get(total)
            if current is None or selected < current:
                states[total] = selected
    feasible = [(total, selected) for total, selected in states.items() if total >= required]
    if not feasible:
        raise Stage12694Error("requested_split_caps_unfilled")
    return min(feasible, key=lambda item: (item[0], item[1]))[1]


def _assign_components(capacities: Mapping[str, int], requested_rows: int) -> dict[str, str]:
    if requested_rows < 10 or requested_rows % 10:
        raise Stage12694Error("requested_rows_must_support_exact_80_10_10")
    caps = {
        "train": requested_rows * 8 // 10,
        "eval": requested_rows // 10,
        "strict_eval": requested_rows // 10,
    }
    candidates = []
    for order in itertools.permutations(SPLITS):
        available = dict(capacities)
        assignments: dict[str, str] = {}
        try:
            for split in order:
                selected = _choose_cover(available, caps[split])
                for component in selected:
                    assignments[component] = split
                    available.pop(component)
        except Stage12694Error:
            continue
        candidates.append(assignments)
    if not candidates:
        raise Stage12694Error("requested_split_caps_unfilled")
    return min(candidates, key=lambda value: tuple(sorted(value.items())))


def _zero_overlap(plan: Sequence[Mapping[str, Any]], rows_by_ref: Mapping[str, _NormalizedRow]) -> dict[str, int]:
    fields = {
        "component": lambda ref, row: (ref["global_component_id"],),
        "encoder_input": lambda ref, row: (row.input_sha256,),
        "input_target": lambda ref, row: (row.input_target_sha256,),
        "semantic": lambda ref, row: row.semantic_sha256s,
        "source": lambda ref, row: row.source_evidence,
        "candidate": lambda ref, row: row.candidate_evidence,
        "patch": lambda ref, row: row.patch_evidence,
        "atomic_file_blob": lambda ref, row: row.atomic_weak_evidence,
    }
    result: dict[str, int] = {}
    for name, getter in fields.items():
        owners: dict[str, set[str]] = collections.defaultdict(set)
        for ref in plan:
            row = rows_by_ref[ref["row_ref"]]
            for value in getter(ref, row):
                owners[value].add(ref["global_split"])
        result[name] = sum(len(splits) > 1 for splits in owners.values())
    if any(result.values()):
        raise Stage12694Error("global_cross_split_overlap_nonzero")
    return result


def build_global_split_core(
    inputs: Sequence[StageArtifacts], *, requested_rows: int
) -> dict[str, Any]:
    """Return an auditable in-memory plan; never read, mutate, or publish artifacts."""

    input_stages = {item.stage for item in inputs}
    if len(input_stages) != len(inputs) or input_stages != SUPPORTED_STAGES:
        raise Stage12694Error("complete_release_requires_exact_stage_set")
    for item in inputs:
        _validate_input(item)
    union, repositories, strong, weak = _build_components(inputs)
    rows, row_components = _normalize_rows(inputs, union, strong)
    conflicting_atomic_weak_tokens = _conflicting_atomic_weak_tokens(
        rows, row_components
    )
    direct_weak_report = _direct_weak_quarantine_report(
        rows, conflicting_atomic_weak_tokens
    )
    assignment_rows, pre_assignment_quarantine = _pre_assignment_quarantine(
        rows, row_components, conflicting_atomic_weak_tokens
    )
    capacities: collections.Counter[str] = collections.Counter()
    for row in assignment_rows:
        capacities[row_components[f"stage{row.stage}:{row.row_id}"]] += 1
    assignments = _assign_components(capacities, requested_rows)
    retained, target_quarantine = _post_assignment_target_quarantine(
        assignment_rows
    )
    quarantine = [
        {**entry, "phase": "pre_assignment_input_or_evidence"}
        for entry in pre_assignment_quarantine
    ] + target_quarantine

    conflicts = []
    source_splits: dict[str, set[str]] = collections.defaultdict(set)
    for row in rows:
        source_splits[row_components[f"stage{row.stage}:{row.row_id}"]].add(row.source_split)
    for component, splits in sorted(source_splits.items()):
        if len(splits) > 1:
            conflicts.append({"global_component_id": component, "source_splits": sorted(splits)})

    split_caps = {
        "train": requested_rows * 8 // 10,
        "eval": requested_rows // 10,
        "strict_eval": requested_rows // 10,
    }
    counts: collections.Counter[str] = collections.Counter()
    plan = []
    rows_by_ref: dict[str, _NormalizedRow] = {}
    for row in sorted(retained, key=lambda value: (value.stage, value.row_id)):
        row_ref = f"stage{row.stage}:{row.row_id}"
        component = row_components[row_ref]
        split = assignments.get(component)
        if split is None or counts[split] >= split_caps[split]:
            continue
        plan.append({
            "row_ref": row_ref,
            "source_split": row.source_split,
            "global_split": split,
            "global_component_id": component,
        })
        rows_by_ref[row_ref] = row
        counts[split] += 1
    deficits = {
        split: split_caps[split] - counts[split]
        for split in SPLITS
    }
    overlaps = _zero_overlap(plan, rows_by_ref)

    component_members: dict[str, list[str]] = collections.defaultdict(list)
    for node in sorted(repositories):
        component_members[union.find(node)].append(node)
    blockers = [
        "release_publication_not_implemented",
        "independent_review_required",
        "confidential_strict_artifacts_unavailable",
        "coordinated_confidential_strict_rebuild_required",
    ]
    if any(deficits.values()):
        blockers.append("post_assignment_target_quarantine_split_deficits")
    result = {
        "stage": STAGE,
        "decision": "BOUNDED_GLOBAL_SPLIT_CORE_ONLY_RELEASE_INELIGIBLE",
        "input_stages": [item.stage for item in sorted(inputs, key=lambda value: value.stage)],
        "input_commitments": {
            str(item.stage): {
                "schema_version": item.schema_version,
                "catalog_sha256": _records_commitment(item.catalog),
                "ledger_sha256": _records_commitment(item.ledger),
                "rows_sha256": _records_commitment(item.rows),
            }
            for item in sorted(inputs, key=lambda value: value.stage)
        },
        "origin_identity_contract": "canonical_recorded_origin_is_supplemental_never_sufficient",
        "weak_lineage_union_authority": "none",
        "direct_weak_row_quarantine": direct_weak_report,
        "global_components": [
            {
                "global_component_id": component,
                "repository_nodes": members,
                "canonical_origins_supplemental": sorted({
                    origin for node in members for origin in repositories[node]["origins"]
                }),
                "strong_immutable_evidence_count": len(set().union(*(strong[node] for node in members))),
                "object_or_file_evidence_count": len(set().union(*(weak[node] for node in members))),
            }
            for component, members in sorted(component_members.items())
        ],
        "cross_stage_split_conflicts": conflicts,
        "pre_target_quarantine_component_capacities": dict(sorted(capacities.items())),
        "requested_split_counts": split_caps,
        "planned_split_counts": {split: counts[split] for split in SPLITS},
        "post_assignment_target_quarantine_split_deficits": deficits,
        "component_assignments": dict(sorted(assignments.items())),
        "row_reference_plan": plan,
        "quarantined_rows": quarantine,
        "global_overlap_counts": overlaps,
        "zero_global_overlap_required": True,
        "source_artifacts_mutated": False,
        "publication_performed": False,
        "strict_core_eligible": False,
        "training_eligible_rows": 0,
        "release_eligible": False,
        "release_blockers": blockers,
        "authority": dict(AUTHORITY),
    }
    result["plan_commitment_sha256"] = stable(result)
    return result


def build_locked_global_split_core(
    inputs: Sequence[StageArtifacts], *, requested_rows: int
) -> dict[str, Any]:
    """Select exact geometry while preserving every authenticated source split."""

    input_stages = {item.stage for item in inputs}
    if len(input_stages) != len(inputs) or input_stages != SUPPORTED_STAGES:
        raise Stage12694Error("complete_release_requires_exact_stage_set")
    if requested_rows < 10 or requested_rows % 10:
        raise Stage12694Error("requested_rows_must_support_exact_80_10_10")
    for item in inputs:
        _validate_input(item)

    union, repositories, strong, weak = _build_components(inputs)
    repo_owners: dict[str, list[str]] = collections.defaultdict(list)
    for node in repositories:
        repo_owners[node.split(":", 1)[1]].append(node)
    for owners in repo_owners.values():
        first = sorted(owners)[0]
        for node in sorted(owners)[1:]:
            union.union(first, node)

    rows, row_components = _normalize_rows(inputs, union, strong)
    conflicting_atomic = _conflicting_atomic_weak_tokens(rows, row_components)
    assignment_rows, pre_quarantine = _pre_assignment_quarantine(
        rows, row_components, conflicting_atomic,
    )
    retained, target_quarantine = _post_assignment_target_quarantine(
        assignment_rows,
    )
    component_splits: dict[str, set[str]] = collections.defaultdict(set)
    for row in rows:
        ref = f"stage{row.stage}:{row.row_id}"
        component_splits[row_components[ref]].add(row.source_split)
    conflicts = [
        {"global_component_id": component, "source_splits": sorted(splits)}
        for component, splits in sorted(component_splits.items())
        if len(splits) != 1
    ]
    if conflicts:
        raise Stage12694Error("source_split_conflict")

    origin_components: dict[str, set[str]] = collections.defaultdict(set)
    for node, metadata in repositories.items():
        component = union.find(node)
        for origin in metadata["origins"]:
            origin_components[origin].add(component)
    if any(len(components) > 1 for components in origin_components.values()):
        raise Stage12694Error("ambiguous_repository_ancestry")

    caps = {
        "train": requested_rows * 8 // 10,
        "eval": requested_rows // 10,
        "strict_eval": requested_rows // 10,
    }
    by_split: dict[str, list[_NormalizedRow]] = collections.defaultdict(list)
    for row in retained:
        by_split[row.source_split].append(row)

    selected: list[_NormalizedRow] = []
    deficits: dict[str, int] = {}
    for split in SPLITS:
        ordered = sorted(
            by_split[split],
            key=lambda row: (row.stage, row.row_id),
        )
        anchors: dict[tuple[int, str], _NormalizedRow] = {}
        row_lookup = {
            (row.stage, row.row_id): row
            for row in ordered
        }
        source_lookup = {
            (item.stage, str(source["row_id"])): str(source["objective_family"])
            for item in inputs
            for source in item.rows
        }
        for row in ordered:
            anchors.setdefault(
                (row.stage, source_lookup[(row.stage, row.row_id)]), row,
            )
        mandatory = sorted(
            anchors.values(), key=lambda row: (row.stage, row.row_id),
        )
        if len(mandatory) > caps[split]:
            raise Stage12694Error("objective_anchor_capacity_exceeded")
        chosen_ids = {(row.stage, row.row_id) for row in mandatory}
        chosen = mandatory + [
            row for row in ordered
            if (row.stage, row.row_id) not in chosen_ids
        ][:caps[split] - len(mandatory)]
        selected.extend(chosen)
        deficits[split] = caps[split] - len(chosen)
    if any(deficits.values()):
        raise Stage12694Error("locked_split_geometry_unavailable")

    plan = []
    rows_by_ref: dict[str, _NormalizedRow] = {}
    for row in sorted(selected, key=lambda value: (value.stage, value.row_id)):
        ref = f"stage{row.stage}:{row.row_id}"
        component = row_components[ref]
        plan.append({
            "row_ref": ref,
            "source_split": row.source_split,
            "global_split": row.source_split,
            "global_component_id": component,
        })
        rows_by_ref[ref] = row
    overlaps = _zero_overlap(plan, rows_by_ref)
    quarantine = [
        {**entry, "phase": "pre_assignment_input_or_evidence"}
        for entry in pre_quarantine
    ] + target_quarantine
    return {
        "stage": STAGE,
        "input_stages": sorted(input_stages),
        "requested_split_counts": caps,
        "planned_split_counts": {
            split: sum(ref["global_split"] == split for ref in plan)
            for split in SPLITS
        },
        "post_assignment_target_quarantine_split_deficits": deficits,
        "row_reference_plan": plan,
        "quarantined_rows": quarantine,
        "global_overlap_counts": overlaps,
        "cross_stage_split_conflicts": conflicts,
        "source_split_assignments_preserved": all(
            ref["source_split"] == ref["global_split"] for ref in plan
        ),
        "authority": dict(AUTHORITY),
    }


def main() -> int:
    raise SystemExit("bounded_core_only:no_artifact_reads_no_publication_no_training")


if __name__ == "__main__":
    main()
