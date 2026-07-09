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
STAGE = 9566
NAME = "stage9566_residual_denoise_target_rendered_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9565_residual_denoise_target_rendering_diagnosis.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9562_residual_denoise_execution_authorization_review/residual_denoise_execution_candidate_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "residual_denoise_target_rendered_manifest.jsonl"
CARD = OUT_DIR / "residual_denoise_target_rendered_manifest_card.json"
COMMANDS = OUT_DIR / "residual_denoise_target_rendered_commands.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESIDUAL_DENOISE_TARGET_RENDERED_MANIFEST_STAGE9566.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")
CONTRACT_OUTPUT_DIR = ROOT / "runs/local/artifacts/stage9567_residual_denoise_target_rendered_contract_preflight/denoise_repair_probe"
EXECUTION_OUTPUT_DIR = ROOT / "runs/local/artifacts/stage9568_residual_denoise_target_rendered_tiny_probe/denoise_repair_probe"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def render_target(row: dict[str, Any]) -> str:
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    repair_bucket = str(target.get("repair_bucket") or "UNKNOWN_REPAIR_BUCKET")
    failure_type = str(target.get("failure_type") or "UNKNOWN_FAILURE_TYPE")
    return f"{repair_bucket} :: {failure_type}"


def command(*, output_dir: Path, run_id: str, contract_only: bool) -> list[str]:
    cmd = [
        "env", f"TMPDIR={TMPDIR}", f"TEMP={TMPDIR}", f"TMP={TMPDIR}",
        "conda", "run", "-n", "trellis", "python", str(TRAINER),
        "--repo-root", str(ROOT), "--manifest", str(MANIFEST),
        "--mode", "denoise_repair_probe", "--probe-scale", "target_100m", "--implementation", "transformer",
        "--model-config", str(MODEL_CONFIG), "--tokenizer-json", str(TOKENIZER_JSON),
        "--tokenizer-config", str(TOKENIZER_CONFIG), "--tokenizer-hashlock", str(TOKENIZER_HASHLOCK),
        "--max-train-rows", "29", "--max-eval-rows", "6", "--max-strict-rows", "6",
        "--max-steps", "16", "--batch-size", "2", "--learning-rate", "1e-5",
        "--max-encoder-tokens", "512", "--max-decoder-tokens", "96",
        "--decoder-ce-weight", "0.0", "--structured-aux-weight", "0.0", "--denoise-weight", "1.0", "--eos-loss-weight", "1.0",
        "--enable-generation-audit", "--max-generation-rows", "12", "--max-generation-tokens", "48",
        "--generation-audit-splits", "train,eval,strict_eval",
        "--require-loss-mask-enforcement-audit", "--no-final-checkpoint-export", "--cleanup-checkpoints-after-probe", "--skip-final-model-save", "1",
        "--output-dir", str(output_dir), "--run-id", run_id,
    ]
    cmd.append("--contract-only" if contract_only else "--execution-authorized-for-recovery-probe")
    return cmd


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    rows = load_jsonl(SOURCE_MANIFEST)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9565_not_passed")
    rendered_rows: list[dict[str, Any]] = []
    split_counts: Counter[str] = Counter()
    target_counts: Counter[str] = Counter()
    loss_counts: Counter[str] = Counter()
    for row in rows:
        out = dict(row)
        target = dict(out.get("target") or {})
        rendered = render_target(out)
        target["decoder_text"] = rendered
        target["label"] = rendered
        target["rendered_from"] = ["repair_bucket", "failure_type"]
        out["target"] = target
        out["target_rendering_contract"] = {
            "stage": STAGE,
            "rendered_target_field": "target.decoder_text",
            "visible_to_model_input": False,
            "bounded_target_chars": len(rendered),
        }
        rendered_rows.append(out)
        split_counts[str(out.get("split"))] += 1
        target_counts[rendered] += 1
        for loss, enabled in (out.get("loss_mask") or {}).items():
            if enabled:
                loss_counts[loss] += 1
    if len(rendered_rows) != 41:
        failures.append("row_count_not_41")
    if dict(split_counts) != {"train": 29, "eval": 6, "strict_eval": 6}:
        failures.append("unexpected_split_counts")
    if dict(loss_counts) != {"denoise_ce": 41}:
        failures.append("loss_mask_not_denoise_only")
    if not target_counts or any(not key.strip() for key in target_counts):
        failures.append("empty_rendered_targets")
    if max((len(key) for key in target_counts), default=0) > 96:
        failures.append("rendered_target_over_char_cap")
    if any("decoder_text" in (row.get("model_input") or {}) or "label" in (row.get("model_input") or {}) for row in rendered_rows):
        failures.append("rendered_target_leaked_to_model_input")
    if any(any((row.get("authority") or {}).values()) for row in rendered_rows):
        failures.append("authority_rows_present")
    with MANIFEST.open("w", encoding="utf-8") as f:
        for row in rendered_rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    contract_command = command(output_dir=CONTRACT_OUTPUT_DIR, run_id="stage9567_residual_denoise_target_rendered_contract_preflight", contract_only=True)
    execution_command = command(output_dir=EXECUTION_OUTPUT_DIR, run_id="stage9568_residual_denoise_target_rendered_tiny_probe", contract_only=False)
    card = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "source_manifest": str(SOURCE_MANIFEST.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "manifest_sha256": sha256(MANIFEST),
        "rows": len(rendered_rows),
        "split_counts": dict(sorted(split_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "rendered_target_counts": dict(sorted(target_counts.items())),
        "max_rendered_target_chars": max((len(key) for key in target_counts), default=0),
        "execution_authorized_for_next_stage": False,
        "model_execution_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "runtime_authorized": False,
        "promotion_ready": False,
        "authority": dict(AUTHORITY_CLOSED),
    }
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    COMMANDS.write_text(json.dumps({"cwd": str(ROOT), "env": "trellis", "tmpdir": str(TMPDIR), "contract_command": contract_command, "future_execution_command": execution_command}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": card["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **card},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "card": str(CARD.relative_to(ROOT)), "commands": str(COMMANDS.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Rendered residual-denoise targets into bounded decoder text while keeping target labels outside model_input.",
        "next_best_step": "Run Stage9567 contract-only preflight on the target-rendered manifest; if it passes, execute Stage9568 tiny target_100M denoise rerun.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9566 Residual Denoise Target-Rendered Manifest", "", f"Passed: `{card['passed']}`", f"Rows: `{len(rendered_rows)}`", f"Rendered targets: `{dict(sorted(target_counts.items()))}`", "", "This stage fixes the Stage9564 EOS-only target bug by writing a bounded `target.decoder_text`/`target.label` consumed by the trainer.", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": card["passed"], "rows": len(rendered_rows), "target_counts": dict(sorted(target_counts.items())), "failures": failures}, indent=2, sort_keys=True))
    if not card["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
