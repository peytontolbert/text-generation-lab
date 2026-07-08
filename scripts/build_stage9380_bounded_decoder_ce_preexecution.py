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
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9380
NAME = "stage9380_bounded_decoder_ce_preexecution"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9379_bounded_decoder_ce_readiness_bridge.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9249_semantic_bounded_decoder_target_repair_package/semantic_bounded_decoder_target_repair_manifest.jsonl"
OUTPUT_DIR = ROOT / "runs/local/artifacts/stage9381_bounded_decoder_ce_probe"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "bounded_decoder_ce_preexecution_audit.json"
COMMAND_JSON = OUT_DIR / "stage9381_bounded_decoder_ce_probe_command.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BOUNDED_DECODER_CE_PREEXECUTION_STAGE9380.md"
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
    "--max-train-rows", "32", "--max-eval-rows", "16", "--max-strict-rows", "16",
    "--max-steps", "16", "--batch-size", "2", "--learning-rate", "1e-5",
    "--max-encoder-tokens", "256", "--max-decoder-tokens", "768",
    "--decoder-ce-weight", "1.0", "--structured-aux-weight", "0.0", "--denoise-weight", "0.0", "--eos-loss-weight", "4.0",
    "--enable-generation-audit", "--max-generation-rows", "16", "--max-generation-tokens", "96",
    "--require-loss-mask-enforcement-audit", "--no-final-checkpoint-export", "--cleanup-checkpoints-after-probe", "--skip-final-model-save", "1",
    "--execution-authorized-for-recovery-probe", "--output-dir", str(OUTPUT_DIR), "--run-id", "stage9381_bounded_decoder_ce_probe",
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
    split_counts = Counter(str(row.get("split")) for row in rows)
    language_counts = Counter(str(row.get("language_family") or row.get("language_group")) for row in rows)
    loss_counts = Counter()
    unsafe: list[str] = []
    over_cap: list[str] = []
    authority_rows: list[str] = []
    target_visible: list[str] = []
    for row in rows:
        row_id = str(row.get("row_id"))
        loss = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        auth = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        for key, value in loss.items():
            if value:
                loss_counts[str(key)] += 1
        non_decoder_enabled = [key for key, value in loss.items() if key != "decoder_ce" and value]
        if loss.get("decoder_ce") is not True or non_decoder_enabled:
            unsafe.append(row_id)
        if any(bool(auth.get(key)) for key in AUTHORITY_CLOSED):
            authority_rows.append(row_id)
        target_len = row.get("decoder_token_len") or row.get("target_token_len") or row.get("decoder_tokens")
        if isinstance(target_len, int) and target_len > 768:
            over_cap.append(row_id)
        model_input = json.dumps(row.get("model_input", {}), sort_keys=True)
        target = str(row.get("decoder_text") or row.get("target_text") or row.get("clean_target") or "")
        if target and target in model_input:
            target_visible.append(row_id)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9379_not_passed")
    if len(rows) != 64:
        failures.append("unexpected_manifest_row_count")
    if dict(split_counts) != {"train": 32, "eval": 16, "strict_eval": 16}:
        failures.append("unexpected_split_counts")
    if dict(language_counts) != {"cpp": 16, "python": 16, "rust": 16, "web_js_ts_html": 16}:
        failures.append("unexpected_language_counts")
    if dict(loss_counts) != {"decoder_ce": 64}:
        failures.append("unexpected_loss_counts")
    if unsafe:
        failures.append("unsafe_loss_rows")
    if authority_rows:
        failures.append("authority_rows")
    if over_cap:
        failures.append("over_cap_rows")
    if target_visible:
        failures.append("target_visible_in_model_input")
    if not str(OUTPUT_DIR.resolve()).startswith(str((ROOT / "runs/local/artifacts").resolve())) or "/arxiv" in str(OUTPUT_DIR):
        failures.append("unsafe_output_dir")
    pairs = {
        "--mode": "bounded_decoder_ce_probe",
        "--probe-scale": "target_100m",
        "--max-train-rows": "32",
        "--max-eval-rows": "16",
        "--max-strict-rows": "16",
        "--max-steps": "16",
        "--max-generation-rows": "16",
        "--decoder-ce-weight": "1.0",
        "--structured-aux-weight": "0.0",
        "--denoise-weight": "0.0",
        "--eos-loss-weight": "4.0",
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
        "over_cap_rows": over_cap[:20],
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
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    authority_counts = {key: 0 for key in AUTHORITY_CLOSED}
    for row in rows:
        auth = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        for key in authority_counts:
            authority_counts[key] += int(bool(auth.get(key, False)))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": authority_counts}
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
        "decision": "Prepared a closed-boundary tiny target-100M bounded decoder CE probe after Stage9378 denoise repair passed. This authorizes only Stage9381.",
        "next_best_step": "Execute Stage9381 bounded decoder CE probe under trellis, then audit generation quality before any further training expansion.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9380 Bounded Decoder CE Preexecution", "", f"Passed: `{card['passed']}`", f"Rows: `{card['manifest_rows']}`", f"Splits: `{card['split_counts']}`", f"Languages: `{card['language_counts']}`", f"Losses: `{card['loss_counts']}`", f"Command ready: `{card['command_ready']}`", "", "Only the Stage9381 tiny target-100M bounded decoder CE probe is authorized. Runtime, Gemma, harness, scoring, source/body emission, promotion, denoise CE, and structured aux remain closed.", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
