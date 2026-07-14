#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11612
NAME = "stage11612_web_fail_to_pass_mutation_materialization_request"
OUT = ART / NAME
SUMMARY = OUT / "web_fail_to_pass_mutation_materialization_request.json"
WORK_ITEMS = OUT / "web_fail_to_pass_mutation_work_items.jsonl"
QUARANTINE = OUT / "web_fail_to_pass_mutation_quarantine.jsonl"

SOURCE_ATLAS = ART / "stage11576_web_fresh_source_candidate_atlas/web_fresh_source_candidate_roots.jsonl"
PASS_RESULTS = ART / "stage11579_web_focused_verifier_execution/web_focused_verifier_results.jsonl"
SUPPLY_AUDIT = ART / "stage11611_web_behavior_transition_supply_audit/web_behavior_transition_supply_audit.json"

TARGET_LANES = {
    "materialize_diverse_openhands_transition_roots_with_test_ids_and_fail_pass_labels",
    "materialize_llama_stack_train_analogues_with_selected_tests_and_root_disjoint_options",
}
MAX_ITEMS_PER_REPO_FAMILY = 12


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def command_key(cmd: Any) -> list[str]:
    return [str(part) for part in cmd] if isinstance(cmd, list) else []


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    roots = load_jsonl(SOURCE_ATLAS)
    pass_results = {str(row.get("root_id")): row for row in load_jsonl(PASS_RESULTS)}
    supply = load_json(SUPPLY_AUDIT) or {}
    accepted: list[dict[str, Any]] = []
    quarantine: list[dict[str, Any]] = []
    repo_counts: Counter[str] = Counter()
    for row in roots:
        rid = str(row.get("root_id") or "")
        lane = str(row.get("lane") or "")
        repo_family = str(row.get("repo_family") or row.get("git_repo_family") or "unknown")
        pass_row = pass_results.get(rid)
        blockers: list[str] = []
        if lane not in TARGET_LANES:
            blockers.append("unsupported_lane_for_fail_to_pass_materialization")
        if not row.get("repo_path"):
            blockers.append("missing_repo_path")
        if not row.get("candidate_options_prepared"):
            blockers.append("missing_candidate_options")
        if not row.get("selected_verifier_path_proposal"):
            blockers.append("missing_selected_verifier_path")
        if pass_row is None:
            blockers.append("missing_baseline_pass_execution")
        elif pass_row.get("returncode") != 0 or pass_row.get("verifier_transition") != "PASS_TO_PASS":
            blockers.append("baseline_not_clean_pass_to_pass")
        if repo_counts[repo_family] >= MAX_ITEMS_PER_REPO_FAMILY:
            blockers.append("repo_family_cap_exceeded")
        candidate_surface = None
        verifier_surface = None
        symptom_surface = None
        for option in row.get("candidate_options_prepared") or []:
            if not isinstance(option, dict):
                continue
            role = option.get("semantic_role")
            if role == "candidate_change_surface" and not candidate_surface:
                candidate_surface = option.get("path")
            if role == "verifier_and_test_constraint" and not verifier_surface:
                verifier_surface = option.get("path")
            if role == "symptom_or_call_path_analogue" and not symptom_surface:
                symptom_surface = option.get("path")
        if not candidate_surface:
            blockers.append("missing_candidate_change_surface")
        if verifier_surface and row.get("selected_verifier_path_proposal") and verifier_surface != row.get("selected_verifier_path_proposal"):
            blockers.append("verifier_option_mismatch")
        item = {
            "work_item_id": f"stage11612::{rid}",
            "root_id": rid,
            "root_lineage_key": rid,
            "language_family": "web_js_ts_html",
            "git_repo_family": row.get("git_repo_family"),
            "repo_family": repo_family,
            "repo_path": row.get("repo_path"),
            "lane": lane,
            "candidate_change_surface": candidate_surface,
            "selected_verifier_path": row.get("selected_verifier_path_proposal"),
            "symptom_or_call_path_analogue": symptom_surface,
            "baseline_pass_command": command_key((pass_row or {}).get("command")),
            "baseline_pass_log_path": (pass_row or {}).get("log_path"),
            "baseline_transition": (pass_row or {}).get("verifier_transition"),
            "required_materialization": {
                "isolation": "copy repo or use reversible patch with backup+restore; do not mutate canonical repo without restore proof",
                "baseline": "focused verifier passes before mutation",
                "mutant": "candidate_change_surface mutation causes focused verifier to fail",
                "repair": "restoring original candidate_change_surface causes focused verifier to pass",
                "target_transition": "FAIL_TO_PASS",
                "logs_required": ["baseline_pass_log", "mutant_fail_log", "restored_pass_log"],
                "row_outputs_required": ["six_perspective_rows", "opaque_options", "deterministic_option_shuffle", "prompt_target_leak_audit", "anti_cheat_card"],
            },
            "admission_contract": {
                "trainable_only_after": [
                    "mutant_fail_observed",
                    "restored_pass_observed",
                    "gold_perspective_answers_completed",
                    "anti_cheat_passed",
                    "root_split_assigned",
                    "no_prompt_target_leak",
                ],
                "strict_eval_eligible_only_if": [
                    "root_family_not_in_train",
                    "not_generated_from_existing_web_heldout_root",
                    "reviewed_by_ai_maintainer_or_human",
                    "not trivially solved by file-name or option-order shortcut",
                ],
            },
            "blockers": blockers,
        }
        if blockers:
            quarantine.append(item)
        else:
            repo_counts[repo_family] += 1
            accepted.append(item)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "fail_to_pass_mutation_work_items_ready" if accepted else "no_fail_to_pass_mutation_work_items_ready",
        "work_items": len(accepted),
        "work_item_roots": len({item["root_id"] for item in accepted}),
        "quarantined_items": len(quarantine),
        "work_items_by_repo_family": dict(Counter(item["repo_family"] for item in accepted)),
        "quarantine_blocker_counts": dict(Counter(blocker for item in quarantine for blocker in item["blockers"])),
        "stage11611_supply_decision": supply.get("decision"),
        "stage11611_candidate_rows": supply.get("candidate_rows"),
        "claim_boundary": [
            "This stage does not admit rows to train/eval and does not run model training.",
            "It creates execution work items for controlled source-backed FAIL_TO_PASS materialization from existing PASS_TO_PASS Web roots.",
            "Rows produced from these work items must be labelled controlled bug-injection, not organic issue replay.",
        ],
        "next_required_actions": [
            "Run a mutation executor in isolated copies for admitted work items.",
            "Require baseline PASS, mutant FAIL, restored PASS logs before row admission.",
            "Build six-perspective rows per admitted root and rerun prompt-target leak plus option-shuffle audits.",
            "Only after admission, build a train/heldout split and compare 100M vs Gemma on heldout Web roots.",
        ],
        "source_artifacts": {
            "source_atlas": rel(SOURCE_ATLAS),
            "pass_results": rel(PASS_RESULTS),
            "supply_audit": rel(SUPPLY_AUDIT),
        },
        "outputs": {"summary": rel(SUMMARY), "work_items": rel(WORK_ITEMS), "quarantine": rel(QUARANTINE)},
    }
    write_jsonl(WORK_ITEMS, accepted)
    write_jsonl(QUARANTINE, quarantine)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({
        "decision": summary["decision"],
        "work_items": summary["work_items"],
        "work_items_by_repo_family": summary["work_items_by_repo_family"],
        "quarantine_blocker_counts": summary["quarantine_blocker_counts"],
        "next_required_actions": summary["next_required_actions"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
