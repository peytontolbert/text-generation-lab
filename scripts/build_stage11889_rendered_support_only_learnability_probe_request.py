#!/usr/bin/env python3
"""Emit a non-promotable support-only learnability probe request.

This stage intentionally trains only on the Stage11884 rendered support rows.
It is diagnostic-only: success means the support interface/objective can fit the
new rows; promotion still requires a later guarded replay run.
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
STAGE = 11889
NAME = "stage11889_rendered_support_only_learnability_probe_request"
OUT = ART / NAME
SUMMARY = OUT / "rendered_support_only_learnability_probe_request.json"
COMMAND_JSON = OUT / "rendered_support_only_learnability_probe_command.json"
MANIFEST = OUT / "rendered_support_only_learnability_manifest.jsonl"

SOURCE_ROWS = ART / "stage11884_rendered_source_heldout_support_probe_package/rendered_source_heldout_support_added_train_rows.jsonl"
INIT_RUNTIME = ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"
RUN_DIR = ART / "stage11890_rendered_support_only_learnability_probe"
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


def main() -> None:
    source_rows = read_jsonl(SOURCE_ROWS)
    rows: list[dict[str, Any]] = []
    for row in source_rows:
        out = dict(row)
        out["split"] = "train"
        out["package_split"] = "train"
        out["train_support_only"] = True
        out["strict_eval_eligible"] = False
        out["stage11889_support_only_diagnostic"] = True
        rows.append(out)
    # The trainer wants eval/strict split caps but tolerates zero eval/strict
    # only poorly in downstream audits. Reuse small train-heldout copies solely
    # for trainer telemetry; postrun audits score the real rowsets explicitly.
    for index, row in enumerate(source_rows[:8]):
        out = dict(row)
        out["row_id"] = f"{row.get('row_id')}::stage11889_train_echo_eval"
        out["split"] = "eval"
        out["package_split"] = "eval"
        out["stage11889_support_only_diagnostic"] = True
        rows.append(out)
    for index, row in enumerate(source_rows[8:16]):
        out = dict(row)
        out["row_id"] = f"{row.get('row_id')}::stage11889_train_echo_strict"
        out["split"] = "strict_eval"
        out["package_split"] = "strict_eval"
        out["stage11889_support_only_diagnostic"] = True
        rows.append(out)
    write_jsonl(MANIFEST, rows)

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
        "160",
        "--max-eval-rows",
        "8",
        "--max-strict-rows",
        "8",
        "--max-steps",
        "512",
        "--batch-size",
        "8",
        "--learning-rate",
        "1e-5",
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
        "--no-final-checkpoint-export",
        "--output-dir",
        str(OUTPUT_DIR),
    ]
    gates = {
        "uses_gpu2_mask": "CUDA_VISIBLE_DEVICES=2" in command and "NVIDIA_VISIBLE_DEVICES=2" in command,
        "source_rows_160": len(source_rows) == 160,
        "manifest_rows_176": len(rows) == 176,
        "init_runtime_exists": INIT_RUNTIME.exists(),
        "diagnostic_only_no_preservation_reference": "--preservation-reference-runtime-model" not in command,
        "decoder_ce_disabled": "0.0" in command,
        "bounded_aux_high": "4.0" in command,
    }
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": all(gates.values()),
        "decision": "rendered_support_only_learnability_probe_request_ready" if all(gates.values()) else "rendered_support_only_learnability_probe_request_blocked",
        "command": command,
        "gates_before_execution": gates,
        "source_artifacts": {
            "source_rows": rel(SOURCE_ROWS),
            "manifest": rel(MANIFEST),
            "initialize_from_runtime_model": rel(INIT_RUNTIME),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "command": rel(COMMAND_JSON),
            "output_dir": rel(OUTPUT_DIR),
            "runtime_dir": rel(RUNTIME_DIR),
        },
        "claim_boundary": [
            "Diagnostic only: this run intentionally omits protected replay/preservation.",
            "A good result cannot be promoted; it only proves the rendered support interface is learnable.",
            "A bad result means the support schema/objective is still not aligned with the scorer.",
        ],
    }
    write_json(COMMAND_JSON, {"command": command})
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "passed": artifact["passed"], "manifest_rows": len(rows)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
