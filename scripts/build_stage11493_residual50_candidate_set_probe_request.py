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

STAGE = 11493
NAME = "stage11493_residual50_candidate_set_probe_request"
OUT = ART / NAME
SUMMARY = OUT / "residual50_candidate_set_probe_request.json"
MANIFEST = OUT / "residual50_candidate_set_probe_manifest.jsonl"
COMMAND_JSON = OUT / "residual50_candidate_set_probe_command.json"

BASE = ART / "stage11436_full_coverage_semantic_candidate_package"
BASE_TRAIN = BASE / "agentkernel_lite_encdec_train.jsonl"
VALIDATION = BASE / "agentkernel_lite_encdec_validation.jsonl"
STRICT = BASE / "agentkernel_lite_encdec_strict_eval.jsonl"
RESIDUAL = BASE / "semantic_candidate_residual_bank.jsonl"
CANDIDATE_ROWS = ART / "stage11492_residual50_candidate_set_recompiler/residual50_candidate_set_rows.jsonl"
CANDIDATE_SUMMARY = ART / "stage11492_residual50_candidate_set_recompiler/residual50_candidate_set_recompiler.json"
INIT_RUNTIME = ART / "stage11444_targeted_residual_role_support_probe/runtime_model/runtime_model_bundle.json"

RUN_DIR = ART / "stage11494_residual50_candidate_set_probe"
RUNTIME_DIR = RUN_DIR / "runtime_model"
OUTPUT_DIR = RUN_DIR / "bounded_decoder_probe"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def root_key(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("source_root_id") or row.get("root_lineage_key") or row.get("row_id") or "")


def row_key(row: dict[str, Any]) -> str:
    return str(row.get("row_id") or "")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    candidate_summary = read_json(CANDIDATE_SUMMARY)
    base_train = read_jsonl(BASE_TRAIN)
    validation = read_jsonl(VALIDATION)
    strict = read_jsonl(STRICT)
    residual = read_jsonl(RESIDUAL)
    candidate_rows = read_jsonl(CANDIDATE_ROWS)

    protected_rows = {row_key(row) for row in validation + strict + residual}
    protected_roots = {root_key(row) for row in validation + strict + residual}
    added_rows = {row_key(row) for row in candidate_rows}
    added_roots = {root_key(row) for row in candidate_rows}
    row_overlaps = sorted(added_rows & protected_rows)
    root_overlaps = sorted(root for root in (added_roots & protected_roots) if root)

    candidate_metrics = candidate_summary.get("metrics") or {}
    ready = (
        candidate_summary.get("decision") == "residual50_candidate_sets_ready_for_listwise_probe"
        and int(candidate_metrics.get("candidate_set_rows") or 0) >= 30
        and bool(candidate_metrics.get("no_protected_overlap")) is True
    )
    allowed = ready and not row_overlaps and not root_overlaps

    train_rows_by_id: dict[str, dict[str, Any]] = {}
    for row in base_train + candidate_rows:
        payload = dict(row)
        payload["split"] = "train"
        train_rows_by_id[row_key(payload)] = payload
    train_rows = list(train_rows_by_id.values())

    manifest_rows: list[dict[str, Any]] = []
    for split, rows in (("train", train_rows), ("eval", validation), ("strict_eval", strict)):
        for row in rows:
            payload = dict(row)
            payload["split"] = split
            manifest_rows.append(payload)
    write_jsonl(MANIFEST, manifest_rows)

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
        str(len(validation)),
        "--max-strict-rows",
        str(len(strict)),
        "--max-steps",
        "160",
        "--batch-size",
        "4",
        "--learning-rate",
        "5e-6",
        "--max-encoder-tokens",
        "768",
        "--max-decoder-tokens",
        "16",
        "--decoder-ce-weight",
        "0.1",
        "--bounded-choice-aux-weight",
        "2.0",
        "--bounded-choice-aux-source",
        "encoder_option_retrieval",
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
        str(RUNTIME_DIR),
        "--initialize-from-runtime-model",
        str(INIT_RUNTIME),
        "--preservation-reference-runtime-model",
        str(INIT_RUNTIME),
        "--bounded-choice-contrast-weight",
        "1.25",
        "--bounded-choice-contrast-margin",
        "0.12",
        "--preservation-kl-weight",
        "0.15",
        "--no-final-checkpoint-export",
        "--output-dir",
        str(OUTPUT_DIR),
    ]
    write_json(COMMAND_JSON, {"command": command, "allowed_to_run": allowed})
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": allowed,
        "decision": "residual50_candidate_set_probe_requested" if allowed else "residual50_candidate_set_probe_blocked",
        "hypothesis": {
            "failure_family": "Residual-50 evidence/verifier role boundary",
            "mechanism": "previous Residual-50 rows contained contradictory same-state sibling targets that shifted role priors instead of teaching candidate-set decisions",
            "single_changed_variable": "data geometry: Stage11481 raw Residual-50 rows replaced by Stage11492 deconflicted candidate-set rows",
            "held_constant": [
                "Stage11444 initialization",
                "product scorer encoder_option_retrieval",
                "loss weights",
                "residual_family_balanced sampler",
                "protected validation/strict/residual splits",
            ],
        },
        "metrics": {
            "base_train_rows": len(base_train),
            "candidate_set_rows": len(candidate_rows),
            "train_rows_after_dedupe": len(train_rows),
            "validation_rows": len(validation),
            "strict_rows": len(strict),
            "residual_rows_for_postrun": len(residual),
            "protected_row_overlaps": len(row_overlaps),
            "protected_root_overlaps": len(root_overlaps),
            "manifest_rows": len(manifest_rows),
            "max_steps": 160,
            "batch_size": 4,
        },
        "postrun_required_gates": {
            "old_canary_strict": "23/23",
            "filtered_strict": "22/22",
            "filtered_validation": ">=20/22",
            "old_canary_validation": ">=21/23",
            "residual_bank_must_improve_for_frontier_claim": ">5/10",
            "product_scorer": "encoder_option_retrieval",
            "full_bounded_choice_coverage": True,
        },
        "blockers": {
            "candidate_set_summary_not_ready": not ready,
            "protected_row_overlaps": row_overlaps,
            "protected_root_overlaps": root_overlaps,
        },
        "source_artifacts": {
            "base_train": rel(BASE_TRAIN),
            "validation": rel(VALIDATION),
            "strict": rel(STRICT),
            "residual_bank": rel(RESIDUAL),
            "candidate_set_rows": rel(CANDIDATE_ROWS),
            "candidate_set_summary": rel(CANDIDATE_SUMMARY),
            "initialize_from_runtime": rel(INIT_RUNTIME),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "manifest_jsonl": rel(MANIFEST),
            "command_json": rel(COMMAND_JSON),
            "probe_output_dir": rel(OUTPUT_DIR),
            "runtime_model_dir": rel(RUNTIME_DIR),
        },
        "command": command,
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"passed": allowed, "decision": summary["decision"], "metrics": summary["metrics"], "blockers": summary["blockers"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
