#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "runs" / "summaries" / "stage8640_full_pipeline_training_readiness_audit.json"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / "stage8640_full_pipeline_training_readiness_audit"
DOC = ROOT / "docs" / "FULL_PIPELINE_TRAINING_READINESS_AUDIT_STAGE8640.md"

AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}

CHECKS = {
    "control_plane": [
        "scripts/authority_gate.py",
        "scripts/loss_mask_card.py",
        "scripts/counterfactual_obligation_audit.py",
        "scripts/shortcut_baseline_audit.py",
        "scripts/safe_paths.py",
        "scripts/safe_cleanup.py",
    ],
    "judge_compiler": [
        "scripts/objective_row_judge.py",
        "scripts/structured_dataset_junk_ranker.py",
        "scripts/curriculum_compiler.py",
        "scripts/audit_curriculum_compiler_outputs.py",
    ],
    "model_path": [
        "legacy_src/agentkernel_lite/modeling_transformer.py",
        "configs/model/agentkernel_100m_seq2seq_recovered_target.json",
        "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json",
    ],
    "trainer_path": [
        "legacy_src/scripts/train_agentkernel_lite_encdec.py",
        "legacy_src/agentkernel_lite/training_loop.py",
        "legacy_src/agentkernel_lite/training_data.py",
    ],
    "objective_scripts": [
        "scripts/build_stage8630_intent_to_build_neutral_manifest.py",
        "scripts/build_stage8636_edit_localization_neutral_manifest.py",
        "scripts/build_stage8638_patch_operator_neutral_manifest.py",
        "scripts/audit_stage8639_patch_operator_shortcut_baseline.py",
    ],
}


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8") if (ROOT / path).is_file() else ""


def exists(path: str) -> bool:
    return (ROOT / path).is_file()


def help_text() -> str:
    trainer = ROOT / "legacy_src" / "scripts" / "train_agentkernel_lite_encdec.py"
    res = subprocess.run([sys.executable, str(trainer), "--help"], cwd=ROOT, text=True, capture_output=True, check=False)
    return res.stdout + res.stderr


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    h = help_text()
    trainer = read("legacy_src/scripts/train_agentkernel_lite_encdec.py")
    loop = read("legacy_src/agentkernel_lite/training_loop.py")
    data = read("legacy_src/agentkernel_lite/training_data.py")
    transformer = read("legacy_src/agentkernel_lite/modeling_transformer.py")

    file_presence = {group: {path: exists(path) for path in paths} for group, paths in CHECKS.items()}
    gates: dict[str, bool] = {
        "control_plane_files_present": all(file_presence["control_plane"].values()),
        "judge_compiler_files_present": all(file_presence["judge_compiler"].values()),
        "transformer_module_present": exists("legacy_src/agentkernel_lite/modeling_transformer.py"),
        "target_100m_config_present": exists("configs/model/agentkernel_100m_seq2seq_recovered_target.json"),
        "recovered_1506_tokenizer_pointer_present": exists("configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"),
        "trainer_has_implementation_selector": "--implementation" in h and "choices=(\"scaffold\", \"transformer\")" in trainer,
        "trainer_has_tokenizer_selector": "--tokenizer-json" in h and "--tokenizer-config" in h,
        "trainer_passes_implementation_to_loop": "implementation=args.implementation" in trainer,
        "trainer_passes_tokenizer_to_loop": "tokenizer_json=args.tokenizer_json" in trainer and "tokenizer_config=args.tokenizer_config" in trainer,
        "loop_has_transformer_runtime_path": "AgentKernelLiteTransformerSeq2Seq" in loop and "tiny_transformer_runtime_path" in loop,
        "loop_uses_selected_tokenizer": "load_tokenizer" in loop and "tokenizer=tokenizer" in loop,
        "batcher_has_bpe_wrapper": "class AgentKernelBPETokenizer" in data and "Tokenizer.from_file" in data,
        "transformer_has_rope": "RotaryEmbedding" in transformer and "apply_rotary" in transformer,
        "transformer_has_retrieval_heads": "retrieval_query_head" in transformer and "retrieval_doc_head" in transformer,
        "transformer_has_structured_heads": "structured_heads" in transformer and "DEFAULT_STRUCTURED_HEAD_DIMS" in transformer,
        "transformer_has_decoder_ce_loss": "def decoder_ce_loss" in transformer,
        "authority_closed": True,
    }

    blockers = []
    if not gates["trainer_has_tokenizer_selector"] or not gates["batcher_has_bpe_wrapper"]:
        blockers.append("1506 BPE tokenizer not fully selectable in trainer/batcher")
    # These are true blockers even after current recovery because they are not yet implemented as full-quality training paths.
    blockers.extend([
        "authorized runtime path is still tiny-probe scale, not full 100M target-config execution",
        "structured non-decoder probe execution loops are not implemented; only bounded decoder CE tiny loop exists",
        "generation quality telemetry is still placeholder until an explicitly authorized measured generation probe exists",
        "row-token CE telemetry records target metadata but not full per-token loss maps for every evaluated row",
        "full target BPE tokenizer is recovered as a pointer, but copied/materialized local tokenizer package and hash gate are not yet enforced by trainer",
        "stage8630/8636/8638 objective rows are reconstructed neutral manifests, not final mined data",
        "near-shortcut graph-topology counterbalancing still needs to be enforced before scaling graph objectives",
    ])

    ready_for_training = False
    card: dict[str, Any] = {
        "stage": 8640,
        "stage_name": "stage8640_full_pipeline_training_readiness_audit",
        "passed": all(gates.values()),
        "ready_for_100m_training": ready_for_training,
        "model_execution_authorized": False,
        "decoder_ce_training_authorized": False,
        "authority": AUTHORITY_CLOSED,
        "gates": gates,
        "file_presence": file_presence,
        "blockers_before_training": blockers,
        "recovered_now": [
            "safe trainer command surface with implementation selector",
            "tiny recovered-transformer runtime path behind explicit execution gate",
            "1506-vocab AgentKernel BPE tokenizer pointer and trainer selection flags",
            "dataset judge/curriculum compiler/loss-mask/counterfactual contracts",
            "intent-to-build, edit-localization, and patch-operator neutral structured objective builders",
        ],
        "do_not_do_next": [
            "do not recover/mine data yet",
            "do not run decoder CE training",
            "do not run model execution without a new explicit authorization stage",
            "do not open runtime/source/body/Gemma/harness/scoring",
        ],
        "next_best_step": "Patch the trainer/runtime audits to enforce recovered tokenizer hash, full target-config compatibility, structured probe execution modes, and real telemetry requirements before any data recovery or mining.",
    }
    (OUT_DIR / "pipeline_readiness_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Stage8640 Full Pipeline Training Readiness Audit",
        "",
        "This is a recovery audit only. It does not authorize model execution, decoder CE training, runtime, source/body emission, Gemma, harness/scoring, controller merge, or promotion.",
        "",
        "## Verdict",
        "",
        f"- audit passed: `{card['passed']}`",
        f"- ready for 100M training: `{card['ready_for_100m_training']}`",
        "- authority: all closed",
        "",
        "## Recovered",
        "",
    ]
    lines += [f"- {item}" for item in card["recovered_now"]]
    lines += ["", "## Blockers Before Training", ""]
    lines += [f"- {item}" for item in blockers]
    lines += ["", "## Gates", ""]
    lines += [f"- `{key}`: `{value}`" for key, value in sorted(gates.items())]
    lines += ["", "## Next", "", card["next_best_step"], ""]
    DOC.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
