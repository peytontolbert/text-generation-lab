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
STAGE = 11643
NAME = "stage11643_normalized_web_head_only_fit_request_fixed"
OUT = ART / NAME
SUMMARY = OUT / "normalized_web_head_only_fit_request.json"
MANIFEST = OUT / "normalized_web_head_only_fit_manifest.jsonl"
COMMAND = OUT / "normalized_web_head_only_fit_command.json"

ROWS = ART / "stage11638_web_support_schema_normalization/web_support_normalized_admitted_train_rows.jsonl"
INIT_RUNTIME = ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"
PROBE = ART / "stage11643_normalized_web_head_only_fit_fixed/bounded_decoder_probe"
RUNTIME_OUT = ART / "stage11643_normalized_web_head_only_fit_fixed/runtime_model"


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


def normalize(row: dict[str, Any], split: str) -> dict[str, Any]:
    out = dict(row)
    out["split"] = split
    out.setdefault("prompt_text", out.get("input_text") or "")
    out.setdefault("decoder_text", out.get("target_text") or out.get("bounded_choice_target_label") or "")
    out["loss_mask"] = {"decoder_ce": True, "bounded_choice_aux": True}
    out["expected_enabled_loss"] = "bounded_choice_aux+bounded_choice_contrast"
    source = dict(out.get("standalone_projection_source") or {})
    source.setdefault("opaque_options", out.get("opaque_options") or [])
    out["standalone_projection_source"] = source
    out["opaque_options"] = source["opaque_options"]
    out["target"] = {
        "decoder_text": out.get("decoder_text"),
        "bounded_choice_target_label": out.get("bounded_choice_target_label") or out.get("target_text"),
        "semantic_value": out.get("semantic_target_value") or out.get("target_semantic_value"),
    }
    return out


def row_root(row: dict[str, Any]) -> str:
    return str(row.get("root_lineage_key") or row.get("root_id") or row.get("row_id"))


def main() -> None:
    source_rows = load_jsonl(ROWS)
    train = [normalize(row, "train") for row in source_rows]
    eval_rows = [normalize(row, "eval") for row in source_rows]
    manifest = train + eval_rows
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
        str(len(eval_rows)),
        "--max-strict-rows",
        "0",
        "--max-steps",
        "1536",
        "--batch-size",
        "8",
        "--learning-rate",
        "3e-4",
        "--max-encoder-tokens",
        "768",
        "--max-decoder-tokens",
        "16",
        "--decoder-ce-weight",
        "0.0",
        "--bounded-choice-aux-weight",
        "3.0",
        "--bounded-choice-aux-source",
        "encoder_option_retrieval_web_task_candidate_head",
        "--bounded-choice-train-head-only",
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
        "8",
        "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness",
        "--runtime-model-save-dir",
        str(RUNTIME_OUT),
        "--initialize-from-runtime-model",
        str(INIT_RUNTIME),
        "--no-final-checkpoint-export",
        "--output-dir",
        str(PROBE),
    ]
    gates = {
        "source_rows_206": len(source_rows) == 206,
        "same_rows_train_eval": len(train) == len(eval_rows) == len(source_rows),
        "roots_32": len({row_root(row) for row in source_rows}) == 32,
        "gpu2_mask_present": "CUDA_VISIBLE_DEVICES=2" in command and "NVIDIA_VISIBLE_DEVICES=2" in command,
        "head_only_enabled": "--bounded-choice-train-head-only" in command,
        "decoder_ce_disabled": "--decoder-ce-weight" in command and command[command.index("--decoder-ce-weight") + 1] == "0.0",
        "strict_disabled": "--max-strict-rows" in command and command[command.index("--max-strict-rows") + 1] == "0",
        "contrast_enabled": "--bounded-choice-contrast-weight" in command and command[command.index("--bounded-choice-contrast-weight") + 1] != "0.0",
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "normalized_web_head_only_fit_fixed_ready" if all(gates.values()) else "normalized_web_head_only_fit_fixed_blocked",
        "gates": gates,
        "metrics": {
            "source_rows": len(source_rows),
            "source_roots": len({row_root(row) for row in source_rows}),
            "manifest_rows": len(manifest),
            "rows_by_repo_family": dict(Counter(str(row.get("repo_family")) for row in source_rows)),
            "rows_by_task_type": dict(Counter(str(row.get("task_type")) for row in source_rows)),
            "rows_by_transition": dict(Counter(str(row.get("observed_verifier_transition")) for row in source_rows)),
        },
        "objective_settings": {
            "bounded_choice_aux_source": "encoder_option_retrieval_web_task_candidate_head",
            "bounded_choice_train_head_only": True,
            "decoder_ce_weight": 0.0,
            "bounded_choice_aux_weight": 3.0,
            "bounded_choice_contrast_weight": 0.5,
            "bounded_choice_contrast_margin": 0.08,
            "learning_rate": "3e-4",
            "max_steps": 1536,
            "batch_size": 8,
        },
        "success_criteria": [
            "same-support normalized_web_train_support fit should be high before any full-model distillation is attempted",
            "this is non-promotable even if support fit is perfect",
            "if support fit remains poor, change scorer architecture or task-specific losses",
        ],
        "claim_boundary": [
            "This is a non-promotable representability probe; decoder CE is enabled in the mask for contract safety but weighted 0.0.",
            "The same normalized Web support rows are intentionally used as train and eval.",
            "A high score proves head/objective fit only; it is not Web heldout progress.",
        ],
        "source_artifacts": {"rows": rel(ROWS), "init_runtime": rel(INIT_RUNTIME)},
        "outputs": {"manifest": rel(MANIFEST), "command": rel(COMMAND), "summary": rel(SUMMARY), "runtime_model": rel(RUNTIME_OUT)},
        "command": command,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(MANIFEST, manifest)
    write_json(COMMAND, {"command": command})
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "gates": gates, "metrics": summary["metrics"], "objective_settings": summary["objective_settings"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
