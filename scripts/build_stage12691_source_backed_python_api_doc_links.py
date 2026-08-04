#!/usr/bin/env python3
"""Build source-backed Python API completion and Sphinx doc-code-test rows."""

from __future__ import annotations

import argparse
import ast
import collections
import io
import json
import os
import re
import stat
import sys
import tokenize
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_stage12690_source_backed_symbol_api_test_links as stage12690

STAGE = "stage12691_source_backed_python_api_doc_links"
DEFAULT_SOURCE_ROOT = Path("/arxiv/repositories")
DEFAULT_OUT = ROOT / "runs/local/artifacts" / STAGE
DEFAULT_SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
MAX_REPOS = 601
MAX_ROWS = 300
MAX_ROWS_PER_REPO = 200
MAX_DOC_BYTES = 250_000
MAX_CANDIDATES = 4
MIN_CANDIDATES = 3
SIGNATURE_PARAMETER_MASK = "<MASKED_SIGNATURE_PARAMETER>"
KEYWORD_MASK = "<MASKED_KEYWORD_NAME>"
DOC_MASK = "<MASKED_SPHINX_REFERENCE>"
DOC_SUFFIXES = frozenset({".rst", ".md"})
DOC_ROLE_RE = re.compile(
    rb":(?P<role>func|class|meth):`(?P<label>~?)(?P<target>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+)`"
)
DOC_SECRET_RE = re.compile(
    rb"(?i)(?:password|passwd|api[_-]?key|access[_-]?token|private[_-]?key)\s*[:=]"
)
AUTHORITY = dict(stage12690.AUTHORITY)
PARSER_ADAPTER = {
    "adapter_id": "cpython_ast_stage12690_scope_plus_sphinx_explicit_role_v1",
    "language_family": "python",
    "parser": "stdlib_ast_and_explicit_sphinx_role_parser",
    "parser_version": sys.version.split()[0],
    "resolution": "Stage12690 scope-aware unique absolute import and repository-wide module index; explicit Sphinx role text without Sphinx domain resolution",
}


class Stage12691Error(RuntimeError):
    pass


@dataclass(frozen=True)
class PreparedRelease:
    rows: list[dict[str, Any]]
    proofs: list[dict[str, Any]]
    catalog: list[dict[str, Any]]
    public_payloads: dict[str, bytes]
    summary: dict[str, Any]
    counters: collections.Counter[str]


@dataclass(frozen=True)
class ApiExample:
    relation: stage12690.Relation
    masked_definition_signature: str
    original_definition_signature: str
    masked_call_text: str
    original_call_text: str
    target: str
    signature_parameter_start_byte: int
    signature_parameter_end_byte: int
    keyword_start_byte: int
    keyword_end_byte: int


@dataclass(frozen=True)
class DocBlob:
    mode: str
    oid: str
    size: int
    path: str
    data: bytes


@dataclass(frozen=True)
class DocExample:
    relation: stage12690.Relation
    doc: DocBlob
    role: str
    qualified_name: str
    reference_start_byte: int
    reference_end_byte: int
    target_start_byte: int
    target_end_byte: int
    doc_context: str


def stable(value: Any) -> str:
    return stage12690.stable(value)


def sha256_bytes(data: bytes) -> str:
    return stage12690.sha256_bytes(data)


def exact_text(data: bytes, start: int, end: int) -> str:
    if not 0 <= start < end <= len(data):
        raise Stage12691Error("invalid_exact_span")
    try:
        value = data[start:end].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Stage12691Error("exact_span_not_utf8") from exc
    if not value.strip() or "\x00" in value:
        raise Stage12691Error("empty_or_nul_exact_span")
    return value


def definition_node(parsed: stage12690.ParsedFile, relation: stage12690.Relation) -> ast.AST | None:
    matches = [
        node for node in parsed.tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and node.name == relation.source.symbol
        and stage12690.node_span(parsed.data, node)[0] == relation.source.span_start_byte
    ]
    return matches[0] if len(matches) == 1 else None


def definition_signature(
    parsed: stage12690.ParsedFile,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[str, int, int] | None:
    node_start, _ = stage12690.node_span(parsed.data, node)
    if not node.body:
        return None
    body_start, _ = stage12690.node_span(parsed.data, node.body[0])
    depth = 0
    saw_def = False
    try:
        tokens = tokenize.tokenize(io.BytesIO(parsed.data).readline)
        for token in tokens:
            if token.type in {tokenize.ENCODING, tokenize.ENDMARKER}:
                continue
            start = stage12690.byte_offset(parsed.data, token.start[0], token.start[1])
            end = stage12690.byte_offset(parsed.data, token.end[0], token.end[1])
            if end <= node_start:
                continue
            if start >= body_start:
                break
            if token.type == tokenize.NAME and token.string == "def":
                saw_def = True
            elif saw_def and token.type == tokenize.OP:
                if token.string in "([{":
                    depth += 1
                elif token.string in ")]}" and depth:
                    depth -= 1
                elif token.string == ":" and depth == 0:
                    return exact_text(parsed.data, node_start, start).strip(), node_start, start
    except (IndentationError, SyntaxError, tokenize.TokenError, ValueError):
        return None
    return None


def relation_call(parsed: stage12690.ParsedFile, relation: stage12690.Relation) -> ast.Call | None:
    matches = [
        node for node in ast.walk(parsed.tree)
        if isinstance(node, ast.Call)
        and stage12690.node_span(parsed.data, node) == (
            relation.call_expression_span_start_byte,
            relation.call_expression_span_end_byte,
        )
    ]
    return matches[0] if len(matches) == 1 else None


@dataclass(frozen=True)
class ParameterSpec:
    name: str
    keyword_capable: bool
    required: bool
    annotation: ast.AST | None


def parameter_specs(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[list[ParameterSpec], list[ParameterSpec]] | None:
    if node.args.vararg is not None or node.args.kwarg is not None:
        return None
    positional_nodes = [*node.args.posonlyargs, *node.args.args]
    default_start = len(positional_nodes) - len(node.args.defaults)
    positional = [
        ParameterSpec(
            argument.arg,
            index >= len(node.args.posonlyargs),
            index < default_start,
            argument.annotation,
        )
        for index, argument in enumerate(positional_nodes)
    ]
    keyword_only = [
        ParameterSpec(argument.arg, True, default is None, argument.annotation)
        for argument, default in zip(
            node.args.kwonlyargs, node.args.kw_defaults, strict=True
        )
    ]
    return positional, keyword_only


def literal_annotation_valid(value: ast.AST, annotation: ast.AST | None) -> bool:
    if not isinstance(annotation, ast.Name):
        return True
    expected = {
        "bool": bool,
        "bytes": bytes,
        "float": float,
        "int": int,
        "str": str,
    }.get(annotation.id)
    if expected is None:
        return True
    return isinstance(value, ast.Constant) and type(value.value) is expected


def keyword_name_span(data: bytes, keyword: ast.keyword) -> tuple[int, int] | None:
    if keyword.arg is None:
        return None
    start, end = stage12690.node_span(data, keyword)
    match = re.match(rb"(?P<name>[A-Za-z_]\w*)\s*=", data[start:end])
    if match is None or match.group("name").decode("ascii") != keyword.arg:
        return None
    return start + match.start("name"), start + match.end("name")


def signature_parameter_span(
    data: bytes,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    name: str,
) -> tuple[int, int] | None:
    matches = [
        argument for argument in [
            *node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs
        ]
        if argument.arg == name
    ]
    if len(matches) != 1:
        return None
    start, _ = stage12690.node_span(data, matches[0])
    end = start + len(name.encode("utf-8"))
    try:
        observed = data[start:end].decode("utf-8")
    except UnicodeDecodeError:
        return None
    return (start, end) if observed == name else None


def normalized_identifier_tokens(text: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKC", text)
    return tuple(
        unicodedata.normalize("NFKC", match.group(0))
        for match in re.finditer(r"[^\W\d]\w*", normalized, flags=re.UNICODE)
    )


def reconstruct_single_mask(masked: str, marker: str, target: str) -> str | None:
    if masked.count(marker) != 1:
        return None
    return masked.replace(marker, target, 1)


def api_examples(
    parsed_files: Iterable[stage12690.ParsedFile],
    relations: Iterable[stage12690.Relation],
) -> tuple[list[ApiExample], collections.Counter[str]]:
    files = {parsed.blob.path: parsed for parsed in parsed_files}
    counters: collections.Counter[str] = collections.Counter()
    examples: list[ApiExample] = []
    for relation in relations:
        source = files.get(relation.source.path)
        test = files.get(relation.test_path)
        if source is None or test is None:
            counters["relation_file_missing_rejected"] += 1
            continue
        node = definition_node(source, relation)
        call = relation_call(test, relation)
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or call is None:
            counters["nonfunction_or_missing_call_rejected"] += 1
            continue
        if not isinstance(call.func, ast.Name):
            counters["method_or_attribute_call_rejected"] += 1
            continue
        same_name_calls = [
            candidate for candidate in ast.walk(test.tree)
            if isinstance(candidate, ast.Call)
            and isinstance(candidate.func, ast.Name)
            and candidate.func.id == relation.local_name
        ]
        if len(same_name_calls) != 1:
            counters["conflicting_direct_calls_rejected"] += 1
            continue
        if any(isinstance(argument, ast.Starred) for argument in call.args):
            counters["star_argument_call_rejected"] += 1
            continue
        if any(keyword.arg is None for keyword in call.keywords):
            counters["dynamic_keyword_unpack_call_rejected"] += 1
            continue
        specs = parameter_specs(node)
        if specs is None:
            counters["variadic_definition_rejected"] += 1
            continue
        positional, keyword_only = specs
        if len(call.args) > len(positional):
            counters["positional_count_invalid_rejected"] += 1
            continue
        bound = {parameter.name for parameter in positional[:len(call.args)]}
        if any(
            not literal_annotation_valid(value, parameter.annotation)
            for value, parameter in zip(call.args, positional, strict=False)
        ):
            counters["statically_wrong_argument_type_rejected"] += 1
            continue
        keyword_capable = {
            parameter.name: parameter
            for parameter in [*positional, *keyword_only]
            if parameter.keyword_capable
        }
        keywords: dict[str, ast.keyword] = {}
        invalid = False
        for keyword in call.keywords:
            name = keyword.arg or ""
            if name not in keyword_capable:
                counters["unknown_keyword_rejected"] += 1
                invalid = True
                break
            if name in bound or name in keywords:
                counters["duplicate_or_conflicting_keyword_rejected"] += 1
                invalid = True
                break
            if not literal_annotation_valid(keyword.value, keyword_capable[name].annotation):
                counters["statically_wrong_argument_type_rejected"] += 1
                invalid = True
                break
            keywords[name] = keyword
        if invalid:
            continue
        fully_bound = bound | set(keywords)
        required = {parameter.name for parameter in [*positional, *keyword_only] if parameter.required}
        if not required.issubset(fully_bound):
            counters["required_binding_invalid_rejected"] += 1
            continue
        signature_evidence = definition_signature(source, node)
        if signature_evidence is None:
            counters["unsupported_definition_signature_rejected"] += 1
            continue
        original_signature, signature_start, signature_end = signature_evidence
        original_call = exact_text(
            test.data,
            relation.call_expression_span_start_byte,
            relation.call_expression_span_end_byte,
        )
        for name, keyword in sorted(keywords.items()):
            existing_bound = bound | (set(keywords) - {name})
            remaining = sorted(set(keyword_capable) - existing_bound)
            if remaining != [name]:
                counters["keyword_not_uniquely_inferable_rejected"] += 1
                continue
            span = keyword_name_span(test.data, keyword)
            if span is None:
                counters["keyword_identifier_span_rejected"] += 1
                continue
            start, end = span
            target = exact_text(test.data, start, end)
            if target != name:
                counters["keyword_identifier_identity_rejected"] += 1
                continue
            parameter_span = signature_parameter_span(source.data, node, name)
            if parameter_span is None:
                counters["signature_parameter_span_rejected"] += 1
                continue
            parameter_start, parameter_end = parameter_span
            masked_signature = stage12690.masked_fragment(
                source.data, signature_start, signature_end,
                [(parameter_start, parameter_end, SIGNATURE_PARAMETER_MASK)],
            )
            masked_call = stage12690.masked_fragment(
                test.data,
                relation.call_expression_span_start_byte,
                relation.call_expression_span_end_byte,
                [(start, end, KEYWORD_MASK)],
            )
            if (
                reconstruct_single_mask(
                    masked_signature, SIGNATURE_PARAMETER_MASK, target
                ) != original_signature
                or reconstruct_single_mask(masked_call, KEYWORD_MASK, target) != original_call
            ):
                counters["dual_mask_reconstruction_rejected"] += 1
                continue
            examples.append(ApiExample(
                relation, masked_signature, original_signature, masked_call, original_call,
                target, parameter_start, parameter_end, start, end,
            ))
            counters["api_keyword_name_examples"] += 1
    return examples, counters


def doc_path_allowed(blob: stage12690.GitBlob) -> bool:
    if blob.mode not in stage12690.SAFE_GIT_MODES or not 1 <= blob.size <= MAX_DOC_BYTES:
        return False
    path = blob.path
    if path.startswith("/") or "\\" in path or "\x00" in path or "//" in path or path.endswith("/"):
        return False
    parts = path.split("/")
    if any(not part or part in {".", ".."} or any(ord(char) < 32 or ord(char) == 127 for char in part) for part in parts):
        return False
    lowered = {part.lower() for part in parts}
    if lowered.intersection(stage12690.stage12687.EXCLUDED_PARTS):
        return False
    if stage12690.STUB_NAME_RE.search(path):
        return False
    return PurePosixPath(path).suffix.lower() in DOC_SUFFIXES


def load_doc_blobs(snapshot: stage12690.Snapshot) -> tuple[list[DocBlob], collections.Counter[str]]:
    counters: collections.Counter[str] = collections.Counter()
    raw_tree = stage12690.stage12687.git(
        snapshot.local_path, "ls-tree", "-r", "-z", "-l", snapshot.revision
    )
    blobs = [blob for blob in stage12690.parse_ls_tree(raw_tree) if doc_path_allowed(blob)]
    selected = sorted(blobs, key=lambda blob: stable([snapshot.repo_key, blob.path]))
    if not selected:
        return [], counters
    payloads = stage12690.stage12687.cat_blobs(snapshot.local_path, [stage12690.stage12687.Blob(blob.oid, blob.size, blob.path) for blob in selected])
    result: list[DocBlob] = []
    for blob in selected:
        data = payloads.get(blob.path)
        if data is None or len(data) != blob.size or not stage12690.stage12687.verify_blob_oid(blob.oid, data):
            counters["doc_blob_identity_rejected"] += 1
            continue
        if (stage12690.stage12687.contains_high_confidence_secret(data) or DOC_SECRET_RE.search(data) or stage12690.stage12687.generated_content(data)):
            counters["doc_secret_or_generated_rejected"] += 1
            continue
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            counters["doc_non_utf8_rejected"] += 1
            continue
        result.append(DocBlob(blob.mode, blob.oid, blob.size, blob.path, data))
    return result, counters


def relation_qualified_names(
    relation: stage12690.Relation,
    module_index: Mapping[str, tuple[str, ...]],
) -> tuple[str, ...]:
    modules = [name for name, paths in module_index.items() if paths == (relation.source.path,)]
    return tuple(sorted(f"{module}.{relation.source.symbol}" for module in modules))


def doc_examples(
    docs: Iterable[DocBlob],
    relations: Iterable[stage12690.Relation],
    module_index: Mapping[str, tuple[str, ...]],
) -> tuple[list[DocExample], collections.Counter[str]]:
    counters: collections.Counter[str] = collections.Counter()
    by_name: dict[str, list[stage12690.Relation]] = collections.defaultdict(list)
    for relation in relations:
        for name in relation_qualified_names(relation, module_index):
            by_name[name].append(relation)
    examples: list[DocExample] = []
    for doc in docs:
        for match in DOC_ROLE_RE.finditer(doc.data):
            role = match.group("role").decode("ascii")
            qualified_name = match.group("target").decode("ascii")
            if role == "meth":
                counters["sphinx_method_role_rejected"] += 1
                continue
            matching = list(by_name.get(qualified_name, []))
            definitions = {
                stage12690.definition_identity(relation.source)
                for relation in matching
            }
            if len(definitions) != 1:
                counters["missing_or_ambiguous_doc_test_relation_rejected"] += 1
                continue
            relation = sorted(matching, key=lambda value: stable(
                stage12690.relation_identity(value)
            ))[0]
            expected_kind = {
                "func": {"FunctionDef", "AsyncFunctionDef"},
                "class": {"ClassDef"},
            }[role]
            if relation.source.kind not in expected_kind:
                counters["sphinx_role_definition_kind_mismatch_rejected"] += 1
                continue
            reference_start, reference_end = match.span(0)
            target_start, target_end = match.span("target")
            target = exact_text(doc.data, target_start, target_end)
            context = stage12690.bounded_evidence(
                doc.data, target_start, target_end, mask=DOC_MASK
            )
            if target in context or DOC_MASK not in context:
                counters["doc_target_leak_or_mask_failure_rejected"] += 1
                continue
            examples.append(DocExample(
                relation, doc, role, qualified_name, reference_start, reference_end,
                target_start, target_end, context,
            ))
            counters["explicit_sphinx_doc_code_test_examples"] += 1
    return examples, counters


def candidate_identity(relation: stage12690.Relation) -> tuple[str, int, str, str]:
    return stage12690.relation_identity(relation)


def candidate_evidence(relation: stage12690.Relation) -> str:
    return (
        f"<definition path={json.dumps(relation.source.path)}>{relation.source.evidence}</definition>\n"
        f"<test>{relation.test_evidence}</test>"
    )


def deterministic_candidates(
    correct: stage12690.Relation,
    universe: Iterable[stage12690.Relation],
    seed: Any,
) -> tuple[list[stage12690.Relation], int] | None:
    unique: dict[tuple[str, int, str, str], stage12690.Relation] = {}
    correct_definition = stage12690.definition_identity(correct.source)
    for relation in universe:
        if stage12690.definition_identity(relation.source) == correct_definition:
            continue
        unique.setdefault(candidate_identity(relation), relation)
    ordered = sorted(unique.values(), key=lambda relation: stable([seed, candidate_identity(relation)]))
    negatives = ordered[: MAX_CANDIDATES - 1]
    if len(negatives) + 1 < MIN_CANDIDATES:
        return None
    position = int(stable(["stage12691_position", seed])[:16], 16) % (len(negatives) + 1)
    candidates = negatives[:]
    candidates.insert(position, correct)
    if len({sha256_bytes(candidate_evidence(value).encode()) for value in candidates}) != len(candidates):
        return None
    return candidates, position


def base_provenance(snapshot: stage12690.Snapshot, relation: stage12690.Relation) -> dict[str, Any]:
    value = stage12690.base_provenance(snapshot, relation)
    value.update({"source_stage": STAGE, "parser_adapter": dict(PARSER_ADAPTER)})
    return value


def make_row(
    snapshot: stage12690.Snapshot,
    objective: str,
    input_text: str,
    target: str,
    relation: stage12690.Relation,
    proof_extra: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    row_id = "stage12691_" + stable([
        snapshot.repo_key, snapshot.revision, objective,
        stage12690.relation_identity(relation), proof_extra,
    ])[:24]
    row = {
        "row_id": row_id,
        "split": snapshot.split,
        "language_family": "python",
        "objective_family": objective,
        "input_text": input_text,
        "target": {"decoder_text": target},
        "loss_mask": {"decoder_ce": True},
        "source_provenance": base_provenance(snapshot, relation),
        "authority": dict(AUTHORITY),
    }
    proof = {
        "row_id": row_id,
        "row_sha256": stable(row),
        "model_input_sha256": sha256_bytes(input_text.encode()),
        "split": snapshot.split,
        "objective_family": objective,
        "repository_key_sha256": snapshot.repo_key,
        "content_component_sha256": snapshot.component_key,
        "source_file_sha256": relation.source.file_sha256,
        "test_file_sha256": relation.test_file_sha256,
        "target_sha256": sha256_bytes(target.encode()),
        "stage12690_relation_verified": True,
        "repository_wide_module_ambiguity_checked": True,
        "target_mutation_input_invariant": True,
        "training_admitted": False,
        "strict_eval_admitted": False,
        "sealed_eval_admitted": False,
        **dict(proof_extra),
    }
    return row, proof


def build_rows(
    snapshot: stage12690.Snapshot,
    parsed: list[stage12690.ParsedFile],
    relations: list[stage12690.Relation],
    docs: list[DocBlob],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], collections.Counter[str]]:
    counters: collections.Counter[str] = collections.Counter()
    rows: list[dict[str, Any]] = []
    proofs: list[dict[str, Any]] = []
    api, api_counts = api_examples(parsed, relations)
    docs_linked, doc_counts = doc_examples(docs, relations, snapshot.module_path_index)
    counters.update(api_counts)
    counters.update(doc_counts)
    for example in api:
        input_text = (
            "Complete the uniquely inferable masked keyword name in this parser-resolved imported function call.\n"
            f"<definition_signature>{example.masked_definition_signature}</definition_signature>\n"
            f"<call>{example.masked_call_text}</call>"
        )
        normalized_target = unicodedata.normalize("NFKC", example.target)
        if normalized_target in normalized_identifier_tokens(input_text):
            counters["full_input_normalized_identifier_leak_rejected"] += 1
            continue
        row, proof = make_row(snapshot, "python_api_keyword_name_completion", input_text,
                              example.target, example.relation, {
            "signature_parameter_span_start_byte": example.signature_parameter_start_byte,
            "signature_parameter_span_end_byte": example.signature_parameter_end_byte,
            "keyword_span_start_byte": example.keyword_start_byte,
            "keyword_span_end_byte": example.keyword_end_byte,
            "exact_signature_parameter_span_verified": True,
            "exact_keyword_identifier_span_verified": True,
            "normalized_identifier_target_absent_from_full_input": True,
            "signature_reconstruction_verified": True,
            "call_reconstruction_verified": True,
            "signature_mask": SIGNATURE_PARAMETER_MASK,
            "keyword_mask": KEYWORD_MASK,
            "original_signature_sha256": sha256_bytes(example.original_definition_signature.encode()),
            "reconstructed_signature_sha256": sha256_bytes(
                reconstruct_single_mask(
                    example.masked_definition_signature, SIGNATURE_PARAMETER_MASK, example.target
                ).encode()
            ),
            "masked_signature_sha256": sha256_bytes(example.masked_definition_signature.encode()),
            "original_call_sha256": sha256_bytes(example.original_call_text.encode()),
            "reconstructed_call_sha256": sha256_bytes(
                reconstruct_single_mask(
                    example.masked_call_text, KEYWORD_MASK, example.target
                ).encode()
            ),
            "masked_call_sha256": sha256_bytes(example.masked_call_text.encode()),
            "static_call_binding_verified": True,
            "unique_remaining_keyword_parameter_verified": True,
            "candidate_count": 0,
            "correct_candidate_position": -1,
            "candidate_evidence_sha256s": [],
        })
        rows.append(row)
        proofs.append(proof)
        counters["api_keyword_name_rows"] += 1
    for example in docs_linked:
        selected = deterministic_candidates(
            example.relation, relations,
            [example.doc.path, example.reference_start_byte, example.qualified_name],
        )
        if selected is None:
            counters["doc_insufficient_or_indistinguishable_candidates"] += 1
            continue
        candidates, position = selected
        blocks = stage12690.candidate_blocks(candidates, candidate_evidence)
        input_text = (
            "Complete the masked absolute Sphinx role target using a syntactic repository module path, unique top-level definition, and test import/direct-call chain.\n"
            f"<documentation path={json.dumps(example.doc.path)}>{example.doc_context}</documentation>\n\n"
            f"{blocks}"
        )
        normalized_doc_target = unicodedata.normalize("NFKC", example.qualified_name)
        normalized_doc_input = unicodedata.normalize("NFKC", input_text)
        if normalized_doc_target in normalized_doc_input:
            counters["doc_full_input_normalized_fully_qualified_target_leak_rejected"] += 1
            continue
        row, proof = make_row(snapshot, "python_sphinx_doc_code_test_relationship",
                              input_text, example.qualified_name, example.relation, {
            "doc_path": example.doc.path,
            "doc_git_blob_oid": example.doc.oid,
            "doc_file_sha256": sha256_bytes(example.doc.data),
            "sphinx_role": example.role,
            "reference_span_start_byte": example.reference_start_byte,
            "reference_span_end_byte": example.reference_end_byte,
            "target_span_start_byte": example.target_start_byte,
            "target_span_end_byte": example.target_end_byte,
            "explicit_sphinx_role_verified": True,
            "same_definition_test_relation_verified": True,
            "normalized_fully_qualified_target_absent_from_full_input": True,
            "proof_contract": "absolute_sphinx_role_text_plus_syntactic_repository_module_path_plus_unique_top_level_definition_plus_test_import_direct_call_chain",
            "candidate_count": len(candidates),
            "correct_candidate_position": position,
            "candidate_evidence_sha256s": [sha256_bytes(candidate_evidence(value).encode()) for value in candidates],
        })
        row["source_provenance"].update({
            "doc_path": example.doc.path,
            "doc_git_blob_oid": example.doc.oid,
            "doc_file_sha256": sha256_bytes(example.doc.data),
            "proof_contract": "absolute_sphinx_role_text_plus_syntactic_repository_module_path_plus_unique_top_level_definition_plus_test_import_direct_call_chain",
            "sphinx_domain_resolution_claimed": False,
        })
        proof["row_sha256"] = stable(row)
        rows.append(row)
        proofs.append(proof)
        counters["doc_rows"] += 1
    return rows, proofs, counters


def source_catalog_entry(snapshot: stage12690.Snapshot) -> dict[str, Any]:
    value = stage12690.source_catalog_entry(snapshot)
    value["parser_adapter"] = dict(PARSER_ADAPTER)
    return value


def cross_split_overlap_count(records: Iterable[Mapping[str, Any]], values) -> int:
    return stage12690.cross_split_overlap_count(records, values)


def publication_generation_id(
    artifact_sha256s: Mapping[str, str],
    strict_eval_commitment_sha256: str,
) -> str:
    return stable([
        "stage12691_generation_v2_descriptor_safe_strict_bound",
        sorted(artifact_sha256s.items()),
        strict_eval_commitment_sha256,
    ])


def publish(
    output_dir: Path,
    summary_path: Path,
    rows: list[dict[str, Any]],
    proofs: list[dict[str, Any]],
    catalog: list[dict[str, Any]],
    counters: Mapping[str, int],
) -> dict[str, Any]:
    visible_rows = [row for row in rows if row["split"] != "strict_eval"]
    visible_proofs = [proof for proof in proofs if proof["split"] != "strict_eval"]
    visible_catalog = [entry for entry in catalog if entry["split"] != "strict_eval"]
    strict_rows = [row for row in rows if row["split"] == "strict_eval"]
    strict_proofs = [proof for proof in proofs if proof["split"] == "strict_eval"]
    strict_catalog = [entry for entry in catalog if entry["split"] == "strict_eval"]
    strict_commitment = stable({
        "contract": "stage12691_strict_eval_v2",
        "row_sha256s": sorted(stable(row) for row in strict_rows),
        "proof_sha256s": sorted(stable(proof) for proof in strict_proofs),
        "catalog_sha256s": sorted(stable(entry) for entry in strict_catalog),
    })
    def overlap_metrics(records):
        return {
            "cross_split_repository_overlap": cross_split_overlap_count(
                records, lambda value: [value["repository_key_sha256"]]
            ),
            "cross_split_component_overlap": cross_split_overlap_count(
                records, lambda value: [value["content_component_sha256"]]
            ),
            "cross_split_source_digest_overlap": cross_split_overlap_count(
                records, lambda value: [value["source_file_sha256"]]
            ),
            "cross_split_test_digest_overlap": cross_split_overlap_count(
                records, lambda value: [value["test_file_sha256"]]
            ),
            "cross_split_doc_file_digest_overlap": cross_split_overlap_count(
                records,
                lambda value: (
                    [value["doc_file_sha256"]]
                    if "doc_file_sha256" in value else []
                ),
            ),
            "cross_split_model_input_overlap": cross_split_overlap_count(
                records, lambda value: [value["model_input_sha256"]]
            ),
            "cross_split_candidate_evidence_overlap": cross_split_overlap_count(
                records, lambda value: value["candidate_evidence_sha256s"]
            ),
        }

    internal_overlaps = overlap_metrics(proofs)
    nonzero = {
        key: value for key, value in internal_overlaps.items() if value
    }
    if nonzero:
        raise Stage12691Error("cross_split_overlap_nonzero")
    public_overlaps = overlap_metrics(visible_proofs)
    encoded = {
        "api_doc_train_eval_manifest.jsonl": stage12690.jsonl_bytes(visible_rows),
        "train_eval_source_provenance_ledger.jsonl": stage12690.jsonl_bytes(visible_proofs),
        "train_eval_source_catalog.jsonl": stage12690.jsonl_bytes(visible_catalog),
    }
    encoded_sha256s = {
        name: sha256_bytes(data) for name, data in encoded.items()
    }
    generation_id = publication_generation_id(encoded_sha256s, strict_commitment)
    artifact_contract = {
        name: {
            "relative_path": f"private/{generation_id}/{name}",
            "sha256": encoded_sha256s[name],
        }
        for name in encoded
    }
    objective_counts = collections.Counter(
        proof["objective_family"] for proof in visible_proofs
    )
    split_counts = collections.Counter(row["split"] for row in visible_rows)
    position_counts = {
        objective: dict(sorted(collections.Counter(
            str(proof["correct_candidate_position"])
            for proof in visible_proofs if proof["objective_family"] == objective
        ).items()))
        for objective in sorted(objective_counts)
    }
    summary = {
        "stage": STAGE,
        "generation_id": generation_id,
        "generation_relative_path": f"private/{generation_id}",
        "artifact_schema_version": 2,
        "authoritative_summary_relative_path": f"private/{generation_id}/summary.json",
        "summary_mirror_is_authoritative": False,
        "decision": "SOURCE_BACKED_PYTHON_API_DOC_LINKS_MATERIALIZED_REVIEW_REQUIRED",
        "language_scope": ["python"],
        "multilanguage_api_claimed": False,
        "sphinx_domain_resolution_claimed": False,
        "doc_proof_contract": "absolute_sphinx_role_text_plus_syntactic_repository_module_path_plus_unique_top_level_definition_plus_test_import_direct_call_chain",
        "row_count": len(rows),
        "materialized_model_row_count": len(visible_rows),
        "reserved_unmaterialized_strict_row_count": len(strict_proofs),
        "strict_eval_commitment_sha256": strict_commitment,
        "strict_eval_plaintext_materialized": False,
        "split_counts": dict(sorted(split_counts.items())),
        "objective_counts": dict(sorted(objective_counts.items())),
        "candidate_position_counts": position_counts,
        "parser_adapter": dict(PARSER_ADAPTER),
        **public_overlaps,
        "artifact_contract": artifact_contract,
        "training_eligible_rows": 0,
        "release_blockers": [
            "independent_semantic_and_leakage_review_required",
            "tokenizer_bound_context_and_target_audit_required",
            "combined_knowledge_release_review_required",
            "unresolved_methods_and_attribute_calls_not_materialized",
            "multilanguage_api_not_materialized",
            "stage12691_trainer_adapter_not_materialized",
        ],
        "authority": dict(AUTHORITY),
    }
    encoded_summary = stage12690.json_bytes(summary)
    private_root = output_dir / "private"
    private_fd, private_identity = stage12690.open_private_root(output_dir)
    pending_name = f".pending-{generation_id}-{os.getpid()}"
    pending_fd: int | None = None
    try:
        try:
            os.stat(generation_id, dir_fd=private_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise Stage12691Error(f"immutable_generation_exists:{generation_id}")
        os.mkdir(pending_name, 0o700, dir_fd=private_fd)
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        pending_fd = os.open(pending_name, flags, dir_fd=private_fd)
        pending_identity = os.fstat(pending_fd)
        if not stat.S_ISDIR(pending_identity.st_mode):
            raise Stage12691Error("pending_generation_not_directory")
        identities = {
            name: stage12690.write_file_at(pending_fd, name, data, mode=0o400)
            for name, data in encoded.items()
        }
        identities["summary.json"] = stage12690.write_file_at(
            pending_fd, "summary.json", encoded_summary, mode=0o400
        )
        os.fchmod(pending_fd, 0o500)
        os.fsync(pending_fd)
        os.close(pending_fd)
        pending_fd = None
        stage12690.revalidate_private_root(private_root, private_fd, private_identity)
        stage12690.verify_generation_entry(
            private_fd, pending_name, pending_identity, identities, phase="pending"
        )
        stage12690.rename_noreplace(private_fd, pending_name, generation_id)
        stage12690.verify_generation_entry(
            private_fd, generation_id, pending_identity, identities, phase="published"
        )
        os.fsync(private_fd)
        stage12690.revalidate_private_root(private_root, private_fd, private_identity)
    finally:
        if pending_fd is not None:
            os.close(pending_fd)
        os.close(private_fd)
    stage12690.stage12687.write_json_atomic(summary_path, summary)
    stage12690.stage12687.write_json_atomic(output_dir / "summary.json", summary)
    return summary


def overlap_evidence_keys(proof: Mapping[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    for field in (
        "repository_key_sha256",
        "content_component_sha256",
        "source_file_sha256",
        "test_file_sha256",
        "doc_file_sha256",
        "model_input_sha256",
    ):
        value = proof.get(field)
        if value:
            values.append(f"{field}:{value}")
    values.extend(
        f"candidate_evidence_sha256s:{value}"
        for value in proof.get("candidate_evidence_sha256s", ())
        if value
    )
    return tuple(sorted(values))


def merge_overlap_evidence_components(
    records_by_component: Mapping[
        str,
        list[tuple[stage12690.Snapshot, dict[str, Any], dict[str, Any]]],
    ],
) -> tuple[
    dict[str, list[tuple[stage12690.Snapshot, dict[str, Any], dict[str, Any]]]],
    dict[str, str],
    dict[str, tuple[str, ...]],
]:
    parent = {component_key: component_key for component_key in records_by_component}

    def find(component_key: str) -> str:
        while parent[component_key] != component_key:
            parent[component_key] = parent[parent[component_key]]
            component_key = parent[component_key]
        return component_key

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root == right_root:
            return
        first, second = sorted((left_root, right_root))
        parent[second] = first

    evidence_owner: dict[str, str] = {}
    for component_key in sorted(records_by_component):
        for _, _, proof in records_by_component[component_key]:
            for evidence_key in overlap_evidence_keys(proof):
                owner = evidence_owner.setdefault(evidence_key, component_key)
                union(component_key, owner)

    component_to_group = {
        component_key: find(component_key)
        for component_key in sorted(records_by_component)
    }
    grouped: dict[
        str,
        list[tuple[stage12690.Snapshot, dict[str, Any], dict[str, Any]]],
    ] = collections.defaultdict(list)
    group_members: dict[str, list[str]] = collections.defaultdict(list)
    for component_key in sorted(records_by_component):
        group_key = component_to_group[component_key]
        grouped[group_key].extend(records_by_component[component_key])
        group_members[group_key].append(component_key)
    return (
        dict(sorted(grouped.items())),
        component_to_group,
        {
            group_key: tuple(members)
            for group_key, members in sorted(group_members.items())
        },
    )


def allocate_component_splits(
    capacities: Mapping[str, int],
    split_caps: Mapping[str, int],
) -> dict[str, str]:
    try:
        return stage12690.allocate_component_splits(capacities, split_caps)
    except stage12690.Stage12690Error as exc:
        raise Stage12691Error("reserved_split_caps_unfilled") from exc


def require_zero_final_overlap(proofs: list[dict[str, Any]]) -> None:
    fields = (
        ("repository_key_sha256", False),
        ("content_component_sha256", False),
        ("source_file_sha256", False),
        ("test_file_sha256", False),
        ("doc_file_sha256", False),
        ("model_input_sha256", False),
        ("candidate_evidence_sha256s", True),
    )
    overlaps = {}
    for field, repeated in fields:
        overlaps[field] = cross_split_overlap_count(
            proofs,
            lambda proof, field=field, repeated=repeated: (
                proof.get(field, ()) if repeated
                else [proof[field]] if proof.get(field) else []
            ),
        )
    if any(overlaps.values()):
        raise Stage12691Error("cross_split_overlap_nonzero")


def materialize(
    source_root: Path,
    *,
    max_repos: int,
    max_rows: int,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    collections.Counter[str],
    dict[str, Any],
]:
    split_caps = reserved_split_caps(max_rows)
    if not source_root.is_dir():
        raise Stage12691Error(f"source_root_missing:{source_root}")
    snapshots, counters = stage12690.discover_repositories(source_root, max_repos)
    if not snapshots:
        raise Stage12691Error("no_pinned_python_repositories")

    records_by_component: dict[
        str,
        list[tuple[stage12690.Snapshot, dict[str, Any], dict[str, Any]]],
    ] = collections.defaultdict(list)
    seen_inputs: set[str] = set()
    repo_counts: collections.Counter[str] = collections.Counter()
    for snapshot in sorted(
        snapshots, key=lambda value: (value.component_key, value.repo_key)
    ):
        snapshot.split = "capacity_estimation"
        parsed, parse_counts = stage12690.parse_snapshot(snapshot)
        counters.update(parse_counts)
        relations, relation_counts = stage12690.extract_relations(
            parsed, snapshot.module_path_index
        )
        counters.update(relation_counts)
        docs, doc_load_counts = load_doc_blobs(snapshot)
        counters.update(doc_load_counts)
        built_rows, built_proofs, build_counts = build_rows(
            snapshot, parsed, relations, docs
        )
        counters.update(build_counts)
        for row, proof in zip(built_rows, built_proofs, strict=True):
            if repo_counts[snapshot.repo_key] >= MAX_ROWS_PER_REPO:
                break
            if proof["model_input_sha256"] in seen_inputs:
                counters["duplicate_model_input_rejected"] += 1
                continue
            seen_inputs.add(proof["model_input_sha256"])
            records_by_component[snapshot.component_key].append(
                (snapshot, row, proof)
            )
            repo_counts[snapshot.repo_key] += 1

    grouped, component_to_group, _ = merge_overlap_evidence_components(
        records_by_component
    )
    capacities = {
        group_key: len(records)
        for group_key, records in grouped.items()
        if records
    }
    component_splits = allocate_component_splits(capacities, split_caps)

    for snapshot in snapshots:
        group_key = component_to_group.get(snapshot.component_key)
        if group_key in component_splits:
            snapshot.split = component_splits[group_key]

    rows: list[dict[str, Any]] = []
    proofs: list[dict[str, Any]] = []
    split_counts: collections.Counter[str] = collections.Counter()
    for group_key in sorted(component_splits):
        split = component_splits[group_key]
        for _, original_row, original_proof in grouped[group_key]:
            if split_counts[split] >= split_caps[split]:
                break
            row = {**original_row, "split": split}
            proof = {
                **original_proof,
                "split": split,
                "row_sha256": stable(row),
            }
            rows.append(row)
            proofs.append(proof)
            split_counts[split] += 1

    if any(split_counts[split] != cap for split, cap in split_caps.items()):
        raise Stage12691Error("reserved_split_caps_unfilled")
    require_zero_final_overlap(proofs)

    selected_groups = set(component_splits)
    catalog = [
        source_catalog_entry(snapshot)
        for snapshot in snapshots
        if component_to_group.get(snapshot.component_key) in selected_groups
    ]
    geometry = {
        "semantic_row_capacity": sum(capacities.values()),
        "repositories_with_semantic_rows": len({
            snapshot.repo_key
            for records in records_by_component.values()
            for snapshot, _, _ in records
        }),
        "source_component_count": len(records_by_component),
        "overlap_component_count": len(grouped),
        "selected_overlap_component_count": len(selected_groups),
        "selected_repository_count": len({
            snapshot.repo_key
            for snapshot in snapshots
            if component_to_group.get(snapshot.component_key) in selected_groups
        }),
        "split_caps": dict(split_caps),
        "assigned_component_capacity": dict(sorted(collections.Counter({
            split: sum(
                capacities[group_key]
                for group_key, assigned_split in component_splits.items()
                if assigned_split == split
            )
            for split in split_caps
        }).items())),
        "assigned_component_counts": dict(sorted(collections.Counter(
            component_splits.values()
        ).items())),
        "final_overlap_gate_passed": True,
    }
    return rows, proofs, catalog, counters, geometry


def _prepare_public_view(
    rows: list[dict[str, Any]],
    proofs: list[dict[str, Any]],
    catalog: list[dict[str, Any]],
) -> tuple[dict[str, bytes], dict[str, Any]]:
    visible_rows = [row for row in rows if row["split"] != "strict_eval"]
    visible_proofs = [proof for proof in proofs if proof["split"] != "strict_eval"]
    visible_catalog = [entry for entry in catalog if entry["split"] != "strict_eval"]
    strict_rows = [row for row in rows if row["split"] == "strict_eval"]
    strict_proofs = [proof for proof in proofs if proof["split"] == "strict_eval"]
    strict_catalog = [entry for entry in catalog if entry["split"] == "strict_eval"]
    strict_commitment = stable({
        "contract": "stage12691_strict_eval_v2",
        "row_sha256s": sorted(stable(row) for row in strict_rows),
        "proof_sha256s": sorted(stable(proof) for proof in strict_proofs),
        "catalog_sha256s": sorted(stable(entry) for entry in strict_catalog),
    })

    def overlap_metrics(records):
        return {
            "cross_split_repository_overlap": cross_split_overlap_count(
                records, lambda value: [value["repository_key_sha256"]]
            ),
            "cross_split_component_overlap": cross_split_overlap_count(
                records, lambda value: [value["content_component_sha256"]]
            ),
            "cross_split_source_digest_overlap": cross_split_overlap_count(
                records, lambda value: [value["source_file_sha256"]]
            ),
            "cross_split_test_digest_overlap": cross_split_overlap_count(
                records, lambda value: [value["test_file_sha256"]]
            ),
            "cross_split_doc_file_digest_overlap": cross_split_overlap_count(
                records,
                lambda value: (
                    [value["doc_file_sha256"]]
                    if "doc_file_sha256" in value else []
                ),
            ),
            "cross_split_model_input_overlap": cross_split_overlap_count(
                records, lambda value: [value["model_input_sha256"]]
            ),
            "cross_split_candidate_evidence_overlap": cross_split_overlap_count(
                records, lambda value: value["candidate_evidence_sha256s"]
            ),
        }

    if any(overlap_metrics(proofs).values()):
        raise Stage12691Error("cross_split_overlap_nonzero")
    public_overlaps = overlap_metrics(visible_proofs)
    payloads = {
        "api_doc_train_eval_manifest.jsonl": stage12690.jsonl_bytes(visible_rows),
        "train_eval_source_provenance_ledger.jsonl": stage12690.jsonl_bytes(
            visible_proofs
        ),
        "train_eval_source_catalog.jsonl": stage12690.jsonl_bytes(visible_catalog),
    }
    encoded_sha256s = {
        name: sha256_bytes(data) for name, data in payloads.items()
    }
    generation_id = publication_generation_id(encoded_sha256s, strict_commitment)
    objective_counts = collections.Counter(
        proof["objective_family"] for proof in visible_proofs
    )
    position_counts = {
        objective: dict(sorted(collections.Counter(
            str(proof["correct_candidate_position"])
            for proof in visible_proofs
            if proof["objective_family"] == objective
        ).items()))
        for objective in sorted(objective_counts)
    }
    summary = {
        "stage": STAGE,
        "generation_id": generation_id,
        "generation_relative_path": f"private/{generation_id}",
        "artifact_schema_version": 2,
        "authoritative_summary_relative_path": f"private/{generation_id}/summary.json",
        "summary_mirror_is_authoritative": False,
        "decision": "SOURCE_BACKED_PYTHON_API_DOC_LINKS_MATERIALIZED_REVIEW_REQUIRED",
        "language_scope": ["python"],
        "multilanguage_api_claimed": False,
        "sphinx_domain_resolution_claimed": False,
        "doc_proof_contract": "absolute_sphinx_role_text_plus_syntactic_repository_module_path_plus_unique_top_level_definition_plus_test_import_direct_call_chain",
        "row_count": len(rows),
        "materialized_model_row_count": len(visible_rows),
        "reserved_unmaterialized_strict_row_count": len(strict_proofs),
        "strict_eval_commitment_sha256": strict_commitment,
        "strict_eval_plaintext_materialized": False,
        "split_counts": dict(sorted(collections.Counter(
            row["split"] for row in visible_rows
        ).items())),
        "objective_counts": dict(sorted(objective_counts.items())),
        "candidate_position_counts": position_counts,
        "parser_adapter": dict(PARSER_ADAPTER),
        **public_overlaps,
        "artifact_contract": {
            name: {
                "relative_path": f"private/{generation_id}/{name}",
                "sha256": encoded_sha256s[name],
            }
            for name in payloads
        },
        "training_eligible_rows": 0,
        "release_blockers": [
            "independent_semantic_and_leakage_review_required",
            "tokenizer_bound_context_and_target_audit_required",
            "combined_knowledge_release_review_required",
            "unresolved_methods_and_attribute_calls_not_materialized",
            "multilanguage_api_not_materialized",
            "stage12691_trainer_adapter_not_materialized",
        ],
        "authority": dict(AUTHORITY),
    }
    return payloads, summary


def prepare_release(
    source_root: Path,
    *,
    max_repos: int,
    max_rows: int,
) -> PreparedRelease:
    rows, proofs, catalog, counters, _ = materialize(
        source_root, max_repos=max_repos, max_rows=max_rows
    )
    payloads, summary = _prepare_public_view(rows, proofs, catalog)
    return PreparedRelease(rows, proofs, catalog, payloads, summary, counters)


def build(
    source_root: Path,
    output_dir: Path,
    summary_path: Path,
    *,
    max_repos: int,
    max_rows: int,
) -> dict[str, Any]:
    rows, proofs, catalog, counters, _ = materialize(
        source_root, max_repos=max_repos, max_rows=max_rows
    )
    return publish(output_dir, summary_path, rows, proofs, catalog, counters)

def reserved_split_caps(max_rows: int) -> dict[str, int]:
    if max_rows < 10 or max_rows % 10 != 0:
        raise Stage12691Error("max_rows_must_be_multiple_of_10_and_at_least_10")
    train = max_rows * 8 // 10
    evaluation = max_rows // 10
    return {
        "train": train,
        "eval": evaluation,
        "strict_eval": max_rows - train - evaluation,
    }


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
    if args.max_repos <= 0 or args.max_rows < 10 or args.max_rows % 10 != 0:
        raise SystemExit(
            "max-repos must be positive and max-rows must be a multiple of 10 and at least 10"
        )
    print(json.dumps(build(
        args.source_root.resolve(), args.output_dir.resolve(), args.summary_path.resolve(),
        max_repos=args.max_repos, max_rows=args.max_rows,
    ), indent=2, sort_keys=True))
