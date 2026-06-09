#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


PARAM_RUNGS = (
    1_000,
    7_600,
    10_000,
    16_280,
    23_369,
    25_852,
    100_000,
    1_000_000,
    10_000_000,
    100_000_000,
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_report() -> dict[str, Any]:
    manifest = load_json(ROOT / "runs/local/tmp/general_kbpp_pilot_v1/general_kbpp_pilot_manifest.json")
    oracle = load_json(ROOT / "runs/local/artifacts/general_kbpp_pilot_oracle_score_100m.json")
    total_bits = float(manifest["total_eval_verified_bits_available"])
    weighted_bits = float(oracle["total"]["weighted_verified_bits"])
    generalization_bits = float(oracle["generalization"]["verified_bits"])
    composition_bits = float(oracle["composition"]["verified_bits"])

    rungs = []
    for params in PARAM_RUNGS:
        params_f = float(params)
        ceiling_kbpp = total_bits / params_f
        ceiling_eid = weighted_bits / params_f
        if params <= 25_852:
            role = "informative_tiny_geometry_probe"
        elif params <= 1_000_000:
            role = "sanity_check_only_expand_before_claims"
        else:
            role = "underpowered_benchmark_requires_more_hidden_bits"
        rungs.append(
            {
                "params": params,
                "oracle_kbpp_ceiling": ceiling_kbpp,
                "oracle_generalization_kbpp_ceiling": generalization_bits / params_f,
                "oracle_composition_kbpp_ceiling": composition_bits / params_f,
                "oracle_eid_proxy_ceiling": ceiling_eid,
                "role": role,
            }
        )

    return {
        "artifact_kind": "general_kbpp_sweep_readiness",
        "pilot_manifest": "runs/local/tmp/general_kbpp_pilot_v1/general_kbpp_pilot_manifest.json",
        "oracle_score": "runs/local/artifacts/general_kbpp_pilot_oracle_score_100m.json",
        "hidden_eval_units": int(manifest["eval_units"]),
        "hidden_eval_bits": total_bits,
        "hidden_generalization_bits": generalization_bits,
        "hidden_composition_bits": composition_bits,
        "weighted_hidden_bits": weighted_bits,
        "param_rungs": rungs,
        "finding": (
            "The pilot is useful for validating scoring and tiny-rung representation geometry, "
            "but it is far too low-entropy for 10M-100M conclusions. A 100M model can only score "
            f"{total_bits / 100_000_000.0} KBPP at oracle on this pilot, so the benchmark must expand "
            "before it can test whether a 100M general model beats a modern 7B on useful intelligence density."
        ),
        "next_dataset_target": {
            "minimum_hidden_bits_for_100m_screen": 10_000_000,
            "reason": "A 100M model needs millions of hidden verified bits before KBPP differences are measurable above noise and formatting artifacts.",
            "required_growth_from_pilot": 10_000_000 / total_bits,
        },
    }


def write_doc(report: dict[str, Any]) -> None:
    rows = []
    for row in report["param_rungs"]:
        rows.append(
            f"- `{row['params']}` params: oracle KBPP `{row['oracle_kbpp_ceiling']}`, "
            f"generalization KBPP `{row['oracle_generalization_kbpp_ceiling']}`, "
            f"composition KBPP `{row['oracle_composition_kbpp_ceiling']}`; role `{row['role']}`"
        )
    doc = f"""# General KBPP Sweep Readiness

Artifact: `runs/local/artifacts/general_kbpp_sweep_readiness.json`

## Finding

{report['finding']}

## Pilot Entropy

- Hidden eval units: `{report['hidden_eval_units']}`
- Hidden eval bits: `{report['hidden_eval_bits']}`
- Hidden generalization bits: `{report['hidden_generalization_bits']}`
- Hidden composition bits: `{report['hidden_composition_bits']}`
- Depth-weighted hidden bits: `{report['weighted_hidden_bits']}`

## Parameter Rungs

{chr(10).join(rows)}

## Next Target

The next dataset target is at least `{report['next_dataset_target']['minimum_hidden_bits_for_100m_screen']}` hidden verified bits before using the benchmark to judge 100M-vs-7B density. That is a `{report['next_dataset_target']['required_growth_from_pilot']}`x increase over the current pilot.
"""
    (ROOT / "docs/general_kbpp_sweep_readiness.md").write_text(doc, encoding="utf-8")


def main() -> None:
    report = build_report()
    output = ROOT / "runs/local/artifacts/general_kbpp_sweep_readiness.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_doc(report)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
