#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9396
NAME = "stage9396_training_loop_frontier_diagnosis_contract"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9395_bounded_decoder_short_suffix_generation_cap_probe_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "training_loop_frontier_diagnosis_contract.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAINING_LOOP_FRONTIER_DIAGNOSIS_CONTRACT_STAGE9396.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def update_registry(summary: dict) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_contract() -> dict:
    source = load_json(SOURCE_SUMMARY)
    metrics = source.get("metrics") if isinstance(source.get("metrics"), dict) else {}
    failures: list[str] = []
    if source.get("passed") is not False or metrics.get("safety_gate_passed") is not True:
        failures.append("source_stage9395_not_safe_failed_audit")
    if metrics.get("contentful_rate") != 1.0:
        failures.append("stage9395_contentful_not_fixed")
    if metrics.get("unterminated_rows") != 0:
        failures.append("stage9395_generation_cap_not_fixed")
    return {
        "passed": not failures,
        "failures": failures,
        "source_stage": 9395,
        "source_safety_gate_passed": metrics.get("safety_gate_passed"),
        "source_quality_gate_passed": metrics.get("quality_gate_passed"),
        "source_exact_match_rate": metrics.get("exact_match_rate"),
        "source_target_prefix_match_rate": metrics.get("target_prefix_match_rate"),
        "source_contentful_rate": metrics.get("contentful_rate"),
        "source_unterminated_rows": metrics.get("unterminated_rows"),
        "active_training_loop_mechanics": {
            "tokenization": "agentkernel_bytelevel_bpe_v1, vocab 1506, tokenizer hashlock required",
            "loss_masking": "row loss masks select denoise_ce only for current probes; decoder_ce remains closed",
            "post_prefix_loss_mask": "denoise probes mask prefix tokens and train only post-prefix suffix targets",
            "optimizer": "AdamW over model parameters with fixed tiny-probe learning rate",
            "gradient_clipping": "clip_grad_norm_ max_norm=1.0 and log pre/post clip norms",
            "evaluation": "eval and strict_eval run under no_grad with separate loss records",
            "generation_audit": "greedy generation with active prefix field, exact/prefix/boundary/contentful/short/repetition/leak checks",
            "telemetry": "row_token_loss, row_gradient_norms, row_dynamics_history, activation_summary, module_delta_norms",
            "checkpoint_safety": "no final checkpoint export, skip final model save, cleanup proof emitted",
        },
        "not_yet_scale_features": {
            "gradient_accumulation": "not required for tiny 23-row probes; add before large batches",
            "mixed_precision_bf16": "not required for current probe; add only behind determinism/NaN guards",
            "optimizer_param_groups": "current AdamW uses all params together; add no-decay groups before longer runs",
            "distributed_training": "not relevant until compiler produces scaled manifests",
            "checkpoint_resume": "disabled for safety probes; only reintroduce under safe checkpoint contract",
        },
        "stage9395_diagnosis": "Train rows overfit exactly after target resolver and generation-cap fixes, but eval/strict rows remain weak. The next blocker is heldout suffix support/generalization, not safety, EOS clipping, leaks, repetition, or decoder CE.",
        "next_patch_contract": {
            "objective": "heldout_contrastive_suffix_support_manifest",
            "must_keep_closed": ["decoder_ce", "runtime", "gemma", "harness", "source_body_emission", "promotion"],
            "required_rows": "add train support rows for failing eval/strict suffix families without copying heldout row IDs or exact target text into model input",
            "required_audits": [
                "target resolver surfaces all agree",
                "post-prefix suffix loss mask active",
                "train/eval/strict family coverage card",
                "single-template shortcut audit",
                "generation cap >= observed target token max plus EOS margin",
                "row_token_loss and boundary_next_token telemetry required",
            ],
            "pass_gate": "strict exact, prefix, boundary, contentful all 23/23 with short/junk/repetition/leak/unterminated rows all zero before rejoining bounded decoder repair",
        },
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    contract = build_contract()
    AUDIT.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": contract["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **contract},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Recorded the training-loop mechanics that explain Stage9395: safety and EOS/generation cap are fixed, train rows overfit, heldout suffix support remains the active blocker.",
        "next_best_step": "Build a heldout contrastive suffix-support manifest with family-balanced train support for eval/strict suffix failures; keep decoder CE closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9396 Training Loop Frontier Diagnosis Contract",
                "",
                "Stage9395 fixed the mechanics that were still ambiguous after Stage9393:",
                "",
                "- target resolver surfaces are repaired by Stage9391",
                "- generation cap is no longer clipping short byte/BPE targets",
                "- train rows overfit exactly",
                "- eval/strict rows still fail",
                "- leaks, repetition, short/junk, and unterminated output are zero",
                "",
                "## Active Training Mechanics",
                "",
                "- Tokenization: `agentkernel_bytelevel_bpe_v1`, vocab 1506, hashlock required.",
                "- Loss masking: current probes enable `denoise_ce` only; `decoder_ce` remains closed.",
                "- Post-prefix masking: denoise probes train only suffix tokens after `model_input.active_generation_prefix_span`.",
                "- Optimizer: AdamW with tiny-probe LR.",
                "- Gradients: `clip_grad_norm_(..., 1.0)` plus pre/post clip telemetry.",
                "- Evaluation: `eval` and `strict_eval` run under `no_grad` and emit split loss records.",
                "- Telemetry: `row_token_loss`, `row_gradient_norms`, `row_dynamics_history`, `activation_summary`, `module_delta_norms`, generation audits.",
                "- Checkpoint safety: no final checkpoint export, no final model save, cleanup proof emitted.",
                "",
                "## Not Yet Scale Features",
                "",
                "- Gradient accumulation is not required for tiny 23-row probes.",
                "- BF16/mixed precision should wait for determinism and NaN guards.",
                "- AdamW no-decay parameter groups should be added before longer runs.",
                "- Distributed/sharded training is out of scope until scaled manifests exist.",
                "- Checkpoint resume remains closed under the safety-probe contract.",
                "",
                "## Current Diagnosis",
                "",
                "Stage9395 shows the model can memorize the short-suffix train rows, but it does not generalize to eval/strict suffix families. The next data patch is heldout contrastive suffix support, not broader decoder CE.",
                "",
                "## Next Gate",
                "",
                "Before any rejoin or wider decoder work, the next probe must hit exact/prefix/boundary/contentful 23/23 with zero short/junk, repetition, leak, and unterminated rows.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "next": summary["next_best_step"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
