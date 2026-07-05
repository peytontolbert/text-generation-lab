#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from model_output_packet_telemetry_contract_builder import AUTHORITY_CLOSED
from native_probe_preflight_gate import audit_preflight_rows

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8864
NAME = "stage8864_native_probe_preflight_gate"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "NATIVE_PROBE_PREFLIGHT_GATE_STAGE8864.md"
MANIFEST = OUT_DIR / "native_probe_preflight_plan.jsonl"


def build_rows() -> list[dict[str, object]]:
    return [
        {
            "probe_id": "stage8865_tiny_structured_policy_probe_candidate",
            "purpose": "First real tiny native structured probe candidate after Stage8862 telemetry gate recovery.",
            "mode": "structured_policy_probe",
            "objective_family": "intent_to_build_strategy",
            "source_manifest": "runs/local/artifacts/stage8630_intent_to_build_neutral_manifest/intent_to_build_neutral_manifest.jsonl",
            "output_dir": "runs/local/probes/stage8865_tiny_structured_policy_probe_candidate",
            "max_train_rows": 32,
            "max_eval_rows": 16,
            "max_strict_rows": 16,
            "max_steps": 8,
            "batch_size": 2,
            "max_encoder_tokens": 256,
            "max_decoder_tokens": 64,
            "implementation": "transformer",
            "loss_weights": {
                "decoder_ce_weight": 0.0,
                "structured_aux_weight": 1.0,
                "denoise_weight": 0.0,
            },
            "required_trainable_fields": [
                "build_mode",
                "allowed_import_policy",
                "blocked_import_policy",
                "repo_dependency_policy",
                "action_sequence",
                "file_plan",
            ],
            "post_run_artifact_gate": {
                "required": True,
                "script": "scripts/native_probe_interpretability_artifact_contract.py",
                "mode": "structured_aux_probe",
                "fail_if_missing_or_empty": True,
            },
            "required_interpretability_artifacts": [
                "row_field_logits.jsonl",
                "row_field_losses.jsonl",
                "row_gradient_norms.jsonl",
                "activation_summary.jsonl",
                "feature_ablation_attribution.jsonl",
                "activation_patch_recovery.jsonl",
                "row_dynamics_history.jsonl",
                "module_delta_norms.json",
                "field_exact_by_cell.json",
            ],
            "cleanup_policy": "safe_cleanup_checkpoints_only",
            "cleanup_forbidden_paths": ["/", "/data", "/arxiv", str(ROOT)],
            "execution_authorized_now": False,
            "authority": AUTHORITY_CLOSED,
        }
    ]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    MANIFEST.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    audit = audit_preflight_rows(rows, repo_root=ROOT)
    passed = audit["passed"]
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": passed,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            **audit,
            "execution_authorized_now": False,
            "model_training_authorized_now": False,
            "decoder_ce_authorized_now": False,
        },
        "artifacts": {
            "manifest": str(MANIFEST.relative_to(ROOT)),
            "audit_card": str((OUT_DIR / "native_probe_preflight_gate_card.json").relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Native probe preflight gate passed. This defines a candidate tiny structured probe but does not authorize execution." if passed else "Native probe preflight gate failed.",
        "next_best_step": "If explicitly authorized, run only the tiny Stage8865 structured-policy probe candidate and immediately audit its output with scripts/native_probe_interpretability_artifact_contract.py. Keep decoder CE closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "native_probe_preflight_gate_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8864 Native Probe Preflight Gate",
        "",
        f"Passed: `{passed}`",
        "",
        "This stage defines one candidate tiny structured native probe plan and audits that the plan remains closed-authority.",
        "",
        "## Candidate Probe",
        "",
        "- mode: `structured_policy_probe`",
        "- objective: `intent_to_build_strategy`",
        "- caps: train 32, eval 16, strict 16, steps 8",
        "- losses: structured aux only; decoder CE and denoise are `0.0`",
        "- output root: `runs/local/probes/...`",
        "- post-run gate: `scripts/native_probe_interpretability_artifact_contract.py --mode structured_aux_probe`",
        "",
        "## Boundary",
        "",
        "No model execution, decoder CE, denoise CE, runtime, Gemma, harness/scoring, source/body emission, controller merge, repository mining, or promotion is authorized by this stage.",
        "",
        "If the future Stage8865 probe is explicitly run, its output must pass the Stage8862 artifact contract before any metric can be trusted.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
