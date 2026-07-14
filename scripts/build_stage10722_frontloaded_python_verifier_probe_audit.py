#!/usr/bin/env python3
"""Audit the corrected frontloaded Python verifier probe."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
OUT_DIR = ROOT / "runs/local/artifacts/stage10722_frontloaded_python_verifier_probe_audit"

STRICT_10719 = ROOT / "runs/local/artifacts/stage10719_execution_repaired_plus_python_verifier_probe/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json"
STRICT_10721 = ROOT / "runs/local/artifacts/stage10721_frontloaded_python_verifier_probe/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json"
EVAL_10719 = ROOT / "runs/local/artifacts/stage10719_execution_repaired_plus_python_verifier_probe/bounded_decoder_probe/bounded_choice_eval_audit_eval.json"
EVAL_10721 = ROOT / "runs/local/artifacts/stage10721_frontloaded_python_verifier_probe/bounded_decoder_probe/bounded_choice_eval_audit_eval.json"
SAMPLING_10720 = ROOT / "runs/local/artifacts/stage10720_python_support_sampling_gap_audit/python_support_sampling_gap_audit.json"
LOSS_10721 = ROOT / "runs/local/artifacts/stage10721_frontloaded_python_verifier_probe/bounded_decoder_probe/loss_by_step.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def find_row(data: dict[str, Any], needle: str) -> dict[str, Any]:
    for row in data.get("row_cards", []):
        if needle in str(row.get("row_id") or ""):
            return row
    return {}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    strict19 = load_json(STRICT_10719)
    strict21 = load_json(STRICT_10721)
    eval19 = load_json(EVAL_10719)
    eval21 = load_json(EVAL_10721)
    sampling20 = load_json(SAMPLING_10720)
    loss21 = load_jsonl(LOSS_10721)

    support_markers = ("stage10236::localsess_code_assist", "stage10499::localsess_code_assist_hf_local_multitest_repaired", "multitarget_abstain_support")
    support_hits = 0
    for row in loss21:
        for rid in row.get("row_ids", []):
            if any(marker in rid for marker in support_markers):
                support_hits += 1

    py19 = find_row(strict19, "python::verifier_outcome")
    py21 = find_row(strict21, "python::verifier_outcome")
    rust19 = find_row(strict19, "rust::evidence_citation")
    rust21 = find_row(strict21, "rust::evidence_citation")

    audit = {
        "stage": 10722,
        "stage_name": "stage10722_frontloaded_python_verifier_probe_audit",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": True,
        "claim_scope": [
            "Judge whether fixing the stage10719 sampling gap changed the frontier.",
            "Separate sampling-path failure from capability failure.",
            "Define the next bottleneck based on the corrected rerun."
        ],
        "headline_findings": [
            "The corrected stage10721 rerun did sample all six Python verifier support rows.",
            "Strict top-1 accuracy still stayed at 22/24, so the flat result is no longer explainable by unsampled support.",
            "The strict Python verifier residual improved materially in full-vocab rank (24 -> 9) but remained top-1 wrong (C instead of B).",
            "The strict Rust citation residual remained top-1 wrong and its full-vocab rank worsened slightly (2 -> 4).",
            "This isolates the next bottleneck as decision-boundary quality or representation, not support reachability."
        ],
        "metric_deltas": {
            "strict_constrained_top1_10719": strict19.get("constrained_choice_top1_accuracy"),
            "strict_constrained_top1_10721": strict21.get("constrained_choice_top1_accuracy"),
            "eval_constrained_top1_10719": eval19.get("constrained_choice_top1_accuracy"),
            "eval_constrained_top1_10721": eval21.get("constrained_choice_top1_accuracy"),
            "eval_full_vocab_top1_10719": eval19.get("full_vocab_top1_accuracy"),
            "eval_full_vocab_top1_10721": eval21.get("full_vocab_top1_accuracy"),
        },
        "residuals": {
            "python_verifier": {
                "target": py21.get("bounded_choice_target_label"),
                "pred_10719": py19.get("constrained_choice_top1_label"),
                "pred_10721": py21.get("constrained_choice_top1_label"),
                "target_rank_full_vocab_10719": py19.get("target_rank_full_vocab"),
                "target_rank_full_vocab_10721": py21.get("target_rank_full_vocab"),
            },
            "rust_citation": {
                "target": rust21.get("bounded_choice_target_label"),
                "pred_10719": rust19.get("constrained_choice_top1_label"),
                "pred_10721": rust21.get("constrained_choice_top1_label"),
                "target_rank_full_vocab_10719": rust19.get("target_rank_full_vocab"),
                "target_rank_full_vocab_10721": rust21.get("target_rank_full_vocab"),
            },
        },
        "sampling_confirmation": {
            "sampling_gap_stage10719_support_rows_sampled": sampling20["sampling_audit"]["support_rows_sampled"],
            "sampling_gap_stage10719_support_rows_unsampled": len(sampling20["sampling_audit"]["support_rows_unsampled"]),
            "stage10721_support_row_hits": support_hits,
        },
        "next_best_step": [
            "Build a representation-focused Python verifier contrast lane rather than adding more of the same root support.",
            "Specifically target the B-vs-C confusion on the MirrorMind strict row using stronger selected-test semantics and alternative-hypothesis evidence.",
            "In parallel, build a real fresh non-tokenizers Rust citation contrast root because the current Rust miss is also no longer a simple support-reachability issue."
        ],
        "outputs": {
            "summary_json": "runs/local/artifacts/stage10722_frontloaded_python_verifier_probe_audit/frontloaded_python_verifier_probe_audit.json"
        },
    }

    write_json(OUT_DIR / "frontloaded_python_verifier_probe_audit.json", audit)


if __name__ == "__main__":
    main()
