#!/usr/bin/env python3
"""Emit corrected guarded probe request using Stage11884 rendered support rows."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11886
NAME = "stage11886_rendered_source_heldout_support_guarded_probe_request"
OUT = ART / NAME
SUMMARY = OUT / "rendered_source_heldout_support_guarded_probe_request.json"
COMMAND_JSON = OUT / "rendered_source_heldout_support_guarded_probe_command.json"

PACKAGE = ART / "stage11884_rendered_source_heldout_support_probe_package/rendered_source_heldout_support_probe_package.json"
MANIFEST = ART / "stage11884_rendered_source_heldout_support_probe_package/rendered_source_heldout_support_probe_manifest.jsonl"
INIT_RUNTIME = ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"
RUN_DIR = ART / "stage11887_rendered_source_heldout_support_guarded_probe"
RUNTIME_DIR = RUN_DIR / "runtime_model"
OUTPUT_DIR = RUN_DIR / "bounded_decoder_probe"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    package = read_json(PACKAGE)
    if not package.get("passed"):
        raise SystemExit("Stage11884 rendered package did not pass")
    rows = package["row_counts"]
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
        str(rows["split_counts"]["train"]),
        "--max-eval-rows",
        "23",
        "--max-strict-rows",
        "23",
        "--max-steps",
        "256",
        "--batch-size",
        "8",
        "--learning-rate",
        "3e-6",
        "--max-encoder-tokens",
        "768",
        "--max-decoder-tokens",
        "16",
        "--decoder-ce-weight",
        "0.05",
        "--bounded-choice-aux-weight",
        "2.0",
        "--bounded-choice-root-group-aux-weight",
        "0.5",
        "--bounded-choice-aux-source",
        "encoder_option_retrieval_evidence_judgment_head",
        "--bounded-decoder-train-sampler",
        "task_balanced",
        "--bounded-choice-contrast-weight",
        "0.25",
        "--bounded-choice-contrast-margin",
        "0.06",
        "--structured-aux-weight",
        "0.0",
        "--denoise-weight",
        "0.0",
        "--eos-loss-weight",
        "4.0",
        "--enable-generation-audit",
        "--max-generation-rows",
        "12",
        "--max-generation-tokens",
        "16",
        "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness",
        "--runtime-model-save-dir",
        str(RUNTIME_DIR),
        "--initialize-from-runtime-model",
        str(INIT_RUNTIME),
        "--preservation-reference-runtime-model",
        str(INIT_RUNTIME),
        "--preservation-kl-weight",
        "6.0",
        "--no-final-checkpoint-export",
        "--output-dir",
        str(OUTPUT_DIR),
    ]
    gates = {
        "uses_gpu2_mask": "CUDA_VISIBLE_DEVICES=2" in command and "NVIDIA_VISIBLE_DEVICES=2" in command,
        "manifest_exists": MANIFEST.exists(),
        "init_runtime_exists": INIT_RUNTIME.exists(),
        "stage11884_passed": bool(package.get("passed")),
        "rendered_support_rows_160": rows.get("rendered_support_rows") == 160,
        "eval_23": rows["split_counts"].get("eval") == 23,
        "strict_23": rows["split_counts"].get("strict_eval") == 23,
        "pre_options_leaks_zero": package.get("renderer_audit", {}).get("pre_options_target_value_leak_count") == 0,
        "preservation_kl_high": "6.0" in command,
    }
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": all(gates.values()),
        "decision": "rendered_source_heldout_support_guarded_probe_request_ready" if all(gates.values()) else "rendered_source_heldout_support_guarded_probe_request_blocked",
        "command": command,
        "gates_before_execution": gates,
        "source_artifacts": {
            "package": rel(PACKAGE),
            "manifest": rel(MANIFEST),
            "initialize_from_runtime_model": rel(INIT_RUNTIME),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "command": rel(COMMAND_JSON),
            "output_dir": rel(OUTPUT_DIR),
            "runtime_dir": rel(RUNTIME_DIR),
        },
        "promotion_gates_after_run": [
            "old canary strict remains 23/23",
            "filtered strict remains 22/22",
            "old validation remains >=21/23",
            "filtered validation remains >=20/22",
            "residual remains >=7/10",
            "rendered support train fit improves substantially over Stage11507 26/160",
            "source-heldout smoke does not regress under corrected row count",
        ],
        "claim_boundary": [
            "This is the corrected version of Stage11882 after rendering support evidence into prompt/input text.",
            "This remains a guarded diagnostic training request, not a promoted result.",
            "C/C++ support still includes repeated google_benchmark repo-family roots and must not be claimed as source-heldout breadth.",
        ],
    }
    write_json(COMMAND_JSON, {"command": command})
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "passed": artifact["passed"], "manifest": rel(MANIFEST)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
