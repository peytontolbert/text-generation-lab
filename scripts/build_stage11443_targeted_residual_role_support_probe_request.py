#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11443
NAME = "stage11443_targeted_residual_role_support_probe_request"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "targeted_residual_role_support_probe_request.json"
COMMAND_JSON = OUT_DIR / "targeted_residual_role_support_probe_command.json"
MANIFEST_JSONL = OUT_DIR / "targeted_residual_role_support_probe_manifest.jsonl"

PACKAGE = ARTIFACTS / "stage11442_targeted_residual_role_support_package"
PACKAGE_JSON = PACKAGE / "targeted_residual_role_support_package.json"
TRAIN_JSONL = PACKAGE / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_JSONL = PACKAGE / "agentkernel_lite_encdec_validation.jsonl"
STRICT_JSONL = PACKAGE / "agentkernel_lite_encdec_strict_eval.jsonl"
RESIDUAL_JSONL = PACKAGE / "semantic_candidate_residual_bank.jsonl"
QUARANTINE_JSONL = PACKAGE / "targeted_residual_role_quarantine.jsonl"
OLD_CANARY_VALIDATION = ARTIFACTS / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_validation.jsonl"
OLD_CANARY_STRICT = ARTIFACTS / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
INIT_RUNTIME = ARTIFACTS / "stage11440_root_purged_semantic_candidate_probe/runtime_model/runtime_model_bundle.json"
RUN_DIR = ARTIFACTS / "stage11444_targeted_residual_role_support_probe"
PROBE_OUT = RUN_DIR / "bounded_decoder_probe"
RUNTIME_OUT = RUN_DIR / "runtime_model"


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def root_key(row: dict[str, Any]) -> str:
    for key in ("root_id", "source_root_id", "root_lineage_key", "source_bundle_id"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return str(row.get("row_id") or "")


def main() -> None:
    package = load_json(PACKAGE_JSON)
    if not package.get("passed"):
        raise SystemExit("Stage11442 package did not pass")
    if not package.get("gates", {}).get("root_split_clean"):
        raise SystemExit("Stage11442 package is not root-split clean")
    train_rows = load_jsonl(TRAIN_JSONL)
    validation_rows = load_jsonl(VALIDATION_JSONL)
    strict_rows = load_jsonl(STRICT_JSONL)
    residual_rows = load_jsonl(RESIDUAL_JSONL)
    old_validation_rows = load_jsonl(OLD_CANARY_VALIDATION)
    old_strict_rows = load_jsonl(OLD_CANARY_STRICT)
    quarantined_rows = load_jsonl(QUARANTINE_JSONL)

    protected_roots = {root_key(row) for row in validation_rows + strict_rows + residual_rows}
    train_roots = {root_key(row) for row in train_rows}
    overlaps = sorted(train_roots & protected_roots)
    if overlaps:
        raise SystemExit(f"train roots overlap protected roots: {overlaps[:20]}")

    manifest_rows: list[dict[str, Any]] = []
    for split, rows in (("train", train_rows), ("eval", validation_rows), ("strict_eval", strict_rows)):
        for row in rows:
            out = dict(row)
            out["split"] = split
            manifest_rows.append(out)
    write_jsonl(MANIFEST_JSONL, manifest_rows)

    command = [
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
        str((ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py").resolve()),
        "--repo-root",
        str(ROOT),
        "--manifest",
        str(MANIFEST_JSONL.resolve()),
        "--mode",
        "bounded_decoder_ce_probe",
        "--probe-scale",
        "target_100m",
        "--implementation",
        "transformer",
        "--model-config",
        str((ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json").resolve()),
        "--tokenizer-json",
        str((ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json").resolve()),
        "--tokenizer-config",
        str((ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json").resolve()),
        "--tokenizer-hashlock",
        str((ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json").resolve()),
        "--execution-authorized-for-recovery-probe",
        "--max-train-rows",
        str(len(train_rows)),
        "--max-eval-rows",
        str(len(validation_rows)),
        "--max-strict-rows",
        str(len(strict_rows)),
        "--max-steps",
        "160",
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
        "encoder_option_retrieval_semantic_candidate_head",
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
        str(RUNTIME_OUT.resolve()),
        "--initialize-from-runtime-model",
        str(INIT_RUNTIME.resolve()),
        "--preservation-reference-runtime-model",
        str(INIT_RUNTIME.resolve()),
        "--bounded-choice-contrast-weight",
        "1.0",
        "--bounded-choice-contrast-margin",
        "0.10",
        "--preservation-kl-weight",
        "0.15",
        "--no-final-checkpoint-export",
        "--output-dir",
        str(PROBE_OUT.resolve()),
    ]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "targeted_residual_role_support_probe_requested",
        "claim_scope": "diagnostic residual-role support probe only; validation/strict/residual denominators unchanged from Stage11438 root-purged package; old canary must be audited separately",
        "metrics": {
            "train_rows": len(train_rows),
            "validation_rows_filtered": len(validation_rows),
            "strict_rows_filtered": len(strict_rows),
            "residual_rows_for_postrun": len(residual_rows),
            "old_canary_validation_rows_for_postrun": len(old_validation_rows),
            "old_canary_strict_rows_for_postrun": len(old_strict_rows),
            "quarantined_rows": len(quarantined_rows),
            "train_roots": len(train_roots),
            "protected_roots": len(protected_roots),
            "protected_root_overlaps": overlaps,
        },
        "postrun_required_gates": {
            "filtered_strict_no_regression_target": ">=22/22",
            "filtered_validation_no_regression_target": ">=20/22",
            "residual_must_improve_for_frontier_claim": ">5/10",
            "old_canary_strict_must_be_reported_with_base_scorer": "22/23 baseline is separate and unchanged denominator",
            "coverage_corrected_accuracy_required": True,
        },
        "source_artifacts": {
            "package": rel(PACKAGE_JSON),
            "train": rel(TRAIN_JSONL),
            "validation_filtered": rel(VALIDATION_JSONL),
            "strict_filtered": rel(STRICT_JSONL),
            "residual_bank": rel(RESIDUAL_JSONL),
            "quarantine": rel(QUARANTINE_JSONL),
            "old_canary_validation": rel(OLD_CANARY_VALIDATION),
            "old_canary_strict": rel(OLD_CANARY_STRICT),
            "initialize_from_runtime": rel(INIT_RUNTIME),
        },
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "command_json": rel(COMMAND_JSON),
            "manifest_jsonl": rel(MANIFEST_JSONL),
            "probe_output_dir": rel(PROBE_OUT),
            "runtime_model_dir": rel(RUNTIME_OUT),
        },
        "command": command,
    }
    write_json(COMMAND_JSON, {"command": command})
    write_json(SUMMARY_JSON, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY_JSON, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "metrics": summary["metrics"], "passed": True}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
