#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11639
NAME = "stage11639_normalized_web_support_guarded_probe_request"
OUT = ART / NAME
SUMMARY = OUT / "normalized_web_support_guarded_probe_request.json"
MANIFEST = OUT / "normalized_web_support_guarded_probe_manifest.jsonl"
COMMAND = OUT / "normalized_web_support_guarded_probe_command.json"
TRAIN_ROWS_OUT = OUT / "normalized_web_support_train_rows.jsonl"

TRAIN_ROWS = ART / "stage11638_web_support_schema_normalization/web_support_normalized_admitted_train_rows.jsonl"
FILTERED_VALIDATION = ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_validation.jsonl"
FILTERED_STRICT = ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
OLD_VALIDATION = ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_validation.jsonl"
OLD_STRICT = ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
RESIDUAL_BANK = ART / "stage11442_targeted_residual_role_support_package/semantic_candidate_residual_bank.jsonl"
WEB_HELDOUT = ART / "stage11548_web_root_heldout_stage11507_score_audit/web_root_heldout_rows.jsonl"
INIT_RUNTIME = ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"
PROBE = ART / "stage11639_normalized_web_support_guarded_probe/bounded_decoder_probe"
RUNTIME_OUT = ART / "stage11639_normalized_web_support_guarded_probe/runtime_model"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def row_root(row: dict[str, Any]) -> str:
    return str(row.get("root_lineage_key") or row.get("root_id") or row.get("source_root_id") or row.get("row_id"))


def roots(rows: list[dict[str, Any]]) -> set[str]:
    return {row_root(row) for row in rows}


def options(row: dict[str, Any]) -> list[dict[str, Any]]:
    return list((row.get("standalone_projection_source") or {}).get("opaque_options") or row.get("opaque_options") or [])


def normalize(row: dict[str, Any], split: str, *, train: bool = False) -> dict[str, Any]:
    out = dict(row)
    out["split"] = split
    out.setdefault("prompt_text", out.get("input_text") or out.get("prompt") or "")
    out.setdefault("input_text", out.get("prompt_text") or "")
    out.setdefault("bounded_choice_target_label", out.get("target_text"))
    out.setdefault("decoder_text", out.get("target_text") or out.get("bounded_choice_target_label") or "")
    src = dict(out.get("standalone_projection_source") or {})
    src.setdefault("opaque_options", out.get("opaque_options") or [])
    out["standalone_projection_source"] = src
    out["opaque_options"] = src["opaque_options"]
    out["loss_mask"] = {"decoder_ce": True, "bounded_choice_aux": True}
    out["expected_enabled_loss"] = "decoder_ce+bounded_choice_aux+bounded_choice_contrast" if train else "decoder_ce+bounded_choice_aux"
    out["target"] = {
        "decoder_text": out.get("decoder_text"),
        "bounded_choice_target_label": out.get("bounded_choice_target_label") or out.get("target_text"),
        "semantic_value": out.get("semantic_target_value") or out.get("target_semantic_value"),
    }
    return out


def main() -> None:
    train = [normalize(row, "train", train=True) for row in load_jsonl(TRAIN_ROWS)]
    validation = [normalize(row, "eval") for row in load_jsonl(FILTERED_VALIDATION)]
    strict = [normalize(row, "strict_eval") for row in load_jsonl(FILTERED_STRICT)]
    old_validation = load_jsonl(OLD_VALIDATION)
    old_strict = load_jsonl(OLD_STRICT)
    residual = load_jsonl(RESIDUAL_BANK)
    web_heldout = load_jsonl(WEB_HELDOUT)
    manifest = train + validation + strict
    overlaps = {
        "train_vs_filtered_validation": sorted(roots(train) & roots(validation)),
        "train_vs_filtered_strict": sorted(roots(train) & roots(strict)),
        "train_vs_old_validation": sorted(roots(train) & roots(old_validation)),
        "train_vs_old_strict": sorted(roots(train) & roots(old_strict)),
        "train_vs_residual": sorted(roots(train) & roots(residual)),
        "train_vs_web_heldout": sorted(roots(train) & roots(web_heldout)),
    }
    command = [
        "env",
        "CUDA_VISIBLE_DEVICES=2",
        "NVIDIA_VISIBLE_DEVICES=2",
        "AGENTKERNEL_EVAL_DEVICE=cuda:0",
        "PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True",
        "TMPDIR=/data/tmp",
        "TEMP=/data/tmp",
        "TMP=/data/tmp",
        "conda",
        "run",
        "-n",
        "trellis",
        "python",
        str(ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"),
        "--repo-root",
        str(ROOT),
        "--manifest",
        str(MANIFEST),
        "--mode",
        "bounded_decoder_ce_probe",
        "--probe-scale",
        "target_100m",
        "--implementation",
        "transformer",
        "--model-config",
        str(ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"),
        "--tokenizer-json",
        str(ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"),
        "--tokenizer-config",
        str(ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"),
        "--tokenizer-hashlock",
        str(ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"),
        "--execution-authorized-for-recovery-probe",
        "--max-train-rows",
        str(len(train)),
        "--max-eval-rows",
        str(len(validation)),
        "--max-strict-rows",
        str(len(strict)),
        "--max-steps",
        "256",
        "--batch-size",
        "8",
        "--learning-rate",
        "2e-7",
        "--max-encoder-tokens",
        "768",
        "--max-decoder-tokens",
        "16",
        "--decoder-ce-weight",
        "0.04",
        "--bounded-choice-aux-weight",
        "3.0",
        "--bounded-choice-aux-source",
        "encoder_option_retrieval_web_task_candidate_head",
        "--bounded-decoder-train-sampler",
        "web_task_family_balanced",
        "--bounded-choice-contrast-weight",
        "0.5",
        "--bounded-choice-contrast-margin",
        "0.08",
        "--structured-aux-weight",
        "0.0",
        "--denoise-weight",
        "0.0",
        "--eos-loss-weight",
        "4.0",
        "--enable-generation-audit",
        "--max-generation-rows",
        "8",
        "--max-generation-tokens",
        "16",
        "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness",
        "--runtime-model-save-dir",
        str(RUNTIME_OUT),
        "--initialize-from-runtime-model",
        str(INIT_RUNTIME),
        "--preservation-reference-runtime-model",
        str(INIT_RUNTIME),
        "--preservation-kl-weight",
        "10.0",
        "--no-final-checkpoint-export",
        "--output-dir",
        str(PROBE),
    ]
    gates = {
        "train_rows_at_least_200": len(train) >= 200,
        "train_roots_at_least_30": len(roots(train)) >= 30,
        "has_pass_to_pass_and_fail_to_pass": {"PASS_TO_PASS", "FAIL_TO_PASS"}.issubset({str(row.get("observed_verifier_transition")) for row in train}),
        "has_openhands_and_llama": {"openhands_openhands_frontend", "llama_stack_ui"}.issubset({str(row.get("repo_family")) for row in train}),
        "all_train_rows_have_options": all(len(options(row)) >= 3 for row in train),
        "no_root_overlap_with_protected_or_web_heldout": all(not vals for vals in overlaps.values()),
        "gpu2_mask_present": "CUDA_VISIBLE_DEVICES=2" in command and "NVIDIA_VISIBLE_DEVICES=2" in command,
        "task_aware_sampler_present": "web_task_family_balanced" in command,
        "contrast_enabled": "--bounded-choice-contrast-weight" in command and command[command.index("--bounded-choice-contrast-weight") + 1] != "0.0",
        "high_preservation_kl": "--preservation-kl-weight" in command and float(command[command.index("--preservation-kl-weight") + 1]) >= 10.0,
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "normalized_web_support_guarded_probe_ready" if all(gates.values()) else "normalized_web_support_guarded_probe_blocked",
        "gates": gates,
        "metrics": {
            "train_rows": len(train),
            "train_roots": len(roots(train)),
            "train_by_source": dict(Counter(str(row.get("stage11638_source")) for row in train)),
            "train_by_repo_family": dict(Counter(str(row.get("repo_family")) for row in train)),
            "train_by_task_type": dict(Counter(str(row.get("task_type")) for row in train)),
            "train_by_transition": dict(Counter(str(row.get("observed_verifier_transition")) for row in train)),
            "filtered_validation_rows": len(validation),
            "filtered_strict_rows": len(strict),
            "root_overlaps": overlaps,
        },
        "command": command,
        "objective_settings": {
            "bounded_choice_aux_source": "encoder_option_retrieval_web_task_candidate_head",
            "sampler": "web_task_family_balanced",
            "contrast_weight": 0.5,
            "contrast_margin": 0.08,
            "preservation_kl_weight": 10.0,
            "learning_rate": "2e-7",
            "max_steps": 256,
            "batch_size": 8,
        },
        "postrun_required_gates": {
            "filtered_strict": "22/22",
            "filtered_validation": ">=20/22",
            "old_canary_strict": "23/23",
            "old_canary_validation": ">=21/23",
            "residual_bank": ">=7/10",
            "web_heldout": ">38/66 to beat routed policy; >52/66 to beat Gemma",
            "same_manifest_gemma_attached": True,
        },
        "claim_boundary": [
            "This emits a guarded training request only; it does not execute training.",
            "Stage11638 rows are train-support rows, not strict eval rows.",
            "Promotion requires postrun audits against protected canaries, residual bank, Web heldout, and same-manifest Gemma.",
        ],
        "source_artifacts": {
            "train_rows": rel(TRAIN_ROWS),
            "filtered_validation": rel(FILTERED_VALIDATION),
            "filtered_strict": rel(FILTERED_STRICT),
            "old_validation": rel(OLD_VALIDATION),
            "old_strict": rel(OLD_STRICT),
            "residual_bank": rel(RESIDUAL_BANK),
            "web_heldout": rel(WEB_HELDOUT),
            "init_runtime": rel(INIT_RUNTIME),
        },
        "outputs": {
            "train_rows": rel(TRAIN_ROWS_OUT),
            "manifest": rel(MANIFEST),
            "command": rel(COMMAND),
            "summary": rel(SUMMARY),
            "runtime_model": rel(RUNTIME_OUT),
            "probe_output": rel(PROBE),
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(TRAIN_ROWS_OUT, train)
    write_jsonl(MANIFEST, manifest)
    write_json(COMMAND, {"command": command})
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "gates": gates, "metrics": summary["metrics"], "objective_settings": summary["objective_settings"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
