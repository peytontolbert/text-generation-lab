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
STAGE = 9666
NAME = "stage9666_sidecar_gated_residual_denoise_preexecution"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9665_observe_repair_control_promotion_contract.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9560_residual_denoise_loss_mask_reopen_design/residual_denoise_loss_mask_reopen_candidate_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "sidecar_gated_residual_denoise_manifest.jsonl"
RUN_DIR = OUT_DIR / "denoise_contract"
AUDIT = OUT_DIR / "sidecar_gated_residual_denoise_preexecution_audit.json"
COMMAND_JSON = OUT_DIR / "stage9667_sidecar_gated_residual_denoise_probe_command.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SIDECAR_GATED_RESIDUAL_DENOISE_PREEXECUTION_STAGE9666.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")
OUTPUT_DIR = ROOT / "runs/local/artifacts/stage9667_sidecar_gated_residual_denoise_probe"
AUTHORITY_RUN = dict(AUTHORITY_CLOSED)
AUTHORITY_RUN["model_execution_authorized_next"] = True
AUTHORITY_RUN["denoise_ce_training_authorized_next"] = True


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def transition(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("episode_transition") if isinstance(row.get("episode_transition"), dict) else {}


def obs(row: dict[str, Any]) -> dict[str, Any]:
    t = transition(row)
    return t.get("observation_t") if isinstance(t.get("observation_t"), dict) else {}


def nxt(row: dict[str, Any]) -> dict[str, Any]:
    t = transition(row)
    return t.get("state_t_plus_1") if isinstance(t.get("state_t_plus_1"), dict) else {}


def is_candidate(row: dict[str, Any]) -> bool:
    design = row.get("residual_denoise_loss_mask_reopen_design") if isinstance(row.get("residual_denoise_loss_mask_reopen_design"), dict) else {}
    return bool(design.get("future_denoise_ce_candidate")) and not bool(design.get("rare_holdout")) and row.get("source_kind") == "real"


def patch_row(row: dict[str, Any], idx: int) -> dict[str, Any]:
    out = copy.deepcopy(row)
    observation = obs(out)
    clean = str(nxt(out).get("decoder_text") or "")
    generated = str(observation.get("generated_text") or "")
    out["row_id"] = f"stage9666_sidecar_gated_residual_denoise_{idx:04d}"
    out["source_stage9560_row_id"] = row.get("row_id")
    out["objective_family"] = "sidecar_gated_residual_denoise"
    out["route"] = "KEEP_SIDECAR_GATED_RESIDUAL_DENOISE"
    out["corrupted_output"] = generated
    out["verifier_failure"] = str((out.get("effective_verifier") or {}).get("effective_failure_type") or (out.get("residual_repair_route") or {}).get("failure_type") or "residual_suffix_failure")
    out["target"] = {"decoder_text": clean, "target_authority": "episode_state_t_plus_1_clean_decoder_text", "source_stage": 9560}
    mask = out.get("loss_mask") if isinstance(out.get("loss_mask"), dict) else {}
    for key in list(mask):
        mask[key] = False
    mask.update({"decoder_ce": False, "structured_aux": False, "denoise_ce": True, "runtime_reward": False})
    out["loss_mask"] = mask
    model_input = out.get("model_input") if isinstance(out.get("model_input"), dict) else {}
    model_input.update({
        "stage9664_observe_repair_control_required": True,
        "stage9664_control_contract_passed": True,
        "sidecar_gated_denoise_phase": True,
        "corrupted_output_visible": True,
        "clean_target_visible_in_model_input": False,
        "clean_target_location": "target.decoder_text",
    })
    out["model_input"] = model_input
    anti = out.get("anti_cheat") if isinstance(out.get("anti_cheat"), dict) else {}
    anti.update({
        "decoder_ce_closed": True,
        "runtime_closed": True,
        "target_copied_to_model_input": False,
        "corrupted_output_visible": True,
        "clean_target_only_in_target_decoder_text": True,
        "stage9664_control_contract_required": True,
    })
    out["anti_cheat"] = anti
    return out


def command(*, contract_only: bool) -> list[str]:
    cmd = ["env", f"TMPDIR={TMPDIR}", f"TEMP={TMPDIR}", f"TMP={TMPDIR}", "conda", "run", "-n", "trellis", "python", str(TRAINER),
        "--repo-root", str(ROOT), "--manifest", str(MANIFEST), "--mode", "denoise_repair_probe", "--probe-scale", "target_100m", "--implementation", "transformer",
        "--model-config", str(MODEL_CONFIG), "--tokenizer-json", str(TOKENIZER_JSON), "--tokenizer-config", str(TOKENIZER_CONFIG), "--tokenizer-hashlock", str(TOKENIZER_HASHLOCK),
        "--max-train-rows", "20", "--max-eval-rows", "3", "--max-strict-rows", "3", "--max-steps", "80", "--batch-size", "2", "--learning-rate", "1e-5",
        "--max-encoder-tokens", "512", "--max-decoder-tokens", "96", "--decoder-ce-weight", "0.0", "--structured-aux-weight", "0.0", "--denoise-weight", "1.0", "--eos-loss-weight", "1.0",
        "--enable-generation-audit", "--max-generation-rows", "26", "--max-generation-tokens", "96", "--generation-audit-splits", "train,eval,strict_eval",
        "--require-loss-mask-enforcement-audit", "--no-final-checkpoint-export", "--cleanup-checkpoints-after-probe", "--skip-final-model-save", "1",
        "--output-dir", str(RUN_DIR if contract_only else OUTPUT_DIR), "--run-id", "stage9666_sidecar_gated_residual_denoise_contract" if contract_only else "stage9667_sidecar_gated_residual_denoise_probe"]
    if contract_only:
        cmd.extend(["--contract-only", "--max-steps", "0"])
    else:
        cmd.append("--execution-authorized-for-recovery-probe")
    return cmd


def has_pair(cmd: list[str], flag: str, value: str) -> bool:
    return any(cmd[i] == flag and i + 1 < len(cmd) and cmd[i + 1] == value for i in range(len(cmd)))


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": summary["authority"], "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = bool(rows)
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows)}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    rows = [patch_row(row, idx) for idx, row in enumerate(load_jsonl(SOURCE_MANIFEST)) if is_candidate(row)]
    write_jsonl(MANIFEST, rows)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9665_not_passed")
    split_counts = dict(Counter(str(row.get("split")) for row in rows))
    if split_counts != {"train": 20, "eval": 3, "strict_eval": 3}:
        failures.append("split_counts_wrong")
    if len(rows) != 26:
        failures.append("row_count_not_26")
    loss_counts: Counter[str] = Counter()
    unsafe_rows: list[str] = []
    for row in rows:
        loss = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        for key, value in loss.items():
            if value:
                loss_counts[key] += 1
        target = row.get("target") if isinstance(row.get("target"), dict) else {}
        mi = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        if not loss.get("denoise_ce") or loss.get("decoder_ce") or loss.get("structured_aux") or loss.get("runtime_reward"):
            unsafe_rows.append(str(row.get("row_id")))
        if not target.get("decoder_text") or target.get("decoder_text") == row.get("corrupted_output"):
            unsafe_rows.append(str(row.get("row_id")))
        if mi.get("clean_target_visible_in_model_input") is not False:
            unsafe_rows.append(str(row.get("row_id")))
        if any((row.get("authority") or {}).get(key) for key in AUTHORITY_CLOSED):
            unsafe_rows.append(str(row.get("row_id")))
    if dict(loss_counts) != {"denoise_ce": 26}:
        failures.append("loss_counts_not_denoise_only")
    if unsafe_rows:
        failures.append("unsafe_rows_present")
    contract_cmd = command(contract_only=True)
    if "--contract-only" not in contract_cmd:
        failures.append("contract_command_missing_contract_only")
    run_cmd = command(contract_only=False)
    required_pairs = {"--mode": "denoise_repair_probe", "--probe-scale": "target_100m", "--max-train-rows": "20", "--max-eval-rows": "3", "--max-strict-rows": "3", "--denoise-weight": "1.0", "--decoder-ce-weight": "0.0", "--structured-aux-weight": "0.0"}
    for flag, value in required_pairs.items():
        if not has_pair(run_cmd, flag, value):
            failures.append(f"missing_run_pair:{flag}={value}")
    for flag in ["--execution-authorized-for-recovery-probe", "--require-loss-mask-enforcement-audit", "--no-final-checkpoint-export", "--cleanup-checkpoints-after-probe", "--enable-generation-audit"]:
        if flag not in run_cmd:
            failures.append(f"missing_run_flag:{flag}")
    run = subprocess.run(contract_cmd, cwd=ROOT, text=True, capture_output=True, check=False) if not failures else None
    if run is not None and run.returncode != 0:
        failures.append("contract_command_failed")
    card = load_json(RUN_DIR / "probe_contract_audit.json")
    if not card and not failures:
        failures.append("missing_probe_contract_audit")
    elif card and card.get("passed") is not True:
        failures.append("probe_contract_not_passed")
    audit = {"passed": not failures, "failures": failures, "rows": len(rows), "split_counts": split_counts, "loss_counts": dict(loss_counts), "unsafe_rows": unsafe_rows[:20], "manifest": str(MANIFEST.relative_to(ROOT)), "contract_passed": card.get("passed"), "contract_loss_counts": card.get("loss_counts"), "model_execution_attempted": card.get("model_execution_attempted"), "run_command_ready": not failures, "authority": AUTHORITY_RUN if not failures else dict(AUTHORITY_CLOSED)}
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    COMMAND_JSON.write_text(json.dumps({"command": run_cmd, "cwd": str(ROOT), "env": "trellis", "tmpdir": str(TMPDIR), "authority": AUTHORITY_RUN if not failures else dict(AUTHORITY_CLOSED)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "If Stage9666 passes, execute Stage9667 sidecar-gated 26-row real residual denoise target-100M probe and audit exact/contentful/leak/repetition metrics."
    summary = {"stage": STAGE, "stage_name": NAME, "name": NAME, "passed": audit["passed"], "authority": audit["authority"], "metrics": {**{key: bool(audit["authority"].get(key, False)) for key in AUTHORITY_CLOSED}, **audit}, "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "command": str(COMMAND_JSON.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "manifest": str(MANIFEST.relative_to(ROOT)), "run_dir": str(RUN_DIR.relative_to(ROOT))}, "decision": "Prepared sidecar-gated 26-row real residual denoise preexecution package; decoder/runtime remain closed, denoise CE authorized only for the next tiny recovery probe." if audit["passed"] else "Sidecar-gated denoise preexecution failed; do not execute.", "next_best_step": next_step, "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9666 Sidecar-Gated Residual Denoise Preexecution", "", f"Passed: `{audit['passed']}`", f"Rows: `{audit['rows']}`", f"Splits: `{audit['split_counts']}`", f"Loss counts: `{audit['loss_counts']}`", "", "This stage materializes the 26 real Stage9561 residual denoise candidates into denoise-trainer-ready rows by exposing the corrupted output and placing the clean target only in `target.decoder_text`.", "", "Only the next tiny denoise probe is authorized. Decoder CE, runtime, source/body emission, Gemma, harness, scoring, final checkpoint export, controller merge, and promotion remain closed.", "", f"Next: {next_step}", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "failures": failures, "rows": len(rows), "next_best_step": next_step}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
