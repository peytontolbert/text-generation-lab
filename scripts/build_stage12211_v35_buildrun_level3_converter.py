#!/usr/bin/env python3
"""Convert v35 PASS_CURRENT_BUILD_AND_RUN rows into Level-3 train-support records.

These rows are rendered support rows, not raw replay logs. We admit only rows
with explicit PASS_CURRENT_BUILD_AND_RUN, non-singleton shuffled options, command
text and output tail in the prompt, and no duplicate root/transition already in
Stage12206. They remain train-support-only and strict-eval-ineligible.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12211_v35_buildrun_level3_converter"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
SRC = ROOT / "runs/local/artifacts/stage12056_transition_support_rollup_v35/transition_support_rows_v35.jsonl"
EXISTING = ROOT / "runs/local/artifacts/stage12206_level3_passfail_training_rollup/level3_passfail_train_support_full.jsonl"


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "\n".join(json.dumps(p, sort_keys=True, default=str) for p in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


def iter_jsonl(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if line:
                yield line_no, json.loads(line)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def existing_keys() -> set[tuple[str, str, str]]:
    keys: set[tuple[str, str, str]] = set()
    for _, row in iter_jsonl(EXISTING) or []:
        keys.add((str(row.get("root_id") or ""), str(row.get("selected_test_anchor") or ""), str(row.get("verifier_transition") or "")))
    return keys


def extract_after(label: str, text: str) -> str:
    m = re.search(re.escape(label) + r"\s*(.*?)(?:\n[A-Z][A-Za-z ]+(?: rc| tail| pair| root| verifier| command):|\nOptions:|\Z)", text, re.S)
    if not m:
        return ""
    return m.group(1).strip()


def option_candidates(row: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    target = row.get("bounded_choice_target_label")
    for opt in row.get("opaque_options") or []:
        label = str(opt.get("label"))
        out.append({
            "action_id": label,
            "label": label,
            "role": str(opt.get("canonical_value") or opt.get("value") or opt.get("role") or "unknown"),
            "action_type": "CLASSIFY_VERIFIER_TRANSITION",
            "description": str(opt.get("text") or opt.get("value") or ""),
            "artifact_type": opt.get("artifact_type"),
            "is_chosen": label == target,
            "negative_kind": None if label == target else "verifier_transition_distractor",
        })
    return out


def convert(line_no: int, row: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    if row.get("observed_verifier_transition") != "PASS_CURRENT_BUILD_AND_RUN":
        return None, "not_pass_current_build_and_run"
    if row.get("train_support_only") is not True or row.get("strict_eval_eligible") is not False:
        return None, "not_train_support_only"
    ac = row.get("anti_cheat") or {}
    if not ac.get("deterministic_option_shuffle") or ac.get("singleton_options"):
        return None, "anti_cheat_failed"
    input_text = str(row.get("input_text") or row.get("prompt_text") or "")
    if "Observed command:" not in input_text or "Output tail:" not in input_text or "Return code: 0" not in input_text:
        return None, "missing_command_output_contract"
    candidates = option_candidates(row)
    if len(candidates) < 2 or not any(c.get("is_chosen") for c in candidates):
        return None, "bad_candidate_set"
    chosen = next(c for c in candidates if c.get("is_chosen"))
    root_id = str(row.get("root_id") or row.get("source_root_id") or row.get("row_id"))
    selected = str(row.get("selected_test_anchor") or row.get("verifier_anchor") or "")
    command = extract_after("Observed command:", input_text)
    output_tail = extract_after("Output tail:", input_text)
    episode_id = stable_id("stage12211_episode", row.get("row_id"), root_id, selected, command)
    command_result_id = stable_id("stage12211_command", command, output_tail, root_id)
    record = {
        "episode_id": episode_id,
        "root_id": root_id,
        "repo_id": row.get("repo_id"),
        "repo_family": row.get("repo_family"),
        "root_lineage_key": row.get("root_lineage_key") or row.get("source_root_id") or root_id,
        "language": row.get("language_family"),
        "task_type": "transition_verifier_transition",
        "selected_test_anchor": row.get("selected_test_anchor"),
        "verifier_anchor": row.get("verifier_anchor"),
        "source_bundle_id": row.get("source_bundle_id"),
        "source_row_id": row.get("row_id"),
        "source_stage": STAGE + "::stage12056_transition_support_rollup_v35",
        "candidate_action_set": {
            "candidate_set_id": stable_id("stage12211_candidates", row.get("row_id"), row.get("opaque_options")),
            "chosen_action_id": chosen["action_id"],
            "candidate_actions": candidates,
        },
        "observed_action": {
            "action_id": chosen["action_id"],
            "action_type": "CLASSIFY_VERIFIER_TRANSITION",
            "command_result_id": command_result_id,
            "semantic_value": "PASS_CURRENT_BUILD_AND_RUN",
        },
        "command_result": {
            "command_result_id": command_result_id,
            "command": command,
            "cwd": row.get("source_root_id") or row.get("root_id"),
            "returncode": 0,
            "stdout_tail": output_tail,
            "stderr_tail": "",
            "source_kind": "rendered_v35_command_output_tail",
        },
        "verifier_status": "PASS_CURRENT_BUILD_AND_RUN",
        "verifier_transition": "PASS_CURRENT_BUILD_AND_RUN",
        "state_update": {
            "state_update_id": stable_id("stage12211_state_update", episode_id),
            "state_update_type": "observed_build_and_run_pass",
            "new_facts": ["build/typecheck and runnable verifier evidence both passed"],
            "invalidated_claims": [],
            "remaining_blockers": [],
        },
        "stop_decision": {
            "stop_decision_id": stable_id("stage12211_stop", episode_id),
            "continue_or_stop": "CONTINUE",
            "reason": "build and focused run are strong verifier evidence but this row is still a transition-observation training record, not full task acceptance",
        },
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "singleton_options": False,
            "target_label_not_visible_before_options": True,
            "target_value_not_visible_before_options": True,
            "source_is_rendered_prior_support_row": True,
            "target_not_promotable_eval": True,
        },
        "train_support_only": True,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "projection_permissions": {
            "may_project_verifier_transition": True,
            "may_project_candidate_selection": False,
            "may_project_patch_generation": False,
            "claim_boundary": "Rendered v35 build+run verifier evidence converted to Level-3 train support only.",
        },
    }
    return record, None


def main() -> int:
    seen = existing_keys()
    rows: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    dup_skipped = 0
    for line_no, row in iter_jsonl(SRC) or []:
        rec, reason = convert(line_no, row)
        if rec is None:
            if reason != "not_pass_current_build_and_run":
                blocked.append({"line_no": line_no, "row_id": row.get("row_id"), "blocker": reason})
            continue
        key = (str(rec.get("root_id") or ""), str(rec.get("selected_test_anchor") or ""), str(rec.get("verifier_transition") or ""))
        if key in seen:
            dup_skipped += 1
            blocked.append({"line_no": line_no, "row_id": row.get("row_id"), "blocker": "already_represented_in_stage12206"})
            continue
        seen.add(key)
        rows.append(rec)
    rows.sort(key=lambda r: (str(r.get("language")), str(r.get("repo_family")), str(r.get("episode_id"))))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT_DIR / "v35_buildrun_level3_records.jsonl", rows)
    write_jsonl(OUT_DIR / "blocked_v35_buildrun_rows.jsonl", blocked)
    summary = {
        "stage": STAGE,
        "decision": "v35_buildrun_records_materialized" if rows else "blocked_no_new_v35_buildrun_records",
        "level3_episode_count": len(rows),
        "duplicate_skipped_count": dup_skipped,
        "blocked_count": len(blocked),
        "language_counts": dict(Counter(str(r.get("language")) for r in rows)),
        "repo_family_counts_top20": Counter(str(r.get("repo_family")) for r in rows).most_common(20),
        "verifier_transition_counts": dict(Counter(str(r.get("verifier_transition")) for r in rows)),
        "train_support_only": True,
        "strict_eval_eligible": False,
        "claim_boundary": "Rendered v35 PASS_CURRENT_BUILD_AND_RUN command-output rows converted to Level-3 train support only; no eval claim.",
        "artifact_paths": {
            "records": str(OUT_DIR / "v35_buildrun_level3_records.jsonl"),
            "blocked": str(OUT_DIR / "blocked_v35_buildrun_rows.jsonl"),
        },
    }
    write_json(OUT_DIR / "summary.json", summary)
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if rows else 2

if __name__ == "__main__":
    raise SystemExit(main())
