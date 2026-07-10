#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10110
NAME = "stage10110_real_session_shortcut_safe_successor_packet"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKET = OUT_DIR / "real_session_shortcut_safe_successor_packet.jsonl"
AUDIT = OUT_DIR / "real_session_shortcut_safe_successor_audit.json"
DROPS = OUT_DIR / "real_session_shortcut_safe_successor_drops.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REAL_SESSION_SHORTCUT_SAFE_SUCCESSOR_PACKET_STAGE10110.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

INVENTORY = ROOT / "runs/local/artifacts/session_like_source_inventory_real/packable_augmented_session_episode_examples_v4_dense_neighbors_realindex/packable_augmented_session_episode_examples.jsonl"
LEDGER = ROOT / "runs/local/artifacts/stage10109_real_session_multilingual_replenishment_ledger/real_session_multilingual_replenishment_ledger.json"
CANDIDATES = ROOT / "runs/local/artifacts/stage10109_real_session_multilingual_replenishment_ledger/real_session_multilingual_replenishment_candidates.jsonl"
SUCCESSOR = ROOT / "runs/local/artifacts/stage10108_real_session_shortcut_safe_successor_request/real_session_shortcut_safe_successor_request.json"

OPAQUE_IDS = ("A", "B", "C", "D")
CONFIG_EXTS = {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf"}
ENTRYPOINT_NAMES = {"index.html", "index.js", "index.ts", "main.py", "main.rs", "main.c", "main.cpp", "app.py", "app.js", "app.ts", "server.py", "server.js"}
CPP_EXTS = {".c", ".cc", ".cpp", ".cxx", ".cu", ".h", ".hh", ".hpp", ".hxx"}


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


def _episode_id(row: dict[str, Any]) -> str:
    return str(
        row.get("episode_id")
        or row.get("example_id")
        or row.get("id")
        or row.get("session_id")
        or row.get("program_id")
        or ""
    )


def _inventory_by_episode() -> dict[str, dict[str, Any]]:
    return {_episode_id(row): row for row in load_jsonl(INVENTORY)}


def _context_rows(row: dict[str, Any]) -> list[dict[str, Any]]:
    items = row.get("context_rows")
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def _snippet_by_path(row: dict[str, Any]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for item in _context_rows(row):
        path_text = str(item.get("path", "")).strip()
        text = str(item.get("text", "")).strip()
        if path_text and text and path_text not in mapping:
            mapping[path_text] = text[:260]
    return mapping


def _support_snippets(row: dict[str, Any]) -> list[str]:
    snippets: list[str] = []
    for item in _context_rows(row):
        role = str(item.get("role", "")).strip()
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        if role in {"verification_constraint", "trace_analogue", "repo_graph_neighbor"}:
            snippets.append(text[:220])
        if len(snippets) >= 3:
            break
    return snippets


def _redact_path(path_text: str) -> str:
    suffix = Path(path_text).suffix.lower() or "<none>"
    stem = Path(path_text).stem[:24]
    return f"{stem}:{suffix}"


def _opaque_order(seed: str, count: int) -> list[str]:
    labels = list(OPAQUE_IDS[:count])
    labels.sort(key=lambda label: hashlib.sha256(f"{seed}:{label}".encode("utf-8")).hexdigest())
    return labels


def _candidate_preview(snippet_map: dict[str, str], path_text: str) -> str:
    snippet = snippet_map.get(path_text, "").strip()
    if snippet:
        return snippet[:220]
    return f"Relevant source excerpt withheld for {_redact_path(path_text)}"


def _is_config(path_text: str) -> bool:
    path = Path(path_text)
    return path.suffix.lower() in CONFIG_EXTS or "config" in path.name.lower()


def _is_entrypoint(path_text: str) -> bool:
    return Path(path_text).name.lower() in ENTRYPOINT_NAMES


def _is_cpp(path_text: str) -> bool:
    return Path(path_text).suffix.lower() in CPP_EXTS


def _choose_candidate_paths(candidate_row: dict[str, Any]) -> tuple[list[str], str]:
    paths = list(candidate_row.get("change_paths_for_language") or [])
    language = str(candidate_row.get("language_family") or "")
    tags = set(candidate_row.get("candidate_geometry_tags") or [])
    if language == "python":
        config_path = next((path for path in paths if _is_config(path)), "")
        impl_paths = [path for path in paths if not _is_config(path)]
        if "implementation_vs_config" in tags and config_path and impl_paths:
            return [impl_paths[0], config_path], "python_implementation_vs_config"
        if len(paths) >= 2:
            return paths[:2], "python_implementation_vs_implementation"
        return [], "insufficient_python_candidate_paths"
    if language == "c_cpp":
        cpp_paths = [path for path in paths if _is_cpp(path)]
        if len(cpp_paths) >= 2:
            return cpp_paths[:2], "cpp_implementation_vs_implementation"
        return [], "insufficient_cpp_candidate_paths"
    if language == "web_js_ts_html":
        entry_path = next((path for path in paths if _is_entrypoint(path)), "")
        impl_path = next((path for path in paths if path != entry_path), "")
        if "entrypoint_vs_implementation" in tags and entry_path and impl_path:
            return [entry_path, impl_path], "web_entrypoint_vs_implementation"
        if len(paths) >= 2:
            return paths[:2], "web_implementation_vs_implementation"
        return [], "insufficient_web_candidate_paths"
    return [], "unsupported_language"


def _candidate_type(template_name: str, path_text: str) -> str:
    if "entrypoint" in template_name and _is_entrypoint(path_text):
        return "ENTRYPOINT"
    if _is_config(path_text):
        return "CONFIG"
    return "IMPLEMENTATION"


def _materialize_row(candidate_row: dict[str, Any], inventory_row: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    candidate_paths, template_name = _choose_candidate_paths(candidate_row)
    if not candidate_paths:
        return None, template_name
    snippet_map = _snippet_by_path(inventory_row)
    support_snippets = _support_snippets(inventory_row)
    if not support_snippets:
        return None, "missing_support_snippets"

    opaque_ids = _opaque_order(str(candidate_row.get("episode_id") or ""), len(candidate_paths))
    opaque_candidates = []
    for opaque_id, path_text in zip(opaque_ids, candidate_paths):
        opaque_candidates.append(
            {
                "candidate_id": opaque_id,
                "candidate_label_hint": _candidate_type(template_name, path_text).lower(),
                "candidate_surface_family": _candidate_type(template_name, path_text),
                "redacted_path_hint": _redact_path(path_text),
                "snippet_preview": _candidate_preview(snippet_map, path_text),
            }
        )

    prompt_visible_evidence = support_snippets + [candidate["snippet_preview"] for candidate in opaque_candidates]
    materialized = {
        "row_id": f"stage10110::{candidate_row.get('episode_id')}::{template_name}",
        "episode_id": candidate_row.get("episode_id"),
        "repo_id": candidate_row.get("repo_id"),
        "language_family": candidate_row.get("language_family"),
        "successor_template": template_name,
        "prompt_surface": {
            "task_observation": "A real repository-maintenance session left multiple plausible edit surfaces. Use the visible maintenance clues and candidate snippets to choose the most plausible first surface to inspect or edit.",
            "visible_evidence": prompt_visible_evidence,
            "candidate_choices": [
                {
                    "candidate_id": candidate["candidate_id"],
                    "snippet_preview": candidate["snippet_preview"],
                }
                for candidate in opaque_candidates
            ],
            "return_protocol": "return_only_the_candidate_id",
        },
        "hidden_metadata": {
            "candidate_geometry_tags": candidate_row.get("candidate_geometry_tags"),
            "redacted_candidates": opaque_candidates,
            "selected_tests": candidate_row.get("selected_tests"),
            "requires_expert_maintainer_identifiability_review": True,
            "requires_gold_label_adjudication_before_training_or_scoring": True,
            "raw_change_paths_withheld_from_prompt": True,
        },
    }
    return materialized, ""


def _quota_by_language(successor: dict[str, Any]) -> dict[str, int]:
    request = successor.get("replacement_request") if isinstance(successor.get("replacement_request"), dict) else {}
    return {language: int((payload or {}).get("replacement_rows_required", 0)) for language, payload in request.items()}


def build() -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    successor = load_json(SUCCESSOR)
    ledger = load_json(LEDGER)
    candidate_rows = load_jsonl(CANDIDATES)
    inventory_by_episode = _inventory_by_episode()
    failures: list[str] = []
    if successor.get("passed") is not True:
        failures.append("stage10108_not_passed")
    if ledger.get("passed") is not True:
        failures.append("stage10109_not_passed")

    quotas = _quota_by_language(successor)
    target_languages = {"python", "c_cpp", "web_js_ts_html"}
    filtered = [
        row for row in candidate_rows
        if row.get("language_family") in target_languages and row.get("supports_shortcut_safe_successor") is True
    ]

    def rank(row: dict[str, Any]) -> tuple[int, str, str]:
        tags = set(row.get("candidate_geometry_tags") or [])
        language = str(row.get("language_family") or "")
        if language == "python":
            pref = 0 if "implementation_vs_config" in tags else 1
        elif language == "web_js_ts_html":
            pref = 0 if "entrypoint_vs_implementation" in tags else 1
        else:
            pref = 0
        return pref, str(row.get("repo_id") or ""), str(row.get("episode_id") or "")

    filtered.sort(key=rank)

    packet_rows: list[dict[str, Any]] = []
    dropped_rows: list[dict[str, Any]] = []
    selected_counts = Counter()
    unmet_quotas = {}
    used_ids: set[tuple[str, str]] = set()

    for row in filtered:
        language = str(row.get("language_family") or "")
        episode_id = str(row.get("episode_id") or "")
        if selected_counts[language] >= quotas.get(language, 0):
            continue
        if (language, episode_id) in used_ids:
            continue
        inventory_row = inventory_by_episode.get(episode_id)
        if not inventory_row:
            dropped_rows.append({"episode_id": episode_id, "language_family": language, "drop_reason": "missing_inventory_row"})
            continue
        materialized, reason = _materialize_row(row, inventory_row)
        if materialized is None:
            dropped_rows.append({"episode_id": episode_id, "language_family": language, "drop_reason": reason})
            continue
        packet_rows.append(materialized)
        used_ids.add((language, episode_id))
        selected_counts[language] += 1

    for language in sorted(target_languages):
        required = quotas.get(language, 0)
        selected = int(selected_counts.get(language, 0))
        if selected < required:
            unmet_quotas[language] = required - selected

    metrics = {
        "selected_rows": len(packet_rows),
        "selected_language_counts": dict(sorted(selected_counts.items())),
        "unmet_quotas": dict(sorted(unmet_quotas.items())),
        "dropped_rows": len(dropped_rows),
        "drop_reason_counts": dict(sorted(Counter(str(row.get("drop_reason") or "") for row in dropped_rows).items())),
        "template_counts": dict(sorted(Counter(str(row.get("successor_template") or "") for row in packet_rows).items())),
    }
    claim_boundary = {
        "supports_training_or_scoring_now": False,
        "python_successor_packet_materialized": int(selected_counts.get("python", 0)) == quotas.get("python", 0),
        "c_cpp_successor_packet_materialized": int(selected_counts.get("c_cpp", 0)) == quotas.get("c_cpp", 0),
        "web_successor_packet_still_underfilled": int(selected_counts.get("web_js_ts_html", 0)) < quotas.get("web_js_ts_html", 0),
        "rust_successor_packet_missing_by_design": True,
    }
    next_best_step = "Run expert-maintainer and anti-cheat review on this shortcut-safe successor packet, then replenish the remaining missing Web and Rust supply before any multilingual maintainer-vs-Gemma claim."
    audit = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "metrics": metrics,
        "claim_boundary": claim_boundary,
        "failures": failures,
        "next_best_step": next_best_step,
    }
    return audit, packet_rows, dropped_rows


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    audit, packet_rows, dropped_rows = build()
    write_json(AUDIT, audit)
    write_jsonl(PACKET, packet_rows)
    write_jsonl(DROPS, dropped_rows)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "metrics": {**audit["metrics"], "failures": audit["failures"]},
        "artifacts": {
            "packet": display(PACKET),
            "audit": display(AUDIT),
            "drops": display(DROPS),
            "successor_request": display(SUCCESSOR),
            "replenishment_ledger": display(LEDGER),
        },
        "decision": "Materialized the first shortcut-safe real-session successor packet from identified Python/C++/Web supply, using real source snippets and non-test competition geometry while keeping the missing Web and Rust quotas explicit.",
        "next_best_step": audit["next_best_step"],
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(SUMMARY, summary)
    DOC.write_text(
        "\n".join(
            [
                "# Stage10110 Real Session Shortcut Safe Successor Packet",
                "",
                f"Passed: `{summary['passed']}`",
                f"Selected rows: `{audit['metrics']['selected_rows']}`",
                f"Selected language counts: `{audit['metrics']['selected_language_counts']}`",
                f"Unmet quotas: `{audit['metrics']['unmet_quotas']}`",
                "",
                summary["decision"],
                "",
                f"Next: {audit['next_best_step']}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "metrics": audit["metrics"], "failures": audit["failures"], "next_best_step": audit["next_best_step"]}, indent=2, sort_keys=True))
    if audit["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
