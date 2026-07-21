#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12238_verifier_observation_auxiliary_conversion_audit"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
SRC = (
    ROOT
    / "runs/local/artifacts/stage12216_normalized_verifier_observation_dataset/"
    / "normalized_verifier_observation_records.jsonl"
)
BLOCKED_SRC = (
    ROOT
    / "runs/local/artifacts/stage12216_normalized_verifier_observation_dataset/"
    / "blocked_normalization_rows.jsonl"
)

ALLOWED_PROJECTIONS = {
    "transition_verifier_transition",
    "transition_continue_or_stop",
    "transition_next_action",
    "execution_trace_interpretation",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def permissions(row: dict[str, Any]) -> set[str]:
    raw = row.get("projection_permissions") or []
    if isinstance(raw, list):
        return {str(x) for x in raw}
    if isinstance(raw, dict):
        return {str(k) for k, v in raw.items() if v}
    return set()


def missing_required(row: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for field in [
        "state_before",
        "ordered_events",
        "chosen_action",
        "command_result",
        "verifier_result",
        "state_after",
        "stop_decision",
    ]:
        if not row.get(field):
            missing.append(field)
    vr = row.get("verifier_result") or {}
    cr = row.get("command_result") or {}
    if not vr.get("command_text"):
        missing.append("verifier_result.command_text")
    if "exit_code" not in vr:
        missing.append("verifier_result.exit_code")
    if not (
        vr.get("stdout_sha256")
        or vr.get("stderr_sha256")
        or cr.get("stdout_sha256")
        or cr.get("stderr_sha256")
    ):
        missing.append("command_or_verifier_result.stdout_or_stderr_hash")
    return missing


def blocked_reason(row: dict[str, Any]) -> list[str]:
    reasons = missing_required(row)
    if row.get("patch_trace", {}).get("has_patch_trace") or row.get("patch_diff"):
        reasons.append("has_patch_trace_not_verifier_observation_only")
    if row.get("strict_eval_eligible"):
        reasons.append("strict_eval_eligible_must_be_false")
    if not row.get("train_support_only"):
        reasons.append("train_support_only_must_be_true")
    if row.get("source_heldout_admissible"):
        reasons.append("source_heldout_admissible_must_be_false")
    if row.get("counts_toward_unbounded_patch_trace_floor"):
        reasons.append("counts_toward_patch_trace_floor_must_be_false")
    return reasons


def projection_row(row: dict[str, Any], family: str) -> dict[str, Any]:
    verifier = row.get("verifier_result") or {}
    stop = row.get("stop_decision") or {}
    chosen = row.get("chosen_action") or {}
    target_by_family = {
        "transition_verifier_transition": verifier.get("verifier_transition")
        or row.get("verifier_transition")
        or row.get("verifier_status"),
        "transition_continue_or_stop": stop.get("continue_or_stop", "CONTINUE"),
        "transition_next_action": chosen.get("role") or chosen.get("description"),
        "execution_trace_interpretation": row.get("state_update", {}).get("state_update_type")
        or row.get("state_after", {}).get("verifier_transition")
        or verifier.get("verifier_transition"),
    }
    return {
        "row_id": f"{STAGE}::{row.get('rollup_record_id') or row.get('episode_id')}::{family}",
        "source_stage": "stage12216_normalized_verifier_observation_dataset",
        "source_ref": row.get("source_ref") or row.get("rollup_source_ref"),
        "root_id": row.get("root_id"),
        "repo_family": row.get("repo_family"),
        "language_family": row.get("language_family") or row.get("language"),
        "split": "train_support",
        "task_type": family,
        "target_semantic_value": target_by_family[family],
        "state_before": row.get("state_before"),
        "candidate_action_set": row.get("candidate_action_set"),
        "ordered_events": row.get("ordered_events"),
        "command_result": row.get("command_result"),
        "verifier_result": verifier,
        "state_after": row.get("state_after"),
        "stop_decision": stop,
        "patch_trace": {
            "has_patch_trace": False,
            "patch_diff": None,
            "counts_toward_patch_trace_floor": False,
            "no_patch_reason": row.get("no_patch_reason")
            or "verifier_observation_only_no_edit_or_patch_action_in_source_record",
        },
        "loss_mask_enabled": False,
        "training_allowed": False,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "counts_toward_unbounded_patch_trace_floor": False,
        "claim_boundary": "safe verifier-observation auxiliary candidate only; not Level-3 patch trace or repair proof",
    }


def main() -> int:
    rows = read_jsonl(SRC)
    blocked_source_rows = read_jsonl(BLOCKED_SRC)
    blocked: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    source_counts = Counter()
    transition_counts = Counter()
    lang_counts = Counter()
    repo_counts = Counter()
    projection_counts = Counter()
    block_counts = Counter()
    projection_by_transition: dict[str, Counter[str]] = defaultdict(Counter)

    for row in rows:
        source_counts["input_rows"] += 1
        transition = (
            (row.get("verifier_result") or {}).get("verifier_transition")
            or row.get("verifier_transition")
            or row.get("verifier_status")
            or "unknown"
        )
        transition_counts[transition] += 1
        lang_counts[row.get("language_family") or row.get("language") or "unknown"] += 1
        repo_counts[row.get("repo_family") or "unknown"] += 1
        reasons = blocked_reason(row)
        if reasons:
            block_counts.update(reasons)
            blocked.append(
                {
                    "rollup_record_id": row.get("rollup_record_id"),
                    "root_id": row.get("root_id"),
                    "repo_family": row.get("repo_family"),
                    "language_family": row.get("language_family") or row.get("language"),
                    "verifier_transition": transition,
                    "blocked_reasons": reasons,
                }
            )
            continue

        perms = permissions(row)
        for family in sorted(perms & ALLOWED_PROJECTIONS):
            if family in {"transition_next_action", "execution_trace_interpretation"}:
                # Keep these as action/verifier-policy support only when a candidate action set is present.
                if not row.get("candidate_action_set"):
                    block_counts[f"{family}_missing_candidate_action_set"] += 1
                    continue
            if family == "transition_continue_or_stop":
                # Single verifier observations are never DONE/final-acceptance proof.
                if (row.get("stop_decision") or {}).get("continue_or_stop") not in {None, "CONTINUE"}:
                    block_counts["continue_stop_non_continue_target"] += 1
                    continue
            candidate = projection_row(row, family)
            candidates.append(candidate)
            projection_counts[family] += 1
            projection_by_transition[family][transition] += 1

    payload = {
        "stage": STAGE,
        "decision": "verifier_observation_auxiliary_candidates_ready_loss_disabled",
        "source_stage": "stage12216_normalized_verifier_observation_dataset",
        "source_counts": {
            "input_rows": len(rows),
            "source_blocked_rows": len(blocked_source_rows),
            "conversion_blocked_rows": len(blocked),
            "conversion_candidate_rows": len(candidates),
        },
        "language_family_counts": dict(sorted(lang_counts.items())),
        "repo_family_counts_top20": repo_counts.most_common(20),
        "verifier_transition_counts": dict(sorted(transition_counts.items())),
        "projection_candidate_counts": dict(sorted(projection_counts.items())),
        "projection_by_transition": {
            family: dict(sorted(counter.items()))
            for family, counter in sorted(projection_by_transition.items())
        },
        "blocked_reason_counts": dict(sorted(block_counts.items())),
        "allowed_projection_families": sorted(ALLOWED_PROJECTIONS),
        "disallowed_projection_families": [
            "patch_apply",
            "patch_generation",
            "patch_judgment",
            "final_acceptance",
            "level_3_patch_trace",
            "source_heldout_eval",
        ],
        "hard_rules": [
            "loss_mask_enabled remains false for all emitted candidates",
            "patch_trace.has_patch_trace must be false",
            "counts_toward_unbounded_patch_trace_floor must be false",
            "strict_eval_eligible and source_heldout_admissible must be false",
            "PASS_CURRENT_BUILD is build-only verifier-status support, not runnable repair proof",
            "single verifier observations train CONTINUE only, never DONE/final acceptance",
            "prompt renderer must hide chosen_action_id, is_chosen, negative_kind, command_result, verifier_result, state_after, and stop_decision until target time",
        ],
        "artifact_paths": {
            "candidate_rows": str(OUT / "verifier_observation_auxiliary_candidates.jsonl"),
            "blocked_rows": str(OUT / "blocked_verifier_observation_auxiliary_conversion.jsonl"),
            "summary": str(SUMMARY),
        },
        "training_allowed": False,
        "claim_boundary": "Conversion audit only. These candidates can support future verifier/status auxiliary training after a separate trainer request, but they are not Level-3 patch traces or repair proof.",
    }

    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT / "verifier_observation_auxiliary_candidates.jsonl", candidates)
    write_jsonl(OUT / "blocked_verifier_observation_auxiliary_conversion.jsonl", blocked)
    write_json(OUT / "verifier_observation_auxiliary_conversion_audit.json", payload)
    write_json(SUMMARY, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
