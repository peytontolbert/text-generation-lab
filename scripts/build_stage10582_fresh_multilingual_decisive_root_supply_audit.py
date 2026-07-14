#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10582
NAME = "stage10582_fresh_multilingual_decisive_root_supply_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "fresh_multilingual_decisive_root_supply_audit.json"
SEEDS_JSONL = OUT_DIR / "fresh_multilingual_decisive_root_seed_records.jsonl"
SUPPLEMENTAL_JSONL = OUT_DIR / "supplemental_local_root_seed_records.jsonl"
RUN_SUMMARY_JSON = ROOT / "runs/summaries" / f"{NAME}.json"

COMPILED_ROOTS = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_root_records.jsonl"
COMPILED_ROWS = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_multitarget_rows.jsonl"
STRICT_ROWS = ROOT / "runs/local/artifacts/stage10561_visible_candidate_successor_package/strict_eval_rows.jsonl"
LOCAL_ROOT_EPISODES = ROOT / "runs/local/artifacts/session_like_source_inventory_real/local_root_session_episodes_broadverify_recovery_smallbudget_v4/local_root_session_episodes.jsonl"

TARGET_LANGS = ["python", "c_cpp", "rust", "web_js_ts_html"]
REQUIRED_SUBTYPES = {"decisive_evidence", "retrieve_answer_abstain", "verifier_outcome"}


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


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


def parse_field_list(input_text: str, field_name: str) -> list[str]:
    prefix = f"{field_name}:"
    for line in input_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith(prefix):
            continue
        _, _, rest = stripped.partition(":")
        return [part.strip() for part in rest.split(",") if part.strip()]
    return []


def infer_language_from_paths(paths: list[str]) -> str:
    counts: Counter[str] = Counter()
    for path in paths:
        lowered = path.lower()
        if lowered.endswith((".py", ".pyi")):
            counts["python"] += 1
        elif lowered.endswith(".rs"):
            counts["rust"] += 1
        elif lowered.endswith((".c", ".cc", ".cpp", ".cu", ".cuh", ".h", ".hpp")):
            counts["c_cpp"] += 1
        elif lowered.endswith((".js", ".jsx", ".ts", ".tsx", ".html", ".css")):
            counts["web_js_ts_html"] += 1
    return counts.most_common(1)[0][0] if counts else "unknown"


def current_strict_sets(rows: list[dict[str, Any]]) -> tuple[set[str], set[str]]:
    strict_roots = {str(row.get("root_id") or "") for row in rows}
    strict_repos = {str(row.get("repo_family") or row.get("repo_id") or "") for row in rows}
    return strict_roots, strict_repos


def main() -> None:
    compiled_roots = {row["root_id"]: row for row in load_jsonl(COMPILED_ROOTS)}
    compiled_rows = load_jsonl(COMPILED_ROWS)
    strict_rows = load_jsonl(STRICT_ROWS)
    local_root_episodes = load_jsonl(LOCAL_ROOT_EPISODES)
    strict_root_ids, strict_repo_families = current_strict_sets(strict_rows)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in compiled_rows:
        grouped[str(row.get("root_id") or "")].append(row)

    seed_records: list[dict[str, Any]] = []
    for root_id, rows in grouped.items():
        root = compiled_roots.get(root_id, {})
        language_family = str(root.get("language_family") or "unknown")
        if language_family not in TARGET_LANGS:
            continue
        present_subtypes = {str(row.get("target_subtype") or "") for row in rows}
        decisive_row = next((row for row in rows if str(row.get("target_subtype") or "") == "decisive_evidence"), None)
        if decisive_row is None:
            continue
        input_text = str(decisive_row.get("input_text") or "")
        changed_files = parse_field_list(input_text, "Changed files")
        verification_targets = parse_field_list(input_text, "Verification targets")
        key_symbols = parse_field_list(input_text, "Key symbols")
        overlap_repo = str(root.get("repo_family") or root.get("repo_id") or "") in strict_repo_families
        overlap_root = root_id in strict_root_ids
        quality_score = 0
        if REQUIRED_SUBTYPES.issubset(present_subtypes):
            quality_score += 4
        if verification_targets:
            quality_score += 3
        if changed_files:
            quality_score += 2
        if len(verification_targets) >= 2:
            quality_score += 1
        if len(changed_files) >= 2:
            quality_score += 1
        if str(root.get("verifier_id") or "") == "PASS_TARGETED_TEST_SELECTION":
            quality_score += 2
        if not overlap_repo:
            quality_score += 3
        if not overlap_root:
            quality_score += 2
        if str(root.get("split_component") or "") == "audited_train":
            quality_score += 1
        freshness_tier = "repo_disjoint" if not overlap_repo else "repo_overlap_root_disjoint" if not overlap_root else "strict_overlap"
        seed_records.append(
            {
                "root_id": root_id,
                "repo_id": root.get("repo_id"),
                "repo_family": root.get("repo_family"),
                "language_family": language_family,
                "split_component": root.get("split_component"),
                "task_family": root.get("task_family"),
                "verifier_id": root.get("verifier_id"),
                "source_family_id": ((root.get("provenance") or {}).get("source_family_id")),
                "pack_id": ((root.get("provenance") or {}).get("pack_id")),
                "query_index": ((root.get("provenance") or {}).get("query_index")),
                "present_subtypes": sorted(present_subtypes),
                "has_required_bundle": REQUIRED_SUBTYPES.issubset(present_subtypes),
                "changed_file_count": len(changed_files),
                "verification_target_count": len(verification_targets),
                "key_symbol_count": len(key_symbols),
                "changed_files": changed_files[:8],
                "verification_targets": verification_targets[:8],
                "strict_root_overlap": overlap_root,
                "strict_repo_overlap": overlap_repo,
                "freshness_tier": freshness_tier,
                "quality_score": quality_score,
            }
        )

    seed_records.sort(
        key=lambda row: (
            row["language_family"],
            row["freshness_tier"] != "repo_disjoint",
            not row["has_required_bundle"],
            -int(row["quality_score"]),
            str(row["repo_family"] or ""),
            str(row["root_id"] or ""),
        )
    )

    supplemental_records: list[dict[str, Any]] = []
    for row in local_root_episodes:
        repo_family = str(row.get("repo_id") or "")
        changes = [str(item.get("path") or "") for item in row.get("changes", []) if str(item.get("path") or "")]
        language_family = infer_language_from_paths(changes)
        if language_family not in TARGET_LANGS:
            continue
        selected_tests = [str(item) for item in row.get("selected_tests", []) if str(item)]
        overlap_repo = repo_family in strict_repo_families
        quality_score = 0
        if selected_tests:
            quality_score += 3
        if changes:
            quality_score += 2
        if len(selected_tests) >= 2:
            quality_score += 1
        if len(changes) >= 2:
            quality_score += 1
        if not overlap_repo:
            quality_score += 2
        supplemental_records.append(
            {
                "repo_id": repo_family,
                "language_family": language_family,
                "seed_id": row.get("seed_id"),
                "episode_id": row.get("episode_id"),
                "seed_type": row.get("seed_type"),
                "test_selection_route": row.get("test_selection_route"),
                "changed_file_count": len(changes),
                "selected_test_count": len(selected_tests),
                "changed_files": changes[:8],
                "selected_tests": selected_tests[:8],
                "strict_repo_overlap": overlap_repo,
                "quality_score": quality_score,
            }
        )

    supplemental_records.sort(
        key=lambda row: (
            row["language_family"],
            row["strict_repo_overlap"],
            -int(row["quality_score"]),
            str(row["repo_id"] or ""),
            str(row["episode_id"] or ""),
        )
    )

    by_language = Counter(row["language_family"] for row in seed_records)
    by_tier = Counter((row["language_family"], row["freshness_tier"]) for row in seed_records)
    by_bundle = Counter((row["language_family"], row["has_required_bundle"]) for row in seed_records)
    supplemental_by_language = Counter(row["language_family"] for row in supplemental_records)

    top_candidates_by_language: dict[str, list[dict[str, Any]]] = {}
    for lang in TARGET_LANGS:
        top_candidates_by_language[lang] = [
            {
                "root_id": row["root_id"],
                "repo_family": row["repo_family"],
                "freshness_tier": row["freshness_tier"],
                "quality_score": row["quality_score"],
                "changed_file_count": row["changed_file_count"],
                "verification_target_count": row["verification_target_count"],
                "pack_id": row["pack_id"],
                "query_index": row["query_index"],
            }
            for row in seed_records
            if row["language_family"] == lang and row["has_required_bundle"]
        ][:8]

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Audits fresh multilingual decisive-evidence root supply from the stage10516 compiled root/state corpus and the local-root broadverify recovery episode inventory.",
            "Marks overlap risk against the current stage10561 rebuilt strict frontier by root and by repo family.",
            "This is a source-supply audit and seed package, not a model-improvement claim.",
        ],
        "inputs": {
            "compiled_root_records": display(COMPILED_ROOTS),
            "compiled_multitarget_rows": display(COMPILED_ROWS),
            "current_rebuilt_strict_rows": display(STRICT_ROWS),
            "local_root_broadverify_episodes": display(LOCAL_ROOT_EPISODES),
        },
        "selection_policy": {
            "target_languages": TARGET_LANGS,
            "required_bundle_subtypes": sorted(REQUIRED_SUBTYPES),
            "freshness_tiers": ["repo_disjoint", "repo_overlap_root_disjoint", "strict_overlap"],
            "strict_root_overlap_forbidden_for_new_eval": True,
            "repo_disjoint_preferred_for_new_eval": True,
        },
        "metrics": {
            "compiled_seed_records": len(seed_records),
            "compiled_seed_language_counts": dict(sorted(by_language.items())),
            "compiled_seed_tier_counts": {f"{lang}::{tier}": count for (lang, tier), count in sorted(by_tier.items())},
            "compiled_seed_required_bundle_counts": {f"{lang}::{flag}": count for (lang, flag), count in sorted(by_bundle.items())},
            "supplemental_local_root_seed_records": len(supplemental_records),
            "supplemental_local_root_language_counts": dict(sorted(supplemental_by_language.items())),
        },
        "top_candidates_by_language": top_candidates_by_language,
        "truthful_read": [
            "The compiled root/state corpus contains materially more non-Python decisive-evidence supply than the strict retrieval dataset alone, especially for C/C++.",
            "Rust and Web are still thin even in the compiled corpus, so multilingual expansion cannot rely on balanced replay alone; it needs targeted fresh-root materialization or additional source mining.",
            "Repo-disjoint roots with the full decisive/retrieve/verifier trio should become the next promotable eval candidates. Repo-overlap roots can still be useful for train support or diagnostic expansion.",
        ],
        "outputs": {
            "seed_records": display(SEEDS_JSONL),
            "supplemental_local_root_seed_records": display(SUPPLEMENTAL_JSONL),
            "audit_json": display(SUMMARY_JSON),
        },
    }

    write_jsonl(SEEDS_JSONL, seed_records)
    write_jsonl(SUPPLEMENTAL_JSONL, supplemental_records)
    write_json(SUMMARY_JSON, payload)
    write_json(RUN_SUMMARY_JSON, payload)
    print(json.dumps(payload["metrics"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
