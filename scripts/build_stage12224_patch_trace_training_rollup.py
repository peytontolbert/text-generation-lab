#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12224_patch_trace_training_rollup"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

SOURCES = [
    (
        "stage12221_agent_governance_patch_replay",
        ROOT / "runs/local/artifacts/stage12221_agent_governance_patch_replay/patch_replay_records.jsonl",
    ),
    (
        "stage12223_targeted_patch_replay_smoke",
        ROOT / "runs/local/artifacts/stage12223_targeted_patch_replay_smoke/targeted_patch_replay_records.jsonl",
    ),
]


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
    patch = row.get("patch_trace") or {}
    if row.get("split") != "train_support":
        blockers.append("not_train_support")
    if row.get("strict_eval_eligible") is not False:
        blockers.append("strict_eval_boundary_not_false")
    if row.get("source_heldout_admissible") is not False:
        blockers.append("source_heldout_boundary_not_false")
    if not patch.get("counts_toward_patch_trace_floor"):
        blockers.append("not_patch_trace_floor")
    if (patch.get("patch_apply_check") or {}).get("returncode") != 0:
        blockers.append("patch_apply_check_failed")
    if (patch.get("patch_apply_result") or {}).get("returncode") != 0:
        blockers.append("patch_apply_failed")
    if not isinstance(row.get("ordered_events"), list) or len(row["ordered_events"]) < 8:
        blockers.append("missing_structured_ordered_events")
    if not row.get("verifier_result", {}).get("runnable_verifier_proof"):
        blockers.append("missing_runnable_verifier_proof")
    if row.get("verifier_transition") not in {"FAIL_TO_PASS", "PASS_TO_PASS"}:
        blockers.append("unsupported_transition_for_patch_rollup")
    return not blockers, blockers


def main() -> int:
    admitted: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    seen = set()
    for source_stage, path in SOURCES:
        for line_no, row in iter_jsonl(path) or []:
            key = row.get("episode_id")
            if key in seen:
                continue
            seen.add(key)
            ok, blockers = audit(row)
            row = dict(row)
            row["rollup_source_stage"] = source_stage
            row["rollup_source_ref"] = f"{path}:{line_no}"
            row["training_allowed"] = False
            row["train_support_only"] = True
            if ok:
                admitted.append(row)
            else:
                row["stage12224_blockers"] = blockers
                blocked.append(row)

    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT / "patch_trace_train_support.jsonl", admitted)
    write_jsonl(OUT / "blocked_patch_trace_records.jsonl", blocked)
    summary = {
        "stage": STAGE,
        "decision": "patch_trace_train_support_ready" if admitted else "blocked_no_patch_trace_train_support",
        "source_stages": [s for s, _ in SOURCES],
        "admitted_count": len(admitted),
        "blocked_count": len(blocked),
        "patch_trace_floor_count": sum(1 for r in admitted if r.get("patch_trace", {}).get("counts_toward_patch_trace_floor")),
        "fail_to_pass_floor_count": sum(1 for r in admitted if r.get("patch_trace", {}).get("counts_toward_fail_to_pass_floor")),
        "transition_counts": dict(Counter(str(r.get("verifier_transition")) for r in admitted)),
        "language_counts": dict(Counter(str(r.get("language_family")) for r in admitted)),
        "repo_family_counts": dict(Counter(str(r.get("repo_family")) for r in admitted)),
        "training_allowed": False,
        "tests_executed": False,
        "claim_boundary": "Patch-trace train-support rollup only. No strict/source-heldout claim. Only FAIL_TO_PASS rows count toward repair proof floor.",
        "next_blocker": "Scale beyond 3 Python patch-trace rows and add non-Python direct verifier-tied patch replays before training.",
        "artifact_paths": {
            "admitted": str(OUT / "patch_trace_train_support.jsonl"),
            "blocked": str(OUT / "blocked_patch_trace_records.jsonl"),
        },
    }
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if admitted else 2


if __name__ == "__main__":
    raise SystemExit(main())
