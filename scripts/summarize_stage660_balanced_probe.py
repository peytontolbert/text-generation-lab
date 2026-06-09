#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FAST_EVAL = ROOT / "runs/local/artifacts/stage660_stage659_balanced_probe_fast_eval.json"
SURFACE = ROOT / "runs/local/artifacts/stage659_balanced_generalized_8kbpp_surface.json"
BUNDLE = ROOT / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage660_stage659_balanced_probe_lr1e6_steps80"
OUT = ROOT / "runs/local/artifacts/stage660_balanced_probe_summary.json"
DOC = ROOT / "docs/stage660_balanced_probe.md"


def main() -> None:
    result = json.loads(FAST_EVAL.read_text(encoding="utf-8"))
    surface = json.loads(SURFACE.read_text(encoding="utf-8"))
    summary = {
        "artifact_kind": "stage660_balanced_probe_summary",
        "timestamp": int(time.time()),
        "bundle_dir": str(BUNDLE),
        "checkpoint": str(BUNDLE / "checkpoints/step_00000080.pt"),
        "surface_artifact": str(SURFACE),
        "fast_eval": str(FAST_EVAL),
        "dataset_manifest": "runs/local/tmp/stage659_balanced_generalized_8kbpp_surface/agentkernel_lite_encdec_dataset_manifest.json",
        "surface_perfect_ceiling_kbpp": surface["perfect_ceiling_kbpp_at_16280_params"],
        "target_answer_kbpp": 8.0,
        "no_filter_exact_kbpp": result["exact_kbpp"],
        "no_filter_answer_kbpp": result["answer_kbpp"],
        "no_filter_exact_accuracy": result["total"]["exact_accuracy"],
        "no_filter_answer_accuracy": result["total"]["answer_accuracy"],
        "decision": "rejected_as_8kbpp_rung_balanced_split_not_sufficient",
        "finding": (
            "Balanced schema exposure lowers the entropy ceiling but does not improve the 16k trained gate. "
            "Atomic facts and relations remain near chance. The next algorithmic test should isolate binding "
            "acquisition on train-visible atomic/relation rows before attempting another broad generalized run."
        ),
        "by_unit_family": result["by_unit_family"],
        "next_stage": {
            "label": "stage661_atomic_binding_capacity_probe",
            "goal": "Test whether the 16k architecture can overfit/train-recover Stage659 atomic and relation bindings with compact selectors.",
            "acceptance": "High train and held-out seen-schema binding recovery before composition/counterfactual expansion.",
        },
    }
    OUT.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        f"""# Stage660 Balanced Probe

Summary: `{OUT.relative_to(ROOT)}`

Bundle: `{BUNDLE.relative_to(ROOT)}`

Fast eval: `{FAST_EVAL.relative_to(ROOT)}`

## Result

- Surface perfect ceiling: `{summary['surface_perfect_ceiling_kbpp']}` KBPP
- Target: `8.0` no-filter answer KBPP
- No-filter exact/answer KBPP: `{summary['no_filter_exact_kbpp']}` / `{summary['no_filter_answer_kbpp']}`
- No-filter exact/answer accuracy: `{summary['no_filter_exact_accuracy']}` / `{summary['no_filter_answer_accuracy']}`

## Decision

Rejected as the 8-KBPP rung. Balanced schema exposure alone is not sufficient.

The next algorithmic test should isolate binding capacity: train and evaluate atomic/relation bindings before adding composition, procedures, and counterfactual negatives.
""",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
