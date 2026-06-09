#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FAST_EVAL = ROOT / "runs/local/artifacts/stage654_stage653_generalized_probe_fast_eval.json"
SURFACE = ROOT / "runs/local/artifacts/stage653_generalized_8kbpp_surface.json"
BUNDLE = ROOT / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage654_stage653_generalized_probe_lr1e6_steps40"
OUT = ROOT / "runs/local/artifacts/stage654_stage653_generalized_probe_summary.json"
DOC = ROOT / "docs/stage654_stage653_generalized_probe.md"
TARGET_KBPP = 8.0


def main() -> None:
    eval_result = json.loads(FAST_EVAL.read_text(encoding="utf-8"))
    surface = json.loads(SURFACE.read_text(encoding="utf-8"))
    total = eval_result["total"]
    families = eval_result["by_unit_family"]
    summary = {
        "artifact_kind": "stage654_stage653_generalized_probe_summary",
        "timestamp": int(time.time()),
        "bundle_dir": str(BUNDLE),
        "checkpoint": str(BUNDLE / "checkpoints/step_00000040.pt"),
        "surface_artifact": str(SURFACE),
        "dataset_manifest": "runs/local/tmp/stage653_generalized_8kbpp_surface/agentkernel_lite_encdec_dataset_manifest.json",
        "fast_eval": str(FAST_EVAL),
        "target_answer_kbpp": TARGET_KBPP,
        "surface_perfect_ceiling_kbpp": surface["perfect_ceiling_kbpp_at_16280_params"],
        "no_filter_exact_kbpp": eval_result["exact_kbpp"],
        "no_filter_answer_kbpp": eval_result["answer_kbpp"],
        "no_filter_exact_accuracy": total["exact_accuracy"],
        "no_filter_answer_accuracy": total["answer_accuracy"],
        "answer_verified_bits": total["answer_verified_bits"],
        "exact_verified_bits": total["exact_verified_bits"],
        "available_bits": total["available_bits"],
        "decision": "rejected_as_8kbpp_trained_rung_but_diagnostic",
        "finding": (
            "Stage653 has enough entropy, but a direct 40-step continuation from Stage651 does not learn the new "
            "generalized surface. Set-count answer recovery is high, while atomic facts, relations, two-hop "
            "compositions, and counterfactual negatives are near chance. The next stage needs a bridge curriculum "
            "and compact family-specific selectors, not only a larger entropy surface."
        ),
        "by_unit_family": families,
        "next_stage": {
            "label": "stage655_generalized_bridge_curriculum",
            "goal": "Convert Stage653 from a high-entropy surface into a learnable 8-KBPP rung.",
            "steps": [
                "Use a staged mix: train-visible atomic/relation bindings first, then hidden-field facts, then compositions/counterfactuals.",
                "Add compact selectors per family: domain|field|entity for facts, domain|relation|entity for relations, and domain|path|entity for compositions.",
                "Keep procedure/math/code families separate from entity memory so operation-gated contrast does not collapse answer-equivalent counts.",
                "Run 80-160 step initialized probes and accept only no-filter general KBPP >= 8.0.",
            ],
        },
    }
    OUT.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        f"""# Stage654 Stage653 Generalized Probe

Summary: `{OUT.relative_to(ROOT)}`

Bundle: `{BUNDLE.relative_to(ROOT)}`

Fast eval: `{FAST_EVAL.relative_to(ROOT)}`

## Result

- Surface perfect ceiling: `{summary['surface_perfect_ceiling_kbpp']}` generalized KBPP
- Target: `{TARGET_KBPP}` no-filter generalized answer KBPP
- No-filter exact/answer KBPP: `{summary['no_filter_exact_kbpp']}` / `{summary['no_filter_answer_kbpp']}`
- No-filter exact/answer accuracy: `{summary['no_filter_exact_accuracy']}` / `{summary['no_filter_answer_accuracy']}`
- Answer verified bits: `{summary['answer_verified_bits']}` of `{summary['available_bits']}`

## Family Read

| family | exact KBPP bits | answer bits | answer recovery |
|---|---:|---:|---:|
"""
        + "\n".join(
            f"| `{family}` | {stats['exact_verified_bits']} | {stats['answer_verified_bits']} | {stats['answer_bit_recovery']} |"
            for family, stats in families.items()
        )
        + """

## Decision

Rejected as a trained 8-KBPP rung. Accepted as a diagnostic.

The surface has enough verified entropy, but direct continuation does not transfer the Stage651 retrieval geometry to the generalized unit mix. The next step is `stage655_generalized_bridge_curriculum`: staged family exposure plus compact selectors for facts, relations, and compositions before another 8-KBPP acceptance run.
""",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
