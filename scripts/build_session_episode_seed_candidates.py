from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from long_context_common import stable_id, write_json, write_jsonl


CODE_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".java", ".go", ".rs", ".c", ".cc", ".cpp", ".h", ".hpp", ".sh"}
TEST_MARKERS = ("tests/", "/tests/", "test_", "_test.")
STRONG_TRACE_FAILURE_TYPES = {
    'test_assertion_failure',
    'runtime_contract_failure',
    'dependency_import_failure',
    'module_import_failure',
    'attribute_error',
    'type_error',
    'value_error',
    'file_not_found',
    'assertion_failure',
}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _is_test_path(path: str) -> bool:
    lower = str(path or "").lower()
    name = lower.rsplit("/", 1)[-1]
    return lower.startswith("tests/") or "/tests/" in lower or name.startswith("test_") or any(marker in lower for marker in TEST_MARKERS)


def _path_score(path: str) -> float:
    lower = str(path or "").lower()
    score = 0.0
    if any(lower.endswith(ext) for ext in CODE_EXTENSIONS):
        score += 2.0
    if _is_test_path(lower):
        score -= 0.5
    if any(part in lower for part in ["/src/", "/lib/", "/app/", "/core/", "/pkg/", "/cmd/"]):
        score += 1.0
    if any(part in lower for part in ["/dist/", "/build/", "/vendor/", "/node_modules/"]):
        score -= 2.0
    return score


def _trace_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get('source_root_label') or ''), str(row.get('session_id_hint') or ''))


def _load_trace_index(path: Path | None) -> dict[tuple[str, str], list[dict[str, Any]]]:
    if path is None or not path.exists():
        return {}
    by_session: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in _read_jsonl(path):
        by_session[_trace_key(row)].append(row)
    return by_session


def _trace_score(row: dict[str, Any]) -> float:
    signal_kind = str(row.get('signal_kind') or '')
    command = str(row.get('command') or '').lower()
    refs = [str(item) for item in row.get('file_path_refs') or [] if str(item)]
    packet = dict(row.get('runtime_trace') or {})
    failure_type = str(packet.get('failure_type') or 'unknown_runtime_failure')
    exception_type = str(packet.get('exception_type') or '')
    exit_code = row.get('exit_code')
    score = 0.0
    if signal_kind == 'verification':
        score += 2.0
    if exit_code not in (None, 0):
        score += 1.5
    if failure_type in STRONG_TRACE_FAILURE_TYPES:
        score += 2.0
    elif failure_type and failure_type != 'unknown_runtime_failure':
        score += 1.0
    if exception_type:
        score += 0.5
    if 'pytest' in command or any('test' in ref.lower() for ref in refs):
        score += 1.0
    score += min(len(refs), 8) * 0.1
    return score


def _best_trace_rows(rows: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=lambda row: (-_trace_score(row), str(row.get('trace_id') or '')))
    return ordered[:limit]


def _verification_targets(trace_rows: list[dict[str, Any]], verification_paths: list[str]) -> list[str]:
    targets: list[str] = []
    seen: set[str] = set()
    for path in verification_paths:
        value = str(path or '')
        if value and value not in seen:
            seen.add(value)
            targets.append(value)
    for row in trace_rows:
        for ref in row.get('file_path_refs') or []:
            value = str(ref or '')
            if not value or value in seen:
                continue
            if _is_test_path(value) or any(marker in value.lower() for marker in ('config', 'spec', 'verify', 'validation', 'smoke', 'check')):
                seen.add(value)
                targets.append(value)
    return targets[:8]


def _goal_text(*, changes: list[dict[str, Any]], verification_targets: list[str], trace_rows: list[dict[str, Any]], route: str) -> str:
    changed = ', '.join(str(item.get('path') or '') for item in changes[:8]) or '<none>'
    verification = ', '.join(verification_targets[:8]) or '<none>'
    failure_types = []
    exception_types = []
    command_heads = []
    for row in trace_rows[:4]:
        packet = dict(row.get('runtime_trace') or {})
        failure_type = str(packet.get('failure_type') or '')
        exception_type = str(packet.get('exception_type') or '')
        command_head = str(row.get('command_head') or '')
        if failure_type and failure_type not in failure_types:
            failure_types.append(failure_type)
        if exception_type and exception_type not in exception_types:
            exception_types.append(exception_type)
        if command_head and command_head not in command_heads:
            command_heads.append(command_head)
    lines = [
        'Modify repository files to preserve behavior under execution-backed maintenance.',
        f'Changed files: {changed}',
        f'Verification targets: {verification}',
        f'Execution route: {route}',
    ]
    if failure_types:
        lines.append(f'Observed failure types: {", ".join(failure_types[:8])}')
    if exception_types:
        lines.append(f'Observed exception types: {", ".join(exception_types[:8])}')
    if command_heads:
        lines.append(f'Observed command heads: {", ".join(command_heads[:8])}')
    return '\n'.join(lines)


def build_session_episode_seed_candidates(
    *,
    normalized_events_path: Path,
    execution_traces_path: Path | None = None,
    require_execution_traces: bool = False,
    min_trace_rows: int = 1,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    events = _read_jsonl(normalized_events_path)
    trace_index = _load_trace_index(execution_traces_path)
    by_session: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in events:
        key = (str(row.get("source_root_label") or ""), str(row.get("session_id_hint") or ""))
        by_session[key].append(row)

    seeds: list[dict[str, Any]] = []
    route_counts: Counter[str] = Counter()
    for (root_label, session_id), session_events in sorted(by_session.items()):
        normalized_counts: Counter[str] = Counter(str(event.get("normalized_event_type") or "") for event in session_events)
        tool_counts: Counter[str] = Counter(str(event.get("tool_name") or "") for event in session_events if str(event.get("tool_name") or ""))
        repo_hints: Counter[str] = Counter(str(event.get("repo_hint") or "") for event in session_events if str(event.get("repo_hint") or ""))
        patch_paths: list[str] = []
        verification_paths: list[str] = []
        all_paths: list[str] = []
        for event in session_events:
            refs = [str(ref) for ref in event.get("file_path_refs") or [] if str(ref)]
            all_paths.extend(refs)
            if str(event.get("normalized_event_type") or "") == "patch_applied":
                patch_paths.extend(refs)
            if str(event.get("normalized_event_type") or "") == "verification_command":
                verification_paths.extend(refs)

        chosen_paths = patch_paths or verification_paths or all_paths
        deduped_paths = sorted({path for path in chosen_paths if path})
        deduped_paths.sort(key=lambda path: (-_path_score(path), path))
        changes = [{"path": path} for path in deduped_paths[:8]]

        has_patch = normalized_counts["patch_applied"] > 0
        has_verify = normalized_counts["verification_command"] > 0
        has_exec = tool_counts["exec_command"] > 0 or normalized_counts.get('tool_call_exec_command', 0) > 0
        if has_patch and has_verify:
            route = "PATCH_PLUS_VERIFY"
        elif has_patch and has_exec:
            route = "PATCH_PLUS_EXEC"
        elif has_patch:
            route = "PATCH_ONLY"
        elif has_verify and deduped_paths:
            route = "VERIFY_WITH_PATHS"
        else:
            route = "SKIP_WEAK_SESSION"

        repo_hint = repo_hints.most_common(1)[0][0] if repo_hints else ""
        trace_rows = _best_trace_rows(trace_index.get((root_label, session_id), []), limit=max(1, int(min_trace_rows) * 4))
        if require_execution_traces and len(trace_rows) < int(min_trace_rows):
            route_counts['SKIP_NO_EXECUTION_TRACES'] += 1
            continue

        verification_targets = _verification_targets(trace_rows, verification_paths)
        if require_execution_traces and not verification_targets:
            route_counts['SKIP_NO_VERIFICATION_TARGETS'] += 1
            continue

        route_counts[route] += 1
        if route == "SKIP_WEAK_SESSION" or not changes:
            continue

        goal = _goal_text(changes=changes, verification_targets=verification_targets, trace_rows=trace_rows, route=route)
        seed_id = stable_id("sessseed", root_label, session_id, route, repo_hint)
        seeds.append(
            {
                "seed_id": seed_id,
                "seed_type": "session_episode",
                "source_root_label": root_label,
                "session_id_hint": session_id,
                "repo_hint": repo_hint,
                "goal": goal,
                "changes": changes,
                "metadata": {
                    "route": route,
                    "normalized_event_type_counts": dict(sorted(normalized_counts.items())),
                    "tool_name_counts": dict(sorted(tool_counts.items())),
                    "file_path_ref_count": len(deduped_paths),
                    "event_count": len(session_events),
                    "trace_count": len(trace_rows),
                    "trace_failure_types": sorted({str(dict(row.get('runtime_trace') or {}).get('failure_type') or '') for row in trace_rows if str(dict(row.get('runtime_trace') or {}).get('failure_type') or '')}),
                    "trace_exception_types": sorted({str(dict(row.get('runtime_trace') or {}).get('exception_type') or '') for row in trace_rows if str(dict(row.get('runtime_trace') or {}).get('exception_type') or '')}),
                    "trace_command_heads": sorted({str(row.get('command_head') or '') for row in trace_rows if str(row.get('command_head') or '')}),
                    "trace_verification_targets": verification_targets,
                    "trace_ids": [str(row.get('trace_id') or '') for row in trace_rows[:16]],
                },
            }
        )

    summary = {
        "event_rows": len(events),
        "session_count": len(by_session),
        "seed_count": len(seeds),
        "route_counts": dict(sorted(route_counts.items())),
        "require_execution_traces": bool(require_execution_traces),
        "min_trace_rows": int(min_trace_rows),
    }
    return seeds, summary


def materialize_session_episode_seed_candidates(
    *,
    normalized_events_path: Path,
    output_dir: Path,
    execution_traces_path: Path | None = None,
    require_execution_traces: bool = False,
    min_trace_rows: int = 1,
) -> dict[str, Any]:
    seeds, summary = build_session_episode_seed_candidates(
        normalized_events_path=normalized_events_path,
        execution_traces_path=execution_traces_path,
        require_execution_traces=require_execution_traces,
        min_trace_rows=min_trace_rows,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "session_episode_seed_candidates.jsonl", seeds)
    write_json(output_dir / "session_episode_seed_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build session-derived episode seed candidates from normalized metadata-only event rows.")
    parser.add_argument("--normalized-events", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--execution-traces", type=Path)
    parser.add_argument("--require-execution-traces", action='store_true')
    parser.add_argument("--min-trace-rows", type=int, default=1)
    args = parser.parse_args()
    materialize_session_episode_seed_candidates(
        normalized_events_path=args.normalized_events,
        output_dir=args.output_dir,
        execution_traces_path=args.execution_traces,
        require_execution_traces=args.require_execution_traces,
        min_trace_rows=args.min_trace_rows,
    )


if __name__ == "__main__":
    main()
