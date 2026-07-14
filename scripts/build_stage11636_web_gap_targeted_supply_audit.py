#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11636
NAME = "stage11636_web_gap_targeted_supply_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_gap_targeted_supply_audit.json"
WORKLIST = OUT / "web_gap_targeted_worklist.jsonl"

WEB_ROWS = ART / "stage11548_web_root_heldout_stage11507_score_audit/web_root_heldout_rows.jsonl"
STAGE11507_AUDIT = ART / "stage11548_web_root_heldout_stage11507_score_audit/bounded_choice_eval_audit_web_root_heldout_encoder_option_retrieval_evidence_judgment_head.json"
ROUTED_WEB_AUDIT = ART / "stage11631_web_head_only_transfer_audit/bounded_choice_eval_audit_web_heldout.json"
GEMMA_ROWS = ART / "stage11549_web_root_heldout_same_manifest_gemma_comparison/web_root_heldout_gemma_rows.jsonl"
STAGE11635 = ART / "stage11635_routed_product_gemma_comparison_audit/routed_product_gemma_comparison_audit.json"

SUPPORT_SOURCES = {
    "stage11580_verifier_attached": ART / "stage11580_web_verifier_attached_admission_package/web_verifier_attached_rows.jsonl",
    "stage11594_repaired_geometry": ART / "stage11594_web_verifier_attached_repaired_geometry_package/web_verifier_attached_repaired_rows.jsonl",
    "stage11621_fail_to_pass_repaired": ART / "stage11621_web_fail_to_pass_row_geometry_repair/web_fail_to_pass_geometry_repaired_train_support.jsonl",
    "stage11570_semantic_non_evidence": ART / "stage11570_semantic_web_non_evidence_support_package/semantic_web_non_evidence_train_rows.jsonl",
}

WEB_GAP_REPOS = {"openhands_openhands_frontend", "llama_stack_ui"}
REPO_ALIASES = {
    "frontend": "openhands_openhands_frontend",
    "openhands_frontend": "openhands_openhands_frontend",
    "openhands_openhands_frontend": "openhands_openhands_frontend",
    "llama_stack_ui": "llama_stack_ui",
}
PRIORITY_TASKS = {
    "evidence_citation",
    "alternative_hypothesis_elimination",
    "verifier_outcome",
    "symptom_localization",
    "minimal_fix_selection",
    "abstention_insufficient_evidence",
}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def normalize_repo_family(value: Any) -> str:
    raw = str(value or "unknown")
    return REPO_ALIASES.get(raw, raw)


def card_map(path: Path) -> dict[str, dict[str, Any]]:
    data = load_json(path)
    return {str(card.get("row_id")): card for card in data.get("row_cards", []) if card.get("row_id")}


def support_index() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    by_source: dict[str, Any] = {}
    all_rows: list[dict[str, Any]] = []
    for name, path in SUPPORT_SOURCES.items():
        rows = load_jsonl(path)
        all_rows.extend({**row, "_support_source": name} for row in rows)
        by_source[name] = {
            "path": rel(path),
            "exists": path.exists(),
            "rows": len(rows),
            "roots": len({str(row.get("root_id")) for row in rows if row.get("root_id")}),
            "repo_family_counts": dict(Counter(normalize_repo_family(row.get("repo_family")) for row in rows)),
            "task_type_counts": dict(Counter(str(row.get("task_type") or "unknown") for row in rows)),
        }
    by_gap_repo_task: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    by_gap_repo_roots: dict[str, set[str]] = defaultdict(set)
    for row in all_rows:
        repo = normalize_repo_family(row.get("repo_family"))
        task = str(row.get("task_type") or "unknown")
        if repo in WEB_GAP_REPOS:
            by_gap_repo_task[repo][task] += 1
            if row.get("root_id"):
                by_gap_repo_roots[repo].add(str(row["root_id"]))
    aggregate = {
        "sources": by_source,
        "gap_repo_task_counts": {repo: dict(tasks) for repo, tasks in sorted(by_gap_repo_task.items())},
        "gap_repo_root_counts": {repo: len(roots) for repo, roots in sorted(by_gap_repo_roots.items())},
        "total_rows": len(all_rows),
        "total_roots": len({str(row.get("root_id")) for row in all_rows if row.get("root_id")}),
    }
    return aggregate, all_rows


def metric(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    total = len(rows)
    correct = sum(1 for row in rows if row.get(key) is True)
    return {"rows": total, "correct": correct, "accuracy": correct / total if total else None}


def grouped(rows: list[dict[str, Any]], group_key: str, correct_key: str) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get(group_key) or "unknown")].append(row)
    return {key: metric(bucket, correct_key) for key, bucket in sorted(buckets.items())}


def main() -> None:
    web_rows = {str(row.get("row_id")): row for row in load_jsonl(WEB_ROWS)}
    stage11507_cards = card_map(STAGE11507_AUDIT)
    routed_cards = card_map(ROUTED_WEB_AUDIT)
    gemma = {str(row.get("row_id")): row for row in load_jsonl(GEMMA_ROWS)}
    support, _ = support_index()

    joined: list[dict[str, Any]] = []
    for row_id, row in sorted(web_rows.items()):
        base = stage11507_cards.get(row_id, {})
        routed = routed_cards.get(row_id, {})
        gemma_row = gemma.get(row_id, {})
        rec = {
            "row_id": row_id,
            "root_id": row.get("root_id"),
            "repo_family": normalize_repo_family(row.get("repo_family")),
            "task_type": row.get("task_type"),
            "target_text": row.get("target_text"),
            "semantic_target_value": row.get("semantic_target_value"),
            "stage11507_correct": base.get("constrained_choice_match") is True,
            "stage11507_predicted_label": base.get("constrained_choice_top1_label"),
            "routed_correct": routed.get("constrained_choice_match") is True,
            "routed_predicted_label": routed.get("constrained_choice_top1_label"),
            "gemma12b_correct": gemma_row.get("gemma12b_correct") is True,
            "gemma12b_predicted_label": gemma_row.get("gemma12b_predicted_label"),
            "full_vocab_top1_text_routed": routed.get("full_vocab_top1_text"),
            "target_rank_full_vocab_routed": routed.get("target_rank_full_vocab"),
        }
        rec["blocks_web_gemma_win"] = rec["gemma12b_correct"] and not rec["routed_correct"]
        rec["routed_recovered_from_stage11507"] = rec["routed_correct"] and not rec["stage11507_correct"]
        rec["regressed_from_stage11507"] = rec["stage11507_correct"] and not rec["routed_correct"]
        joined.append(rec)

    blockers = [row for row in joined if row["blocks_web_gemma_win"]]
    recovered = [row for row in joined if row["routed_recovered_from_stage11507"]]
    regressions = [row for row in joined if row["regressed_from_stage11507"]]

    work_items: list[dict[str, Any]] = []
    blocker_buckets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in blockers:
        blocker_buckets[(str(row["repo_family"]), str(row["task_type"]))].append(row)
    support_task_counts = support["gap_repo_task_counts"]
    for (repo, task), bucket in sorted(blocker_buckets.items(), key=lambda item: (-len(item[1]), item[0])):
        existing_support = int((support_task_counts.get(repo) or {}).get(task, 0))
        needed_roots = 10 if repo in WEB_GAP_REPOS else 4
        priority = "highest" if repo in WEB_GAP_REPOS and task in PRIORITY_TASKS else "medium"
        work_items.append(
            {
                "repo_family": repo,
                "task_type": task,
                "blocking_rows": len(bucket),
                "example_blocking_row_ids": [row["row_id"] for row in bucket[:5]],
                "existing_train_support_rows_for_repo_task": existing_support,
                "recommended_new_root_target": needed_roots,
                "priority": priority,
                "materialization_requirements": [
                    "root-disjoint from web_root_heldout_66",
                    "real verifier/test anchor or executed transition",
                    "opaque deterministic options",
                    "no target value visible before options",
                    "candidate_change_surface and verifier/test constraint present as hard competitors where applicable",
                    "row must include selected verifier path and observed transition when task_type is verifier_outcome",
                ],
            }
        )

    rows_by_repo = grouped(joined, "repo_family", "routed_correct")
    rows_by_task = grouped(joined, "task_type", "routed_correct")
    blocker_by_repo = dict(Counter(str(row["repo_family"]) for row in blockers))
    blocker_by_task = dict(Counter(str(row["task_type"]) for row in blockers))

    gates = {
        "same_row_inputs_complete": len(web_rows) == len(stage11507_cards) == len(routed_cards) == len(gemma) == 66,
        "routed_improves_stage11507": metric(joined, "routed_correct")["correct"] > metric(joined, "stage11507_correct")["correct"],
        "routed_beats_gemma": metric(joined, "routed_correct")["correct"] > metric(joined, "gemma12b_correct")["correct"],
        "worklist_nonempty": bool(work_items),
        "openhands_or_llama_blockers_present": any(row["repo_family"] in WEB_GAP_REPOS for row in blockers),
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "web_gap_worklist_ready_routed_still_loses_to_gemma",
        "gates": gates,
        "metrics": {
            "stage11507": metric(joined, "stage11507_correct"),
            "routed": metric(joined, "routed_correct"),
            "gemma12b": metric(joined, "gemma12b_correct"),
            "routed_recovered_from_stage11507_rows": len(recovered),
            "routed_regressed_from_stage11507_rows": len(regressions),
            "gemma_correct_routed_wrong_blockers": len(blockers),
        },
        "routed_by_repo_family": rows_by_repo,
        "routed_by_task_type": rows_by_task,
        "gemma_correct_routed_wrong_by_repo_family": blocker_by_repo,
        "gemma_correct_routed_wrong_by_task_type": blocker_by_task,
        "support_inventory": support,
        "worklist_rows": len(work_items),
        "claim_boundary": [
            "This is a targeting audit, not a model promotion.",
            "The routed scorer improves Web heldout but still trails Gemma on the same 66 rows.",
            "New training should be gated on closing these blocker buckets without regressing protected canary/residual gates.",
        ],
        "recommended_next_stage": {
            "name": "stage11637_web_gap_root_materialization_request",
            "minimum_admission_gate": {
                "new_openhands_roots": 10,
                "new_llama_stack_roots": 10,
                "all_six_task_types_per_root": True,
                "selected_verifier_or_executed_transition_required": True,
                "heldout_overlap_allowed": False,
            },
            "promotion_gate_after_training": {
                "protected_filtered_strict": "22/22",
                "protected_old_canary_strict": "23/23",
                "protected_residual_bank": ">=7/10",
                "web_heldout": ">38/66 first, then >52/66",
                "same_manifest_gemma_attached": True,
            },
        },
        "source_artifacts": {
            "stage11635": rel(STAGE11635),
            "web_rows": rel(WEB_ROWS),
            "stage11507_audit": rel(STAGE11507_AUDIT),
            "routed_web_audit": rel(ROUTED_WEB_AUDIT),
            "gemma_rows": rel(GEMMA_ROWS),
            **{f"support_{name}": rel(path) for name, path in SUPPORT_SOURCES.items()},
        },
        "outputs": {"summary": rel(SUMMARY), "worklist": rel(WORKLIST)},
    }

    OUT.mkdir(parents=True, exist_ok=True)
    write_json(SUMMARY, summary)
    write_jsonl(WORKLIST, work_items)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "metrics": summary["metrics"], "blockers_by_repo": blocker_by_repo, "blockers_by_task": blocker_by_task, "worklist_rows": len(work_items)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
