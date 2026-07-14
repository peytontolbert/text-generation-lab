#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10489
NAME = "stage10489_deleaked_python_promotable_probe_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "deleaked_python_promotable_probe_request.json"
MANIFEST_JSONL = OUT_DIR / "deleaked_python_promotable_probe_manifest.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

SUPPORT_ROWS = ROOT / "runs/local/artifacts/stage10487_deleaked_python_verifier_support_package/deleaked_python_verifier_support_rows.jsonl"
STRICT_OVERLAY = ROOT / "runs/local/artifacts/stage10436_repaired_v27_strict_overlay/repaired_v27_strict_overlay.jsonl"
ANTI_CHEAT_AUDIT = ROOT / "runs/local/artifacts/stage10488_deleaked_python_verifier_anti_cheat_audit/deleaked_python_verifier_anti_cheat_audit.json"
PROMOTION_GATE = ROOT / "runs/local/artifacts/stage10461_reviewed_v27_residual_promotion_gate/reviewed_v27_residual_promotion_gate.json"
INIT_RUNTIME = ROOT / "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/runtime_model/runtime_model_bundle.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"

RUN_ID = "stage10490_deleaked_python_promotable_probe"
OUTPUT_DIR = ROOT / "runs/local/artifacts/stage10490_deleaked_python_promotable_probe/bounded_decoder_probe"
RUNTIME_MODEL_DIR = ROOT / "runs/local/artifacts/stage10490_deleaked_python_promotable_probe/runtime_model"


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
    for row in load_jsonl(STRICT_OVERLAY):
        updated = dict(row)
        updated["disable_losses"] = ["denoise_ce", "runtime_reward", "structured_aux"]
        updated["expected_enabled_loss"] = "decoder_ce"
        updated["loss_mask"] = {"decoder_ce": True}
        rows.append(updated)
    return rows


def build_command(train_count: int, strict_count: int) -> list[str]:
    return [
        "env", "TMPDIR=/data/tmp", "TEMP=/data/tmp", "TMP=/data/tmp",
        "conda", "run", "-n", "trellis", "python", str(TRAINER),
        "--repo-root", str(ROOT),
        "--manifest", str(MANIFEST_JSONL),
        "--mode", "bounded_decoder_ce_probe",
        "--probe-scale", "target_100m",
        "--implementation", "transformer",
        "--model-config", str(MODEL_CONFIG),
        "--tokenizer-json", str(TOKENIZER_JSON),
        "--tokenizer-config", str(TOKENIZER_CONFIG),
        "--tokenizer-hashlock", str(TOKENIZER_HASHLOCK),
        "--execution-authorized-for-recovery-probe",
        "--max-train-rows", str(train_count),
        "--max-eval-rows", "0",
        "--max-strict-rows", str(strict_count),
        "--max-steps", "24",
        "--batch-size", "2",
        "--learning-rate", "6e-6",
        "--max-encoder-tokens", "768",
        "--max-decoder-tokens", "8",
        "--decoder-ce-weight", "0.2",
        "--bounded-choice-aux-weight", "1.0",
        "--bounded-choice-aux-source", "encoder_option_retrieval",
        "--structured-aux-weight", "0.0",
        "--denoise-weight", "0.0",
        "--eos-loss-weight", "4.0",
        "--enable-generation-audit",
        "--max-generation-rows", "12",
        "--max-generation-tokens", "8",
        "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness",
        "--runtime-model-save-dir", str(RUNTIME_MODEL_DIR),
        "--initialize-from-runtime-model", str(INIT_RUNTIME),
        "--preservation-reference-runtime-model", str(INIT_RUNTIME),
        "--preservation-kl-weight", "2.0",
        "--no-final-checkpoint-export",
        "--skip-final-model-save", "1",
        "--output-dir", str(OUTPUT_DIR),
        "--run-id", RUN_ID,
    ]


def main() -> None:
    support_rows = load_jsonl(SUPPORT_ROWS)
    strict_rows = normalized_strict_rows()
    anti_cheat = load_json(ANTI_CHEAT_AUDIT)
    gate = load_json(PROMOTION_GATE)
    manifest_rows = support_rows + strict_rows
    write_jsonl(MANIFEST_JSONL, manifest_rows)

    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(support_rows) and anti_cheat["passed"],
        "decision": "deleaked_python_promotable_probe_ready",
        "claim_scope": [
            "Run the first promotable Python-only residual-support probe from a leak-clean, root-disjoint support lane.",
            "Keep Rust out of the train side so any movement can be attributed cleanly to the honest Python verifier support.",
        ],
        "source_artifacts": {
            "support_rows": display(SUPPORT_ROWS),
            "strict_overlay": display(STRICT_OVERLAY),
            "anti_cheat_audit": display(ANTI_CHEAT_AUDIT),
            "initialize_runtime_model": display(INIT_RUNTIME),
            "promotion_gate": display(PROMOTION_GATE),
        },
        "rows": len(manifest_rows),
        "split_counts": {"train": len(support_rows), "strict_eval": len(strict_rows)},
        "manifest": display(MANIFEST_JSONL),
        "command": build_command(len(support_rows), len(strict_rows)),
        "strict_focus_row": "stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_28t20_02_25_019acc0f_4bd7_77f2_b15f_3b0c_models_mirrormind_init_py_models_mirrormind_context_py_models_mirrormind_coordin_fd8013631e_aug_1500000_8b46e7f662::python::verifier_outcome::reviewed_v27_compact",
        "success_criteria": [
            "Python strict verifier_outcome flips from wrong to correct on the repaired strict overlay.",
            "No new strict regressions are introduced.",
            "Strict constrained accuracy exceeds 22/24.",
        ],
        "promotion_gate_requirements": gate["required_for_future_promotion"],
        "required_honesty_gates": [
            "Support lane passed stage10488 anti-cheat audit.",
            "Only de-leaked Python verifier rows are added to train.",
            "Rust remains excluded from this promotable probe.",
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
