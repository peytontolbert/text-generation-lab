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
STAGE = 9562
NAME = "stage9562_residual_denoise_execution_authorization_review"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9561_residual_denoise_loss_mask_reopen_design_audit.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9560_residual_denoise_loss_mask_reopen_design/residual_denoise_loss_mask_reopen_candidate_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
EXECUTION_MANIFEST = OUT_DIR / "residual_denoise_execution_candidate_manifest.jsonl"
REVIEW_CARD = OUT_DIR / "residual_denoise_execution_authorization_review.json"
COMMAND_JSON = OUT_DIR / "residual_denoise_tiny_probe_commands.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESIDUAL_DENOISE_EXECUTION_AUTHORIZATION_REVIEW_STAGE9562.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")
CONTRACT_OUTPUT_DIR = ROOT / "runs/local/artifacts/stage9563_residual_denoise_target_100m_contract_preflight/denoise_repair_probe"
EXECUTION_OUTPUT_DIR = ROOT / "runs/local/artifacts/stage9564_residual_denoise_target_100m_tiny_probe/denoise_repair_probe"

RUN_ID_CONTRACT = "stage9563_residual_denoise_target_100m_contract_preflight"
RUN_ID_EXECUTION = "stage9564_residual_denoise_target_100m_tiny_probe"

CAPS = {
    "max_train_rows": "29",
    "max_eval_rows": "6",
    "max_strict_rows": "6",
    "max_steps": "16",
    "batch_size": "2",
    "learning_rate": "1e-5",
    "max_encoder_tokens": "512",
    "max_decoder_tokens": "96",
    "max_generation_rows": "12",
    "max_generation_tokens": "48",
}


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
    rows = [
        row
        for row in registry.get("rows", [])
        if row.get("stage") != STAGE and row.get("stage_name") != NAME
    ]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": dict(AUTHORITY_CLOSED),
            "next_best_step": summary["next_best_step"],
        }
    )
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def command(*, output_dir: Path, run_id: str, contract_only: bool) -> list[str]:
    cmd = [
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
        str(EXECUTION_MANIFEST),
        "--mode",
        "denoise_repair_probe",
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
        "--max-train-rows",
        CAPS["max_train_rows"],
        "--max-eval-rows",
        CAPS["max_eval_rows"],
        "--max-strict-rows",
        CAPS["max_strict_rows"],
        "--max-steps",
        CAPS["max_steps"],
        "--batch-size",
        CAPS["batch_size"],
        "--learning-rate",
        CAPS["learning_rate"],
        "--max-encoder-tokens",
        CAPS["max_encoder_tokens"],
        "--max-decoder-tokens",
        CAPS["max_decoder_tokens"],
        "--decoder-ce-weight",
        "0.0",
        "--structured-aux-weight",
        "0.0",
        "--denoise-weight",
        "1.0",
        "--eos-loss-weight",
        "1.0",
        "--enable-generation-audit",
        "--max-generation-rows",
        CAPS["max_generation_rows"],
        "--max-generation-tokens",
        CAPS["max_generation_tokens"],
        "--generation-audit-splits",
        "train,eval,strict_eval",
        "--require-loss-mask-enforcement-audit",
        "--no-final-checkpoint-export",
        "--cleanup-checkpoints-after-probe",
        "--skip-final-model-save",
        "1",
        "--output-dir",
        str(output_dir),
        "--run-id",
        run_id,
    ]
    if contract_only:
        cmd.append("--contract-only")
    else:
        cmd.append("--execution-authorized-for-recovery-probe")
    return cmd


def has_pair(cmd: list[str], flag: str, value: str) -> bool:
    return any(cmd[i] == flag and cmd[i + 1] == value for i in range(len(cmd) - 1))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)

    source = load_json(SOURCE_SUMMARY)
    rows = load_jsonl(SOURCE_MANIFEST)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9561_not_passed")

    selected_rows: list[dict[str, Any]] = []
    skipped_holdouts = 0
    split_counts: Counter[str] = Counter()
    loss_counts: Counter[str] = Counter()
    unsafe_rows: list[str] = []
    for row in rows:
        design = row.get("residual_denoise_loss_mask_reopen_design") or {}
        if design.get("rare_holdout"):
            skipped_holdouts += 1
            continue
        if not design.get("future_denoise_ce_candidate"):
            unsafe_rows.append(str(row.get("row_id")))
            continue
        out = dict(row)
        out["source_stage9562_execution_manifest"] = True
        out["loss_mask"] = dict(row.get("loss_mask_proposed_after_future_authorization") or {})
        out["loss_mask_current_before_stage9562"] = dict(row.get("loss_mask_current") or {})
        out["execution_review"] = {
            "stage": STAGE,
            "candidate_only": True,
            "execution_authorized_now": False,
            "requires_stage9563_contract_preflight": True,
        }
        selected_rows.append(out)
        split_counts[str(out.get("split"))] += 1
        enabled = [key for key, value in out["loss_mask"].items() if value]
        for key in enabled:
            loss_counts[key] += 1
        if enabled != ["denoise_ce"] or any((out.get("authority") or {}).values()):
            unsafe_rows.append(str(out.get("row_id")))

    if len(selected_rows) != 41 or skipped_holdouts != 3:
        failures.append("candidate_or_holdout_count_mismatch")
    if dict(split_counts) != {"train": 29, "eval": 6, "strict_eval": 6}:
        failures.append("unexpected_split_counts")
    if dict(loss_counts) != {"denoise_ce": 41}:
        failures.append("loss_mask_not_denoise_only")
    if unsafe_rows:
        failures.append("unsafe_rows_present")
    required_files = [TRAINER, MODEL_CONFIG, TOKENIZER_JSON, TOKENIZER_CONFIG, TOKENIZER_HASHLOCK]
    missing_files = [str(path.relative_to(ROOT)) for path in required_files if not path.is_file()]
    if missing_files:
        failures.append("required_files_missing")
    if not TMPDIR.is_dir():
        failures.append("data_tmp_missing")
    if "/arxiv" in str(CONTRACT_OUTPUT_DIR) or "/arxiv" in str(EXECUTION_OUTPUT_DIR):
        failures.append("arxiv_output_dir_forbidden")
    if not str(CONTRACT_OUTPUT_DIR.resolve()).startswith(str((ROOT / "runs/local/artifacts").resolve())):
        failures.append("contract_output_dir_not_under_artifacts")
    if not str(EXECUTION_OUTPUT_DIR.resolve()).startswith(str((ROOT / "runs/local/artifacts").resolve())):
        failures.append("execution_output_dir_not_under_artifacts")

    with EXECUTION_MANIFEST.open("w", encoding="utf-8") as f:
        for row in selected_rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")

    contract_command = command(output_dir=CONTRACT_OUTPUT_DIR, run_id=RUN_ID_CONTRACT, contract_only=True)
    execution_command = command(output_dir=EXECUTION_OUTPUT_DIR, run_id=RUN_ID_EXECUTION, contract_only=False)
    for cmd, label in [(contract_command, "contract"), (execution_command, "execution")]:
        for flag, value in {
            "--mode": "denoise_repair_probe",
            "--probe-scale": "target_100m",
            "--implementation": "transformer",
            "--decoder-ce-weight": "0.0",
            "--structured-aux-weight": "0.0",
            "--denoise-weight": "1.0",
            "--max-steps": CAPS["max_steps"],
            "--max-train-rows": CAPS["max_train_rows"],
            "--max-eval-rows": CAPS["max_eval_rows"],
            "--max-strict-rows": CAPS["max_strict_rows"],
        }.items():
            if not has_pair(cmd, flag, value):
                failures.append(f"{label}_command_missing_pair:{flag}={value}")
        for flag in ["--require-loss-mask-enforcement-audit", "--no-final-checkpoint-export", "--cleanup-checkpoints-after-probe"]:
            if flag not in cmd:
                failures.append(f"{label}_command_missing_flag:{flag}")

    review = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "source_manifest": str(SOURCE_MANIFEST.relative_to(ROOT)),
        "execution_manifest": str(EXECUTION_MANIFEST.relative_to(ROOT)),
        "execution_manifest_sha256": sha256(EXECUTION_MANIFEST),
        "candidate_rows": len(selected_rows),
        "skipped_holdout_rows": skipped_holdouts,
        "split_counts": dict(sorted(split_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "unsafe_rows": unsafe_rows,
        "missing_files": missing_files,
        "tmpdir": str(TMPDIR),
        "contract_output_dir": str(CONTRACT_OUTPUT_DIR.relative_to(ROOT)),
        "execution_output_dir": str(EXECUTION_OUTPUT_DIR.relative_to(ROOT)),
        "contract_preflight_required": True,
        "will_execute_now": False,
        "model_execution_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "runtime_authorized": False,
        "promotion_ready": False,
        "authority": dict(AUTHORITY_CLOSED),
    }
    REVIEW_CARD.write_text(json.dumps(review, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    COMMAND_JSON.write_text(
        json.dumps(
            {
                "cwd": str(ROOT),
                "env": "trellis",
                "tmpdir": str(TMPDIR),
                "contract_command": contract_command,
                "future_execution_command": execution_command,
                "future_execution_command_authorized_by_stage9562": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": review["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **review},
        "artifacts": {
            "execution_manifest": str(EXECUTION_MANIFEST.relative_to(ROOT)),
            "review": str(REVIEW_CARD.relative_to(ROOT)),
            "commands": str(COMMAND_JSON.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Prepared a candidate-only residual-denoise execution manifest and command review. Actual model execution remains blocked until the Stage9563 contract-only preflight passes.",
        "next_best_step": "Run Stage9563 contract-only target_100M denoise preflight under trellis; only if it passes should Stage9564 actual tiny execution be considered.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9562 Residual Denoise Execution Authorization Review",
                "",
                f"Passed: `{review['passed']}`",
                f"Candidate rows: `{len(selected_rows)}`",
                f"Skipped holdouts: `{skipped_holdouts}`",
                f"Splits: `{dict(sorted(split_counts.items()))}`",
                f"Loss counts: `{dict(sorted(loss_counts.items()))}`",
                "",
                "This stage prepares a candidate-only denoise manifest and command artifacts. It does not authorize actual model execution.",
                "Stage9563 must run the contract-only trainer preflight under `trellis` before any tiny probe is allowed.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": review["passed"], "candidate_rows": len(selected_rows), "split_counts": dict(sorted(split_counts.items())), "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
