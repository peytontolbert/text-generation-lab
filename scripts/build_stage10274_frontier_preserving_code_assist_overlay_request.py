from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, UTC
from pathlib import Path


ROOT = Path("/data/agentkernel-seq2seq-text-lab")

BASE_MANIFEST = ROOT / (
    "runs/local/artifacts/"
    "stage10180_augmented_web_scaled_step_target100m_execution_request/"
    "augmented_web_scaled_step_target100m_manifest.jsonl"
)
SUPPORT_MANIFEST = ROOT / (
    "runs/local/artifacts/"
    "stage10266_code_assist_web_commit_compact_support_package/"
    "agentkernel_lite_encdec_train.jsonl"
)

OUT_DIR = ROOT / (
    "runs/local/artifacts/"
    "stage10274_frontier_preserving_code_assist_overlay_execution_request"
)
OUT_MANIFEST = OUT_DIR / "frontier_preserving_code_assist_overlay_manifest.jsonl"
OUT_REQUEST = OUT_DIR / "frontier_preserving_code_assist_overlay_execution_request.json"


PERSPECTIVE_ALLOWLIST = {
    "symptom_localization": 1,
    "patch_impact": 1,
    "minimal_fix_selection": 1,
    "abstention_insufficient_evidence": 1,
}


def now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def normalize_language(raw: str) -> str:
    if raw in {"tokenizers", "candle-core"}:
        return "rust"
    return raw


def extract_perspective(row_id: str) -> str:
    for token in row_id.split("::"):
        if token in PERSPECTIVE_ALLOWLIST:
            return token
    return "unknown"


def choose_overlay_rows(rows: list[dict]) -> list[dict]:
    selected: list[dict] = []
    seen: Counter[str] = Counter()
    for row in rows:
        row_id = row["row_id"]
        if "stage10264::code_assist_git_commit" not in row_id:
            continue
        perspective = extract_perspective(row_id)
        if perspective not in PERSPECTIVE_ALLOWLIST:
            continue
        if seen[perspective] >= PERSPECTIVE_ALLOWLIST[perspective]:
            continue
        selected.append(row)
        seen[perspective] += 1
    return selected


def count_labels(rows: list[dict]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        target = row.get("target_text") or row.get("target") or row.get("label")
        counts[str(target)] += 1
    return dict(sorted(counts.items()))


def count_languages(rows: list[dict]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    known = {"c_cpp", "python", "rust", "web_js_ts_html"}
    for row in rows:
        parts = row["row_id"].split("::")
        if len(parts) > 3 and parts[0] == "stage10264" and parts[1] == "code_assist_git_commit":
            raw = parts[3]
        else:
            raw = next((part for part in parts if part in known), parts[2] if len(parts) > 2 else "unknown")
        counts[normalize_language(raw)] += 1
    return dict(sorted(counts.items()))


def count_splits(rows: list[dict]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        counts[row.get("split", "unknown")] += 1
    return dict(sorted(counts.items()))


def main() -> None:
    base_rows = read_jsonl(BASE_MANIFEST)
    support_rows = read_jsonl(SUPPORT_MANIFEST)
    overlay_rows = choose_overlay_rows(support_rows)
    merged_rows = [*base_rows, *overlay_rows]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_MANIFEST.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in merged_rows)
    )

    request = {
        "stage": 10274,
        "stage_name": "stage10274_frontier_preserving_code_assist_overlay_execution_request",
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": (
            "Rebuilt the next standalone request from the actual stage10180 frontier "
            "instead of the stale stage10149 base. This preserves the adjudicated "
            "stage10176 web replenishment rows and adds only a minimal stage10264 "
            "code_assist overlay on the web perspectives that remain weak."
        ),
        "next_best_step": (
            "Execute this repaired 224-step bounded-decoder probe in trellis and "
            "compare it directly against stage10181. Promote it only if it improves "
            "web support without regressing the existing Python frontier."
        ),
        "required_honesty_gates": [
            "stage10181 remains the standalone frontier unless this overlay run beats it on the unchanged strict packet",
            "stage10264 rows remain same-repo train support only and not source-heldout headline evidence",
            "strict eval remains unchanged from stage10180/stage10181",
        ],
        "source_packages": {
            "frontier_manifest": str(BASE_MANIFEST.relative_to(ROOT)),
            "overlay_support_manifest": str(SUPPORT_MANIFEST.relative_to(ROOT)),
        },
        "overlay_policy": {
            "preserve_stage10176_frontier_rows": True,
            "overlay_row_count": len(overlay_rows),
            "overlay_perspective_allowlist": PERSPECTIVE_ALLOWLIST,
            "overlay_row_ids": [row["row_id"] for row in overlay_rows],
        },
        "manifest": str(OUT_MANIFEST.relative_to(ROOT)),
        "rows": len(merged_rows),
        "split_counts": count_splits(merged_rows),
        "language_counts": count_languages(merged_rows),
        "label_counts": count_labels(merged_rows),
        "run_id": "stage10275_frontier_preserving_code_assist_overlay_probe",
        "output_dir": (
            "runs/local/artifacts/"
            "stage10275_frontier_preserving_code_assist_overlay_probe/"
            "bounded_decoder_probe"
        ),
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
            str(OUT_MANIFEST),
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
            str(count_splits(merged_rows).get("train", 0)),
            "--max-eval-rows",
            "0",
            "--max-strict-rows",
            str(count_splits(merged_rows).get("strict_eval", 0)),
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
            "--output-dir",
            "/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/"
            "stage10275_frontier_preserving_code_assist_overlay_probe/"
            "bounded_decoder_probe",
            "--run-id",
            "stage10275_frontier_preserving_code_assist_overlay_probe",
        ],
    }
    OUT_REQUEST.write_text(json.dumps(request, indent=2) + "\n")
    print(OUT_REQUEST)


if __name__ == "__main__":
    main()
