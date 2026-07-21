#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12222_patch_trace_floor_audit"
SRC = ROOT / "runs/local/artifacts/stage12221_agent_governance_patch_replay/patch_replay_records.jsonl"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"


REQUIRED_TOP_LEVEL = {
    "episode_id",
    "root_id",
    "repo_family",
    "language_family",
    "split",
    "state_before",
    "state_after",
    "ordered_events",
    "candidate_action_set",
    "chosen_action",
    "verifier_result",
    "verifier_transition",
    "patch_trace",
    "stop_decision",
}


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


def audit(row: dict[str, Any]) -> tuple[bool, list[str]]:
    blockers: list[str] = []
    missing = sorted(REQUIRED_TOP_LEVEL - set(row))
    if missing:
        blockers.append("missing_required_top_level:" + ",".join(missing))
    if row.get("split") != "train_support":
        blockers.append("split_not_train_support")
    if row.get("strict_eval_eligible") is not False:
        blockers.append("strict_eval_boundary_not_false")
    if row.get("source_heldout_admissible") is not False:
        blockers.append("source_heldout_boundary_not_false")
    patch = row.get("patch_trace") or {}
    if not patch.get("has_patch_trace"):
        blockers.append("missing_patch_trace")
    if not patch.get("counts_toward_patch_trace_floor"):
        blockers.append("patch_trace_floor_false")
    if patch.get("counts_toward_fail_to_pass_floor"):
        blockers.append("incorrect_fail_to_pass_floor_true")
    if (patch.get("patch_apply_check") or {}).get("returncode") != 0:
        blockers.append("patch_apply_check_failed")
    if (patch.get("patch_apply_result") or {}).get("returncode") != 0:
        blockers.append("patch_apply_failed")
    events = row.get("ordered_events") or []
    if len(events) < 8 or not all(isinstance(e, dict) for e in events):
        blockers.append("ordered_events_not_structured_or_too_short")
    phases = {e.get("phase") for e in events if isinstance(e, dict)}
    if not {"before", "before_plus_patch", "after"}.issubset(phases):
        blockers.append("missing_before_patch_after_event_phases")
    verifier = row.get("verifier_result") or {}
    if not verifier.get("runnable_verifier_proof"):
        blockers.append("missing_runnable_verifier_proof")
    if row.get("verifier_transition") != "PASS_TO_PASS":
        blockers.append("unexpected_transition_for_stage12221")
    if "weak" not in str(patch.get("semantic_patch_validation_strength", "")):
        blockers.append("missing_weak_validation_disclaimer")
    return not blockers, blockers


def main() -> int:
    admitted: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for line_no, row in iter_jsonl(SRC) or []:
        ok, blockers = audit(row)
        audit_row = {
            "source_ref": f"{SRC}:{line_no}",
            "episode_id": row.get("episode_id"),
            "repo_family": row.get("repo_family"),
            "language_family": row.get("language_family"),
            "verifier_transition": row.get("verifier_transition"),
            "patch_trace_floor": bool((row.get("patch_trace") or {}).get("counts_toward_patch_trace_floor")),
            "fail_to_pass_floor": bool((row.get("patch_trace") or {}).get("counts_toward_fail_to_pass_floor")),
            "blockers": blockers,
            "row": row,
        }
        (admitted if ok else blocked).append(audit_row)

    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT / "admitted_patch_trace_floor_records.jsonl", admitted)
    write_jsonl(OUT / "blocked_patch_trace_floor_records.jsonl", blocked)
    summary = {
        "stage": STAGE,
        "source_stage": "stage12221_agent_governance_patch_replay",
        "decision": "patch_trace_floor_records_ready" if admitted else "blocked_no_patch_trace_floor_records",
        "admitted_count": len(admitted),
        "blocked_count": len(blocked),
        "patch_trace_floor_count": sum(1 for r in admitted if r["patch_trace_floor"]),
        "fail_to_pass_floor_count": sum(1 for r in admitted if r["fail_to_pass_floor"]),
        "transition_counts": dict(Counter(str(r["verifier_transition"]) for r in admitted)),
        "language_counts": dict(Counter(str(r["language_family"]) for r in admitted)),
        "repo_family_counts": dict(Counter(str(r["repo_family"]) for r in admitted)),
        "training_allowed": False,
        "tests_executed": False,
        "claim_boundary": "Audit only. Stage12221 contributes one train-support patch-trace/verifier observation if admitted, but no fail-to-pass repair proof and no strict/source-heldout claim.",
        "artifact_paths": {
            "admitted": str(OUT / "admitted_patch_trace_floor_records.jsonl"),
            "blocked": str(OUT / "blocked_patch_trace_floor_records.jsonl"),
        },
    }
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if admitted else 2


if __name__ == "__main__":
    raise SystemExit(main())
