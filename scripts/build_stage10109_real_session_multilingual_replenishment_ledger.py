#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10109
NAME = "stage10109_real_session_multilingual_replenishment_ledger"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
LEDGER = OUT_DIR / "real_session_multilingual_replenishment_ledger.json"
CANDIDATES = OUT_DIR / "real_session_multilingual_replenishment_candidates.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REAL_SESSION_MULTILINGUAL_REPLENISHMENT_LEDGER_STAGE10109.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

INVENTORY = ROOT / "runs/local/artifacts/session_like_source_inventory_real/packable_augmented_session_episode_examples_v4_dense_neighbors_realindex/packable_augmented_session_episode_examples.jsonl"
SUCCESSOR = ROOT / "runs/local/artifacts/stage10108_real_session_shortcut_safe_successor_request/real_session_shortcut_safe_successor_request.json"

PY_EXTS = {".py"}
RUST_EXTS = {".rs"}
CPP_EXTS = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx", ".cu"}
WEB_EXTS = {".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".scss"}
CONFIG_EXTS = {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf"}
ENTRYPOINT_NAMES = {"index.html", "index.js", "index.ts", "main.py", "main.rs", "main.c", "main.cpp", "app.py", "app.js", "app.ts", "server.py", "server.js"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
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


def _suffix_language(path_text: str) -> set[str]:
    suffix = Path(path_text).suffix.lower()
    langs: set[str] = set()
    if suffix in PY_EXTS:
        langs.add("python")
    if suffix in RUST_EXTS:
        langs.add("rust")
    if suffix in CPP_EXTS:
        langs.add("c_cpp")
    if suffix in WEB_EXTS:
        langs.add("web_js_ts_html")
    return langs


def _collect_change_paths(row: dict[str, Any]) -> list[str]:
    query = row.get("query") if isinstance(row.get("query"), dict) else {}
    paths: list[str] = []
    for entry in row.get("changes") or []:
        if isinstance(entry, dict):
            text = str(entry.get("path", "")).strip()
        else:
            text = str(entry).strip()
        if text:
            paths.append(text)
    for entry in query.get("seed_paths") or row.get("seed_paths") or []:
        text = str(entry).strip()
        if text:
            paths.append(text)
    unique: list[str] = []
    for path_text in paths:
        if path_text not in unique:
            unique.append(path_text)
    return unique


def _selected_tests(row: dict[str, Any]) -> list[str]:
    query = row.get("query") if isinstance(row.get("query"), dict) else {}
    tests = query.get("selected_tests", row.get("selected_tests"))
    if not isinstance(tests, list):
        return []
    return [str(item).strip() for item in tests if str(item).strip()]


def _context_rows(row: dict[str, Any]) -> list[dict[str, Any]]:
    items = row.get("context_rows")
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def _visible_role_counts(row: dict[str, Any]) -> dict[str, int]:
    counts = Counter()
    for item in _context_rows(row):
        role = str(item.get("role", "")).strip()
        if role:
            counts[role] += 1
    return dict(sorted(counts.items()))


def _language_paths(paths: list[str], language: str) -> list[str]:
    return [path_text for path_text in paths if language in _suffix_language(path_text)]


def _has_entrypoint(paths: list[str]) -> bool:
    return any(Path(path_text).name.lower() in ENTRYPOINT_NAMES for path_text in paths)


def _has_config(paths: list[str]) -> bool:
    for path_text in paths:
        path = Path(path_text)
        if path.suffix.lower() in CONFIG_EXTS:
            return True
        if "config" in path.name.lower():
            return True
    return False


def _has_test_path(paths: list[str]) -> bool:
    for path_text in paths:
        path = Path(path_text)
        if "test" in path.name.lower():
            return True
        if any(part.lower() == "tests" for part in path.parts):
            return True
    return False


def _query_text(row: dict[str, Any]) -> str:
    query = row.get("query") if isinstance(row.get("query"), dict) else {}
    for candidate in (query.get("text"), row.get("goal"), row.get("query")):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return ""


def _episode_id(row: dict[str, Any]) -> str:
    return str(
        row.get("episode_id")
        or row.get("example_id")
        or row.get("id")
        or row.get("session_id")
        or row.get("program_id")
        or ""
    )


def _repo_id(row: dict[str, Any]) -> str:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    repo_id = str(metadata.get("repo_id", "")).strip()
    if repo_id:
        return repo_id
    episode_id = _episode_id(row)
    if episode_id.startswith("localsess_") and "_sessseed_" in episode_id:
        return episode_id.split("_sessseed_", 1)[0].replace("localsess_", "")
    return "unknown"


def _geometry_tags(language: str, lang_paths: list[str], tests: list[str]) -> list[str]:
    tags: list[str] = []
    if len(lang_paths) >= 2:
        tags.append("implementation_vs_implementation")
    if _has_entrypoint(lang_paths) and len(lang_paths) >= 2:
        tags.append("implementation_vs_entrypoint")
        if language == "web_js_ts_html":
            tags.append("entrypoint_vs_implementation")
    if _has_config(lang_paths):
        tags.append("implementation_vs_config")
    if len(lang_paths) >= 2:
        tags.append("symbol_vs_symbol")
    if tests:
        tags.append("has_selected_tests")
    if _has_test_path(lang_paths):
        tags.append("changed_test_file_present")
    return sorted(set(tags))


def build() -> dict[str, Any]:
    successor = load_json(SUCCESSOR)
    raw_rows = load_jsonl(INVENTORY)
    failures: list[str] = []
    if successor.get("passed") is not True:
        failures.append("stage10108_successor_request_not_passed")
    if len(raw_rows) != 56:
        failures.append("inventory_rows_not_56")

    candidate_rows: list[dict[str, Any]] = []
    language_counts = Counter()
    geometry_counts: Counter[tuple[str, str]] = Counter()
    repo_counts = Counter()

    for row in raw_rows:
        episode_id = _episode_id(row)
        paths = _collect_change_paths(row)
        tests = _selected_tests(row)
        repo_id = _repo_id(row)
        query_text = _query_text(row)
        role_counts = _visible_role_counts(row)
        for language in sorted({lang for path_text in paths for lang in _suffix_language(path_text)}):
            lang_paths = _language_paths(paths, language)
            tags = _geometry_tags(language, lang_paths, tests if language == "python" else [])
            if not tags:
                continue
            record = {
                "episode_id": episode_id,
                "repo_id": repo_id,
                "language_family": language,
                "change_paths_for_language": lang_paths,
                "selected_tests": tests,
                "query_text_present": bool(query_text),
                "context_role_counts": role_counts,
                "candidate_geometry_tags": tags,
                "supports_shortcut_safe_successor": any(tag in {
                    "implementation_vs_implementation",
                    "implementation_vs_entrypoint",
                    "implementation_vs_config",
                    "entrypoint_vs_implementation",
                    "symbol_vs_symbol",
                } for tag in tags),
            }
            candidate_rows.append(record)
            language_counts[language] += 1
            repo_counts[repo_id] += 1
            for tag in tags:
                geometry_counts[(language, tag)] += 1

    candidate_rows.sort(key=lambda row: (row["language_family"], row["repo_id"], row["episode_id"]))

    replacement_request = successor.get("replacement_request") if isinstance(successor.get("replacement_request"), dict) else {}
    replacement_supply: dict[str, Any] = {}
    for language, request in replacement_request.items():
        required = int((request or {}).get("replacement_rows_required", 0))
        supported = [
            row for row in candidate_rows
            if row["language_family"] == language and row["supports_shortcut_safe_successor"]
        ]
        unique_episodes = sorted({row["episode_id"] for row in supported})
        requested_geometries = list((request or {}).get("required_candidate_geometries") or [])
        geometry_support = {
            geometry: sum(1 for row in supported if geometry in row["candidate_geometry_tags"])
            for geometry in requested_geometries
        }
        replacement_supply[language] = {
            "required_rows": required,
            "supported_episode_count": len(unique_episodes),
            "supported_record_count": len(supported),
            "geometry_support_counts": geometry_support,
            "supply_gap_vs_required_rows": max(0, required - len(unique_episodes)),
            "sample_episode_ids": unique_episodes[:8],
        }

    metrics = {
        "inventory_rows": len(raw_rows),
        "candidate_records": len(candidate_rows),
        "language_counts": dict(sorted(language_counts.items())),
        "geometry_counts": {f"{language}::{tag}": count for (language, tag), count in sorted(geometry_counts.items())},
        "repo_counts": dict(sorted(repo_counts.items())),
    }
    ledger = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "artifacts": {
            "inventory": display(INVENTORY),
            "successor_request": display(SUCCESSOR),
            "candidate_rows": display(CANDIDATES),
        },
        "intent": "Turn the best real-source inventory into a concrete multilingual replenishment ledger showing which episode supply can satisfy the shortcut-safe successor contract and where real gaps remain.",
        "metrics": metrics,
        "replacement_supply": replacement_supply,
        "claim_boundary": {
            "supports_training_or_scoring_now": False,
            "rust_real_source_supply_still_zero": replacement_supply.get("rust", {}).get("supported_episode_count", 0) == 0,
            "python_shortcut_safe_replacements_exist_in_inventory": replacement_supply.get("python", {}).get("supported_episode_count", 0) > 0,
            "web_shortcut_safe_replacements_exist_in_inventory": replacement_supply.get("web_js_ts_html", {}).get("supported_episode_count", 0) > 0,
            "c_cpp_expansion_supply_exists_in_inventory": replacement_supply.get("c_cpp", {}).get("supported_episode_count", 0) > 0,
        },
        "failures": failures,
        "next_best_step": "Use the candidate ledger to materialize shortcut-safe successor rows from the supported Python/Web/C++ episodes, and separately replenish Rust from a new source-backed reservoir because the current real-session inventory still has zero Rust supply.",
    }
    write_json(LEDGER, ledger)
    write_jsonl(CANDIDATES, candidate_rows)
    return ledger


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    built = build()
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": built["artifacts"],
        "decision": "Compiled a concrete replenishment ledger from the best real-source inventory so shortcut-safe successor work can target actual Python/Web/C++ episode supply and quantify the remaining Rust gap.",
        "next_best_step": built["next_best_step"],
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(SUMMARY, summary)
    DOC.write_text(
        "\n".join(
            [
                "# Stage10109 Real Session Multilingual Replenishment Ledger",
                "",
                f"Passed: `{summary['passed']}`",
                f"Inventory rows: `{built['metrics']['inventory_rows']}`",
                f"Candidate records: `{built['metrics']['candidate_records']}`",
                "",
                summary["decision"],
                "",
                f"Next: {built['next_best_step']}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": built["passed"], "metrics": built["metrics"], "failures": built["failures"], "next_best_step": built["next_best_step"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
