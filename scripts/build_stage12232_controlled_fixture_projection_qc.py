#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12232_controlled_fixture_projection_qc"
SRC = ROOT / "runs/local/artifacts/stage12231_controlled_fixture_patch_trace_projections/controlled_fixture_patch_trace_projection_rows.jsonl"
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


def row_blockers(row: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    options = row.get("opaque_options") or []
    if row.get("source_kind") != "controlled_fixture":
        blockers.append("source_kind_not_controlled_fixture")
    if row.get("controlled_curriculum_only") is not True:
        blockers.append("controlled_curriculum_only_not_true")
    if row.get("curriculum_scope") != "controlled_fixture_projection_only":
        blockers.append("bad_curriculum_scope")
    if row.get("external_patch_trace_rollup_eligible") is not False:
        blockers.append("external_patch_trace_rollup_eligible_not_false")
    if row.get("training_gate_required") != "separate_controlled_curriculum_gate":
        blockers.append("missing_training_gate_required")
    if row.get("training_allowed") is not False:
        blockers.append("training_allowed_not_false")
    if row.get("strict_eval_eligible") is not False or row.get("source_heldout_admissible") is not False:
        blockers.append("eval_boundary_not_false")
    patch = row.get("patch_trace") or {}
    if patch.get("counts_toward_patch_trace_floor") is not False:
        blockers.append("controlled_row_counts_toward_external_patch_floor")
    if patch.get("counts_toward_fail_to_pass_floor") is not False:
        blockers.append("controlled_row_counts_toward_external_fail_to_pass_floor")
    if patch.get("controlled_curriculum_only") is not True:
        blockers.append("missing_controlled_curriculum_marker")
    if len(options) < 2:
        blockers.append("singleton_options")
    if sum(1 for o in options if o.get("is_target")) != 1:
        blockers.append("target_count_not_one")
    if options != ((row.get("standalone_projection_source") or {}).get("opaque_options") or []):
        blockers.append("option_mirror_mismatch")
    loss = row.get("loss_mask") or {}
    if loss.get("bounded_choice") is not False or loss.get("decoder_ce") is not False:
        blockers.append("loss_mask_enabled_before_curriculum_gate")
    phases = row.get("verifier_result_by_phase") or {}
    if not {"before", "before_plus_patch", "after"}.issubset(phases):
        blockers.append("missing_phase_evidence")
    prompt = str(row.get("prompt_text") or "")
    if "is_target" in prompt or "bounded_choice_target_label" in prompt:
        blockers.append("target_metadata_leaked")
    if "/data/agentkernel-seq2seq-text-lab" in prompt or "/home/peyton" in prompt:
        blockers.append("absolute_path_leaked_in_prompt")
    return blockers


def main() -> int:
    admitted: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for line_no, row in iter_jsonl(SRC) or []:
        row = dict(row)
        blockers = row_blockers(row)
        if blockers:
            row["stage12232_blockers"] = blockers
            row["source_ref"] = f"{SRC}:{line_no}"
            blocked.append(row)
        else:
            admitted.append(row)
    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT / "admitted_controlled_fixture_projection_rows.jsonl", admitted)
    write_jsonl(OUT / "blocked_controlled_fixture_projection_rows.jsonl", blocked)
    summary = {
        "stage": STAGE,
        "source_stage": "stage12231_controlled_fixture_patch_trace_projections",
        "decision": "controlled_fixture_projection_qc_passed_training_blocked" if admitted and not blocked else "controlled_fixture_projection_qc_has_blockers",
        "admitted_count": len(admitted),
        "blocked_count": len(blocked),
        "blocker_counts": dict(Counter(b for row in blocked for b in row.get("stage12232_blockers", []))),
        "language_counts": dict(Counter(r.get("language_family") for r in admitted)),
        "projection_counts": dict(Counter(r.get("projection_family") for r in admitted)),
        "training_allowed": False,
        "claim_boundary": "QC only. Controlled fixture rows are curriculum-only and excluded from external/source-heldout patch-trace floors.",
        "artifact_paths": {
            "admitted": str(OUT / "admitted_controlled_fixture_projection_rows.jsonl"),
            "blocked": str(OUT / "blocked_controlled_fixture_projection_rows.jsonl"),
        },
    }
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if not blocked else 2


if __name__ == "__main__":
    raise SystemExit(main())
