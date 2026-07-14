#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10292
NAME = "stage10292_hard_perspective_support_execution_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST = OUT_DIR / "hard_perspective_support_execution_request.json"
COMMAND_JSON = OUT_DIR / "hard_perspective_support_command.json"
MANIFEST = OUT_DIR / "hard_perspective_support_manifest.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

BASE_MANIFEST = ROOT / (
    "runs/local/artifacts/"
    "stage10274_frontier_preserving_code_assist_overlay_execution_request/"
    "frontier_preserving_code_assist_overlay_manifest.jsonl"
)
COUNTERBALANCE_MANIFEST = ROOT / (
    "runs/local/artifacts/"
    "stage10248_weakness_counterbalance_execution_request/"
    "weakness_counterbalance_manifest.jsonl"
)
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
INIT_RUNTIME = ROOT / (
    "runs/local/artifacts/"
    "stage10278_frontier_runtime_bundle_probe/runtime_model/runtime_model_bundle.json"
)
TMPDIR = Path("/data/tmp")

RUN_ID = "stage10293_hard_perspective_support_probe"
OUTPUT_DIR = "runs/local/artifacts/stage10293_hard_perspective_support_probe/bounded_decoder_probe"
RUNTIME_MODEL_DIR = "runs/local/artifacts/stage10293_hard_perspective_support_probe/runtime_model"
MAX_STEPS = 48
LEARNING_RATE = "8e-6"

TARGET_PERSPECTIVES = {
    "abstention_insufficient_evidence",
    "verifier_outcome",
    "evidence_citation",
}
SCRIPTS_UNIVERSE_FAMILY = "scripts_universe_build_py_64d2cf209b"
WEB_440_FAMILY = "src_main_js_index_html_440e122a0f"
MIRRORMIND_FAMILY = "models_mirrormind_init_py_models_mirrormind_context_py_models_mirrormind_coordin_fd8013631e"
WEB_F0_FAMILY = "index_html_f0be60dc44"


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


def extract_perspective(row: dict[str, Any]) -> str:
    row_id = str(row.get("row_id", ""))
    for token in row_id.split("::"):
        if token in TARGET_PERSPECTIVES:
            return token
    return str(row.get("task_type") or row.get("perspective") or "unknown")


def split_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        counts[str(row.get("split", "unknown"))] += 1
    return dict(sorted(counts.items()))


def count_focus_rows(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        counts[extract_perspective(row)] += 1
    return dict(sorted(counts.items()))


def dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        row_id = str(row.get("row_id", ""))
        if row_id in seen:
            continue
        seen.add(row_id)
        out.append(row)
    return out


def command(counts: dict[str, int]) -> list[str]:
    return [
        "env",
        f"TMPDIR={TMPDIR}",
        f"TEMP={TMPDIR}",
        f"TMP={TMPDIR}",
        "conda",
        "run",
        "-n",
        "trellis",
        "python",
        str(TRAINER),
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
        str(MODEL_CONFIG),
        "--tokenizer-json",
        str(TOKENIZER_JSON),
        "--tokenizer-config",
        str(TOKENIZER_CONFIG),
        "--tokenizer-hashlock",
        str(TOKENIZER_HASHLOCK),
        "--execution-authorized-for-recovery-probe",
        "--max-train-rows",
        str(counts.get("train", 0)),
        "--max-eval-rows",
        "0",
        "--max-strict-rows",
        str(counts.get("strict_eval", 0)),
        "--max-steps",
        str(MAX_STEPS),
        "--batch-size",
        "2",
        "--learning-rate",
        LEARNING_RATE,
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
        "--allow-runtime-model-save-for-harness",
        "--runtime-model-save-dir",
        str(ROOT / RUNTIME_MODEL_DIR),
        "--initialize-from-runtime-model",
        str(INIT_RUNTIME),
        "--no-final-checkpoint-export",
        "--skip-final-model-save",
        "1",
        "--output-dir",
        str(ROOT / OUTPUT_DIR),
        "--run-id",
        RUN_ID,
    ]


def build_request() -> dict[str, Any]:
    base_rows = load_jsonl(BASE_MANIFEST)
    counter_rows = load_jsonl(COUNTERBALANCE_MANIFEST)

    base_train = [row for row in base_rows if row.get("split") == "train"]
    strict_eval = [row for row in base_rows if row.get("split") == "strict_eval"]
    other_rows = [row for row in base_rows if row.get("split") not in {"train", "strict_eval"}]

    extra_counterbalance = [
        row for row in counter_rows
        if row.get("split") == "train"
        and SCRIPTS_UNIVERSE_FAMILY in str(row.get("row_id", ""))
        and extract_perspective(row) in TARGET_PERSPECTIVES
    ]

    focused_base = [
        row for row in base_train
        if extract_perspective(row) in TARGET_PERSPECTIVES
        and (
            SCRIPTS_UNIVERSE_FAMILY in str(row.get("row_id", ""))
            or WEB_440_FAMILY in str(row.get("row_id", ""))
        )
    ]
    rest_base = [
        row for row in base_train
        if row not in focused_base
    ]

    train_rows = dedupe_rows([*extra_counterbalance, *focused_base, *rest_base])
    rows = [*train_rows, *strict_eval, *other_rows]
    counts = split_counts(rows)

    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": (
            "Build a narrow successor from the saved frontier that preserves the current "
            "strict packet unchanged, initializes from the saved runtime bundle, and "
            "frontloads the only honest hard-perspective train support currently available: "
            "Python scripts_universe abstention/evidence/verifier rows and Web web_440 "
            "abstention/verifier/evidence rows."
        ),
        "next_best_step": (
            "Run this 48-step recovery probe, then re-score it on the stage10288 lower-cue "
            "packet and the stage10291 hard-perspective challenge. Promote only if it "
            "narrows Python/Web weakness without breaking the broader lower-cue win."
        ),
        "source_manifests": {
            "frontier_manifest": display(BASE_MANIFEST),
            "counterbalance_manifest": display(COUNTERBALANCE_MANIFEST),
        },
        "manifest": display(MANIFEST),
        "rows": len(rows),
        "split_counts": counts,
        "output_dir": OUTPUT_DIR,
        "run_id": RUN_ID,
        "initialize_from_runtime_model": display(INIT_RUNTIME),
        "learning_rate": LEARNING_RATE,
        "max_steps": MAX_STEPS,
        "focus_families": {
            "python_supported": SCRIPTS_UNIVERSE_FAMILY,
            "web_supported": WEB_440_FAMILY,
            "python_unsupported_holdout": MIRRORMIND_FAMILY,
            "web_unsupported_holdout": WEB_F0_FAMILY,
        },
        "frontloaded_focus_counts": {
            "counterbalance_added": len(extra_counterbalance),
            "counterbalance_by_perspective": count_focus_rows(extra_counterbalance),
            "base_frontloaded": len(focused_base),
            "base_frontloaded_by_perspective": count_focus_rows(focused_base),
        },
        "required_honesty_gates": [
            "strict eval rows remain identical to stage10274/stage10278",
            "no Mirrormind or web_f0 holdout rows are moved into train",
            "any gain on Python/Web must be described as support-family improvement, not as direct repair of unsupported holdout families",
        ],
        "command": command(counts),
    }
    write_jsonl(MANIFEST, rows)
    write_json(REQUEST, request)
    write_json(COMMAND_JSON, {"command": request["command"], "cwd": str(ROOT), "env": "trellis", "tmpdir": str(TMPDIR)})
    write_json(SUMMARY, {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": True,
        "request": display(REQUEST),
        "manifest": display(MANIFEST),
        "frontloaded_focus_counts": request["frontloaded_focus_counts"],
    })
    return request


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    payload = build_request()
    print(json.dumps({
        "stage": STAGE,
        "passed": True,
        "request": display(REQUEST),
        "manifest": display(MANIFEST),
        "frontloaded_focus_counts": payload["frontloaded_focus_counts"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
