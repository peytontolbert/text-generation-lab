#!/usr/bin/env python3
"""Build a high-quality Level-3 pass/fail training rollup.

Default policy excludes ENV_BLOCKED/INSUFFICIENT rows from the main training
artifact and keeps them in a separate diagnostic file. This is not a training
stage and makes no eval claim.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12206_level3_passfail_training_rollup"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
PASSFAIL = {"PASS_CURRENT_STATE", "PASS_TO_PASS", "PASS_CURRENT_BUILD", "PASS_CURRENT_BUILD_AND_RUN", "FAIL_CURRENT_STATE", "FAIL_TO_FAIL", "FAIL_TO_PASS"}

SOURCES = [
    ("stage12204_hydratable_verifier_replay_batch", ROOT / "runs/local/artifacts/stage12204_hydratable_verifier_replay_batch/passfail_level3_episode_records.jsonl"),
    ("stage12205_authoritative_verifier_log_level3_joiner", ROOT / "runs/local/artifacts/stage12205_authoritative_verifier_log_level3_joiner/authoritative_level3_episode_records.jsonl"),
    ("stage12207_no_install_selected_test_log_level3_joiner", ROOT / "runs/local/artifacts/stage12207_no_install_selected_test_log_level3_joiner/no_install_selected_test_level3_records.jsonl"),
    ("stage12210_controlled_triple_level3_joiner", ROOT / "runs/local/artifacts/stage12210_controlled_triple_level3_joiner/controlled_triple_level3_records.jsonl"),
    ("stage12211_v35_buildrun_level3_converter", ROOT / "runs/local/artifacts/stage12211_v35_buildrun_level3_converter/v35_buildrun_level3_records.jsonl"),
    ("stage12212_v35_buildonly_level3_converter", ROOT / "runs/local/artifacts/stage12212_v35_buildonly_level3_converter/v35_buildonly_level3_records.jsonl"),
    ("stage12213_strict_fail_current_state_level3_converter", ROOT / "runs/local/artifacts/stage12213_strict_fail_current_state_level3_converter/strict_fail_current_state_level3_records.jsonl"),
    ("stage12215_hydratable_selected_verifier_reexecution", ROOT / "runs/local/artifacts/stage12215_hydratable_selected_verifier_reexecution/level3_reexecution_records.jsonl"),
    ("stage12203_controlled_selected_verifier_replay", ROOT / "runs/local/artifacts/stage12203_controlled_selected_verifier_replay/level3_episode_records.jsonl"),
]


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



def load_sidecars(source_stage: str) -> dict[str, dict[str, dict[str, Any]]]:
    stage_dir = ROOT / "runs/local/artifacts" / source_stage
    sidecars: dict[str, dict[str, dict[str, Any]]] = {"command_result": {}, "state_update": {}, "stop_decision": {}}
    for name, key in [
        ("command_results.jsonl", "command_result_id"),
        ("state_updates.jsonl", "state_update_id"),
        ("stop_decisions.jsonl", "stop_decision_id"),
    ]:
        path = stage_dir / name
        if not path.exists():
            continue
        target = name.split(".", 1)[0]
        field = "command_result" if target == "command_results" else ("state_update" if target == "state_updates" else "stop_decision")
        for _, row in iter_jsonl(path) or []:
            row_id = row.get(key)
            if row_id:
                sidecars[field][str(row_id)] = row
    return sidecars


def enrich_sidecars(row: dict[str, Any], source_stage: str, cache: dict[str, dict[str, dict[str, dict[str, Any]]]]) -> dict[str, Any]:
    if source_stage not in cache:
        cache[source_stage] = load_sidecars(source_stage)
    sidecars = cache[source_stage]
    observed = row.get("observed_action") or {}
    command_id = observed.get("command_result_id")
    if command_id and "command_result" not in row and str(command_id) in sidecars.get("command_result", {}):
        row["command_result"] = sidecars["command_result"][str(command_id)]
    state_id = row.get("state_update_id")
    if state_id and "state_update" not in row and str(state_id) in sidecars.get("state_update", {}):
        row["state_update"] = sidecars["state_update"][str(state_id)]
    stop_id = row.get("stop_decision_id")
    if stop_id and "stop_decision" not in row and str(stop_id) in sidecars.get("stop_decision", {}):
        row["stop_decision"] = sidecars["stop_decision"][str(stop_id)]
    return row


def normalize_record(row: dict[str, Any], source_stage: str, source_ref: str) -> dict[str, Any]:
    row = dict(row)
    row["rollup_source_stage"] = source_stage
    row["rollup_source_ref"] = source_ref
    row["rollup_record_id"] = stable_id("stage12206_record", source_stage, row.get("episode_id"), row.get("verifier_transition"), row.get("observed_action"))
    row["strict_eval_eligible"] = False
    row["train_support_only"] = True
    row["stage12206_training_visibility"] = {
        "hide_fields_from_model_prompt": [
            "candidate_action_set.candidate_actions[].is_chosen",
            "candidate_action_set.candidate_actions[].negative_kind",
            "candidate_action_set.chosen_action_id",
            "observed_action",
            "command_result",
            "observation",
            "verifier_status",
            "verifier_transition",
            "state_update",
            "stop_decision",
            "anti_cheat",
            "projection_permissions",
            "repo_commit_after",
            "source_extra",
        ],
        "allowed_prompt_fields": [
            "root_id",
            "repo_family",
            "language",
            "candidate_action_set with opaque labels and no is_chosen/negative_kind",
            "pre-action state/evidence rendered by downstream compiler",
        ],
    }
    return row


def main() -> int:
    passfail_rows: list[dict[str, Any]] = []
    diagnostic_rows: list[dict[str, Any]] = []
    source_seen = Counter()
    duplicate_keys = set()
    duplicate_count = 0
    sidecar_cache: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
    incomplete_required_count = 0
    for source_stage, path in SOURCES:
        for line_no, row in iter_jsonl(path) or []:
            row = enrich_sidecars(dict(row), source_stage, sidecar_cache)
            source_seen[source_stage] += 1
            transition = str(row.get("verifier_transition") or row.get("verifier_status") or "")
            key = (row.get("episode_id"), transition, json.dumps(row.get("observed_action"), sort_keys=True, default=str))
            if key in duplicate_keys:
                duplicate_count += 1
                continue
            duplicate_keys.add(key)
            normalized = normalize_record(row, source_stage, f"{path}:{line_no}")
            required_objects = all(k in normalized for k in ("command_result", "state_update", "stop_decision"))
            if transition in PASSFAIL and row.get("train_support_usable_for_passfail", True) is not False and required_objects:
                passfail_rows.append(normalized)
            else:
                if transition in PASSFAIL and not required_objects:
                    incomplete_required_count += 1
                    normalized["stage12206_blocker"] = "missing_embedded_command_state_or_stop_object"
                diagnostic_rows.append(normalized)

    # Soft cap one dominant repo family in the primary rollup view while also
    # keeping the full passfail artifact. This prevents OpenHands from silently
    # defining the whole next training packet.
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in passfail_rows:
        by_family[str(row.get("repo_family") or "unknown")].append(row)
    capped_rows: list[dict[str, Any]] = []
    cap = 16
    for family, rows in sorted(by_family.items()):
        capped_rows.extend(rows[:cap])
    capped_rows.sort(key=lambda r: (str(r.get("language")), str(r.get("repo_family")), str(r.get("episode_id"))))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT_DIR / "level3_passfail_train_support_full.jsonl", passfail_rows)
    write_jsonl(OUT_DIR / "level3_passfail_train_support_repo_capped.jsonl", capped_rows)
    write_jsonl(OUT_DIR / "level3_non_passfail_diagnostic.jsonl", diagnostic_rows)

    summary = {
        "stage": STAGE,
        "decision": "level3_passfail_rollup_ready" if passfail_rows else "blocked_no_passfail_rows",
        "full_passfail_count": len(passfail_rows),
        "repo_capped_passfail_count": len(capped_rows),
        "diagnostic_non_passfail_count": len(diagnostic_rows),
        "duplicate_count": duplicate_count,
        "incomplete_required_count": incomplete_required_count,
        "source_input_counts": dict(source_seen),
        "full_language_counts": dict(Counter(str(r.get("language")) for r in passfail_rows)),
        "capped_language_counts": dict(Counter(str(r.get("language")) for r in capped_rows)),
        "full_transition_counts": dict(Counter(str(r.get("verifier_transition")) for r in passfail_rows)),
        "capped_transition_counts": dict(Counter(str(r.get("verifier_transition")) for r in capped_rows)),
        "repo_family_counts_top20": Counter(str(r.get("repo_family")) for r in passfail_rows).most_common(20),
        "artifact_paths": {
            "full": str(OUT_DIR / "level3_passfail_train_support_full.jsonl"),
            "repo_capped": str(OUT_DIR / "level3_passfail_train_support_repo_capped.jsonl"),
            "diagnostic_non_passfail": str(OUT_DIR / "level3_non_passfail_diagnostic.jsonl"),
        },
        "claim_boundary": "Train-support rollup only. No eval claim. ENV_BLOCKED/non-passfail rows are diagnostic by default.",
    }
    write_json(OUT_DIR / "summary.json", summary)
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if passfail_rows else 2


if __name__ == "__main__":
    raise SystemExit(main())
