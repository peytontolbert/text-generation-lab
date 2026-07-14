#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11563
NAME = "stage11563_conservative_openhands_from_stage11507_probe_request"
OUT = ART / NAME
SUMMARY = OUT / "conservative_openhands_from_stage11507_probe_request.json"
MANIFEST = OUT / "conservative_openhands_from_stage11507_probe_manifest.jsonl"
COMMAND = OUT / "conservative_openhands_from_stage11507_probe_command.json"
PROBE = ART / "stage11563_conservative_openhands_from_stage11507_probe/bounded_decoder_probe"
RUNTIME_OUT = ART / "stage11563_conservative_openhands_from_stage11507_probe/runtime_model"

TRAIN = ART / "stage11394_openhands_support_unit_verifier_train_rows/openhands_support_unit_verifier_train_rows.jsonl"
FILTERED_VALIDATION = ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_validation.jsonl"
FILTERED_STRICT = ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
INIT_RUNTIME = ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"
OPENHANDS_HELDOUT = ART / "stage11390_openhands_unit_verifier_heldout_candidate_rows/openhands_unit_verifier_heldout_candidate_rows.jsonl"
LLAMA_HELDOUT = ART / "stage11361_web_llama_stack_executed_heldout_rows/web_llama_stack_executed_heldout_rows.jsonl"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def with_split(rows: list[dict[str, Any]], split: str) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        item = dict(row)
        item["split"] = split
        item.setdefault("expected_enabled_loss", "decoder_ce")
        out.append(item)
    return out


def root_ids(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row.get("root_id") or row.get("source_bundle_id") or row.get("row_id", "").split("::")[0]) for row in rows}


def main() -> None:
    train = load_jsonl(TRAIN)
    validation = load_jsonl(FILTERED_VALIDATION)
    strict = load_jsonl(FILTERED_STRICT)
    openhands_heldout = load_jsonl(OPENHANDS_HELDOUT)
    llama_heldout = load_jsonl(LLAMA_HELDOUT)
    manifest_rows = with_split(train, "train") + with_split(validation, "eval") + with_split(strict, "strict_eval")
    train_roots = root_ids(train)
    validation_roots = root_ids(validation)
    strict_roots = root_ids(strict)
    openhands_roots = root_ids(openhands_heldout)
    llama_roots = root_ids(llama_heldout)
    overlaps = {
        "train_vs_validation": sorted(train_roots & validation_roots),
        "train_vs_strict": sorted(train_roots & strict_roots),
        "train_vs_openhands_heldout": sorted(train_roots & openhands_roots),
        "train_vs_llama_heldout": sorted(train_roots & llama_roots),
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
        "96",
        "--batch-size",
        "4",
        "--learning-rate",
        "5e-7",
        "--max-encoder-tokens",
        "768",
        "--max-decoder-tokens",
        "16",
        "--decoder-ce-weight",
        "0.04",
        "--bounded-choice-aux-weight",
        "3.0",
        "--bounded-choice-aux-source",
        "encoder_option_retrieval_evidence_judgment_head",
        "--bounded-decoder-train-sampler",
        "cyclic",
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
        "--bounded-choice-contrast-weight",
        "0.0",
        "--bounded-choice-contrast-margin",
        "0.05",
        "--preservation-kl-weight",
        "4.0",
        "--no-final-checkpoint-export",
        "--output-dir",
        str(PROBE),
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(MANIFEST, manifest_rows)
    write_json(COMMAND, {"command": command})
    gates = {
        "train_rows_present": len(train) == 24,
        "validation_rows_present": len(validation) > 0,
        "strict_rows_present": len(strict) > 0,
        "no_train_validation_or_strict_root_overlap": not overlaps["train_vs_validation"] and not overlaps["train_vs_strict"],
        "no_train_openhands_or_llama_heldout_root_overlap": not overlaps["train_vs_openhands_heldout"] and not overlaps["train_vs_llama_heldout"],
        "all_train_rows_declared_train_support_only": all((row.get("anti_cheat") or {}).get("not_strict_eval_eligible") is True for row in train),
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": all(gates.values()),
        "decision": "conservative_openhands_stage11507_probe_ready" if all(gates.values()) else "conservative_openhands_stage11507_probe_blocked",
        "metrics": {
            "train_rows": len(train),
            "train_roots": len(train_roots),
            "validation_rows": len(validation),
            "strict_rows": len(strict),
            "openhands_heldout_rows": len(openhands_heldout),
            "llama_stack_heldout_rows": len(llama_heldout),
            "root_overlaps": overlaps,
        },
        "gates": gates,
        "command": command,
        "claim_boundary": [
            "Diagnostic conservative Web transfer support probe only.",
            "OpenHands support rows share repo family with OpenHands heldout, so a win there would not be a broad Web promotion claim.",
            "Llama Stack remains a separate Web heldout transfer check.",
            "Gemma outputs are existing artifacts; this request does not use Ollama.",
        ],
        "source_artifacts": {
            "train": rel(TRAIN),
            "filtered_validation": rel(FILTERED_VALIDATION),
            "filtered_strict": rel(FILTERED_STRICT),
            "openhands_heldout": rel(OPENHANDS_HELDOUT),
            "llama_heldout": rel(LLAMA_HELDOUT),
            "init_runtime": rel(INIT_RUNTIME),
        },
        "outputs": {
            "manifest": rel(MANIFEST),
            "command": rel(COMMAND),
            "probe_dir": rel(PROBE),
            "runtime_model": rel(RUNTIME_OUT),
            "summary": rel(SUMMARY),
        },
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "passed": summary["passed"], "metrics": summary["metrics"], "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
