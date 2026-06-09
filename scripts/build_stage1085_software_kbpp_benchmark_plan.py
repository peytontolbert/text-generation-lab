#!/usr/bin/env python3
"""Build the Stage1085 software KBPP benchmark plan artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-json", type=Path, default=Path("runs/local/artifacts/stage1085_software_kbpp_benchmark_plan.json"))
    args = parser.parse_args()

    plan = {
        "artifact_kind": "stage1085_software_kbpp_benchmark_plan",
        "status": "completed_software_kbpp_benchmark_plan",
        "objective": "Define a verifier-first software benchmark path for testing whether a 100M KBPP/proof-expansion system can beat named modern 7B code models under the same context/tool budget.",
        "claim_boundary": {
            "allowed_claim": "100M plus counted proof-expansion interface beats named 7B code models on a defined hidden software verifier benchmark.",
            "disallowed_claim": "100M universally beats all possible 7B models or broad software intelligence without a fixed benchmark, frozen model list, and identical budget.",
            "required_counting": [
                "100M base model parameters",
                "all trainable proof-retrieval/comparator/router/value-head parameters",
                "declared fixed interface primitives",
                "context window and retrieved-token budget",
                "tool calls and verifier calls if available to only one system",
            ],
        },
        "verified_decision_units": {
            "bug_repair": [
                "failing test localized to function/file",
                "patch compiles",
                "hidden tests pass",
                "no regression tests fail",
            ],
            "api_binding": [
                "correct API symbol selected",
                "argument order/type correct",
                "exception behavior correct",
                "contract/invariant satisfied",
            ],
            "trace_debugging": [
                "stack frame/source span selected",
                "fault cause classified",
                "repair target selected",
                "runtime trace invariant restored",
            ],
            "repo_navigation": [
                "correct file",
                "correct symbol",
                "correct dependency/import edge",
                "correct test target",
            ],
            "generation": [
                "unit tests pass",
                "type checks pass",
                "edge-case tests pass",
                "format/interface constraints satisfied",
            ],
        },
        "training_data_recipe": {
            "synthetic_verified": {
                "minimum_tasks": 100000,
                "target_tasks": 1000000,
                "sources": [
                    "generated functions with hidden tests",
                    "bug injection and repair",
                    "API misuse generation",
                    "type-error repair",
                    "trace-to-fault localization",
                    "repo-symbol retrieval tasks",
                ],
                "purpose": "Teach reusable software binding/proof operators before using expensive real repositories.",
            },
            "real_verified": {
                "minimum_tasks": 10000,
                "target_tasks": 100000,
                "sources": [
                    "commit before/after pairs with tests",
                    "issue-to-patch examples",
                    "unit-test repair tasks",
                    "static-analysis warnings with accepted fixes",
                    "package API examples with executable tests",
                ],
                "leakage_gates": [
                    "repository holdout",
                    "package holdout",
                    "time split",
                    "test hidden from training",
                    "near-duplicate patch removal",
                ],
            },
        },
        "model_tracks": {
            "track_a_100m_direct": "100M model receives the same task context and must emit answer/patch directly.",
            "track_b_100m_counted_proof_expansion": "100M model plus counted proof retriever/comparator/value heads retrieves spans and emits constrained patch/action.",
            "track_c_7b_baselines": "Named 7B code models receive the same context/proof/tool budget and are scored by the same verifier.",
        },
        "minimum_benchmark_scale": {
            "pilot": {
                "hidden_tasks": 1000,
                "verified_decision_bits": 100000,
                "purpose": "Find instrumentation bugs and category imbalance.",
            },
            "controlled_claim": {
                "hidden_tasks": 10000,
                "verified_decision_bits": 1000000,
                "purpose": "Claim bounded software KBPP win against named 7B baselines if confidence intervals clear.",
            },
            "serious_claim": {
                "hidden_tasks": 100000,
                "verified_decision_bits": 10000000,
                "purpose": "Support broad software-KBPP density claim.",
            },
        },
        "acceptance_gates": [
            "100M counted proof-expansion track beats every named 7B baseline on aggregate verifier score.",
            "100M wins or ties core categories: bug repair, API binding, trace debugging, repo navigation, generation.",
            "95% confidence interval excludes baseline parity on aggregate score.",
            "No train/test repository, package, or hidden-test leakage.",
            "Direct 100M and proof-expanded 100M are reported separately.",
            "All failed/verifier-invalid outputs are counted as failures.",
        ],
        "next_stage": {
            "stage": "1086",
            "name": "software_kbpp_pilot_harness",
            "implementation": [
                "Create JSONL task schema for verified software decisions.",
                "Build synthetic function/unit-test tasks first.",
                "Add proof fields: relevant symbol, file span, API contract, trace frame, invariant.",
                "Implement verifier runner for unit tests/type checks as the score source.",
                "Add baseline hooks for 100M direct, 100M proof-expanded, and 7B prompt model.",
            ],
        },
        "decision": "Software is a viable external benchmark target because verifier-scored behavior gives dense, objective decision bits. The route must use verified tasks and counted proof expansion, not raw code perplexity.",
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(plan, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
