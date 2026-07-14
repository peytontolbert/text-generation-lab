#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10439
NAME = "stage10439_python_verifier_disjoint_support_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "python_verifier_disjoint_support_request.json"
MANIFEST_JSONL = OUT_DIR / "python_verifier_disjoint_support_manifest.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

STRICT_OVERLAY_JSONL = ROOT / "runs/local/artifacts/stage10436_repaired_v27_strict_overlay/repaired_v27_strict_overlay.jsonl"
PYTHON_SUPPLY_JSONL = ROOT / "runs/local/artifacts/stage10327_python_mirrormind_replenishment_execution_request/python_mirrormind_replenishment_manifest.jsonl"
INIT_RUNTIME = ROOT / "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/runtime_model/runtime_model_bundle.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    strict_rows = load_jsonl(STRICT_OVERLAY_JSONL)
    supply_rows = load_jsonl(PYTHON_SUPPLY_JSONL)

    normalized_strict_rows = []
    for row in strict_rows:
        updated = dict(row)
        updated["disable_losses"] = ["denoise_ce", "runtime_reward", "structured_aux"]
        updated["expected_enabled_loss"] = "decoder_ce"
        updated["loss_mask"] = {"decoder_ce": True}
        normalized_strict_rows.append(updated)

    train_rows = [
        row for row in supply_rows
        if row.get("split") == "train"
        and row.get("language_family") == "python"
        and row.get("task_type") == "verifier_outcome"
        and "stage10327::" in str(row.get("row_id") or "")
    ]
    train_rows.sort(key=lambda row: str(row["row_id"]))

    manifest_rows = train_rows + normalized_strict_rows
    write_jsonl(MANIFEST_JSONL, manifest_rows)

    split_counts = {"train": len(train_rows), "strict_eval": len(strict_rows)}
    command = [
        "env",
        "TMPDIR=/data/tmp",
        "TEMP=/data/tmp",
        "TMP=/data/tmp",
        "conda",
        "run",
        "-n",
        "trellis",
        "python",
        str(TRAINER),
        "--repo-root",
        str(ROOT),
        "--manifest",
        str(MANIFEST_JSONL),
        "--mode",
        "bounded_decoder_ce_probe",
        "--probe-scale",
        "target_100m",
        "--implementation",
        "transformer",
        "--model-config",
        str(MODEL_CONFIG),
        "--tokenizer-json",
        str(TOKENIZER_JSON),
        "--tokenizer-config",
        str(TOKENIZER_CONFIG),
        "--tokenizer-hashlock",
        str(TOKENIZER_HASHLOCK),
        "--execution-authorized-for-recovery-probe",
        "--max-train-rows",
        str(split_counts["train"]),
        "--max-eval-rows",
        "0",
        "--max-strict-rows",
        str(split_counts["strict_eval"]),
        "--max-steps",
        "24",
        "--batch-size",
        "2",
        "--learning-rate",
        "6e-6",
        "--max-encoder-tokens",
        "768",
        "--max-decoder-tokens",
        "8",
        "--decoder-ce-weight",
        "0.2",
        "--bounded-choice-aux-weight",
        "1.0",
        "--bounded-choice-aux-source",
        "encoder_option_retrieval",
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
        "8",
        "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness",
        "--runtime-model-save-dir",
        str(ROOT / "runs/local/artifacts/stage10440_python_verifier_disjoint_support_probe/runtime_model"),
        "--initialize-from-runtime-model",
        str(INIT_RUNTIME),
        "--preservation-reference-runtime-model",
        str(INIT_RUNTIME),
        "--preservation-kl-weight",
        "2.0",
        "--no-final-checkpoint-export",
        "--skip-final-model-save",
        "1",
        "--output-dir",
        str(ROOT / "runs/local/artifacts/stage10440_python_verifier_disjoint_support_probe/bounded_decoder_probe"),
        "--run-id",
        "stage10440_python_verifier_disjoint_support_probe",
    ]

    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "fresh_python_verifier_disjoint_support_ready",
        "claim_scope": [
            "Targeted disjoint Python verifier support request against the hardened repaired-v2.7 strict overlay.",
            "Train only on stage10327 Mirrormind-style disjoint verifier rows; do not replay current strict rows into train.",
            "Use the stage10422 runtime as the preserved baseline.",
        ],
        "source_artifacts": {
            "strict_overlay": display(STRICT_OVERLAY_JSONL),
            "python_supply_manifest": display(PYTHON_SUPPLY_JSONL),
            "initialize_runtime_model": display(INIT_RUNTIME),
        },
        "rows": len(manifest_rows),
        "split_counts": split_counts,
        "train_row_ids": [row["row_id"] for row in train_rows],
        "strict_focus_row": "stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_28t20_02_25_019acc0f_4bd7_77f2_b15f_3b0c_models_mirrormind_init_py_models_mirrormind_context_py_models_mirrormind_coordin_fd8013631e_aug_1500000_8b46e7f662::python::verifier_outcome::reviewed_v27_compact",
        "manifest": display(MANIFEST_JSONL),
        "command": command,
        "success_criteria": [
            "Python strict verifier_outcome flips from wrong to correct on the repaired strict overlay.",
            "No more than one new strict regression elsewhere.",
            "Post-run reporting must keep the repaired overlay claim boundary separate from the live v2.7 package until the overlay is promoted.",
        ],
        "required_honesty_gates": [
            "No same-root replay from the current strict overlay into train.",
            "Train rows remain disjoint stage10327 supply only.",
            "Any improvement claim must reference the repaired strict overlay, not the live package, until promotion is explicit.",
        ],
        "outputs": {
            "request_json": display(REQUEST_JSON),
            "manifest": display(MANIFEST_JSONL),
        },
    }
    write_json(REQUEST_JSON, request)
    write_json(SUMMARY, request)
    print(json.dumps(request, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
