#!/usr/bin/env python3
"""Exact source-backed declarative convention extraction; no discovery/publication."""

from __future__ import annotations
from dataclasses import dataclass
import argparse
import collections
import configparser
import hashlib
import json
import os
import re
import sys
import tomllib
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_stage12687_source_backed_python_foundational_corpus as stage12687
import build_stage12688_source_backed_multilingual_knowledge_corpus as stage12688
import build_stage12690_source_backed_symbol_api_test_links as stage12690

OBJECTIVE_FAMILY = "declarative_test_build_target_resolution"
PARSER_ADAPTER = {"name": "stdlib_json_plus_byte_spans", "version": "1"}
PROOF_CONTRACT = "exact_literal_package_script_reference_v1"
AUTHORITY = {
    "implementation_ready": False,
    "stage12595_allowed": False,
    "replay_trustworthy": False,
    "level_3_materialized": False,
    "training_admitted": False,
    "strict_eval_admitted": False,
    "sealed_eval_admitted": False,
}
CARGO_PACKAGE_RESOLUTION_SUPPORTED = False
_REF = re.compile(r"(?P<manager>npm|yarn|pnpm)[ \t]+run[ \t]+(?P<target>[A-Za-z0-9_.:@/+~-]+)")
_ALIAS_PREFIX_REF = re.compile(
    r"(?P<manager>npm|yarn|pnpm)[ \t]+run[ \t]+"
    r"(?P<target>[A-Za-z0-9_.:@/+~-]+)(?=\Z|[ \t;&|])"
)
_HEX40 = re.compile(r"[0-9a-f]{40}")
_HEX64 = re.compile(r"[0-9a-f]{64}")


class PackageJsonError(ValueError):
    pass


def _reject_constant(value: str) -> None:
    raise PackageJsonError(f"non_finite_json_constant:{value}")


@dataclass(frozen=True)
class JsonMember:
    name: str
    value: Any
    member_start: int
    member_end: int
    name_start: int
    name_end: int
    value_start: int
    value_end: int
    value_kind: str
    children: tuple["JsonMember", ...] = ()


@dataclass(frozen=True)
class ScriptDefinition:
    name: str
    command: str
    member_start: int
    member_end: int
    name_start: int
    name_end: int
    command_start: int
    command_end: int


@dataclass(frozen=True)
class LiteralScriptReference:
    manager: str
    target: str
    target_start: int
    target_end: int


class _SpanParser:
    """Byte parser checked against the independent stdlib JSON result."""

    def __init__(self, source: bytes):
        self.source = source
        self.pos = 0

    def parse(self) -> tuple[Any, str, tuple[JsonMember, ...]]:
        value, kind, children, _, _ = self._value()
        self._space()
        if self.pos != len(self.source):
            raise PackageJsonError("trailing_json_data")
        return value, kind, children

    def _space(self) -> None:
        while self.pos < len(self.source) and self.source[self.pos] in b" \t\r\n":
            self.pos += 1

    def _string(self) -> tuple[str, int, int]:
        if self.pos >= len(self.source) or self.source[self.pos] != 34:
            raise PackageJsonError("expected_json_string")
        start = self.pos
        self.pos += 1
        escaped = False
        while self.pos < len(self.source):
            byte = self.source[self.pos]
            if byte == 34 and not escaped:
                self.pos += 1
                try:
                    value = json.loads(self.source[start:self.pos].decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise PackageJsonError("invalid_json_string") from exc
                return value, start + 1, self.pos - 1
            if byte == 92 and not escaped:
                escaped = True
            else:
                escaped = False
            self.pos += 1
        raise PackageJsonError("unterminated_json_string")

    def _value(self) -> tuple[Any, str, tuple[JsonMember, ...], int, int]:
        self._space()
        if self.pos >= len(self.source):
            raise PackageJsonError("unexpected_json_eof")
        start = self.pos
        byte = self.source[self.pos]
        if byte == 123:
            return self._object()
        if byte == 91:
            return self._array()
        if byte == 34:
            value, _, _ = self._string()
            return value, "string", (), start, self.pos
        while self.pos < len(self.source) and self.source[self.pos] not in b",]} \t\r\n":
            self.pos += 1
        try:
            value = json.loads(
                self.source[start:self.pos].decode("ascii"),
                parse_constant=_reject_constant,
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PackageJsonError("invalid_json_scalar") from exc
        return value, "scalar", (), start, self.pos

    def _object(self) -> tuple[Any, str, tuple[JsonMember, ...], int, int]:
        start = self.pos
        self.pos += 1
        self._space()
        values: dict[str, Any] = {}
        members: list[JsonMember] = []
        if self.pos < len(self.source) and self.source[self.pos] == 125:
            self.pos += 1
            return values, "object", (), start, self.pos
        while True:
            self._space()
            member_start = self.pos
            name, name_start, name_end = self._string()
            if name in values:
                raise PackageJsonError("duplicate_json_key")
            self._space()
            if self.pos >= len(self.source) or self.source[self.pos] != 58:
                raise PackageJsonError("missing_json_colon")
            self.pos += 1
            value, kind, children, value_start, value_end = self._value()
            values[name] = value
            members.append(JsonMember(
                name, value, member_start, value_end, name_start, name_end,
                value_start, value_end, kind, children
            ))
            self._space()
            if self.pos >= len(self.source):
                raise PackageJsonError("unterminated_json_object")
            delimiter = self.source[self.pos]
            self.pos += 1
            if delimiter == 125:
                return values, "object", tuple(members), start, self.pos
            if delimiter != 44:
                raise PackageJsonError("invalid_json_object_delimiter")

    def _array(self) -> tuple[Any, str, tuple[JsonMember, ...], int, int]:
        start = self.pos
        self.pos += 1
        self._space()
        values: list[Any] = []
        if self.pos < len(self.source) and self.source[self.pos] == 93:
            self.pos += 1
            return values, "array", (), start, self.pos
        while True:
            value, _, _, _, _ = self._value()
            values.append(value)
            self._space()
            if self.pos >= len(self.source):
                raise PackageJsonError("unterminated_json_array")
            delimiter = self.source[self.pos]
            self.pos += 1
            if delimiter == 93:
                return values, "array", (), start, self.pos
            if delimiter != 44:
                raise PackageJsonError("invalid_json_array_delimiter")


def _stdlib_unique(source: bytes) -> Any:
    try:
        text = source.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PackageJsonError("package_json_not_utf8") from exc

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise PackageJsonError("duplicate_json_key")
            result[key] = value
        return result

    try:
        return json.loads(
            text,
            object_pairs_hook=unique,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise PackageJsonError("invalid_package_json") from exc


def parse_package_json_scripts(source: bytes) -> tuple[ScriptDefinition, ...]:
    """Parse direct script definitions with exact UTF-8 byte spans."""

    if not isinstance(source, bytes):
        raise TypeError("source_must_be_bytes")
    canonical = _stdlib_unique(source)
    parsed, root_kind, root_members = _SpanParser(source).parse()
    if parsed != canonical:
        raise PackageJsonError("json_parser_disagreement")
    if root_kind != "object":
        raise PackageJsonError("package_json_root_not_object")
    scripts = next((item for item in root_members if item.name == "scripts"), None)
    if scripts is None:
        return ()
    if scripts.value_kind != "object":
        raise PackageJsonError("scripts_not_object")

    result: list[ScriptDefinition] = []
    for member in scripts.children:
        if member.value_kind != "string" or not isinstance(member.value, str):
            raise PackageJsonError("script_definition_not_string")
        raw_name = source[member.name_start:member.name_end]
        raw_command = source[member.value_start + 1:member.value_end - 1]
        try:
            name = raw_name.decode("utf-8")
            command = raw_command.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PackageJsonError("script_span_not_utf8") from exc
        if name != member.name or command != member.value:
            raise PackageJsonError("escaped_script_definition_unsupported")
        if not name or b"\x00" in raw_name or b"\x00" in raw_command:
            raise PackageJsonError("invalid_script_definition")
        result.append(ScriptDefinition(
            name, command, member.member_start, member.member_end,
            member.name_start, member.name_end,
            member.value_start + 1, member.value_end - 1
        ))
    return tuple(result)


def parse_literal_script_reference(definition: ScriptDefinition) -> LiteralScriptReference | None:
    """Accept exactly one literal package-manager run command."""

    match = _REF.fullmatch(definition.command)
    if match is None:
        return None
    char_start, char_end = match.span("target")
    start = definition.command_start + len(definition.command[:char_start].encode("utf-8"))
    end = definition.command_start + len(definition.command[:char_end].encode("utf-8"))
    return LiteralScriptReference(match.group("manager"), match.group("target"), start, end)


def is_alias_script(definition: ScriptDefinition) -> bool:
    """Identify canonical forwarding prefixes, including args or compounds."""

    return _ALIAS_PREFIX_REF.match(definition.command) is not None


def deterministic_candidates(
    definitions: tuple[ScriptDefinition, ...],
) -> tuple[ScriptDefinition, ...]:
    """Choose 4-8 declarations without consulting a reference target."""

    eligible = tuple(
        item for item in definitions
        if not is_alias_script(item)
    )
    if len(eligible) < 4:
        return ()
    return tuple(sorted(
        eligible,
        key=lambda item: (
            hashlib.sha256(item.name.encode("utf-8")).digest(),
            item.name.encode("utf-8"),
        ),
    )[:8])


def _validate_inputs(repo_key: str, revision: str, blob_oid: str, path: str) -> None:
    if not _HEX64.fullmatch(repo_key):
        raise ValueError("repository_key_sha256_must_be_lower_hex64")
    if not _HEX40.fullmatch(revision):
        raise ValueError("revision_must_be_lower_hex40")
    if not re.fullmatch(r"[0-9a-f]{40,64}", blob_oid):
        raise ValueError("package_blob_oid_must_be_lower_hex")
    if (
        not path or path.startswith("/") or "\\" in path or "\x00" in path
        or any(part in {"", ".", ".."} for part in path.split("/"))
    ):
        raise ValueError("package_path_not_canonical_relative")


def extract_package_json_rows(
    source: bytes,
    *,
    repository_key_sha256: str,
    revision: str,
    package_blob_oid: str,
    package_path: str = "package.json",
) -> list[dict[str, Any]]:
    """Create rows from one caller-supplied package.json."""

    _validate_inputs(repository_key_sha256, revision, package_blob_oid, package_path)
    definitions = parse_package_json_scripts(source)
    candidates = deterministic_candidates(definitions)
    if not candidates:
        return []
    index = {item.name: position for position, item in enumerate(candidates)}
    by_name = {item.name: item for item in definitions}
    digest = hashlib.sha256(source).hexdigest()
    candidate_lines = [
        f"candidate_{position}: " + source[item.member_start:item.member_end].decode("utf-8")
        for position, item in enumerate(candidates)
    ]
    rows: list[dict[str, Any]] = []
    for invocation in definitions:
        reference = parse_literal_script_reference(invocation)
        if reference is None or reference.target not in index:
            continue
        definition = by_name[reference.target]
        if is_alias_script(definition):
            continue
        masked = (
            source[invocation.member_start:reference.target_start]
            + b"<TARGET>"
            + source[reference.target_end:invocation.member_end]
        ).decode("utf-8")
        input_text = "\n".join([
            f"objective: {OBJECTIVE_FAMILY}",
            f"package: {package_path}",
            f"invocation: {masked}",
            "candidates:",
            *candidate_lines,
        ])
        provenance = {
            "repository_key_sha256": repository_key_sha256,
            "revision": revision,
            "package_path": package_path,
            "package_git_blob_oid": package_blob_oid,
            "package_file_sha256": digest,
            "invocation_name_start_byte": invocation.name_start,
            "invocation_name_end_byte": invocation.name_end,
            "invocation_command_start_byte": invocation.command_start,
            "invocation_command_end_byte": invocation.command_end,
            "reference_target_start_byte": reference.target_start,
            "reference_target_end_byte": reference.target_end,
            "definition_name_start_byte": definition.name_start,
            "definition_name_end_byte": definition.name_end,
            "definition_command_start_byte": definition.command_start,
            "definition_command_end_byte": definition.command_end,
            "candidate_definition_spans": [
                {"start_byte": item.member_start, "end_byte": item.member_end}
                for item in candidates
            ],
            "parser_adapter": dict(PARSER_ADAPTER),
            "proof_contract": PROOF_CONTRACT,
        }
        position = index[reference.target]
        identity = json.dumps(
            {"input": input_text, "position": position, "provenance": provenance},
            ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        rows.append({
            "row_id": "stage12692_" + hashlib.sha256(identity).hexdigest(),
            "language_family": "declarative_build_test",
            "ecosystem": "npm",
            "objective_family": OBJECTIVE_FAMILY,
            "input_text": input_text,
            "target": {"decoder_text": f"candidate_{position}"},
            "loss_mask": {"decoder_ce": True},
            "source_provenance": provenance,
            "authority": dict(AUTHORITY),
        })
    return rows




@dataclass(frozen=True)
class ExactDefinition:
    value: str
    start: int
    end: int
    member_start: int
    member_end: int


@dataclass(frozen=True)
class ExactReference:
    value: str
    start: int
    end: int
    member_start: int
    member_end: int


def _byte_lines(source: bytes) -> list[tuple[int, int, bytes]]:
    result = []
    offset = 0
    for line in source.splitlines(keepends=True):
        content = line.rstrip(b"\r\n")
        result.append((offset, offset + len(content), content))
        offset += len(line)
    if not source or source.endswith((b"\n", b"\r")):
        return result
    return result


def _parse_toml(source: bytes) -> dict[str, Any]:
    try:
        text = source.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PackageJsonError("declarative_source_not_utf8") from exc
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise PackageJsonError("invalid_toml") from exc


def _exact_string(token: bytes) -> str:
    if len(token) < 2 or token[:1] not in {b'"', b"'"} or token[-1:] != token[:1]:
        raise PackageJsonError("non_literal_string")
    raw = token[1:-1]
    if b"\\" in raw or b"\n" in raw or b"\r" in raw:
        raise PackageJsonError("escaped_or_multiline_value")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PackageJsonError("declarative_source_not_utf8") from exc


def _row_identity(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "stage12692_" + hashlib.sha256(encoded).hexdigest()


def _scalar_row(
    source: bytes,
    *,
    ecosystem: str,
    source_path: str,
    kind: str,
    target_start: int,
    target_end: int,
    member_start: int,
    member_end: int,
    repository_key_sha256: str,
    revision: str,
    source_blob_oid: str,
    adapter: str,
) -> dict[str, Any]:
    target = source[target_start:target_end].decode("utf-8")
    masked = (
        source[member_start:target_start]
        + b"<SCALAR>"
        + source[target_end:member_end]
    ).decode("utf-8")
    input_text = "\n".join([
        "objective: declarative_test_build_scalar_completion",
        f"source: {source_path}",
        f"declaration_kind: {kind}",
        f"declaration: {masked}",
    ])
    provenance = {
        "repository_key_sha256": repository_key_sha256,
        "revision": revision,
        "source_path": source_path,
        "source_git_blob_oid": source_blob_oid,
        "source_file_sha256": hashlib.sha256(source).hexdigest(),
        "target_start_byte": target_start,
        "target_end_byte": target_end,
        "member_start_byte": member_start,
        "member_end_byte": member_end,
        "parser_adapter": {"name": adapter, "version": "1"},
        "proof_contract": "exact_static_literal_scalar_completion_v1",
    }
    return {
        "row_id": _row_identity(
            {"input": input_text, "target": target, "provenance": provenance}
        ),
        "language_family": "declarative_build_test",
        "ecosystem": ecosystem,
        "objective_family": "declarative_test_build_scalar_completion",
        "input_text": input_text,
        "target": {"decoder_text": target},
        "loss_mask": {"decoder_ce": True},
        "source_provenance": provenance,
        "authority": dict(AUTHORITY),
    }


def _resolution_rows(
    source: bytes,
    *,
    ecosystem: str,
    source_path: str,
    definitions: list[ExactDefinition],
    references: list[ExactReference],
    repository_key_sha256: str,
    revision: str,
    source_blob_oid: str,
    adapter: str,
) -> list[dict[str, Any]]:
    values = [item.value for item in definitions]
    if len(values) != len(set(values)):
        raise PackageJsonError("ambiguous_duplicate_definition")
    ordered = sorted(
        definitions,
        key=lambda item: (
            hashlib.sha256(item.value.encode("utf-8")).digest(),
            item.value.encode("utf-8"),
        ),
    )
    if len(ordered) < 4:
        return []
    ordered = ordered[:8]
    positions = {item.value: index for index, item in enumerate(ordered)}
    candidate_lines = [
        f"candidate_{index}: "
        + source[item.member_start:item.member_end].decode("utf-8")
        for index, item in enumerate(ordered)
    ]
    digest = hashlib.sha256(source).hexdigest()
    rows = []
    for reference in references:
        if reference.value not in positions:
            continue
        masked = (
            source[reference.member_start:reference.start]
            + b"<TARGET>"
            + source[reference.end:reference.member_end]
        ).decode("utf-8")
        input_text = "\n".join([
            "objective: declarative_test_build_target_resolution",
            f"source: {source_path}",
            f"invocation: {masked}",
            "candidates:",
            *candidate_lines,
        ])
        position = positions[reference.value]
        definition = next(item for item in ordered if item.value == reference.value)
        provenance = {
            "repository_key_sha256": repository_key_sha256,
            "revision": revision,
            "source_path": source_path,
            "source_git_blob_oid": source_blob_oid,
            "source_file_sha256": digest,
            "reference_target_start_byte": reference.start,
            "reference_target_end_byte": reference.end,
            "definition_start_byte": definition.start,
            "definition_end_byte": definition.end,
            "candidate_definition_spans": [
                {"start_byte": item.member_start, "end_byte": item.member_end}
                for item in ordered
            ],
            "parser_adapter": {"name": adapter, "version": "1"},
            "proof_contract": "exact_static_literal_same_file_resolution_v1",
        }
        rows.append({
            "row_id": _row_identity(
                {"input": input_text, "position": position, "provenance": provenance}
            ),
            "language_family": "declarative_build_test",
            "ecosystem": ecosystem,
            "objective_family": "declarative_test_build_target_resolution",
            "input_text": input_text,
            "target": {"decoder_text": f"candidate_{position}"},
            "loss_mask": {"decoder_ce": True},
            "source_provenance": provenance,
            "authority": dict(AUTHORITY),
        })
    return rows


def _validate_adapter_inputs(
    repository_key_sha256: str,
    revision: str,
    source_blob_oid: str,
    source_path: str,
) -> None:
    _validate_inputs(repository_key_sha256, revision, source_blob_oid, source_path)


def extract_tox_ini_rows(
    source: bytes,
    *,
    repository_key_sha256: str,
    revision: str,
    source_blob_oid: str,
    source_path: str = "tox.ini",
) -> list[dict[str, Any]]:
    """Extract exact static tox environment references."""

    _validate_adapter_inputs(
        repository_key_sha256, revision, source_blob_oid, source_path
    )
    try:
        text = source.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PackageJsonError("declarative_source_not_utf8") from exc
    if any(token in text for token in ("%(", "$", "`", "{", "}")):
        raise PackageJsonError("tox_interpolation_not_allowed")
    parser = configparser.ConfigParser(strict=True, interpolation=None)
    try:
        parser.read_string(text)
    except configparser.Error as exc:
        raise PackageJsonError("invalid_or_duplicate_tox_ini") from exc

    definitions: list[ExactDefinition] = []
    references: list[ExactReference] = []
    alias_environment_names: set[str] = set()
    envlist_values: list[str] = []
    section = ""
    active_option: bytes | None = None
    for line_start, line_end, line in _byte_lines(source):
        section_match = re.fullmatch(
            rb"[ \t]*\[([^]\r\n]+)\][ \t]*", line
        )
        if section_match:
            section = section_match.group(1).decode("utf-8")
            active_option = None
            env_match = re.fullmatch(
                rb"testenv:([A-Za-z0-9_.-]+)", section_match.group(1)
            )
            if env_match:
                value_bytes = env_match.group(1)
                value = value_bytes.decode("ascii")
                value_start = (
                    line_start + section_match.start(1) + env_match.start(1)
                )
                definitions.append(ExactDefinition(
                    value, value_start, value_start + len(value_bytes),
                    line_start, line_end
                ))
            elif section.startswith("testenv:"):
                raise PackageJsonError("dynamic_tox_environment")
            continue

        assignment = re.fullmatch(
            rb"[ \t]*([A-Za-z0-9_.-]+)[ \t]*[:=][ \t]*(.*?)[ \t]*", line
        )
        if assignment:
            active_option = assignment.group(1).lower()
            option_name = active_option
            value_bytes = assignment.group(2)
        elif line[:1] in {b" ", b"\t"} and line.strip():
            option_name = active_option
            value_bytes = line.strip()
        else:
            active_option = None
            option_name = None
            value_bytes = line.strip()
        value_offset = line.find(value_bytes)
        if section == "tox" and option_name == b"envlist":
            try:
                parts = [
                    item for chunk in value_bytes.decode("utf-8").split(",")
                    for item in chunk.split()
                ]
            except UnicodeDecodeError as exc:
                raise PackageJsonError("declarative_source_not_utf8") from exc
            if any(not re.fullmatch(r"[A-Za-z0-9_.-]+", item) for item in parts):
                raise PackageJsonError("dynamic_tox_envlist")
            envlist_values.extend(parts)

        command_option = (
            option_name == b"commands"
            and section.startswith("testenv:")
        )
        alias_ref = re.match(
            rb"tox[ \t]+-e[ \t]+([A-Za-z0-9_.-]+)(?=\Z|[ \t;&|])",
            value_bytes,
        ) if command_option else None
        if alias_ref:
            alias_environment_names.add(section.split(":", 1)[1])
        ref = re.fullmatch(
            rb"tox[ \t]+-e[ \t]+([A-Za-z0-9_.-]+)", value_bytes
        ) if command_option else None
        if ref:
            start = line_start + value_offset + ref.start(1)
            end = line_start + value_offset + ref.end(1)
            references.append(ExactReference(
                ref.group(1).decode("ascii"), start, end, line_start, line_end
            ))

    declared = {item.value for item in definitions}
    if len(declared) != len(definitions):
        raise PackageJsonError("ambiguous_duplicate_definition")
    if any(item not in declared for item in envlist_values):
        raise PackageJsonError("tox_envlist_without_static_testenv")
    definitions = [
        item for item in definitions
        if item.value not in alias_environment_names
    ]
    return _resolution_rows(
        source,
        ecosystem="tox",
        source_path=source_path,
        definitions=definitions,
        references=references,
        repository_key_sha256=repository_key_sha256,
        revision=revision,
        source_blob_oid=source_blob_oid,
        adapter="stdlib_configparser_strict",
    )


def _simple_toml_array(
    value: bytes, absolute_start: int
) -> list[tuple[str, int, int]]:
    if not (value.startswith(b"[") and value.endswith(b"]")):
        raise PackageJsonError("computed_or_multiline_array")
    inner = value[1:-1]
    items = []
    position = 0
    while position < len(inner):
        while position < len(inner) and inner[position] in b" \t,":
            position += 1
        if position == len(inner):
            break
        match = re.match(rb"(['\"])([^'\"\\\r\n]*)\1", inner[position:])
        if not match:
            raise PackageJsonError("escaped_or_dynamic_array_value")
        raw = match.group(0)
        decoded = _exact_string(raw)
        start = absolute_start + 1 + position + 1
        end = start + len(match.group(2))
        items.append((decoded, start, end))
        position += len(raw)
        while position < len(inner) and inner[position] in b" \t":
            position += 1
        if position < len(inner) and inner[position] != 44:
            raise PackageJsonError("ambiguous_array_syntax")
    return items


def extract_pyproject_toml_rows(
    source: bytes,
    *,
    repository_key_sha256: str,
    revision: str,
    source_blob_oid: str,
    source_path: str = "pyproject.toml",
) -> list[dict[str, Any]]:
    """Extract exact pytest paths/options and tool-name scalar completions."""

    _validate_adapter_inputs(
        repository_key_sha256, revision, source_blob_oid, source_path
    )
    parsed = _parse_toml(source)
    declarations: list[tuple[str, int, int, int, int]] = []
    section = ""
    for line_start, line_end, line in _byte_lines(source):
        header = re.fullmatch(rb"[ \t]*\[([^]\r\n]+)\][ \t]*", line)
        if header:
            section = header.group(1).decode("utf-8")
            tool = re.fullmatch(
                r"tool\.([A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*)", section
            )
            if section.startswith("tool.") and not tool:
                raise PackageJsonError("dynamic_or_escaped_tool_table")
            if tool:
                name = tool.group(1).encode("utf-8")
                start = line_start + header.start(1) + len(b"tool.")
                declarations.append(("tool_table_name", start, start + len(name), line_start, line_end))
            continue
        if section != "tool.pytest.ini_options":
            continue
        assignment = re.fullmatch(
            rb"[ \t]*([A-Za-z0-9_-]+)[ \t]*=[ \t]*(.*?)[ \t]*", line
        )
        if not assignment:
            if line.strip():
                raise PackageJsonError("computed_or_multiline_pytest_value")
            continue
        key = assignment.group(1).decode("ascii")
        value = assignment.group(2)
        value_start = line_start + line.find(value)
        if key == "testpaths":
            items = _simple_toml_array(value, value_start)
            semantic = parsed.get("tool", {}).get("pytest", {}).get("ini_options", {}).get("testpaths")
            if semantic != [item[0] for item in items]:
                raise PackageJsonError("toml_span_semantic_mismatch")
            declarations.extend(
                ("pytest_test_path", start, end, line_start, line_end)
                for _, start, end in items
            )
        elif key in {"addopts", "python_files", "python_classes", "python_functions"}:
            exact = _exact_string(value)
            semantic = parsed.get("tool", {}).get("pytest", {}).get("ini_options", {}).get(key)
            if semantic != exact:
                raise PackageJsonError("toml_span_semantic_mismatch")
            declarations.append(
                ("pytest_literal_option", value_start + 1, value_start + len(value) - 1, line_start, line_end)
            )

    seen: set[tuple[str, bytes]] = set()
    rows = []
    for kind, start, end, member_start, member_end in declarations:
        identity = (kind, source[start:end])
        if identity in seen:
            raise PackageJsonError("ambiguous_duplicate_textual_span")
        seen.add(identity)
        rows.append(_scalar_row(
            source,
            ecosystem="python",
            source_path=source_path,
            kind=kind,
            target_start=start,
            target_end=end,
            member_start=member_start,
            member_end=member_end,
            repository_key_sha256=repository_key_sha256,
            revision=revision,
            source_blob_oid=source_blob_oid,
            adapter="stdlib_tomllib_pyproject",
        ))
    return rows


def extract_cargo_toml_rows(
    source: bytes,
    *,
    repository_key_sha256: str,
    revision: str,
    source_blob_oid: str,
    source_path: str = "Cargo.toml",
) -> list[dict[str, Any]]:
    """Extract Cargo scalars; package resolution needs bound child manifests."""

    _validate_adapter_inputs(
        repository_key_sha256, revision, source_blob_oid, source_path
    )
    parsed = _parse_toml(source)
    section = ""
    scalars: list[tuple[str, int, int, int, int]] = []
    for line_start, line_end, line in _byte_lines(source):
        header = re.fullmatch(rb"[ \t]*\[([^]\r\n]+)\][ \t]*", line)
        if header:
            section = header.group(1).decode("utf-8")
            continue
        assignment = re.fullmatch(
            rb"[ \t]*([A-Za-z0-9_.-]+)[ \t]*=[ \t]*(.*?)[ \t]*", line
        )
        if not assignment:
            continue
        key = assignment.group(1).decode("ascii")
        value = assignment.group(2)
        value_start = line_start + line.find(value)
        if section == "package" and key == "name":
            exact = _exact_string(value)
            if parsed.get("package", {}).get("name") != exact:
                raise PackageJsonError("toml_span_semantic_mismatch")
            scalars.append(("cargo_package_name", value_start + 1, value_start + len(value) - 1, line_start, line_end))
        elif section == "workspace" and key == "members":
            items = _simple_toml_array(value, value_start)
            if parsed.get("workspace", {}).get("members") != [item[0] for item in items]:
                raise PackageJsonError("toml_span_semantic_mismatch")
            for exact, start, end in items:
                if any(marker in exact for marker in ("*", "?", "[", "]")):
                    raise PackageJsonError("dynamic_cargo_workspace_member")
                scalars.append(("cargo_workspace_member", start, end, line_start, line_end))

    scalar_seen: set[tuple[str, bytes]] = set()
    rows = []
    for kind, start, end, member_start, member_end in scalars:
        identity = (kind, source[start:end])
        if identity in scalar_seen:
            raise PackageJsonError("ambiguous_duplicate_textual_span")
        scalar_seen.add(identity)
        rows.append(_scalar_row(
            source,
            ecosystem="cargo",
            source_path=source_path,
            kind=kind,
            target_start=start,
            target_end=end,
            member_start=member_start,
            member_end=member_end,
            repository_key_sha256=repository_key_sha256,
            revision=revision,
            source_blob_oid=source_blob_oid,
            adapter="stdlib_tomllib_cargo",
        ))
    return rows




MAKE_RECIPE_SCALAR_COMPLETION_SUPPORTED = False
_MAKE_TOKEN = rb"[A-Za-z0-9][A-Za-z0-9_.@/+~-]*"


@dataclass(frozen=True)
class MakeRule:
    target: ExactDefinition
    prerequisites: tuple[str, ...]
    recipes: tuple[tuple[int, int, bytes], ...]


def _make_directive(line: bytes) -> bool:
    return re.match(
        rb"(?:-?include|sinclude|define|endef|ifeq|ifneq|ifdef|ifndef|else|endif)"
        rb"(?:[ \t]|\Z)",
        line,
    ) is not None


def _make_recipe_delegates(command: bytes) -> bool:
    return re.search(
        rb"(?:\A|[ \t;&|])[\x40\x2b\x2d]*"
        rb"(?:[A-Za-z0-9_./+-]*/)?(?:gmake|make)(?:[ \t]|\Z)", command
    ) is not None


def _parse_makefile_rules(source: bytes) -> tuple[MakeRule, ...]:
    try:
        source.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PackageJsonError("declarative_source_not_utf8") from exc

    provisional: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    names: set[str] = set()
    for line_start, line_end, line in _byte_lines(source):
        stripped = line.strip()
        if not stripped or stripped.startswith(b"#"):
            continue
        if b"\\" in line:
            raise PackageJsonError("make_line_continuation_not_allowed")
        if b"%" in line:
            raise PackageJsonError("make_pattern_rule_not_allowed")
        if b"$" in line or bytes((96,)) in line:
            raise PackageJsonError("make_dynamic_expansion_not_allowed")

        if line.startswith(b"\t"):
            if current is None:
                raise PackageJsonError("orphan_make_recipe")
            command = line[1:]
            if not command or b"#" in command:
                raise PackageJsonError("ambiguous_make_recipe")
            current["recipes"].append((line_start, line_end, command))
            continue

        current = None
        if _make_directive(stripped):
            raise PackageJsonError("make_directive_not_allowed")
        if re.match(
            rb"[A-Za-z_][A-Za-z0-9_.-]*[ \t]*(?::=|\?=|\+=|!=|=)",
            stripped,
        ):
            raise PackageJsonError("make_variable_assignment_not_allowed")
        if b"::" in stripped:
            raise PackageJsonError("make_double_colon_not_allowed")
        if b"#" in stripped or b";" in stripped:
            raise PackageJsonError("ambiguous_make_rule")
        match = re.fullmatch(
            rb"[ \t]*(" + _MAKE_TOKEN + rb")[ \t]*:[ \t]*(.*?)[ \t]*",
            line,
        )
        if match is None:
            raise PackageJsonError("unsupported_or_multi_target_make_rule")
        target_bytes = match.group(1)
        target = target_bytes.decode("ascii")
        if target in names:
            raise PackageJsonError("duplicate_make_target")
        names.add(target)
        prerequisites: list[str] = []
        if match.group(2):
            for token in match.group(2).split():
                if re.fullmatch(_MAKE_TOKEN, token) is None:
                    raise PackageJsonError("dynamic_make_prerequisite")
                prerequisites.append(token.decode("ascii"))
        target_start = line_start + match.start(1)
        current = {
            "target": ExactDefinition(
                target,
                target_start,
                target_start + len(target_bytes),
                line_start,
                line_end,
            ),
            "prerequisites": tuple(prerequisites),
            "recipes": [],
        }
        provisional.append(current)

    return tuple(
        MakeRule(item["target"], item["prerequisites"], tuple(item["recipes"]))
        for item in provisional
    )


def extract_makefile_rows(
    source: bytes,
    *,
    repository_key_sha256: str,
    revision: str,
    source_blob_oid: str,
    source_path: str = "Makefile",
) -> list[dict[str, Any]]:
    """Extract exact bare make-target references from literal rules."""

    _validate_adapter_inputs(
        repository_key_sha256, revision, source_blob_oid, source_path
    )
    rules = _parse_makefile_rules(source)
    definitions: list[ExactDefinition] = []
    references: list[ExactReference] = []
    for rule in rules:
        delegates = any(
            _make_recipe_delegates(command)
            for _, _, command in rule.recipes
        )
        if rule.recipes and not rule.prerequisites and not delegates:
            definitions.append(rule.target)

        for line_start, line_end, command in rule.recipes:
            exact = re.fullmatch(rb"make[ \t]+(" + _MAKE_TOKEN + rb")", command)
            if exact is None:
                continue
            references.append(ExactReference(
                exact.group(1).decode("ascii"),
                line_start + 1 + exact.start(1),
                line_start + 1 + exact.end(1),
                rule.target.member_start,
                line_end,
            ))

    return _resolution_rows(
        source,
        ecosystem="make",
        source_path=source_path,
        definitions=definitions,
        references=references,
        repository_key_sha256=repository_key_sha256,
        revision=revision,
        source_blob_oid=source_blob_oid,
        adapter="raw_makefile_literal_rules",
    )




STAGE = "stage12692_source_backed_declarative_test_build_conventions"
ARTIFACT_SCHEMA_VERSION = 1
DEFAULT_SOURCE_ROOT = Path("/arxiv/repositories")
DEFAULT_OUTPUT_DIR = ROOT / "runs/local/artifacts" / STAGE
DEFAULT_SUMMARY_PATH = ROOT / "runs/summaries" / f"{STAGE}.json"
DEFAULT_MAX_REPOS = 601
DEFAULT_MAX_ROWS = 1_880
DEFAULT_PER_REPO_CAP = 200
MAX_DECLARATIVE_SOURCE_BYTES = 1_000_000
SUPPORTED_BASENAMES = frozenset({
    "package.json", "tox.ini", "pyproject.toml", "Cargo.toml",
    "Makefile", "GNUmakefile", "makefile",
})
YAML_SUPPORTED = False


class Stage12692BuildError(RuntimeError):
    pass


@dataclass
class SupplyScan:
    snapshots: list[Any]
    records_by_component: dict[str, list[tuple[Any, dict[str, Any], dict[str, Any]]]]
    counters: collections.Counter[str]
    grouping_contract: dict[str, Any]
    scan_context: dict[str, Any] | None = None
    scan_commitment_sha256: str = ""

    @property
    def capacities(self) -> dict[str, int]:
        return {
            component: len(records)
            for component, records in sorted(self.records_by_component.items())
            if records
        }

    @property
    def row_count(self) -> int:
        return sum(self.capacities.values())


@dataclass(frozen=True)
class PreparedRelease:
    rows: list[dict[str, Any]]
    proofs: list[dict[str, Any]]
    catalog: list[dict[str, Any]]
    public_payloads: dict[str, bytes]
    summary: dict[str, Any]



def _current_scan_contract(scan: SupplyScan) -> dict[str, Any]:
    if not isinstance(scan.scan_context, dict):
        raise Stage12692BuildError("capacity_scan_commitment_missing")
    snapshots = sorted(
        (
            snapshot.repo_key,
            snapshot.revision,
            snapshot.tree_oid,
            snapshot.component_key,
        )
        for snapshot in scan.snapshots
    )
    return {
        "contract": "stage12692_post_filter_capacity_scan_v1",
        "source_root_identity_sha256": scan.scan_context.get(
            "source_root_identity_sha256"
        ),
        "max_repos": scan.scan_context.get("max_repos"),
        "per_repo_cap": scan.scan_context.get("per_repo_cap"),
        "grouping_contract_sha256": stage12688.stable(scan.grouping_contract),
        "snapshot_identities": snapshots,
        "component_capacities": scan.capacities,
        "post_filter_row_supply": scan.row_count,
    }


def _bind_scan_commitment(
    scan: SupplyScan,
    *,
    source_root_identity_sha256: str,
    max_repos: int,
    per_repo_cap: int,
) -> SupplyScan:
    scan.scan_context = {
        "source_root_identity_sha256": source_root_identity_sha256,
        "max_repos": max_repos,
        "per_repo_cap": per_repo_cap,
    }
    scan.scan_commitment_sha256 = stage12688.stable(
        _current_scan_contract(scan)
    )
    return scan


def _validate_scan_commitment(scan: SupplyScan) -> None:
    if (
        not scan.scan_commitment_sha256
        or scan.scan_commitment_sha256
        != stage12688.stable(_current_scan_contract(scan))
    ):
        raise Stage12692BuildError("capacity_scan_commitment_mismatch")


def _supported_declarative_path(path: str) -> bool:
    return (
        stage12688.canonical_git_path(path)
        and PurePosixPath(path).name in SUPPORTED_BASENAMES
    )


def discover_pinned_snapshots(
    source_root: Path, max_repos: int
) -> tuple[list[Any], collections.Counter[str]]:
    snapshots, counters = stage12688.discover_repositories(source_root, max_repos)
    accepted = []
    for snapshot in snapshots:
        blobs = [
            stage12688.Blob(entry.oid, int(entry.size), entry.path)
            for entry in snapshot.tree_entries
            if entry.object_type == "blob"
            and entry.size is not None
            and entry.mode in {"100644", "100755"}
            and 0 < entry.size <= MAX_DECLARATIVE_SOURCE_BYTES
            and _supported_declarative_path(entry.path)
        ]
        blobs.sort(key=lambda blob: blob.path.encode("utf-8"))
        if not blobs:
            counters["without_stage12692_supported_files"] += 1
            continue
        snapshot.blobs = blobs
        snapshot.estimated_row_capacity = DEFAULT_PER_REPO_CAP
        accepted.append(snapshot)
        counters["stage12692_repositories_accepted"] += 1
        counters["stage12692_supported_blobs"] += len(blobs)
    return accepted, counters


def _adapter_for_path(path: str):
    name = PurePosixPath(path).name
    if name == "package.json":
        return extract_package_json_rows
    if name == "tox.ini":
        return extract_tox_ini_rows
    if name == "pyproject.toml":
        return extract_pyproject_toml_rows
    if name == "Cargo.toml":
        return extract_cargo_toml_rows
    if name in {"Makefile", "GNUmakefile", "makefile"}:
        return extract_makefile_rows
    raise Stage12692BuildError("unsupported_declarative_path")


def _candidate_evidence(
    source: bytes, provenance: dict[str, Any]
) -> list[str]:
    evidence = []
    for span in provenance.get("candidate_definition_spans", []):
        start = span.get("start_byte")
        end = span.get("end_byte")
        if (
            not isinstance(start, int)
            or not isinstance(end, int)
            or start < 0
            or end <= start
            or end > len(source)
        ):
            raise Stage12692BuildError("invalid_candidate_definition_span")
        exact = source[start:end]
        evidence.append(stage12688.stable([
            "stage12692_exact_candidate_definition_v1",
            provenance["source_path"],
            provenance.get("source_git_blob_oid"),
            provenance["source_file_sha256"],
            start,
            end,
            hashlib.sha256(exact).hexdigest(),
        ]))
    return sorted(set(evidence))


def _proof_for_row(
    snapshot: Any, row: dict[str, Any], source: bytes
) -> dict[str, Any]:
    provenance = row["source_provenance"]
    source_digest = provenance["source_file_sha256"]
    definition_start = provenance.get(
        "definition_start_byte",
        provenance.get(
            "target_start_byte", provenance.get("definition_name_start_byte")
        ),
    )
    definition_end = provenance.get(
        "definition_end_byte",
        provenance.get(
            "target_end_byte", provenance.get("definition_name_end_byte")
        ),
    )
    definition_evidence = stage12688.stable([
        provenance["source_path"],
        source_digest,
        definition_start,
        definition_end,
    ])
    input_digest = hashlib.sha256(row["input_text"].encode("utf-8")).hexdigest()
    semantic_digest = stage12688.stable([
        row["objective_family"],
        row["input_text"],
        row["target"]["decoder_text"],
    ])
    return {
        "row_id": row["row_id"],
        "repository_key_sha256": snapshot.repo_key,
        "content_component_sha256": snapshot.component_key,
        "revision": snapshot.revision,
        "tree_oid": snapshot.tree_oid,
        "source_path": provenance["source_path"],
        "source_file_sha256": source_digest,
        "definition_evidence_sha256": definition_evidence,
        "candidate_evidence_sha256s": _candidate_evidence(source, provenance),
        "model_input_sha256": input_digest,
        "semantic_example_sha256": semantic_digest,
        "objective_family": row["objective_family"],
    }


def _extract_snapshot_rows(
    snapshot: Any,
    counters: collections.Counter[str],
    per_repo_cap: int,
) -> list[tuple[Any, dict[str, Any], dict[str, Any]]]:
    try:
        contents = stage12688.cat_blobs(snapshot.local_path, snapshot.blobs)
    except stage12688.Stage12688Error as exc:
        raise Stage12692BuildError("snapshot_blob_read_failure") from exc
    records = []
    for blob in snapshot.blobs:
        if len(records) >= per_repo_cap:
            counters["per_repository_cap_rows_skipped"] += 1
            break
        source = contents.get(blob.path)
        if source is None:
            raise Stage12692BuildError("snapshot_blob_read_failure")
        adapter = _adapter_for_path(blob.path)
        kwargs = {
            "repository_key_sha256": snapshot.repo_key,
            "revision": snapshot.revision,
        }
        try:
            if adapter is extract_package_json_rows:
                rows = adapter(
                    source,
                    package_blob_oid=blob.oid,
                    package_path=blob.path,
                    **kwargs,
                )
            else:
                rows = adapter(
                    source,
                    source_blob_oid=blob.oid,
                    source_path=blob.path,
                    **kwargs,
                )
        except (PackageJsonError, ValueError, TypeError):
            counters["parser_rows_rejected"] += 1
            continue
        for original in rows:
            if len(records) >= per_repo_cap:
                counters["per_repository_cap_rows_skipped"] += 1
                break
            original_provenance = original["source_provenance"]
            provenance = {
                **original_provenance,
                "source_path": original_provenance.get(
                    "source_path", original_provenance.get("package_path")
                ),
                "source_git_blob_oid": original_provenance.get(
                    "source_git_blob_oid",
                    original_provenance.get("package_git_blob_oid"),
                ),
                "source_file_sha256": original_provenance.get(
                    "source_file_sha256",
                    original_provenance.get("package_file_sha256"),
                ),
                "repository_key_sha256": snapshot.repo_key,
                "revision": snapshot.revision,
                "tree_oid": snapshot.tree_oid,
                "content_component_sha256": snapshot.component_key,
            }
            row = {**original, "source_provenance": provenance}
            proof = _proof_for_row(snapshot, row, source)
            records.append((snapshot, row, proof))
            counters["rows_extracted"] += 1
    records.sort(key=lambda item: item[1]["row_id"])
    return records


def _quarantine_and_deduplicate(
    records_by_component: dict[str, list[tuple[Any, dict[str, Any], dict[str, Any]]]],
    counters: collections.Counter[str],
) -> dict[str, list[tuple[Any, dict[str, Any], dict[str, Any]]]]:
    ownership: dict[tuple[str, str], set[str]] = collections.defaultdict(set)
    fields = (
        "source_file_sha256",
        "definition_evidence_sha256",
        "model_input_sha256",
        "semantic_example_sha256",
    )
    for component, records in records_by_component.items():
        for _, _, proof in records:
            for field in fields:
                ownership[(field, proof[field])].add(component)
            for evidence in proof["candidate_evidence_sha256s"]:
                ownership[("candidate", evidence)].add(component)
    shared = {
        key for key, owners in ownership.items() if len(owners) > 1
    }

    seen: dict[str, set[str]] = {
        "row": set(), "input": set(), "semantic": set()
    }
    retained: dict[str, list[tuple[Any, dict[str, Any], dict[str, Any]]]] = {}
    for component in sorted(records_by_component):
        component_rows = []
        for record in records_by_component[component]:
            _, row, proof = record
            keys = [
                ("source_file_sha256", proof["source_file_sha256"]),
                ("definition_evidence_sha256", proof["definition_evidence_sha256"]),
                ("model_input_sha256", proof["model_input_sha256"]),
                ("semantic_example_sha256", proof["semantic_example_sha256"]),
                *(("candidate", value) for value in proof["candidate_evidence_sha256s"]),
            ]
            if any(key in shared for key in keys):
                counters["cross_component_evidence_rows_quarantined"] += 1
                continue
            duplicate = (
                row["row_id"] in seen["row"]
                or proof["model_input_sha256"] in seen["input"]
                or proof["semantic_example_sha256"] in seen["semantic"]
            )
            if duplicate:
                counters["global_duplicate_rows_rejected"] += 1
                continue
            seen["row"].add(row["row_id"])
            seen["input"].add(proof["model_input_sha256"])
            seen["semantic"].add(proof["semantic_example_sha256"])
            component_rows.append(record)
        if component_rows:
            retained[component] = component_rows
    return retained


def scan_repository_supply(
    source_root: Path,
    *,
    max_repos: int = DEFAULT_MAX_REPOS,
    per_repo_cap: int = DEFAULT_PER_REPO_CAP,
) -> SupplyScan:
    if max_repos <= 0 or per_repo_cap <= 0:
        raise Stage12692BuildError("invalid_scan_limits")
    if not source_root.is_dir():
        raise Stage12692BuildError("source_root_missing")
    snapshots, counters = discover_pinned_snapshots(source_root, max_repos)
    if not snapshots:
        raise Stage12692BuildError("no_supported_pinned_repositories")
    grouping = stage12688.assign_components(snapshots)
    records: dict[str, list[tuple[Any, dict[str, Any], dict[str, Any]]]] = collections.defaultdict(list)
    for snapshot in sorted(
        snapshots, key=lambda item: (item.component_key, item.repo_key)
    ):
        records[snapshot.component_key].extend(
            _extract_snapshot_rows(snapshot, counters, per_repo_cap)
        )
    retained = _quarantine_and_deduplicate(dict(records), counters)
    source_root_stat = source_root.stat()
    scan = SupplyScan(snapshots, retained, counters, grouping)
    return _bind_scan_commitment(
        scan,
        source_root_identity_sha256=stage12688.stable([
            str(source_root.absolute()),
            source_root_stat.st_dev,
            source_root_stat.st_ino,
        ]),
        max_repos=max_repos,
        per_repo_cap=per_repo_cap,
    )


def _split_caps(max_rows: int) -> dict[str, int]:
    try:
        return stage12690.reserved_split_caps(max_rows)
    except stage12690.Stage12690Error as exc:
        raise Stage12692BuildError("invalid_max_rows") from exc


def materialize_split_rows(
    scan: SupplyScan, max_rows: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, str]]:
    _validate_scan_commitment(scan)
    caps = _split_caps(max_rows)
    try:
        assignments = stage12690.allocate_component_splits(scan.capacities, caps)
    except stage12690.Stage12690Error as exc:
        raise Stage12692BuildError("requested_split_caps_unfilled") from exc
    counts: collections.Counter[str] = collections.Counter()
    rows = []
    proofs = []
    for component in sorted(assignments):
        split = assignments[component]
        for _, original_row, original_proof in scan.records_by_component[component]:
            if counts[split] >= caps[split]:
                break
            row = {**original_row, "split": split}
            proof = {
                **original_proof,
                "split": split,
                "row_sha256": stage12688.stable(row),
            }
            rows.append(row)
            proofs.append(proof)
            counts[split] += 1
    if any(counts[split] != cap for split, cap in caps.items()):
        raise Stage12692BuildError("requested_split_caps_unfilled")
    _assert_zero_split_overlap(proofs)
    return rows, proofs, assignments


def _assert_zero_split_overlap(proofs: list[dict[str, Any]]) -> None:
    fields = {
        "repository": lambda proof: [proof["repository_key_sha256"]],
        "component": lambda proof: [proof["content_component_sha256"]],
        "source": lambda proof: [proof["source_file_sha256"]],
        "definition": lambda proof: [proof["definition_evidence_sha256"]],
        "model_input": lambda proof: [proof["model_input_sha256"]],
        "candidate": lambda proof: proof["candidate_evidence_sha256s"],
        "semantic": lambda proof: [proof["semantic_example_sha256"]],
    }
    for values in fields.values():
        owners: dict[str, set[str]] = collections.defaultdict(set)
        for proof in proofs:
            for value in values(proof):
                owners[value].add(proof["split"])
        if any(len(splits) > 1 for splits in owners.values()):
            raise Stage12692BuildError("cross_split_overlap_nonzero")


def _jsonl(records: list[dict[str, Any]]) -> bytes:
    return b"".join(
        (
            json.dumps(record, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
            + "\n"
        ).encode("ascii")
        for record in records
    )


def prepare_full_release(scan: SupplyScan, max_rows: int) -> PreparedRelease:
    rows, proofs, assignments = materialize_split_rows(scan, max_rows)
    public_rows = [row for row in rows if row["split"] != "strict_eval"]
    public_proofs = [proof for proof in proofs if proof["split"] != "strict_eval"]
    strict_proofs = [proof for proof in proofs if proof["split"] == "strict_eval"]
    full_catalog = []
    selected = set(assignments)
    for snapshot in scan.snapshots:
        if snapshot.component_key not in selected:
            continue
        split = assignments[snapshot.component_key]
        full_catalog.append({
            "repository_key_sha256": snapshot.repo_key,
            "content_component_sha256": snapshot.component_key,
            "revision": snapshot.revision,
            "tree_oid": snapshot.tree_oid,
            "split": split,
            "all_tree_object_count": len(snapshot.component_objects),
            "all_tree_object_identity_inventory_sha256": stage12688.stable(
                snapshot.component_objects
            ),
        })
    full_catalog.sort(key=lambda item: (
        item["content_component_sha256"], item["repository_key_sha256"]
    ))
    public_catalog = [
        entry for entry in full_catalog if entry["split"] != "strict_eval"
    ]
    strict_commitment = stage12688.stable(
        sorted(proof["row_sha256"] for proof in strict_proofs)
    )
    payloads = {
        "train_eval_rows.jsonl": _jsonl(public_rows),
        "train_eval_proofs.jsonl": _jsonl(public_proofs),
        "train_eval_source_catalog.jsonl": _jsonl(public_catalog),
    }
    artifact_hashes = {
        name: hashlib.sha256(payload).hexdigest()
        for name, payload in sorted(payloads.items())
    }
    generation_id = stage12688.stable([
        "stage12692_generation_v1",
        ARTIFACT_SCHEMA_VERSION,
        artifact_hashes,
        len(strict_proofs),
        strict_commitment,
    ])
    public_objectives = collections.Counter(
        row["objective_family"] for row in public_rows
    )
    public_ecosystems = collections.Counter(row["ecosystem"] for row in public_rows)
    summary = {
        "stage": STAGE,
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "generation_id": generation_id,
        "decision": "SOURCE_BACKED_DECLARATIVE_ROWS_MATERIALIZED_REVIEW_REQUIRED",
        "max_rows": max_rows,
        "capacity_scan_commitment_sha256": scan.scan_commitment_sha256,
        "materialized_train_eval_rows": len(public_rows),
        "reserved_unmaterialized_strict_row_count": len(strict_proofs),
        "strict_eval_commitment_sha256": strict_commitment,
        "objective_counts_train_eval_only": dict(sorted(public_objectives.items())),
        "ecosystem_counts_train_eval_only": dict(sorted(public_ecosystems.items())),
        "artifact_sha256s": artifact_hashes,
        "source_catalog_rows_train_eval_only": len(public_catalog),
        "yaml_supported": False,
        "cargo_package_resolution_supported": False,
        "make_recipe_scalar_completion_supported": False,
        "whole_component_assignment": True,
        "training_eligible_rows": 0,
        "authority": dict(AUTHORITY),
    }
    return PreparedRelease(rows, proofs, full_catalog, payloads, summary)


def prepare_release(
    scan: SupplyScan, max_rows: int
) -> tuple[
    dict[str, Any],
    dict[str, bytes],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    prepared = prepare_full_release(scan, max_rows)
    return (
        prepared.summary,
        prepared.public_payloads,
        prepared.rows,
        prepared.proofs,
    )


def publish_release(
    output_dir: Path,
    summary_path: Path,
    scan: SupplyScan,
    max_rows: int,
) -> dict[str, Any]:
    summary, payloads, _, _ = prepare_release(scan, max_rows)
    try:
        stage12687.publish_generation(
            output_dir,
            summary["generation_id"],
            payloads,
            summary,
        )
        stage12687.write_json_atomic(summary_path, summary)
        stage12687.write_json_atomic(output_dir / "summary.json", summary)
    except (stage12688.Stage12688Error, stage12687.Stage12687Error, OSError) as exc:
        raise Stage12692BuildError("immutable_publication_failed") from exc
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--summary-path", type=Path, default=DEFAULT_SUMMARY_PATH)
    parser.add_argument("--max-repos", type=int, default=DEFAULT_MAX_REPOS)
    parser.add_argument("--per-repo-cap", type=int, default=DEFAULT_PER_REPO_CAP)
    parser.add_argument("--max-rows", type=int, default=DEFAULT_MAX_ROWS)
    parser.add_argument("--no-publication-capacity-scan", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    scan = scan_repository_supply(
        args.source_root,
        max_repos=args.max_repos,
        per_repo_cap=args.per_repo_cap,
    )
    if args.no_publication_capacity_scan:
        result = {
            "stage": STAGE,
            "publication_performed": False,
            "post_filter_row_supply": scan.row_count,
            "component_capacities": scan.capacities,
            "counters": dict(sorted(scan.counters.items())),
        }
        print(json.dumps(result, sort_keys=True))
        return 0
    if args.max_rows is None:
        raise Stage12692BuildError("max_rows_requires_grounded_capacity_scan")
    publish_release(args.output_dir, args.summary_path, scan, args.max_rows)
    return 0


__all__ = [
    "AUTHORITY", "CARGO_PACKAGE_RESOLUTION_SUPPORTED", "MAKE_RECIPE_SCALAR_COMPLETION_SUPPORTED", "OBJECTIVE_FAMILY", "PackageJsonError", "ScriptDefinition",
    "deterministic_candidates", "extract_package_json_rows",
    "parse_literal_script_reference", "parse_package_json_scripts",
    "extract_tox_ini_rows", "extract_pyproject_toml_rows",
    "extract_cargo_toml_rows", "extract_makefile_rows",
    "PreparedRelease", "scan_repository_supply", "materialize_split_rows",
    "prepare_full_release", "prepare_release",
    "publish_release",
]


if __name__ == "__main__":
    raise SystemExit(main())
