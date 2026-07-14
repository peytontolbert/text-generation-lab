#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11177
NAME = "stage11177_root_disjoint_evidence_materialization_queue"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "root_disjoint_evidence_materialization_queue.json"
QUEUE_JSONL = OUT_DIR / "materialization_work_items.jsonl"
ROOT_CARDS_JSONL = OUT_DIR / "selected_root_cards.jsonl"

ROOT_MANIFEST = ARTIFACTS / "stage10784_root_admission_manifest_v5" / "root_admission_manifest_v5.jsonl"
CONTRACT = ARTIFACTS / "stage11175_clean_evidence_role_rewrite_package" / "evidence_role_admission_contract.json"
TRAINABLE_AUDIT = ARTIFACTS / "stage11176_trainable_evidence_contract_audit" / "trainable_evidence_contract_audit.json"
CURRENT_ROW_SOURCES = [
    ARTIFACTS / "stage11146_singleton_strict_quarantine_successor" / "agentkernel_lite_encdec_strict_eval.jsonl",
    ARTIFACTS / "stage11146_singleton_strict_quarantine_successor" / "agentkernel_lite_encdec_validation.jsonl",
    ARTIFACTS / "stage11051_successor_residual_support_plus_priority_evidence" / "reserved_residual_candidates.jsonl",
]

LANGUAGE_TARGET_ROOTS = {
    "python": 12,
    "c_cpp": 12,
    "rust": 7,
    "web_js_ts_html": 8,
}
ROLE_TARGETS = [
    "candidate_change_surface",
    "verifier_and_test_constraint",
    "symptom_or_call_path_analogue",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def current_exclusions() -> dict[str, set[str]]:
    roots: set[str] = set()
    repos: set[str] = set()
    row_ids: set[str] = set()
    for path in CURRENT_ROW_SOURCES:
        for row in load_jsonl(path):
            if row.get("source_root_id"):
                roots.add(str(row["source_root_id"]))
            if row.get("repo_family"):
                repos.add(str(row["repo_family"]))
            if row.get("row_id"):
                row_ids.add(str(row["row_id"]))
    return {"roots": roots, "repos": repos, "row_ids": row_ids}


def root_quality_key(row: dict[str, Any]) -> tuple[int, int, float, str]:
    selected = 1 if row.get("selected_test_anchor") else 0
    verifier = 1 if row.get("verifier_anchor") else 0
    quality = float(row.get("quality_score") or 0.0)
    return (selected + verifier, selected, quality, str(row.get("root_id") or ""))


def select_roots(rows: list[dict[str, Any]], exclusions: dict[str, set[str]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for row in rows:
        root_id = str(row.get("root_id") or "")
        repo = str(row.get("repo_family") or "")
        lang = str(row.get("language_family") or "")
        if not root_id or lang not in LANGUAGE_TARGET_ROOTS:
            continue
        if root_id in exclusions["roots"] or repo in exclusions["repos"]:
            continue
        if not (row.get("selected_test_anchor") or row.get("verifier_anchor")):
            continue
        candidates.append(row)

    by_lang_repo: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in candidates:
        by_lang_repo[str(row.get("language_family"))][str(row.get("repo_family") or "unknown")].append(row)
    for repos in by_lang_repo.values():
        for repo_rows in repos.values():
            repo_rows.sort(key=root_quality_key, reverse=True)

    selected: list[dict[str, Any]] = []
    for lang, target in LANGUAGE_TARGET_ROOTS.items():
        repos = by_lang_repo.get(lang, {})
        round_robin: list[dict[str, Any]] = []
        offsets = {repo: 0 for repo in repos}
        while len(round_robin) < target:
            moved = False
            for repo in sorted(repos):
                idx = offsets[repo]
                if idx < len(repos[repo]):
                    round_robin.append(repos[repo][idx])
                    offsets[repo] = idx + 1
                    moved = True
                    if len(round_robin) >= target:
                        break
            if not moved:
                break
        selected.extend(round_robin)
    return selected


def work_items_for_root(root: dict[str, Any]) -> list[dict[str, Any]]:
    root_id = str(root.get("root_id") or "")
    lang = str(root.get("language_family") or "unknown")
    repo = str(root.get("repo_family") or "unknown")
    items: list[dict[str, Any]] = []
    for role in ROLE_TARGETS:
        item_id = f"stage11177::{root_id}::evidence_citation::{role}"
        role_requirements = {
            "candidate_change_surface": [
                "Candidate surface evidence must be the unique strongest support; verifier text must not independently argue that candidate surface is correct.",
                "Include a plausible verifier/test distractor that is visibly less specific than the candidate surface evidence.",
            ],
            "verifier_and_test_constraint": [
                "Expose selected test, verifier route, assertion, command, or transition as independent evidence.",
                "Candidate surface must remain a plausible but wrong distractor, not a duplicate of verifier evidence.",
            ],
            "symptom_or_call_path_analogue": [
                "Expose symptom/call-path/trace evidence as a distinct visible fact, not the same path/span as candidate_change_surface.",
                "If source material cannot separate symptom/call-path from candidate surface, mark this item blocked instead of forcing gold.",
            ],
        }[role]
        items.append(
            {
                "work_item_id": item_id,
                "stage": STAGE,
                "source_root_id": root_id,
                "root_lineage_key": root.get("root_lineage_key"),
                "repo_family": repo,
                "repo_id": root.get("repo_id"),
                "language_family": lang,
                "snapshot_id": root.get("snapshot_id"),
                "source_family_id": root.get("source_family_id"),
                "target_task_type": "evidence_citation",
                "target_gold_value": role,
                "admit_role": "materialization_queue_train_support_candidate",
                "selected_test_anchor": bool(root.get("selected_test_anchor")),
                "verifier_anchor": bool(root.get("verifier_anchor")),
                "quality_score": root.get("quality_score"),
                "materialization_status": root.get("materialization_status"),
                "required_outputs": [
                    "One bounded evidence_citation row with opaque labels and deterministic/recorded option shuffle.",
                    "Visible evidence ledger with separate candidate, verifier/test, symptom/call-path, and nearby context entries.",
                    "Machine-readable option mapping and gold semantic value.",
                    "Anti-cheat card proving no target-path leakage before options and no duplicated role span.",
                ],
                "role_specific_requirements": role_requirements,
                "admission_contract": "stage11175 evidence_role_admission_contract_v1",
                "train_eval_policy": "train_support_candidate_only_until materialized row passes contract and root split is frozen",
                "query_text": root.get("query_text"),
                "notes": root.get("notes"),
            }
        )
    return items


def main() -> None:
    contract = load_json(CONTRACT)
    trainable_audit = load_json(TRAINABLE_AUDIT)
    exclusions = current_exclusions()
    roots = load_jsonl(ROOT_MANIFEST)
    selected = select_roots(roots, exclusions)
    work_items: list[dict[str, Any]] = []
    for root in selected:
        work_items.extend(work_items_for_root(root))

    lang_root_counts = Counter(str(root.get("language_family") or "unknown") for root in selected)
    repo_counts = Counter(str(root.get("repo_family") or "unknown") for root in selected)
    role_counts = Counter(str(item["target_gold_value"]) for item in work_items)
    lang_role_counts = Counter((str(item["language_family"]), str(item["target_gold_value"])) for item in work_items)
    selected_test_counts = Counter(str(root.get("language_family") or "unknown") for root in selected if root.get("selected_test_anchor"))
    verifier_counts = Counter(str(root.get("language_family") or "unknown") for root in selected if root.get("verifier_anchor"))

    undersupplied_languages = [lang for lang, target in LANGUAGE_TARGET_ROOTS.items() if lang_root_counts.get(lang, 0) < target]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "root_disjoint_evidence_materialization_queue_ready",
        "source_artifacts": {
            "root_manifest": rel(ROOT_MANIFEST),
            "contract": rel(CONTRACT),
            "trainable_evidence_audit": rel(TRAINABLE_AUDIT),
            "current_exclusion_sources": [rel(path) for path in CURRENT_ROW_SOURCES],
        },
        "exclusions": {
            "excluded_roots": len(exclusions["roots"]),
            "excluded_repo_families": sorted(exclusions["repos"]),
        },
        "selection_policy": {
            "language_target_roots": LANGUAGE_TARGET_ROOTS,
            "roles_per_root": ROLE_TARGETS,
            "exclude_current_strict_validation_reserved_roots_and_repo_families": True,
            "require_selected_test_or_verifier_anchor": True,
            "repo_balanced_round_robin_with_quality_sort": True,
        },
        "counts": {
            "selected_roots": len(selected),
            "work_items": len(work_items),
            "language_root_counts": dict(sorted(lang_root_counts.items())),
            "selected_test_root_counts": dict(sorted(selected_test_counts.items())),
            "verifier_root_counts": dict(sorted(verifier_counts.items())),
            "repo_family_counts": dict(sorted(repo_counts.items())),
            "role_counts": dict(sorted(role_counts.items())),
            "language_role_counts": {f"{lang}::{role}": count for (lang, role), count in sorted(lang_role_counts.items())},
            "undersupplied_languages_vs_target": undersupplied_languages,
        },
        "contract_summary": {
            "contract_name": contract.get("contract_name"),
            "reject_if": contract.get("reject_if"),
        },
        "why_this_moves_the_frontier": [
            "Fills the missing symptom_or_call_path_analogue positive lane that stage11176 found absent from trainable support.",
            "Adds root-disjoint Rust and Web materialization targets instead of recycling tokenizers/candle/bddy/code_assist heldout/reserved rows.",
            "Keeps candidate_change_surface positive controls balanced against verifier_and_test_constraint so role-map-style overcorrection can be audited.",
        ],
        "not_yet_trainable": [
            "These are materialization work items, not admitted train rows.",
            "Each item must be converted into a concrete visible evidence ledger and pass the stage11175 contract before inclusion in a training package.",
        ],
        "next_best_step": "Materialize these work items into concrete evidence_citation rows, then run a contract admission audit before training a semantic evidence scorer objective.",
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "queue_jsonl": rel(QUEUE_JSONL),
            "root_cards_jsonl": rel(ROOT_CARDS_JSONL),
        },
    }
    write_json(SUMMARY_JSON, summary)
    write_jsonl(QUEUE_JSONL, work_items)
    write_jsonl(ROOT_CARDS_JSONL, selected)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
