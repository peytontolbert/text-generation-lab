#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9798
NAME = "stage9798_opaque_choice_bounded_decoder_preexecution"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9797_opaque_choice_bounded_decoder_manifest.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9797_opaque_choice_bounded_decoder_manifest/opaque_choice_bounded_decoder_manifest.jsonl"
OUTPUT_DIR = ROOT / "runs/local/artifacts/stage9799_opaque_choice_bounded_decoder_probe"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "opaque_choice_bounded_decoder_preexecution_audit.json"
COMMAND_JSON = OUT_DIR / "stage9799_opaque_choice_bounded_decoder_probe_command.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "OPAQUE_CHOICE_BOUNDED_DECODER_PREEXECUTION_STAGE9798.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")

AUTHORITY_RUN = dict(AUTHORITY_CLOSED)
AUTHORITY_RUN["model_execution_authorized_next"] = True
AUTHORITY_RUN["decoder_ce_training_authorized_next"] = True

COMMAND = [
    "env", f"TMPDIR={TMPDIR}", f"TEMP={TMPDIR}", f"TMP={TMPDIR}",
    "conda", "run", "-n", "trellis", "python", str(TRAINER),
    "--repo-root", str(ROOT), "--manifest", str(MANIFEST),
    "--mode", "bounded_decoder_ce_probe", "--probe-scale", "target_100m", "--implementation", "transformer",
    "--model-config", str(MODEL_CONFIG), "--tokenizer-json", str(TOKENIZER_JSON),
    "--tokenizer-config", str(TOKENIZER_CONFIG), "--tokenizer-hashlock", str(TOKENIZER_HASHLOCK),
    "--max-train-rows", "20", "--max-eval-rows", "20", "--max-strict-rows", "20",
    "--max-steps", "64", "--batch-size", "2", "--learning-rate", "5e-5",
    "--max-encoder-tokens", "512", "--max-decoder-tokens", "4",
    "--decoder-ce-weight", "1.0", "--structured-aux-weight", "0.0", "--denoise-weight", "0.0", "--eos-loss-weight", "1.0",
    "--enable-generation-audit", "--max-generation-rows", "20", "--max-generation-tokens", "4",
    "--require-loss-mask-enforcement-audit", "--no-final-checkpoint-export", "--cleanup-checkpoints-after-probe", "--skip-final-model-save", "1",
    "--execution-authorized-for-recovery-probe", "--output-dir", str(OUTPUT_DIR), "--run-id", "stage9799_opaque_choice_bounded_decoder_probe",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def has_pair(flag: str, value: str) -> bool:
    return any(COMMAND[i] == flag and COMMAND[i + 1] == value for i in range(len(COMMAND) - 1))


def audit() -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    rows = load_jsonl(MANIFEST)
    split_counts = Counter(str(row.get("split") or "") for row in rows)
    language_counts = Counter(str(row.get("language_family") or "") for row in rows)
    loss_counts = Counter()
    unsafe = []
    authority_rows = []
    target_visible = []
    for row in rows:
        row_id = str(row.get("row_id") or "")
        mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        auth = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        for key, value in mask.items():
            loss_counts[str(key)] += int(bool(value))
        enabled = [key for key, value in mask.items() if value]
        if enabled != ["decoder_ce"]:
            unsafe.append(row_id)
        if any(bool(auth.get(key)) for key in AUTHORITY_CLOSED):
            authority_rows.append(row_id)
    failures = []
    if source.get("passed") is not True:
        failures.append("source_stage9797_not_passed")
    if len(rows) != 60:
        failures.append("unexpected_manifest_row_count")
    if dict(split_counts) != {"train": 20, "eval": 20, "strict_eval": 20}:
        failures.append("unexpected_split_counts")
    if dict(language_counts) != {"c_cpp": 15, "python": 15, "rust": 15, "web_js_ts_html": 15}:
        failures.append("unexpected_language_counts")
    if int(loss_counts.get("decoder_ce") or 0) != 60:
        failures.append("unexpected_loss_counts")
    forbidden = [key for key, value in loss_counts.items() if key != "decoder_ce" and value]
    if forbidden:
        failures.append("forbidden_loss_counts")
    if unsafe:
        failures.append("unsafe_loss_rows")
    if authority_rows:
        failures.append("authority_rows")
    pairs = {
        "--mode": "bounded_decoder_ce_probe",
        "--probe-scale": "target_100m",
        "--max-train-rows": "20",
        "--max-eval-rows": "20",
        "--max-strict-rows": "20",
        "--max-steps": "64",
        "--decoder-ce-weight": "1.0",
        "--structured-aux-weight": "0.0",
        "--denoise-weight": "0.0",
        "--eos-loss-weight": "1.0",
        "--max-decoder-tokens": "4",
    }
    for flag, value in pairs.items():
        if not has_pair(flag, value):
            failures.append(f"missing_pair:{flag}={value}")
    for flag in ["--execution-authorized-for-recovery-probe", "--require-loss-mask-enforcement-audit", "--no-final-checkpoint-export", "--cleanup-checkpoints-after-probe", "--enable-generation-audit"]:
        if flag not in COMMAND:
            failures.append(f"missing_flag:{flag}")
    return {
        "passed": not failures,
        "failures": failures,
        "manifest_rows": len(rows),
        "manifest_sha256": sha256(MANIFEST),
        "split_counts": dict(sorted(split_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "unsafe_rows": unsafe[:20],
        "authority_rows": authority_rows[:20],
        "target_visible_rows": target_visible[:20],
        "command": COMMAND,
        "command_ready": not failures,
        "authority": AUTHORITY_RUN if not failures else dict(AUTHORITY_CLOSED),
    }


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": summary["authority"], "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    card = audit()
    AUDIT.write_text(json.dumps({k: v for k, v in card.items() if k != "command"}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    COMMAND_JSON.write_text(json.dumps({"command": COMMAND, "cwd": str(ROOT), "env": "trellis", "tmpdir": str(TMPDIR)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": card["passed"],
        "authority": card["authority"],
        "metrics": {**{key: bool(card["authority"].get(key, False)) for key in AUTHORITY_CLOSED}, "command_ready": card["command_ready"], "manifest_rows": card["manifest_rows"], "manifest_sha256": card["manifest_sha256"], "split_counts": card["split_counts"], "language_counts": card["language_counts"], "loss_counts": card["loss_counts"], "failures": len(card["failures"])},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "command": str(COMMAND_JSON.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Prepared a bounded decoder CE execution ticket for the corrected Stage9790 opaque-choice surface so the model can learn the A-E output protocol through the decoder path.",
        "next_best_step": "Execute Stage9799 bounded decoder CE probe under trellis, then compare it against Stage9794 and Gemma on the same strict-eval rows before deciding whether decoder CE improved the multilingual head-to-head position.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9798 Opaque Choice Bounded Decoder Preexecution",
        "",
        f"Passed: `{card['passed']}`",
        f"Rows: `{card['manifest_rows']}`",
        f"Splits: `{card['split_counts']}`",
        f"Languages: `{card['language_counts']}`",
        f"Losses: `{card['loss_counts']}`",
        f"Command ready: `{card['command_ready']}`",
        "",
        "This stage opens exactly one bounded decoder CE execution ticket on the corrected opaque-choice surface. It is intended to test whether decoder-side learning improves the multilingual comparison without reintroducing leakage or generation collapse.",
        "",
        f"Next: {summary['next_best_step']}",
        "",
    ]) + "\n", encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
