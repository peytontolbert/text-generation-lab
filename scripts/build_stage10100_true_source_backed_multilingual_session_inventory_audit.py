#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10100
NAME = "stage10100_true_source_backed_multilingual_session_inventory_audit"
INVENTORY_ROOT = ROOT / "runs/local/artifacts/session_like_source_inventory_real"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "true_source_backed_multilingual_session_inventory_audit.json"
ROWS = OUT_DIR / "true_source_backed_multilingual_session_inventory_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRUE_SOURCE_BACKED_MULTILINGUAL_SESSION_INVENTORY_AUDIT_STAGE10100.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

LANGUAGE_FAMILIES = ("python", "rust", "c_cpp", "web_js_ts_html")
SESSION_FILE_NAMES = {
    "augmented_session_episodes.jsonl",
    "local_root_session_episodes.jsonl",
    "packable_examples.jsonl",
    "packable_augmented_session_episode_examples.jsonl",
}
TRACE_ROLES = {"trace_analogue", "verification_constraint", "repo_graph_neighbor", "seed_change"}
PYTHON_EXTS = {".py"}
RUST_EXTS = {".rs"}
CPP_EXTS = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"}
WEB_EXTS = {".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".scss"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [
        row
        for row in registry.get("rows", [])
        if row.get("stage") != STAGE and row.get("stage_name") != NAME
    ]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "next_best_step": summary["next_best_step"],
        }
    )
    registry["rows"] = sorted(
        rows,
        key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")),
    )
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0) or 0)),
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def iter_session_files() -> list[Path]:
    return sorted(
        path
        for path in INVENTORY_ROOT.rglob("*.jsonl")
        if path.name in SESSION_FILE_NAMES
    )


def iter_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _path_language(path_text: str) -> set[str]:
    suffix = Path(path_text).suffix.lower()
    languages: set[str] = set()
    if suffix in PYTHON_EXTS:
        languages.add("python")
    if suffix in RUST_EXTS:
        languages.add("rust")
    if suffix in CPP_EXTS:
        languages.add("c_cpp")
    if suffix in WEB_EXTS:
        languages.add("web_js_ts_html")
    return languages


def _query_block(row: dict[str, Any]) -> dict[str, Any]:
    query = row.get("query")
    return query if isinstance(query, dict) else {}


def _context_rows(row: dict[str, Any]) -> list[dict[str, Any]]:
    context_rows = row.get("context_rows")
    return [item for item in context_rows if isinstance(item, dict)] if isinstance(context_rows, list) else []


def _changes(row: dict[str, Any]) -> list[str]:
    changes = row.get("changes")
    paths: list[str] = []
    if isinstance(changes, list):
        for entry in changes:
            if isinstance(entry, dict):
                path_text = str(entry.get("path", "")).strip()
            else:
                path_text = str(entry).strip()
            if path_text:
                paths.append(path_text)
    query = _query_block(row)
    seed_paths = query.get("seed_paths", row.get("seed_paths"))
    if isinstance(seed_paths, list):
        for entry in seed_paths:
            path_text = str(entry).strip()
            if path_text:
                paths.append(path_text)
    return paths


def _selected_tests(row: dict[str, Any]) -> list[str]:
    query = _query_block(row)
    tests = query.get("selected_tests", row.get("selected_tests"))
    if not isinstance(tests, list):
        return []
    return [str(item).strip() for item in tests if str(item).strip()]


def _text_value(row: dict[str, Any]) -> str:
    query = _query_block(row)
    for candidate in (query.get("text"), row.get("goal"), row.get("query")):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return ""


def _route(row: dict[str, Any]) -> str:
    for block_name in ("source_metadata", "metadata"):
        block = row.get(block_name)
        if isinstance(block, dict):
            route = str(block.get("route", "")).strip()
            if route:
                return route
    query = _query_block(row)
    route = str(query.get("execution_route", "")).strip()
    if route:
        return route
    goal = str(row.get("goal", "")).strip()
    return "PATCH_PLUS_EXEC" if "PATCH_PLUS_EXEC" in goal else goal


def _row_languages(row: dict[str, Any]) -> set[str]:
    languages: set[str] = set()
    for path_text in _changes(row):
        languages.update(_path_language(path_text))
    return languages


def _trace_roles(row: dict[str, Any]) -> set[str]:
    roles = {
        str(context_row.get("role", "")).strip()
        for context_row in _context_rows(row)
        if str(context_row.get("role", "")).strip()
    }
    return roles & TRACE_ROLES


def _code_snippet_count(row: dict[str, Any]) -> int:
    count = 0
    for context_row in _context_rows(row):
        text = str(context_row.get("text", ""))
        if text.strip():
            count += 1
    return count


def summarize_inventory(path: Path) -> dict[str, Any]:
    raw_rows = iter_jsonl(path)
    language_counts = Counter()
    route_counts = Counter()
    trace_role_counts = Counter()
    rows_with_code_snippets = 0
    rows_with_changed_files = 0
    rows_with_selected_tests = 0
    rows_with_query_text = 0
    rows_with_trace_like_context = 0
    rows_patch_plus_exec = 0
    rows_with_any_target_language = 0
    rows_with_multilang_signals = 0
    for row in raw_rows:
        languages = _row_languages(row)
        if languages:
            rows_with_any_target_language += 1
        if len(languages) > 1:
            rows_with_multilang_signals += 1
        for language in languages:
            language_counts[language] += 1
        route = _route(row)
        if route:
            route_counts[route] += 1
        if route == "PATCH_PLUS_EXEC":
            rows_patch_plus_exec += 1
        changes = _changes(row)
        if changes:
            rows_with_changed_files += 1
        tests = _selected_tests(row)
        if tests:
            rows_with_selected_tests += 1
        text_value = _text_value(row)
        if text_value:
            rows_with_query_text += 1
        code_snippet_count = _code_snippet_count(row)
        if code_snippet_count > 0:
            rows_with_code_snippets += 1
        trace_roles = _trace_roles(row)
        if trace_roles:
            rows_with_trace_like_context += 1
            trace_role_counts.update(trace_roles)
    coverage_languages = [language for language in LANGUAGE_FAMILIES if language_counts.get(language, 0) > 0]
    bootstrap_score = (
        rows_with_code_snippets
        + rows_with_changed_files
        + rows_with_selected_tests
        + rows_with_query_text
        + rows_with_trace_like_context
        + (6 * len([lang for lang in ("python", "c_cpp", "web_js_ts_html") if language_counts.get(lang, 0) > 0]))
        + (8 if language_counts.get("rust", 0) > 0 else 0)
    )
    return {
        "inventory_path": display(path),
        "row_count": len(raw_rows),
        "language_row_counts": {language: int(language_counts.get(language, 0)) for language in LANGUAGE_FAMILIES},
        "languages_present": coverage_languages,
        "route_counts": dict(sorted(route_counts.items())),
        "trace_role_counts": dict(sorted(trace_role_counts.items())),
        "rows_patch_plus_exec": rows_patch_plus_exec,
        "rows_with_any_target_language": rows_with_any_target_language,
        "rows_with_multilang_signals": rows_with_multilang_signals,
        "rows_with_changed_files": rows_with_changed_files,
        "rows_with_code_snippets": rows_with_code_snippets,
        "rows_with_query_text": rows_with_query_text,
        "rows_with_selected_tests": rows_with_selected_tests,
        "rows_with_trace_like_context": rows_with_trace_like_context,
        "bootstrap_score": bootstrap_score,
        "supports_builder_minimum_fields": bool(
            rows_with_changed_files and rows_with_code_snippets and rows_with_query_text
        ),
    }


def build() -> dict[str, Any]:
    session_files = iter_session_files()
    inventory_rows = [summarize_inventory(path) for path in session_files]
    inventory_rows.sort(
        key=lambda row: (
            int(row.get("bootstrap_score", 0)),
            int(row.get("row_count", 0)),
            row.get("inventory_path", ""),
        ),
        reverse=True,
    )
    best = inventory_rows[0] if inventory_rows else {}
    aggregate_language_counts = Counter()
    rust_inventories = 0
    for row in inventory_rows:
        lang_counts = row.get("language_row_counts", {})
        if not isinstance(lang_counts, dict):
            continue
        for language in LANGUAGE_FAMILIES:
            aggregate_language_counts[language] += int(lang_counts.get(language, 0) or 0)
        if int(lang_counts.get("rust", 0) or 0) > 0:
            rust_inventories += 1
    failures: list[str] = []
    if not inventory_rows:
        failures.append("no_session_inventories_found")
    if not best:
        failures.append("no_best_inventory_selected")
    claim_boundary = {
        "true_source_backed_builder_bootstrap_ready_for_python_web_c_cpp": bool(
            best
            and best.get("supports_builder_minimum_fields")
            and int(((best.get("language_row_counts") or {}).get("python", 0)) or 0) > 0
            and int(((best.get("language_row_counts") or {}).get("c_cpp", 0)) or 0) > 0
            and int(((best.get("language_row_counts") or {}).get("web_js_ts_html", 0)) or 0) > 0
        ),
        "multilingual_rust_coverage_already_present": bool(rust_inventories > 0),
        "rust_replenishment_required_before_four_language_claim": not bool(rust_inventories > 0),
        "synthetic_stage8765_lineage_still_rejected": True,
    }
    next_step = (
        "Bootstrap the true source-backed maintainer eval builder from "
        f"{best.get('inventory_path', 'no_inventory_selected')} for python/web/c_cpp, and replenish real Rust session roots before any four-language maintainer claim."
    )
    audit = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "artifacts": {
            "inventory_root": display(INVENTORY_ROOT),
            "inventory_rows": display(ROWS),
        },
        "metrics": {
            "inventories_scanned": len(inventory_rows),
            "aggregate_language_row_counts": {
                language: int(aggregate_language_counts.get(language, 0)) for language in LANGUAGE_FAMILIES
            },
            "inventories_with_rust_rows": rust_inventories,
            "best_bootstrap_inventory": best.get("inventory_path"),
            "best_bootstrap_row_count": best.get("row_count"),
            "best_bootstrap_score": best.get("bootstrap_score"),
        },
        "best_bootstrap_inventory": best,
        "inventory_summaries": inventory_rows[:24],
        "claim_boundary": claim_boundary,
        "failures": failures,
        "next_best_step": next_step,
    }
    return audit


def write_doc(audit: dict[str, Any]) -> None:
    best = audit.get("best_bootstrap_inventory") or {}
    lines = [
        "# Stage10100 True Source-Backed Multilingual Session Inventory Audit",
        "",
        f"Passed: `{audit['passed']}`",
        "",
        "This audit scans the real session-inventory family to determine whether a true maintainer-visible edit-localization builder can be bootstrapped without using the rejected synthetic stage8636 -> stage8765 lineage.",
        "",
        f"Best bootstrap inventory: `{best.get('inventory_path', 'n/a')}`",
        f"Languages present there: `{', '.join(best.get('languages_present', [])) or 'none'}`",
        f"Next: {audit['next_best_step']}",
        "",
    ]
    DOC.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    audit = build()
    write_json(AUDIT, audit)
    write_jsonl(ROWS, audit.get("inventory_summaries", []))
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "artifacts": audit["artifacts"],
        "metrics": audit["metrics"],
        "next_best_step": audit["next_best_step"],
    }
    write_json(SUMMARY, summary)
    write_doc(audit)
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "failures": audit["failures"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
