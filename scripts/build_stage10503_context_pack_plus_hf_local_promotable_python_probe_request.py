#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10503
NAME = "stage10503_context_pack_plus_hf_local_promotable_python_probe_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "context_pack_plus_hf_local_promotable_python_probe_request.json"
MANIFEST_JSONL = OUT_DIR / "context_pack_plus_hf_local_promotable_python_probe_manifest.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

QUALIFIED_ROWS = ROOT / "runs/local/artifacts/stage10502_python_verifier_packet_refresh/python_verifier_reviewed_support_rows.jsonl"
STRICT_OVERLAY = ROOT / "runs/local/artifacts/stage10436_repaired_v27_strict_overlay/repaired_v27_strict_overlay.jsonl"
INIT_RUNTIME = ROOT / "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/runtime_model/runtime_model_bundle.json"
PROMOTION_GATE = ROOT / "runs/local/artifacts/stage10461_reviewed_v27_residual_promotion_gate/reviewed_v27_residual_promotion_gate.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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
    support_rows = load_jsonl(QUALIFIED_ROWS)
    strict_rows_raw = load_jsonl(STRICT_OVERLAY)
    strict_rows: list[dict[str, Any]] = []
    for row in strict_rows_raw:
        updated = dict(row)
        updated["expected_enabled_loss"] = "decoder_ce"
        updated["loss_mask"] = {"decoder_ce": True}
        updated["disable_losses"] = ["denoise_ce", "runtime_reward", "structured_aux"]
        strict_rows.append(updated)

    manifest_rows = support_rows + strict_rows
    write_jsonl(MANIFEST_JSONL, manifest_rows)

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
        str(ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"),
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
        str(ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"),
        "--tokenizer-json",
        str(ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"),
        "--tokenizer-config",
        str(ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"),
        "--tokenizer-hashlock",
        str(ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"),
        "--execution-authorized-for-recovery-probe",
        "--max-train-rows",
        str(len(support_rows)),
        "--max-eval-rows",
        "0",
        "--max-strict-rows",
        "24",
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
        "16",
        "--max-generation-tokens",
        "8",
        "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness",
        "--runtime-model-save-dir",
        str(ROOT / "runs/local/artifacts/stage10503_context_pack_plus_hf_local_promotable_python_probe/runtime_model"),
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
        str(ROOT / "runs/local/artifacts/stage10503_context_pack_plus_hf_local_promotable_python_probe/bounded_decoder_probe"),
        "--run-id",
        "stage10503_context_pack_plus_hf_local_promotable_python_probe",
    ]

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "context_pack_plus_hf_local_promotable_python_probe_ready",
        "claim_scope": [
            "Run the next clean promotable Python-only probe using the previously qualified context_pack root plus the newly repaired hf_local verifier packet.",
            "Keep the interpretation narrow: this probe tests whether richer reviewed verifier support moves the repaired v2.7 frontier without bringing in blocked agentkernel scaffolding.",
        ],
        "diagnostic_boundaries": {
            "agentkernel_excluded": True,
            "python_only": True,
            "same_surface_strict_overlay_retained": True,
            "hf_local_v3_neighbor_weaker_than_ideal": True,
        },
        "source_artifacts": {
            "qualified_rows": display(QUALIFIED_ROWS),
            "strict_overlay": display(STRICT_OVERLAY),
            "initialize_runtime_model": display(INIT_RUNTIME),
            "promotion_gate": display(PROMOTION_GATE),
        },
        "manifest": display(MANIFEST_JSONL),
        "command": command,
        "train_bundle_ids": sorted({row["source_bundle_id"] for row in support_rows}),
        "train_task_types": sorted({row["task_type"] for row in support_rows}),
        "split_counts": {
            "train": len(support_rows),
            "strict_eval": len(strict_rows),
        },
        "success_criteria": [
            "Strict constrained accuracy must exceed 22/24 with zero regressions to be promotion-interesting.",
            "Python verifier residual should improve in rank or flip; unchanged plateau means fresh Python verifier roots are still required.",
            "Overlay leak audit and repaired hf_local anti-cheat assumptions must remain clean.",
        ],
        "promotion_gate_requirements": [
            "Strict constrained accuracy must exceed 22/24.",
            "Regression count must remain zero relative to the live repaired-overlay baseline.",
            "A fresh disjoint residual-root artifact must show the same improvement on unseen roots.",
            "Overlay leak audit must remain clean.",
        ],
        "outputs": {
            "request_json": display(REQUEST_JSON),
            "manifest": display(MANIFEST_JSONL),
        },
    }

    write_json(REQUEST_JSON, payload)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "manifest": display(MANIFEST_JSONL),
            "train_rows": len(support_rows),
            "strict_rows": len(strict_rows),
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
