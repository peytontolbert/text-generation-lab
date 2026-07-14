#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
STAGE = 11344
NAME = "stage11344_rust_web_source_verifier_blocker_audit"
OUT = ART / NAME
SUMMARY = OUT / "rust_web_source_verifier_blocker_audit.json"
OUT_BLOCKERS = OUT / "source_verifier_blocker_queue.jsonl"
OUT_ACTIONS = OUT / "next_materialization_actions.jsonl"

STAGE11331 = ART / "stage11331_rust_web_gap_recovery_manifest/rust_web_gap_recovery_manifest.json"
RUST_ADMITTED = ART / "stage11331_rust_web_gap_recovery_manifest/admitted_rust_strict_replacement_rows.jsonl"
WEB_READY = ART / "stage11331_rust_web_gap_recovery_manifest/web_ready_candidate_queue.jsonl"
RUST_WEB_BLOCKED = ART / "stage11331_rust_web_gap_recovery_manifest/rust_web_blocked_source_queue.jsonl"
WEB_SNIPPETS = ART / "stage11338_web_source_snippet_evidence_materialization/web_source_snippet_evidence_rows.jsonl"
STAGE11343 = ART / "stage11343_web_source_snippet_support_decision/web_source_snippet_support_decision.json"
CANARY_TRAIN = ART / "stage11312_deleaked_fail_to_pass_transition_package/deleaked_fail_to_pass_train_rows.jsonl"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def lang(row: dict[str, Any]) -> str:
    return str(row.get("language_family") or row.get("language") or "unknown")


def blockers(row: dict[str, Any]) -> list[str]:
    raw = row.get("blockers") or row.get("stage11311_blockers") or []
    if isinstance(raw, str):
        return [raw]
    return [str(x) for x in raw]


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(r.get(key) or "unknown") for r in rows).items()))


def semantic_value(row: dict[str, Any]) -> str:
    projection = row.get("standalone_projection_source") or {}
    return str(row.get("semantic_target_value") or projection.get("gold_value") or "unknown")


def canonical_root_key(value: Any) -> str:
    text = str(value or "").lower()
    text = text.replace("stage11237::", "")
    text = text.replace("audited::", "")
    text = text.replace("retrieval::", "")
    text = text.replace("dbt-core::", "dbt_core::")
    text = text.replace("::q", "::")
    return text


def row_root_keys(row: dict[str, Any]) -> set[str]:
    keys = set()
    for field in ("root_id", "source_root_id", "source_row_id", "root_lineage_key"):
        value = row.get(field)
        if value:
            keys.add(canonical_root_key(value))
    return keys


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    rust_admitted = read_jsonl(RUST_ADMITTED)
    web_ready = read_jsonl(WEB_READY)
    blocked = read_jsonl(RUST_WEB_BLOCKED)
    web_snippets = read_jsonl(WEB_SNIPPETS)
    decision = read_json(STAGE11343)
    recovery = read_json(STAGE11331)
    canary_train = read_jsonl(CANARY_TRAIN)
    canary_train_root_keys = set()
    for row in canary_train:
        canary_train_root_keys.update(row_root_keys(row))

    blocked_by_lang_reason: dict[str, Counter[str]] = defaultdict(Counter)
    blocker_queue = []
    for row in blocked:
        row_lang = lang(row)
        reasons = blockers(row) or ["unspecified_source_verifier_blocker"]
        for reason in reasons:
            blocked_by_lang_reason[row_lang][reason] += 1
        blocker_queue.append(
            {
                "source_row_id": row.get("source_row_id"),
                "root_id": row.get("root_id") or row.get("source_root_id"),
                "repo_family": row.get("repo_family"),
                "language_family": row_lang,
                "blockers": reasons,
                "required_to_admit": [
                    "local_or_fetchable_repo_snapshot",
                    "changed_source_or_config_path",
                    "selected_test_or_verifier_path",
                    "distinct_visible_snippets_for_candidate_roles",
                    "no_role_alias_or_prompt_target_leak",
                ],
                "usable_now": False,
            }
        )

    web_roots = sorted({str(r.get("root_id")) for r in web_snippets})
    web_by_gold = count_by(web_snippets, "semantic_target_value")
    rust_replacement_roots = sorted({str(r.get("root_id")) for r in rust_admitted})
    rust_by_gold = dict(sorted(Counter(semantic_value(r) for r in rust_admitted).items()))
    web_ready_replay_overlap = [
        row for row in web_ready
        if row_root_keys(row) & canary_train_root_keys
    ]
    rust_ready_overlap_count = sum(
        1
        for row in read_jsonl(ART / "stage11237_multilingual_verifier_constraint_source_inventory/verifier_constraint_source_candidates.jsonl")
        if lang(row) == "rust"
        and row_root_keys(row) & canary_train_root_keys
    )

    product_metrics = decision.get("product_metrics") or {}
    web_metric = product_metrics.get("web_source_snippet_support") or {}
    rust_metric = product_metrics.get("rust_admitted_replacements") or {}
    canary_metric = product_metrics.get("canary_strict") or {}

    actions = [
        {
            "priority": 1,
            "lane": "web_source_backed_verifier_roots",
            "action": "acquire_locked_sphinx_or_new_pure_web_task_roots_with_executed_verifier_output",
            "why": "Stage11338 rows include snippets but no locked historical commit or executed verifier transition; Stage11341 stayed 7/21.",
            "minimum_acceptance": {
                "new_roots": 10,
                "must_include": [
                    "locked_commit",
                    "changed_path",
                    "selected_test_or_fixture",
                    "observed_expected_actual_or_test_result",
                    "source_snippet",
                    "verifier_snippet",
                    "symptom_or_call_path_snippet",
                ],
                "split_policy": "root-disjoint before row projection",
            },
        },
        {
            "priority": 2,
            "lane": "rust_train_support_supply",
            "action": "materialize_disjoint_rust_evidence_train_roots_instead_of_training_on_reserved_replacements",
            "why": "Rust rows are admitted as strict replacements and current runtime scores 1/3; they are not train support.",
            "minimum_acceptance": {
                "new_roots": 10,
                "must_include": [
                    "non_tokenizers_repo_family_or_fresh_time_split",
                    "selected_test_or_verifier_anchor",
                    "distinct_candidate_change_surface",
                    "distinct_symptom_or_call_path",
                    "distinct_verifier_and_test_constraint",
                ],
                "split_policy": "train roots must not overlap rust admitted replacement roots",
            },
        },
        {
            "priority": 3,
            "lane": "scorer_objective",
            "action": "prototype_semantic_evidence_candidate_objective_on_clean_source_verifier_rows",
            "why": "Path-only and snippet Web support preserved canary but did not move target rows; prior scorer heads failed on weak/alias-prone residual geometry.",
            "minimum_acceptance": {
                "candidate_contract": [
                    "state_text",
                    "candidate_evidence_text",
                    "candidate_role_metadata",
                    "binary_gold_or_pairwise_preference",
                ],
                "promotion_gate": [
                    "canary_strict_not_below_stage11200",
                    "web_source_snippet_support_above_7_of_21",
                    "rust_replacements_above_1_of_3_or_no_rust_claim",
                ],
            },
        },
    ]

    write_jsonl(OUT_BLOCKERS, blocker_queue)
    write_jsonl(OUT_ACTIONS, actions)

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "dataset_repair_required_before_more_support_probes",
        "kept_frontier": {
            "stage": 11200,
            "reason": "Stage11343 rejected Stage11341; canary was preserved but Web/Rust target slices did not improve.",
        },
        "observed_scores": {
            "web_source_snippet_support": web_metric,
            "rust_admitted_replacements": rust_metric,
            "canary_strict": canary_metric,
        },
        "inventory": {
            "rust_admitted_reserved_replacement_rows": len(rust_admitted),
            "rust_admitted_reserved_replacement_roots": len(rust_replacement_roots),
            "rust_admitted_by_gold": rust_by_gold,
            "web_ready_candidates_from_stage11331": len(web_ready),
            "web_source_snippet_support_rows": len(web_snippets),
            "web_source_snippet_support_roots": len(web_roots),
            "web_source_snippet_by_gold": web_by_gold,
            "blocked_rust_web_source_rows": len(blocked),
            "blocked_by_language": count_by(blocked, "language_family"),
            "blocked_by_language_reason": {
                k: dict(sorted(v.items())) for k, v in sorted(blocked_by_lang_reason.items())
            },
            "ready_rust_candidates_already_in_train": rust_ready_overlap_count,
            "web_ready_candidates_already_in_train": len(web_ready_replay_overlap),
        },
        "admissibility": {
            "train_again_on_stage11338_rows": False,
            "use_rust_admitted_rows_as_train_support": False,
            "headline_multilingual_claim_ready": False,
            "why": [
                "Stage11338 rows are support-only snippets without executed verifier output.",
                "Stage11341 did not improve Web source-snippet support beyond 7/21.",
                "Rust rows are reserved strict replacements, not disjoint train roots.",
                "Ready dbt_core Rust candidates are already represented in current train support.",
                "Blocked Rust/Web roots still need concrete changed+verifier source pairs.",
            ],
        },
        "next_actions": actions,
        "source_artifacts": {
            "stage11331_summary": rel(STAGE11331),
            "rust_admitted_rows": rel(RUST_ADMITTED),
            "web_ready_queue": rel(WEB_READY),
            "rust_web_blocked_queue": rel(RUST_WEB_BLOCKED),
            "web_source_snippet_rows": rel(WEB_SNIPPETS),
            "stage11343_decision": rel(STAGE11343),
        },
        "source_stage11331_counts": recovery.get("counts", {}),
        "outputs": {
            "summary": rel(SUMMARY),
            "source_verifier_blocker_queue": rel(OUT_BLOCKERS),
            "next_materialization_actions": rel(OUT_ACTIONS),
        },
    }
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
