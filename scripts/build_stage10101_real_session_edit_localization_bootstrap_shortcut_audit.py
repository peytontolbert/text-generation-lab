#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10101
NAME = "stage10101_real_session_edit_localization_bootstrap_shortcut_audit"
SOURCE = ROOT / "runs/local/artifacts/session_like_source_inventory_real/augmented_session_episodes_v4_dense_neighbors_realindex/augmented_session_episodes.jsonl"
INVENTORY_AUDIT = ROOT / "runs/local/artifacts/stage10100_true_source_backed_multilingual_session_inventory_audit/true_source_backed_multilingual_session_inventory_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "real_session_edit_localization_bootstrap_shortcut_audit.json"
ROWS = OUT_DIR / "real_session_edit_localization_bootstrap_shortcut_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REAL_SESSION_EDIT_LOCALIZATION_BOOTSTRAP_SHORTCUT_AUDIT_STAGE10101.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

LANGUAGE_FAMILIES = ("python", "rust", "c_cpp", "web_js_ts_html")
CONFIG_EXTS = {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf"}
TEST_PARTS = {"test", "tests", "spec"}
TEST_SUFFIXES = (".spec.ts", ".spec.js", ".test.ts", ".test.js", ".test.py", "_test.py")
ENTRYPOINT_BASENAMES = {
    "main.py",
    "main.js",
    "main.ts",
    "app.py",
    "app.js",
    "app.ts",
    "index.js",
    "index.ts",
    "index.html",
    "server.py",
    "server.js",
}
PYTHON_EXTS = {".py"}
CPP_EXTS = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx", ".cu"}
WEB_EXTS = {".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".scss"}
TRACE_ROLES = {"trace_analogue", "verification_constraint", "seed_change", "repo_graph_neighbor"}


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


def _change_paths(row: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for entry in row.get("changes") or []:
        if isinstance(entry, dict):
            path_text = str(entry.get("path", "")).strip()
        else:
            path_text = str(entry).strip()
        if path_text:
            paths.append(path_text)
    return paths


def _selected_tests(row: dict[str, Any]) -> list[str]:
    return [str(item).strip() for item in (row.get("selected_tests") or []) if str(item).strip()]


def _language_family(paths: list[str]) -> str:
    counts = Counter()
    for path_text in paths:
        suffix = Path(path_text).suffix.lower()
        if suffix in PYTHON_EXTS:
            counts["python"] += 1
        elif suffix == ".rs":
            counts["rust"] += 1
        elif suffix in CPP_EXTS:
            counts["c_cpp"] += 1
        elif suffix in WEB_EXTS:
            counts["web_js_ts_html"] += 1
    if not counts:
        return ""
    return counts.most_common(1)[0][0]


def _is_test_path(path_text: str) -> bool:
    lowered = path_text.lower()
    path = Path(lowered)
    if any(part in TEST_PARTS for part in path.parts):
        return True
    name = path.name
    return name.startswith("test_") or any(name.endswith(suffix) for suffix in TEST_SUFFIXES)


def _target_family_flags(paths: list[str], selected_tests: list[str]) -> list[str]:
    flags: list[str] = []
    if any(Path(path_text).suffix.lower() in CONFIG_EXTS for path_text in paths):
        flags.append("TARGET_CONFIG")
    if any(_is_test_path(path_text) for path_text in paths) or selected_tests:
        flags.append("TARGET_TEST")
    if any(Path(path_text).name.lower() in ENTRYPOINT_BASENAMES for path_text in paths):
        flags.append("TARGET_ENTRYPOINT")
    if any(
        Path(path_text).suffix.lower() not in CONFIG_EXTS and not _is_test_path(path_text)
        for path_text in paths
    ):
        flags.append("TARGET_FILE")
    return sorted(set(flags))


def _signature(paths: list[str], selected_tests: list[str]) -> tuple[str, ...]:
    parts: list[str] = []
    suffixes = sorted({Path(path_text).suffix.lower() or "<none>" for path_text in paths})
    if any(Path(path_text).name.lower() in ENTRYPOINT_BASENAMES for path_text in paths):
        parts.append("has_entrypoint")
    if any(Path(path_text).suffix.lower() in CONFIG_EXTS for path_text in paths):
        parts.append("has_config")
    if selected_tests:
        parts.append("has_selected_tests")
    if any(_is_test_path(path_text) for path_text in paths):
        parts.append("has_test_path")
    parts.extend(suffixes)
    return tuple(parts)


def _visible_snippet_preview(row: dict[str, Any]) -> list[dict[str, str]]:
    previews: list[dict[str, str]] = []
    for context_row in row.get("context_rows") or []:
        if not isinstance(context_row, dict):
            continue
        role = str(context_row.get("role", "")).strip()
        text = str(context_row.get("text", "")).strip()
        path_text = str(context_row.get("path", "")).strip()
        if role not in TRACE_ROLES or not text:
            continue
        previews.append(
            {
                "role": role,
                "path": path_text,
                "text_preview": text[:220],
            }
        )
        if len(previews) >= 3:
            break
    return previews


def build() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    inventory_audit = load_json(INVENTORY_AUDIT)
    rows = load_jsonl(SOURCE)
    candidate_rows: list[dict[str, Any]] = []
    signature_buckets: defaultdict[tuple[str, ...], Counter[str]] = defaultdict(Counter)
    target_combo_counts = Counter()
    unique_target_counts = Counter()
    unique_target_by_language = Counter()
    for row in rows:
        change_paths = _change_paths(row)
        selected_tests = _selected_tests(row)
        language_family = _language_family(change_paths)
        target_flags = _target_family_flags(change_paths, selected_tests)
        target_combo_counts["+".join(target_flags) if target_flags else "NONE"] += 1
        unique_target = target_flags[0] if len(target_flags) == 1 else None
        signature = _signature(change_paths, selected_tests)
        if unique_target:
            unique_target_counts[unique_target] += 1
            if language_family:
                unique_target_by_language[(language_family, unique_target)] += 1
            signature_buckets[signature][unique_target] += 1
        candidate_rows.append(
            {
                "episode_id": row.get("episode_id"),
                "repo_id": row.get("repo_id"),
                "language_family": language_family,
                "route": str((row.get("source_metadata") or {}).get("route", "")).strip(),
                "change_paths": change_paths,
                "selected_tests": selected_tests,
                "context_role_counts": row.get("context_role_counts") if isinstance(row.get("context_role_counts"), dict) else {},
                "candidate_target_families": target_flags,
                "unique_target_family": unique_target,
                "visible_evidence_preview": _visible_snippet_preview(row),
                "changed_path_signature": list(signature),
            }
        )
    unique_rows = sum(unique_target_counts.values())
    signature_majority_correct = sum(max(bucket.values()) for bucket in signature_buckets.values())
    signature_majority_exact = (
        round(signature_majority_correct / unique_rows, 4)
        if unique_rows > 0
        else None
    )
    metrics = {
        "source_inventory_path": display(SOURCE),
        "rows_scanned": len(candidate_rows),
        "language_row_counts": {
            language: sum(1 for row in candidate_rows if row.get("language_family") == language)
            for language in LANGUAGE_FAMILIES
        },
        "target_combo_counts": dict(sorted(target_combo_counts.items())),
        "unique_target_counts": dict(sorted(unique_target_counts.items())),
        "unique_target_rows": unique_rows,
        "unique_target_rows_by_language": {
            f"{language}::{target}": count
            for (language, target), count in sorted(unique_target_by_language.items())
        },
        "changed_path_signature_majority_exact_on_unique_rows": signature_majority_exact,
        "unique_changed_path_signatures": len(signature_buckets),
        "best_stage10100_bootstrap_inventory": ((inventory_audit.get("best_bootstrap_inventory") or {}).get("inventory_path")),
    }
    failures: list[str] = []
    if metrics["rows_scanned"] != 56:
        failures.append("expected_56_rows_in_source_inventory")
    if unique_target_counts.get("TARGET_FILE", 0) <= 0:
        failures.append("no_unique_target_file_rows_found")
    claim_boundary = {
        "real_session_inventory_is_evaluator_ready_for_edit_localization": False,
        "usable_as_source_evidence_reservoir": True,
        "target_family_bootstrap_is_collapsed_to_file_rows": unique_target_counts == {"TARGET_FILE": unique_rows} if unique_rows else False,
        "changed_path_signature_shortcut_present": bool(signature_majority_exact == 1.0),
    }
    next_best_step = (
        "Do not score this inventory directly as edit localization. Use it as a source evidence reservoir, then build explicit candidate competition and anti-shortcut controls so the answer is not recoverable from changed-path signatures alone."
    )
    audit = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "artifacts": {
            "source_inventory": display(SOURCE),
            "stage10100_inventory_audit": display(INVENTORY_AUDIT),
            "shortcut_rows": display(ROWS),
        },
        "intent": "Test whether the best real session inventory can already support a fair maintainer-visible edit-localization bootstrap, or whether source-side path signatures and target-family collapse still make it unsuitable as an eval packet.",
        "metrics": metrics,
        "claim_boundary": claim_boundary,
        "failures": failures,
        "next_best_step": next_best_step,
    }
    return audit, candidate_rows


def write_doc(audit: dict[str, Any]) -> None:
    metrics = audit["metrics"]
    lines = [
        "# Stage10101 Real Session Edit Localization Bootstrap Shortcut Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Rows scanned: `{metrics['rows_scanned']}`",
        f"Unique target rows: `{metrics['unique_target_rows']}`",
        f"Unique target counts: `{metrics['unique_target_counts']}`",
        f"Changed-path signature majority exact: `{metrics['changed_path_signature_majority_exact_on_unique_rows']}`",
        "",
        "This stage audits the real augmented session inventory identified in stage10100. The result is that the inventory is useful as a real source evidence reservoir, but it is not yet a fair edit-localization eval packet: uniquely targetable rows collapse to `TARGET_FILE`, and changed-path signatures alone recover those labels perfectly.",
        "",
        f"Next: {audit['next_best_step']}",
        "",
    ]
    DOC.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    audit, rows = build()
    write_json(AUDIT, audit)
    write_jsonl(ROWS, rows)
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
