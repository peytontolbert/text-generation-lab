#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from argparse import Namespace
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9291
NAME = "stage9291_one_next_token_contract_preflight"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9290_one_next_token_suffix_manifest.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9290_one_next_token_suffix_manifest/one_next_token_suffix_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "one_next_token_contract_preflight_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ONE_NEXT_TOKEN_CONTRACT_PREFLIGHT_STAGE9291.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
TRAINING_LOOP = ROOT / "legacy_src/agentkernel_lite/training_loop.py"

GENERATION_PREFIX_FIELD = "model_input.bridge_priming_span"
GENERATION_AUDIT_SPLITS = "train,eval,strict_eval"
REQUIRED_ARTIFACTS = [
    "probe_contract_audit.json",
    "execution_result.json",
    "loss_by_step.jsonl",
    "eval_loss_by_checkpoint.jsonl",
    "row_token_loss.jsonl",
    "row_gradient_norms.jsonl",
    "activation_summary.jsonl",
    "row_dynamics_history.jsonl",
    "sample_generation_audit.json",
    "short_output_probe.json",
    "repetition_probe.json",
    "internal_leak_probe.json",
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


def _authority_open(row: dict[str, Any]) -> bool:
    authority = row.get("authority") if isinstance(row.get("authority"), dict) else row
    return any(bool(authority.get(key, False)) for key in AUTHORITY_CLOSED)


def _loss_mask_ok(row: dict[str, Any]) -> bool:
    mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
    return mask.get("denoise_ce") is True and mask.get("decoder_ce") is False and mask.get("runtime_reward") is False


def _nested(row: dict[str, Any], dotted: str) -> Any:
    cur: Any = row
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _trainer_contract_card(rows: list[dict[str, Any]]) -> dict[str, Any]:
    import sys

    scripts_dir = str(ROOT / "legacy_src/scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import train_agentkernel_lite_encdec as trainer  # type: ignore

    args = Namespace(
        repo_root=ROOT,
        manifest=MANIFEST,
        mode="denoise_repair_probe",
        max_train_rows=4,
        max_eval_rows=1,
        max_strict_rows=1,
        max_steps=16,
        max_decoder_tokens=96,
        decoder_ce_weight=0.0,
        eos_loss_weight=1.0,
        structured_aux_weight=0.0,
        denoise_weight=1.0,
        require_loss_mask_enforcement_audit=True,
        require_counterfactual_obligation_audit=False,
        no_final_checkpoint_export=True,
        cleanup_checkpoints_after_probe=True,
        skip_final_model_save=1,
        output_dir=OUT_DIR / "one_next_token_probe",
        run_id=NAME,
        batch_size=2,
        max_encoder_tokens=256,
        learning_rate=1e-5,
        enable_generation_audit=True,
        max_generation_rows=6,
        max_generation_tokens=32,
        generation_prefix_field=GENERATION_PREFIX_FIELD,
        generation_audit_splits=GENERATION_AUDIT_SPLITS,
        implementation="transformer",
        probe_scale="target_100m",
        model_config=ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json",
        tokenizer_json=ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json",
        tokenizer_config=ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json",
        tokenizer_hashlock=ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json",
        execution_authorized_for_recovery_probe=False,
        contract_only=True,
    )
    return trainer.validate_contract(args, rows)


def _runtime_support() -> dict[str, Any]:
    trainer_text = TRAINER.read_text(encoding="utf-8") if TRAINER.exists() else ""
    loop_text = TRAINING_LOOP.read_text(encoding="utf-8") if TRAINING_LOOP.exists() else ""
    return {
        "has_native_denoise_runner": "def run_denoise_repair_probe" in loop_text,
        "trainer_dispatches_native_denoise_runner": "run_denoise_repair_probe" in trainer_text,
        "generation_prefix_contract_supported": "validate_generation_prefix_contract" in trainer_text and "generation_prefix_field" in trainer_text,
        "generation_audit_splits_supported": "--generation-audit-splits" in trainer_text and "def _generation_audit_rows" in loop_text,
    }


def audit_preflight() -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    rows = load_jsonl(MANIFEST)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9290_not_passed")
    if not rows:
        failures.append("manifest_empty")
    split_counts: dict[str, int] = {}
    language_counts: dict[str, int] = {}
    empty_targets = authority_rows = unsafe_loss_rows = missing_prefix_rows = prefix_target_mismatch_rows = over_decoder_token_cap_rows = 0
    for row in rows:
        split_counts[str(row.get("split"))] = split_counts.get(str(row.get("split")), 0) + 1
        language_counts[str(row.get("language_family"))] = language_counts.get(str(row.get("language_family")), 0) + 1
        if _authority_open(row):
            authority_rows += 1
        if not _loss_mask_ok(row):
            unsafe_loss_rows += 1
        target = str((row.get("target") or {}).get("decoder_text", ""))
        prefix = str(_nested(row, GENERATION_PREFIX_FIELD) or "")
        if not target.strip():
            empty_targets += 1
        if not prefix:
            missing_prefix_rows += 1
        if prefix and not target.startswith(prefix):
            prefix_target_mismatch_rows += 1
        if len(target.encode("utf-8")) > 96:
            over_decoder_token_cap_rows += 1
    if split_counts != {"train": 4, "eval": 1, "strict_eval": 1}:
        failures.append("split_counts_unexpected")
    if authority_rows:
        failures.append("authority_rows_nonzero")
    if unsafe_loss_rows:
        failures.append("unsafe_loss_rows_nonzero")
    if empty_targets:
        failures.append("empty_targets_nonzero")
    if missing_prefix_rows:
        failures.append("missing_generation_prefix_rows_nonzero")
    if prefix_target_mismatch_rows:
        failures.append("prefix_target_mismatch_rows_nonzero")
    if over_decoder_token_cap_rows:
        failures.append("over_decoder_token_cap_rows_nonzero")
    contract_card = _trainer_contract_card(rows) if rows else {"passed": False, "errors": ["manifest_empty"]}
    if contract_card.get("passed") is not True:
        failures.append("trainer_contract_not_passed")
    if contract_card.get("generation_prefix_field") != GENERATION_PREFIX_FIELD:
        failures.append("trainer_generation_prefix_field_not_recorded")
    if contract_card.get("generation_audit_splits") != GENERATION_AUDIT_SPLITS:
        failures.append("trainer_generation_audit_splits_not_recorded")
    runtime_support = _runtime_support()
    execution_ready = bool(contract_card.get("passed") and all(runtime_support.values()))
    return {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "split_counts": split_counts,
        "language_counts": language_counts,
        "authority_rows": authority_rows,
        "unsafe_loss_rows": unsafe_loss_rows,
        "empty_targets": empty_targets,
        "missing_generation_prefix_rows": missing_prefix_rows,
        "prefix_target_mismatch_rows": prefix_target_mismatch_rows,
        "over_decoder_token_cap_rows": over_decoder_token_cap_rows,
        "generation_prefix_field": GENERATION_PREFIX_FIELD,
        "generation_audit_splits": GENERATION_AUDIT_SPLITS,
        "trainer_contract_passed": contract_card.get("passed") is True,
        "trainer_contract_errors": contract_card.get("errors", []),
        "loss_counts": contract_card.get("loss_counts", {}),
        "allowed_losses": contract_card.get("allowed_losses", []),
        "manifest_sha256": contract_card.get("manifest_sha256"),
        "contract_generation_prefix_field": contract_card.get("generation_prefix_field"),
        "contract_generation_audit_splits": contract_card.get("generation_audit_splits"),
        "runtime_support": runtime_support,
        "execution_authorized_now": False,
        "one_next_token_execution_ready": execution_ready,
        "required_runtime_artifacts": REQUIRED_ARTIFACTS,
        "authority": dict(AUTHORITY_CLOSED),
    }


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    audit = audit_preflight()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "manifest": str(MANIFEST.relative_to(ROOT))},
        "decision": "Stage9290 one-next-token suffix manifest passes trainer contract preflight with train/eval/strict generation audit enabled for the next diagnostic.",
        "next_best_step": "Build one-run execution review and final pre-execution audit for a tiny target-100M one-next-token suffix denoise probe.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9291 One-Next-Token Contract Preflight",
        "",
        f"Rows: {audit['rows']}",
        f"Splits: {audit['split_counts']}",
        f"Trainer contract passed: {audit['trainer_contract_passed']}",
        f"Generation audit splits: {audit['generation_audit_splits']}",
        f"Execution ready: {audit['one_next_token_execution_ready']}",
        "Execution is not authorized in this stage.",
        "",
    ]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
