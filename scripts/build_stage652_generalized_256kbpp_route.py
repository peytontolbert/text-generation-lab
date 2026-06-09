#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PARAMS_16K = 16280
PARAMS_100M = 100_000_000
CURRENT_STAGE = "stage651_rank3_residual"
CURRENT_KBPP = 3.798421037978204
TARGET_KBPP = 256.0
OUT = ROOT / "runs/local/artifacts/stage652_generalized_256kbpp_route.json"
DOC = ROOT / "docs/stage652_generalized_256kbpp_route.md"


def rows_for_bits(bits: float) -> int:
    if bits <= 0:
        return 0
    lo, hi = 2, 2
    while hi * math.log2(hi) < bits:
        hi *= 2
    while lo < hi:
        mid = (lo + hi) // 2
        if mid * math.log2(mid) >= bits:
            hi = mid
        else:
            lo = mid + 1
    return lo


def rung(target_kbpp: float) -> dict[str, float | int | str]:
    bits_16k = target_kbpp * PARAMS_16K
    rows = rows_for_bits(bits_16k)
    return {
        "target_kbpp": target_kbpp,
        "verified_bits_at_16280_params": bits_16k,
        "approx_unique_eval_units_if_flat_answer_cards": rows,
        "flat_answer_card_bits": rows * math.log2(rows),
        "verified_bits_at_100m_params": target_kbpp * PARAMS_100M,
    }


def main() -> None:
    targets = [8, 16, 32, 64, 128, 256]
    ladder = [rung(float(target)) for target in targets]
    doublings_needed = math.log2(TARGET_KBPP / CURRENT_KBPP)
    artifact = {
        "artifact_kind": "stage652_generalized_256kbpp_route",
        "timestamp": int(time.time()),
        "current_frontier": {
            "label": CURRENT_STAGE,
            "kbpp": CURRENT_KBPP,
            "source": "runs/local/artifacts/stage651_rank3_residual_summary.json",
        },
        "target": {
            "kbpp": TARGET_KBPP,
            "multiplier_needed": TARGET_KBPP / CURRENT_KBPP,
            "doublings_needed": doublings_needed,
            "practical_doubling_rounds": math.ceil(doublings_needed),
            "verified_bits_at_16280_params": TARGET_KBPP * PARAMS_16K,
            "verified_bits_at_100m_params": TARGET_KBPP * PARAMS_100M,
        },
        "ladder": ladder,
        "generalized_kbpp_unit_mix": [
            {
                "unit_family": "atomic_facts",
                "role": "base recoverable knowledge; must include held-out entities and fields",
                "acceptance": "answer/exact bpp improves without singleton exact-key solving",
            },
            {
                "unit_family": "relations_and_sets",
                "role": "inverse lookup, membership, counts, joins, and typed relation edges",
                "acceptance": "set/member/count equivalence handled without inflating answer-only scores",
            },
            {
                "unit_family": "multi_hop_compositions",
                "role": "depth-2 to depth-4 transformations with distractors",
                "acceptance": "held-out path templates must remain above the rung threshold",
            },
            {
                "unit_family": "procedures",
                "role": "small executable rules, parsing, transforms, and deterministic algorithms",
                "acceptance": "held-out parameters and held-out procedure combinations pass",
            },
            {
                "unit_family": "abstractions",
                "role": "schema reuse, default/exception reuse, class rules, and reusable latent programs",
                "acceptance": "verified bits gained per trained primitive increases across domains",
            },
            {
                "unit_family": "counterfactual_and_negative_knowledge",
                "role": "false-claim rejection, near-neighbor discrimination, and impossible-state filtering",
                "acceptance": "near-negative robustness improves without broad exact-regression",
            },
        ],
        "recursive_algorithm": [
            "Measure current no-filter KBPP and perfect surface ceiling.",
            "If perfect ceiling < 2x current KBPP, expand generalized verified entropy first.",
            "Serialize compact binding identities as minimal selectors, not learned hash sidepaths.",
            "Collision-condition deterministic keys so filters narrow candidate sets but do not solve the row.",
            "Train initialized tiny retrieval geometry first; scratch runs require a separate warmup schedule.",
            "Mine train-side rank-2/3 residuals; replay only operation-local near misses.",
            "Accept a doubling only when no-filter held-out generalized KBPP clears the target.",
            "Run the 1k-100M sweep after each accepted generalized rung to map density knees.",
        ],
        "hard_rules": [
            "Hard-filter-only gains do not count as neural KBPP.",
            "Answer-only gains from binary/count equivalence must be tracked separately from exact-card gains.",
            "Do not claim 100M beats 7B until the 100M model beats a measured 7B baseline on the same generalized scorer.",
            "Each rung must include held-out entities, held-out schemas, and held-out compositions.",
        ],
        "next_stage": {
            "label": "stage653_generalized_8kbpp_surface",
            "goal": "Build the first generalized rung above Stage651 with enough ceiling for 8 no-filter KBPP at 16k.",
            "minimum_verified_bits_at_16k": 8 * PARAMS_16K,
            "approx_flat_eval_units": rows_for_bits(8 * PARAMS_16K),
            "required_change": "Replace the current mostly answer-card expansion with a generalized unit mix containing facts, relations, compositions, procedures, abstractions, and counterfactual negatives.",
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.parent.mkdir(parents=True, exist_ok=True)
    DOC.write_text(
        f"""# Stage652 Generalized 256 KBPP Route

Artifact: `runs/local/artifacts/stage652_generalized_256kbpp_route.json`

## Target

Current frontier: `{CURRENT_STAGE}` at `{CURRENT_KBPP}` no-filter answer KBPP.

Target: `{TARGET_KBPP}` generalized no-filter KBPP.

- Multiplier needed: `{TARGET_KBPP / CURRENT_KBPP}`
- Practical doubling rounds: `{math.ceil(doublings_needed)}`
- 16k verified bits at target: `{TARGET_KBPP * PARAMS_16K}`
- 100M verified bits at target: `{TARGET_KBPP * PARAMS_100M}`

## Ladder

| Target KBPP | 16k verified bits | Approx flat eval units | 100M verified bits |
|---:|---:|---:|---:|
"""
        + "\n".join(
            f"| {row['target_kbpp']:.0f} | {row['verified_bits_at_16280_params']:.0f} | {row['approx_unique_eval_units_if_flat_answer_cards']} | {row['verified_bits_at_100m_params']:.0f} |"
            for row in ladder
        )
        + f"""

## Algorithm

1. Measure current no-filter KBPP and surface ceiling.
2. Expand generalized entropy before training if the ceiling cannot support the next 2x.
3. Use compact selectors for binding identity.
4. Collision-condition deterministic keys so filters do not solve the task alone.
5. Train initialized tiny retrieval geometry.
6. Mine train-side rank-2/3 residuals and replay only local near misses.
7. Accept only no-filter held-out generalized KBPP.
8. Sweep 1k through 100M after every accepted rung.

## Next Stage

`stage653_generalized_8kbpp_surface`

Minimum 16k verified bits: `{8 * PARAMS_16K}`.

Approx flat eval units: `{rows_for_bits(8 * PARAMS_16K)}`.

The next surface must mix facts, relations, compositions, procedures, abstractions, and counterfactual negatives. It should not be a larger lookup-only answer-card set.
""",
        encoding="utf-8",
    )
    print(json.dumps({"artifact": str(OUT), "doc": str(DOC)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
