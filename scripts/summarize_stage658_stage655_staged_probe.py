#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FAST_EVAL = ROOT / "runs/local/artifacts/stage658_stage655_staged_probe_fast_eval.json"
BASE_EVAL = ROOT / "runs/local/artifacts/stage654_stage653_generalized_probe_fast_eval.json"
BUNDLE = ROOT / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage658_stage655_stage3_full_lr1e6_steps40"
OUT = ROOT / "runs/local/artifacts/stage658_stage655_staged_probe_summary.json"
DOC = ROOT / "docs/stage658_stage655_staged_probe.md"


def main() -> None:
    result = json.loads(FAST_EVAL.read_text(encoding="utf-8"))
    base = json.loads(BASE_EVAL.read_text(encoding="utf-8"))
    summary = {
        "artifact_kind": "stage658_stage655_staged_probe_summary",
        "timestamp": int(time.time()),
        "bundle_dir": str(BUNDLE),
        "checkpoint": str(BUNDLE / "checkpoints/step_00000040.pt"),
        "fast_eval": str(FAST_EVAL),
        "baseline_stage654_fast_eval": str(BASE_EVAL),
        "dataset_manifest": "runs/local/tmp/stage655_generalized_bridge_curriculum/agentkernel_lite_encdec_dataset_manifest.json",
        "stage_sequence": [
            "stage656_stage1_bindings_40_steps",
            "stage657_stage2_compositions_40_steps",
            "stage658_stage3_full_40_steps",
        ],
        "target_answer_kbpp": 8.0,
        "no_filter_exact_kbpp": result["exact_kbpp"],
        "no_filter_answer_kbpp": result["answer_kbpp"],
        "stage654_answer_kbpp": base["answer_kbpp"],
        "answer_kbpp_delta_vs_stage654": result["answer_kbpp"] - base["answer_kbpp"],
        "no_filter_exact_accuracy": result["total"]["exact_accuracy"],
        "no_filter_answer_accuracy": result["total"]["answer_accuracy"],
        "decision": "rejected_as_8kbpp_rung_tiny_positive_diagnostic",
        "finding": (
            "Selectors plus staged exposure give a tiny answer gain but do not solve the 8-KBPP rung. "
            "The surface split is likely wrong for learnability: some fields are held out as whole schemas, "
            "so the model lacks train examples for the field families it must recover. The next algorithmic "
            "correction is balanced generalization: train must cover every schema and eval should hold out "
            "bindings/entities/compositions, not entire field families."
        ),
        "by_unit_family": result["by_unit_family"],
        "next_stage": {
            "label": "stage659_balanced_generalized_8kbpp_surface",
            "goal": "Rebuild the generalized 8-KBPP surface so every schema family appears in train while eval holds out bindings and compositions.",
            "acceptance": "surface ceiling >= 8 KBPP, then no-filter trained answer KBPP >= 8.0",
        },
    }
    OUT.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        f"""# Stage658 Stage655 Staged Probe

Summary: `{OUT.relative_to(ROOT)}`

Bundle: `{BUNDLE.relative_to(ROOT)}`

Fast eval: `{FAST_EVAL.relative_to(ROOT)}`

## Result

- Stage sequence: Stage656 bindings -> Stage657 compositions -> Stage658 full
- Target: `8.0` no-filter generalized answer KBPP
- No-filter exact/answer KBPP: `{summary['no_filter_exact_kbpp']}` / `{summary['no_filter_answer_kbpp']}`
- Delta vs Stage654 answer KBPP: `{summary['answer_kbpp_delta_vs_stage654']}`
- No-filter exact/answer accuracy: `{summary['no_filter_exact_accuracy']}` / `{summary['no_filter_answer_accuracy']}`

## Decision

Rejected as the 8-KBPP rung. Accepted as a diagnostic.

The important finding is that selectors alone are not the missing algorithm. The split must be balanced so every field/schema family is trained somewhere; eval should hold out bindings, entities, and compositions rather than entire schema families. Next: `stage659_balanced_generalized_8kbpp_surface`.
""",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
