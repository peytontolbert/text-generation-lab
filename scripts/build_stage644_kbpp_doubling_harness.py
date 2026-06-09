#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PARAMS = 16280


STAGE643_EVAL = ROOT / "runs/local/tmp/recursive_kbpp_selector_stage643_entity_schema_probe/domain_field_entity_8df3558087/eval/retrieval_eval_full_corpus_operation_gated.json"
STAGE643_SUMMARY = ROOT / "runs/local/artifacts/stage643_entity_schema_probe_summary.json"
SEMANTIC_64_MANIFEST = ROOT / "runs/local/tmp/stage644_semantic_ops_64_domain_seed461_base/agentkernel_lite_encdec_dataset_manifest.json"
SEMANTIC_72_MANIFEST = ROOT / "runs/local/tmp/stage644_semantic_ops_72_domain_seed461_base/agentkernel_lite_encdec_dataset_manifest.json"
PILOT_MANIFESTS = [
    ROOT / f"runs/local/tmp/stage644_kbpp_doubling_probe_epd_{epd}/general_kbpp_pilot_manifest.json"
    for epd in (32, 64, 128, 256)
]
ARTIFACT = ROOT / "runs/local/artifacts/stage644_kbpp_doubling_harness.json"
DOC = ROOT / "docs/stage644_kbpp_doubling_harness.md"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def _semantic_ceiling(manifest_path: Path, domains: int) -> dict[str, Any]:
    manifest = _load_json(manifest_path)
    eval_rows = int(manifest["eval_examples"])
    bits_per_card = math.log2(eval_rows)
    ceiling_bits = eval_rows * bits_per_card
    return {
        "manifest": _rel(manifest_path),
        "domains": domains,
        "eval_rows": eval_rows,
        "train_rows": int(manifest["train_examples"]),
        "total_rows": int(manifest["total_examples"]),
        "bits_per_eval_card_choice": bits_per_card,
        "perfect_answer_ceiling_bits": ceiling_bits,
        "perfect_answer_ceiling_bits_per_param": ceiling_bits / PARAMS,
    }


def main() -> None:
    summary = _load_json(STAGE643_SUMMARY)
    stage643_eval = _load_json(STAGE643_EVAL)
    density = stage643_eval["verified_density"]
    token_stats = density["token_stats"]

    current_answer_bpp = float(summary["best_metrics"]["answer_bits_per_param"])
    current_exact_bpp = float(summary["best_metrics"]["exact_bits_per_param"])
    current_answer_bits = float(density["answer_verified_bits"])
    current_exact_bits = float(density["exact_verified_bits"])
    current_eval_rows = int(token_stats["eval_rows"])
    current_bits_per_card = float(token_stats["bits_per_eval_card_choice"])
    current_perfect_ceiling_bits = current_eval_rows * current_bits_per_card
    current_perfect_ceiling_bpp = current_perfect_ceiling_bits / PARAMS
    target_answer_bpp = current_answer_bpp * 2.0
    target_answer_bits = target_answer_bpp * PARAMS
    required_extra_ceiling_bits = target_answer_bits - current_perfect_ceiling_bits
    required_eval_rows_at_current_entropy = math.ceil(target_answer_bits / current_bits_per_card)

    pilot_surfaces = []
    for manifest_path in PILOT_MANIFESTS:
        if not manifest_path.exists():
            continue
        manifest = _load_json(manifest_path)
        pilot_surfaces.append(
            {
                "manifest": _rel(manifest_path),
                "eval_units": int(manifest["eval_units"]),
                "total_eval_verified_bits_available": float(manifest["total_eval_verified_bits_available"]),
                "perfect_bits_per_param": float(manifest["total_eval_verified_bits_available"]) / PARAMS,
            }
        )

    semantic_64 = _semantic_ceiling(SEMANTIC_64_MANIFEST, domains=64) if SEMANTIC_64_MANIFEST.exists() else None
    semantic_72 = _semantic_ceiling(SEMANTIC_72_MANIFEST, domains=72) if SEMANTIC_72_MANIFEST.exists() else None
    min_domains_for_target = math.ceil(64 * required_eval_rows_at_current_entropy / semantic_64["eval_rows"]) if semantic_64 else 72
    recommended_domains = max(72, min_domains_for_target)
    projected_eval_rows = math.floor(semantic_64["eval_rows"] * recommended_domains / 64) if semantic_64 else None
    projected_bits_per_card = math.log2(projected_eval_rows) if projected_eval_rows else None
    projected_ceiling_bits = projected_eval_rows * projected_bits_per_card if projected_eval_rows else None

    artifact = {
        "artifact_kind": "stage644_kbpp_doubling_harness",
        "timestamp": int(time.time()),
        "source_frontier": {
            "label": "stage643_entity_context_domain_field_entity_schema_probe",
            "summary": _rel(STAGE643_SUMMARY),
            "eval_json": _rel(STAGE643_EVAL),
            "params": PARAMS,
            "exact_bits": current_exact_bits,
            "answer_bits": current_answer_bits,
            "exact_bits_per_param": current_exact_bpp,
            "answer_bits_per_param": current_answer_bpp,
            "answer_top1": float(summary["best_metrics"]["answer_top1"]),
            "hard_filter_corrections": int(summary["best_metrics"]["hard_filter_corrections"]),
            "eval_rows": current_eval_rows,
            "bits_per_eval_card_choice": current_bits_per_card,
            "perfect_current_surface_answer_ceiling_bits": current_perfect_ceiling_bits,
            "perfect_current_surface_answer_ceiling_bits_per_param": current_perfect_ceiling_bpp,
        },
        "doubling_target": {
            "target_answer_bits_per_param": target_answer_bpp,
            "target_answer_bits": target_answer_bits,
            "current_surface_ceiling_gap_bits": required_extra_ceiling_bits,
            "current_surface_ceiling_multiplier_needed": target_answer_bits / current_perfect_ceiling_bits,
            "required_eval_rows_at_current_bits_per_card": required_eval_rows_at_current_entropy,
            "additional_eval_rows_at_current_bits_per_card": required_eval_rows_at_current_entropy - current_eval_rows,
        },
        "entropy_probe_results": {
            "general_kbpp_pilots": pilot_surfaces,
            "semantic_ops_64_domain_base": semantic_64,
            "semantic_ops_72_domain_base": semantic_72,
            "interpretation": "The general pilot is useful for broad intelligence taxonomy but is far below the entropy needed for a 2x 16k KBPP gate. The semantic-op surface is much closer because answer-card entropy scales with rows, but 64 domains still undershoots the full 2x target.",
        },
        "recommended_stage644_surface": {
            "generator": "legacy_src/scripts/build_pocketpal_stage430_semantic_ops.py",
            "domains": recommended_domains,
            "entities_per_domain": 10,
            "seed": 461,
            "eval_ratio": 0.12,
            "flags": {
                "reverse_lookup_mode": "set",
                "operation_token_prefix": 1,
                "reverse_lookup_key_prefix": 1,
                "compact_reverse_set_cards": 1,
                "direct_fact_key_prefix": 1,
                "false_claim_key_prefix": 1,
                "compact_false_claim_cards": 1,
                "extended_set_ops": 1,
                "compact_set_op_cards": 1,
                "factorized_direct_fact_cards": 1,
                "rule_key_prefix": 1,
                "composition_key_prefix": 1,
                "rule_set_ops": 1,
                "rule_case_intersection_ops": 1,
                "derived_set_ops": 1,
            },
            "projected_eval_rows": projected_eval_rows,
            "projected_perfect_answer_ceiling_bits": projected_ceiling_bits,
            "projected_perfect_answer_ceiling_bits_per_param": projected_ceiling_bits / PARAMS if projected_ceiling_bits else None,
            "materialized_manifest": _rel(SEMANTIC_72_MANIFEST) if semantic_72 else None,
            "materialized_eval_rows": semantic_72["eval_rows"] if semantic_72 else None,
            "materialized_perfect_answer_ceiling_bits": semantic_72["perfect_answer_ceiling_bits"] if semantic_72 else None,
            "materialized_perfect_answer_ceiling_bits_per_param": semantic_72["perfect_answer_ceiling_bits_per_param"] if semantic_72 else None,
            "required_canonicalization": [
                "Apply the Stage642/643 raw domain|field|entity selector to direct_fact and entity_context rows.",
                "Rebuild collision-conditioned keys and balance replay after the larger surface exists, not before.",
                "Keep deterministic key filtering as an evaluator ceiling only; do not train a learned hash sidepath.",
            ],
        },
        "acceptance_gates": [
            {
                "gate": "entropy",
                "criterion": "Perfect answer-card ceiling >= 2.0x Stage643 answer bits.",
                "threshold_bits": target_answer_bits,
            },
            {
                "gate": "learnability_probe",
                "criterion": "A 16k checkpoint should clear at least 1.10x Stage643 answer bpp on the expanded surface before long training.",
                "threshold_answer_bits_per_param": current_answer_bpp * 1.10,
            },
            {
                "gate": "recursive_compression",
                "criterion": "After selectors are canonicalized, remove redundant markers only when exact, answer, and hard-filter corrections hold.",
                "threshold": "no lower exact/answer bpp and no higher hard-filter corrections versus the previous accepted expanded-surface run",
            },
            {
                "gate": "doubling",
                "criterion": "Accepted only when a same-params model reaches >= 2.0x Stage643 answer bpp on verified held-out entropy.",
                "threshold_answer_bits_per_param": target_answer_bpp,
            },
        ],
        "finding": "We do not need a more agentic 100M route to double KBPP; we need a same-parameter entropy expansion where the verified target carries at least 51954.623 bits and the compact selector schema remains learnable. The next non-experimental route is an entropy-first Stage644 surface, then selector canonicalization, then residual-only training.",
    }

    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    doc = f"""# Stage644 KBPP Doubling Harness

Artifact: `{_rel(ARTIFACT)}`

## Result

Stage643 is near the ceiling of its current evaluation surface. It has `{current_answer_bpp}` answer bits/param, but a perfect model on the same surface can only reach `{current_perfect_ceiling_bpp}` answer bits/param. A true 2x run needs `{target_answer_bits}` verified answer bits, or `{target_answer_bpp}` answer bits/param at `{PARAMS}` params.

That requires about `{required_eval_rows_at_current_entropy}` eval rows at the current `{current_bits_per_card}` bits/card density. The current surface has `{current_eval_rows}` rows, so the missing ingredient is not another continuation; it is roughly another `{required_eval_rows_at_current_entropy - current_eval_rows}` independent held-out answer-card choices.

## Entropy Probes

- General KBPP pilot at 256 entities/domain exposes only `{pilot_surfaces[-1]['total_eval_verified_bits_available'] if pilot_surfaces else 'n/a'}` eval bits, or `{pilot_surfaces[-1]['perfect_bits_per_param'] if pilot_surfaces else 'n/a'}` perfect bits/param. It is useful as a broad taxonomy, but not dense enough for the 16k doubling gate.
- 64-domain semantic ops generated `{semantic_64['eval_rows'] if semantic_64 else 'n/a'}` eval rows and a perfect ceiling of `{semantic_64['perfect_answer_ceiling_bits_per_param'] if semantic_64 else 'n/a'}` bits/param. This is close but below the 2x target.
- The 72-domain base surface is materialized at `{_rel(SEMANTIC_72_MANIFEST) if semantic_72 else 'n/a'}` with `{semantic_72['eval_rows'] if semantic_72 else 'n/a'}` eval rows and `{semantic_72['perfect_answer_ceiling_bits_per_param'] if semantic_72 else 'n/a'}` perfect bits/param before selector/collision rewrites.

## Next Route

1. Build the `{recommended_domains}`-domain semantic-op surface with the Stage626-family compact flags.
2. Apply the proven `domain|field|entity` selector to `direct_fact` and `entity_context`.
3. Recreate collision-conditioned evaluation and balanced replay on the expanded surface.
4. Run a short 16k learnability probe; accept the route only if it clears `{current_answer_bpp * 1.10}` answer bits/param before long training.
5. Continue recursive compression only by evidence-gated deletion of redundant selectors.

## Interpretation

The doubling algorithm is now constrained: entropy expansion first, compact identity selectors second, residual-only gradient third, canonicalization last. Anything that only improves Stage643 by a few residual rows cannot materially increase knowledge bits per parameter because the current benchmark is already saturated.
"""
    DOC.parent.mkdir(parents=True, exist_ok=True)
    DOC.write_text(doc, encoding="utf-8")
    print(json.dumps({"artifact": _rel(ARTIFACT), "doc": _rel(DOC)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
