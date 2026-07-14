#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
STAGE = 11327
NAME = "stage11327_alias_free_evidence_scale_probe_request"
OUT = ART / NAME
SUMMARY = OUT / "alias_free_evidence_scale_probe_request.json"
CMD = OUT / "alias_free_evidence_scale_probe_command.json"
MANIFEST = OUT / "alias_free_evidence_scale_probe_manifest.jsonl"

PKG = ART / "stage11326_alias_free_evidence_item_selection_scale_package"
PKG_JSON = PKG / "alias_free_evidence_item_selection_scale_package.json"
TRAIN = PKG / "alias_free_evidence_item_selection_scale_train_rows.jsonl"
VAL = PKG / "alias_free_evidence_item_selection_scale_validation_rows.jsonl"
STRICT = PKG / "alias_free_evidence_item_selection_scale_strict_rows.jsonl"
DIAG = PKG / "alias_free_evidence_item_selection_scale_diagnostic_rows.jsonl"
CANARY = ART / "stage11312_deleaked_fail_to_pass_transition_package"
CANARY_VAL = CANARY / "deleaked_fail_to_pass_validation_rows.jsonl"
CANARY_STRICT = CANARY / "deleaked_fail_to_pass_strict_rows.jsonl"
CANARY_RES = CANARY / "deleaked_fail_to_pass_residual_rows.jsonl"
INIT = ART / "stage11200_role_focused_residual_probe/runtime_model/runtime_model_bundle.json"
RUN = ART / "stage11328_alias_free_evidence_scale_probe"
PROBE = RUN / "bounded_decoder_probe"
RUNTIME = RUN / "runtime_model"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def root_id(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("source_root_id") or row.get("root_lineage_key") or row.get("row_id") or "")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pkg = read_json(PKG_JSON)
    if not pkg.get("passed"):
        raise SystemExit("stage11326 package did not pass")
    train = read_jsonl(TRAIN)
    val = read_jsonl(VAL)
    strict = read_jsonl(STRICT)
    diag = read_jsonl(DIAG)
    canary_rows = read_jsonl(CANARY_VAL) + read_jsonl(CANARY_STRICT) + read_jsonl(CANARY_RES)
    protected = {root_id(row) for row in val + strict + diag + canary_rows}
    overlaps = sorted({root_id(row) for row in train} & protected)
    if overlaps:
        raise SystemExit(f"protected root overlap in train: {overlaps[:10]}")

    manifest_rows = []
    for split, rows in [("train", train), ("eval", val), ("strict_eval", strict)]:
        for row in rows:
            item = dict(row)
            item["split"] = split
            manifest_rows.append(item)
    write_jsonl(MANIFEST, manifest_rows)

    cmd = [
        "env",
        "CUDA_VISIBLE_DEVICES=2",
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
        str(len(val)),
        "--max-strict-rows",
        str(len(strict)),
        "--max-steps",
        "256",
        "--batch-size",
        "4",
        "--learning-rate",
        "6e-6",
        "--max-encoder-tokens",
        "768",
        "--max-decoder-tokens",
        "16",
        "--decoder-ce-weight",
        "0.1",
        "--bounded-choice-aux-weight",
        "2.0",
        "--bounded-choice-aux-source",
        "encoder_option_retrieval_evidence_judgment_head",
        "--bounded-decoder-train-sampler",
        "residual_family_balanced",
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
        str(RUNTIME),
        "--initialize-from-runtime-model",
        str(INIT),
        "--preservation-reference-runtime-model",
        str(INIT),
        "--bounded-choice-contrast-weight",
        "1.0",
        "--bounded-choice-contrast-margin",
        "0.10",
        "--preservation-kl-weight",
        "0.25",
        "--no-final-checkpoint-export",
        "--output-dir",
        str(PROBE),
    ]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": True,
        "decision": "alias_free_evidence_scale_probe_requested_diagnostic_only",
        "metrics": {
            "train_rows": len(train),
            "validation_rows": len(val),
            "strict_rows": len(strict),
            "diagnostic_rows_for_postrun": len(diag),
            "protected_root_overlaps": overlaps,
        },
        "source_artifacts": {
            "package": rel(PKG_JSON),
            "train": rel(TRAIN),
            "validation": rel(VAL),
            "strict": rel(STRICT),
            "diagnostic": rel(DIAG),
            "canary_validation": rel(CANARY_VAL),
            "canary_strict": rel(CANARY_STRICT),
            "canary_residual": rel(CANARY_RES),
            "init_runtime": rel(INIT),
        },
        "outputs": {
            "summary_json": rel(SUMMARY),
            "command_json": rel(CMD),
            "manifest_jsonl": rel(MANIFEST),
            "probe_output_dir": rel(PROBE),
            "runtime_model_dir": rel(RUNTIME),
        },
        "promotion_gate": {
            "diagnostic_only": True,
            "reason": "stage11326 train split is Python-heavy with inadequate Rust/Web supply",
            "canary_strict_must_remain": "22/22",
            "canary_validation_must_remain": ">=20/23",
            "alias_free_diagnostic_should_exceed": "5/7",
            "alias_free_validation_should_exceed": "12/22 equivalent prior is superseded by larger 100-row split; require >=70%",
            "alias_free_strict_should_exceed": "11/20 equivalent prior is superseded by larger 170-row split; require >=70%",
        },
        "command": cmd,
    }
    write_json(CMD, {"command": cmd})
    write_json(SUMMARY, summary)
    print(json.dumps({"passed": True, "metrics": summary["metrics"], "cmd": rel(CMD)}, indent=2))


if __name__ == "__main__":
    main()
