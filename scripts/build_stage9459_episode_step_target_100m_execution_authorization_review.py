#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9459
NAME = "stage9459_episode_step_target_100m_execution_authorization_review"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9458_episode_step_structured_probe_static_audit.json"
PREFLIGHT_DIR = ROOT / "runs/local/artifacts/stage9459_episode_step_target_100m_contract_preflight"
CONTRACT = PREFLIGHT_DIR / "probe_contract_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REVIEW = OUT_DIR / "episode_step_target_100m_execution_authorization_review.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_STEP_TARGET_100M_EXECUTION_AUTHORIZATION_REVIEW_STAGE9459.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
COMMAND = [
    "conda", "run", "-n", "trellis", "python", "legacy_src/scripts/train_agentkernel_lite_encdec.py",
    "--repo-root", ".",
    "--manifest", "runs/local/artifacts/stage9455_episode_step_trainable_manifest/episode_step_trainable_manifest.jsonl",
    "--mode", "episode_step_structured_probe",
    "--max-train-rows", "48",
    "--max-eval-rows", "1",
    "--max-strict-rows", "1",
    "--max-steps", "16",
    "--decoder-ce-weight", "0",
    "--structured-aux-weight", "1",
    "--denoise-weight", "0",
    "--require-loss-mask-enforcement-audit",
    "--no-final-checkpoint-export",
    "--cleanup-checkpoints-after-probe",
    "--skip-final-model-save", "1",
    "--output-dir", "runs/local/artifacts/stage9460_episode_step_target_100m_tiny_probe",
    "--run-id", "stage9460_episode_step_target_100m_tiny_probe",
    "--probe-scale", "target_100m",
    "--model-config", "configs/model/agentkernel_100m_seq2seq_recovered_target.json",
    "--tokenizer-json", "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json",
    "--tokenizer-config", "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json",
    "--execution-authorized-for-recovery-probe",
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def run_trellis_check() -> dict:
    if not shutil.which("conda"):
        return {"available": False, "error": "conda_not_found"}
    proc = subprocess.run(
        ["conda", "run", "-n", "trellis", "python", "-c", "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.device_count())"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    return {
        "available": proc.returncode == 0,
        "returncode": proc.returncode,
        "torch_version": lines[0] if len(lines) > 0 else None,
        "cuda_available": lines[1] == "True" if len(lines) > 1 else False,
        "cuda_device_count": int(lines[2]) if len(lines) > 2 and lines[2].isdigit() else 0,
        "stderr_tail": proc.stderr[-500:],
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    contract = load_json(CONTRACT)
    trellis = run_trellis_check()
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9458_not_passed")
    if contract.get("passed") is not True:
        failures.append("target_100m_contract_preflight_not_passed")
    if contract.get("probe_scale") != "target_100m":
        failures.append("contract_not_target_100m")
    if contract.get("model_execution_attempted") is not False:
        failures.append("contract_preflight_attempted_execution")
    tokenizer = contract.get("tokenizer_contract") if isinstance(contract.get("tokenizer_contract"), dict) else {}
    if tokenizer.get("byte_fallback_used_when_unset") is not False:
        failures.append("target_100m_tokenizer_not_locked")
    if contract.get("unsafe_loss_rows") != 0 or contract.get("authority_rows") != 0:
        failures.append("unsafe_or_authority_rows_present")
    loss_counts = contract.get("loss_counts") if isinstance(contract.get("loss_counts"), dict) else {}
    for forbidden in ["decoder_ce", "denoise_ce", "runtime_reward"]:
        if loss_counts.get(forbidden, 0) != 0:
            failures.append(f"forbidden_loss_reopened:{forbidden}")
    if not trellis.get("available"):
        failures.append("trellis_unavailable")
    if not trellis.get("cuda_available"):
        failures.append("cuda_unavailable_in_trellis")
    output_dir = ROOT / "runs/local/artifacts/stage9460_episode_step_target_100m_tiny_probe"
    if not str(output_dir.resolve()).startswith(str((ROOT / "runs/local/artifacts").resolve())):
        failures.append("unsafe_output_dir")
    review = {
        "passed": not failures,
        "failures": failures,
        "source_stage": "stage9458_episode_step_structured_probe_static_audit",
        "contract_preflight": str(CONTRACT.relative_to(ROOT)),
        "probe_scale": contract.get("probe_scale"),
        "mode": contract.get("mode"),
        "rows": contract.get("rows"),
        "split_counts": contract.get("split_counts"),
        "manifest_sha256": contract.get("manifest_sha256"),
        "loss_counts": loss_counts,
        "tokenizer_contract": tokenizer,
        "trellis_check": trellis,
        "execution_command": COMMAND,
        "execution_authorized_for_next_stage": not failures,
        "model_execution_authorized_next": not failures,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "authority": {**dict(AUTHORITY_CLOSED), "model_execution_authorized_next": not failures},
    }
    REVIEW.write_text(json.dumps(review, indent=2, sort_keys=True) + "\n")
    summary_authority = {**dict(AUTHORITY_CLOSED), "model_execution_authorized_next": not failures}
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": review["passed"],
        "authority": summary_authority,
        "metrics": {**summary_authority, **review},
        "artifacts": {"review": str(REVIEW.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Authorized only the next tiny target-100M episode-step structured probe if this review passes; decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, controller merge, and promotion remain closed.",
        "next_best_step": "Run Stage9460 tiny target-100M episode-step structured probe under trellis with the reviewed command, then audit telemetry and cleanup proof.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9459 Episode-Step Target-100M Execution Authorization Review",
        "",
        f"Passed: `{review['passed']}`",
        f"Mode: `{review['mode']}`",
        f"Probe scale: `{review['probe_scale']}`",
        f"Rows: `{review['rows']}`",
        f"Trellis torch: `{trellis.get('torch_version')}`",
        f"CUDA available: `{trellis.get('cuda_available')}`",
        "",
        "Only the Stage9460 tiny episode-step structured probe is authorized by this card. Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, controller merge, checkpoint export, and promotion remain closed.",
        "",
    ]))
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": summary_authority, "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows)}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "failures": failures, "execution_authorized_for_next_stage": review["execution_authorized_for_next_stage"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
