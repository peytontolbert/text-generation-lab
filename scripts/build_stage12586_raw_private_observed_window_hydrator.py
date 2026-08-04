#!/usr/bin/env python3
"""Hydrate canonical observed Codex windows without exposing raw payloads."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shlex
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12586_raw_private_observed_window_hydrator"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
STAGE12585 = ROOT / "runs/local/artifacts/stage12585_same_source_observed_trajectory_root_miner/candidate_ledger.jsonl"
PHYSICAL = ROOT / "runs/local/artifacts/stage12256_live_physical_session_inventory_refresh/live_physical_source_records.jsonl"
CHATS = ROOT / "runs/local/artifacts/stage12258_live_codex_chat_reconstruction_index/per_chat_manifest.jsonl"
EVENTS = ROOT / "runs/local/artifacts/stage12258_live_codex_chat_reconstruction_index/chat_event_index.jsonl"
PAIRS = ROOT / "runs/local/artifacts/stage12259_codex_tool_call_observation_pairer/tool_call_observation_pairs.jsonl"
WINDOWS = ROOT / "runs/local/artifacts/stage12260_codex_chat_task_boundary_miner/codex_task_windows.jsonl"
CODEX_SESSIONS = Path("/home/peyton/.codex/sessions")

EXIT_RE = re.compile(r"Process exited with code (?P<code>-?\d+)")
WRAPPED_EXIT_RE = re.compile(r"\AExit code:[ \t]*(?P<code>-?\d+)[ \t]*(?:\r?\n|\Z)")
RUNNING_RE = re.compile(r"Process running with session ID (?P<session>\d+)")
PATCH_HEADER_RE = re.compile(r"^\*\*\* (?P<op>Add|Update|Delete) File: (?P<path>.+)$")
ABSOLUTE_PATH_RE = re.compile(r"(?<![A-Za-z0-9_:])(?:/(?:[A-Za-z0-9._~-]+/)*[A-Za-z0-9._~-]+|[A-Za-z]:[\\/][^\s'\"`,;:]*)")
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", re.I),
    re.compile(r"\b(?:sk|ghp|github_pat|xox[baprs])-[A-Za-z0-9_-]{8,}\b", re.I),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\b(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)\s*[:=]\s*[^\s,;]{6,}", re.I),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.I),
)
NO_PATCH_PATTERNS = (
    ("no_changes_needed", re.compile(r"\bno (?:code )?changes? (?:were )?(?:needed|required)\b", re.I)),
    ("no_changes_made", re.compile(r"\bno (?:files? |code )?(?:were )?(?:changed|modified)\b", re.I)),
    ("assistant_declined_mutation", re.compile(r"\b(?:did not|didn't) (?:make|apply|modify|change)\b", re.I)),
    ("read_only_outcome", re.compile(r"\bread[- ]only (?:analysis|review|audit)\b", re.I)),
)
EDIT_TOOLS = {"apply_patch", "_apply_patch"}
FORBIDDEN_OUTPUT_KEYS = {
    "admission",
    "admissions",
    "admitted_episodes",
    "admitted_training_projections",
    "candidate_actions",
    "model_input",
    "model_inputs",
    "projection",
    "projections",
    "trainer_manifest",
    "trainer_manifests",
    "training_rows",
}
STAGE12314_HASH_SALT = "stage12314_no_raw_path_or_text_join_v1"


class GateError(RuntimeError):
    pass


def sha1_text(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=True, default=str)
    return sha256_bytes(raw.encode("utf-8"))


def stable_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
    return sha256_bytes(raw.encode("utf-8"))


def stable_id(prefix: str, *parts: Any) -> str:
    return f"{prefix}_{stable_hash(parts)[:20]}"


def stage12314_session_hash(value: Any) -> str | None:
    if value in (None, "", [], {}):
        return None
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE12314_HASH_SALT}:{payload}".encode("utf-8")).hexdigest()[:24]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return list(iter_jsonl(path))


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.is_file():
        raise GateError(f"required_input_missing:{path}")
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise GateError(f"malformed_jsonl:{path}:{line_number}") from exc
            if not isinstance(row, dict):
                raise GateError(f"non_object_jsonl_row:{path}:{line_number}")
            yield row


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    os.replace(temporary, path)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iso_utc(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def index_unique(rows: Iterable[dict[str, Any]], key: str, label: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        identity = str(row.get(key) or "")
        if not identity:
            raise GateError(f"{label}_identity_missing")
        if identity in indexed:
            raise GateError(f"duplicate_{label}_identity:{identity}")
        indexed[identity] = row
    return indexed


def _unsafe_string(value: str) -> str | None:
    if ABSOLUTE_PATH_RE.search(value):
        return "absolute_path_value"
    for pattern in SECRET_PATTERNS:
        if pattern.search(value):
            return "secret_like_value"
    return None


def assert_safe_shape(value: Any) -> None:
    """Fail closed on model-facing shapes, secrets, paths, or enabled training flags."""
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            if key_text in FORBIDDEN_OUTPUT_KEYS:
                raise GateError(f"forbidden_output_key:{key_text}")
            if key_text == "training_allowed" and child is not False:
                raise GateError("training_allowed_must_be_explicit_false")
            assert_safe_shape(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            assert_safe_shape(child)
    elif isinstance(value, str):
        reason = _unsafe_string(value)
        if reason:
            raise GateError(reason)


def safe_json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if not isinstance(value, str):
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def payload_of(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload")
    return payload if isinstance(payload, dict) else event


def indexed_payload_digest(payload: dict[str, Any]) -> str:
    scrubbed = dict(payload)
    for key in ("content", "output", "arguments", "message", "encrypted_content", "summary"):
        if key in scrubbed:
            scrubbed[key] = f"<{key}:redacted:{sha256_json(scrubbed[key])[:16]}>"
    return sha256_json(scrubbed)


def content_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(content_text(item) for item in value)
    if isinstance(value, dict):
        for key in ("text", "content", "output", "message"):
            if key in value:
                return content_text(value[key])
    return ""


def message_digest_fact(line_number: int, payload: dict[str, Any]) -> dict[str, Any]:
    content = payload.get("content", payload.get("message"))
    content_types: Counter[str] = Counter()
    if isinstance(content, list):
        for item in content:
            content_types[str(item.get("type") or "object") if isinstance(item, dict) else type(item).__name__] += 1
    elif content is not None:
        content_types[type(content).__name__] += 1
    return {
        "line_number": line_number,
        "role": str(payload.get("role") or ""),
        "payload_type": str(payload.get("type") or ""),
        "content_sha256": sha256_json(content),
        "content_shape_counts": dict(sorted(content_types.items())),
        "raw_content_emitted": False,
    }


def _shell_tokens(command: str) -> list[str]:
    try:
        return shlex.split(command, posix=True)
    except ValueError:
        return command.strip().split()


def command_head(command: str) -> str:
    tokens = _shell_tokens(command)
    while tokens and "=" in tokens[0] and not tokens[0].startswith(("./", "/")):
        tokens.pop(0)
    return Path(tokens[0]).name if tokens else ""


def verifier_kind(command: str) -> str | None:
    """Recognize literal verifier invocations without inferring relevance."""
    tokens = _shell_tokens(command)
    basenames = [Path(token).name for token in tokens]
    if "pytest" in basenames or any(item.endswith("pytest") for item in basenames):
        return "pytest"
    for idx, token in enumerate(basenames[:-2]):
        if token.startswith("python") and tokens[idx + 1] == "-m" and tokens[idx + 2] == "pytest":
            return "python_module_pytest"
    if "ctest" in basenames:
        return "ctest"
    if "vitest" in basenames:
        return "vitest"
    if "tsc" in basenames:
        return "typescript_check"
    if "cargo" in basenames and "test" in tokens:
        return "cargo_test"
    if "go" in basenames and "test" in tokens:
        return "go_test"
    if any(item in {"npm", "pnpm", "yarn", "npx"} for item in basenames) and any(
        token in {"test", "check", "lint", "typecheck"} for token in tokens
    ):
        return "package_script_check"
    if "bash" in basenames and "-n" in tokens:
        return "bash_syntax_check"
    return None


def state_probe_kind(command: str) -> str | None:
    tokens = _shell_tokens(command)
    basenames = [Path(token).name for token in tokens]
    try:
        idx = basenames.index("git")
    except ValueError:
        return None
    tail = tokens[idx + 1 :]
    while len(tail) >= 2 and tail[0] in {"-C", "--git-dir", "--work-tree"}:
        tail = tail[2:]
    if not tail:
        return None
    if tail[0] == "status":
        return "git_status"
    if tail[0] == "diff":
        return "git_diff"
    return None


def output_status(output: Any, *, tool_name: str = "") -> dict[str, Any]:
    text = content_text(output)
    if isinstance(output, dict) and isinstance(output.get("exit_code"), int):
        code = int(output["exit_code"])
        return {"status": "passed" if code == 0 else "failed", "exit_code": code, "status_source": "structured_exit_code"}
    match = EXIT_RE.search(text)
    if match:
        code = int(match.group("code"))
        return {"status": "passed" if code == 0 else "failed", "exit_code": code, "status_source": "observed_exit_marker"}
    match = WRAPPED_EXIT_RE.search(text)
    if match:
        code = int(match.group("code"))
        return {"status": "passed" if code == 0 else "failed", "exit_code": code, "status_source": "observed_wrapped_exit_marker"}
    if RUNNING_RE.search(text):
        return {"status": "running", "exit_code": None, "status_source": "observed_running_marker"}
    lowered = text.lower()
    if tool_name in EDIT_TOOLS and re.search(r"\A\s*(?:success\.|done!)(?=\s|$)", text, re.I):
        return {
            "status": "passed",
            "exit_code": None,
            "status_source": "observed_apply_patch_success_marker",
        }
    if re.search(r"(?:^|\n)(?:success\.|done!)(?:\n|$)", text, re.I):
        return {"status": "passed", "exit_code": None, "status_source": "observed_tool_success_marker"}
    if any(marker in lowered for marker in ("patch failed", "failed to find expected", "verification failed", "error applying patch")):
        return {"status": "failed", "exit_code": None, "status_source": "observed_tool_failure_marker"}
    return {"status": "unknown", "exit_code": None, "status_source": "no_terminal_status_marker"}


def _normalize_target(path: str, workdir: str = "") -> str | None:
    path = path.strip().strip("'\"")
    if not path or path in {"-", "/dev/null"} or any(ch in path for ch in "*$`{}"):
        return None
    candidate = Path(path)
    if candidate.is_absolute():
        if workdir:
            try:
                candidate = candidate.relative_to(Path(workdir))
            except ValueError:
                return None
        else:
            return None
    normalized = PurePosixPath(str(candidate).replace("\\", "/"))
    if ".." in normalized.parts:
        return None
    text = str(normalized).lstrip("./")
    return text or None


def _patch_details(raw_patch: str, *, edit_format: str, call_line: int, sequence: int) -> dict[str, Any] | None:
    operations: Counter[str] = Counter()
    targets: list[str] = []
    for line in raw_patch.splitlines():
        match = PATCH_HEADER_RE.match(line.strip())
        if match:
            operations[match.group("op").lower()] += 1
            target = _normalize_target(match.group("path"))
            if target:
                targets.append(target)
    if not targets:
        return None
    return {
        "action_sequence": sequence,
        "call_line_number": call_line,
        "edit_format": edit_format,
        "operation_counts": dict(sorted(operations.items())),
        "payload_observed": True,
        "payload_sha256": sha256_bytes(raw_patch.encode("utf-8")),
        "payload_size_bytes": len(raw_patch.encode("utf-8")),
        "target_path_sha256": sorted({sha256_bytes(path.encode("utf-8")) for path in targets}),
        "raw_payload_emitted": False,
        "_targets": sorted(set(targets)),
    }


def patch_fact(tool_name: str, payload: dict[str, Any], args: dict[str, Any], *, call_line: int = 0, sequence: int = 0) -> dict[str, Any] | None:
    if tool_name not in EDIT_TOOLS:
        return None
    raw_patch = args.get("patch") or payload.get("input") or args.get("input")
    if not isinstance(raw_patch, str):
        return None
    return _patch_details(raw_patch, edit_format="apply_patch", call_line=call_line, sequence=sequence)

def _exec_edit_fact(command: str, args: dict[str, Any], *, call_line: int, sequence: int) -> dict[str, Any] | None:
    if "*** Begin Patch" in command and "*** End Patch" in command:
        start = command.find("*** Begin Patch")
        end = command.rfind("*** End Patch") + len("*** End Patch")
        return _patch_details(command[start:end], edit_format="exec_apply_patch", call_line=call_line, sequence=sequence)

    workdir = str(args.get("workdir") or "")
    targets: list[str] = []
    shell_surface = command
    python_body = ""
    heredoc = re.search(r"<<-?\s*['\"]?(?P<marker>[A-Za-z_][A-Za-z0-9_]*)['\"]?[^\n]*\n", command)
    if heredoc:
        marker = heredoc.group("marker")
        body_start = heredoc.end()
        terminator = re.search(rf"(?m)^\s*{re.escape(marker)}\s*$", command[body_start:])
        if terminator:
            python_body = command[body_start : body_start + terminator.start()]
        shell_surface = command[: heredoc.start()]
    for match in re.finditer(r"(?<![<>=])(?:>>|>(?!=))\s*([^\s;&|]+)", shell_surface):
        target = _normalize_target(match.group(1), workdir)
        if target:
            targets.append(target)
    tokens = _shell_tokens(shell_surface)
    basenames = [Path(token).name for token in tokens]
    for idx, base in enumerate(basenames):
        if base == "sed" and "-i" in tokens[idx + 1 :]:
            for token in tokens[idx + 1 :]:
                if not token.startswith("-") and not token.startswith("s/"):
                    target = _normalize_target(token, workdir)
                    if target and ("/" in target or "." in Path(target).name):
                        targets.append(target)
        elif base == "tee" and idx + 1 < len(tokens):
            for token in tokens[idx + 1 :]:
                if not token.startswith("-"):
                    target = _normalize_target(token, workdir)
                    if target:
                        targets.append(target)
        elif base in {"touch", "truncate"} and idx + 1 < len(tokens):
            for token in tokens[idx + 1 :]:
                if not token.startswith("-"):
                    target = _normalize_target(token, workdir)
                    if target:
                        targets.append(target)
    if python_body and any(Path(token).name.startswith("python") for token in tokens):
        targets.extend(_python_write_targets(python_body, workdir))
    targets = sorted(set(targets))
    if not targets:
        return None
    payload = {"command_sha256": sha256_bytes(command.encode("utf-8")), "targets": targets}
    return {
        "action_sequence": sequence,
        "call_line_number": call_line,
        "edit_format": "exec_command_mutation",
        "operation_counts": {"update": len(targets)},
        "payload_observed": True,
        "payload_sha256": sha256_json(payload),
        "payload_size_bytes": len(command.encode("utf-8")),
        "target_path_sha256": [sha256_bytes(path.encode("utf-8")) for path in targets],
        "raw_payload_emitted": False,
        "_targets": targets,
    }


def _python_write_targets(source: str, workdir: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    path_bindings: dict[str, str] = {}

    def literal_path(node: ast.AST) -> str | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return _normalize_target(node.value, workdir)
        if isinstance(node, ast.Name):
            return path_bindings.get(node.id)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"Path", "PurePath"} and node.args:
            return literal_path(node.args[0])
        return None

    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            target_nodes = node.targets if isinstance(node, ast.Assign) else [node.target]
            path = literal_path(value) if value is not None else None
            if path:
                for target_node in target_nodes:
                    if isinstance(target_node, ast.Name):
                        path_bindings[target_node.id] = path

    targets: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute) and node.func.attr in {"write_text", "write_bytes", "touch", "unlink"}:
            path = literal_path(node.func.value)
            if path:
                targets.append(path)
        elif isinstance(node.func, ast.Name) and node.func.id == "open" and node.args:
            mode = str(node.args[1].value) if len(node.args) > 1 and isinstance(node.args[1], ast.Constant) else ""
            for keyword in node.keywords:
                if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant):
                    mode = str(keyword.value.value)
            path = literal_path(node.args[0])
            if path and mode and any(flag in mode for flag in "wax+"):
                targets.append(path)
    return sorted(set(targets))

def explicit_no_patch_fact(events: dict[int, dict[str, Any]]) -> dict[str, Any] | None:
    for line_number, event in sorted(events.items(), reverse=True):
        payload = payload_of(event)
        if str(payload.get("role") or "") != "assistant":
            continue
        text = content_text(payload.get("content", payload.get("message")))
        for reason_code, pattern in NO_PATCH_PATTERNS:
            if pattern.search(text):
                return {
                    "reason_code": reason_code,
                    "line_number": line_number,
                    "evidence_content_sha256": sha256_bytes(text.encode("utf-8")),
                    "raw_content_emitted": False,
                }
    return None


def _verifier_targets(command: str, workdir: str = "") -> list[str]:
    targets: list[str] = []
    ignored = {"test", "tests", "check", "lint", "--", "."}
    for token in _shell_tokens(command):
        if token.startswith("-") or token in ignored:
            continue
        base = Path(token).name
        if base in {"pytest", "python", "python3", "cargo", "go", "npm", "pnpm", "yarn", "npx", "ctest", "vitest", "bash"}:
            continue
        if "/" in token or Path(token).suffix in {".py", ".rs", ".go", ".js", ".ts", ".tsx", ".jsx", ".sh"}:
            target = _normalize_target(token.split("::", 1)[0], workdir)
            if target:
                targets.append(target)
    return sorted(set(targets))


def _target_terms(path: str) -> set[str]:
    stem = Path(path).stem.lower()
    for prefix in ("test_", "tests_", "spec_"):
        if stem.startswith(prefix):
            stem = stem[len(prefix) :]
    for suffix in ("_test", "_tests", ".spec", ".test"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
    return {part for part in re.split(r"[^a-z0-9]+", stem) if len(part) >= 2}


def _linked_targets(edit_targets: Iterable[str], verifier_targets: Iterable[str]) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    for edit in edit_targets:
        edit_terms = _target_terms(edit)
        for verifier in verifier_targets:
            verifier_terms = _target_terms(verifier)
            if edit == verifier or (edit_terms and verifier_terms and edit_terms & verifier_terms):
                links.append((edit, verifier))
    return links


def resolve_source_paths(
    source_root: Path,
    inventory_by_source: dict[str, dict[str, Any]],
    wanted: set[str],
) -> tuple[dict[str, Path], dict[str, list[str]]]:
    resolved: dict[str, Path] = {}
    blockers = {source: [] for source in wanted}
    if not source_root.is_dir():
        for source in wanted:
            blockers[source].append("codex_session_root_missing_or_unreadable")
        return resolved, blockers
    for path in sorted(source_root.rglob("*.jsonl")):
        if not path.is_file():
            continue
        source = sha1_text(str(path))
        if source not in wanted:
            continue
        inventory = inventory_by_source.get(source)
        if not inventory:
            blockers[source].append("source_absent_from_stage12256_inventory")
            continue
        try:
            relative_hash = sha1_text(str(path.relative_to(source_root)))
        except ValueError:
            blockers[source].append("source_path_outside_codex_root")
            continue
        if relative_hash != str(inventory.get("relative_path_hash") or ""):
            blockers[source].append("source_inventory_relative_path_hash_mismatch")
            continue
        if source in resolved:
            blockers[source].append("ambiguous_physical_source_mapping")
            continue
        resolved[source] = path
    for source in wanted:
        if source not in inventory_by_source:
            blockers[source].append("source_absent_from_stage12256_inventory")
        if source not in resolved and not blockers[source]:
            blockers[source].append("physical_source_path_not_resolved")
    return resolved, {key: sorted(set(value)) for key, value in blockers.items()}


def read_validated_window(
    path: Path,
    source: str,
    start_line: int,
    end_line: int,
    manifest: dict[str, Any],
    inventory: dict[str, Any],
) -> tuple[dict[int, dict[str, Any]], dict[str, Any], list[str]]:
    blockers: list[str] = []
    if sha1_text(str(path)) != source:
        return {}, {}, ["physical_path_source_hash_mismatch"]
    try:
        stat = path.stat()
    except OSError:
        return {}, {}, ["physical_source_unreadable"]
    expected_sizes = {int(value) for value in (manifest.get("file_size_bytes"), inventory.get("file_size_bytes")) if isinstance(value, int)}
    if expected_sizes and stat.st_size not in expected_sizes:
        blockers.append("physical_source_size_mutated")
    expected_mtimes = {str(value) for value in (manifest.get("mtime_utc"), inventory.get("mtime_utc")) if isinstance(value, str) and value}
    observed_mtime = iso_utc(stat.st_mtime)
    if expected_mtimes and observed_mtime not in expected_mtimes:
        blockers.append("physical_source_mtime_mutated")

    digest = hashlib.sha256()
    raw_lines: dict[int, bytes] = {}
    try:
        with path.open("rb") as handle:
            for line_number, raw_line in enumerate(handle, 1):
                digest.update(raw_line)
                if start_line <= line_number <= end_line:
                    raw_lines[line_number] = raw_line
    except OSError:
        return {}, {}, sorted(set(blockers + ["physical_source_unreadable"]))
    current_sha = digest.hexdigest()
    expected_sha = str(manifest.get("file_content_sha256") or "")
    if not expected_sha or current_sha != expected_sha:
        blockers.append("physical_source_content_sha256_mutated")
    validation = {
        "source_file_hash_compat": source,
        "physical_source_id": inventory.get("physical_source_id"),
        "expected_content_sha256": expected_sha or None,
        "observed_content_sha256": current_sha if not blockers else None,
        "content_hash_match": bool(expected_sha and current_sha == expected_sha),
        "expected_file_size_bytes": manifest.get("file_size_bytes"),
        "observed_file_size_bytes": stat.st_size if not blockers else None,
        "expected_mtime_utc": manifest.get("mtime_utc"),
        "observed_mtime_utc": observed_mtime,
        "raw_path_emitted": False,
    }
    if blockers:
        return {}, validation, sorted(set(blockers))
    expected_count = end_line - start_line + 1
    if len(raw_lines) != expected_count:
        return {}, validation, ["task_window_lines_missing_from_raw_source"]
    events: dict[int, dict[str, Any]] = {}
    for line_number, raw_line in raw_lines.items():
        try:
            event = json.loads(raw_line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            blockers.append("raw_window_json_parse_failure")
            continue
        if not isinstance(event, dict):
            blockers.append("raw_window_non_object_event")
            continue
        events[line_number] = event
    return events, validation, sorted(set(blockers))


def _empty_record(candidate: dict[str, Any], window: dict[str, Any] | None) -> dict[str, Any]:
    components = candidate.get("source_session_root_window") if isinstance(candidate.get("source_session_root_window"), dict) else {}
    window_id = str(components.get("window") or candidate.get("task_window_id") or "")
    return {
        "hydration_record_id": stable_id("stage12586_hydration", candidate.get("candidate_id"), window_id),
        "record_type": "stage12586_raw_private_observed_window_v2",
        "upstream_candidate_id": candidate.get("candidate_id"),
        "source_identity": {
            "source_file_hash_compat": str(components.get("source") or ""),
            "session_id_hash": str(components.get("session") or ""),
            "root_id": str(components.get("root") or ""),
            "task_window_id": window_id,
            "recomputed_dedupe_key_sha256": stable_hash(components) if components else None,
            "same_source_join_validated": False,
        },
        "source_validation": {},
        "task_boundary": {
            "start_line": (window or {}).get("start_line"),
            "end_line": (window or {}).get("end_line"),
            "line_count": (window or {}).get("line_count"),
            "start_event_id": (window or {}).get("start_event_id"),
            "terminal_event_id": (window or {}).get("terminal_event_id"),
            "boundary_confidence": (window or {}).get("boundary_confidence"),
        },
        "observed_task_messages": [],
        "ordered_tool_actions": [],
        "paired_observations": [],
        "verifier_observations": [],
        "verifier_audit_observations": [],
        "failed_verifier_observations": [],
        "verifier_status_counts": {"passed": 0, "failed": 0},
        "transition_local_facts": {
            "first_transition_line": None,
            "last_transition_line": None,
            "pre_transition_facts": [],
            "post_transition_facts": [],
            "derived_post_state_claim_emitted": False,
        },
        "terminal_observation": {
            "present": False,
            "event_id": None,
            "line_number": None,
            "lifecycle_event": None,
            "synthetic_stop_or_continue_label_emitted": False,
        },
        "edit_evidence": {"observed_edits": [], "explicit_no_edit_reason": None},
        "classification": {"hydrated_core_status": "BLOCKED_CORE", "level3_status": "NOT_EVALUATED", "floors_credited": False},
        "guardrails": {
            "candidate_alternatives_emitted": False,
            "level3_evaluation_performed": False,
            "projection_artifacts_emitted": False,
            "training_artifacts_emitted": False,
            "raw_command_text_emitted": False,
            "raw_message_text_emitted": False,
            "raw_patch_body_emitted": False,
            "raw_source_path_emitted": False,
            "raw_tool_arguments_emitted": False,
            "raw_tool_output_emitted": False,
        },
        "blocked_reasons": [],
        "training_allowed": False,
    }


def _indexed_event_matches(raw_event: dict[str, Any], indexed: dict[str, Any]) -> bool:
    payload = payload_of(raw_event)
    return indexed_payload_digest(payload) == str(indexed.get("payload_digest_redacted") or "")


def hydrate_window(
    candidate: dict[str, Any],
    window: dict[str, Any] | None,
    manifest: dict[str, Any] | None,
    inventory: dict[str, Any] | None,
    event_rows: list[dict[str, Any]],
    pair_rows: list[dict[str, Any]],
    raw_path: Path | None,
    mapping_blockers: list[str] | None = None,
) -> dict[str, Any]:
    record = _empty_record(candidate, window)
    blockers = list(mapping_blockers or [])
    components = candidate.get("source_session_root_window") if isinstance(candidate.get("source_session_root_window"), dict) else {}
    source = str(components.get("source") or "")
    window_id = str(components.get("window") or "")
    if not window or str(window.get("task_window_id") or "") != window_id:
        blockers.append("task_window_join_missing_or_mismatched")
    if not manifest or not window or str(manifest.get("chat_id") or "") != str(window.get("chat_id") or ""):
        blockers.append("chat_manifest_join_missing_or_mismatched")
    if not inventory or str(inventory.get("source_file_hash_compat") or "") != source:
        blockers.append("physical_inventory_join_missing_or_mismatched")
    if window and manifest and not (
        str(window.get("source_file_hash_compat") or "") == source == str(manifest.get("source_file_hash_compat") or "")
    ):
        blockers.append("source_identity_join_mismatch")

    recomputed_session = stage12314_session_hash((window or {}).get("session_id_hint") or (manifest or {}).get("session_id_hint"))
    recomputed_dedupe = stable_hash({
        "source": source,
        "session": recomputed_session,
        "root": str(components.get("root") or ""),
        "window": window_id,
    })
    claimed_dedupe = str(candidate.get("dedupe_key_sha256") or "")
    if not recomputed_session or str(components.get("session") or "") != recomputed_session:
        blockers.append("recomputed_session_identity_mismatch")
    if not str(components.get("root") or "").startswith("canonical_root_"):
        blockers.append("recomputed_root_identity_invalid")
    if claimed_dedupe != recomputed_dedupe:
        blockers.append("recomputed_dedupe_identity_mismatch")
    record["source_identity"].update(
        session_id_hash=recomputed_session,
        recomputed_dedupe_key_sha256=recomputed_dedupe,
        root_identity_sha256=sha256_json(str(components.get("root") or "")),
    )

    if not raw_path or not window or not manifest or not inventory:
        blockers.append("physical_source_path_not_resolved")
        record["blocked_reasons"] = sorted(set(blockers))
        assert_safe_shape(record)
        return record
    events, validation, validation_blockers = read_validated_window(
        raw_path,
        source,
        int(window.get("start_line") or 0),
        int(window.get("end_line") or -1),
        manifest,
        inventory,
    )
    record["source_validation"] = validation
    blockers.extend(validation_blockers)
    if validation_blockers:
        record["blocked_reasons"] = sorted(set(blockers))
        assert_safe_shape(record)
        return record

    indexed_by_line = {int(row["line_number"]): row for row in event_rows if isinstance(row.get("line_number"), int)}
    for line, indexed in indexed_by_line.items():
        raw_event = events.get(line)
        if raw_event is None or not _indexed_event_matches(raw_event, indexed):
            blockers.append("raw_event_index_digest_mismatch")

    pair_by_call: dict[tuple[str, int], dict[str, Any]] = {}
    for pair in pair_rows:
        key = (str(pair.get("call_id") or ""), int(pair.get("call_line_number") or 0))
        if key in pair_by_call:
            blockers.append("duplicate_authoritative_pair")
        pair_by_call[key] = pair

    call_rows: list[dict[str, Any]] = []
    output_by_call: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    for line_number, event in sorted(events.items()):
        payload = payload_of(event)
        payload_type = str(payload.get("type") or "")
        if payload_type in {"function_call", "custom_tool_call"} and payload.get("name"):
            args = safe_json_object(payload.get("arguments"))
            if not args and isinstance(payload.get("input"), dict):
                args = dict(payload["input"])
            elif not args and isinstance(payload.get("input"), str):
                args = {"input": payload["input"]}
            call_rows.append({"line": line_number, "payload": payload, "args": args})
        elif payload_type in {"function_call_output", "custom_tool_call_output"}:
            output_by_call[str(payload.get("call_id") or "")].append((line_number, payload))

    actions: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    action_private: dict[str, dict[str, Any]] = {}
    call_id_to_action: dict[str, str] = {}
    for sequence, call in enumerate(call_rows, 1):
        line_number = call["line"]
        payload = call["payload"]
        args = call["args"]
        call_id = str(payload.get("call_id") or "")
        tool_name = str(payload.get("name") or "")
        pair = pair_by_call.get((call_id, line_number))
        outputs = output_by_call.get(call_id, [])
        if not pair or not outputs:
            blockers.append("authoritative_pair_without_raw_tool_action")
            continue
        output_line, output_payload = outputs[0]
        call_index = indexed_by_line.get(line_number, {})
        output_index = indexed_by_line.get(output_line, {})
        pair_shape_valid = bool(
            int(pair.get("output_line_number") or 0) == output_line
            and str(pair.get("chat_id") or "") == str(window.get("chat_id") or "")
            and pair.get("call_before_output") is not False
            and str(pair.get("tool_name") or "") == tool_name
            and str(pair.get("call_event_id") or "") == str(call_index.get("event_id") or "")
            and str(pair.get("output_event_id") or "") == str(output_index.get("event_id") or "")
            and str(pair.get("output_digest") or "") == str(output_index.get("payload_digest_redacted") or "")
        )
        if not pair_shape_valid:
            blockers.append("authoritative_pair_raw_join_mismatch")
            continue
        pair_arguments_digest = pair.get("arguments_digest")
        if pair_arguments_digest is not None and sha256_json(args) != str(pair_arguments_digest):
            blockers.append("authoritative_pair_arguments_digest_mismatch")
            continue
        command = str(args.get("cmd") or "") if tool_name == "exec_command" else ""
        action_id = stable_id("stage12586_action", candidate.get("candidate_id"), call_id, line_number)
        call_id_to_action[call_id] = action_id
        status = output_status(output_payload.get("output"), tool_name=tool_name)
        action = {
            "action_id": action_id,
            "sequence": sequence,
            "action_kind": "command" if tool_name in {"exec_command", "write_stdin"} else "tool",
            "tool_name": tool_name,
            "call_line_number": line_number,
            "call_id_sha256": sha256_bytes(call_id.encode("utf-8")),
            "arguments_sha256": sha256_json(args),
            "command_sha256": sha256_bytes(command.encode("utf-8")) if command else None,
            "command_head": command_head(command) if command else tool_name,
            "recognized_verifier_invocation": verifier_kind(command) if command else None,
            "recognized_state_probe": state_probe_kind(command) if command else None,
            "authoritative_pair_present": True,
            "raw_arguments_emitted": False,
            "raw_command_emitted": False,
        }
        observation = {
            "observation_id": stable_id("stage12586_observation", action_id, output_line),
            "action_id": action_id,
            "call_line_number": line_number,
            "output_line_number": output_line,
            "output_payload_type": str(output_payload.get("type") or ""),
            "output_payload_sha256": sha256_json(output_payload),
            "output_content_sha256": sha256_json(output_payload.get("output")),
            "status": status["status"],
            "exit_code": status["exit_code"],
            "status_source": status["status_source"],
            "raw_output_emitted": False,
        }
        actions.append(action)
        observations.append(observation)
        action_private[action_id] = {
            "args": args,
            "command": command,
            "payload": payload,
            "outputs": outputs,
            "status": status,
            "call_id": call_id,
        }

    # Join write_stdin polling actions back to the exec command that created the session.
    actions_by_id = {row["action_id"]: row for row in actions}
    observations_by_id = {row["action_id"]: row for row in observations}
    origin_by_session: dict[str, str] = {}
    for action in actions:
        private = action_private[action["action_id"]]
        if action["tool_name"] == "exec_command":
            text = "\n".join(content_text(payload.get("output")) for _, payload in private["outputs"])
            match = RUNNING_RE.search(text)
            if match:
                origin_by_session[match.group("session")] = action["action_id"]
        elif action["tool_name"] == "write_stdin":
            session = str(private["args"].get("session_id") or "")
            origin_id = origin_by_session.get(session)
            if not origin_id:
                blockers.append("write_stdin_originating_command_missing")
                continue
            action["originating_action_id"] = origin_id
            origin_private = action_private[origin_id]
            origin_private["outputs"].extend(private["outputs"])
            joined_output = "\n".join(content_text(payload.get("output")) for _, payload in origin_private["outputs"])
            joined_status = output_status(joined_output)
            origin_private["status"] = joined_status
            origin_observation = observations_by_id[origin_id]
            origin_observation.update(
                output_line_number=max(line for line, _ in origin_private["outputs"]),
                output_content_sha256=sha256_bytes(joined_output.encode("utf-8")),
                status=joined_status["status"],
                exit_code=joined_status["exit_code"],
                status_source=f"joined_write_stdin:{joined_status['status_source']}",
            )
            actions_by_id[origin_id].setdefault("continuation_action_ids", []).append(action["action_id"])

    edit_private: list[tuple[dict[str, Any], list[str], str]] = []
    for action in actions:
        private = action_private[action["action_id"]]
        status = observations_by_id[action["action_id"]]["status"]
        fact = patch_fact(
            action["tool_name"],
            private["payload"],
            private["args"],
            call_line=action["call_line_number"],
            sequence=action["sequence"],
        )
        if fact is None and action["tool_name"] == "exec_command":
            fact = _exec_edit_fact(
                private["command"], private["args"], call_line=action["call_line_number"], sequence=action["sequence"]
            )
        if fact is not None:
            if status != "passed":
                continue
            targets = list(fact.pop("_targets"))
            fact["action_id"] = action["action_id"]
            fact["paired_success_proof"] = True
            edit_private.append((fact, targets, action["action_id"]))

    edit_private.sort(key=lambda item: (item[0]["call_line_number"], item[0]["action_sequence"]))
    observed_edits = [fact for fact, _, _ in edit_private]
    edit_targets = [target for _, targets, _ in edit_private for target in targets]
    first_edit_line = observed_edits[0]["call_line_number"] if observed_edits else None
    last_edit_line = observed_edits[-1]["call_line_number"] if observed_edits else None

    verifiers: list[dict[str, Any]] = []
    for action in actions:
        kind = action.get("recognized_verifier_invocation")
        if not kind:
            continue
        observation = observations_by_id[action["action_id"]]
        command = action_private[action["action_id"]]["command"]
        targets = _verifier_targets(command, str(action_private[action["action_id"]]["args"].get("workdir") or ""))
        links = _linked_targets(edit_targets, targets)
        if first_edit_line is None or action["call_line_number"] < first_edit_line:
            relative = "before_first_edit"
        elif action["call_line_number"] > int(last_edit_line or first_edit_line):
            relative = "after_last_edit"
        else:
            relative = "between_edits"
        verifier = {
            "action_id": action["action_id"],
            "call_line_number": action["call_line_number"],
            "output_line_number": observation["output_line_number"],
            "command_sha256": action["command_sha256"],
            "invocation_kind": kind,
            "status": observation["status"],
            "exit_code": observation["exit_code"],
            "status_source": observation["status_source"],
            "completed": observation["status"] in {"passed", "failed"},
            "failed": observation["status"] == "failed",
            "observed_order_relative_to_edits": relative,
            "target_path_sha256": [sha256_bytes(path.encode("utf-8")) for path in targets],
            "linked_edit_action_ids": sorted({edit_id for _, edit_targets_for_action, edit_id in edit_private if any(e == link[0] for link in links for e in edit_targets_for_action)}),
            "patch_test_target_linked": bool(links),
            "relevant_to_observed_edit": bool(links),
        }
        verifiers.append(verifier)

    state_facts: list[dict[str, Any]] = []
    for action in actions:
        probe = action.get("recognized_state_probe")
        observation = observations_by_id[action["action_id"]]
        if not probe or observation["status"] != "passed":
            continue
        state_facts.append(
            {
                "fact_type": probe,
                "action_id": action["action_id"],
                "call_line_number": action["call_line_number"],
                "output_line_number": observation["output_line_number"],
                "output_content_sha256": observation["output_content_sha256"],
                "status": "passed",
                "repo_probe_success": True,
                "raw_state_emitted": False,
            }
        )
    pre_facts = [fact for fact in state_facts if first_edit_line is not None and fact["call_line_number"] < first_edit_line]
    post_facts = [fact for fact in state_facts if last_edit_line is not None and fact["call_line_number"] > last_edit_line]

    task_messages: list[dict[str, Any]] = []
    for line_number, event in sorted(events.items()):
        payload = payload_of(event)
        if str(payload.get("role") or "") == "user" and str(payload.get("type") or "") in {"message", "user_message"}:
            task_messages.append(message_digest_fact(line_number, payload))

    terminal_line = int(window.get("end_line") or -1)
    terminal_payload = payload_of(events.get(terminal_line, {}))
    terminal_type = str(terminal_payload.get("type") or "")
    terminal_present = bool(
        terminal_type in {"task_complete", "turn_aborted"}
        and terminal_type == str(window.get("terminal_status") or "")
        and str(indexed_by_line.get(terminal_line, {}).get("event_id") or "") == str(window.get("terminal_event_id") or "")
    )

    explicit_no_edit = explicit_no_patch_fact(events) if not observed_edits else None
    if not task_messages:
        blockers.append("observed_task_message_missing")
    if not actions:
        blockers.append("ordered_tool_actions_missing")
    if not observed_edits and explicit_no_edit is None:
        blockers.append("edit_payload_or_explicit_no_patch_reason_missing")
    completed_verifiers = [row for row in verifiers if row["completed"]]
    if not completed_verifiers:
        blockers.append("completed_verifier_invocation_not_observed")
    relevant_post = [
        row for row in completed_verifiers if row["observed_order_relative_to_edits"] == "after_last_edit" and row["patch_test_target_linked"]
    ]
    if observed_edits and not relevant_post:
        blockers.append("post_edit_relevant_verifier_not_observed")
    if observed_edits and not pre_facts:
        blockers.append("pre_transition_successful_repo_probe_missing")
    if observed_edits and not post_facts:
        blockers.append("post_transition_successful_repo_probe_missing")
    if not terminal_present:
        blockers.append("literal_terminal_lifecycle_event_missing_or_mismatched")

    same_source_join = not any(
        blocker
        for blocker in blockers
        if blocker.startswith(("task_window_", "chat_manifest_", "physical_inventory_", "source_identity_", "recomputed_", "duplicate_"))
    )
    record["source_identity"]["same_source_join_validated"] = same_source_join
    record["observed_task_messages"] = task_messages
    record["ordered_tool_actions"] = actions
    record["paired_observations"] = observations
    record["verifier_audit_observations"] = verifiers
    record["failed_verifier_observations"] = [row for row in relevant_post if row["failed"]]
    record["verifier_observations"] = relevant_post
    record["verifier_status_counts"] = {
        "passed": sum(row["status"] == "passed" for row in verifiers),
        "failed": sum(row["status"] == "failed" for row in verifiers),
        "incomplete": sum(not row["completed"] for row in verifiers),
        "relevant_post_edit_completed": len(relevant_post),
    }
    record["transition_local_facts"] = {
        "first_transition_line": first_edit_line,
        "last_transition_line": last_edit_line,
        "pre_transition_facts": pre_facts,
        "post_transition_facts": post_facts,
        "derived_post_state_claim_emitted": False,
    }
    record["terminal_observation"] = {
        "present": terminal_present,
        "event_id": window.get("terminal_event_id") if terminal_present else None,
        "line_number": terminal_line if terminal_present else None,
        "lifecycle_event": terminal_type if terminal_present else None,
        "synthetic_stop_or_continue_label_emitted": False,
    }
    record["edit_evidence"] = {"observed_edits": observed_edits, "explicit_no_edit_reason": explicit_no_edit}
    record["blocked_reasons"] = sorted(set(blockers))
    if not record["blocked_reasons"]:
        record["classification"]["hydrated_core_status"] = "HYDRATED_CORE"
    assert_safe_shape(record)
    return record


def select_canonical(
    candidates: list[dict[str, Any]], expected_count: int | None = 32
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    canonical = [row for row in candidates if row.get("canonical_for_dedupe_key") is True]
    if expected_count is not None and len(canonical) != expected_count:
        raise GateError(f"stage12585_canonical_count_mismatch:{len(canonical)}:{expected_count}")
    natural = [row for row in canonical if row.get("source_kind") == "same_session_observed_trace"]
    excluded = [row for row in canonical if row.get("source_kind") != "same_session_observed_trace"]
    for row in natural:
        if row.get("duplicate_of") is not None or row.get("exact_same_source_join") is not True:
            raise GateError(f"stage12585_noncanonical_or_inexact_natural_record:{row.get('candidate_id')}")
    return natural, excluded


def execute(
    *,
    out: Path = OUT,
    summary_path: Path = SUMMARY,
    candidate_path: Path = STAGE12585,
    physical_path: Path = PHYSICAL,
    chat_path: Path = CHATS,
    event_path: Path = EVENTS,
    pair_path: Path = PAIRS,
    window_path: Path = WINDOWS,
    codex_root: Path = CODEX_SESSIONS,
    expected_canonical_count: int | None = 32,
) -> dict[str, Any]:
    input_paths = {
        "stage12585_candidates": candidate_path,
        "stage12256_physical_inventory": physical_path,
        "stage12258_chat_manifest": chat_path,
        "stage12258_event_index": event_path,
        "stage12259_pair_index": pair_path,
        "stage12260_task_windows": window_path,
    }
    natural, excluded = select_canonical(read_jsonl(candidate_path), expected_canonical_count)
    wanted_windows = {str(row["source_session_root_window"]["window"]) for row in natural}
    wanted_sources = {str(row["source_session_root_window"]["source"]) for row in natural}
    window_by_id = index_unique(
        (row for row in iter_jsonl(window_path) if str(row.get("task_window_id") or "") in wanted_windows),
        "task_window_id",
        "window",
    )
    wanted_chats = {str(row.get("chat_id") or "") for row in window_by_id.values()}
    manifest_by_chat = index_unique(
        (row for row in iter_jsonl(chat_path) if str(row.get("chat_id") or "") in wanted_chats),
        "chat_id",
        "chat",
    )
    inventory_by_source = index_unique(
        (row for row in iter_jsonl(physical_path) if str(row.get("source_file_hash_compat") or "") in wanted_sources),
        "source_file_hash_compat",
        "physical_source",
    )
    resolved_paths, source_mapping_blockers = resolve_source_paths(codex_root, inventory_by_source, wanted_sources)

    ranges_by_chat: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for window in window_by_id.values():
        ranges_by_chat[str(window.get("chat_id") or "")].append((int(window.get("start_line") or 0), int(window.get("end_line") or -1)))
    events_by_chat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in iter_jsonl(event_path):
        chat = str(row.get("chat_id") or "")
        line = int(row.get("line_number") or 0)
        if any(start <= line <= end for start, end in ranges_by_chat.get(chat, [])):
            events_by_chat[chat].append(row)
    pairs_by_chat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in iter_jsonl(pair_path):
        chat = str(row.get("chat_id") or "")
        line = int(row.get("call_line_number") or 0)
        if any(start <= line <= end for start, end in ranges_by_chat.get(chat, [])):
            pairs_by_chat[chat].append(row)

    identity_blockers: dict[str, list[str]] = defaultdict(list)
    seen_dedupe: dict[str, str] = {}
    seen_root: dict[str, str] = {}
    recomputed_sessions: set[str] = set()
    recomputed_dedupes: set[str] = set()
    recomputed_roots: set[str] = set()
    for candidate in natural:
        candidate_id = str(candidate.get("candidate_id") or "")
        components = candidate.get("source_session_root_window") if isinstance(candidate.get("source_session_root_window"), dict) else {}
        window = window_by_id.get(str(components.get("window") or ""), {})
        manifest = manifest_by_chat.get(str(window.get("chat_id") or ""), {})
        session = stage12314_session_hash(window.get("session_id_hint") or manifest.get("session_id_hint")) or ""
        root = str(components.get("root") or "")
        dedupe = stable_hash({"source": str(components.get("source") or ""), "session": session, "root": root, "window": str(components.get("window") or "")})
        recomputed_sessions.add(session)
        recomputed_roots.add(root)
        recomputed_dedupes.add(dedupe)
        if dedupe in seen_dedupe:
            identity_blockers[candidate_id].append("duplicate_recomputed_dedupe_identity")
            identity_blockers[seen_dedupe[dedupe]].append("duplicate_recomputed_dedupe_identity")
        else:
            seen_dedupe[dedupe] = candidate_id
        if root in seen_root:
            identity_blockers[candidate_id].append("duplicate_recomputed_root_identity")
            identity_blockers[seen_root[root]].append("duplicate_recomputed_root_identity")
        else:
            seen_root[root] = candidate_id

    records: list[dict[str, Any]] = []
    for candidate in sorted(natural, key=lambda row: str(row.get("candidate_id") or "")):
        candidate_id = str(candidate.get("candidate_id") or "")
        components = candidate.get("source_session_root_window") if isinstance(candidate.get("source_session_root_window"), dict) else {}
        source = str(components.get("source") or "")
        window = window_by_id.get(str(components.get("window") or ""))
        chat = str((window or {}).get("chat_id") or "")
        blockers = source_mapping_blockers.get(source, []) + identity_blockers.get(candidate_id, [])
        start_line = int((window or {}).get("start_line") or 0)
        end_line = int((window or {}).get("end_line") or -1)
        window_events = [row for row in events_by_chat.get(chat, []) if start_line <= int(row.get("line_number") or 0) <= end_line]
        window_pairs = [row for row in pairs_by_chat.get(chat, []) if start_line <= int(row.get("call_line_number") or 0) <= end_line]
        records.append(
            hydrate_window(
                candidate,
                window,
                manifest_by_chat.get(chat),
                inventory_by_source.get(source),
                window_events,
                window_pairs,
                resolved_paths.get(source),
                blockers,
            )
        )

    blocked_rows = [
        {
            "hydration_record_id": row["hydration_record_id"],
            "upstream_candidate_id": row["upstream_candidate_id"],
            "task_window_id": row["source_identity"]["task_window_id"],
            "blocked_reasons": row["blocked_reasons"],
            "training_allowed": False,
        }
        for row in records
        if row["blocked_reasons"]
    ]
    excluded_rows = [
        {
            "upstream_candidate_id": row.get("candidate_id"),
            "source_kind": row.get("source_kind"),
            "reason": "canonical_replay_only_not_natural_same_session_window",
            "hydrated": False,
            "training_allowed": False,
        }
        for row in excluded
    ]
    blocker_counts = Counter(reason for row in records for reason in row["blocked_reasons"])
    source_hash_matches = {
        str(row["source_identity"]["source_file_hash_compat"])
        for row in records
        if row["source_validation"].get("content_hash_match") is True
    }
    summary = {
        "stage": STAGE,
        "status": "RAW_PRIVATE_HYDRATION_COMPLETE",
        "decision": "hydrated_core_only_level3_not_evaluated_no_training",
        "claim_boundary": (
            "Raw-private reconstruction of natural Stage12585 canonical Codex windows using only Stage12256, "
            "Stage12258, Stage12259, Stage12260, and privately reopened immutable source files. No candidate "
            "alternatives, derived post-state claims, verifier inference without target linkage, synthetic stop labels, "
            "Level3 review, floor credit, projection, admission, or training artifacts."
        ),
        "training_allowed": False,
        "counts": {
            "stage12585_canonical_records": len(natural) + len(excluded),
            "natural_same_session_windows_selected": len(natural),
            "replay_only_records_excluded": len(excluded),
            "distinct_source_hashes_requested": len(wanted_sources),
            "physical_source_paths_resolved_privately": len(resolved_paths),
            "physical_sources_content_hash_validated": len(source_hash_matches),
            "hydration_records": len(records),
            "hydrated_core_records": sum(not row["blocked_reasons"] for row in records),
            "blocked_core_records": sum(bool(row["blocked_reasons"]) for row in records),
            "ordered_tool_actions": sum(len(row["ordered_tool_actions"]) for row in records),
            "paired_observations": sum(len(row["paired_observations"]) for row in records),
            "observed_edit_actions": sum(len(row["edit_evidence"]["observed_edits"]) for row in records),
            "verifier_audit_observations": sum(len(row["verifier_audit_observations"]) for row in records),
            "explicit_no_edit_reasons": sum(row["edit_evidence"]["explicit_no_edit_reason"] is not None for row in records),
            "verifier_observations": sum(len(row["verifier_observations"]) for row in records),
            "completed_verifier_observations": sum(row["verifier_status_counts"].get("passed", 0) + row["verifier_status_counts"].get("failed", 0) for row in records),
            "failed_verifier_observations": sum(row["verifier_status_counts"].get("failed", 0) for row in records),
            "literal_terminal_observations": sum(row["terminal_observation"]["present"] for row in records),
        },
        "identity_recomputation": {
            "distinct_sessions": len(recomputed_sessions),
            "distinct_roots": len(recomputed_roots),
            "distinct_dedupe_keys": len(recomputed_dedupes),
            "root_identity_unique": len(recomputed_roots) == len(natural),
            "dedupe_identity_unique": len(recomputed_dedupes) == len(natural),
        },
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "classification_contract": {
            "hydrated_core_classified_separately": True,
            "level3_status": "NOT_EVALUATED",
            "floors_credited": {"level3_plus": 0, "patch_trace_episodes": 0, "repositories": 0},
        },
        "artifact_contract": {
            "raw_private_records": "raw_private_observed_windows.jsonl",
            "blocked_reasons": "blocked_reasons.jsonl",
            "excluded_replay_records": "excluded_replay_records.jsonl",
            "training_artifacts_emitted": False,
            "projection_artifacts_emitted": False,
            "records_authorized_for_training": 0,
        },
        "execution_contract": {
            "cpu_only": True,
            "conda_environment": "ai",
            "raw_paths_emitted": False,
            "raw_payloads_emitted": False,
            "training_allowed": False,
        },
        "input_sha256": {name: file_sha256(path) for name, path in sorted(input_paths.items())},
    }
    for value in (records, blocked_rows, excluded_rows, summary):
        assert_safe_shape(value)
    write_jsonl(out / "raw_private_observed_windows.jsonl", records)
    write_jsonl(out / "blocked_reasons.jsonl", blocked_rows)
    write_jsonl(out / "excluded_replay_records.jsonl", excluded_rows)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--summary", type=Path, default=SUMMARY)
    parser.add_argument("--stage12585-candidates", type=Path, default=STAGE12585)
    parser.add_argument("--physical-inventory", type=Path, default=PHYSICAL)
    parser.add_argument("--chat-manifest", type=Path, default=CHATS)
    parser.add_argument("--event-index", type=Path, default=EVENTS)
    parser.add_argument("--pair-index", type=Path, default=PAIRS)
    parser.add_argument("--task-windows", type=Path, default=WINDOWS)
    parser.add_argument("--codex-root", type=Path, default=CODEX_SESSIONS)
    parser.add_argument("--expected-canonical-count", type=int, default=32)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = execute(
        out=args.out,
        summary_path=args.summary,
        candidate_path=args.stage12585_candidates,
        physical_path=args.physical_inventory,
        chat_path=args.chat_manifest,
        event_path=args.event_index,
        pair_path=args.pair_index,
        window_path=args.task_windows,
        codex_root=args.codex_root,
        expected_canonical_count=args.expected_canonical_count,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
