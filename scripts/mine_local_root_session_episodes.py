from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

from coverage_test_selection import select_tests
from long_context_common import extract_terms, safe_read_text, stable_id, write_json, write_jsonl
from program_state_call_graph_extractor import extract_python_call_graph
from program_state_symbol_table_extractor import extract_python_symbols

TEXT_SUFFIXES = {".py", ".md", ".txt", ".rst", ".json", ".jsonl", ".yaml", ".yml", ".toml", ".cfg", ".ini", ".ts", ".tsx", ".js", ".jsx", ".java", ".go", ".rs", ".c", ".cc", ".cpp", ".h", ".hpp", ".sh"}
SKIP_DIR_NAMES = {".venv", "venv", "__pycache__", "node_modules", "dist", "build"}
VERIFICATION_PATH_MARKERS = ("config", "spec", "contract", "assert", "check", "verify", "validation", "smoke")
VERIFICATION_ALLOWED_SUFFIXES = {".py", ".md", ".rst", ".json", ".jsonl", ".yaml", ".yml", ".toml", ".cfg", ".ini", ".sh"}
VERIFICATION_EXCLUDED_PARTS = {"logs", "log", "records", "record", "artifacts", "artifact", "outputs", "output", "checkpoints", "checkpoint", "dist", "build", "node_modules", "vendor", "third_party", "tmp", "cache", "caches", "helpful_repos"}
VERIFICATION_STRUCTURAL_DIRS = {"config", "configs", "spec", "specs", "verify", "verification", "validation", "checks"}
GENERIC_QUERY_TERMS = {"modify", "repository", "files", "preserve", "behavior", "under", "execution", "backed", "maintenance", "changed", "verification", "targets", "key", "symbols", "route", "patch", "plus", "exec", "verify", "repair", "edit", "tool", "used", "goal", "task", "expected", "outcome"}


STRONG_EXECUTION_ROUTES = {"PATCH_PLUS_EXEC", "PATCH_PLUS_VERIFY"}


def _task_summary(*, changed_rel_paths: list[str], selected_tests: list[str], seed_symbols: set[str], execution_route: str) -> str:
    changed = ', '.join(changed_rel_paths[:8])
    tests = ', '.join(selected_tests[:8])
    symbols = ', '.join(sorted(seed_symbols)[:12]) if seed_symbols else '<none>'
    return '\n'.join(
        [
            f'Modify repository files to preserve behavior under execution-backed maintenance.',
            f'Changed files: {changed}',
            f'Verification targets: {tests}',
            f'Key symbols: {symbols}',
            f'Execution route: {execution_route}',
        ]
    )


def _target_payload(*, changed_rel_paths: list[str], selected_tests: list[str], seed_symbols: set[str], execution_route: str, test_selection_route: str) -> dict[str, Any]:
    if execution_route not in STRONG_EXECUTION_ROUTES:
        raise ValueError(f'weak_execution_route:{execution_route}')
    if not selected_tests:
        raise ValueError('missing_selected_tests')
    patch_summary = f"Update {', '.join(changed_rel_paths[:8])} so that {', '.join(selected_tests[:8])} remain satisfied after {execution_route.lower()}."
    return {
        'expected_patch_summary': patch_summary,
        'expected_outcome': f"verification_targets_hold_under_{execution_route.lower()}",
        'state_after': {
            'expected_changed_files': list(changed_rel_paths),
            'verification_targets': list(selected_tests),
            'execution_route': execution_route,
            'test_selection_route': test_selection_route,
            'key_symbols': sorted(seed_symbols)[:32],
        },
    }


def _norm_path(path: str) -> str:
    return str(path or "").replace("\\", "/").lstrip("./")


def _is_python_path(path: str) -> bool:
    return _norm_path(path).endswith(".py")


def _is_test_path(path: str) -> bool:
    normalized = _norm_path(path)
    name = normalized.rsplit("/", 1)[-1]
    return normalized.startswith("tests/") or "/tests/" in normalized or name.startswith("test_") or name.endswith("_test.py")


def _has_excluded_path_parts(path: str) -> bool:
    normalized = _norm_path(path)
    if not normalized:
        return False
    parts = {part.lower() for part in Path(normalized).parts[:-1]}
    return bool(parts & VERIFICATION_EXCLUDED_PARTS)


def _is_discoverable_test_path(path: str) -> bool:
    normalized = _norm_path(path)
    return _is_test_path(normalized) and not _has_excluded_path_parts(normalized)


def _is_verification_artifact_path(path: str) -> bool:
    normalized = _norm_path(path)
    if not normalized:
        return False
    if _is_test_path(normalized):
        return False
    suffix = Path(normalized).suffix.lower()
    if suffix and suffix not in VERIFICATION_ALLOWED_SUFFIXES:
        return False
    if _has_excluded_path_parts(normalized):
        return False
    lower = normalized.lower()
    name = lower.rsplit("/", 1)[-1]
    return any(marker in lower or marker in name for marker in VERIFICATION_PATH_MARKERS)


def _walk_text_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            name
            for name in dirnames
            if not name.startswith(".git") and name not in SKIP_DIR_NAMES
        ]
        for name in sorted(filenames):
            path = Path(dirpath) / name
            if any(part.startswith(".git") for part in path.parts):
                continue
            if path.suffix.lower() in TEXT_SUFFIXES:
                out.append(path)
    return sorted(out)


def _bounded_walk_text_files(root: Path, *, limit: int) -> list[Path]:
    files = _walk_text_files(root)
    return files[:limit] if limit > 0 else files


def _repo_index_from_paths(
    root: Path,
    paths: list[Path],
    *,
    file_info_cache: dict[str, dict[str, Any]] | None = None,
    max_chars: int = 200_000,
) -> dict[str, dict[str, Any]]:
    files: dict[str, dict[str, Any]] = {}
    cache = file_info_cache if file_info_cache is not None else {}
    for path in paths:
        rel = _norm_path(str(path.relative_to(root)))
        cache_key = str(path)
        cached = cache.get(cache_key)
        if cached is not None:
            files[rel] = dict(cached)
            continue
        text = safe_read_text(path, max_chars=max_chars)
        if not text.strip():
            continue
        analysis_status = "non_python"
        analysis_error_type = ""
        if _is_python_path(rel):
            analysis_status = "parsed"
            try:
                symbol_packet = extract_python_symbols(text, row_id=rel, path=rel).to_dict()
                call_packet = extract_python_call_graph(text, row_id=rel, path=rel).to_dict()
                defined = sorted(
                    {
                        str(symbol.get("name") or "")
                        for symbol in symbol_packet.get("symbols", [])
                        if str(symbol.get("symbol_kind") or "") in {"function", "async_function", "method", "class"}
                    }
                )
                imported = sorted(
                    {
                        str(symbol.get("name") or "")
                        for symbol in symbol_packet.get("symbols", [])
                        if str(symbol.get("symbol_kind") or "") == "import"
                    }
                )
                called = sorted(
                    {
                        str(node.get("name") or "")
                        for node in call_packet.get("call_nodes", [])
                        if str(node.get("node_kind") or "") in {"callee_reference", "callsite"} and str(node.get("name") or "") != "<unknown>"
                    }
                )
            except (RecursionError, SyntaxError, ValueError, MemoryError) as exc:
                defined = []
                imported = []
                called = []
                analysis_status = "parse_failed"
                analysis_error_type = type(exc).__name__
        else:
            defined = []
            imported = []
            called = []
        info = {
            "abs_path": str(path),
            "rel_path": rel,
            "text": text,
            "token_count": max(1, len(text.split())),
            "defined_symbols": defined,
            "imported_symbols": imported,
            "called_symbols": called,
            "analysis_status": analysis_status,
            "analysis_error_type": analysis_error_type,
        }
        cache[cache_key] = dict(info)
        files[rel] = info
    return files


def _candidate_roots(root: Path, changed_rel_paths: list[str]) -> list[Path]:
    candidates: list[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        if not path.exists():
            return
        try:
            path.relative_to(root)
        except ValueError:
            return
        try:
            resolved = str(path.resolve())
        except OSError:
            resolved = str(path)
        if resolved in seen:
            return
        seen.add(resolved)
        candidates.append(path)

    add(root)
    for rel in changed_rel_paths:
        path = root / rel
        add(path.parent)
        if path.parent.parent != path.parent:
            add(path.parent.parent)
        parts = Path(rel).parts
        if parts:
            add(root / parts[0])
    for name in ("tests", "test", "src", "lib", "config", "configs", "docs"):
        add(root / name)
    return candidates


def _resolve_existing_candidate_paths(root: Path, raw_paths: list[str]) -> list[Path]:
    resolved: list[Path] = []
    seen: set[str] = set()
    for raw in raw_paths:
        value = str(raw or '')
        if not value:
            continue
        candidate_inputs: list[Path] = []
        candidate_path = Path(value)
        if candidate_path.is_absolute():
            candidate_inputs.append(candidate_path)
        else:
            candidate_inputs.append(root / value)
            if len(candidate_path.parts) >= 2 and candidate_path.parts[0] == root.name:
                candidate_inputs.append(root / Path(*candidate_path.parts[1:]))
        for candidate in candidate_inputs:
            if candidate.exists() and candidate.is_file():
                key = str(candidate)
                if key not in seen:
                    seen.add(key)
                    resolved.append(candidate)
                break
    return resolved


def _collect_candidate_paths(
    root: Path,
    changed_rel_paths: list[str],
    *,
    root_file_limit: int,
    neighbor_dir_file_limit: int,
    max_total_candidates: int,
    walk_cache: dict[str, list[Path]] | None = None,
) -> list[Path]:
    selected: list[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        if not path.exists() or not path.is_file():
            return
        key = str(path)
        if key in seen:
            return
        seen.add(key)
        selected.append(path)

    for rel in changed_rel_paths:
        add(root / rel)

    cache = walk_cache if walk_cache is not None else {}
    for candidate_root in _candidate_roots(root, changed_rel_paths):
        if len(selected) >= max_total_candidates:
            break
        limit = root_file_limit if candidate_root == root else neighbor_dir_file_limit
        cache_key = str(candidate_root)
        walked = cache.get(cache_key)
        if walked is None:
            walked = _walk_text_files(candidate_root)
            cache[cache_key] = walked
        for path in walked[:limit] if limit > 0 else walked:
            add(path)
            if len(selected) >= max_total_candidates:
                break
    return sorted(selected)


def _resolve_repo_relative_paths(root: Path, paths: list[str], repo_files: dict[str, dict[str, Any]]) -> list[str]:
    resolved: list[str] = []
    seen: set[str] = set()
    for raw in paths:
        value = str(raw or '')
        if not value:
            continue
        candidate_paths: list[Path] = []
        path = Path(value)
        if path.is_absolute():
            candidate_paths.append(path)
        else:
            candidate_paths.append(root / value)
            if len(path.parts) >= 2 and path.parts[0] == root.name:
                candidate_paths.append(root / Path(*path.parts[1:]))
        for candidate in candidate_paths:
            try:
                rel = _norm_path(str(candidate.relative_to(root)))
            except ValueError:
                continue
            if rel in repo_files and rel not in seen:
                seen.add(rel)
                resolved.append(rel)
                break
    return resolved


def _seed_symbols(changes: list[dict[str, Any]], repo_files: dict[str, dict[str, Any]], root: Path) -> set[str]:
    out: set[str] = set()
    for change in changes:
        try:
            rel = _norm_path(str(Path(str(change.get("path") or "")).relative_to(root)))
        except ValueError:
            continue
        info = repo_files.get(rel)
        if not info:
            continue
        out.update(info.get("defined_symbols", []))
        out.update(info.get("imported_symbols", []))
        out.update(info.get("called_symbols", []))
    return {item for item in out if item}


def _neighbor_paths(repo_files: dict[str, dict[str, Any]], changed_rel_paths: list[str], seed_symbols: set[str], *, max_neighbors: int) -> list[dict[str, Any]]:
    changed = set(changed_rel_paths)
    scored = []
    for rel, info in repo_files.items():
        if rel in changed:
            continue
        reasons = []
        score = 0.0
        defined = set(info.get("defined_symbols", []))
        imported = set(info.get("imported_symbols", []))
        called = set(info.get("called_symbols", []))
        if defined & seed_symbols:
            reasons.append("defines_seed_symbol")
            score += 3.0
        if imported & seed_symbols:
            reasons.append("imports_seed_symbol")
            score += 2.0
        if called & seed_symbols:
            reasons.append("calls_seed_symbol")
            score += 2.0
        if not reasons:
            continue
        if _is_test_path(rel):
            score -= 0.5
        scored.append({"rel_path": rel, "score": score, "reasons": sorted(set(reasons))})
    return sorted(scored, key=lambda row: (-float(row["score"]), row["rel_path"]))[:max_neighbors]


def _lexical_overlap_score(left: str, right: str) -> float:
    left_terms = set(extract_terms(str(left or ""), max_terms=64))
    right_terms = set(extract_terms(str(right or ""), max_terms=64))
    if not left_terms or not right_terms:
        return 0.0
    return float(len(left_terms & right_terms))


def _basename_stem(path: str) -> str:
    normalized = _norm_path(path)
    name = normalized.rsplit("/", 1)[-1]
    suffix = Path(name).suffix
    if suffix:
        name = name[: -len(suffix)]
    if name.startswith("test_"):
        name = name[5:]
    if name.endswith("_test"):
        name = name[:-5]
    return name


def _focus_terms_from_goal(goal: str) -> set[str]:
    out: set[str] = set()
    lines = [line.strip() for line in str(goal or "").splitlines() if line.strip()]
    for line in lines:
        if ":" in line:
            _, value = line.split(":", 1)
            target = value.strip()
        else:
            target = line
        out.update(extract_terms(target, max_terms=64))
    return {term for term in out if term and term not in GENERIC_QUERY_TERMS}


def _focus_terms_from_paths(paths: list[str]) -> set[str]:
    out: set[str] = set()
    for raw in paths:
        normalized = _norm_path(raw)
        if not normalized:
            continue
        out.update(extract_terms(_basename_stem(normalized), max_terms=32))
    return {term for term in out if term and term not in GENERIC_QUERY_TERMS}


def _focus_terms_from_symbols(symbols: set[str]) -> set[str]:
    out: set[str] = set()
    for symbol in symbols:
        out.update(extract_terms(str(symbol), max_terms=32))
    return {term for term in out if term and term not in GENERIC_QUERY_TERMS}


def _candidate_focus_terms(path: str, text: str) -> set[str]:
    terms = set(extract_terms(_basename_stem(path), max_terms=32))
    terms.update(extract_terms(str(text or "")[:1000], max_terms=64))
    return {term for term in terms if term and term not in GENERIC_QUERY_TERMS}


def _broad_discovery_test_candidates(
    *,
    repo_files: dict[str, dict[str, Any]],
    changed_rel_paths: list[str],
    seed_symbols: set[str],
    goal: str,
    max_tests: int,
) -> list[dict[str, Any]]:
    changed_set = set(changed_rel_paths)
    changed_text = "\n".join(str(repo_files[path].get("text") or "")[:4000] for path in changed_rel_paths if path in repo_files)
    query_text = "\n".join([
        str(goal or ""),
        " ".join(changed_rel_paths),
        " ".join(sorted(seed_symbols)),
        changed_text,
    ])
    changed_topdirs = {parts[0] for parts in (_norm_path(path).split("/") for path in changed_rel_paths) if len(parts) > 1 and parts[0]}
    changed_stems = {_basename_stem(path) for path in changed_rel_paths if _basename_stem(path)}
    focus_terms = _focus_terms_from_paths(changed_rel_paths) | _focus_terms_from_goal(goal) | _focus_terms_from_symbols(seed_symbols)
    candidates: list[dict[str, Any]] = []
    for rel, info in repo_files.items():
        if rel in changed_set or not _is_discoverable_test_path(rel):
            continue
        text = str(info.get("text") or "")
        symbols = set(info.get("defined_symbols", [])) | set(info.get("called_symbols", [])) | set(info.get("imported_symbols", []))
        shared_symbols = sorted(seed_symbols & symbols)
        lexical = _lexical_overlap_score(query_text, text)
        candidate_focus_terms = _candidate_focus_terms(rel, text)
        focus_overlap = sorted(focus_terms & candidate_focus_terms)
        score = 0.0
        reasons: list[str] = []
        if lexical > 0.0:
            score += lexical * 8.0
            reasons.append("lexical_overlap")
        if focus_overlap:
            score += min(len(focus_overlap), 6) * 2.5
            reasons.append("focus_overlap")
        if shared_symbols:
            score += min(len(shared_symbols), 8) * 2.0
            reasons.append("shared_seed_symbol")
        stem = _basename_stem(rel)
        if any(changed and (changed == stem or changed in stem or stem in changed) for changed in changed_stems):
            score += 3.0
            reasons.append("path_stem_overlap")
        path_parts = [part for part in _norm_path(rel).split("/") if part]
        if changed_topdirs & set(path_parts):
            score += 1.0
            reasons.append("directory_overlap")
        if score <= 0.0:
            continue
        if not ({"shared_seed_symbol", "path_stem_overlap", "focus_overlap"} & set(reasons)):
            continue
        candidates.append({"rel_path": rel, "score": score, "reasons": sorted(set(reasons)), "focus_overlap_terms": focus_overlap[:12]})
    return sorted(candidates, key=lambda row: (-float(row["score"]), row["rel_path"]))[:max_tests]


def _broad_discovery_verification_candidates(
    *,
    repo_files: dict[str, dict[str, Any]],
    changed_rel_paths: list[str],
    seed_symbols: set[str],
    goal: str,
    max_tests: int,
) -> list[dict[str, Any]]:
    changed_set = set(changed_rel_paths)
    changed_text = "\n".join(str(repo_files[path].get("text") or "")[:4000] for path in changed_rel_paths if path in repo_files)
    query_text = "\n".join([
        str(goal or ""),
        " ".join(changed_rel_paths),
        " ".join(sorted(seed_symbols)),
        changed_text,
    ])
    changed_stems = {_basename_stem(path) for path in changed_rel_paths if _basename_stem(path)}
    changed_topdirs = {parts[0] for parts in (_norm_path(path).split("/") for path in changed_rel_paths) if len(parts) > 1 and parts[0]}
    focus_terms = _focus_terms_from_paths(changed_rel_paths) | _focus_terms_from_goal(goal) | _focus_terms_from_symbols(seed_symbols)
    candidates: list[dict[str, Any]] = []
    for rel, info in repo_files.items():
        if rel in changed_set or not _is_verification_artifact_path(rel):
            continue
        text = str(info.get("text") or "")
        symbols = set(info.get("defined_symbols", [])) | set(info.get("called_symbols", [])) | set(info.get("imported_symbols", []))
        shared_symbols = sorted(seed_symbols & symbols)
        lexical = _lexical_overlap_score(query_text, text)
        candidate_focus_terms = _candidate_focus_terms(rel, text)
        focus_overlap = sorted(focus_terms & candidate_focus_terms)
        score = 0.0
        reasons: list[str] = []
        if lexical > 0.0:
            score += lexical * 8.0
            reasons.append("lexical_overlap")
        if focus_overlap:
            score += min(len(focus_overlap), 6) * 2.5
            reasons.append("focus_overlap")
        if shared_symbols:
            score += min(len(shared_symbols), 8) * 2.0
            reasons.append("shared_seed_symbol")
        stem = _basename_stem(rel)
        if any(changed and (changed == stem or changed in stem or stem in changed) for changed in changed_stems):
            score += 2.0
            reasons.append("path_stem_overlap")
        path_parts = [part for part in _norm_path(rel).split("/") if part]
        if changed_topdirs and changed_topdirs & set(path_parts):
            score += 1.0
            reasons.append("directory_overlap")
        structural_dirs = {part.lower() for part in path_parts[:-1]} & VERIFICATION_STRUCTURAL_DIRS
        if structural_dirs:
            score += 1.0
            reasons.append("verification_directory")
        lower_path = rel.lower()
        marker_hits = [marker for marker in VERIFICATION_PATH_MARKERS if marker in lower_path]
        if marker_hits:
            score += min(len(marker_hits), 3) * 0.75
            reasons.append("verification_marker")
        if score <= 0.0:
            continue
        if not ({"shared_seed_symbol", "path_stem_overlap", "focus_overlap"} & set(reasons)):
            continue
        candidates.append({"rel_path": rel, "score": score, "reasons": sorted(set(reasons)), "focus_overlap_terms": focus_overlap[:12]})
    return sorted(candidates, key=lambda row: (-float(row["score"]), row["rel_path"]))[:max_tests]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _trace_rows_for_seed(
    *,
    seed: dict[str, Any],
    trace_rows: dict[tuple[str, str, str], list[dict[str, Any]]],
    changed_rel_paths: list[str],
    max_trace_rows: int,
) -> list[dict[str, Any]]:
    if max_trace_rows <= 0:
        return []
    source_root_label = str(seed.get("source_root_label") or "")
    session_id_hint = str(seed.get("session_id_hint") or "")
    repo_hint = str(seed.get("repo_hint") or "")
    key = (source_root_label, session_id_hint, repo_hint)
    candidates = list(trace_rows.get(key, []))
    if not candidates:
        return []
    changed_terms = {Path(path).stem.lower() for path in changed_rel_paths}
    ranked: list[tuple[tuple[float, str], dict[str, Any]]] = []
    for row in candidates:
        refs = [str(item) for item in row.get("file_path_refs") or [] if str(item)]
        summary_text = str(row.get("summary_text") or "")
        trace = dict(row.get("runtime_trace") or {})
        failure_type = str(trace.get("failure_type") or "unknown_runtime_failure")
        exit_code = row.get("exit_code")
        command = str(row.get("command") or "")
        signal_kind = str(row.get("signal_kind") or "")
        verification_like = signal_kind == "verification" and (
            "pytest" in command.lower()
            or any("test" in ref.lower() for ref in refs)
            or "py_compile" in command
        )
        if failure_type == "unknown_runtime_failure" and exit_code in (None, 0) and not verification_like:
            continue
        score = 0.0
        if int(exit_code or 0) != 0:
            score += 1.0
        if signal_kind == "verification":
            score += 1.0
        if any(term and any(term in ref.lower() for ref in refs) for term in changed_terms):
            score += 1.5
        if any("test" in ref.lower() for ref in refs):
            score += 0.75
        if "failure type:" in summary_text.lower():
            score += 0.25
        ranked.append(((-score, str(row.get("trace_id") or "")), row))
    selected: list[dict[str, Any]] = []
    for _, row in sorted(ranked)[:max_trace_rows]:
        selected.append(
            {
                "chunk_id": str(row.get("trace_id") or ""),
                "source_type": "dataset",
                "source_id": str(row.get("session_id_hint") or ""),
                "path": f"codex_sessions/{session_id_hint}/{row.get('trace_id')}.trace.txt",
                "abs_path": "",
                "token_count": max(1, len(str(row.get("summary_text") or "").split())),
                "text": str(row.get("summary_text") or ""),
                "role": "trace_analogue",
                "retrieval_reason": f"session_trace|{row.get('command_head') or '<unknown>'}|{failure_type}",
                "distance_from_seed": 1,
                "retrieval_score": 2.0,
            }
        )
    return selected


def mine_local_root_session_episodes(
    *,
    resolved_local_seeds_path: Path,
    max_neighbors: int = 12,
    max_tests: int = 8,
    root_file_limit: int = 400,
    neighbor_dir_file_limit: int = 250,
    max_total_candidates: int = 1600,
    execution_traces_path: Path | None = None,
    max_trace_rows: int = 3,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    seeds = [json.loads(line) for line in resolved_local_seeds_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    episodes: list[dict[str, Any]] = []
    route_counts: Counter[str] = Counter()
    trace_index: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    if execution_traces_path is not None and execution_traces_path.exists():
        for row in _read_jsonl(execution_traces_path):
            key = (
                str(row.get("source_root_label") or ""),
                str(row.get("session_id_hint") or ""),
                str(row.get("repo_hint") or ""),
            )
            trace_index.setdefault(key, []).append(row)

    by_root: dict[str, list[dict[str, Any]]] = {}
    for seed in seeds:
        root = str(seed.get("local_repo_root") or "")
        if root and list(seed.get("changes") or []):
            by_root.setdefault(root, []).append(seed)

    for root_str, root_seeds in by_root.items():
        root = Path(root_str)
        if not root.exists():
            continue
        repo_id = root.name
        walk_cache: dict[str, list[Path]] = {}
        file_info_cache: dict[str, dict[str, Any]] = {}
        for seed in root_seeds:
            abs_changes = [dict(item) for item in seed.get("changes") or [] if isinstance(item, dict)]
            changed_rel_paths = []
            for change in abs_changes:
                try:
                    changed_rel_paths.append(_norm_path(str(Path(str(change.get("path") or "")).relative_to(root))))
                except ValueError:
                    continue

            candidate_paths = _collect_candidate_paths(
                root,
                changed_rel_paths,
                root_file_limit=root_file_limit,
                neighbor_dir_file_limit=neighbor_dir_file_limit,
                max_total_candidates=max_total_candidates,
                walk_cache=walk_cache,
            )
            trace_priority_paths = _resolve_existing_candidate_paths(
                root,
                list((seed.get('metadata') or {}).get('trace_verification_targets') or []),
            )
            if trace_priority_paths:
                existing = {str(path) for path in candidate_paths}
                candidate_paths.extend(path for path in trace_priority_paths if str(path) not in existing)
            repo_files = _repo_index_from_paths(root, candidate_paths, file_info_cache=file_info_cache)
            changed_rel_paths = [path for path in changed_rel_paths if path in repo_files]
            if not changed_rel_paths:
                route_counts["SKIP_NO_CHANGED_FILES"] += 1
                continue

            test_to_symbols = {
                rel: sorted(set(info.get("defined_symbols", [])) | set(info.get("called_symbols", [])))
                for rel, info in repo_files.items()
                if _is_discoverable_test_path(rel)
            }
            repo_index = {
                "files": sorted(repo_files),
                "coverage_map": {},
                "test_to_symbols": test_to_symbols,
            }

            seed_symbols = _seed_symbols(abs_changes, repo_files, root)
            neighbor_rows = _neighbor_paths(repo_files, changed_rel_paths, seed_symbols, max_neighbors=max_neighbors)
            execution_route = str((seed.get("metadata") or {}).get("route") or "")
            if execution_route not in STRONG_EXECUTION_ROUTES:
                route_counts["SKIP_WEAK_EXECUTION_ROUTE"] += 1
                continue
            trace_verification_targets = _resolve_repo_relative_paths(
                root,
                list((seed.get('metadata') or {}).get('trace_verification_targets') or []),
                repo_files,
            )
            broad_map: dict[str, dict[str, Any]] = {}
            if trace_verification_targets:
                selected_tests = [path for path in trace_verification_targets if _is_discoverable_test_path(path) or _is_verification_artifact_path(path)]
                selected_test_route = 'PASS_TRACE_VERIFICATION_TARGETS'
                route_counts[selected_test_route] += 1
            else:
                test_selection = select_tests(
                    {
                        "row_id": str(seed.get("seed_id") or ""),
                        "repo_index": repo_index,
                        "changes": [{"path": path} for path in changed_rel_paths],
                    },
                    max_tests=max_tests,
                )
                selected_tests = [str(path) for path in list(test_selection.get("selected_tests") or []) if _is_discoverable_test_path(str(path))]
                selected_test_route = str(test_selection.get("test_selection_route") or "")
                route_counts[selected_test_route] += 1
            if not selected_tests and selected_test_route == "NEEDS_BROAD_TEST_DISCOVERY":
                broad_candidates = _broad_discovery_test_candidates(
                    repo_files=repo_files,
                    changed_rel_paths=changed_rel_paths,
                    seed_symbols=seed_symbols,
                    goal=str(seed.get("goal") or ""),
                    max_tests=max_tests,
                )
                if broad_candidates:
                    selected_tests = [str(row["rel_path"]) for row in broad_candidates]
                    broad_map = {str(row["rel_path"]): row for row in broad_candidates}
                    selected_test_route = "PASS_BROAD_TEST_DISCOVERY"
                    route_counts[selected_test_route] += 1
                else:
                    verification_candidates = _broad_discovery_verification_candidates(
                        repo_files=repo_files,
                        changed_rel_paths=changed_rel_paths,
                        seed_symbols=seed_symbols,
                        goal=str(seed.get("goal") or ""),
                        max_tests=max_tests,
                    )
                    if verification_candidates:
                        selected_tests = [str(row["rel_path"]) for row in verification_candidates]
                        broad_map = {str(row["rel_path"]): row for row in verification_candidates}
                        selected_test_route = "PASS_BROAD_VERIFICATION_DISCOVERY"
                        route_counts[selected_test_route] += 1
            if not selected_tests:
                route_counts["SKIP_NO_SELECTED_TESTS"] += 1
                continue

            context_rows: list[dict[str, Any]] = []
            for rel in changed_rel_paths:
                info = repo_files[rel]
                context_rows.append(
                    {
                        "chunk_id": stable_id("localchunk", repo_id, rel),
                        "source_type": "local_repo",
                        "source_id": repo_id,
                        "path": rel,
                        "abs_path": info["abs_path"],
                        "token_count": int(info["token_count"]),
                        "text": info["text"],
                        "role": "seed_change",
                        "retrieval_reason": "resolved_session_change",
                        "distance_from_seed": 0,
                        "retrieval_score": 1.0,
                    }
                )
            for neighbor in neighbor_rows:
                info = repo_files[neighbor["rel_path"]]
                context_rows.append(
                    {
                        "chunk_id": stable_id("localchunk", repo_id, neighbor["rel_path"]),
                        "source_type": "local_repo",
                        "source_id": repo_id,
                        "path": neighbor["rel_path"],
                        "abs_path": info["abs_path"],
                        "token_count": int(info["token_count"]),
                        "text": info["text"],
                        "role": "repo_graph_neighbor" if not _is_test_path(neighbor["rel_path"]) else "test_neighbor",
                        "retrieval_reason": "|".join(neighbor["reasons"]),
                        "distance_from_seed": 1,
                        "retrieval_score": float(neighbor["score"]),
                    }
                )
            for test_path in selected_tests:
                info = repo_files.get(str(test_path))
                if not info:
                    continue
                retrieval_reason = "targeted_test_selection"
                retrieval_score = 1.5
                if str(test_path) in broad_map:
                    retrieval_reason = "|".join(list(broad_map[str(test_path)].get("reasons") or []))
                    retrieval_score = float(broad_map[str(test_path)].get("score") or 1.5)
                context_rows.append(
                    {
                        "chunk_id": stable_id("localchunk", repo_id, str(test_path)),
                        "source_type": "local_repo",
                        "source_id": repo_id,
                        "path": str(test_path),
                        "abs_path": info["abs_path"],
                        "token_count": int(info["token_count"]),
                        "text": info["text"],
                        "role": "verification_constraint",
                        "retrieval_reason": retrieval_reason,
                        "distance_from_seed": 1,
                        "retrieval_score": retrieval_score,
                    }
                )
            context_rows.extend(
                _trace_rows_for_seed(
                    seed=seed,
                    trace_rows=trace_index,
                    changed_rel_paths=changed_rel_paths,
                    max_trace_rows=max_trace_rows,
                )
            )

            task_summary = _task_summary(
                changed_rel_paths=changed_rel_paths,
                selected_tests=selected_tests,
                seed_symbols=seed_symbols,
                execution_route=execution_route,
            )
            target = _target_payload(
                changed_rel_paths=changed_rel_paths,
                selected_tests=selected_tests,
                seed_symbols=seed_symbols,
                execution_route=execution_route,
                test_selection_route=selected_test_route,
            )
            episode_id = stable_id("localsess", repo_id, str(seed.get("seed_id") or ""), "|".join(changed_rel_paths))
            episodes.append(
                {
                    "episode_id": episode_id,
                    "seed_id": str(seed.get("seed_id") or ""),
                    "seed_type": "session_episode_local_root",
                    "repo_id": repo_id,
                    "local_repo_root": str(root),
                    "goal": task_summary,
                    "changes": [{"path": rel} for rel in changed_rel_paths],
                    "seed_paths": changed_rel_paths,
                    "seed_symbols": sorted(seed_symbols),
                    "selected_tests": selected_tests,
                    "test_selection_route": selected_test_route,
                    "candidate_file_count": len(repo_files),
                    "context_rows": context_rows,
                    "context_token_count": sum(int(row.get("token_count") or 0) for row in context_rows),
                    "context_role_counts": dict(sorted(Counter(str(row.get("role") or "") for row in context_rows).items())),
                    "target": target,
                    "source_metadata": dict(seed.get("metadata") or {}),
                }
            )

    summary = {
        "input_seed_rows": len(seeds),
        "episode_count": len(episodes),
        "route_counts": dict(sorted(route_counts.items())),
    }
    return episodes, summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Mine long-context episodes directly from local-root-resolved session seeds.")
    parser.add_argument("--resolved-local-seeds", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path)
    parser.add_argument("--max-neighbors", type=int, default=12)
    parser.add_argument("--max-tests", type=int, default=8)
    parser.add_argument("--root-file-limit", type=int, default=400)
    parser.add_argument("--neighbor-dir-file-limit", type=int, default=250)
    parser.add_argument("--max-total-candidates", type=int, default=1600)
    parser.add_argument("--execution-traces", type=Path)
    parser.add_argument("--max-trace-rows", type=int, default=3)
    args = parser.parse_args()
    episodes, summary = mine_local_root_session_episodes(
        resolved_local_seeds_path=args.resolved_local_seeds,
        max_neighbors=args.max_neighbors,
        max_tests=args.max_tests,
        root_file_limit=args.root_file_limit,
        neighbor_dir_file_limit=args.neighbor_dir_file_limit,
        max_total_candidates=args.max_total_candidates,
        execution_traces_path=args.execution_traces,
        max_trace_rows=args.max_trace_rows,
    )
    write_jsonl(args.output, episodes)
    write_json(args.summary_output or args.output.with_name("local_root_session_episode_summary.json"), summary)


if __name__ == "__main__":
    main()
