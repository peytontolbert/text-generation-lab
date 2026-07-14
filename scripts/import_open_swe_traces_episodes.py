from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from long_context_common import approx_token_count, extract_terms, stable_id, write_json, write_jsonl

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_GLOB = "/arxiv/datasets/nvidia--Open-SWE-Traces/data/**/*.parquet"
DEFAULT_OUTPUT_PATH = ROOT / "runs" / "local" / "artifacts" / "open_swe_trace_episodes_v1" / "open_swe_trace_episodes.jsonl"
PATCH_PLUS_VERIFY = "PATCH_PLUS_VERIFY"
VERIFICATION_MARKERS = ("pytest", "FAILED", "PASSED", "ERROR", "Traceback", "AssertionError", "TypeError")
EXECUTION_TOOL_NAMES = {"execute_bash", "run_tests", "bash", "shell"}
TEST_PATH_RE = re.compile(r"(?:^|[^A-Za-z0-9_./-])((?:tests?|test)/[A-Za-z0-9_./-]+\.py(?:::[A-Za-z0-9_]+)*)")
DIFF_HEADER_RE = re.compile(r"^diff --git a/(.+?) b/(.+?)$", re.MULTILINE)
ISSUE_RE = re.compile(r"<issue_description>\s*(.*?)\s*</issue_description>", re.DOTALL | re.IGNORECASE)
BACKTICK_RE = re.compile(r"`([^`]+)`")
DEF_RE = re.compile(r"^\s*(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE)
ERROR_TYPE_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception|Warning))\b")


def _ordered_unique(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _safe_json_loads(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _normalize_path(path: str, *, repo_root_hint: str | None) -> str:
    value = str(path or "").replace("\\", "/").strip()
    if not value:
        return ""
    if repo_root_hint and value.startswith(repo_root_hint.rstrip("/") + "/"):
        value = value[len(repo_root_hint.rstrip("/") + "/") :]
    if value.startswith("/workspace/"):
        pieces = value.split("/")
        if len(pieces) >= 4:
            value = "/".join(pieces[3:])
    return value.lstrip("./")


def _extract_issue_text(trajectory: list[dict[str, Any]]) -> tuple[str, str | None]:
    for turn_index, turn in enumerate(trajectory):
        if str(turn.get("role") or "") != "user":
            continue
        content = str(turn.get("content") or "")
        issue_match = ISSUE_RE.search(content)
        repo_root = None
        upload_start = content.find("<uploaded_files>")
        upload_end = content.find("</uploaded_files>")
        if upload_start != -1 and upload_end != -1 and upload_end > upload_start:
            uploaded_block = content[upload_start + len("<uploaded_files>") : upload_end].strip()
            first_line = next((line.strip() for line in uploaded_block.splitlines() if line.strip()), "")
            repo_root = first_line if first_line else None
        if issue_match:
            return issue_match.group(1).strip(), repo_root
        stripped = content.strip()
        if stripped:
            return stripped, repo_root
    return "", None


def _parse_patch_files(model_patch: str) -> tuple[list[str], dict[str, str]]:
    lines = str(model_patch or "").splitlines()
    changed_paths: list[str] = []
    patch_by_path: dict[str, list[str]] = {}
    current_path = ""
    for line in lines:
        match = DIFF_HEADER_RE.match(line)
        if match:
            current_path = match.group(2).strip()
            changed_paths.append(current_path)
            patch_by_path.setdefault(current_path, []).append(line)
            continue
        if current_path:
            patch_by_path[current_path].append(line)
    return _ordered_unique(changed_paths), {path: "\n".join(chunk_lines).strip() for path, chunk_lines in patch_by_path.items()}


def _extract_seed_symbols(issue_text: str, patch_by_path: dict[str, str]) -> list[str]:
    symbols: list[str] = []
    for value in BACKTICK_RE.findall(issue_text):
        symbols.append(value.strip())
    for patch_text in patch_by_path.values():
        symbols.extend(DEF_RE.findall(patch_text))
    if not symbols:
        symbols.extend(extract_terms(issue_text, max_terms=12))
    return _ordered_unique(symbols)[:16]


def _content_has_verification_signal(content: str) -> bool:
    text = str(content or "")
    if any(marker in text for marker in VERIFICATION_MARKERS):
        return True
    return bool(TEST_PATH_RE.search(text))


def _is_test_target(value: str) -> bool:
    target = str(value or "").strip()
    if not target:
        return False
    path_only = target.split("::", 1)[0]
    name = Path(path_only).name
    if "::" in target:
        return True
    if name == "conftest.py":
        return False
    return name.startswith("test_") or name.endswith("_test.py")


def _extract_test_targets(text: str) -> list[str]:
    values = []
    for match in TEST_PATH_RE.finditer(str(text or "")):
        candidate = match.group(1).strip()
        if _is_test_target(candidate):
            values.append(candidate)
    return _ordered_unique(values)


def _extract_error_types(text: str) -> list[str]:
    return _ordered_unique(ERROR_TYPE_RE.findall(str(text or "")))


def _tool_name_from_turn(turn: dict[str, Any]) -> str:
    tool_calls = turn.get("tool_calls") or []
    if not isinstance(tool_calls, list) or not tool_calls:
        return ""
    first = tool_calls[0] or {}
    function = (first.get("function") or {}) if isinstance(first, dict) else {}
    return str(function.get("name") or "")


def _tool_args_from_turn(turn: dict[str, Any]) -> dict[str, Any]:
    tool_calls = turn.get("tool_calls") or []
    if not isinstance(tool_calls, list) or not tool_calls:
        return {}
    first = tool_calls[0] or {}
    function = (first.get("function") or {}) if isinstance(first, dict) else {}
    return _safe_json_loads(str(function.get("arguments") or ""))


def _trace_context_rows(
    *,
    trajectory: list[dict[str, Any]],
    repo_root_hint: str | None,
    changed_paths: list[str],
    patch_by_path: dict[str, str],
    issue_text: str,
    source_id: str,
    episode_id: str,
) -> tuple[list[dict[str, Any]], list[str], dict[str, list[str]]]:
    context_rows: list[dict[str, Any]] = []
    verification_targets: list[str] = []
    trace_failure_types: list[str] = []
    trace_exception_types: list[str] = []

    changed_path_set = set(changed_paths)
    if issue_text:
        context_rows.append(
            {
                "chunk_id": stable_id("openswe", episode_id, "issue"),
                "source_type": "dataset",
                "source_id": source_id,
                "path": "issue_description.txt",
                "token_count": approx_token_count(issue_text),
                "text": issue_text,
                "role": "repo_graph_neighbor",
                "retrieval_reason": "trace_issue_description",
            }
        )

    for path in changed_paths:
        patch_text = patch_by_path.get(path, "")
        if not patch_text:
            continue
        context_rows.append(
            {
                "chunk_id": stable_id("openswe", episode_id, path, "patch"),
                "source_type": "dataset",
                "source_id": source_id,
                "path": path,
                "token_count": approx_token_count(patch_text),
                "text": patch_text,
                "role": "seed_change",
                "retrieval_reason": "trace_model_patch",
            }
        )

    pending_tool_name = ""
    pending_tool_args: dict[str, Any] = {}
    for turn_index, turn in enumerate(trajectory):
        role = str(turn.get("role") or "")
        if role == "assistant":
            pending_tool_name = _tool_name_from_turn(turn)
            pending_tool_args = _tool_args_from_turn(turn)
            continue
        if role != "tool":
            continue
        content = str(turn.get("content") or "").strip()
        if not content:
            pending_tool_name = ""
            pending_tool_args = {}
            continue

        raw_path = str(pending_tool_args.get("path") or "")
        normalized_path = _normalize_path(raw_path, repo_root_hint=repo_root_hint)
        if pending_tool_name == "str_replace_editor" and normalized_path:
            if normalized_path in changed_path_set:
                context_rows.append(
                    {
                        "chunk_id": stable_id("openswe", episode_id, normalized_path, "view", str(turn_index)),
                        "source_type": "dataset",
                        "source_id": source_id,
                        "path": normalized_path,
                        "token_count": approx_token_count(content),
                        "text": content,
                        "role": "seed_change",
                        "retrieval_reason": "trace_file_view",
                    }
                )
            elif _is_test_target(normalized_path):
                context_rows.append(
                    {
                        "chunk_id": stable_id("openswe", episode_id, normalized_path, "testview", str(turn_index)),
                        "source_type": "dataset",
                        "source_id": source_id,
                        "path": normalized_path,
                        "token_count": approx_token_count(content),
                        "text": content,
                        "role": "verification_constraint",
                        "retrieval_reason": "trace_test_view",
                    }
                )
                verification_targets.extend(_extract_test_targets(normalized_path))
            elif content and any(part in normalized_path for part in ("src/", "lib/", "pkg/")):
                context_rows.append(
                    {
                        "chunk_id": stable_id("openswe", episode_id, normalized_path, "neighbor", str(turn_index)),
                        "source_type": "dataset",
                        "source_id": source_id,
                        "path": normalized_path,
                        "token_count": approx_token_count(content),
                        "text": content,
                        "role": "repo_graph_neighbor",
                        "retrieval_reason": "trace_neighbor_view",
                    }
                )

        if pending_tool_name in EXECUTION_TOOL_NAMES and _content_has_verification_signal(content):
            tests = _extract_test_targets(content)
            error_types = _extract_error_types(content)
            verification_targets.extend(tests)
            trace_exception_types.extend(error_types)
            if "Traceback" in content:
                trace_failure_types.append("Traceback")
            if "FAILED" in content:
                trace_failure_types.append("FAILED")
            if "ERROR" in content:
                trace_failure_types.append("ERROR")
            if "PASSED" in content:
                trace_failure_types.append("PASSED")
            context_rows.append(
                {
                    "chunk_id": stable_id("openswe", episode_id, str(len(context_rows)), "verify"),
                    "source_type": "dataset",
                    "source_id": source_id,
                    "path": tests[0] if tests else "trace/verification_output.txt",
                    "token_count": approx_token_count(content),
                    "text": content,
                    "role": "verification_constraint",
                    "retrieval_reason": "trace_verification_output",
                }
            )

        pending_tool_name = ""
        pending_tool_args = {}

    return context_rows, _ordered_unique(verification_targets), {
        "trace_failure_types": _ordered_unique(trace_failure_types),
        "trace_exception_types": _ordered_unique(trace_exception_types),
    }


def _build_episode(row: dict[str, Any], *, dataset_name: str) -> dict[str, Any] | None:
    if int(row.get("resolved") or 0) != 1:
        return None
    trajectory = row.get("trajectory") or []
    if not isinstance(trajectory, list) or not trajectory:
        return None
    issue_text, repo_root_hint = _extract_issue_text(trajectory)
    if not issue_text:
        return None
    model_patch = str(row.get("model_patch") or "")
    changed_paths, patch_by_path = _parse_patch_files(model_patch)
    if not changed_paths:
        return None
    seed_symbols = _extract_seed_symbols(issue_text, patch_by_path)
    episode_id = stable_id("openswe", str(row.get("instance_id") or ""), str(row.get("trajectory_id") or ""))
    context_rows, verification_targets, trace_meta = _trace_context_rows(
        trajectory=trajectory,
        repo_root_hint=repo_root_hint,
        changed_paths=changed_paths,
        patch_by_path=patch_by_path,
        issue_text=issue_text,
        source_id=dataset_name,
        episode_id=episode_id,
    )
    if not verification_targets:
        return None
    roles = Counter(str(context_row.get("role") or "") for context_row in context_rows)
    if roles.get("seed_change", 0) == 0 or roles.get("verification_constraint", 0) == 0:
        return None
    goal = " ".join(line.strip() for line in issue_text.splitlines() if line.strip())
    repo_id = str(row.get("repo") or "").strip()
    metadata = dict(row.get("metadata") or {})
    expected_patch_summary = f"Apply the verified patch for {', '.join(changed_paths[:4])} to resolve the traced issue."
    expected_outcome = f"Preserve behavior while satisfying traced verification targets: {', '.join(verification_targets[:6])}."
    return {
        "episode_id": episode_id,
        "repo_id": repo_id,
        "seed_type": "open_swe_trace_episode",
        "goal": goal,
        "seed_paths": changed_paths,
        "seed_symbols": seed_symbols,
        "selected_tests": verification_targets,
        "candidate_file_count": int(metadata.get("num_modified_files") or len(changed_paths)),
        "context_rows": context_rows,
        "context_token_count": sum(int(context_row.get("token_count") or 0) for context_row in context_rows),
        "context_role_counts": dict(sorted(roles.items())),
        "test_selection_route": "TRACE_VERIFICATION_DISCOVERY",
        "target": {
            "expected_patch_summary": expected_patch_summary,
            "expected_outcome": expected_outcome,
            "state_after": {
                "expected_changed_files": changed_paths,
                "verification_targets": verification_targets,
                "execution_route": PATCH_PLUS_VERIFY,
            },
        },
        "source_metadata": {
            "dataset_name": dataset_name,
            "instance_id": str(row.get("instance_id") or ""),
            "trajectory_id": str(row.get("trajectory_id") or ""),
            "license": str(row.get("license") or ""),
            "language": str(row.get("language") or ""),
            "category": str(metadata.get("category") or ""),
            "num_modified_lines": int(metadata.get("num_modified_lines") or 0),
            "route": PATCH_PLUS_VERIFY,
            "trace_verification_targets": verification_targets,
            "trace_failure_types": list(trace_meta["trace_failure_types"]),
            "trace_exception_types": list(trace_meta["trace_exception_types"]),
        },
    }


def import_open_swe_traces_episodes(
    *,
    input_glob: str = DEFAULT_INPUT_GLOB,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    limit: int | None = None,
    dataset_name: str = "nvidia--Open-SWE-Traces",
) -> dict[str, Any]:
    import pyarrow.parquet as pq

    rows_out: list[dict[str, Any]] = []
    skipped = Counter()
    scanned_files = 0
    scanned_rows = 0
    for parquet_path in sorted(Path("/").glob(input_glob.lstrip("/")) if input_glob.startswith("/") else ROOT.glob(input_glob)):
        scanned_files += 1
        table = pq.read_table(parquet_path)
        for row in table.to_pylist():
            scanned_rows += 1
            episode = _build_episode(row, dataset_name=dataset_name)
            if episode is None:
                reason = "weak_or_incomplete_trace"
                if int(row.get("resolved") or 0) != 1:
                    reason = "unresolved"
                elif not str(row.get("model_patch") or "").strip():
                    reason = "missing_patch"
                skipped[reason] += 1
                continue
            rows_out.append(episode)
            if limit is not None and len(rows_out) >= limit:
                break
        if limit is not None and len(rows_out) >= limit:
            break
    if not rows_out:
        raise ValueError("no_open_swe_trace_episodes_imported")
    write_jsonl(output_path, rows_out)
    summary = {
        "input_glob": input_glob,
        "output_path": str(output_path.resolve()),
        "dataset_name": dataset_name,
        "scanned_files": scanned_files,
        "scanned_rows": scanned_rows,
        "imported_rows": len(rows_out),
        "skipped_counts": dict(sorted(skipped.items())),
        "seed_type_counts": {"open_swe_trace_episode": len(rows_out)},
    }
    write_json(output_path.with_name("open_swe_trace_episodes_summary.json"), summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Import resolved Open-SWE traces into the canonical strict long-context episode schema.")
    parser.add_argument("--input-glob", default=DEFAULT_INPUT_GLOB)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dataset-name", default="nvidia--Open-SWE-Traces")
    args = parser.parse_args()
    import_open_swe_traces_episodes(
        input_glob=args.input_glob,
        output_path=args.output,
        limit=args.limit,
        dataset_name=args.dataset_name,
    )


if __name__ == "__main__":
    main()
