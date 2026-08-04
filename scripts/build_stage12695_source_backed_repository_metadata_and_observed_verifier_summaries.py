#!/usr/bin/env python3
"""Fail-closed nonpublishing Stage12695 evidence and deduplication core."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
GEN12688 = ROOT / (
    "runs/local/artifacts/stage12688_source_backed_multilingual_knowledge_corpus/"
    "private/23cac72b1c420605413d0f77"
)
STAGE12688_CATALOG = GEN12688 / "train_eval_source_catalog.jsonl"
GEN12692 = ROOT / (
    "runs/local/artifacts/stage12692_source_backed_declarative_test_build_conventions/"
    "private/0251bea687f8f0fa4baff39661d3cf2e0f7c9e5e33521fb3587089c202f812be"
)
STAGE12692_ROWS = GEN12692 / "train_eval_rows.jsonl"
STAGE12537_DIR = ROOT / (
    "runs/local/artifacts/stage12537_command_output_verifier_observation_materialization_preflight"
)
STAGE12537_ROWS = STAGE12537_DIR / "real_command_output_verifier_observation_candidate_rows.jsonl"
STAGE12125_DIR = ROOT / "runs/local/artifacts/stage12125_exact_selected_test_refinement"
STAGE12125_RESULTS = STAGE12125_DIR / "exact_selected_test_refinement_results.jsonl"
STAGE12123_DIR = ROOT / "runs/local/artifacts/stage12123_verifier_ready_checkout_execution_smoke"
STAGE12123_RESULTS = STAGE12123_DIR / "execution_smoke_results.jsonl"

ACCEPTED_SHA256 = {
    "stage12688_catalog": "efdc8a4c3051e1621242fad34d82e0b2d5586c2373d438bcca2e12c5a51b98bb",
    "stage12692_rows": "477d5dc664726de10d5e2ce1c22f2f5a6cefd42f0ede01eb632ecf1760266894",
    "stage12537_rows": "425c0be57fbd3444f2a3972f1dd71a8270ec1d43153768e48f4e43d8133d8ac8",
    "stage12125_results": "f801622b8a62485ee14b0da6d5615764194f38cda1c71b3c061076ea84596161",
    "stage12123_results": "5b58429313d2feeed38cdc2bd85874f54c63b4298ab0549ce7b74fd01ca1a7ee",
    "stage12125_log_inventory": "c56dbc1e343469c380e838ef97eb0878ad88d753d6bdbc489df655054b95fdf5",
    "stage12123_log_inventory": "b64995a44da79b32e5269922da42ee363c532b76d9e447c0835d3bac8e1e2c47",
}
AUTHORITY = {
    "implementation_ready": False,
    "stage12595_allowed": False,
    "replay_trustworthy": False,
    "level_3_materialized": False,
    "training_admitted": False,
    "strict_eval_admitted": False,
    "sealed_eval_admitted": False,
}
GLOBAL_SPLIT_DEPENDENCY = {
    "stage": 12694,
    "contract": "global_knowledge_release_split_core",
    "required_state": "independent_review_passed_and_global_zero_overlap",
    "current_state": "blocked_security_and_schema_repair",
    "satisfied": False,
}
GIT_INPUT_FIELDS = (
    "classification_field", "representative_paths", "file_suffixes",
    "complete_layout_observations",
)
DECLARATION_INPUT_FIELDS = (
    "classification_field", "parser_observation_kind", "parser_observation"
)
VERIFIER_INPUT_FIELDS = ("command", "selected_scope", "stdout", "stderr", "timeout")
FORBIDDEN_INPUT_KEY_FRAGMENTS = ("_id", "oid", "hash", "target", "label", "answer")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_GIT_OID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_PYTEST_TERMINAL = re.compile(
    r"^(?P<body>(?:\d+ (?:passed|failed|error|errors|skipped|xfailed|xpassed)(?:, )?)+)"
    r" in [0-9.]+s$"
)
_PYTEST_COUNT = re.compile(r"(\d+) (passed|failed|error|errors|skipped|xfailed|xpassed)")
_CTEST_TERMINAL = re.compile(
    r"^(?P<percent>\d+)% tests passed, (?P<failed>\d+) tests failed out of (?P<total>\d+)$"
)
_CTEST_RESULT = re.compile(
    r"^\s*(?P<ordinal>\d+)/(?P<total>\d+) Test #(?P<test_id>\d+): .*?\s+"
    r"(?P<status>Passed|(?:\*\*\*)?Failed)\s+",
    re.M,
)
_DECLARATION_CLASSES = {
    ("declarative_test_build_scalar_completion", "cargo", "stdlib_tomllib_cargo",
     "exact_static_literal_scalar_completion_v1"): "cargo_toml_literal_scalar",
    ("declarative_test_build_scalar_completion", "python", "stdlib_tomllib_pyproject",
     "exact_static_literal_scalar_completion_v1"): "python_toml_literal_scalar",
    ("declarative_test_build_target_resolution", "npm", "stdlib_json_plus_byte_spans",
     "exact_literal_package_script_reference_v1"): "npm_literal_script_reference",
}


class Stage12695Error(ValueError):
    pass


class EvidenceUnavailable(Stage12695Error):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _stable(value: Any) -> str:
    return _sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii"))


def _canonical_bytes(value: Any, *, newline: bool = False) -> bytes:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    return payload + (b"\n" if newline else b"")


def _require_sha256(value: Any, reason: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise Stage12695Error(reason)
    return value


def _require_git_oid(value: Any, reason: str) -> str:
    if not isinstance(value, str) or not _GIT_OID.fullmatch(value):
        raise Stage12695Error(reason)
    return value


def _require_int(value: Any, reason: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise Stage12695Error(reason)
    return value


def _closed_authority(record: Mapping[str, Any]) -> None:
    authority = record.get("authority")
    if authority is not None and (
        not isinstance(authority, Mapping)
        or any(authority.get(key) is not False for key in AUTHORITY)
    ):
        raise Stage12695Error("source_authority_not_closed")
    for key in ("training_allowed", "admissible_for_training", "strict_eval_eligible"):
        if record.get(key) not in (None, False):
            raise Stage12695Error("source_authority_not_closed")


def _bind_raw_record(record: Mapping[str, Any], raw: bytes | None, reason: str) -> str:
    if raw is None:
        raise EvidenceUnavailable(reason)
    try:
        decoded = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise Stage12695Error("raw_record_not_json") from error
    if decoded != record:
        raise Stage12695Error("raw_record_binding_mismatch")
    return _sha256(raw)


def _git_blob_oid(data: bytes, width: int) -> str:
    payload = b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    if width == 40:
        return hashlib.sha1(payload).hexdigest()
    if width == 64:
        return hashlib.sha256(payload).hexdigest()
    raise Stage12695Error("unsupported_git_oid_width")


def _render_input(objective: str, fields: Mapping[str, Any], allowlist: Sequence[str]) -> str:
    if tuple(fields) != tuple(allowlist):
        raise Stage12695Error("encoder_input_allowlist_mismatch")
    for key in fields:
        if any(fragment in key.lower() for fragment in FORBIDDEN_INPUT_KEY_FRAGMENTS):
            raise Stage12695Error("forbidden_encoder_input_field")
    return "objective: " + objective + "\nevidence: " + json.dumps(
        fields, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )


def _candidate(
    objective: str, input_text: str, target: Mapping[str, Any], proof: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "record_type": "stage12695_nonpublishing_candidate_v2",
        "objective_family": objective,
        "input_text": input_text,
        "target": dict(target),
        "proof": dict(proof),
        "global_split_dependency": dict(GLOBAL_SPLIT_DEPENDENCY),
        "authority": dict(AUTHORITY),
    }


def _bucket(count: int, boundaries: Sequence[tuple[int, str]]) -> str:
    for upper, name in boundaries:
        if count <= upper:
            return name
    raise AssertionError("unbounded bucket table")


def _canonical_tree_objects(values: Sequence[Sequence[Any]]) -> list[list[Any]]:
    objects: list[list[Any]] = []
    for value in values:
        if not isinstance(value, (list, tuple)) or len(value) != 3:
            raise Stage12695Error("invalid_canonical_tree_object")
        object_type, oid, size = value
        if object_type not in {"blob", "commit"}:
            raise Stage12695Error("invalid_canonical_tree_object_type")
        oid = _require_git_oid(oid, "invalid_canonical_tree_object_oid")
        if object_type == "blob":
            size = _require_int(size, "invalid_canonical_blob_size")
        elif size is not None:
            raise Stage12695Error("commit_object_size_must_be_null")
        objects.append([object_type, oid, size])
    if objects != sorted(objects):
        raise Stage12695Error("noncanonical_tree_object_order")
    if not objects:
        raise Stage12695Error("canonical_tree_objects_empty")
    return objects


def _canonical_tree_layout(values: Sequence[Sequence[Any]]) -> tuple[list[list[str]], dict[str, Any]]:
    entries: list[list[str]] = []
    for value in values:
        if not isinstance(value, (list, tuple)) or len(value) != 5:
            raise Stage12695Error("invalid_canonical_tree_entry")
        tree_oid, mode, object_type, object_oid, path = value
        _require_git_oid(tree_oid, "invalid_canonical_tree_entry_tree_oid")
        _require_git_oid(object_oid, "invalid_canonical_tree_entry_object_oid")
        if mode not in {"100644", "100755", "120000", "160000", "40000", "040000"}:
            raise Stage12695Error("invalid_canonical_tree_entry_mode")
        if object_type not in {"blob", "tree", "commit"}:
            raise Stage12695Error("invalid_canonical_tree_entry_type")
        if (
            not isinstance(path, str)
            or not path
            or any(unicodedata.category(char).startswith("C") for char in path)
        ):
            raise Stage12695Error("invalid_canonical_tree_entry_path")
        parts = PurePosixPath(path).parts
        if (
            path.startswith("/") or path.endswith("/") or "//" in path
            or "\\" in path or "\x00" in path
            or any(part in {"", ".", ".."} for part in parts)
            or "/".join(parts) != path
        ):
            raise Stage12695Error("invalid_canonical_tree_entry_path")
        entries.append([tree_oid, mode, object_type, object_oid, path])
    if not entries or entries != sorted(entries):
        raise Stage12695Error("noncanonical_tree_entry_inventory")
    all_paths = sorted({entry[4] for entry in entries})
    all_parts = {path: PurePosixPath(path).parts for path in all_paths}
    test_directories = {"test", "tests", "testing", "spec", "specs"}
    root_doc_names = {"readme", "readme.md", "readme.rst", "readme.txt"}
    test_paths = [
        path for path, parts in all_parts.items()
        if any(part.lower() in test_directories for part in parts[:-1])
        or parts[-1].lower().startswith(("test_", "spec_"))
        or parts[-1].lower().endswith(
            ("_test.py", ".test.js", ".test.ts", ".spec.js", ".spec.ts")
        )
    ]
    documentation_paths = [
        path for path, parts in all_parts.items()
        if (len(parts) == 1 and parts[0].lower() in root_doc_names)
        or (len(parts) > 1 and parts[0].lower() in {"doc", "docs", "documentation"})
    ]
    top_level_examples: dict[str, str] = {}
    for path, parts in all_parts.items():
        if len(parts) > 1:
            top_level_examples.setdefault(parts[0].lower(), path)
    prioritized = (
        test_paths[:32] + documentation_paths[:32]
        + [top_level_examples[key] for key in sorted(top_level_examples)[:64]]
        + all_paths
    )
    representative_paths = []
    seen_paths = set()
    for path in prioritized:
        if path not in seen_paths:
            representative_paths.append(path)
            seen_paths.add(path)
        if len(representative_paths) == 512:
            break
    observations = {
        "has_top_level_directory": bool(top_level_examples),
        "has_multiple_top_level_directories": len(top_level_examples) > 1,
        "has_dedicated_top_level_tests": any(
            parts[0].lower() in test_directories for parts in all_parts.values()
        ),
        "has_other_test_path": bool(test_paths),
        "has_root_documentation": any(
            len(parts) == 1 and parts[0].lower() in root_doc_names
            for parts in all_parts.values()
        ),
        "has_documentation_directory": any(
            len(parts) > 1 and parts[0].lower() in {"doc", "docs", "documentation"}
            for parts in all_parts.values()
        ),
        "complete_authenticated_inventory_scanned": True,
    }
    suffixes = sorted({
        PurePosixPath(path).suffix.lower()
        for path in representative_paths if PurePosixPath(path).suffix
    })
    return entries, {
        "representative_paths": representative_paths,
        "file_suffixes": suffixes,
        "complete_layout_observations": observations,
    }


def build_git_metadata_candidates(
    record: Mapping[str, Any],
    *,
    canonical_tree_objects: Sequence[Sequence[Any]] | None = None,
    canonical_tree_entries: Sequence[Sequence[Any]] | None = None,
    canonical_root_commit_oids: Sequence[str] | None = None,
    raw_source_record_bytes: bytes | None = None,
) -> list[dict[str, Any]]:
    """Build labels only from supplied canonical object/root evidence."""
    if (
        canonical_tree_objects is None or canonical_tree_entries is None
        or canonical_root_commit_oids is None
    ):
        raise EvidenceUnavailable("canonical_git_evidence_unavailable")
    record_sha = _bind_raw_record(
        record, raw_source_record_bytes, "raw_git_source_record_unavailable"
    )
    required = {
        "repository_key_sha256", "content_component_sha256", "revision",
        "head_commit_git_oid", "git_tree_oid", "tree_git_oids",
        "root_commit_git_oids", "hard_grouping_key_sha256s",
        "all_tree_object_count", "tree_object_type_counts",
        "all_tree_object_identity_inventory_sha256",
    }
    if set(record) < required:
        raise Stage12695Error("stage12688_catalog_fields_missing")
    _closed_authority(record)
    repo_key = _require_sha256(record["repository_key_sha256"], "invalid_repository_key")
    component = _require_sha256(record["content_component_sha256"], "invalid_component")
    revision = _require_git_oid(record["revision"], "invalid_revision")
    head = _require_git_oid(record["head_commit_git_oid"], "invalid_head")
    tree = _require_git_oid(record["git_tree_oid"], "invalid_tree")
    if revision != head:
        raise Stage12695Error("revision_head_mismatch")

    objects = _canonical_tree_objects(canonical_tree_objects)
    layout_entries, layout_fields = _canonical_tree_layout(canonical_tree_entries)
    layout_object_ids = sorted(
        (entry[2], entry[3]) for entry in layout_entries
        if entry[2] in {"blob", "commit"}
    )
    component_object_ids = sorted(
        (object_type, oid) for object_type, oid, _size in objects
    )
    if layout_object_ids != component_object_ids:
        raise Stage12695Error("tree_layout_object_inventory_mismatch")
    roots = [_require_git_oid(value, "invalid_canonical_root") for value in canonical_root_commit_oids]
    if roots != sorted(set(roots)) or not roots:
        raise Stage12695Error("noncanonical_root_inventory")
    record_roots = record["root_commit_git_oids"]
    trees = record["tree_git_oids"]
    if (
        record_roots != roots or not isinstance(trees, list) or tree not in trees
        or trees != sorted(set(trees))
    ):
        raise Stage12695Error("catalog_lineage_inventory_mismatch")
    lineage = [f"head:{head}", *(f"root:{oid}" for oid in roots), *(f"tree:{oid}" for oid in trees)]
    expected_grouping = [_sha256(value.encode("utf-8")) for value in sorted(set(lineage))]
    if record["hard_grouping_key_sha256s"] != expected_grouping:
        raise Stage12695Error("hard_grouping_commitment_mismatch")

    object_count = len(objects)
    type_counts: dict[str, int] = {}
    for object_type, _oid, _size in objects:
        type_counts[object_type] = type_counts.get(object_type, 0) + 1
    type_counts = dict(sorted(type_counts.items()))
    if record["all_tree_object_count"] != object_count:
        raise Stage12695Error("catalog_tree_object_count_mismatch")
    if record["tree_object_type_counts"] != type_counts:
        raise Stage12695Error("catalog_tree_object_type_counts_mismatch")
    inventory_sha = _stable(objects)
    if record["all_tree_object_identity_inventory_sha256"] != inventory_sha:
        raise Stage12695Error("catalog_tree_object_inventory_mismatch")

    observations = layout_fields["complete_layout_observations"]
    repository_structure = (
        "multi_area" if observations["has_multiple_top_level_directories"]
        else "single_area" if observations["has_top_level_directory"]
        else "flat"
    )
    test_layout = (
        "dedicated_top_level" if observations["has_dedicated_top_level_tests"]
        else "colocated_or_nested" if observations["has_other_test_path"]
        else "none_observed"
    )
    documentation_layout = (
        "root_and_directory"
        if observations["has_root_documentation"]
        and observations["has_documentation_directory"]
        else "root_only" if observations["has_root_documentation"]
        else "dedicated_directory"
        if observations["has_documentation_directory"]
        else "none_observed"
    )
    labels = {
        "repository_structure": repository_structure,
        "test_layout_convention": test_layout,
        "documentation_layout_convention": documentation_layout,
    }
    candidates = []
    for field, label in labels.items():
        fields = {"classification_field": field, **layout_fields}
        input_text = _render_input(
            "exact_repository_metadata_classification", fields, GIT_INPUT_FIELDS
        )
        candidates.append(_candidate(
            "exact_repository_metadata_classification",
            input_text,
            {"classification_field": field, "class": label},
            {
                "source_stage": 12688,
                "source_record_sha256": record_sha,
                "repository_key_sha256": repo_key,
                "content_component_sha256": component,
                "canonical_tree_object_inventory_sha256": inventory_sha,
                "canonical_tree_entry_inventory_sha256": _stable(layout_entries),
                "canonical_tree_object_count": object_count,
                "canonical_tree_object_type_counts": type_counts,
                "canonical_root_commit_oids": roots,
                "input_sha256": _sha256(input_text.encode()),
                "proof_contract": (
                    "canonical_head_tree_and_catalog_bound_root_objects_v3"
                ),
            },
        ))
    return candidates


def _span(provenance: Mapping[str, Any], start_name: str, end_name: str, size: int) -> tuple[int, int]:
    start = _require_int(provenance.get(start_name), f"invalid_{start_name}")
    end = _require_int(provenance.get(end_name), f"invalid_{end_name}")
    if not 0 <= start < end <= size:
        raise Stage12695Error("source_span_out_of_bounds")
    return start, end


def _decode_slice(source: bytes, start: int, end: int, reason: str) -> str:
    try:
        return source[start:end].decode("utf-8")
    except UnicodeDecodeError as error:
        raise Stage12695Error(reason) from error


def build_parsed_declaration_metadata_candidate(
    row: Mapping[str, Any],
    *,
    canonical_source_bytes: bytes | None = None,
    raw_source_record_bytes: bytes | None = None,
) -> dict[str, Any]:
    """Revalidate selected literals and spans against exact canonical source bytes."""
    if canonical_source_bytes is None:
        raise EvidenceUnavailable("canonical_declaration_source_bytes_unavailable")
    record_sha = _bind_raw_record(
        row, raw_source_record_bytes, "raw_declaration_source_record_unavailable"
    )
    _closed_authority(row)
    provenance = row.get("source_provenance")
    target = row.get("target")
    if not isinstance(provenance, Mapping) or not isinstance(target, Mapping):
        raise Stage12695Error("declaration_record_shape_invalid")
    decoder_text = target.get("decoder_text")
    if not isinstance(decoder_text, str) or not decoder_text:
        raise Stage12695Error("declaration_target_missing")
    adapter = provenance.get("parser_adapter")
    if not isinstance(adapter, Mapping) or adapter.get("version") != "1":
        raise Stage12695Error("unsupported_parser_adapter")
    key = (
        row.get("objective_family"), row.get("ecosystem"), adapter.get("name"),
        provenance.get("proof_contract"),
    )
    declaration_class = _DECLARATION_CLASSES.get(key)
    if declaration_class is None:
        raise Stage12695Error("unsupported_parser_proof_combination")
    repository_key = _require_sha256(
        provenance.get("repository_key_sha256"), "invalid_declaration_repository_key",
    )
    content_component = _require_sha256(
        provenance.get("content_component_sha256"),
        "invalid_declaration_content_component",
    )
    revision = _require_git_oid(
        provenance.get("revision"), "invalid_declaration_revision",
    )
    source_path = provenance.get("source_path", provenance.get("package_path"))
    if (
        not isinstance(source_path, str) or not source_path
        or PurePosixPath(source_path).is_absolute()
        or str(PurePosixPath(source_path)) != source_path
        or any(part in {"", ".", ".."} for part in PurePosixPath(source_path).parts)
    ):
        raise Stage12695Error("invalid_declaration_source_path")
    file_sha = _require_sha256(provenance.get("source_file_sha256"), "invalid_source_file_sha")
    if _sha256(canonical_source_bytes) != file_sha:
        raise Stage12695Error("canonical_source_sha256_mismatch")
    blob_oid = _require_git_oid(provenance.get("source_git_blob_oid"), "invalid_source_blob_oid")
    if _git_blob_oid(canonical_source_bytes, len(blob_oid)) != blob_oid:
        raise Stage12695Error("canonical_source_git_blob_mismatch")
    size = len(canonical_source_bytes)
    is_reference = row.get("objective_family") == "declarative_test_build_target_resolution"

    if is_reference:
        ref_start, ref_end = _span(
            provenance, "reference_target_start_byte", "reference_target_end_byte", size
        )
        name_start, name_end = _span(
            provenance, "definition_name_start_byte", "definition_name_end_byte", size
        )
        command_start, command_end = _span(
            provenance, "definition_command_start_byte", "definition_command_end_byte", size
        )
        invocation_start, invocation_end = _span(
            provenance, "invocation_command_start_byte", "invocation_command_end_byte", size
        )
        if not (invocation_start <= ref_start < ref_end <= invocation_end):
            raise Stage12695Error("reference_not_inside_invocation_command")
        reference = _decode_slice(canonical_source_bytes, ref_start, ref_end, "reference_not_utf8")
        definition = _decode_slice(canonical_source_bytes, name_start, name_end, "definition_not_utf8")
        if reference != definition:
            raise Stage12695Error("selected_reference_definition_mismatch")
        match = re.fullmatch(r"candidate_(\d+)", decoder_text)
        spans = provenance.get("candidate_definition_spans")
        if match is None or not isinstance(spans, list):
            raise Stage12695Error("selected_candidate_binding_missing")
        index = int(match.group(1))
        canonical_spans = []
        for item in spans:
            if not isinstance(item, Mapping):
                raise Stage12695Error("candidate_span_shape_invalid")
            canonical_spans.append(_span(item, "start_byte", "end_byte", size))
        if index >= len(canonical_spans) or len(set(canonical_spans)) != len(canonical_spans):
            raise Stage12695Error("selected_candidate_index_invalid")
        selected_start, selected_end = canonical_spans[index]
        if not (
            selected_start <= name_start < name_end <= selected_end
            and selected_start <= command_start < command_end <= selected_end
        ):
            raise Stage12695Error("selected_definition_not_in_candidate_span")
        observations = [
            _decode_slice(canonical_source_bytes, invocation_start, invocation_end, "invocation_not_utf8"),
            *[
                _decode_slice(canonical_source_bytes, start, end, "candidate_not_utf8")
                for start, end in canonical_spans
            ],
        ]
        observation_kind = "literal_script_reference"
        literal_sha = _sha256(reference.encode())
    else:
        start, end = _span(provenance, "target_start_byte", "target_end_byte", size)
        member_start, member_end = _span(
            provenance, "member_start_byte", "member_end_byte", size
        )
        if not member_start <= start < end <= member_end:
            raise Stage12695Error("target_not_inside_member_span")
        selected = _decode_slice(canonical_source_bytes, start, end, "selected_literal_not_utf8")
        if selected != decoder_text:
            raise Stage12695Error("selected_literal_target_mismatch")
        masked = (
            canonical_source_bytes[member_start:start]
            + b"<SCALAR>"
            + canonical_source_bytes[end:member_end]
        )
        observations = [_decode_slice(masked, 0, len(masked), "member_not_utf8")]
        observation_kind = "literal_scalar"
        literal_sha = _sha256(canonical_source_bytes[start:end])

    fields = {
        "classification_field": "parsed_declaration_class",
        "parser_observation_kind": observation_kind,
        "parser_observation": observations,
    }
    input_text = _render_input(
        "exact_repository_metadata_classification", fields, DECLARATION_INPUT_FIELDS
    )
    return _candidate(
        "exact_repository_metadata_classification",
        input_text,
        {"classification_field": "parsed_declaration_class", "class": declaration_class},
        {
            "source_stage": 12692,
            "source_record_sha256": record_sha,
            "repository_key_sha256": repository_key,
            "content_component_sha256": content_component,
            "revision": revision,
            "source_path": source_path,
            "source_file_sha256": file_sha,
            "source_git_blob_oid": blob_oid,
            "selected_literal_sha256": literal_sha,
            "parser_adapter": dict(adapter),
            "input_sha256": _sha256(input_text.encode()),
            "proof_contract": "canonical_source_byte_literal_revalidation_v2",
        },
    )


def parse_observed_test_report(
    command: Sequence[str], stdout: str, stderr: str
) -> dict[str, Any]:
    if not command or not all(isinstance(item, str) and item for item in command):
        raise Stage12695Error("invalid_verifier_command")
    if not isinstance(stdout, str) or not isinstance(stderr, str):
        raise Stage12695Error("invalid_report_stream")
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if not lines:
        raise Stage12695Error("terminal_test_summary_missing")
    if "pytest" in command:
        match = _PYTEST_TERMINAL.fullmatch(lines[-1])
        if match is None:
            raise Stage12695Error("pytest_terminal_marker_missing")
        counts = {
            "passed": 0, "failed": 0, "errors": 0, "skipped": 0,
            "xfailed": 0, "xpassed": 0,
        }
        seen_names = set()
        for value, name in _PYTEST_COUNT.findall(match.group("body")):
            normalized = "errors" if name == "error" else name
            if normalized in seen_names:
                raise Stage12695Error("pytest_duplicate_count_class")
            seen_names.add(normalized)
            counts[normalized] = int(value)
        if sum(counts.values()) == 0:
            raise Stage12695Error("pytest_counts_empty")
        family = "pytest"
    elif command[0] == "ctest":
        indexes = [
            index for index, line in enumerate(lines) if _CTEST_TERMINAL.fullmatch(line)
        ]
        if len(indexes) != 1:
            raise Stage12695Error("ctest_terminal_marker_count_invalid")
        trailing = lines[indexes[0] + 1:]
        if trailing and (
            len(trailing) != 1 or not trailing[0].startswith("Total Test time (real) = ")
        ):
            raise Stage12695Error("ctest_noncanonical_trailing_output")
        match = _CTEST_TERMINAL.fullmatch(lines[indexes[0]])
        assert match is not None
        total = int(match.group("total"))
        failed = int(match.group("failed"))
        results = [item.groupdict() for item in _CTEST_RESULT.finditer(stdout)]
        ordinals = [int(item["ordinal"]) for item in results]
        test_ids = [item["test_id"] for item in results]
        declared_totals = [int(item["total"]) for item in results]
        if (
            total <= 0 or failed > total or len(results) != total
            or ordinals != list(range(1, total + 1))
            or len(set(ordinals)) != total
            or len(set(test_ids)) != total
            or any(value != total for value in declared_totals)
        ):
            raise Stage12695Error("ctest_result_identity_or_count_mismatch")
        observed_failed = sum(item["status"].endswith("Failed") for item in results)
        if observed_failed != failed:
            raise Stage12695Error("ctest_failure_count_mismatch")
        if int(match.group("percent")) != round(100 * (total - failed) / total):
            raise Stage12695Error("ctest_percent_mismatch")
        counts = {
            "passed": total - failed, "failed": failed, "errors": 0,
            "skipped": 0, "xfailed": 0, "xpassed": 0,
        }
        family = "ctest"
    else:
        raise Stage12695Error("unsupported_verifier_family")
    outcome = (
        "test_failure" if counts["failed"]
        else "environment_or_setup_failure" if counts["errors"]
        else "observed_pass"
    )
    return {"verifier_family": family, "counts": counts, "outcome_class": outcome}


def _canonical_checkout(value: Any) -> str:
    if not isinstance(value, str) or not value.startswith("/") or "\x00" in value:
        raise Stage12695Error("checkout_path_invalid")
    path = PurePosixPath(value)
    if str(path) != value or any(part in {".", ".."} for part in path.parts):
        raise Stage12695Error("checkout_path_noncanonical")
    return value


def _validate_selected_scope(command: Sequence[str], selected: Sequence[str]) -> None:
    if command[0] == "ctest":
        if len(selected) != 1 or "-R" not in command:
            raise Stage12695Error("ctest_selected_scope_not_bound")
        index = command.index("-R")
        if index + 1 >= len(command):
            raise Stage12695Error("ctest_selected_scope_not_bound")
        selected_id = selected[0]
        patterns = {"^" + re.escape(selected_id) + "$"}
        if re.fullmatch(r"[A-Za-z0-9_\/-]+", selected_id):
            patterns.add("^" + selected_id + "$")
        if command[index + 1] not in patterns:
            raise Stage12695Error("ctest_selected_scope_not_bound")
    elif "pytest" in command:
        selectors = [item for item in command if not item.startswith("-") and item.endswith(".py")]
        if len(selectors) != 1 or any(
            item != selectors[0] and not item.startswith(selectors[0] + "::")
            for item in selected
        ):
            raise Stage12695Error("pytest_selected_scope_not_bound")
    else:
        raise Stage12695Error("unsupported_verifier_family")


def build_observed_verifier_candidate(
    stage12537: Mapping[str, Any],
    result: Mapping[str, Any],
    report: Mapping[str, Any],
    commit_record: Mapping[str, Any],
    smoke_record: Mapping[str, Any],
    join_record: Mapping[str, Any] | None,
    *,
    raw_stage12537_bytes: bytes | None,
    raw_result_bytes: bytes | None,
    raw_report_bytes: bytes | None,
    raw_commit_bytes: bytes | None,
    raw_smoke_bytes: bytes | None,
    raw_join_bytes: bytes | None,
) -> dict[str, Any]:
    """Require a complete immutable Stage12537/12125/12123 join."""
    if join_record is None:
        raise EvidenceUnavailable("stage12537_command_observation_join_unavailable")
    raw_hashes = {
        "stage12537": _bind_raw_record(
            stage12537, raw_stage12537_bytes, "raw_stage12537_record_unavailable"
        ),
        "result": _bind_raw_record(result, raw_result_bytes, "raw_result_record_unavailable"),
        "report": _bind_raw_record(report, raw_report_bytes, "raw_report_unavailable"),
        "commit": _bind_raw_record(commit_record, raw_commit_bytes, "raw_commit_record_unavailable"),
        "smoke": _bind_raw_record(smoke_record, raw_smoke_bytes, "raw_smoke_record_unavailable"),
        "join": _bind_raw_record(join_record, raw_join_bytes, "raw_join_record_unavailable"),
    }
    for record in (stage12537, result):
        _closed_authority(record)
    if (
        stage12537.get("source_stage") != "stage12125_exact_selected_test_refinement"
        or stage12537.get("actual_verifier_command_output_observation_provenance") is not True
        or stage12537.get("hydratable_verifier_observation_candidate") is not True
        or stage12537.get("stage12534_constraint_preflight_passed") is not True
        or stage12537.get("source_lineage_checked") is not True
        or stage12537.get("controlled_fixture_like") is not False
        or stage12537.get("generic_selected_test_collapsed") is not False
    ):
        raise Stage12695Error("stage12537_guardrail_contract_missing")

    queue = result.get("queue_id")
    repo = result.get("repo_family")
    if not isinstance(queue, str) or not queue or not isinstance(repo, str) or not repo:
        raise Stage12695Error("result_identity_missing")
    for record in (report, commit_record, smoke_record, join_record):
        if record.get("queue_id") != queue or record.get("repo_family") != repo:
            raise Stage12695Error("queue_or_repository_join_mismatch")
    checkout = _canonical_checkout(result.get("checkout_path"))
    for value in (
        report.get("cwd"), commit_record.get("cwd"), smoke_record.get("checkout_path"),
        join_record.get("checkout_path"),
    ):
        if _canonical_checkout(value) != checkout:
            raise Stage12695Error("checkout_path_join_mismatch")
    commit = _require_git_oid(result.get("commit_sha"), "result_commit_missing")
    if smoke_record.get("commit_sha") != commit or join_record.get("commit_sha") != commit:
        raise Stage12695Error("commit_join_mismatch")
    if (
        commit_record.get("command") != ["git", "rev-parse", "HEAD"]
        or commit_record.get("stdout_tail") != commit + "\n"
        or commit_record.get("exit_code") != 0
        or commit_record.get("timeout") is not False
    ):
        raise Stage12695Error("commit_command_output_invalid")
    commit_attempts = [
        item for item in smoke_record.get("commands_attempted", [])
        if isinstance(item, Mapping) and item.get("command") == ["git", "rev-parse", "HEAD"]
    ]
    if (
        len(commit_attempts) != 1
        or commit_attempts[0].get("log_path") != commit_record.get("log_path")
        or commit_attempts[0].get("exit_code") != 0
        or commit_attempts[0].get("timeout") is not False
    ):
        raise Stage12695Error("smoke_commit_command_join_mismatch")

    command = report.get("command")
    selected = result.get("selected_test_ids")
    if (
        not isinstance(command, list) or not isinstance(selected, list) or not selected
        or not all(isinstance(item, str) and item for item in selected)
    ):
        raise Stage12695Error("command_or_selected_scope_missing")
    _validate_selected_scope(command, selected)
    if (
        result.get("command_attempted") != report.get("command_text")
        or result.get("command_log") != report.get("log_path")
        or join_record.get("command") != command
        or join_record.get("selected_test_ids") != selected
        or join_record.get("report_sha256") != raw_hashes["report"]
        or join_record.get("result_sha256") != raw_hashes["result"]
        or join_record.get("stage12537_record_sha256") != raw_hashes["stage12537"]
        or join_record.get("smoke_record_sha256") != raw_hashes["smoke"]
        or join_record.get("commit_record_sha256") != raw_hashes["commit"]
        or join_record.get("candidate_ref_hash") != stage12537.get("candidate_ref_hash")
    ):
        raise Stage12695Error("explicit_join_commitment_mismatch")

    if report.get("timeout") is not False or result.get("timeout") not in (None, False):
        raise Stage12695Error("timed_out_report_ineligible")
    process_exit = report.get("exit_code")
    session_exit = result.get("exit_code")
    if (
        isinstance(process_exit, bool) or not isinstance(process_exit, int)
        or isinstance(session_exit, bool) or not isinstance(session_exit, int)
        or process_exit != session_exit
        or join_record.get("process_exit_code") != process_exit
        or join_record.get("session_exit_code") != session_exit
        or join_record.get("timeout") is not False
    ):
        raise Stage12695Error("process_session_timeout_join_mismatch")
    expected_exit_class = "exit_zero" if process_exit == 0 else "exit_nonzero"
    if stage12537.get("verifier_exit_status_class") != expected_exit_class:
        raise Stage12695Error("stage12537_exit_class_mismatch")

    stdout = report.get("stdout_tail")
    stderr = report.get("stderr_tail")
    if not isinstance(stdout, str) or not isinstance(stderr, str):
        raise Stage12695Error("report_stream_missing")
    if (
        _sha256(stdout.encode()) != stage12537.get("verifier_stdout_hash")
        or _sha256(stderr.encode()) != stage12537.get("verifier_stderr_hash")
    ):
        raise Stage12695Error("stage12537_stream_hash_mismatch")
    parsed = parse_observed_test_report(command, stdout, stderr)
    if (process_exit == 0) != (parsed["outcome_class"] == "observed_pass"):
        raise Stage12695Error("terminal_summary_exit_mismatch")

    fields = {
        "command": command,
        "selected_scope": selected,
        "stdout": stdout,
        "stderr": stderr,
        "timeout": False,
    }
    input_text = _render_input(
        "compact_observed_verifier_summary", fields, VERIFIER_INPUT_FIELDS
    )
    return _candidate(
        "compact_observed_verifier_summary",
        input_text,
        {**parsed, "scope": "selected_tests_only", "process_exit_code": process_exit},
        {
            "source_stages": [12537, 12125, 12123],
            "raw_record_sha256s": raw_hashes,
            "immutable_commit_git_oid": commit,
            "checkout_path_sha256": _sha256(checkout.encode()),
            "scope": "selected_tests_only",
            "input_sha256": _sha256(input_text.encode()),
            "proof_contract": "complete_command_scope_checkout_commit_join_v2",
        },
    )


def deduplicate_candidates(
    candidates: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Collapse exact examples and quarantine any input carrying conflicting targets."""
    grouped: dict[str, list[tuple[str, str, Mapping[str, Any]]]] = {}
    for candidate in candidates:
        _closed_authority(candidate)
        input_text = candidate.get("input_text")
        target = candidate.get("target")
        if not isinstance(input_text, str) or not isinstance(target, Mapping):
            raise Stage12695Error("candidate_shape_invalid")
        input_sha = _sha256(input_text.encode())
        target_sha = _sha256(_canonical_bytes(target))
        model_sha = _sha256(_canonical_bytes([input_text, target]))
        grouped.setdefault(input_sha, []).append((target_sha, model_sha, candidate))
    retained = []
    conflicting_inputs = 0
    duplicate_rows = 0
    for input_sha in sorted(grouped):
        rows = grouped[input_sha]
        targets = {target_sha for target_sha, _model_sha, _candidate in rows}
        if len(targets) != 1:
            conflicting_inputs += 1
            duplicate_rows += len(rows)
            continue
        ordered = sorted(rows, key=lambda item: _canonical_bytes(item[2]))
        duplicate_rows += len(ordered) - 1
        target_sha, model_sha, candidate = ordered[0]
        copied = dict(candidate)
        proof = dict(copied.get("proof", {}))
        proof.update({
            "dedup_encoder_input_sha256": input_sha,
            "dedup_target_sha256": target_sha,
            "dedup_model_example_sha256": model_sha,
        })
        copied["proof"] = proof
        retained.append(copied)
    if len({row["proof"]["dedup_encoder_input_sha256"] for row in retained}) != len(retained):
        raise Stage12695Error("post_dedup_input_collision")
    return retained, {
        "raw_candidate_rows": len(candidates),
        "unique_candidate_rows": len(retained),
        "duplicate_or_conflicting_rows_quarantined": duplicate_rows,
        "conflicting_encoder_inputs": conflicting_inputs,
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open("rb") as handle:
        for number, raw in enumerate(handle, 1):
            if not raw.strip():
                raise Stage12695Error(f"blank_jsonl_line:{path.name}:{number}")
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise Stage12695Error(f"non_object_jsonl_record:{path.name}:{number}")
            records.append(value)
    return records


def _verify_file(path: Path, expected: str, reason: str) -> None:
    if _sha256(path.read_bytes()) != expected:
        raise Stage12695Error(reason)


def _log_inventory(path: Path) -> str:
    inventory = [
        [item.name, _sha256(item.read_bytes())] for item in sorted(path.glob("*.json"))
    ]
    return _sha256(json.dumps(inventory, separators=(",", ":")).encode())


def _legacy_projection_probe(
    catalog: Sequence[Mapping[str, Any]],
    declarations: Sequence[Mapping[str, Any]],
    provenance: Sequence[Mapping[str, Any]],
    results: Sequence[Mapping[str, Any]],
) -> tuple[int, int]:
    """Measure old projections only; none are returned as validated candidates."""
    inputs = []
    for record in catalog:
        labels = ("history_topology", "root_count_bucket", "tree_object_count_bucket")
        for field in labels:
            inputs.append(_render_input(
                "exact_repository_metadata_classification",
                {
                    "classification_field": field,
                    "root_count": len(record.get("root_commit_git_oids", [])),
                    "tree_object_count": record.get("all_tree_object_count"),
                    "tree_object_type_counts": record.get("tree_object_type_counts"),
                },
                ("classification_field", "root_count", "tree_object_count",
                 "tree_object_type_counts"),
            ))
    for row in declarations:
        source_input = row.get("input_text", "")
        lines = source_input.splitlines()
        is_reference = row.get("objective_family") == "declarative_test_build_target_resolution"
        observation = [
            line for line in lines
            if line.startswith(
                ("invocation: ", "candidates:", "candidate_") if is_reference
                else ("declaration_kind: ", "declaration: ")
            )
        ]
        inputs.append(_render_input(
            "exact_repository_metadata_classification",
            {
                "classification_field": "parsed_declaration_class",
                "parser_observation_kind": (
                    "literal_script_reference" if is_reference else "literal_scalar"
                ),
                "parser_observation": observation,
            },
            DECLARATION_INPUT_FIELDS,
        ))
    by_stdout = {
        row.get("verifier_stdout_hash"): row
        for row in provenance
        if row.get("source_stage") == "stage12125_exact_selected_test_refinement"
    }
    for result in results:
        report = json.loads((ROOT / result["command_log"]).read_bytes())
        if _sha256(report["stdout_tail"].encode()) not in by_stdout:
            continue
        inputs.append(_render_input(
            "compact_observed_verifier_summary",
            {
                "command": report["command"],
                "selected_scope": result["selected_test_ids"],
                "stdout": report["stdout_tail"],
                "stderr": report["stderr_tail"],
                "timeout": False,
            },
            VERIFIER_INPUT_FIELDS,
        ))
    return len(inputs), len({_sha256(value.encode()) for value in inputs})


def discover_source_counts() -> dict[str, Any]:
    """Audit exact local supply without publishing or claiming unavailable evidence."""
    _verify_file(STAGE12688_CATALOG, ACCEPTED_SHA256["stage12688_catalog"], "stage12688_catalog_drift")
    _verify_file(STAGE12692_ROWS, ACCEPTED_SHA256["stage12692_rows"], "stage12692_rows_drift")
    _verify_file(STAGE12537_ROWS, ACCEPTED_SHA256["stage12537_rows"], "stage12537_rows_drift")
    _verify_file(STAGE12125_RESULTS, ACCEPTED_SHA256["stage12125_results"], "stage12125_results_drift")
    _verify_file(STAGE12123_RESULTS, ACCEPTED_SHA256["stage12123_results"], "stage12123_results_drift")
    if _log_inventory(STAGE12125_DIR / "command_logs") != ACCEPTED_SHA256["stage12125_log_inventory"]:
        raise Stage12695Error("stage12125_log_inventory_drift")
    if _log_inventory(STAGE12123_DIR / "command_logs") != ACCEPTED_SHA256["stage12123_log_inventory"]:
        raise Stage12695Error("stage12123_log_inventory_drift")

    catalog = _read_jsonl(STAGE12688_CATALOG)
    declarations = _read_jsonl(STAGE12692_ROWS)
    provenance = _read_jsonl(STAGE12537_ROWS)
    results = _read_jsonl(STAGE12125_RESULTS)
    smoke = _read_jsonl(STAGE12123_RESULTS)
    raw, legacy_unique = _legacy_projection_probe(catalog, declarations, provenance, results)
    if raw != 3132 or legacy_unique != 1329:
        raise Stage12695Error("legacy_projection_probe_drift")
    validated, dedup = deduplicate_candidates([])
    assert validated == []
    return {
        "stage": 12695,
        "record_type": "stage12695_nonpublishing_fail_closed_inventory_v2",
        "source_counts": {
            "stage12688_catalog_records": len(catalog),
            "stage12692_parser_backed_rows": len(declarations),
            "stage12537_provenance_candidates": len(provenance),
            "stage12537_candidates_grounded_in_stage12125": 3,
            "stage12125_selected_test_results": len(results),
            "stage12123_smoke_results": len(smoke),
        },
        "legacy_unvalidated_projection_probe": {
            "raw_projection_rows": raw,
            "unique_encoder_inputs": legacy_unique,
            "duplicate_encoder_input_rows": raw - legacy_unique,
            "counted_as_validated_supply": False,
        },
        "quarantine": {
            "canonical_git_object_evidence_absent_projection_rows": len(catalog) * 3,
            "canonical_declaration_source_bytes_absent_rows": len(declarations),
            "stage12537_command_observation_join_absent_rows": 3,
            "total_quarantined_raw_projection_rows": raw,
        },
        "validated_unique_supply": {
            "git_metadata_classification_rows": 0,
            "parsed_declaration_classification_rows": 0,
            "observed_verifier_summary_rows": 0,
            "total_rows": 0,
        },
        "global_deduplication": dedup,
        "global_split_dependency": dict(GLOBAL_SPLIT_DEPENDENCY),
        "full_materialization_performed": False,
        "publication_performed": False,
        "authority": dict(AUTHORITY),
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory-only", action="store_true")
    args = parser.parse_args(argv)
    if not args.inventory_only:
        raise Stage12695Error("nonpublishing_core_requires_inventory_only")
    print(json.dumps(discover_source_counts(), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
