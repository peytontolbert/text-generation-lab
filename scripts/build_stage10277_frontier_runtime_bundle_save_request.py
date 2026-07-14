from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path("/data/agentkernel-seq2seq-text-lab")

MANIFEST = ROOT / (
    "runs/local/artifacts/"
    "stage10274_frontier_preserving_code_assist_overlay_execution_request/"
    "frontier_preserving_code_assist_overlay_manifest.jsonl"
)

OUT_DIR = ROOT / "runs/local/artifacts/stage10277_frontier_runtime_bundle_save_request"
RUNTIME_DIR = ROOT / "runs/local/artifacts/stage10278_frontier_runtime_bundle_probe/runtime_model"
PROBE_DIR = ROOT / "runs/local/artifacts/stage10278_frontier_runtime_bundle_probe/bounded_decoder_probe"
REQUEST = OUT_DIR / "frontier_runtime_bundle_save_request.json"


def now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_jsonl_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def count_split(rows: list[dict], split: str) -> int:
    return sum(1 for row in rows if row.get("split") == split)


def main() -> None:
    rows = read_jsonl_rows(MANIFEST)
    train_rows = count_split(rows, "train")
    strict_rows = count_split(rows, "strict_eval")

    request = {
        "stage": 10277,
        "stage_name": "stage10277_frontier_runtime_bundle_save_request",
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": (
            "Materialized a save-model rerun of the frontier-preserving standalone mix so "
            "the current frontier-equivalent 100M weights can be evaluated directly against "
            "Gemma on the multilingual admitted-bundle runtime and harness packets."
        ),
        "next_best_step": (
            "Execute this save-model probe in trellis, then swap the resulting runtime_model_bundle "
            "into the stage10240 and stage10244 payloads for direct 100M-versus-Gemma comparison."
        ),
        "required_honesty_gates": [
            "strict eval remains unchanged from the stage10181 frontier packet",
            "runtime model save is allowed only as a harness/runtime comparison artifact, not as a hidden checkpoint export",
            "promotion still requires same-surface comparison against Gemma after the bundle is saved",
        ],
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "rows": len(rows),
        "split_counts": {"train": train_rows, "strict_eval": strict_rows, "eval": 0, "other": 0},
        "run_id": "stage10278_frontier_runtime_bundle_probe",
        "runtime_model_save_dir": str(RUNTIME_DIR.relative_to(ROOT)),
        "output_dir": str(PROBE_DIR.relative_to(ROOT)),
        "command": [
            "env",
            "TMPDIR=/data/tmp",
            "TEMP=/data/tmp",
            "TMP=/data/tmp",
            "conda",
            "run",
            "-n",
            "trellis",
            "python",
            "/data/agentkernel-seq2seq-text-lab/legacy_src/scripts/train_agentkernel_lite_encdec.py",
            "--repo-root",
            "/data/agentkernel-seq2seq-text-lab",
            "--manifest",
            str(MANIFEST),
            "--mode",
            "bounded_decoder_ce_probe",
            "--probe-scale",
            "target_100m",
            "--implementation",
            "transformer",
            "--model-config",
            "/data/agentkernel-seq2seq-text-lab/configs/model/agentkernel_100m_seq2seq_recovered_target.json",
            "--tokenizer-json",
            "/data/agentkernel-seq2seq-text-lab/configs/tokenizer/agentkernel_bpe_1506/tokenizer.json",
            "--tokenizer-config",
            "/data/agentkernel-seq2seq-text-lab/configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json",
            "--tokenizer-hashlock",
            "/data/agentkernel-seq2seq-text-lab/configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json",
            "--execution-authorized-for-recovery-probe",
            "--max-train-rows",
            str(train_rows),
            "--max-eval-rows",
            "0",
            "--max-strict-rows",
            str(strict_rows),
            "--max-steps",
            "224",
            "--batch-size",
            "2",
            "--learning-rate",
            "5e-5",
            "--max-encoder-tokens",
            "768",
            "--max-decoder-tokens",
            "8",
            "--decoder-ce-weight",
            "0.25",
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
            "24",
            "--max-generation-tokens",
            "8",
            "--require-loss-mask-enforcement-audit",
            "--no-final-checkpoint-export",
            "--cleanup-checkpoints-after-probe",
            "--skip-final-model-save",
            "1",
            "--allow-runtime-model-save-for-harness",
            "--runtime-model-save-dir",
            str(RUNTIME_DIR),
            "--output-dir",
            str(PROBE_DIR),
            "--run-id",
            "stage10278_frontier_runtime_bundle_probe",
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REQUEST.write_text(json.dumps(request, indent=2) + "\n")
    print(REQUEST)


if __name__ == "__main__":
    main()
