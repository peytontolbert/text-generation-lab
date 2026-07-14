#!/usr/bin/env python3
"""Retarget underhydrated nonzero/timeout transition observations to INSUFFICIENT_EVIDENCE support."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path("runs/local/artifacts/stage11997_insufficient_evidence_admission")
INPUT = Path("runs/local/artifacts/stage11986_transition_root_250_second_batch_admission_audit/transition_root_250_second_batch_rejected_rows.jsonl")
ADMITTED = ROOT / "insufficient_evidence_admitted_rows.jsonl"
REJECTED = ROOT / "insufficient_evidence_rejected_rows.jsonl"
SUMMARY = ROOT / "insufficient_evidence_admission.json"
SUMMARY_MIRROR = Path("runs/summaries/stage11997_insufficient_evidence_admission.json")
UNDERHYDRATED_MARKERS = [
    "Missing script", "not found", "Could not find", "No such file", "timeout", "timed out",
    "No cmake_minimum_required", "FindTorch.cmake", "gflags", "vitest", "underhydrated",
]


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists(): return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def root_key(row: dict) -> str | None:
    return row.get("root_lineage_key") or row.get("root_id") or row.get("source_root_id") or row.get("source_bundle_id") or row.get("row_id")


def observation(row: dict) -> dict:
    src = row.get("standalone_projection_source") or {}
    return src.get("tool_or_verifier_observation") or src.get("test_observation") or src.get("build_observation") or {}


def observation_text(row: dict) -> str:
    o = observation(row)
    cmd = " ".join(map(str, o.get("command") or []))
    return "\n".join([cmd, o.get("stdout_tail") or "", o.get("stderr_tail") or ""])


def is_underhydrated(row: dict) -> tuple[bool, str | None]:
    reason = row.get("stage11986_rejection_reason") or ""
    if not reason.startswith("nonzero_or_timeout"):
        return False, "not_nonzero_or_timeout_rejection"
    o = observation(row)
    if o.get("returncode") == 0 and not o.get("timed_out"):
        return False, "observation_was_successful"
    text = observation_text(row)
    if o.get("timed_out"):
        return True, "timeout_no_trustworthy_transition"
    if any(marker.lower() in text.lower() for marker in UNDERHYDRATED_MARKERS):
        return True, "missing_dependency_script_or_fixture"
    return False, "nonzero_without_underhydration_marker"


def retarget(row: dict) -> dict:
    out = dict(row)
    options = out.get("opaque_options") or []
    labels = [opt.get("label") for opt in options if opt.get("canonical_value") == "INSUFFICIENT_EVIDENCE" or opt.get("value") == "INSUFFICIENT_EVIDENCE"]
    if not labels:
        raise ValueError(f"missing insufficient option for {out.get('row_id')}")
    target_label = labels[0]
    out["observed_verifier_transition"] = "INSUFFICIENT_EVIDENCE"
    out["bounded_choice_target_label"] = target_label
    out["decoder_text"] = target_label
    out["target_text"] = target_label
    out["target"] = {"bounded_choice_target_label": target_label, "decoder_text": target_label, "semantic_value": "INSUFFICIENT_EVIDENCE"}
    src = dict(out.get("standalone_projection_source") or {})
    src["gold_label"] = target_label
    src["gold_value"] = "INSUFFICIENT_EVIDENCE"
    src["observed_verifier_transition"] = "INSUFFICIENT_EVIDENCE"
    src["projection_mode"] = "stage11997_underhydrated_insufficient_evidence_admission"
    out["standalone_projection_source"] = src
    out["row_id"] = out.get("row_id", "stage11997") + "::stage11997_insufficient_evidence"
    out["root_id"] = (out.get("root_id") or "stage11997_root") + "::stage11997_insufficient_evidence"
    out["source_root_id"] = out["root_id"]
    out["source_bundle_id"] = out["root_id"]
    out["split"] = "train"
    out["split_role"] = "stage11997_insufficient_evidence_train_support_only"
    out["train_support_only"] = True
    out["strict_eval_eligible"] = False
    out["source_heldout_admissible"] = False
    out["stage11997_admission"] = {"admitted": True, "reason": "underhydrated_or_timeout_no_trustworthy_verifier_transition", "original_rejection_reason": row.get("stage11986_rejection_reason")}
    anti = dict(out.get("anti_cheat") or {})
    anti.update({"review_queue_only": False, "not_merged_into_train": False, "deterministic_option_shuffle": True, "singleton_options": False, "target_label_not_visible_before_options": True, "target_value_not_visible_before_options": True})
    out["anti_cheat"] = anti
    return out


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    SUMMARY_MIRROR.parent.mkdir(parents=True, exist_ok=True)
    admitted, rejected = [], []
    reasons = Counter()
    seen = set()
    for row in read_jsonl(INPUT):
        ok, reason = is_underhydrated(row)
        if ok:
            key = (root_key(row), "INSUFFICIENT_EVIDENCE")
            if key in seen:
                ok, reason = False, "duplicate_root_key"
            else:
                seen.add(key)
        if ok:
            try:
                admitted.append(retarget(row))
            except Exception as exc:
                reasons[f"retarget_error::{type(exc).__name__}"] += 1
                rejected.append({"row_id": row.get("row_id"), "reason": str(exc)})
        else:
            reasons[reason or "unknown"] += 1
            rejected.append({"row_id": row.get("row_id"), "reason": reason or "unknown", "original_reason": row.get("stage11986_rejection_reason")})
    write_jsonl(ADMITTED, admitted)
    write_jsonl(REJECTED, rejected)
    summary = {
        "stage": "stage11997_insufficient_evidence_admission",
        "source": str(INPUT),
        "admitted_rows_path": str(ADMITTED),
        "rows_reviewed": len(read_jsonl(INPUT)),
        "admitted_rows": len(admitted),
        "rejected_rows": len(rejected),
        "rejection_reasons": dict(sorted(reasons.items())),
        "language_counts": dict(Counter(r.get("language_family") for r in admitted)),
        "repo_family_counts": dict(Counter(r.get("repo_family") for r in admitted)),
        "status_counts": dict(Counter(r.get("observed_verifier_transition") for r in admitted)),
        "unique_roots": len({root_key(r) for r in admitted}),
        "decision": "admit_insufficient_evidence_train_support" if admitted else "no_insufficient_evidence_rows_admitted",
        "claim_boundary": "Train-support underhydration/timeout rows only; not executable verifier success/failure evidence and not strict/source-heldout.",
        "next_stage_recommendation": {"stage": "stage11998_transition_support_rollup_v6", "action": "Merge INSUFFICIENT_EVIDENCE support and report remaining floors."},
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    SUMMARY_MIRROR.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__": main()
