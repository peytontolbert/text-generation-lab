#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JSON_OUT = ROOT / "runs/local/artifacts/stage758_100m_factorized_binding_route.json"
DOC_OUT = ROOT / "docs/stage758_100m_factorized_binding_route.md"


STAGE_METRICS = {
    "stage749_64_answer_kbpp": 101.71841710448409,
    "stage749_64_exact_kbpp": 99.64035351034333,
    "stage750_128_answer_kbpp": 130.74282974483415,
    "stage750_128_exact_kbpp": 127.92777674971687,
    "stage754_1792_answer_kbpp": 227.15636741430188,
    "stage755_2048_answer_kbpp": 249.03219259543124,
    "stage756_2048_answer_kbpp": 249.3560488610709,
    "stage759_2048_answer_kbpp": 372.46443714113553,
    "stage759_2048_exact_kbpp": 365.7994972816619,
    "stage755_ceiling_kbpp": 381.7782355888606,
    "stage757_ceiling_kbpp": 405.619821560921,
    "tiny_parameter_count": 16794.0,
}


def build() -> dict:
    target_100m_bits = {
        "kbpp_256": 256 * 100_000_000,
        "kbpp_512": 512 * 100_000_000,
        "kbpp_1024": 1024 * 100_000_000,
    }
    current_100m_projection = {
        "stage749_64_density_bits_at_100m": STAGE_METRICS["stage749_64_answer_kbpp"] * 100_000_000,
        "stage750_128_density_bits_at_100m": STAGE_METRICS["stage750_128_answer_kbpp"] * 100_000_000,
        "stage756_2048_density_bits_at_100m": STAGE_METRICS["stage756_2048_answer_kbpp"] * 100_000_000,
        "stage759_2048_density_bits_at_100m": STAGE_METRICS["stage759_2048_answer_kbpp"] * 100_000_000,
        "stage757_ceiling_bits_at_100m": STAGE_METRICS["stage757_ceiling_kbpp"] * 100_000_000,
    }
    route = {
        "artifact_kind": "stage758_100m_factorized_binding_route",
        "scope": "Wrap the generalized KBPP factor algorithm around a 100M model while preserving qidless, no-answer-leakage gates.",
        "current_status": {
            "accepted_64_answer_exact": True,
            "accepted_128_answer": True,
            "accepted_256_answer": True,
            "accepted_256_exact": True,
            "best_completed_answer_kbpp": STAGE_METRICS["stage759_2048_answer_kbpp"],
            "best_completed_exact_kbpp": STAGE_METRICS["stage759_2048_exact_kbpp"],
            "best_completed_factor_mode": "text_multi_axis_nonanswer_entity_pair",
            "current_blocker": "The 256 answer/exact gate is closed on the stable 2048-domain surface. The next 16k gate is 512 KBPP before a real 100M short-probe budget.",
        },
        "100m_dry_run_validation": {
            "status": "passed",
            "artifact": "runs/local/artifacts/stage758_100m_factorized_binding_dry_run/agentkernel_lite_encdec_manifest.json",
            "parameter_count": 101463808,
            "preset": "100m",
            "factor_mode": "text_multi_axis_nonanswer_entity_pair",
            "factor_weight": 4.0,
            "dataset_manifest": "runs/local/tmp/stage751_generalized_256kbpp_collision_surface_d1792/agentkernel_lite_encdec_dataset_manifest.json",
            "note": "Dry run validates architecture/config compatibility only; it does not train or prove 100M KBPP.",
        },
        "target_bits_at_100m": target_100m_bits,
        "density_projection_at_100m": current_100m_projection,
        "algorithm_components": [
            {
                "name": "qidless held-out alias surfaces",
                "requirement": "No qid text, held-out eval entity aliases, and collision selectors remain mandatory.",
            },
            {
                "name": "compositional binding ids",
                "requirement": "Use semantic axes and non-answer entities only: no answer value, no row id, no full qid.",
                "current_mode": "text_multi_axis_nonanswer_entity_pair",
            },
            {
                "name": "factorized binding head",
                "requirement": "Move the factor from post-hoc scoring into a trainable auxiliary head for 100M, with the same ids used at eval.",
            },
            {
                "name": "verified-bit training curriculum",
                "requirement": "Sample and weight examples by recoverable verified bits, residual collision groups, and held-out family gaps.",
            },
            {
                "name": "general path distillation",
                "requirement": "The final 100M must answer through its normal text path; the binding head can train and rerank but cannot be the only oracle.",
            },
        ],
        "100m_training_phases": [
            {
                "phase": "phase0_16k_gate_close",
                "goal": "Scale and profile the accepted multi-axis factor toward the 512 KBPP rung on the 16k microscope.",
                "gate": "answer_kbpp >= 512 on qidless held-out alias collision eval, or a stable ceiling is documented.",
            },
            {
                "phase": "phase1_100m_dry_run",
                "goal": "Verify the 100M architecture, tokenizer, and factorized binding ids compile and produce a manifest without training.",
                "gate": "dry-run bundle has correct factor mode and parameter count near 100M.",
            },
            {
                "phase": "phase2_100m_short_probe",
                "goal": "Run 100M for a short fixed budget on the 128/256 surfaces.",
                "gate": "100M answer KBPP exceeds the 16k density curve after parameter normalization and does not rely on qid/answer leakage.",
            },
            {
                "phase": "phase3_7b_baseline",
                "goal": "Score a representative 7B on the same verified-bit benchmark.",
                "gate": "100M projected KBPP exceeds measured 7B useful KBPP with margin.",
            },
            {
                "phase": "phase4_1024_route",
                "goal": "Scale surface entropy and factor recovery until 1024 KBPP is reached or a stable ceiling is mapped.",
                "gate": "1024 answer KBPP = 102.4B verified bits at 100M.",
            },
        ],
        "command_templates": {
            "100m_dry_run": [
                "/home/peyton/miniconda3/envs/ai/bin/python",
                "legacy_src/scripts/train_agentkernel_lite_encdec.py",
                "--dataset-manifest",
                "runs/local/tmp/stage751_generalized_256kbpp_collision_surface_d1792/agentkernel_lite_encdec_dataset_manifest.json",
                "--output-dir",
                "runs/local/artifacts/stage758_100m_factorized_binding_dry_run",
                "--preset",
                "100m",
                "--tokenizer-kind",
                "agentkernel-bpe",
                "--max-steps",
                "1",
                "--batch-size",
                "8",
                "--eval-every",
                "0",
                "--device",
                "cpu",
                "--dry-run",
                "1",
                "--decoder-loss-weight",
                "0",
                "--retrieval-factorized-contrastive-weight",
                "1.0",
                "--retrieval-factor-score-weight",
                "4.0",
                "--retrieval-factor-key-hash-mode",
                "text_multi_axis_nonanswer_entity_pair",
                "--retrieval-factor-key-hash-buckets",
                "32",
                "--retrieval-factor-key-hash-slots",
                "8",
            ],
            "100m_short_probe": [
                "/home/peyton/miniconda3/envs/ai/bin/python",
                "legacy_src/scripts/train_agentkernel_lite_encdec.py",
                "--dataset-manifest",
                "runs/local/tmp/stage751_generalized_256kbpp_collision_surface_d1792/agentkernel_lite_encdec_dataset_manifest.json",
                "--output-dir",
                "runs/local/artifacts/stage758_100m_factorized_binding_short_probe",
                "--preset",
                "100m",
                "--max-steps",
                "200",
                "--batch-size",
                "8",
                "--eval-every",
                "0",
                "--device",
                "cuda",
                "--dry-run",
                "0",
                "--decoder-loss-weight",
                "0",
                "--retrieval-factorized-contrastive-weight",
                "1.0",
                "--retrieval-factor-score-weight",
                "4.0",
                "--retrieval-factor-key-hash-mode",
                "text_multi_axis_nonanswer_entity_pair",
                "--retrieval-factor-key-hash-buckets",
                "32",
                "--retrieval-factor-key-hash-slots",
                "8",
            ],
            "strict_eval": [
                "/home/peyton/miniconda3/envs/ai/bin/python",
                "scripts/evaluate_retrieval_factor_grid_fast.py",
                "--bundle-dir",
                "runs/local/artifacts/stage758_100m_factorized_binding_short_probe",
                "--dataset-manifest",
                "runs/local/tmp/stage751_generalized_256kbpp_collision_surface_d1792/agentkernel_lite_encdec_dataset_manifest.json",
                "--device",
                "cuda",
                "--batch-size",
                "512",
                "--key-factor-modes",
                "text_multi_axis_nonanswer_entity_pair",
                "--key-factor-weights",
                "4.0",
                "--output-json",
                "runs/local/artifacts/stage758_100m_factorized_binding_short_probe_eval.json",
            ],
        },
        "non_negotiable_acceptance_rules": [
            "No qid tokens in eval text.",
            "No answer value included in factor ids.",
            "Eval entities must remain held-out aliases.",
            "Collision selectors must remain non-singleton enough that full key lookup cannot explain the score.",
            "7B comparison must use the same verified-bit scorer.",
        ],
        "next_local_action": "Build a stable 512-rung surface and evaluate text_multi_axis_nonanswer_entity_pair before running a real 100M short probe.",
    }
    return route


def write_doc(route: dict) -> None:
    lines = [
        "# Stage758 100M Factorized Binding Route",
        "",
        "This route wraps the current generalized KBPP algorithm around a 100M model without relaxing the qidless, no-answer-leakage, held-out alias gates.",
        "",
        "## Current State",
        "",
        f"- Best completed 16k answer KBPP: `{route['current_status']['best_completed_answer_kbpp']}`",
        f"- Best completed 16k exact KBPP: `{route['current_status']['best_completed_exact_kbpp']}`",
        f"- Current factor mode: `{route['current_status']['best_completed_factor_mode']}`",
        f"- 256 status: `{route['current_status']['accepted_256_answer']}`",
        f"- Blocker: {route['current_status']['current_blocker']}",
        "",
        "## 100M Dry Run",
        "",
        f"- Status: `{route['100m_dry_run_validation']['status']}`",
        f"- Parameter count: `{route['100m_dry_run_validation']['parameter_count']}`",
        f"- Factor mode: `{route['100m_dry_run_validation']['factor_mode']}`",
        f"- Artifact: `{route['100m_dry_run_validation']['artifact']}`",
        f"- Note: {route['100m_dry_run_validation']['note']}",
        "",
        "## 100M Targets",
        "",
    ]
    for name, value in route["target_bits_at_100m"].items():
        lines.append(f"- `{name}`: `{value}` verified bits")
    lines.extend(["", "## Algorithm Components", ""])
    for item in route["algorithm_components"]:
        lines.append(f"- `{item['name']}`: {item['requirement']}")
    lines.extend(["", "## Training Phases", ""])
    for phase in route["100m_training_phases"]:
        lines.append(f"- `{phase['phase']}`: {phase['goal']} Gate: {phase['gate']}")
    lines.extend(["", "## Command Templates", ""])
    for name, command in route["command_templates"].items():
        lines.append(f"### {name}")
        lines.append("")
        lines.append("```bash")
        lines.append(" ".join(command))
        lines.append("```")
        lines.append("")
    lines.extend(["## Acceptance Rules", ""])
    for rule in route["non_negotiable_acceptance_rules"]:
        lines.append(f"- {rule}")
    lines.extend(["", "## Next Local Action", "", route["next_local_action"], ""])
    DOC_OUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    route = build()
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    DOC_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(route, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_doc(route)
    print(json.dumps({"json": str(JSON_OUT), "doc": str(DOC_OUT)}, indent=2))


if __name__ == "__main__":
    main()
