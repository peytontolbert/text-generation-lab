#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12229_patch_trace_projection_qc"
SRC = ROOT / "runs/local/artifacts/stage12228_patch_trace_projection_rows/patch_trace_projection_rows.jsonl"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"


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


def blockers(row: dict[str, Any]) -> list[str]:
    out: list[str] = []
    options = row.get("opaque_options") or []
    mirrored = ((row.get("standalone_projection_source") or {}).get("opaque_options") or [])
    target_count = sum(1 for opt in options if opt.get("is_target"))
    labels = [opt.get("label") for opt in options]
    if len(options) < 2:
        out.append("singleton_or_missing_options")
    if len(set(labels)) != len(labels):
        out.append("duplicate_option_labels")
    if options != mirrored:
        out.append("option_mirror_mismatch")
    if target_count != 1:
        out.append("target_count_not_one")
    if not row.get("bounded_choice_target_label"):
        out.append("missing_target_label")
    if row.get("bounded_choice_target_label") not in labels:
        out.append("target_label_not_in_options")
    if row.get("strict_eval_eligible") is not False or row.get("source_heldout_admissible") is not False:
        out.append("eval_boundary_not_false")
    if row.get("training_allowed") is not False:
        out.append("training_allowed_not_false")
    loss = row.get("loss_mask") or {}
    if loss.get("bounded_choice") is not False or loss.get("decoder_ce") is not False:
        out.append("loss_mask_enabled_before_training_gate")
    patch = row.get("patch_trace") or {}
    strength = str(patch.get("semantic_patch_validation_strength") or "")
    projection = str(row.get("projection_family") or "")
    target = str(row.get("target") or "")
    if "weak" in strength and projection != "patch_apply":
        out.append("weak_unrelated_verifier_projected_beyond_patch_apply")
    if "downgraded" in strength and target == "FAIL_TO_PASS":
        out.append("downgraded_row_still_targets_fail_to_pass")
    if row.get("state_after", {}).get("verifier_transition") == "FAIL_TO_PASS" and target == "TEST_ADDED_NOT_COMPARABLE":
        out.append("stale_nested_state_after_fail_to_pass")
    phases = row.get("verifier_result_by_phase") or {}
    if not {"before", "before_plus_patch", "after"}.issubset(set(phases)):
        out.append("missing_phase_verifier_result")
    events = row.get("ordered_events") or []
    if not isinstance(events, list) or len(events) < 3:
        out.append("missing_ordered_events")
    prompt = str(row.get("prompt_text") or "")
    if "is_target" in prompt or "bounded_choice_target_label" in prompt:
        out.append("target_metadata_leaked_in_prompt")
    return out


def main() -> int:
    admitted: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for line_no, row in iter_jsonl(SRC) or []:
        row = dict(row)
        b = blockers(row)
        if b:
            row["stage12229_blockers"] = b
            row["source_ref"] = f"{SRC}:{line_no}"
            blocked.append(row)
        else:
            admitted.append(row)

    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT / "admitted_patch_trace_projection_rows.jsonl", admitted)
    write_jsonl(OUT / "blocked_patch_trace_projection_rows.jsonl", blocked)
    summary = {
        "stage": STAGE,
        "source_stage": "stage12228_patch_trace_projection_rows",
        "decision": "projection_qc_passed_training_still_blocked" if admitted and not blocked else "projection_qc_has_blockers",
        "admitted_count": len(admitted),
        "blocked_count": len(blocked),
        "blocker_counts": dict(Counter(b for row in blocked for b in row.get("stage12229_blockers", []))),
        "projection_counts": dict(Counter(r.get("projection_family") for r in admitted)),
        "target_counts": dict(Counter(r.get("target") for r in admitted)),
        "training_allowed": False,
        "claim_boundary": "Projection QC only. Passing rows still have disabled loss masks and cannot trigger training until source supply and trainer task routing gates are met.",
        "artifact_paths": {
            "admitted": str(OUT / "admitted_patch_trace_projection_rows.jsonl"),
            "blocked": str(OUT / "blocked_patch_trace_projection_rows.jsonl"),
        },
    }
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if not blocked else 2


if __name__ == "__main__":
    raise SystemExit(main())
