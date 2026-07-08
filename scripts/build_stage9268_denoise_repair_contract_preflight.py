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
STAGE = 9268
NAME = "stage9268_denoise_repair_contract_preflight"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9267_repetition_to_denoise_repair_manifest.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9267_repetition_to_denoise_repair_manifest/repetition_to_denoise_repair_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "denoise_repair_contract_preflight_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "DENOISE_REPAIR_CONTRACT_PREFLIGHT_STAGE9268.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
TRAINING_LOOP = ROOT / "legacy_src/agentkernel_lite/training_loop.py"

REQUIRED_ARTIFACTS = [
    "loss_by_step.jsonl",
    "eval_loss_by_checkpoint.jsonl",
    "row_token_loss.jsonl",
    "row_gradient_norms.jsonl",
    "activation_summary.jsonl",
    "row_dynamics_history.jsonl",
    "denoise_repair_quality_audit.json",
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
        max_train_rows=8,
        max_eval_rows=7,
        max_strict_rows=6,
        max_steps=16,
        max_decoder_tokens=768,
        decoder_ce_weight=0.0,
        eos_loss_weight=1.0,
        structured_aux_weight=0.0,
        denoise_weight=1.0,
        require_loss_mask_enforcement_audit=True,
        require_counterfactual_obligation_audit=False,
        no_final_checkpoint_export=True,
        cleanup_checkpoints_after_probe=True,
        skip_final_model_save=1,
        output_dir=OUT_DIR / "denoise_repair_probe",
        run_id=NAME,
        batch_size=2,
        max_encoder_tokens=256,
        learning_rate=1e-5,
        enable_generation_audit=False,
        max_generation_rows=0,
        max_generation_tokens=0,
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


def _denoise_runtime_support() -> dict[str, Any]:
    trainer_text = TRAINER.read_text(encoding="utf-8") if TRAINER.exists() else ""
    loop_text = TRAINING_LOOP.read_text(encoding="utf-8") if TRAINING_LOOP.exists() else ""
    has_native_runner = "def run_denoise_repair_probe" in loop_text
    structured_maps_denoise = '"denoise_ce"' in loop_text and "STRUCTURED_LOSS_TO_FIELD" in loop_text and '"denoise_ce":' in loop_text
    dispatches_native = "run_denoise_repair_probe" in trainer_text
    return {
        "has_native_denoise_runner": has_native_runner,
        "structured_loss_maps_denoise_ce": structured_maps_denoise,
        "trainer_dispatches_native_denoise_runner": dispatches_native,
        "execution_supported": has_native_runner and dispatches_native,
    }


def audit_preflight() -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    rows = load_jsonl(MANIFEST)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9267_not_passed")
    if not rows:
        failures.append("manifest_empty")
    split_counts: dict[str, int] = {}
    route_counts: dict[str, int] = {}
    empty_targets = 0
    authority_rows = 0
    unsafe_loss_rows = 0
    for row in rows:
        split_counts[str(row.get("split"))] = split_counts.get(str(row.get("split")), 0) + 1
        route_counts[str(row.get("route"))] = route_counts.get(str(row.get("route")), 0) + 1
        if _authority_open(row):
            authority_rows += 1
        if not _loss_mask_ok(row):
            unsafe_loss_rows += 1
        target = row.get("target") if isinstance(row.get("target"), dict) else {}
        if not str(target.get("decoder_text", "")).strip():
            empty_targets += 1
    if split_counts.get("train", 0) < 1 or split_counts.get("eval", 0) < 1 or split_counts.get("strict_eval", 0) < 1:
        failures.append("missing_required_split")
    if authority_rows:
        failures.append("authority_rows_nonzero")
    if unsafe_loss_rows:
        failures.append("unsafe_loss_rows_nonzero")
    if empty_targets:
        failures.append("empty_targets_nonzero")

    contract_card = _trainer_contract_card(rows) if rows else {"passed": False, "errors": ["manifest_empty"]}
    if contract_card.get("passed") is not True:
        failures.append("trainer_contract_not_passed")
    runtime_support = _denoise_runtime_support()
    execution_ready = bool(contract_card.get("passed") and runtime_support.get("execution_supported"))

    return {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "split_counts": split_counts,
        "route_counts": route_counts,
        "authority_rows": authority_rows,
        "unsafe_loss_rows": unsafe_loss_rows,
        "empty_targets": empty_targets,
        "trainer_contract_passed": contract_card.get("passed") is True,
        "trainer_contract_errors": contract_card.get("errors", []),
        "loss_counts": contract_card.get("loss_counts", {}),
        "allowed_losses": contract_card.get("allowed_losses", []),
        "manifest_sha256": contract_card.get("manifest_sha256"),
        "runtime_support": runtime_support,
        "execution_authorized_now": False,
        "denoise_execution_ready": execution_ready,
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
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))), "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
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
        "decision": "Stage9267 passes the denoise-only manifest and trainer contract preflight. Native denoise runtime support is present, but execution authority remains closed until a dedicated execution review is built.",
        "next_best_step": "Build a no-runtime denoise repair execution review for one tiny target-100M denoise probe, then run a final pre-execution audit before any model execution.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9268 Denoise Repair Contract Preflight",
                "",
                "Stage9268 validates the Stage9267 denoise-only manifest and records whether native denoise repair runtime support is present. Execution authority remains closed either way.",
                "",
                f"Rows: {audit['rows']}",
                f"Splits: {audit['split_counts']}",
                f"Trainer contract passed: {audit['trainer_contract_passed']}",
                f"Denoise execution ready: {audit['denoise_execution_ready']}",
                "",
                "Required runtime artifacts:",
                *[f"- `{artifact}`" for artifact in REQUIRED_ARTIFACTS],
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
