#!/usr/bin/env python3
"""Build source-backed Python symbol-reference and test-association rows."""

from __future__ import annotations

import argparse
import ast
import collections
import ctypes
import errno
import hashlib
import json
import os
import re
import stat
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_stage12687_source_backed_python_foundational_corpus as stage12687

STAGE = "stage12690_source_backed_symbol_api_test_links"
ARTIFACT_SCHEMA_VERSION = 3
DEFAULT_SOURCE_ROOT = Path("/arxiv/repositories")
DEFAULT_OUT = ROOT / "runs/local/artifacts" / STAGE
DEFAULT_SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
ACQUISITION_DATE = "2026-08-02"
PARSER_ADAPTER = {
    "adapter_id": "cpython_ast_import_call_unique_module_v1",
    "language_family": "python",
    "parser": "stdlib_ast",
    "parser_version": sys.version.split()[0],
    "supported_imports": "absolute ImportFrom with explicit names",
    "resolution": "syntactic unique repository module path and unique top-level definition",
}
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
MAX_REPOS = 601
MAX_ROWS = 13_000
MAX_FILES_PER_REPO = 400
MAX_FILE_BYTES = 250_000
MAX_ROWS_PER_REPO = 200
MIN_CANDIDATES = 3
MAX_CANDIDATES = 4
WINDOW_CHARS = 500
SAFE_GIT_MODES = frozenset({"100644", "100755"})
SOURCE_ROOT_PARTS = frozenset({"src", "lib", "python", "py"})
TEST_PARTS = frozenset({"test", "tests", "testing"})
TEST_NAME_RE = re.compile(r"(?:^test_.+|.+_test)\.py$")
STUB_NAME_RE = re.compile(r"(?:^|/)(?:stub|stubs|fixtures?|snapshots?)(?:/|$)", re.I)
MASK = "<MASKED_IMPORTED_SYMBOL>"


class Stage12690Error(RuntimeError):
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
class GitBlob:
    mode: str
    oid: str
    size: int
    path: str


@dataclass
class Snapshot:
    local_path: Path
    repo_key: str
    origin_url: str
    revision: str
    blobs: list[GitBlob]
    component_blobs: tuple[tuple[str, int], ...]
    lineage_keys: tuple[str, ...]
    module_path_index: dict[str, tuple[str, ...]]
    component_key: str = ""
    split: str = ""


@dataclass(frozen=True)
class ParsedFile:
    blob: GitBlob
    data: bytes
    text: str
    tree: ast.Module
    module_names: tuple[str, ...]
    is_test: bool


@dataclass(frozen=True)
class Definition:
    path: str
    blob_oid: str
    file_sha256: str
    symbol: str
    kind: str
    span_start_byte: int
    span_end_byte: int
    evidence: str


@dataclass(frozen=True)
class Relation:
    test_path: str
    test_blob_oid: str
    test_file_sha256: str
    source: Definition
    imported_symbol: str
    local_name: str
    import_span_start_byte: int
    import_span_end_byte: int
    import_alias_span_start_byte: int
    import_alias_span_end_byte: int
    call_span_start_byte: int
    call_span_end_byte: int
    call_expression_span_start_byte: int
    call_expression_span_end_byte: int
    import_scope_kind: str
    call_scope_kind: str
    test_evidence: str


@dataclass(frozen=True)
class ImportBinding:
    scope_id: int
    scope_kind: str
    node: ast.ImportFrom
    alias: ast.alias
    local_name: str


@dataclass
class ScopeRecord:
    scope_id: int
    kind: str
    parent_id: int | None
    imports: dict[str, list[ImportBinding]]
    bindings: set[str]
    calls: list[ast.Call]


def stable(value: Any) -> str:
    return stage12687.stable(value)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_ls_tree(data: bytes) -> list[GitBlob]:
    result: list[GitBlob] = []
    for record in data.split(b"\0"):
        if not record:
            continue
        try:
            header, raw_path = record.split(b"\t", 1)
            mode, object_type, oid, raw_size = header.decode("ascii").split()
            path = raw_path.decode("utf-8")
            size = int(raw_size)
        except (UnicodeDecodeError, ValueError) as exc:
            raise Stage12690Error("malformed_ls_tree_record") from exc
        if object_type == "blob":
            result.append(GitBlob(mode, oid, size, path))
    return result


def path_allowed(blob: GitBlob) -> bool:
    if blob.mode not in SAFE_GIT_MODES or not (1 <= blob.size <= MAX_FILE_BYTES):
        return False
    path = blob.path
    if path.startswith("/") or "\\" in path or "\x00" in path or not path.endswith(".py"):
        return False
    parts = PurePosixPath(path).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        return False
    lowered = {part.lower() for part in parts}
    if lowered.intersection(stage12687.EXCLUDED_PARTS) or path.endswith(".pyi"):
        return False
    if path.lower().endswith(stage12687.EXCLUDED_SUFFIXES) or STUB_NAME_RE.search(path):
        return False
    return True


def is_test_path(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return bool({part.lower() for part in parts[:-1]}.intersection(TEST_PARTS)) or bool(
        TEST_NAME_RE.fullmatch(parts[-1].lower())
    )


def module_names_for_path(path: str) -> tuple[str, ...]:
    parts = list(PurePosixPath(path).parts)
    if not parts or not parts[-1].endswith(".py"):
        return ()
    parts[-1] = parts[-1][:-3]
    if parts[-1] == "__init__":
        parts.pop()
    if not parts or any(not part.isidentifier() for part in parts):
        return ()
    candidates = [".".join(parts)]
    for index, part in enumerate(parts[:-1]):
        if part.lower() in SOURCE_ROOT_PARTS and index + 1 < len(parts):
            suffix = ".".join(parts[index + 1 :])
            if suffix:
                candidates.append(suffix)
    return tuple(dict.fromkeys(candidates))


def byte_offset(data: bytes, line: int, column: int) -> int:
    lines = data.splitlines(keepends=True)
    return stage12687.byte_position(lines, line, column)


def node_span(data: bytes, node: ast.AST) -> tuple[int, int]:
    try:
        return (
            byte_offset(data, int(node.lineno), int(node.col_offset)),
            byte_offset(data, int(node.end_lineno), int(node.end_col_offset)),
        )
    except (AttributeError, ValueError, stage12687.Stage12687Error) as exc:
        raise Stage12690Error("ast_node_without_exact_span") from exc


def bounded_evidence(data: bytes, start: int, end: int, *, mask: str | None = None) -> str:
    left = max(0, start - WINDOW_CHARS)
    right = min(len(data), end + WINDOW_CHARS)
    while left < start and data[left] & 0xC0 == 0x80:
        left += 1
    while right > end and right < len(data) and data[right] & 0xC0 == 0x80:
        right -= 1
    before = data[left:start].decode("utf-8")
    middle = mask if mask is not None else data[start:end].decode("utf-8")
    after = data[end:right].decode("utf-8")
    return (before + middle + after).strip()


def exact_evidence(data: bytes, start: int, end: int, *, max_bytes: int = 900) -> str:
    capped_end = min(end, start + max_bytes)
    while capped_end > start:
        try:
            return data[start:capped_end].decode("utf-8").strip()
        except UnicodeDecodeError:
            capped_end -= 1
    raise Stage12690Error("definition_evidence_decode_failure")


def top_level_definitions(parsed: ParsedFile) -> list[Definition]:
    definitions: list[Definition] = []
    names: collections.Counter[str] = collections.Counter()
    nodes: list[tuple[str, str, ast.AST]] = []
    for node in parsed.tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            nodes.append((node.name, type(node).__name__, node))
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    nodes.append((target.id, type(node).__name__, target))
    for name, _kind, _node in nodes:
        names[name] += 1
    for name, kind, node in nodes:
        if names[name] != 1:
            continue
        start, end = node_span(parsed.data, node)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            full_start, full_end = node_span(parsed.data, node)
            evidence = exact_evidence(parsed.data, full_start, full_end)
        else:
            evidence = exact_evidence(parsed.data, start, end)
        definitions.append(Definition(
            path=parsed.blob.path,
            blob_oid=parsed.blob.oid,
            file_sha256=sha256_bytes(parsed.data),
            symbol=name,
            kind=kind,
            span_start_byte=start,
            span_end_byte=end,
            evidence=evidence,
        ))
    return definitions


class ScopeAnalyzer(ast.NodeVisitor):
    def __init__(self, tree: ast.Module) -> None:
        self.records: dict[int, ScopeRecord] = {
            0: ScopeRecord(0, "module", None, collections.defaultdict(list), set(), [])
        }
        self.current = 0
        self.next_scope = 1
        self.rejections: collections.Counter[str] = collections.Counter()
        for statement in tree.body:
            self.visit(statement)

    def _enter(self, kind: str, body: Iterable[ast.AST], bindings: Iterable[str] = ()) -> None:
        parent = self.current
        scope_id = self.next_scope
        self.next_scope += 1
        self.records[scope_id] = ScopeRecord(
            scope_id, kind, parent, collections.defaultdict(list), set(bindings), []
        )
        self.current = scope_id
        for node in body:
            self.visit(node)
        self.current = parent

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.records[self.current].bindings.add(node.name)
        for value in [*node.decorator_list, *node.args.defaults, *node.args.kw_defaults]:
            if value is not None:
                self.visit(value)
        argument_names = [
            argument.arg
            for argument in [
                *node.args.posonlyargs,
                *node.args.args,
                *node.args.kwonlyargs,
                *([node.args.vararg] if node.args.vararg else []),
                *([node.args.kwarg] if node.args.kwarg else []),
            ]
        ]
        self._enter("function", node.body, argument_names)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        argument_names = [
            argument.arg
            for argument in [
                *node.args.posonlyargs,
                *node.args.args,
                *node.args.kwonlyargs,
                *([node.args.vararg] if node.args.vararg else []),
                *([node.args.kwarg] if node.args.kwarg else []),
            ]
        ]
        self._enter("lambda", [node.body], argument_names)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.records[self.current].bindings.add(node.name)
        for value in [*node.decorator_list, *node.bases, *node.keywords]:
            self.visit(value.value if isinstance(value, ast.keyword) else value)
        self._enter("class", node.body)

    def _visit_comprehension_scope(self, node: ast.AST, values: Iterable[ast.AST]) -> None:
        self._enter("comprehension", values)

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._visit_comprehension_scope(node, [*node.generators, node.elt])

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._visit_comprehension_scope(node, [*node.generators, node.elt])

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._visit_comprehension_scope(node, [*node.generators, node.key, node.value])

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._visit_comprehension_scope(node, [*node.generators, node.elt])

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.records[self.current].bindings.add(node.id)

    def visit_Global(self, node: ast.Global) -> None:
        self.records[self.current].bindings.update(node.names)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.records[self.current].bindings.update(node.names)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if isinstance(node.name, str):
            self.records[self.current].bindings.add(node.name)
        if node.type is not None:
            self.visit(node.type)
        for statement in node.body:
            self.visit(statement)

    def visit_MatchAs(self, node: ast.MatchAs) -> None:
        if isinstance(node.name, str):
            self.records[self.current].bindings.add(node.name)
        if node.pattern is not None:
            self.visit(node.pattern)

    def visit_MatchStar(self, node: ast.MatchStar) -> None:
        if isinstance(node.name, str):
            self.records[self.current].bindings.add(node.name)

    def visit_MatchMapping(self, node: ast.MatchMapping) -> None:
        if isinstance(node.rest, str):
            self.records[self.current].bindings.add(node.rest)
        for key in node.keys:
            self.visit(key)
        for pattern in node.patterns:
            self.visit(pattern)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.records[self.current].bindings.add(alias.asname or alias.name.split(".", 1)[0])

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level != 0 or not node.module:
            self.rejections["relative_or_empty_import_rejected"] += 1
            return
        if any(alias.name == "*" for alias in node.names):
            self.rejections["star_import_rejected"] += 1
            return
        record = self.records[self.current]
        for alias in node.names:
            local_name = alias.asname or alias.name
            record.imports[local_name].append(
                ImportBinding(record.scope_id, record.kind, node, alias, local_name)
            )

    def visit_Call(self, node: ast.Call) -> None:
        self.records[self.current].calls.append(node)
        self.generic_visit(node)

    def resolve_call(self, scope_id: int, local_name: str) -> ImportBinding | None:
        record = self.records[scope_id]
        local_imports = record.imports.get(local_name, [])
        if local_name in record.bindings:
            return None
        if len(local_imports) == 1:
            return local_imports[0]
        if len(local_imports) > 1:
            return None
        if scope_id == 0:
            return None
        cursor = record
        while cursor.parent_id is not None and cursor.parent_id != 0:
            cursor = self.records[cursor.parent_id]
            if local_name in cursor.bindings or cursor.imports.get(local_name):
                return None
        module_record = self.records[0]
        if local_name in module_record.bindings:
            return None
        module_imports = module_record.imports.get(local_name, [])
        return module_imports[0] if len(module_imports) == 1 else None


def masked_fragment(
    data: bytes,
    start: int,
    end: int,
    replacements: Iterable[tuple[int, int, str]],
) -> str:
    if not (0 <= start <= end <= len(data)):
        raise Stage12690Error("masked_fragment_outer_span_invalid")
    rendered = bytearray(data[start:end])
    for replacement_start, replacement_end, marker in sorted(replacements, reverse=True):
        if not (start <= replacement_start < replacement_end <= end):
            raise Stage12690Error("masked_fragment_inner_span_invalid")
        rendered[replacement_start - start : replacement_end - start] = marker.encode("ascii")
    try:
        return bytes(rendered).decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise Stage12690Error("masked_fragment_decode_failure") from exc


def identifier_is_visible(text: str, name: str) -> bool:
    return re.search(
        rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])",
        text,
    ) is not None


def repository_module_path_index(blobs: Iterable[GitBlob]) -> dict[str, tuple[str, ...]]:
    paths: dict[str, set[str]] = collections.defaultdict(set)
    for blob in blobs:
        for module_name in module_names_for_path(blob.path):
            paths[module_name].add(blob.path)
    return {name: tuple(sorted(values)) for name, values in sorted(paths.items())}


def extract_relations(
    files: Iterable[ParsedFile],
    module_path_index: Mapping[str, tuple[str, ...]],
) -> tuple[list[Relation], collections.Counter[str]]:
    files = list(files)
    counters: collections.Counter[str] = collections.Counter()
    parsed_by_path = {parsed.blob.path: parsed for parsed in files}
    definitions_by_file = {
        parsed.blob.path: {
            definition.symbol: definition for definition in top_level_definitions(parsed)
        }
        for parsed in files
    }

    relations: list[Relation] = []
    for test_file in (parsed for parsed in files if parsed.is_test):
        analyzer = ScopeAnalyzer(test_file.tree)
        counters.update(analyzer.rejections)
        selected_calls: dict[tuple[int, int, int, str], tuple[ImportBinding, ScopeRecord, ast.Call]] = {}
        for scope_id, scope in analyzer.records.items():
            for call in scope.calls:
                if not isinstance(call.func, ast.Name):
                    continue
                binding = analyzer.resolve_call(scope_id, call.func.id)
                if binding is None:
                    counters["unbound_ambiguous_or_rebound_call_rejected"] += 1
                    continue
                key = (
                    binding.scope_id,
                    int(binding.node.lineno),
                    int(binding.node.col_offset),
                    binding.local_name,
                )
                previous = selected_calls.get(key)
                if previous is None or (call.lineno, call.col_offset) < (
                    previous[2].lineno,
                    previous[2].col_offset,
                ):
                    selected_calls[key] = (binding, scope, call)

        for binding, call_scope, call in selected_calls.values():
            module_name = binding.node.module or ""
            universe_paths = module_path_index.get(module_name, ())
            if len(universe_paths) != 1:
                counters["ambiguous_or_missing_syntactic_module_rejected"] += 1
                continue
            source_file = parsed_by_path.get(universe_paths[0])
            if source_file is None:
                counters["unique_module_outside_parse_cap_rejected"] += 1
                continue
            definition = definitions_by_file[source_file.blob.path].get(binding.alias.name)
            if definition is None:
                counters["missing_or_ambiguous_definition_rejected"] += 1
                continue
            import_start, import_end = node_span(test_file.data, binding.node)
            alias_start, alias_end = node_span(test_file.data, binding.alias)
            call_start, call_end = node_span(test_file.data, call.func)
            expression_start, expression_end = node_span(test_file.data, call)
            try:
                encoded_local = test_file.data[call_start:call_end].decode("utf-8")
            except UnicodeDecodeError:
                counters["call_span_decode_rejected"] += 1
                continue
            if encoded_local != binding.local_name:
                counters["call_span_identity_rejected"] += 1
                continue
            import_evidence = masked_fragment(
                test_file.data,
                import_start,
                import_end,
                [(alias_start, alias_end, "<MASKED_IMPORT_ALIAS>")],
            )
            call_evidence = masked_fragment(
                test_file.data,
                expression_start,
                expression_end,
                [(call_start, call_end, "<MASKED_CALL_NAME>")],
            )
            test_evidence = (
                f"<import_statement>{import_evidence}</import_statement>\n"
                f"<call_expression>{call_evidence}</call_expression>"
            )
            if identifier_is_visible(test_evidence, binding.alias.name) or identifier_is_visible(
                test_evidence, binding.local_name
            ):
                counters["masked_symbol_or_alias_still_visible_rejected"] += 1
                continue
            relations.append(Relation(
                test_path=test_file.blob.path,
                test_blob_oid=test_file.blob.oid,
                test_file_sha256=sha256_bytes(test_file.data),
                source=definition,
                imported_symbol=binding.alias.name,
                local_name=binding.local_name,
                import_span_start_byte=import_start,
                import_span_end_byte=import_end,
                import_alias_span_start_byte=alias_start,
                import_alias_span_end_byte=alias_end,
                call_span_start_byte=call_start,
                call_span_end_byte=call_end,
                call_expression_span_start_byte=expression_start,
                call_expression_span_end_byte=expression_end,
                import_scope_kind=binding.scope_kind,
                call_scope_kind=call_scope.kind,
                test_evidence=test_evidence,
            ))
            counters["ast_scope_resolved_syntactic_relations"] += 1
    relations.sort(key=lambda relation: stable([
        relation.test_path,
        relation.call_span_start_byte,
        relation.source.path,
        relation.source.symbol,
    ]))
    return relations, counters


def deterministic_candidates(
    correct: Any,
    negatives: Iterable[Any],
    *,
    identity,
    seed: Any,
    limit: int = MAX_CANDIDATES,
) -> tuple[list[Any], int] | None:
    correct_key = identity(correct)
    unique: dict[Any, Any] = {}
    for candidate in negatives:
        key = identity(candidate)
        if key != correct_key:
            unique.setdefault(key, candidate)
    ordered_negatives = sorted(unique.values(), key=lambda value: stable([seed, identity(value)]))
    selected = ordered_negatives[: max(0, limit - 1)]
    if len(selected) + 1 < MIN_CANDIDATES:
        return None
    position = int(stable(["candidate_position", seed])[:16], 16) % (len(selected) + 1)
    candidates = selected[:]
    candidates.insert(position, correct)
    return candidates, position


def relation_identity(relation: Relation) -> tuple[str, int, str, str]:
    return (relation.test_path, relation.call_span_start_byte, relation.source.path, relation.source.symbol)


def definition_identity(definition: Definition) -> tuple[str, int, str]:
    return (definition.path, definition.span_start_byte, definition.symbol)


def candidate_blocks(candidates: list[Any], render) -> str:
    return "\n\n".join(f"<candidate_{index}>\n{render(value)}\n</candidate>" for index, value in enumerate(candidates))


def base_provenance(snapshot: Snapshot, relation: Relation) -> dict[str, Any]:
    return {
        "source_stage": STAGE,
        "origin_url": snapshot.origin_url,
        "revision": snapshot.revision,
        "repository_key_sha256": snapshot.repo_key,
        "content_component_sha256": snapshot.component_key,
        "parser_adapter": dict(PARSER_ADAPTER),
        "test_path": relation.test_path,
        "test_git_blob_oid": relation.test_blob_oid,
        "test_file_sha256": relation.test_file_sha256,
        "test_import_span_start_byte": relation.import_span_start_byte,
        "test_import_span_end_byte": relation.import_span_end_byte,
        "test_import_alias_span_start_byte": relation.import_alias_span_start_byte,
        "test_import_alias_span_end_byte": relation.import_alias_span_end_byte,
        "test_call_span_start_byte": relation.call_span_start_byte,
        "test_call_span_end_byte": relation.call_span_end_byte,
        "test_call_expression_span_start_byte": relation.call_expression_span_start_byte,
        "test_call_expression_span_end_byte": relation.call_expression_span_end_byte,
        "import_scope_kind": relation.import_scope_kind,
        "call_scope_kind": relation.call_scope_kind,
        "source_path": relation.source.path,
        "source_git_blob_oid": relation.source.blob_oid,
        "source_file_sha256": relation.source.file_sha256,
        "source_definition_span_start_byte": relation.source.span_start_byte,
        "source_definition_span_end_byte": relation.source.span_end_byte,
        "source_definition_kind": relation.source.kind,
        "proof_contract": "absolute_import_scope_aware_syntactic_repository_module_unique_definition_direct_name_call_v2",
        "acquisition_date": ACQUISITION_DATE,
    }


def make_row(
    snapshot: Snapshot,
    objective: str,
    input_text: str,
    target: str,
    relation: Relation,
    candidates: list[Any],
    correct_position: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    evidence_key = [
        snapshot.repo_key, snapshot.revision, objective, relation_identity(relation),
        [definition_identity(value) if isinstance(value, Definition) else relation_identity(value) for value in candidates],
    ]
    row_id = "stage12690_" + stable(evidence_key)[:24]
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
        "model_input_sha256": sha256_bytes(input_text.encode("utf-8")),
        "split": snapshot.split,
        "objective_family": objective,
        "repository_key_sha256": snapshot.repo_key,
        "content_component_sha256": snapshot.component_key,
        "correct_candidate_position": correct_position,
        "candidate_count": len(candidates),
        "candidate_evidence_sha256s": [sha256_bytes(
            (value.evidence if isinstance(value, Definition) else value.test_evidence).encode("utf-8")
        ) for value in candidates],
        "candidate_source_definition_keys": [
            stable(definition_identity(value if isinstance(value, Definition) else value.source))
            for value in candidates
        ],
        "correct_source_definition_key": stable(definition_identity(relation.source)),
        "ast_import_resolved": True,
        "syntactic_repository_module_resolution_verified": True,
        "unique_definition_verified": True,
        "direct_call_verified": True,
        "candidate_evidence_distinguishable": True,
        "target_mutation_input_invariant": True,
        "training_admitted": False,
        "strict_eval_admitted": False,
        "sealed_eval_admitted": False,
    }
    return row, proof


def build_relation_rows(
    snapshot: Snapshot,
    relations: list[Relation],
    definitions: list[Definition],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], collections.Counter[str]]:
    rows: list[dict[str, Any]] = []
    proofs: list[dict[str, Any]] = []
    counters: collections.Counter[str] = collections.Counter()
    for relation in relations:
        definition_candidates = deterministic_candidates(
            relation.source,
            (definition for definition in definitions if definition.evidence != relation.source.evidence),
            identity=definition_identity,
            seed=["symbol_reference", relation_identity(relation)],
        )
        if definition_candidates is None:
            counters["symbol_reference_insufficient_candidates"] += 1
        else:
            candidates, position = definition_candidates
            evidence_hashes = {sha256_bytes(candidate.evidence.encode("utf-8")) for candidate in candidates}
            if len(evidence_hashes) != len(candidates):
                counters["symbol_reference_indistinguishable_candidates"] += 1
            else:
                test_context = relation.test_evidence
                input_text = (
                    "Select the source definition resolved by the imported direct call.\n"
                    f"<test_source>\n{test_context}\n</test_source>\n\n"
                    + candidate_blocks(candidates, lambda value: f"path: {value.path}\n{value.evidence}")
                )
                row, proof = make_row(
                    snapshot, "python_symbol_reference_prediction", input_text,
                    f"candidate_{position}", relation, candidates, position,
                )
                rows.append(row)
                proofs.append(proof)
                counters["symbol_reference_rows"] += 1

        test_candidates = deterministic_candidates(
            relation,
            (other for other in relations if definition_identity(other.source) != definition_identity(relation.source)),
            identity=relation_identity,
            seed=["test_association", relation.source.path, relation.source.symbol, relation_identity(relation)],
        )
        if test_candidates is None:
            counters["test_association_insufficient_candidates"] += 1
        else:
            candidates, position = test_candidates
            evidence_hashes = {sha256_bytes(candidate.test_evidence.encode("utf-8")) for candidate in candidates}
            if len(evidence_hashes) != len(candidates):
                counters["test_association_indistinguishable_candidates"] += 1
            else:
                input_text = (
                    "Select the test source with a parser-resolved import and direct call to this definition.\n"
                    f"<source_definition path={json.dumps(relation.source.path)}>\n"
                    f"{relation.source.evidence}\n</source_definition>\n\n"
                    + candidate_blocks(candidates, lambda value: value.test_evidence)
                )
                row, proof = make_row(
                    snapshot, "python_test_file_association", input_text,
                    f"candidate_{position}", relation, candidates, position,
                )
                rows.append(row)
                proofs.append(proof)
                counters["test_association_rows"] += 1
    return rows, proofs, counters


def discover_repositories(source_root: Path, max_repos: int) -> tuple[list[Snapshot], collections.Counter[str]]:
    snapshots: list[Snapshot] = []
    counters: collections.Counter[str] = collections.Counter()
    for repo in sorted((path for path in source_root.iterdir() if path.is_dir()), key=lambda path: path.name):
        if len(snapshots) >= max_repos:
            break
        counters["repository_directories_seen"] += 1
        if not (repo / ".git").exists():
            counters["without_git"] += 1
            continue
        try:
            revision = stage12687.git(repo, "rev-parse", "--verify", "HEAD").decode("ascii").strip().lower()
            origin = stage12687.sanitize_origin(
                stage12687.git(repo, "config", "--get", "remote.origin.url").decode("utf-8")
            )
            entries = parse_ls_tree(stage12687.git(repo, "ls-tree", "-r", "-l", "-z", revision))
            tree_oid = stage12687.git(repo, "rev-parse", revision + "^{tree}").decode("ascii").strip().lower()
            roots = stage12687.git(repo, "rev-list", "--max-parents=0", revision).decode("ascii").splitlines()
            remotes = stage12687.git(repo, "remote", "-v").decode("utf-8").splitlines()
        except (stage12687.Stage12687Error, Stage12690Error, UnicodeDecodeError):
            counters["git_metadata_failure"] += 1
            continue
        if not stage12687.REVISION_RE.fullmatch(revision) or not origin:
            counters["unpinned_or_origin_missing"] += 1
            continue
        eligible = [entry for entry in entries if path_allowed(entry)]
        eligible.sort(key=lambda entry: (stable([origin, revision, entry.path]), entry.path))
        selected = eligible[:MAX_FILES_PER_REPO]
        if not selected:
            counters["without_python_candidates"] += 1
            continue
        remote_urls = {
            stage12687.sanitize_origin(parts[1])
            for line in remotes for parts in [line.split()] if len(parts) >= 2
        }
        snapshots.append(Snapshot(
            local_path=repo,
            repo_key=stable([origin, revision]),
            origin_url=origin,
            revision=revision,
            blobs=selected,
            component_blobs=tuple(sorted((entry.oid, entry.size) for entry in eligible)),
            lineage_keys=tuple(sorted({
                *(f"root:{root}" for root in roots if stage12687.REVISION_RE.fullmatch(root)),
                f"tree:{tree_oid}",
                *(f"remote:{url}" for url in remote_urls if url),
            })),
            module_path_index=repository_module_path_index(entries),
        ))
        counters["repositories_accepted"] += 1
        counters["python_blobs_selected"] += len(selected)
    stage12687.assign_components(snapshots)
    return snapshots, counters


def parse_snapshot(snapshot: Snapshot) -> tuple[list[ParsedFile], collections.Counter[str]]:
    counters: collections.Counter[str] = collections.Counter()
    base_blobs = [stage12687.Blob(blob.oid, blob.size, blob.path) for blob in snapshot.blobs]
    contents = stage12687.cat_blobs(snapshot.local_path, base_blobs)
    parsed: list[ParsedFile] = []
    for blob in snapshot.blobs:
        data = contents.get(blob.path)
        if data is None or len(data) != blob.size or not stage12687.verify_blob_oid(blob.oid, data):
            counters["missing_size_or_oid_mismatch"] += 1
            continue
        if b"\x00" in data or stage12687.generated_content(data) or stage12687.contains_high_confidence_secret(data):
            counters["binary_generated_or_secret_rejected"] += 1
            continue
        try:
            text = data.decode("utf-8")
            tree = ast.parse(text, filename=blob.path)
        except (UnicodeDecodeError, SyntaxError, ValueError):
            counters["parse_rejected"] += 1
            continue
        names = module_names_for_path(blob.path)
        if not names:
            counters["module_name_rejected"] += 1
            continue
        parsed.append(ParsedFile(blob, data, text, tree, names, is_test_path(blob.path)))
        counters["python_files_parsed"] += 1
    return parsed, counters


def source_catalog_entry(snapshot: Snapshot) -> dict[str, Any]:
    return {
        "repository_key_sha256": snapshot.repo_key,
        "origin_url": snapshot.origin_url,
        "revision": snapshot.revision,
        "content_component_sha256": snapshot.component_key,
        "split": snapshot.split,
        "eligible_python_blob_count": len(snapshot.component_blobs),
        "eligible_python_blob_set_sha256": stable(snapshot.component_blobs),
        "repository_module_name_count": len(snapshot.module_path_index),
        "ambiguous_repository_module_name_count": sum(
            len(paths) != 1 for paths in snapshot.module_path_index.values()
        ),
        "root_commit_git_oids": sorted(key[5:] for key in snapshot.lineage_keys if key.startswith("root:")),
        "tree_git_oids": sorted(key[5:] for key in snapshot.lineage_keys if key.startswith("tree:")),
        "lineage_key_sha256s": [sha256_bytes(key.encode("utf-8")) for key in snapshot.lineage_keys],
        "parser_adapter": dict(PARSER_ADAPTER),
    }


def rename_noreplace(parent_fd: int, source_name: str, destination_name: str) -> None:
    renameat2 = getattr(ctypes.CDLL(None, use_errno=True), "renameat2", None)
    if renameat2 is None:
        raise Stage12690Error("renameat2_noreplace_unavailable")
    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    if renameat2(
        parent_fd,
        source_name.encode("utf-8"),
        parent_fd,
        destination_name.encode("utf-8"),
        1,
    ) != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number), destination_name)


def cross_split_overlap_count(
    records: Iterable[Mapping[str, Any]],
    values,
) -> int:
    owners: dict[str, set[str]] = collections.defaultdict(set)
    for record in records:
        split = str(record["split"])
        for value in values(record):
            owners[str(value)].add(split)
    return sum(len(splits) > 1 for splits in owners.values())


def publication_generation_id(
    *,
    artifact_schema_version: int,
    strict_eval_commitment_sha256: str,
    artifact_sha256s: Mapping[str, str],
) -> str:
    return stable({
        "identity_contract": "stage12690_generation_v4_complete_artifact_identity",
        "artifact_schema_version": artifact_schema_version,
        "strict_eval_commitment_sha256": strict_eval_commitment_sha256,
        "immutable_train_eval_artifact_sha256s": dict(sorted(artifact_sha256s.items())),
    })[:24]


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("ascii")


def jsonl_bytes(records: Iterable[Mapping[str, Any]]) -> bytes:
    return b"".join(
        json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii") + b"\n"
        for record in records
    )


@dataclass(frozen=True)
class ArtifactIdentity:
    device: int
    inode: int
    size: int
    sha256: str


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


def write_file_at(
    directory_fd: int,
    name: str,
    data: bytes,
    *,
    mode: int,
) -> ArtifactIdentity:
    if not name or "/" in name or "\\" in name or name in {".", ".."}:
        raise Stage12690Error("unsafe_publication_filename")
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(name, flags, mode, dir_fd=directory_fd)
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode):
            raise Stage12690Error("publication_leaf_not_regular")
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise Stage12690Error("publication_short_write")
            view = view[written:]
        os.fchmod(fd, mode)
        os.fsync(fd)
        finalized = os.fstat(fd)
        digest = sha256_open_fd(fd)
        if finalized.st_size != len(data):
            raise Stage12690Error("publication_size_mismatch")
        return ArtifactIdentity(
            device=finalized.st_dev,
            inode=finalized.st_ino,
            size=finalized.st_size,
            sha256=digest,
        )
    finally:
        os.close(fd)


def open_private_root(output_dir: Path) -> tuple[int, os.stat_result]:
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    output_fd = stage12687.open_directory_nofollow(output_dir)
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        try:
            os.mkdir("private", 0o700, dir_fd=output_fd)
        except FileExistsError:
            pass
        private_fd = os.open("private", flags, dir_fd=output_fd)
    finally:
        os.close(output_fd)
    opened = os.fstat(private_fd)
    if not stat.S_ISDIR(opened.st_mode):
        os.close(private_fd)
        raise Stage12690Error("private_root_not_directory")
    os.fchmod(private_fd, 0o700)
    return private_fd, opened


def revalidate_private_root(
    private_root: Path,
    private_fd: int,
    expected: os.stat_result,
) -> None:
    opened = os.fstat(private_fd)
    try:
        current = os.stat(private_root, follow_symlinks=False)
    except OSError as exc:
        raise Stage12690Error("private_root_inode_revalidation_failed") from exc
    identity = (expected.st_dev, expected.st_ino)
    if (
        not stat.S_ISDIR(current.st_mode)
        or (opened.st_dev, opened.st_ino) != identity
        or (current.st_dev, current.st_ino) != identity
    ):
        raise Stage12690Error("private_root_inode_changed")


def verify_generation_entry(
    private_fd: int,
    entry_name: str,
    expected: os.stat_result,
    required_artifacts: Mapping[str, ArtifactIdentity],
    *,
    phase: str,
) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        entry_stat = os.stat(entry_name, dir_fd=private_fd, follow_symlinks=False)
        entry_fd = os.open(entry_name, flags, dir_fd=private_fd)
    except OSError as exc:
        raise Stage12690Error(f"{phase}_generation_entry_unavailable") from exc
    try:
        opened = os.fstat(entry_fd)
        expected_identity = (expected.st_dev, expected.st_ino)
        if (
            not stat.S_ISDIR(entry_stat.st_mode)
            or (entry_stat.st_dev, entry_stat.st_ino) != expected_identity
            or (opened.st_dev, opened.st_ino) != expected_identity
        ):
            raise Stage12690Error(f"{phase}_generation_inode_mismatch")
        artifact_flags = (
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0)
        )
        for name, expected_artifact in required_artifacts.items():
            artifact_fd: int | None = None
            try:
                named_before = os.stat(name, dir_fd=entry_fd, follow_symlinks=False)
                artifact_fd = os.open(name, artifact_flags, dir_fd=entry_fd)
                artifact = os.fstat(artifact_fd)
                digest = sha256_open_fd(artifact_fd)
                named_after = os.stat(name, dir_fd=entry_fd, follow_symlinks=False)
            except OSError as exc:
                raise Stage12690Error(
                    f"{phase}_generation_required_artifact_missing:{name}"
                ) from exc
            finally:
                if artifact_fd is not None:
                    os.close(artifact_fd)
            expected_file_identity = (
                expected_artifact.device,
                expected_artifact.inode,
            )
            if (
                not stat.S_ISREG(named_before.st_mode)
                or not stat.S_ISREG(artifact.st_mode)
                or not stat.S_ISREG(named_after.st_mode)
                or (named_before.st_dev, named_before.st_ino) != expected_file_identity
                or (artifact.st_dev, artifact.st_ino) != expected_file_identity
                or (named_after.st_dev, named_after.st_ino) != expected_file_identity
                or artifact.st_size != expected_artifact.size
                or named_after.st_size != expected_artifact.size
                or digest != expected_artifact.sha256
            ):
                raise Stage12690Error(
                    f"{phase}_generation_artifact_identity_mismatch:{name}"
                )
    finally:
        os.close(entry_fd)


def publish(
    output_dir: Path,
    summary_path: Path,
    rows: list[dict[str, Any]],
    proofs: list[dict[str, Any]],
    catalog: list[dict[str, Any]],
    counters: Mapping[str, int],
) -> dict[str, Any]:
    train_eval_rows = [row for row in rows if row["split"] != "strict_eval"]
    train_eval_proofs = [proof for proof in proofs if proof["split"] != "strict_eval"]
    train_eval_catalog = [entry for entry in catalog if entry["split"] != "strict_eval"]
    strict_proofs = [proof for proof in proofs if proof["split"] == "strict_eval"]
    split_counts = collections.Counter(row["split"] for row in rows)
    objective_counts = collections.Counter(
        proof["objective_family"] for proof in train_eval_proofs
    )
    position_counts: dict[str, dict[str, int]] = {}
    for objective in sorted(objective_counts):
        position_counts[objective] = dict(sorted(collections.Counter(
            str(proof["correct_candidate_position"])
            for proof in train_eval_proofs if proof["objective_family"] == objective
        ).items()))
    overlap_metrics = {
        "cross_split_repository_overlap": cross_split_overlap_count(
            proofs, lambda proof: [proof["repository_key_sha256"]]
        ),
        "cross_split_component_overlap": cross_split_overlap_count(
            proofs, lambda proof: [proof["content_component_sha256"]]
        ),
        "cross_split_source_file_digest_overlap": cross_split_overlap_count(
            rows, lambda row: [row["source_provenance"]["source_file_sha256"]]
        ),
        "cross_split_test_file_digest_overlap": cross_split_overlap_count(
            rows, lambda row: [row["source_provenance"]["test_file_sha256"]]
        ),
        "cross_split_model_input_overlap": cross_split_overlap_count(
            proofs, lambda proof: [proof["model_input_sha256"]]
        ),
        "cross_split_candidate_evidence_overlap": cross_split_overlap_count(
            proofs, lambda proof: proof["candidate_evidence_sha256s"]
        ),
    }
    if any(value != 0 for value in overlap_metrics.values()):
        raise Stage12690Error("cross_split_overlap_nonzero")

    encoded_values = {
        "symbol_test_train_eval_manifest.jsonl": jsonl_bytes(train_eval_rows),
        "train_eval_source_provenance_ledger.jsonl": jsonl_bytes(train_eval_proofs),
        "train_eval_source_catalog.jsonl": jsonl_bytes(train_eval_catalog),
    }
    strict_eval_commitment_sha256 = stable(
        sorted(proof["row_sha256"] for proof in strict_proofs)
    )
    artifact_sha256s = {
        name: sha256_bytes(value) for name, value in encoded_values.items()
    }
    generation_id = publication_generation_id(
        artifact_schema_version=ARTIFACT_SCHEMA_VERSION,
        strict_eval_commitment_sha256=strict_eval_commitment_sha256,
        artifact_sha256s=artifact_sha256s,
    )
    artifact_contract = {
        name: {
            "relative_path": f"private/{generation_id}/{name}",
            "rows": len(records),
            "sha256": artifact_sha256s[name],
        }
        for name, records in {
            "symbol_test_train_eval_manifest.jsonl": train_eval_rows,
            "train_eval_source_provenance_ledger.jsonl": train_eval_proofs,
            "train_eval_source_catalog.jsonl": train_eval_catalog,
        }.items()
    }
    summary = {
        "stage": STAGE,
        "generation_id": generation_id,
        "generation_relative_path": f"private/{generation_id}",
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "authoritative_summary_relative_path": f"private/{generation_id}/summary.json",
        "summary_mirror_is_authoritative": False,
        "decision": "SOURCE_BACKED_SYMBOL_AND_TEST_RELATIONS_MATERIALIZED_REVIEW_REQUIRED",
        "objectives": sorted(objective_counts),
        "row_count": len(rows),
        "materialized_model_row_count": len(train_eval_rows),
        "reserved_unmaterialized_strict_row_count": len(strict_proofs),
        "strict_eval_commitment_sha256": strict_eval_commitment_sha256,
        "strict_eval_plaintext_materialized": False,
        "split_counts": dict(sorted(split_counts.items())),
        "objective_counts": dict(sorted(objective_counts.items())),
        "candidate_position_counts": position_counts,
        "parser_adapter": dict(PARSER_ADAPTER),
        "source_catalog_rows": len(train_eval_catalog),
        **overlap_metrics,
        "target_mutation_input_invariant_rows": len(train_eval_rows),
        "artifact_contract": artifact_contract,
        "training_eligible_rows": 0,
        "release_blockers": [
            "independent_semantic_and_leakage_review_required",
            "tokenizer_bound_context_and_target_audit_required",
            "multilanguage_parser_adapters_not_materialized",
        ],
        "authority": dict(AUTHORITY),
    }
    encoded_summary = json_bytes(summary)

    private_root = output_dir / "private"
    private_fd, private_identity = open_private_root(output_dir)
    pending_name = f".pending-{generation_id}-{os.getpid()}"
    pending_fd: int | None = None
    try:
        try:
            os.stat(generation_id, dir_fd=private_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise Stage12690Error(f"immutable_generation_exists:{generation_id}")
        os.mkdir(pending_name, 0o700, dir_fd=private_fd)
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        pending_fd = os.open(pending_name, flags, dir_fd=private_fd)
        pending_identity = os.fstat(pending_fd)
        if not stat.S_ISDIR(pending_identity.st_mode):
            raise Stage12690Error("pending_generation_not_directory")
        expected_artifacts = {
            name: write_file_at(pending_fd, name, data, mode=0o400)
            for name, data in encoded_values.items()
        }
        expected_artifacts["summary.json"] = write_file_at(
            pending_fd, "summary.json", encoded_summary, mode=0o400
        )
        os.fchmod(pending_fd, 0o500)
        os.fsync(pending_fd)
        os.close(pending_fd)
        pending_fd = None
        revalidate_private_root(private_root, private_fd, private_identity)
        verify_generation_entry(
            private_fd, pending_name, pending_identity, expected_artifacts, phase="pending"
        )
        rename_noreplace(private_fd, pending_name, generation_id)
        verify_generation_entry(
            private_fd, generation_id, pending_identity, expected_artifacts, phase="published"
        )
        os.fsync(private_fd)
        revalidate_private_root(private_root, private_fd, private_identity)
    finally:
        if pending_fd is not None:
            os.close(pending_fd)
        os.close(private_fd)

    stage12687.write_json_atomic(summary_path, summary)
    stage12687.write_json_atomic(output_dir / "summary.json", summary)
    return summary


def reserved_split_caps(max_rows: int) -> dict[str, int]:
    if max_rows < 10 or max_rows % 10 != 0:
        raise Stage12690Error("max_rows_must_be_multiple_of_10_and_at_least_10")
    train = max_rows * 8 // 10
    evaluation = max_rows // 10
    return {
        "train": train,
        "eval": evaluation,
        "strict_eval": max_rows - train - evaluation,
    }


def quarantine_cross_component_candidate_evidence(
    records_by_component: Mapping[
        str, list[tuple[Snapshot, dict[str, Any], dict[str, Any]]]
    ],
    counters: collections.Counter[str],
) -> dict[str, list[tuple[Snapshot, dict[str, Any], dict[str, Any]]]]:
    evidence_owners: dict[str, set[str]] = collections.defaultdict(set)
    for component_key, records in records_by_component.items():
        for _, _, proof in records:
            for evidence_sha256 in proof["candidate_evidence_sha256s"]:
                evidence_owners[str(evidence_sha256)].add(component_key)
    shared_evidence = {
        evidence_sha256
        for evidence_sha256, owners in evidence_owners.items()
        if len(owners) > 1
    }
    quarantined: dict[
        str, list[tuple[Snapshot, dict[str, Any], dict[str, Any]]]
    ] = {}
    for component_key in sorted(records_by_component):
        retained = []
        for record in records_by_component[component_key]:
            proof = record[2]
            if any(
                str(evidence_sha256) in shared_evidence
                for evidence_sha256 in proof["candidate_evidence_sha256s"]
            ):
                counters["cross_component_candidate_evidence_rows_quarantined"] += 1
                continue
            retained.append(record)
        if retained:
            quarantined[component_key] = retained
    return quarantined


def estimate_component_relation_capacities(
    records_by_component: Mapping[str, list[tuple[Snapshot, dict[str, Any], dict[str, Any]]]],
) -> dict[str, int]:
    return {
        component_key: len(records)
        for component_key, records in sorted(records_by_component.items())
        if records
    }


def choose_component_subset(
    capacities: Mapping[str, int],
    available: set[str],
    *,
    minimum_capacity: int,
    maximum_capacity: int,
) -> set[str] | None:
    if minimum_capacity <= 0:
        return set()
    if maximum_capacity < minimum_capacity:
        return None
    states: dict[int, tuple[str, ...]] = {0: ()}
    for component_key in sorted(available):
        capacity = capacities[component_key]
        additions: dict[int, tuple[str, ...]] = {}
        for current_capacity, members in states.items():
            candidate_capacity = current_capacity + capacity
            if candidate_capacity > maximum_capacity:
                continue
            candidate_members = members + (component_key,)
            existing = states.get(candidate_capacity) or additions.get(candidate_capacity)
            if existing is None or candidate_members < existing:
                additions[candidate_capacity] = candidate_members
        for candidate_capacity, candidate_members in additions.items():
            existing = states.get(candidate_capacity)
            if existing is None or candidate_members < existing:
                states[candidate_capacity] = candidate_members
    feasible = [capacity for capacity in states if capacity >= minimum_capacity]
    if not feasible:
        return None
    selected_capacity = min(feasible)
    return set(states[selected_capacity])


def allocate_component_splits(
    capacities: Mapping[str, int],
    split_caps: Mapping[str, int],
) -> dict[str, str]:
    positive = {
        component_key: capacity
        for component_key, capacity in capacities.items()
        if capacity > 0
    }
    if sum(positive.values()) < sum(split_caps.values()):
        raise Stage12690Error("reserved_split_caps_unfilled")

    attempts: list[tuple[tuple[Any, ...], dict[str, str]]] = []
    for heldout_order in (("eval", "strict_eval"), ("strict_eval", "eval")):
        available = set(positive)
        assignment: dict[str, str] = {}
        assigned_capacity: dict[str, int] = {}
        feasible = True
        for index, split in enumerate(heldout_order):
            remaining_required = split_caps["train"] + sum(
                split_caps[later] for later in heldout_order[index + 1:]
            )
            maximum_capacity = sum(positive[key] for key in available) - remaining_required
            selected = choose_component_subset(
                positive,
                available,
                minimum_capacity=split_caps[split],
                maximum_capacity=maximum_capacity,
            )
            if selected is None:
                feasible = False
                break
            assigned_capacity[split] = sum(positive[key] for key in selected)
            for component_key in selected:
                assignment[component_key] = split
            available.difference_update(selected)
        if not feasible:
            continue
        train_capacity = sum(positive[key] for key in available)
        if train_capacity < split_caps["train"]:
            continue
        for component_key in available:
            assignment[component_key] = "train"
        score = (
            sum(assigned_capacity[split] - split_caps[split] for split in heldout_order),
            tuple(sorted(assignment.items())),
        )
        attempts.append((score, assignment))
    if not attempts:
        raise Stage12690Error("reserved_split_caps_unfilled")
    return min(attempts, key=lambda value: value[0])[1]


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
]:
    split_caps = reserved_split_caps(max_rows)
    if not source_root.is_dir():
        raise Stage12690Error(f"source_root_missing:{source_root}")
    snapshots, counters = discover_repositories(source_root, max_repos)
    if not snapshots:
        raise Stage12690Error("no_pinned_python_repositories")

    records_by_component: dict[
        str, list[tuple[Snapshot, dict[str, Any], dict[str, Any]]]
    ] = collections.defaultdict(list)
    seen_inputs: set[str] = set()
    repo_counts: collections.Counter[str] = collections.Counter()
    for snapshot in sorted(snapshots, key=lambda value: (value.component_key, value.repo_key)):
        try:
            parsed, parse_counts = parse_snapshot(snapshot)
        except stage12687.Stage12687Error:
            counters["snapshot_blob_read_failure"] += 1
            continue
        counters.update(parse_counts)
        relations, relation_counts = extract_relations(parsed, snapshot.module_path_index)
        counters.update(relation_counts)
        definitions = [
            definition
            for source in parsed
            if not source.is_test
            for definition in top_level_definitions(source)
        ]
        built_rows, built_proofs, build_counts = build_relation_rows(
            snapshot, relations, definitions
        )
        counters.update(build_counts)
        for row, proof in zip(built_rows, built_proofs, strict=True):
            if repo_counts[snapshot.repo_key] >= MAX_ROWS_PER_REPO:
                break
            input_hash = proof["model_input_sha256"]
            if input_hash in seen_inputs:
                counters["duplicate_model_input_rejected"] += 1
                continue
            seen_inputs.add(input_hash)
            records_by_component[snapshot.component_key].append((snapshot, row, proof))
            repo_counts[snapshot.repo_key] += 1

    records_by_component = quarantine_cross_component_candidate_evidence(
        records_by_component, counters
    )
    capacities = estimate_component_relation_capacities(records_by_component)
    component_splits = allocate_component_splits(capacities, split_caps)
    for snapshot in snapshots:
        if snapshot.component_key in component_splits:
            snapshot.split = component_splits[snapshot.component_key]

    rows: list[dict[str, Any]] = []
    proofs: list[dict[str, Any]] = []
    split_counts: collections.Counter[str] = collections.Counter()
    for component_key in sorted(component_splits):
        split = component_splits[component_key]
        for snapshot, original_row, original_proof in records_by_component[component_key]:
            if split_counts[split] >= split_caps[split]:
                break
            row = {**original_row, "split": split}
            proof = {**original_proof, "split": split, "row_sha256": stable(row)}
            rows.append(row)
            proofs.append(proof)
            split_counts[split] += 1

    if any(split_counts[split] != cap for split, cap in split_caps.items()):
        raise Stage12690Error("reserved_split_caps_unfilled")
    selected_components = set(component_splits)
    catalog = [
        source_catalog_entry(snapshot)
        for snapshot in snapshots
        if snapshot.component_key in selected_components
    ]
    return rows, proofs, catalog, counters


def _prepare_public_view(
    rows: list[dict[str, Any]],
    proofs: list[dict[str, Any]],
    catalog: list[dict[str, Any]],
) -> tuple[dict[str, bytes], dict[str, Any]]:
    train_eval_rows = [row for row in rows if row["split"] != "strict_eval"]
    train_eval_proofs = [proof for proof in proofs if proof["split"] != "strict_eval"]
    train_eval_catalog = [entry for entry in catalog if entry["split"] != "strict_eval"]
    strict_proofs = [proof for proof in proofs if proof["split"] == "strict_eval"]
    overlap_metrics = {
        "cross_split_repository_overlap": cross_split_overlap_count(
            proofs, lambda proof: [proof["repository_key_sha256"]]
        ),
        "cross_split_component_overlap": cross_split_overlap_count(
            proofs, lambda proof: [proof["content_component_sha256"]]
        ),
        "cross_split_source_file_digest_overlap": cross_split_overlap_count(
            rows, lambda row: [row["source_provenance"]["source_file_sha256"]]
        ),
        "cross_split_test_file_digest_overlap": cross_split_overlap_count(
            rows, lambda row: [row["source_provenance"]["test_file_sha256"]]
        ),
        "cross_split_model_input_overlap": cross_split_overlap_count(
            proofs, lambda proof: [proof["model_input_sha256"]]
        ),
        "cross_split_candidate_evidence_overlap": cross_split_overlap_count(
            proofs, lambda proof: proof["candidate_evidence_sha256s"]
        ),
    }
    if any(overlap_metrics.values()):
        raise Stage12690Error("cross_split_overlap_nonzero")
    payloads = {
        "symbol_test_train_eval_manifest.jsonl": jsonl_bytes(train_eval_rows),
        "train_eval_source_provenance_ledger.jsonl": jsonl_bytes(train_eval_proofs),
        "train_eval_source_catalog.jsonl": jsonl_bytes(train_eval_catalog),
    }
    strict_commitment = stable(sorted(
        proof["row_sha256"] for proof in strict_proofs
    ))
    artifact_sha256s = {
        name: sha256_bytes(value) for name, value in payloads.items()
    }
    generation_id = publication_generation_id(
        artifact_schema_version=ARTIFACT_SCHEMA_VERSION,
        strict_eval_commitment_sha256=strict_commitment,
        artifact_sha256s=artifact_sha256s,
    )
    objective_counts = collections.Counter(
        proof["objective_family"] for proof in train_eval_proofs
    )
    position_counts = {
        objective: dict(sorted(collections.Counter(
            str(proof["correct_candidate_position"])
            for proof in train_eval_proofs
            if proof["objective_family"] == objective
        ).items()))
        for objective in sorted(objective_counts)
    }
    summary = {
        "stage": STAGE,
        "generation_id": generation_id,
        "generation_relative_path": f"private/{generation_id}",
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "authoritative_summary_relative_path": f"private/{generation_id}/summary.json",
        "summary_mirror_is_authoritative": False,
        "decision": "SOURCE_BACKED_SYMBOL_AND_TEST_RELATIONS_MATERIALIZED_REVIEW_REQUIRED",
        "objectives": sorted(objective_counts),
        "row_count": len(rows),
        "materialized_model_row_count": len(train_eval_rows),
        "reserved_unmaterialized_strict_row_count": len(strict_proofs),
        "strict_eval_commitment_sha256": strict_commitment,
        "strict_eval_plaintext_materialized": False,
        "split_counts": dict(sorted(collections.Counter(
            row["split"] for row in rows
        ).items())),
        "objective_counts": dict(sorted(objective_counts.items())),
        "candidate_position_counts": position_counts,
        "parser_adapter": dict(PARSER_ADAPTER),
        "source_catalog_rows": len(train_eval_catalog),
        **overlap_metrics,
        "target_mutation_input_invariant_rows": len(train_eval_rows),
        "artifact_contract": {
            name: {
                "relative_path": f"private/{generation_id}/{name}",
                "rows": len(records),
                "sha256": artifact_sha256s[name],
            }
            for name, records in {
                "symbol_test_train_eval_manifest.jsonl": train_eval_rows,
                "train_eval_source_provenance_ledger.jsonl": train_eval_proofs,
                "train_eval_source_catalog.jsonl": train_eval_catalog,
            }.items()
        },
        "training_eligible_rows": 0,
        "release_blockers": [
            "independent_semantic_and_leakage_review_required",
            "tokenizer_bound_context_and_target_audit_required",
            "multilanguage_parser_adapters_not_materialized",
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
    rows, proofs, catalog, counters = materialize(
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
    rows, proofs, catalog, counters = materialize(
        source_root, max_repos=max_repos, max_rows=max_rows
    )
    return publish(output_dir, summary_path, rows, proofs, catalog, counters)


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
        raise SystemExit("max-repos must be positive and max-rows must be a multiple of 10 and at least 10")
    print(json.dumps(build(
        args.source_root.resolve(), args.output_dir.resolve(), args.summary_path.resolve(),
        max_repos=args.max_repos, max_rows=args.max_rows,
    ), indent=2, sort_keys=True))
