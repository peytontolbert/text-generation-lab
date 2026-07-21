#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12231_controlled_fixture_patch_trace_projections"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
SRC = ROOT / "runs/summaries/stage12025_controlled_fail_to_pass_expansion_rows.json"
LABELS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def sid(prefix: str, *parts: Any) -> str:
    raw = "\n".join(json.dumps(p, sort_keys=True, default=str) for p in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def scrub(value: Any) -> str:
    text = str(value or "")
    text = text.replace(str(ROOT), "[workspace]")
    text = text.replace("/data/agentkernel-seq2seq-text-lab", "[workspace]")
    text = text.replace("/home/peyton", "[home]")
    text = text.replace("/dev/pytest-cache-files", "[pytest-cache]")
    return text

def compact(value: Any, limit: int = 600) -> str:
    return " ".join(scrub(value).split())[:limit]


def opt(values: list[tuple[str, str]], target: str) -> tuple[list[dict[str, Any]], str]:
    rows = []
    target_label = ""
    for i, (value, role) in enumerate(values):
        row = {"label": LABELS[i], "value": value, "semantic_role": role, "is_target": value == target}
        if value == target:
            target_label = LABELS[i]
        rows.append(row)
    if not target_label:
        raise ValueError(target)
    return rows, target_label


def command_text(result: dict[str, Any]) -> str:
    return " ".join(str(x) for x in (result.get("command") or []))


def phase(card: dict[str, Any], name: str) -> dict[str, Any]:
    r = card.get(name) or {}
    return {
        "phase": name,
        "command": command_text(r),
        "cwd": r.get("cwd"),
        "returncode": r.get("returncode"),
        "status": "PASS_CURRENT_STATE" if r.get("returncode") == 0 else "FAIL_CURRENT_STATE",
        "stdout_excerpt": compact(r.get("stdout_tail"), 800),
        "stderr_excerpt": compact(r.get("stderr_tail"), 800),
        "log_path": r.get("log_path"),
    }


def render(card: dict[str, Any], projection: str, options: list[dict[str, Any]]) -> str:
    fixture = card.get("fixture") or {}
    phases = [phase(card, "mutant"), phase(card, "restored"), phase(card, "baseline")]
    lines = [
        "TASK",
        "source_kind: controlled_curriculum_only",
        f"projection_family: {projection}",
        f"fixture_id: {fixture.get('id')}",
        f"language_family: {fixture.get('language_family')}",
        "instruction: choose the best option using only the controlled phase evidence below.",
        "",
        "PATCH_TRACE",
        f"source_file: {fixture.get('source_file')}",
        f"mutant_change: {compact(fixture.get('find'))} -> {compact(fixture.get('replace'))}",
        f"selected_verifier_path: {fixture.get('selected_verifier_path')}",
        "",
        "PHASE_EVIDENCE",
    ]
    for p in phases:
        lines.extend(
            [
                f"[{p['phase']}] status={p['status']} returncode={p['returncode']}",
                f"[{p['phase']}] command={compact(p['command'], 300)}",
                f"[{p['phase']}] stdout={p['stdout_excerpt']}",
                f"[{p['phase']}] stderr={p['stderr_excerpt']}",
            ]
        )
    lines.extend(["", "CANDIDATES"])
    for o in options:
        lines.append(f"{o['label']}: role={o['semantic_role']}; value={o['value']}")
    lines.extend(["", "QUESTION", "Return only the option label."])
    return "\n".join(lines)


def projection_values(projection: str) -> tuple[list[tuple[str, str]], str]:
    if projection == "patch_apply":
        return [
            ("PATCH_APPLIES_CLEANLY", "controlled_patch_apply_success"),
            ("PATCH_DOES_NOT_APPLY", "controlled_patch_apply_failure"),
            ("ABSTAIN_PATCH_APPLY_UNKNOWN", "insufficient_patch_apply_evidence"),
        ], "PATCH_APPLIES_CLEANLY"
    if projection == "verifier_transition":
        return [
            ("FAIL_TO_PASS", "controlled_behavior_repair"),
            ("PASS_TO_PASS", "safe_nonrepair"),
            ("TEST_ADDED_OR_VERIFIER_NOT_COMPARABLE", "not_comparable"),
            ("ENV_BLOCKED", "environment_blocked"),
        ], "FAIL_TO_PASS"
    if projection == "stop_continue":
        return [
            ("STOP_VERIFIED_DIRECT_FIX", "controlled_stop_after_verified_repair"),
            ("CONTINUE_WEAK_OR_PASS_TO_PASS", "continue_nonrepair"),
            ("ABSTAIN_NOT_COMPARABLE", "abstain_not_comparable"),
        ], "STOP_VERIFIED_DIRECT_FIX"
    if projection == "next_action":
        return [
            ("RUN_RESTORED_VERIFIER", "verify_patch_candidate"),
            ("CLAIM_REPAIR_WITHOUT_VERIFIER", "premature_claim"),
            ("ABSTAIN_ENV_BLOCKED", "abstain_environment"),
        ], "RUN_RESTORED_VERIFIER"
    if projection == "patch_judgment":
        return [
            ("CONTROLLED_DIRECT_FIX", "controlled_direct_behavior_repair"),
            ("PASS_TO_PASS_SAFE_REFACTOR", "safe_replay_nonrepair"),
            ("TEST_ADDED_NOT_COMPARABLE", "test_added_shortcut"),
            ("REJECT", "reject_patch_trace"),
        ], "CONTROLLED_DIRECT_FIX"
    raise ValueError(projection)


def build_row(card: dict[str, Any], projection: str) -> dict[str, Any]:
    fixture = card.get("fixture") or {}
    values, target = projection_values(projection)
    options, label = opt(values, target)
    prompt = render(card, projection, options)
    fixture_id = str(fixture.get("id"))
    return {
        "row_id": sid("stage12231_row", fixture_id, projection),
        "source_record_id": f"stage12025::{fixture_id}",
        "episode_id": f"stage12025::{fixture_id}",
        "root_id": str(card.get("mutant", {}).get("cwd") or ""),
        "repo_family": str(fixture.get("repo_family")),
        "language_family": str(fixture.get("language_family")),
        "split": "train_support",
        "source_kind": "controlled_fixture",
        "controlled_curriculum_only": True,
        "curriculum_scope": "controlled_fixture_projection_only",
        "source_stage": "stage12025_controlled_fail_to_pass_expansion_rows",
        "split_role": "stage12231_controlled_curriculum_only_not_external_rollup",
        "external_patch_trace_rollup_eligible": False,
        "quality_flags": ["synthetic_fixture", "toy_one_function_or_assertion", "not_source_heldout"],
        "training_gate_required": "separate_controlled_curriculum_gate",
        "projection_family": projection,
        "task_type": f"controlled_patch_trace_{projection}",
        "prompt_text": prompt,
        "input_text": prompt,
        "target": target,
        "decoder_text": label,
        "bounded_choice_target_label": label,
        "opaque_options": options,
        "standalone_projection_source": {"opaque_options": options},
        "state_before": {"phase": "mutant", "status": phase(card, "mutant")["status"]},
        "state_before_plus_patch": {"phase": "restored", "status": phase(card, "restored")["status"]},
        "state_after": {"phase": "baseline", "status": phase(card, "baseline")["status"], "verifier_transition": "FAIL_TO_PASS"},
        "ordered_events": [
            {"event_type": "STATE_BEFORE", "phase": "mutant"},
            {"event_type": "COMMAND_RESULT", **phase(card, "mutant")},
            {"event_type": "PATCH_APPLY", "phase": "restored", "status": "controlled_restored_matches_original"},
            {"event_type": "COMMAND_RESULT", **phase(card, "restored")},
            {"event_type": "COMMAND_RESULT", **phase(card, "baseline")},
            {"event_type": "VERIFIER_RESULT", "verifier_transition": "FAIL_TO_PASS"},
        ],
        "patch_trace": {
            "has_patch_trace": True,
            "counts_toward_patch_trace_floor": False,
            "counts_toward_fail_to_pass_floor": False,
            "controlled_curriculum_only": True,
            "source_file": fixture.get("source_file"),
            "find": fixture.get("find"),
            "replace": fixture.get("replace"),
            "semantic_patch_validation_strength": "controlled_fixture_direct_behavior_repair",
        },
        "verifier_result_by_phase": {
            "before": phase(card, "mutant"),
            "before_plus_patch": phase(card, "restored"),
            "after": phase(card, "baseline"),
        },
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "target_not_visible_before_options": True,
            "source_kind": "controlled_fixture",
        "controlled_curriculum_only": True,
        "curriculum_scope": "controlled_fixture_projection_only",
        "source_stage": "stage12025_controlled_fail_to_pass_expansion_rows",
        "split_role": "stage12231_controlled_curriculum_only_not_external_rollup",
        "external_patch_trace_rollup_eligible": False,
        "quality_flags": ["synthetic_fixture", "toy_one_function_or_assertion", "not_source_heldout"],
        "training_gate_required": "separate_controlled_curriculum_gate",
        },
        "loss_mask": {
            "bounded_choice": False,
            "decoder_ce": False,
            "reason": "controlled curriculum projection only; training blocked until curriculum gate",
        },
        "train_support_only": True,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "training_allowed": False,
    }


def main() -> int:
    src = json.loads(SRC.read_text())
    cards = [c for c in src.get("probe_cards", []) if c.get("admitted") and c.get("restored_matches_original")]
    rows = []
    for card in cards:
        for projection in ["patch_apply", "verifier_transition", "stop_continue", "next_action", "patch_judgment"]:
            rows.append(build_row(card, projection))
    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT / "controlled_fixture_patch_trace_projection_rows.jsonl", rows)
    summary = {
        "stage": STAGE,
        "decision": "controlled_fixture_projection_rows_ready_training_blocked" if rows else "blocked_no_controlled_fixture_rows",
        "source_stage": "stage12025_controlled_fail_to_pass_expansion_rows",
        "fixture_count": len(cards),
        "row_count": len(rows),
        "projection_counts": dict(Counter(r["projection_family"] for r in rows)),
        "language_counts": dict(Counter(r["language_family"] for r in rows)),
        "repo_family_counts": dict(Counter(r["repo_family"] for r in rows)),
        "target_counts": dict(Counter(r["target"] for r in rows)),
        "training_allowed": False,
        "claim_boundary": "Controlled curriculum only. These rows are not source-heldout, not strict eval, and do not count toward external patch-trace floors.",
        "artifact_paths": {"rows": str(OUT / "controlled_fixture_patch_trace_projection_rows.jsonl")},
    }
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if rows else 2


if __name__ == "__main__":
    raise SystemExit(main())
