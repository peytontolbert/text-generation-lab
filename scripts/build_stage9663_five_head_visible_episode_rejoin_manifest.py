#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9663
NAME = "stage9663_five_head_visible_episode_rejoin_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9662_visible_semantic_episode_tiny_probe.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9661_visible_semantic_episode_manifest/visible_semantic_episode_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "five_head_visible_episode_rejoin_manifest.jsonl"
RUN_DIR = OUT_DIR / "episode_step_contract"
AUDIT = OUT_DIR / "five_head_visible_episode_rejoin_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "FIVE_HEAD_VISIBLE_EPISODE_REJOIN_MANIFEST_STAGE9663.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")
ACTIVE_LOSSES = {"episode_boundary_match_ce", "episode_target_prefix_match_ce", "episode_failure_type_ce", "episode_repair_outcome_ce", "episode_step_value_mse"}
SPLIT_CAPS = {"train": 48, "eval": 9, "strict_eval": 9}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def trans(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("episode_transition") if isinstance(row.get("episode_transition"), dict) else {}


def obs(row: dict[str, Any]) -> dict[str, Any]:
    t = trans(row)
    return t.get("observation_t") if isinstance(t.get("observation_t"), dict) else {}


def ver(row: dict[str, Any]) -> dict[str, Any]:
    t = trans(row)
    return t.get("reward_or_verifier") if isinstance(t.get("reward_or_verifier"), dict) else {}


def nxt(row: dict[str, Any]) -> dict[str, Any]:
    t = trans(row)
    return t.get("state_t_plus_1") if isinstance(t.get("state_t_plus_1"), dict) else {}


def label(row: dict[str, Any], field: str) -> str:
    if field == "episode_boundary_match":
        return "true" if bool(obs(row).get("boundary_next_token_match")) else "false"
    if field == "episode_target_prefix_match":
        return "true" if bool(obs(row).get("target_prefix_match")) else "false"
    if field == "episode_failure_type":
        return str(ver(row).get("failure_type"))
    if field == "episode_repair_outcome":
        return str(nxt(row).get("repair_outcome"))
    if field == "episode_step_value":
        return "1.0" if float(ver(row).get("reward") or 0.0) >= 0.5 else "0.0"
    raise ValueError(field)


def patch_row(row: dict[str, Any], idx: int) -> dict[str, Any]:
    out = copy.deepcopy(row)
    out["row_id"] = f"stage9663_five_head_visible_episode_{idx:04d}"
    out["source_stage9661_row_id"] = row.get("row_id")
    out["objective_family"] = "five_head_visible_episode_rejoin"
    out["route"] = "KEEP_FIVE_HEAD_VISIBLE_EPISODE_REJOIN"
    mask = out.get("loss_mask") if isinstance(out.get("loss_mask"), dict) else {}
    for key in list(mask):
        mask[key] = key in ACTIVE_LOSSES
    for key in ACTIVE_LOSSES:
        mask.setdefault(key, True)
    out["loss_mask"] = mask
    anti = out.get("anti_cheat") if isinstance(out.get("anti_cheat"), dict) else {}
    anti.update({"five_head_rejoin": True, "decoder_ce_closed": True, "denoise_ce_closed": True, "runtime_closed": True, "active_losses": sorted(ACTIVE_LOSSES)})
    out["anti_cheat"] = anti
    return out


def contract_command() -> list[str]:
    return ["env", f"TMPDIR={TMPDIR}", f"TEMP={TMPDIR}", f"TMP={TMPDIR}", "conda", "run", "-n", "trellis", "python", str(TRAINER),
        "--repo-root", str(ROOT), "--manifest", str(MANIFEST), "--mode", "episode_step_structured_probe", "--probe-scale", "target_100m", "--implementation", "transformer",
        "--model-config", str(MODEL_CONFIG), "--tokenizer-json", str(TOKENIZER_JSON), "--tokenizer-config", str(TOKENIZER_CONFIG), "--tokenizer-hashlock", str(TOKENIZER_HASHLOCK),
        "--max-train-rows", str(SPLIT_CAPS["train"]), "--max-eval-rows", str(SPLIT_CAPS["eval"]), "--max-strict-rows", str(SPLIT_CAPS["strict_eval"]), "--max-steps", "0", "--batch-size", "3", "--learning-rate", "3e-4",
        "--max-encoder-tokens", "512", "--max-decoder-tokens", "8", "--decoder-ce-weight", "0.0", "--structured-aux-weight", "1.0", "--denoise-weight", "0.0",
        "--require-loss-mask-enforcement-audit", "--no-final-checkpoint-export", "--cleanup-checkpoints-after-probe", "--skip-final-model-save", "1",
        "--output-dir", str(RUN_DIR), "--run-id", "stage9663_five_head_visible_episode_rejoin_contract", "--contract-only"]


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    rows = [patch_row(row, idx) for idx, row in enumerate(load_jsonl(SOURCE_MANIFEST))]
    write_jsonl(MANIFEST, rows)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9662_not_passed")
    split_counts = dict(Counter(str(row.get("split")) for row in rows))
    if split_counts != SPLIT_CAPS:
        failures.append("split_counts_wrong")
    loss_counts: Counter[str] = Counter()
    for row in rows:
        for key, value in (row.get("loss_mask") or {}).items():
            if value:
                loss_counts[key] += 1
    expected = {key: len(rows) for key in sorted(ACTIVE_LOSSES)}
    if dict(sorted(loss_counts.items())) != expected:
        failures.append("active_loss_counts_wrong")
    if any((row.get("loss_mask") or {}).get(key) for row in rows for key in ["decoder_ce", "denoise_ce", "runtime_reward"]):
        failures.append("forbidden_loss_enabled")
    fields = ["episode_boundary_match", "episode_target_prefix_match", "episode_failure_type", "episode_repair_outcome", "episode_step_value"]
    label_by_split = {split: {field: dict(Counter(label(row, field) for row in rows if row.get("split") == split)) for field in fields} for split in ["train", "eval", "strict_eval"]}
    authority_rows = [row.get("row_id") for row in rows if any((row.get("authority") or {}).get(key) for key in AUTHORITY_CLOSED)]
    if authority_rows:
        failures.append("authority_rows_present")
    run = subprocess.run(contract_command(), cwd=ROOT, text=True, capture_output=True, check=False) if not failures else None
    if run is not None and run.returncode != 0:
        failures.append("contract_command_failed")
    card = load_json(RUN_DIR / "probe_contract_audit.json")
    if not card and not failures:
        failures.append("missing_probe_contract_audit")
    elif card and card.get("passed") is not True:
        failures.append("probe_contract_not_passed")
    audit = {"passed": not failures, "failures": failures, "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)), "source_manifest": str(SOURCE_MANIFEST.relative_to(ROOT)), "manifest": str(MANIFEST.relative_to(ROOT)), "rows": len(rows), "split_counts": split_counts, "loss_counts": dict(sorted(loss_counts.items())), "label_by_split": label_by_split, "authority_rows": len(authority_rows), "contract_passed": card.get("passed"), "contract_loss_counts": card.get("loss_counts"), "model_execution_attempted": card.get("model_execution_attempted"), "authority": dict(AUTHORITY_CLOSED)}
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "If Stage9663 passes, run Stage9664 five-head visible episode target-100M rejoin probe."
    summary = {"stage": STAGE, "stage_name": NAME, "name": NAME, "passed": audit["passed"], "authority": dict(AUTHORITY_CLOSED), "metrics": {**dict(AUTHORITY_CLOSED), **audit}, "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "manifest": str(MANIFEST.relative_to(ROOT)), "run_dir": str(RUN_DIR.relative_to(ROOT))}, "decision": "Built five-head visible episode rejoin manifest; no decoder/runtime opened." if audit["passed"] else "Five-head rejoin manifest failed; do not execute.", "next_best_step": next_step, "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9663 Five-Head Visible Episode Rejoin Manifest", "", f"Passed: `{audit['passed']}`", f"Rows: `{audit['rows']}`", f"Splits: `{split_counts}`", f"Loss counts: `{audit['loss_counts']}`", "", "This stage rejoins the two passed boundary/prefix heads with the three passed semantic episode heads on the same collator-visible observe/repair rows.", "", "Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, final checkpoint export, controller merge, and promotion remain closed.", "", f"Next: {next_step}", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "failures": failures, "rows": len(rows), "next_best_step": next_step}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
