#!/usr/bin/env python3
"""Emit a diagnostic rendered-support + protected-replay probe request.

This stage intentionally includes protected canary/residual rows as train replay
copies. It is not promotable. It tests whether the current objective can fit the
rendered support interface while retaining the selected frontier geometry when
protected replay is present.
"""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11892
NAME = "stage11892_rendered_support_protected_replay_probe_request"
OUT = ART / NAME
SUMMARY = OUT / "rendered_support_protected_replay_probe_request.json"
COMMAND_JSON = OUT / "rendered_support_protected_replay_command.json"
MANIFEST = OUT / "rendered_support_protected_replay_manifest.jsonl"

SUPPORT_ROWS = ART / "stage11884_rendered_source_heldout_support_probe_package/rendered_source_heldout_support_added_train_rows.jsonl"
PROTECTED_ROWSETS = {
    "residual_bank": ART / "stage11442_targeted_residual_role_support_package/semantic_candidate_residual_bank.jsonl",
    "filtered_strict": ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_strict_eval.jsonl",
    "old_canary_strict": ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_strict_eval.jsonl",
    "filtered_validation": ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_validation.jsonl",
    "old_canary_validation": ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_validation.jsonl",
}
INIT_RUNTIME = ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"
RUN_DIR = ART / "stage11893_rendered_support_protected_replay_probe"
RUNTIME_DIR = RUN_DIR / "runtime_model"
OUTPUT_DIR = RUN_DIR / "bounded_decoder_probe"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def train_copy(row: dict[str, Any], *, suffix: str, replay_kind: str, preservation_exempt: bool) -> dict[str, Any]:
    out = dict(row)
    out["row_id"] = f"{row.get('row_id')}::{suffix}"
    out["split"] = "train"
    out["package_split"] = "train"
    out["train_support_only"] = True
    out["strict_eval_eligible"] = False
    out["stage11892_replay_kind"] = replay_kind
    out["preservation_exempt"] = preservation_exempt
    source = dict(out.get("standalone_projection_source") or {})
    source.setdefault("opaque_options", out.get("opaque_options") or [])
    out["standalone_projection_source"] = source
    if not isinstance(out.get("target"), dict):
        label = out.get("bounded_choice_target_label") or out.get("target_label") or out.get("target_text")
        out["target"] = {
            "decoder_text": out.get("decoder_text") or label,
            "bounded_choice_target_label": label,
            "semantic_value": out.get("semantic_target_value") or out.get("target_value"),
        }
    if not isinstance(out.get("loss_mask"), dict):
        out["loss_mask"] = {"decoder_ce": True, "bounded_choice_aux": True}
    return out


def main() -> None:
    support = read_jsonl(SUPPORT_ROWS)
    protected_sources = {name: read_jsonl(path) for name, path in PROTECTED_ROWSETS.items()}
    train_rows: list[dict[str, Any]] = []
    for row in support:
        train_rows.append(train_copy(row, suffix="stage11892_support", replay_kind="rendered_support", preservation_exempt=True))
    # Repeat protected rows enough to materially constrain the scorer while still
    # letting support rows dominate the update.
    for repeat in range(3):
        for name, rows in protected_sources.items():
            for row in rows:
                train_rows.append(
                    train_copy(
                        row,
                        suffix=f"stage11892_{name}_replay_r{repeat}",
                        replay_kind=name,
                        preservation_exempt=False,
                    )
                )
    eval_rows = []
    for row in protected_sources["filtered_validation"]:
        out = dict(row)
        out["split"] = "eval"
        out["package_split"] = "eval"
        eval_rows.append(out)
    strict_rows = []
    for row in protected_sources["filtered_strict"]:
        out = dict(row)
        out["split"] = "strict_eval"
        out["package_split"] = "strict_eval"
        strict_rows.append(out)
    manifest_rows = train_rows + eval_rows + strict_rows
    write_jsonl(MANIFEST, manifest_rows)

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
        str(len(train_rows)),
        "--max-eval-rows",
        str(len(eval_rows)),
        "--max-strict-rows",
        str(len(strict_rows)),
        "--max-steps",
        "512",
        "--batch-size",
        "8",
        "--learning-rate",
        "5e-6",
        "--max-encoder-tokens",
        "768",
        "--max-decoder-tokens",
        "16",
        "--decoder-ce-weight",
        "0.0",
        "--bounded-choice-aux-weight",
        "4.0",
        "--bounded-choice-root-group-aux-weight",
        "0.0",
        "--bounded-choice-aux-source",
        "encoder_option_retrieval_evidence_judgment_head",
        "--bounded-decoder-train-sampler",
        "task_balanced",
        "--bounded-choice-contrast-weight",
        "0.5",
        "--bounded-choice-contrast-margin",
        "0.08",
        "--structured-aux-weight",
        "0.0",
        "--denoise-weight",
        "0.0",
        "--eos-loss-weight",
        "1.0",
        "--enable-generation-audit",
        "--max-generation-rows",
        "8",
        "--max-generation-tokens",
        "8",
        "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness",
        "--runtime-model-save-dir",
        str(RUNTIME_DIR),
        "--initialize-from-runtime-model",
        str(INIT_RUNTIME),
        "--preservation-reference-runtime-model",
        str(INIT_RUNTIME),
        "--preservation-kl-weight",
        "2.0",
        "--no-final-checkpoint-export",
        "--output-dir",
        str(OUTPUT_DIR),
    ]
    gates = {
        "uses_gpu2_mask": "CUDA_VISIBLE_DEVICES=2" in command and "NVIDIA_VISIBLE_DEVICES=2" in command,
        "support_rows_160": len(support) == 160,
        "train_rows_expected": len(train_rows) == 160 + (3 * sum(len(rows) for rows in protected_sources.values())),
        "eval_filtered_validation_22": len(eval_rows) == 22,
        "strict_filtered_22": len(strict_rows) == 22,
        "init_runtime_exists": INIT_RUNTIME.exists(),
        "diagnostic_train_eval_overlap_declared": True,
        "support_preservation_exempt": all(row.get("preservation_exempt") for row in train_rows if row.get("stage11892_replay_kind") == "rendered_support"),
    }
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": all(gates.values()),
        "decision": "rendered_support_protected_replay_probe_request_ready" if all(gates.values()) else "rendered_support_protected_replay_probe_request_blocked",
        "command": command,
        "gates_before_execution": gates,
        "row_counts": {
            "train_rows": len(train_rows),
            "eval_rows": len(eval_rows),
            "strict_rows": len(strict_rows),
            "support_rows": len(support),
            "protected_replay_source_rows": {name: len(rows) for name, rows in protected_sources.items()},
        },
        "source_artifacts": {
            "support_rows": rel(SUPPORT_ROWS),
            "manifest": rel(MANIFEST),
            "initialize_from_runtime_model": rel(INIT_RUNTIME),
            "protected_rowsets": {name: rel(path) for name, path in PROTECTED_ROWSETS.items()},
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "command": rel(COMMAND_JSON),
            "output_dir": rel(OUTPUT_DIR),
            "runtime_dir": rel(RUNTIME_DIR),
        },
        "claim_boundary": [
            "Diagnostic only: this stage intentionally trains on protected replay copies.",
            "If successful, replace protected replay with disjoint analogue replay before any promotable run.",
            "This tests mechanism, not benchmark standing.",
        ],
    }
    write_json(COMMAND_JSON, {"command": command})
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "passed": artifact["passed"], "row_counts": artifact["row_counts"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
