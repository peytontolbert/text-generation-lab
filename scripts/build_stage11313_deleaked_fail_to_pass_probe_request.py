#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11313
NAME = "stage11313_deleaked_fail_to_pass_probe_request"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "deleaked_fail_to_pass_probe_request.json"
COMMAND_JSON = OUT_DIR / "deleaked_fail_to_pass_probe_command.json"
MANIFEST = OUT_DIR / "deleaked_fail_to_pass_probe_manifest.jsonl"

PACKAGE = ARTIFACTS / "stage11312_deleaked_fail_to_pass_transition_package"
PACKAGE_JSON = PACKAGE / "deleaked_fail_to_pass_transition_package.json"
TRAIN = PACKAGE / "deleaked_fail_to_pass_train_rows.jsonl"
VALIDATION = PACKAGE / "deleaked_fail_to_pass_validation_rows.jsonl"
STRICT = PACKAGE / "deleaked_fail_to_pass_strict_rows.jsonl"
JUDGMENT_VALIDATION = PACKAGE / "deleaked_fail_to_pass_judgment_validation_rows.jsonl"
JUDGMENT_STRICT = PACKAGE / "deleaked_fail_to_pass_judgment_strict_rows.jsonl"
RESIDUAL = PACKAGE / "deleaked_fail_to_pass_residual_rows.jsonl"
ADDED = PACKAGE / "added_deleaked_fail_to_pass_rows.jsonl"
INIT_RUNTIME = ARTIFACTS / "stage11200_role_focused_residual_probe/runtime_model/runtime_model_bundle.json"
RUN_DIR = ARTIFACTS / "stage11314_deleaked_fail_to_pass_probe"
PROBE_OUT = RUN_DIR / "bounded_decoder_probe"
RUNTIME_OUT = RUN_DIR / "runtime_model"


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def root_key(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("source_root_id") or row.get("root_lineage_key") or row.get("row_id") or "")


def main() -> None:
    package = read_json(PACKAGE_JSON)
    if not package.get("passed"):
        raise SystemExit("Stage11312 package did not pass")
    train = read_jsonl(TRAIN)
    validation = read_jsonl(VALIDATION)
    strict = read_jsonl(STRICT)
    residual = read_jsonl(RESIDUAL)
    judgment_validation = read_jsonl(JUDGMENT_VALIDATION)
    judgment_strict = read_jsonl(JUDGMENT_STRICT)
    added = read_jsonl(ADDED)
    protected = {root_key(row) for row in validation + strict + residual + judgment_validation + judgment_strict}
    train_overlap = sorted({root_key(row) for row in train} & protected)
    if train_overlap:
        raise SystemExit(f"train/protected root overlap: {train_overlap[:10]}")
    manifest_rows = []
    for split, rows in (("train", train), ("eval", validation), ("strict_eval", strict)):
        for row in rows:
            out = dict(row)
            out["split"] = split
            manifest_rows.append(out)
    write_jsonl(MANIFEST, manifest_rows)
    command = [
        "env", "CUDA_VISIBLE_DEVICES=2", "PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True", "TMPDIR=/data/tmp", "TEMP=/data/tmp", "TMP=/data/tmp",
        "conda", "run", "-n", "trellis", "python", str(ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"),
        "--repo-root", str(ROOT),
        "--manifest", str(MANIFEST),
        "--mode", "bounded_decoder_ce_probe",
        "--probe-scale", "target_100m",
        "--implementation", "transformer",
        "--model-config", str(ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"),
        "--tokenizer-json", str(ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"),
        "--tokenizer-config", str(ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"),
        "--tokenizer-hashlock", str(ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"),
        "--execution-authorized-for-recovery-probe",
        "--max-train-rows", str(len(train)),
        "--max-eval-rows", str(len(validation)),
        "--max-strict-rows", str(len(strict)),
        "--max-steps", "128",
        "--batch-size", "4",
        "--learning-rate", "6e-6",
        "--max-encoder-tokens", "768",
        "--max-decoder-tokens", "16",
        "--decoder-ce-weight", "0.1",
        "--bounded-choice-aux-weight", "2.0",
        "--bounded-choice-aux-source", "encoder_option_retrieval_verifier_conditioned",
        "--bounded-decoder-train-sampler", "residual_family_balanced",
        "--structured-aux-weight", "0.0",
        "--denoise-weight", "0.0",
        "--eos-loss-weight", "4.0",
        "--enable-generation-audit",
        "--max-generation-rows", "12",
        "--max-generation-tokens", "16",
        "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness",
        "--runtime-model-save-dir", str(RUNTIME_OUT),
        "--initialize-from-runtime-model", str(INIT_RUNTIME),
        "--preservation-reference-runtime-model", str(INIT_RUNTIME),
        "--bounded-choice-contrast-weight", "1.0",
        "--bounded-choice-contrast-margin", "0.10",
        "--preservation-kl-weight", "0.35",
        "--no-final-checkpoint-export",
        "--output-dir", str(PROBE_OUT),
    ]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "deleaked_fail_to_pass_probe_requested",
        "claim_scope": "Diagnostic only. Tests whether 5 de-leaked Python FAIL_TO_PASS transition roots plus 15 clean PASS_TO_PASS roots move the verifier residual without canary regression.",
        "source_artifacts": {"package": rel(PACKAGE_JSON), "train": rel(TRAIN), "validation": rel(VALIDATION), "strict": rel(STRICT), "residual": rel(RESIDUAL), "added_rows": rel(ADDED), "initialize_from_runtime": rel(INIT_RUNTIME)},
        "metrics": {"train_rows": len(train), "validation_rows": len(validation), "strict_rows": len(strict), "residual_rows_for_postrun": len(residual), "judgment_validation_rows_for_postrun": len(judgment_validation), "judgment_strict_rows_for_postrun": len(judgment_strict), "added_rows": len(added), "added_roots": len({root_key(row) for row in added}), "protected_root_overlaps": train_overlap},
        "promotion_gate_for_postrun": {"clean_strict_must_remain": "22/22", "clean_validation_should_not_regress": ">=20/23", "residual_bank_must_improve": ">5/10", "verifier_transition_residual_should_flip": "stage10894/code_assist Python row", "no_frontier_promotion_if_flat": True},
        "outputs": {"summary_json": rel(SUMMARY_JSON), "command_json": rel(COMMAND_JSON), "manifest_jsonl": rel(MANIFEST), "probe_output_dir": rel(PROBE_OUT), "runtime_model_dir": rel(RUNTIME_OUT)},
        "command": command,
    }
    write_json(COMMAND_JSON, {"command": command})
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
