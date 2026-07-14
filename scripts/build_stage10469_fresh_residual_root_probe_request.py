#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10469
NAME = "stage10469_fresh_residual_root_probe_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "fresh_residual_root_probe_request.json"
MANIFEST_JSONL = OUT_DIR / "fresh_residual_root_probe_manifest.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

SUPPORT_ROWS_JSONL = ROOT / "runs/local/artifacts/stage10468_fresh_residual_root_support_package/fresh_residual_root_support_rows.jsonl"
STRICT_OVERLAY_JSONL = ROOT / "runs/local/artifacts/stage10436_repaired_v27_strict_overlay/repaired_v27_strict_overlay.jsonl"
PROMOTION_GATE = ROOT / "runs/local/artifacts/stage10461_reviewed_v27_residual_promotion_gate/reviewed_v27_residual_promotion_gate.json"
PACKAGE_JSON = ROOT / "runs/local/artifacts/stage10468_fresh_residual_root_support_package/fresh_residual_root_support_package.json"
INIT_RUNTIME = ROOT / "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/runtime_model/runtime_model_bundle.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"

RUN_ID = "stage10470_fresh_residual_root_probe"
OUTPUT_DIR = ROOT / "runs/local/artifacts/stage10470_fresh_residual_root_probe/bounded_decoder_probe"
RUNTIME_MODEL_DIR = ROOT / "runs/local/artifacts/stage10470_fresh_residual_root_probe/runtime_model"


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


def normalized_strict_rows() -> list[dict[str, Any]]:
    rows = []
    for row in load_jsonl(STRICT_OVERLAY_JSONL):
        updated = dict(row)
        updated["disable_losses"] = ["denoise_ce", "runtime_reward", "structured_aux"]
        updated["expected_enabled_loss"] = "decoder_ce"
        updated["loss_mask"] = {"decoder_ce": True}
        rows.append(updated)
    return rows


def build_command(train_count: int, strict_count: int) -> list[str]:
    return [
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
        str(train_count),
        "--max-eval-rows",
        "0",
        "--max-strict-rows",
        str(strict_count),
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
        str(RUNTIME_MODEL_DIR),
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
        str(OUTPUT_DIR),
        "--run-id",
        RUN_ID,
    ]


def main() -> None:
    support_rows = load_jsonl(SUPPORT_ROWS_JSONL)
    strict_rows = normalized_strict_rows()
    package = load_json(PACKAGE_JSON)
    gate = load_json(PROMOTION_GATE)

    manifest_rows = support_rows + strict_rows
    write_jsonl(MANIFEST_JSONL, manifest_rows)

    train_task_counts: dict[str, int] = {}
    train_language_counts: dict[str, int] = {}
    for row in support_rows:
        task = str(row.get("task_type") or "unknown")
        lang = str(row.get("language_family") or "unknown")
        train_task_counts[task] = train_task_counts.get(task, 0) + 1
        train_language_counts[lang] = train_language_counts.get(lang, 0) + 1

    command = build_command(len(support_rows), len(strict_rows))
    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(support_rows) and bool(strict_rows),
        "decision": "fresh_residual_root_probe_ready",
        "claim_scope": [
            "Diagnostic preserved-runtime probe against the repaired v2.7 strict overlay using the new fresh residual support package.",
            "This probe can validate movement on the live residuals, but it is not promotable evidence for Rust until a true fresh-root Rust bundle exists beyond candle-core interim support.",
            "Python movement can inform the promotable path because the executable support is root-disjoint code_assist supply.",
        ],
        "source_artifacts": {
            "support_package": display(PACKAGE_JSON),
            "support_rows": display(SUPPORT_ROWS_JSONL),
            "strict_overlay": display(STRICT_OVERLAY_JSONL),
            "initialize_runtime_model": display(INIT_RUNTIME),
            "promotion_gate": display(PROMOTION_GATE),
        },
        "rows": len(manifest_rows),
        "split_counts": {
            "train": len(support_rows),
            "strict_eval": len(strict_rows),
        },
        "train_task_counts": dict(sorted(train_task_counts.items())),
        "train_language_counts": dict(sorted(train_language_counts.items())),
        "strict_focus_rows": [
            "stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_28t20_02_25_019acc0f_4bd7_77f2_b15f_3b0c_models_mirrormind_init_py_models_mirrormind_context_py_models_mirrormind_coordin_fd8013631e_aug_1500000_8b46e7f662::python::verifier_outcome::reviewed_v27_compact",
            "stage10126::tokenizers::tokenizers::rust::evidence_citation::reviewed_v27_compact",
        ],
        "manifest": display(MANIFEST_JSONL),
        "command": command,
        "diagnostic_boundaries": {
            "python_promotable_component_present": True,
            "rust_promotable_component_present": False,
            "reason_rust_not_promotable_yet": package["required_honesty_gates"][3],
        },
        "success_criteria": [
            "Strict constrained accuracy must exceed 22/24 with zero new regressions to remain interesting.",
            "Python verifier residual should flip or show materially improved margin if the code_assist disjoint support is useful.",
            "Any Rust improvement is diagnostic-only until fresh non-tokenizers roots are built and reviewed.",
        ],
        "promotion_gate_requirements": gate["required_for_future_promotion"],
        "required_honesty_gates": [
            "No repaired strict overlay row is copied into train.",
            "Train rows remain stage10468 support only.",
            "Tokenizers same-surface rows remain absent from train.",
            "Any upgraded claim must still pass fresh-root audit requirements from stage10461.",
        ],
        "outputs": {
            "request_json": display(REQUEST_JSON),
            "manifest": display(MANIFEST_JSONL),
        },
    }
    write_json(REQUEST_JSON, request)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": request["passed"],
            "manifest": display(MANIFEST_JSONL),
            "split_counts": request["split_counts"],
            "request": display(REQUEST_JSON),
        },
    )
    print(json.dumps(request, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
