#!/usr/bin/env python3
"""Build Stage12153 counterfactual selected-test transition rows."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12153_counterfactual_selected_test_transition_rows"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY_MIRROR = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12149_ROWS = ROOT / "runs/local/artifacts/stage12149_corrected_selected_test_row_materialization_package/corrected_selected_test_rows.jsonl"
STAGE12149_AUDIT = ROOT / "runs/local/artifacts/stage12149_corrected_selected_test_row_materialization_package/row_materialization_audit.json"
STAGE12152_SUMMARY = ROOT / "runs/summaries/stage12152_selected_test_training_utility_audit.json"
STAGE12148_CONTRACT = ROOT / "runs/local/artifacts/stage12148_task_specific_selected_test_materialization_contract/materialization_contract.json"
STAGE12151_HYGIENE = ROOT / "runs/summaries/stage12151_selected_test_supply_hygiene_audit.json"

TASKS = [
    "transition_candidate_selection",
    "transition_next_action",
    "transition_continue_or_stop",
    "transition_verifier_transition",
    "transition_evidence_citation",
]

VARIANTS = [
    "verifier_observed_success",
    "pre_verifier_ready",
    "source_surface_only",
    "verifier_removed",
]

TARGET_KINDS = {
    "transition_candidate_selection": "candidate_artifact_or_evidence_candidate",
    "transition_next_action": "maintainer_action",
    "transition_continue_or_stop": "episode_control_decision",
    "transition_verifier_transition": "verifier_status",
    "transition_evidence_citation": "evidence_role_or_evidence_item",
}

ARTIFACT_TYPES = {
    "transition_candidate_selection": "candidate_artifact",
    "transition_next_action": "action",
    "transition_continue_or_stop": "control",
    "transition_verifier_transition": "verifier_status",
    "transition_evidence_citation": "evidence_role",
}

TASK_OPTIONS = {
    "transition_candidate_selection": [
        "selected_test_backed_verifier_candidate",
        "verifier_and_test_constraint",
        "candidate_change_surface",
        "source_surface",
    ],
    "transition_next_action": ["FINISH", "RUN_VERIFIER", "SELECT_TEST", "RETRIEVE_EVIDENCE"],
    "transition_continue_or_stop": ["STOP_DONE", "CONTINUE", "NOT_DONE_MISSING_TESTS", "ABSTAIN_INSUFFICIENT_EVIDENCE"],
    "transition_verifier_transition": ["PASS_CURRENT_STATE", "PASS_CURRENT_BUILD_AND_RUN", "INSUFFICIENT_EVIDENCE", "VERIFIER_REMOVED"],
    "transition_evidence_citation": ["verifier_and_test_constraint", "candidate_change_surface", "source_surface", "insufficient_evidence"],
}

UTILITY_MIN_ROWS = 40
UTILITY_MIN_ROOTS = 8
UTILITY_MIN_LANGUAGES = 3
UTILITY_MIN_TARGETS_BY_TASK = {
    "transition_next_action": 3,
    "transition_continue_or_stop": 2,
    "transition_verifier_transition": 3,
    "transition_evidence_citation": 2,
    "transition_candidate_selection": 2,
}
DISALLOWED_SINGLETON_TARGETS = {
    "transition_next_action": {"FINISH"},
    "transition_continue_or_stop": {"STOP_DONE"},
    "transition_evidence_citation": {"verifier_and_test_constraint"},
    "transition_candidate_selection": {"selected_test_backed_verifier_candidate"},
}

DEPENDENCY_MARKERS = (
    "node_modules/",
    "/node_modules/",
    ".git/",
    "/.git/",
    "target/debug/",
    "target/release/",
    "/target/",
    ".venv/",
    "/.venv/",
    "__pycache__/",
)


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sid(*parts: str, n: int = 12) -> str:
    return hashlib.sha256("::".join(parts).encode()).hexdigest()[:n]


def entropy(values: list[str]) -> float:
    if not values:
        return 0.0
    counts = Counter(values)
    total = sum(counts.values())
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


def target_for(root: dict[str, Any], variant: str, task: str) -> str:
    pass_status = "PASS_CURRENT_STATE" if root["language_family"] == "python" else "PASS_CURRENT_BUILD_AND_RUN"
    table = {
        "verifier_observed_success": {
            "transition_candidate_selection": "selected_test_backed_verifier_candidate",
            "transition_next_action": "FINISH",
            "transition_continue_or_stop": "STOP_DONE",
            "transition_verifier_transition": pass_status,
            "transition_evidence_citation": "verifier_and_test_constraint",
        },
        "pre_verifier_ready": {
            "transition_candidate_selection": "verifier_and_test_constraint",
            "transition_next_action": "RUN_VERIFIER",
            "transition_continue_or_stop": "CONTINUE",
            "transition_verifier_transition": "INSUFFICIENT_EVIDENCE",
            "transition_evidence_citation": "verifier_and_test_constraint",
        },
        "source_surface_only": {
            "transition_candidate_selection": "candidate_change_surface",
            "transition_next_action": "SELECT_TEST",
            "transition_continue_or_stop": "CONTINUE",
            "transition_verifier_transition": "INSUFFICIENT_EVIDENCE",
            "transition_evidence_citation": "source_surface",
        },
        "verifier_removed": {
            "transition_candidate_selection": "source_surface",
            "transition_next_action": "RETRIEVE_EVIDENCE",
            "transition_continue_or_stop": "CONTINUE",
            "transition_verifier_transition": "VERIFIER_REMOVED",
            "transition_evidence_citation": "insufficient_evidence",
        },
    }
    return table[variant][task]


def evidence_for_variant(source: dict[str, Any], variant: str) -> tuple[list[dict[str, str]], list[str], str, int]:
    hashes = list(source["source_test_hashes"])
    if variant == "source_surface_only":
        hashes = [h for h in hashes if h.get("kind") == "source"]
        return hashes, [f"source_hash::{h['path']}::{h['sha256']}" for h in hashes], "source-only state; selected-test and verifier result evidence are absent", 0
    source_ids = [f"source_hash::{h['path']}::{h['sha256']}" for h in hashes if h.get("kind") == "source"]
    test_ids = [f"test_hash::{h['path']}::{h['sha256']}" for h in hashes if h.get("kind") == "test"]
    if variant == "pre_verifier_ready":
        return hashes, source_ids + test_ids, "source and selected-test hashes are present; verifier result is not present", source["selected_test_count"]
    if variant == "verifier_removed":
        return hashes, source_ids + test_ids, "source and selected-test hashes remain; verifier result was deliberately removed", source["selected_test_count"]
    return hashes, source_ids + test_ids + [f"verifier_success::{source['root_id']}"], "successful selected-test verifier evidence is present", source["selected_test_count"]


def make_options(root_id: str, variant: str, task: str, target: str, evidence_ids: list[str]) -> list[dict[str, Any]]:
    options = sorted(TASK_OPTIONS[task], key=lambda value: sid(root_id, variant, task, value))
    labels = ["A", "B", "C", "D"]
    out = []
    for idx, (value, label) in enumerate(zip(options, labels)):
        out.append(
            {
                "deterministic_position": idx,
                "label": label,
                "semantic_id": f"{variant}::{task}::{value}",
                "value": value,
                "role": value,
                "artifact_type": ARTIFACT_TYPES[task],
                "target_kind": TARGET_KINDS[task],
                "semantic_candidate": {
                    "role": value,
                    "target_kind": TARGET_KINDS[task],
                    "artifact_type": ARTIFACT_TYPES[task],
                    "value": value,
                    "evidence_ids": evidence_ids if value == target else [],
                },
            }
        )
    return out


def render_prompt(root: dict[str, Any], variant: str, task: str, hashes: list[dict[str, str]], evidence_ids: list[str], options: list[dict[str, Any]], state_text: str, selected_count: int) -> str:
    source_hashes = [f"{h['path']}@{h['sha256'][:12]}" for h in hashes if h.get("kind") == "source"][:4]
    test_hashes = [f"{h['path']}@{h['sha256'][:12]}" for h in hashes if h.get("kind") == "test"][:4]
    if selected_count == 0:
        selected_line = "Selected-test evidence: absent in this counterfactual state."
    else:
        selected_line = f"Selected-test evidence: {selected_count} selected test id(s); identifiers withheld from target surface."
    lines = [
        f"Task family: {task}",
        f"Counterfactual state: {sid(root['root_id'], variant, 'display')}",
        f"Repository: {root['repo_family']}",
        f"Language: {root['language_family']}",
        f"Commit: {root['commit_sha']}",
        selected_line,
        f"State evidence summary: {state_text}.",
        f"Source hash summary: {', '.join(source_hashes) if source_hashes else 'none'}",
        f"Test hash summary: {', '.join(test_hashes) if test_hashes else 'none'}",
        f"Evidence ledger refs: {json.dumps([sid(e) for e in evidence_ids[:6]], sort_keys=True)}",
        "Choose the single option best supported by this counterfactual state. Use only the opaque labels below.",
        "Options:",
    ]
    lines.extend(f"- {opt['label']}: Option {opt['label']}" for opt in options)
    lines.append("Answer:")
    return "\n".join(lines)


def source_roots(rows: list[dict[str, Any]], hygiene: dict[str, Any]) -> list[dict[str, Any]]:
    passed = {rec["root_id"] for rec in hygiene["records"] if rec.get("passed") is True}
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row["root_id"] not in passed or row["root_id"] in grouped:
            continue
        src = row["standalone_projection_source"]
        grouped[row["root_id"]] = {
            "root_id": row["root_id"],
            "repo_family": row["repo_family"],
            "language_family": row["language_family"],
            "commit_sha": row["commit_sha"],
            "selected_test_count": src["selected_test_count"],
            "source_test_hashes": src["source_test_hashes"],
            "source_stage": src["source_stage"],
        }
    return [grouped[root_id] for root_id in sorted(grouped)]


def build_row(root: dict[str, Any], variant: str, task: str) -> dict[str, Any]:
    target = target_for(root, variant, task)
    hashes, evidence_ids, state_text, selected_count = evidence_for_variant(root, variant)
    options = make_options(root["root_id"], variant, task, target, evidence_ids)
    target_option = next(opt for opt in options if opt["value"] == target)
    prompt = render_prompt(root, variant, task, hashes, evidence_ids, options, state_text, selected_count)
    projection = {
        "stage": STAGE,
        "source_stage": root["source_stage"],
        "source_package": "stage12149_corrected_selected_test_row_materialization_package",
        "repo_family": root["repo_family"],
        "root_id": root["root_id"],
        "commit_sha": root["commit_sha"],
        "state_variant": variant,
        "counterfactual_train_support_only": True,
        "selected_test_count": selected_count,
        "source_test_hashes": hashes,
        "evidence_ids": evidence_ids,
        "gold_value": target,
        "gold_role": target,
        "gold_target_kind": TARGET_KINDS[task],
        "opaque_options": options,
        "counterfactual_claim_boundary": "Rows describe state variants only; absent verifier/test evidence is not represented as executed.",
    }
    return {
        "row_id": f"stage12153::{root['root_id']}::{variant}::{task}::{sid(root['root_id'], variant, task, target)}",
        "stage": STAGE,
        "surface": "stage12153_counterfactual_selected_test_bounded_choice_train_support",
        "split": "train",
        "package_split": "train",
        "split_role": "stage12153_counterfactual_train_support_only_not_strict_eval",
        "task_type": task,
        "state_variant": variant,
        "counterfactual_train_support_only": True,
        "language_family": root["language_family"],
        "repo_family": root["repo_family"],
        "repo_id": root["repo_family"].replace("/", "__"),
        "root_id": root["root_id"],
        "source_root_id": root["root_id"],
        "commit_sha": root["commit_sha"],
        "selected_test_anchor": variant in {"verifier_observed_success", "pre_verifier_ready", "verifier_removed"},
        "verifier_anchor": variant == "verifier_observed_success",
        "train_support_only": True,
        "strict_eval_eligible": False,
        "promotion_eligible": False,
        "training_allowed": False,
        "prompt_text": prompt,
        "input_text": prompt,
        "target_label": target_option["label"],
        "bounded_choice_target_label": target_option["label"],
        "target_text": target_option["label"],
        "decoder_text": target_option["label"],
        "target_semantic_value": target,
        "target": {
            "bounded_choice_target_label": target_option["label"],
            "decoder_text": target_option["label"],
            "semantic_value": target,
            "semantic_role": target,
            "target_kind": TARGET_KINDS[task],
        },
        "opaque_options": options,
        "standalone_projection_source": projection,
        "loss_mask": {
            "bounded_choice_aux": True,
            "decoder_ce": True,
            "structured_aux": True,
            "transition_projection": True,
        },
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "single_token_labels": True,
            "nested_top_level_options_mirror": True,
            "target_label_not_visible_before_options": True,
            "target_value_not_visible_before_options": True,
            "dependency_paths_excluded": True,
            "stage12153_train_support_only": True,
            "strict_eval_not_cleared": True,
        },
    }


def target_value(row: dict[str, Any]) -> str:
    target = row.get("target")
    if isinstance(target, dict):
        return str(target.get("semantic_value") or "")
    return str(row.get("target_semantic_value") or "")


def safety_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    blockers: dict[str, list[str]] = {}
    for row in rows:
        row_blockers = []
        row_id = row["row_id"]
        options = row.get("opaque_options") or []
        nested = (row.get("standalone_projection_source") or {}).get("opaque_options")
        labels = [str(opt.get("label", "")) for opt in options]
        if labels != ["A", "B", "C", "D"]:
            row_blockers.append("labels_not_A_B_C_D")
        if options != nested:
            row_blockers.append("nested_top_level_options_mismatch")
        pre = str(row.get("prompt_text", "")).split("Options:", 1)[0]
        label_re = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(row['target_label'])}(?![A-Za-z0-9_])")
        if label_re.search(pre) or target_value(row) in pre:
            row_blockers.append("target_visible_before_options")
        blob = json.dumps({"prompt": row.get("prompt_text"), "projection": row.get("standalone_projection_source")}, sort_keys=True)
        if any(marker in blob for marker in DEPENDENCY_MARKERS):
            row_blockers.append("dependency_path_visible")
        if row.get("strict_eval_eligible") is not False or row.get("training_allowed") is not False or row.get("promotion_eligible") is not False:
            row_blockers.append("train_support_flags_invalid")
        if not row.get("counterfactual_train_support_only"):
            row_blockers.append("missing_counterfactual_train_support_only")
        variant = row["state_variant"]
        text = json.dumps(row, sort_keys=True)
        if variant in {"pre_verifier_ready", "source_surface_only", "verifier_removed"} and "successful selected-test verifier evidence is present" in text:
            row_blockers.append("removed_or_pre_verifier_claims_success")
        if row_blockers:
            blockers[row_id] = row_blockers
    return {
        "passed": not blockers,
        "blocker_row_count": len(blockers),
        "blockers_by_row": blockers,
    }


def utility_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_task: dict[str, list[str]] = defaultdict(list)
    by_root: dict[str, list[str]] = defaultdict(list)
    by_variant_task: dict[str, Counter[str]] = defaultdict(Counter)
    languages = Counter()
    blockers: list[str] = []
    for row in rows:
        value = target_value(row)
        by_task[row["task_type"]].append(value)
        by_root[row["root_id"]].append(value)
        by_variant_task[f"{row['state_variant']}::{row['task_type']}"][value] += 1
        languages[row["language_family"]] += 1
    if len(rows) < UTILITY_MIN_ROWS:
        blockers.append(f"row_count_below_training_floor:{len(rows)}<{UTILITY_MIN_ROWS}")
    if len(by_root) < UTILITY_MIN_ROOTS:
        blockers.append(f"root_count_below_training_floor:{len(by_root)}<{UTILITY_MIN_ROOTS}")
    if len(languages) < UTILITY_MIN_LANGUAGES:
        blockers.append(f"language_count_below_training_floor:{len(languages)}<{UTILITY_MIN_LANGUAGES}")
    task_report = {}
    for task, values in sorted(by_task.items()):
        counts = Counter(values)
        task_report[task] = {
            "row_count": len(values),
            "target_counts": dict(sorted(counts.items())),
            "unique_targets": len(counts),
            "entropy_bits": entropy(values),
        }
        required = UTILITY_MIN_TARGETS_BY_TASK.get(task)
        if required and len(counts) < required:
            blockers.append(f"{task}:target_diversity_below_floor:{len(counts)}<{required}")
        if len(counts) == 1 and task in DISALLOWED_SINGLETON_TARGETS and next(iter(counts)) in DISALLOWED_SINGLETON_TARGETS[task]:
            blockers.append(f"{task}:one_sided_target_shortcut:{next(iter(counts))}")
    return {
        "stage12152_style_passed": not blockers,
        "blockers": blockers,
        "row_count": len(rows),
        "root_count": len(by_root),
        "language_counts": dict(sorted(languages.items())),
        "task_report": task_report,
        "row_counts_by_state_variant_task_target": {key: dict(sorted(counter.items())) for key, counter in sorted(by_variant_task.items())},
    }


def main() -> None:
    stage12149_rows = read_jsonl(STAGE12149_ROWS)
    stage12149_audit = read_json(STAGE12149_AUDIT)
    stage12152 = read_json(STAGE12152_SUMMARY)
    contract = read_json(STAGE12148_CONTRACT)
    hygiene = read_json(STAGE12151_HYGIENE)
    roots = source_roots(stage12149_rows, hygiene)
    rows = [build_row(root, variant, task) for root in roots for variant in VARIANTS for task in TASKS]
    safety = safety_audit(rows)
    utility = utility_audit(rows)
    audit = {
        "stage": STAGE,
        "created_at_utc": now(),
        "input_stage12149_rows": str(STAGE12149_ROWS.relative_to(ROOT)),
        "input_stage12149_audit": str(STAGE12149_AUDIT.relative_to(ROOT)),
        "input_stage12152_summary": str(STAGE12152_SUMMARY.relative_to(ROOT)),
        "input_stage12148_contract": str(STAGE12148_CONTRACT.relative_to(ROOT)),
        "input_stage12151_hygiene": str(STAGE12151_HYGIENE.relative_to(ROOT)),
        "source_audit_passed": not stage12149_audit.get("blockers"),
        "source_stage12152_blockers": stage12152.get("blockers", []),
        "contract_task_families": sorted((contract.get("row_families") or {}).keys()),
        "safety_audit": safety,
        "stage12152_style_utility_audit": utility,
        "validator_execution_note": "Existing Stage12150/Stage12152 scripts are hardcoded to Stage12149 paths; Stage12153 emits equivalent safety and utility audit results for this package.",
        "training_allowed": False,
        "strict_eval_eligible": False,
        "promotion_eligible": False,
    }
    summary = {
        "stage": STAGE,
        "created_at_utc": audit["created_at_utc"],
        "rows": len(rows),
        "roots": sorted({row["repo_family"] for row in rows}),
        "state_variants": VARIANTS,
        "strict_eval_eligible": False,
        "training_allowed": False,
        "promotion_eligible": False,
        "train_support_only": True,
        "counterfactual_train_support_only": True,
        "safety_passed": safety["passed"],
        "stage12152_style_passed": utility["stage12152_style_passed"],
        "stage12152_style_blockers": utility["blockers"],
        "future_training_request_blocked": bool(utility["blockers"]) or not safety["passed"],
        "outputs": {
            "rows": str((OUT / "counterfactual_selected_test_rows.jsonl").relative_to(ROOT)),
            "audit": str((OUT / "counterfactual_training_utility_audit.json").relative_to(ROOT)),
            "summary": str((OUT / "summary.json").relative_to(ROOT)),
            "summary_mirror": str(SUMMARY_MIRROR.relative_to(ROOT)),
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT / "counterfactual_selected_test_rows.jsonl", rows)
    write_json(OUT / "counterfactual_training_utility_audit.json", audit)
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY_MIRROR, summary)


if __name__ == "__main__":
    main()
