#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
    from golden_locked_eval_suite import builder_exclusion_decision, load_locked_source_ids_from_exclusions
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from scripts.golden_locked_eval_suite import builder_exclusion_decision, load_locked_source_ids_from_exclusions  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9689
NAME = "stage9689_slot_template_controller_target_100m_contract_preflight"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9688_locked_eval_guard_graph_attachment.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9678_slot_template_controller_preexecution/slot_template_controller_manifest.jsonl"
EXCLUSIONS = ROOT / "runs/local/artifacts/stage9685_locked_multilingual_task_pack_skeleton/v27_locked_source_exclusions.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
RUN_DIR = OUT_DIR / "contract_only_probe"
AUDIT = OUT_DIR / "slot_template_controller_target_100m_contract_preflight_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SLOT_TEMPLATE_CONTROLLER_TARGET_100M_CONTRACT_PREFLIGHT_STAGE9689.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")
REQUIRED_CONTRACT_ARTIFACTS = [
    "probe_contract_audit.json",
    "loss_by_step.jsonl",
    "eval_loss_by_checkpoint.jsonl",
    "row_field_logits.jsonl",
    "row_field_losses.jsonl",
    "row_gradient_norms.jsonl",
    "activation_summary.jsonl",
    "feature_ablation_attribution.jsonl",
    "activation_patch_recovery.jsonl",
    "row_dynamics_history.jsonl",
    "field_exact_by_cell.json",
    "field_label_vocabs.json",
    "structured_confusion_matrix.json",
    "module_delta_norms.json",
    "failure_bucket_card.json",
    "cleanup_proof.json",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def command() -> list[str]:
    return [
        sys.executable,
        str(TRAINER),
        "--repo-root", str(ROOT),
        "--manifest", str(MANIFEST.relative_to(ROOT)),
        "--mode", "structured_policy_probe",
        "--probe-scale", "target_100m",
        "--implementation", "transformer",
        "--model-config", str(MODEL_CONFIG.relative_to(ROOT)),
        "--tokenizer-json", str(TOKENIZER_JSON.relative_to(ROOT)),
        "--tokenizer-config", str(TOKENIZER_CONFIG.relative_to(ROOT)),
        "--tokenizer-hashlock", str(TOKENIZER_HASHLOCK.relative_to(ROOT)),
        "--max-train-rows", "21",
        "--max-eval-rows", "3",
        "--max-strict-rows", "3",
        "--max-steps", "0",
        "--batch-size", "2",
        "--learning-rate", "2e-4",
        "--max-encoder-tokens", "512",
        "--max-decoder-tokens", "8",
        "--decoder-ce-weight", "0.0",
        "--structured-aux-weight", "1.0",
        "--denoise-weight", "0.0",
        "--require-loss-mask-enforcement-audit",
        "--no-final-checkpoint-export",
        "--cleanup-checkpoints-after-probe",
        "--skip-final-model-save", "1",
        "--output-dir", str(RUN_DIR.relative_to(ROOT)),
        "--run-id", NAME,
        "--contract-only",
    ]


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": summary["next_best_step"],
    })
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


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    rows = load_jsonl(MANIFEST)
    locked_ids = load_locked_source_ids_from_exclusions(EXCLUSIONS)
    locked_decisions = [builder_exclusion_decision(row, locked_ids) for row in rows]
    blocked_rows = [decision for decision in locked_decisions if decision["blocked_from_training"]]

    safety_failures: list[str] = []
    if source.get("passed") is not True:
        safety_failures.append("stage9688_not_passed")
    if not rows:
        safety_failures.append("manifest_empty")
    if blocked_rows:
        safety_failures.append("selected_manifest_contains_locked_eval_sources")

    run = None
    if not safety_failures:
        env = dict(os.environ)
        env.update({"TMPDIR": str(TMPDIR), "TEMP": str(TMPDIR), "TMP": str(TMPDIR)})
        run = subprocess.run(command(), cwd=ROOT, env=env, text=True, capture_output=True, check=False)
        if run.returncode != 0:
            safety_failures.append("contract_only_trainer_failed")

    contract = load_json(RUN_DIR / "probe_contract_audit.json")
    missing_artifacts = [name for name in REQUIRED_CONTRACT_ARTIFACTS if not (RUN_DIR / name).exists()]
    if not contract:
        safety_failures.append("missing_probe_contract_audit")
    if missing_artifacts:
        safety_failures.append("missing_contract_artifacts")
    if contract and contract.get("passed") is not True:
        safety_failures.append("probe_contract_not_passed")
    if contract.get("probe_scale") != "target_100m":
        safety_failures.append("not_target_100m_contract")
    if contract.get("implementation") != "transformer":
        safety_failures.append("not_transformer_contract")
    if contract.get("model_execution_attempted") is not False:
        safety_failures.append("model_execution_attempted_in_contract_only")
    if contract.get("authority_rows") != 0:
        safety_failures.append("authority_rows_present")
    if contract.get("unsafe_loss_rows") != 0:
        safety_failures.append("unsafe_loss_rows_present")
    loss_counts = contract.get("loss_counts") if isinstance(contract.get("loss_counts"), dict) else {}
    if loss_counts.get("suffix_choice_ce") != 27:
        safety_failures.append("suffix_choice_ce_count_not_27")
    for forbidden_loss in ["decoder_ce", "denoise_ce", "runtime_reward"]:
        if loss_counts.get(forbidden_loss, 0) != 0:
            safety_failures.append(f"forbidden_loss_enabled:{forbidden_loss}")

    tokenizer_contract = contract.get("tokenizer_contract") if isinstance(contract.get("tokenizer_contract"), dict) else {}
    impl_contract = contract.get("implementation_contract") if isinstance(contract.get("implementation_contract"), dict) else {}
    guard = impl_contract.get("target_implementation_guard") if isinstance(impl_contract.get("target_implementation_guard"), dict) else {}
    if tokenizer_contract.get("byte_fallback_used_when_unset") is not False:
        safety_failures.append("tokenizer_fell_back_to_byte")
    if tokenizer_contract.get("target_100m_vocab_size") != 1506:
        safety_failures.append("target_100m_vocab_not_1506")
    if guard.get("allowed_for_recovered_100m_target") is not True:
        safety_failures.append("target_implementation_guard_failed")

    audit = {
        "passed": not safety_failures,
        "safety_failures": safety_failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "manifest_rows": len(rows),
        "locked_source_ids_loaded": len(locked_ids),
        "locked_guard_blocked_rows": len(blocked_rows),
        "blocked_row_decisions": blocked_rows[:20],
        "trainer_returncode": None if run is None else run.returncode,
        "trainer_stdout_tail": "" if run is None else run.stdout[-4000:],
        "trainer_stderr_tail": "" if run is None else run.stderr[-4000:],
        "contract_passed": contract.get("passed"),
        "probe_scale": contract.get("probe_scale"),
        "implementation": contract.get("implementation"),
        "rows": contract.get("rows"),
        "split_counts": contract.get("split_counts"),
        "loss_counts": loss_counts,
        "authority_rows": contract.get("authority_rows"),
        "unsafe_loss_rows": contract.get("unsafe_loss_rows"),
        "model_execution_attempted": contract.get("model_execution_attempted"),
        "tokenizer_contract": tokenizer_contract,
        "target_implementation_guard": guard,
        "missing_contract_artifacts": missing_artifacts,
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    next_step = "Build Stage9690 execution-authorization review for the slot-template controller tiny target-100M structured probe, or select the next non-template non-eval training package if controller execution remains unnecessary."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "contract_audit": str((RUN_DIR / "probe_contract_audit.json").relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
            "run_dir": str(RUN_DIR.relative_to(ROOT)),
        },
        "decision": "Validated the Stage9678 slot-template controller manifest under locked-source guard and target-100M contract-only trainer preflight.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9689 Slot-Template Controller Target-100M Contract Preflight",
        "",
        f"Passed: `{summary['passed']}`",
        f"Manifest rows: `{audit['manifest_rows']}`",
        f"Locked guard blocked rows: `{audit['locked_guard_blocked_rows']}`",
        f"Probe scale: `{audit['probe_scale']}`",
        f"Implementation: `{audit['implementation']}`",
        f"Loss counts: `{audit['loss_counts']}`",
        f"Model execution attempted: `{audit['model_execution_attempted']}`",
        "",
        "This is contract-only. No model forward/backward, runtime, Gemma, harness, scoring, source/body emission, checkpoint export, or promotion is authorized.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "safety_failures": safety_failures,
        "probe_scale": audit["probe_scale"],
        "loss_counts": audit["loss_counts"],
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if safety_failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
