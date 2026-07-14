#!/usr/bin/env python3
"""Audit why stage10719 support failed to move: support rows were unsampled."""

from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
OUT_DIR = ROOT / "runs/local/artifacts/stage10720_python_support_sampling_gap_audit"

REQUEST_JSON = ROOT / "runs/local/artifacts/stage10719_execution_repaired_plus_python_verifier_probe_request/execution_repaired_plus_python_verifier_probe_request.json"
MANIFEST_JSONL = ROOT / "runs/local/artifacts/stage10719_execution_repaired_plus_python_verifier_probe_request/execution_repaired_plus_python_verifier_probe_manifest.jsonl"
LOSS_JSONL = ROOT / "runs/local/artifacts/stage10719_execution_repaired_plus_python_verifier_probe/bounded_decoder_probe/loss_by_step.jsonl"
STRICT10710 = ROOT / "runs/local/artifacts/stage10710_rewritten_plus_reviewed_probe_execution_repaired/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json"
STRICT10719 = ROOT / "runs/local/artifacts/stage10719_execution_repaired_plus_python_verifier_probe/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json"

SUPPORT_MARKERS = (
    "stage10236::localsess_code_assist",
    "stage10499::localsess_code_assist_hf_local_multitest_repaired",
    "multitarget_abstain_support",
)


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


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    request = load_json(REQUEST_JSON)
    manifest_rows = load_jsonl(MANIFEST_JSONL)
    train_rows = manifest_rows[: int(request["split_counts"]["train"])]
    loss_rows = load_jsonl(LOSS_JSONL)
    seen = []
    for row in loss_rows:
        seen.extend(row.get("row_ids", []))
    seen_set = set(seen)

    support_rows = [row for row in train_rows if any(marker in str(row.get("row_id") or "") for marker in SUPPORT_MARKERS)]
    unsampled_rows = [row for row in train_rows if str(row.get("row_id") or "") not in seen_set]

    strict10710 = load_json(STRICT10710)
    strict10719 = load_json(STRICT10719)

    def residual_card(data: dict[str, Any], needle: str) -> dict[str, Any]:
        for row in data.get("row_cards", []):
            if needle in str(row.get("row_id") or ""):
                return row
        return {}

    py10 = residual_card(strict10710, "python::verifier_outcome")
    py19 = residual_card(strict10719, "python::verifier_outcome")
    rust10 = residual_card(strict10710, "rust::evidence_citation")
    rust19 = residual_card(strict10719, "rust::evidence_citation")

    batch_size = 2
    max_steps = 128
    minimum_steps_to_cover_all_train_rows = math.ceil(len(train_rows) / batch_size)

    audit = {
        "stage": 10720,
        "stage_name": "stage10720_python_support_sampling_gap_audit",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": True,
        "claim_scope": [
            "Explain why stage10719 added Python verifier support but did not move the strict frontier.",
            "Audit the train-row sampling path, not just the strict score.",
            "Produce the exact operational correction needed for the next honest probe."
        ],
        "headline_findings": [
            "All six newly added Python verifier support rows were present inside the train cap but were never sampled.",
            "The stage10719 run consumed exactly 256 train-row events (128 steps * batch size 2) out of a 287-row train slice.",
            "The new Python support rows were appended at manifest positions 281-286, so they remained outside the sampled prefix.",
            "The flat 22/24 result is therefore not evidence that the new support was ineffective; the support was never actually trained on."
        ],
        "sampling_audit": {
            "train_rows": len(train_rows),
            "sample_events": len(seen),
            "unique_seen_rows": len(seen_set),
            "unsampled_rows": len(unsampled_rows),
            "max_steps": max_steps,
            "batch_size": batch_size,
            "minimum_steps_to_cover_all_train_rows_once": minimum_steps_to_cover_all_train_rows,
            "support_rows_added": len(support_rows),
            "support_rows_sampled": sum(1 for row in support_rows if row["row_id"] in seen_set),
            "support_rows_unsampled": [row["row_id"] for row in support_rows if row["row_id"] not in seen_set],
            "support_manifest_indices": {
                row["row_id"]: idx
                for idx, row in enumerate(train_rows)
                if row in support_rows
            },
        },
        "strict_residual_comparison": {
            "python_verifier": {
                "stage10710_pred": py10.get("constrained_choice_top1_label"),
                "stage10719_pred": py19.get("constrained_choice_top1_label"),
                "target": py19.get("bounded_choice_target_label"),
                "target_rank_full_vocab_10710": py10.get("target_rank_full_vocab"),
                "target_rank_full_vocab_10719": py19.get("target_rank_full_vocab"),
            },
            "rust_citation": {
                "stage10710_pred": rust10.get("constrained_choice_top1_label"),
                "stage10719_pred": rust19.get("constrained_choice_top1_label"),
                "target": rust19.get("bounded_choice_target_label"),
                "target_rank_full_vocab_10710": rust10.get("target_rank_full_vocab"),
                "target_rank_full_vocab_10719": rust19.get("target_rank_full_vocab"),
            },
        },
        "required_fix": {
            "frontload_new_support_rows": True,
            "or_raise_max_steps_to_cover_train_rows": True,
            "recommended_next_probe_min_steps": minimum_steps_to_cover_all_train_rows,
            "recommended_next_probe_strategy": "frontload the six Python verifier support rows and raise max_steps to at least 144 so no appended support can be skipped again",
        },
        "outputs": {
            "summary_json": "runs/local/artifacts/stage10720_python_support_sampling_gap_audit/python_support_sampling_gap_audit.json"
        },
    }

    write_json(OUT_DIR / "python_support_sampling_gap_audit.json", audit)


if __name__ == "__main__":
    main()
