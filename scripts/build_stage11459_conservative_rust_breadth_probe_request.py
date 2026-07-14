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
STAGE = 11459
NAME = "stage11459_conservative_rust_breadth_probe_request"
OUT = ART / NAME
SUMMARY = OUT / "conservative_rust_breadth_probe_request.json"
MANIFEST = OUT / "conservative_rust_breadth_probe_manifest.jsonl"
COMMAND_JSON = OUT / "conservative_rust_breadth_probe_command.json"

PACKAGE = ART / "stage11454_rust_breadth_support_package_v2"
TRAIN = PACKAGE / "added_rust_breadth_support_rows.jsonl"
VALIDATION = PACKAGE / "agentkernel_lite_encdec_validation.jsonl"
STRICT = PACKAGE / "agentkernel_lite_encdec_strict_eval.jsonl"
READINESS = ART / "stage11455_rust_breadth_support_probe_readiness_decision/rust_breadth_support_probe_readiness_decision.json"
INIT_RUNTIME = ART / "stage11444_targeted_residual_role_support_probe/runtime_model/runtime_model_bundle.json"
RUN_DIR = ART / "stage11460_conservative_rust_breadth_probe"
RUNTIME_DIR = RUN_DIR / "runtime_model"
OUTPUT_DIR = RUN_DIR / "bounded_decoder_probe"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text()) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def root_key(row: dict[str, Any]) -> str:
    return str(row.get("root_lineage_key") or row.get("root_id") or row.get("source_root_id") or row.get("row_id"))


def repo_family(row: dict[str, Any]) -> str:
    return str(row.get("repo_family") or row.get("repo_id") or "unknown")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    readiness = read_json(READINESS)
    train = read_jsonl(TRAIN)
    validation = read_jsonl(VALIDATION)
    strict = read_jsonl(STRICT)
    rows = train + validation + strict
    write_jsonl(MANIFEST, rows)

    train_roots = {root_key(row) for row in train}
    protected_roots = {root_key(row) for row in validation + strict}
    root_overlap = sorted(train_roots & protected_roots)
    allowed = (
        readiness.get("quality_gate", {}).get("ready_for_probe_request") is True
        and len(train) == 18
        and len(train_roots) == 6
        and len({repo_family(row) for row in train}) >= 4
        and not root_overlap
    )
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
        str(len(train)),
        "--max-eval-rows",
        str(len(validation)),
        "--max-strict-rows",
        str(len(strict)),
        "--max-steps",
        "24",
        "--batch-size",
        "2",
        "--learning-rate",
        "5e-7",
        "--max-encoder-tokens",
        "768",
        "--max-decoder-tokens",
        "16",
        "--decoder-ce-weight",
        "0.05",
        "--bounded-choice-aux-weight",
        "0.5",
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
        "0.2",
        "--bounded-choice-contrast-margin",
        "0.05",
        "--preservation-kl-weight",
        "5.0",
        "--no-final-checkpoint-export",
        "--output-dir",
        str(OUTPUT_DIR),
    ]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": allowed,
        "decision": "conservative_rust_breadth_probe_requested" if allowed else "conservative_rust_breadth_probe_blocked",
        "claim_scope": "diagnostic low-update Rust breadth probe only; Stage11444 remains selected unless postrun gates pass",
        "metrics": {
            "train_rows": len(train),
            "train_roots": len(train_roots),
            "train_repo_families": len({repo_family(row) for row in train}),
            "validation_rows": len(validation),
            "strict_rows": len(strict),
            "manifest_rows": len(rows),
            "train_protected_root_overlap": len(root_overlap),
        },
        "training_safety_controls": {
            "max_steps": 24,
            "learning_rate": "5e-7",
            "preservation_kl_weight": 5.0,
            "decoder_ce_weight": 0.05,
            "bounded_choice_aux_weight": 0.5,
            "train_only_new_rust_rows": True,
        },
        "postrun_required_gates": {
            "old_canary_strict_no_regression": ">=23/23 with selected base scorer",
            "filtered_strict_no_regression": ">=22/22",
            "filtered_validation_no_regression": ">=20/22",
            "residual_bank_must_not_regress": ">=5/10",
            "promotion_requires_residual_improvement": ">5/10",
        },
        "source_artifacts": {
            "new_rust_train_rows": rel(TRAIN),
            "readiness_decision": rel(READINESS),
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
    write_json(COMMAND_JSON, {"command": command})
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"passed": allowed, **summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
