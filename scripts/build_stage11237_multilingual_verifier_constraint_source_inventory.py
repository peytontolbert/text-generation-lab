#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11237
NAME = "stage11237_multilingual_verifier_constraint_source_inventory"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "multilingual_verifier_constraint_source_inventory.json"
CANDIDATES_JSONL = OUT_DIR / "verifier_constraint_source_candidates.jsonl"
BLOCKED_JSONL = OUT_DIR / "verifier_constraint_source_blocked.jsonl"

RETRIEVAL_ROWS = ARTIFACTS / "strict_long_context_train_ready_plus_audit_v1/retrieval_rows.jsonl"
CURRENT_TRAIN = ARTIFACTS / "stage11198_role_focused_residual_support_package/agentkernel_lite_encdec_train.jsonl"
CURRENT_VALIDATION = ARTIFACTS / "stage11198_role_focused_residual_support_package/agentkernel_lite_encdec_validation.jsonl"
CURRENT_STRICT = ARTIFACTS / "stage11198_role_focused_residual_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
RESIDUAL_BANK = ARTIFACTS / "stage11195_clean_residual_successor_bank/clean_residual_successor_bank.jsonl"
GROUPED_DIAG = ARTIFACTS / "stage11233_grouped_evidence_item_fact_package/grouped_evidence_item_fact_diagnostic_rows.jsonl"

EXT_LANGUAGE = {
    ".py": "python",
    ".pyi": "python",
    ".rs": "rust",
    ".c": "c_cpp",
    ".cc": "c_cpp",
    ".cpp": "c_cpp",
    ".cxx": "c_cpp",
    ".h": "c_cpp",
    ".hh": "c_cpp",
    ".hpp": "c_cpp",
    ".cu": "c_cpp",
    ".cuh": "c_cpp",
    ".js": "web_js_ts_html",
    ".jsx": "web_js_ts_html",
    ".ts": "web_js_ts_html",
    ".tsx": "web_js_ts_html",
    ".html": "web_js_ts_html",
    ".css": "web_js_ts_html",
    ".scss": "web_js_ts_html",
    ".vue": "web_js_ts_html",
    ".svelte": "web_js_ts_html",
}
OLD_EVAL_REPOS = {
    "agentkernel",
    "bddy_website",
    "candle",
    "code_assist",
    "parametergolf",
    "repository_library",
    "tokenizers",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def normalize_repo(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "unknown"


def path_language(path: str) -> str | None:
    lower = path.lower().split("?", 1)[0].split("#", 1)[0]
    for ext, lang in sorted(EXT_LANGUAGE.items(), key=lambda item: len(item[0]), reverse=True):
        if lower.endswith(ext):
            return lang
    if lower.endswith("cmakelists.txt") or "cmakelists" in lower:
        return "c_cpp"
    if lower.endswith("package.json"):
        return "web_js_ts_html"
    if lower.endswith("cargo.toml"):
        return "rust"
    return None


def infer_language(paths: list[str]) -> str | None:
    counts = Counter(lang for path in paths if (lang := path_language(path)))
    if not counts:
        return None
    priority = {"python": 4, "rust": 3, "c_cpp": 2, "web_js_ts_html": 1}
    return max(counts, key=lambda lang: (counts[lang], priority.get(lang, 0)))


def root_key(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("source_root_id") or row.get("source_row_id") or row.get("row_id") or "")


def used_state() -> dict[str, set[str]]:
    rows: list[dict[str, Any]] = []
    for path in [CURRENT_TRAIN, CURRENT_VALIDATION, CURRENT_STRICT, RESIDUAL_BANK, GROUPED_DIAG]:
        rows.extend(load_jsonl(path))
    roots = {root_key(row) for row in rows if root_key(row)}
    source_rows = {str((row.get("standalone_projection_source") or {}).get("source_row_id") or row.get("source_row_id") or "") for row in rows}
    repos = {str(row.get("repo_family") or "") for row in rows if row.get("repo_family")}
    repos |= OLD_EVAL_REPOS
    return {"roots": roots, "source_rows": {x for x in source_rows if x}, "repos": repos}


def parse_target(row: dict[str, Any]) -> dict[str, Any] | None:
    try:
        parsed = json.loads(row.get("target_text") or "{}")
    except Exception:
        return None
    fs = parsed.get("final_state") or {}
    if not isinstance(fs, dict):
        return None
    return parsed


def listify(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value:
        return [str(value)]
    return []


def support_paths(row: dict[str, Any], *, include_roles: set[str] | None = None) -> list[str]:
    paths = []
    for score in row.get("support_scores") or []:
        if not isinstance(score, dict):
            continue
        if include_roles is not None:
            role = str(score.get("role") or "")
            reasons = " ".join(str(x) for x in score.get("support_reasons") or [])
            source_type = str(score.get("source_type") or "")
            if not (role in include_roles or any(key in reasons for key in include_roles) or source_type in include_roles):
                continue
        path = str(score.get("path") or "").strip()
        if path:
            paths.append(path)
    return sorted(dict.fromkeys(paths))


def candidate_from(row: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    parsed = parse_target(row)
    if parsed is None:
        return None, {"source_row_id": row.get("row_id"), "blockers": ["target_not_json_final_state"]}
    fs = parsed.get("final_state") or {}
    changed = listify(fs.get("expected_changed_files"))
    tests = listify(fs.get("verification_targets"))
    symbols = listify(fs.get("key_symbols"))
    repo = normalize_repo(str(parsed.get("canonical_name") or (row.get("metadata") or {}).get("canonical_name") or "unknown"))
    candidate_paths = changed
    verifier_paths = tests
    symptom_paths = support_paths(row, include_roles={"local_repo", "call_path", "runtime", "analogue"})
    if not symptom_paths:
        symptom_paths = symbols[:8]
    all_paths = candidate_paths + verifier_paths + symptom_paths
    lang = infer_language(all_paths)
    blockers: list[str] = []
    if not candidate_paths:
        blockers.append("missing_candidate_change_surface_paths")
    if not verifier_paths:
        blockers.append("missing_verifier_targets")
    if not symptom_paths:
        blockers.append("missing_symptom_or_call_path_support")
    if set(candidate_paths) & set(verifier_paths):
        blockers.append("candidate_verifier_path_overlap")
    if lang is None:
        blockers.append("language_not_inferred")
    if repo in OLD_EVAL_REPOS:
        blockers.append("old_eval_repo_family")
    root = f"retrieval::{row.get('pack_id')}::{(row.get('metadata') or {}).get('query_index')}"
    item = {
        "source_row_id": row.get("row_id"),
        "source_root_id": root,
        "root_id": f"stage11237::{root}",
        "root_lineage_key": f"{repo}::{row.get('pack_id')}",
        "repo_family": repo,
        "repo_id": parsed.get("canonical_name") or repo,
        "language_family": lang,
        "candidate_change_surface_paths": candidate_paths,
        "verifier_and_test_constraint_paths": verifier_paths,
        "symptom_or_call_path_analogue_paths": symptom_paths,
        "key_symbols": symbols[:16],
        "execution_route": fs.get("execution_route"),
        "test_selection_route": fs.get("test_selection_route"),
        "quality_score": float(row.get("span_ratio") or 0.0) + (0.2 if row.get("long_join_positive") else 0.0),
        "source_family_id": "strict_long_context_train_ready_plus_audit_v1",
        "admission_ready": not blockers,
        "blockers": blockers,
    }
    return item, None


def main() -> None:
    used = used_state()
    candidates: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for row in load_jsonl(RETRIEVAL_ROWS):
        item, block = candidate_from(row)
        if block:
            blocked.append(block)
            continue
        assert item is not None
        if item["source_row_id"] in used["source_rows"] or item["source_root_id"] in used["roots"] or item["root_id"] in used["roots"]:
            item["admission_ready"] = False
            item["blockers"] = list(item["blockers"]) + ["already_consumed_source_or_root"]
        if item["repo_family"] in used["repos"]:
            item["admission_ready"] = False
            item["blockers"] = list(item["blockers"]) + ["repo_family_already_in_eval_or_train"]
        if item["admission_ready"]:
            candidates.append(item)
        else:
            blocked.append(item)
    candidates.sort(key=lambda item: (str(item.get("language_family") or ""), -float(item.get("quality_score") or 0.0), str(item.get("source_row_id") or "")))
    blocked.sort(key=lambda item: (str(item.get("language_family") or "unknown"), str(item.get("source_row_id") or "")))
    by_lang = Counter(str(item.get("language_family") or "unknown") for item in candidates)
    by_repo = Counter(str(item.get("repo_family") or "unknown") for item in candidates)
    blocked_reasons = Counter(reason for item in blocked for reason in item.get("blockers", []))
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(candidates),
        "decision": "multilingual_verifier_constraint_source_inventory_ready" if candidates else "multilingual_verifier_constraint_source_inventory_empty",
        "counts": {
            "ready_candidates": len(candidates),
            "blocked_candidates": len(blocked),
            "ready_by_language": dict(sorted(by_lang.items())),
            "ready_repo_families": len(by_repo),
            "top_ready_repos": dict(by_repo.most_common(20)),
            "blocked_reasons": dict(blocked_reasons.most_common(30)),
        },
        "quality_gates": {
            "all_ready_have_candidate_paths": all(bool(item.get("candidate_change_surface_paths")) for item in candidates),
            "all_ready_have_verifier_paths": all(bool(item.get("verifier_and_test_constraint_paths")) for item in candidates),
            "all_ready_have_symptom_paths": all(bool(item.get("symptom_or_call_path_analogue_paths")) for item in candidates),
            "all_ready_have_language": all(item.get("language_family") in {"python", "rust", "c_cpp", "web_js_ts_html"} for item in candidates),
        },
        "source_artifacts": {"retrieval_rows": rel(RETRIEVAL_ROWS)},
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "candidates_jsonl": rel(CANDIDATES_JSONL),
            "blocked_jsonl": rel(BLOCKED_JSONL),
        },
    }
    write_jsonl(CANDIDATES_JSONL, candidates)
    write_jsonl(BLOCKED_JSONL, blocked)
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
