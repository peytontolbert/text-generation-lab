#!/usr/bin/env python3
from __future__ import annotations

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
STAGE = 9368
NAME = "stage9368_route0_dependency_duplicate_probe_preexecution"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9367_route0_dependency_duplicate_repair_manifest.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9367_route0_dependency_duplicate_repair_manifest/route0_dependency_duplicate_repair_manifest.jsonl"
OUTPUT_DIR = ROOT / "runs/local/artifacts/stage9369_route0_dependency_duplicate_probe"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "route0_dependency_duplicate_probe_preexecution_audit.json"
COMMAND_JSON = OUT_DIR / "stage9369_route0_dependency_duplicate_probe_command.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ROUTE0_DEPENDENCY_DUPLICATE_PROBE_PREEXECUTION_STAGE9368.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")

AUTHORITY_RUN = dict(AUTHORITY_CLOSED)
AUTHORITY_RUN["model_execution_authorized_next"] = True
AUTHORITY_RUN["denoise_ce_training_authorized_next"] = True

COMMAND = [
    "env", f"TMPDIR={TMPDIR}", f"TEMP={TMPDIR}", f"TMP={TMPDIR}",
    "conda", "run", "-n", "trellis", "python", str(TRAINER),
    "--repo-root", str(ROOT), "--manifest", str(MANIFEST),
    "--mode", "denoise_repair_probe", "--probe-scale", "target_100m", "--implementation", "transformer",
    "--model-config", str(MODEL_CONFIG), "--tokenizer-json", str(TOKENIZER_JSON),
    "--tokenizer-config", str(TOKENIZER_CONFIG), "--tokenizer-hashlock", str(TOKENIZER_HASHLOCK),
    "--max-train-rows", "24", "--max-eval-rows", "11", "--max-strict-rows", "6",
    "--max-steps", "90", "--batch-size", "2", "--learning-rate", "1e-5",
    "--max-encoder-tokens", "256", "--max-decoder-tokens", "96",
    "--decoder-ce-weight", "0.0", "--structured-aux-weight", "0.0", "--denoise-weight", "1.0", "--eos-loss-weight", "1.0",
    "--enable-generation-audit", "--max-generation-rows", "41", "--max-generation-tokens", "64",
    "--generation-prefix-field", "model_input.active_generation_prefix_span", "--generation-audit-splits", "train,eval,strict_eval",
    "--require-loss-mask-enforcement-audit", "--no-final-checkpoint-export", "--cleanup-checkpoints-after-probe", "--skip-final-model-save", "1",
    "--execution-authorized-for-recovery-probe", "--output-dir", str(OUTPUT_DIR), "--run-id", "stage9369_route0_dependency_duplicate_probe",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def has_pair(flag: str, value: str) -> bool:
    return any(COMMAND[i] == flag and COMMAND[i + 1] == value for i in range(len(COMMAND) - 1))


def audit() -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    rows = load_jsonl(MANIFEST)
    split_counts = Counter(str(row.get("split")) for row in rows)
    route_counts = Counter(str(row.get("model_input", {}).get("opaque_phrase_route_id")) for row in rows)
    unsafe: list[str] = []
    for row in rows:
        loss = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        auth = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        if loss.get("decoder_ce") or loss.get("structured_aux") or loss.get("runtime_reward") or not loss.get("denoise_ce"):
            unsafe.append(str(row.get("row_id")))
        if any(bool(auth.get(key)) for key in AUTHORITY_CLOSED):
            unsafe.append(str(row.get("row_id")))
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9367_not_passed")
    if len(rows) != 41:
        failures.append("unexpected_manifest_row_count")
    if dict(split_counts) != {"train": 24, "eval": 11, "strict_eval": 6}:
        failures.append("unexpected_split_counts")
    if dict(route_counts) != {"route_0": 41}:
        failures.append("unexpected_route_counts")
    if unsafe:
        failures.append("unsafe_manifest_rows")
    if not str(OUTPUT_DIR.resolve()).startswith(str((ROOT / "runs/local/artifacts").resolve())) or "/arxiv" in str(OUTPUT_DIR):
        failures.append("unsafe_output_dir")
    pairs = {
        "--mode": "denoise_repair_probe",
        "--probe-scale": "target_100m",
        "--max-train-rows": "24",
        "--max-eval-rows": "11",
        "--max-strict-rows": "6",
        "--max-steps": "90",
        "--max-generation-rows": "41",
        "--decoder-ce-weight": "0.0",
        "--structured-aux-weight": "0.0",
        "--denoise-weight": "1.0",
        "--generation-prefix-field": "model_input.active_generation_prefix_span",
    }
    for flag, value in pairs.items():
        if not has_pair(flag, value):
            failures.append(f"missing_pair:{flag}={value}")
    for flag in ["--execution-authorized-for-recovery-probe", "--require-loss-mask-enforcement-audit", "--no-final-checkpoint-export", "--cleanup-checkpoints-after-probe", "--enable-generation-audit"]:
        if flag not in COMMAND:
            failures.append(f"missing_flag:{flag}")
    return {"passed": not failures, "failures": failures, "manifest_rows": len(rows), "split_counts": dict(sorted(split_counts.items())), "route_counts": dict(sorted(route_counts.items())), "unsafe_rows": sorted(set(unsafe)), "command": COMMAND, "command_ready": not failures, "authority": AUTHORITY_RUN if not failures else dict(AUTHORITY_CLOSED)}


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
    DOC.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    card = audit()
    AUDIT.write_text(json.dumps({k: v for k, v in card.items() if k != "command"}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    COMMAND_JSON.write_text(json.dumps({"command": COMMAND, "cwd": str(ROOT), "env": "trellis", "tmpdir": str(TMPDIR)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": card["passed"],
        "authority": card["authority"],
        "metrics": {**{key: bool(card["authority"].get(key, False)) for key in AUTHORITY_CLOSED}, "command_ready": card["command_ready"], "manifest_rows": card["manifest_rows"], "split_counts": card["split_counts"], "route_counts": card["route_counts"], "failures": len(card["failures"])},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "command": str(COMMAND_JSON.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Prepared a closed-boundary 41-row route_0 dependency duplicate denoise probe; decoder CE remains closed.",
        "next_best_step": "Execute Stage9369 route_0 dependency duplicate probe under trellis and audit exactness before another full rejoin.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9368 Route0 Dependency Duplicate Probe Preexecution", "", f"Passed: `{card['passed']}`", f"Rows: `{card['manifest_rows']}`", f"Splits: `{card['split_counts']}`", f"Routes: `{card['route_counts']}`", "", "Only the Stage9369 41-row target-100M denoise probe is authorized. Decoder CE and external authority remain closed.", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
