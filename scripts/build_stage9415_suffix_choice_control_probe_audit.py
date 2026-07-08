#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9415
NAME = "stage9415_suffix_choice_control_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9414_suffix_choice_control_preexecution.json"
RUN_DIR = ROOT / "runs/local/artifacts/stage9415_suffix_choice_control_probe"
AUDIT = RUN_DIR / "stage9415_suffix_choice_control_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SUFFIX_CHOICE_CONTROL_PROBE_AUDIT_STAGE9415.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
REQUIRED = ["probe_contract_audit.json", "execution_result.json", "loss_by_step.jsonl", "eval_loss_by_checkpoint.jsonl", "row_field_logits.jsonl", "row_field_losses.jsonl", "row_gradient_norms.jsonl", "activation_summary.jsonl", "feature_ablation_attribution.jsonl", "activation_patch_recovery.jsonl", "row_dynamics_history.jsonl", "field_exact_by_cell.json", "field_label_vocabs.json", "structured_confusion_matrix.json", "module_delta_norms.json", "failure_bucket_card.json", "cleanup_proof.json"]
TARGET_FAMILIES = {"expected_assertion_behavior__keep_value_small", "current_repair_invariant__do_not_introduce"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def main() -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    contract = load_json(RUN_DIR / "probe_contract_audit.json")
    execution = load_json(RUN_DIR / "execution_result.json")
    logits = load_jsonl(RUN_DIR / "row_field_logits.jsonl")
    missing = [name for name in REQUIRED if not (RUN_DIR / name).exists() or ((RUN_DIR / name).suffix == ".jsonl" and (RUN_DIR / name).stat().st_size == 0)]
    suffix_records = [row for row in logits if row.get("field") == "suffix_choice"]
    by_split = Counter(str(row.get("split")) for row in suffix_records)
    exact_by_split = Counter(str(row.get("split")) for row in suffix_records if row.get("correct"))
    target_records = [row for row in suffix_records if row.get("split") in {"eval", "strict_eval"} and row.get("target") in TARGET_FAMILIES]
    target_exact = sum(1 for row in target_records if row.get("correct"))
    high_conf_wrong = [row for row in suffix_records if (not row.get("correct")) and float(row.get("confidence") or 0.0) >= 0.8]
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9414_not_passed")
    if contract.get("passed") is not True:
        failures.append("contract_not_passed")
    losses = contract.get("loss_counts", {}) if isinstance(contract.get("loss_counts"), dict) else {}
    if losses.get("suffix_choice_ce") != 31:
        failures.append("suffix_choice_row_count_mismatch")
    for forbidden in ["decoder_ce", "denoise_ce", "runtime_reward"]:
        if losses.get(forbidden, 0) or execution.get(f"{forbidden}_rows", 0):
            failures.append(f"forbidden_loss_opened:{forbidden}")
    if execution.get("runtime_executed") is not False or execution.get("gemma_executed") is not False or execution.get("harness_executed") is not False:
        failures.append("forbidden_execution_surface_opened")
    if execution.get("final_checkpoint_exported") is not False:
        failures.append("checkpoint_exported")
    if missing:
        failures.append("required_artifacts_missing")
    # Structured probe row_field_logits currently records heldout eval/strict rows;
    # train dynamics are carried by row_dynamics_history and row_field_losses.
    expected_eval_splits = {"eval": 9, "strict_eval": 7}
    if dict(by_split) != expected_eval_splits:
        failures.append("suffix_choice_eval_logit_split_counts_bad")
    safety_gate_passed = not failures
    strict_exact = exact_by_split.get("strict_eval", 0)
    eval_exact = exact_by_split.get("eval", 0)
    quality_gate_passed = bool(
        safety_gate_passed
        and eval_exact >= 8
        and strict_exact >= 6
        and len(target_records) == 4
        and target_exact == 4
        and len(high_conf_wrong) == 0
    )
    audit = {
        "passed": safety_gate_passed and quality_gate_passed,
        "safety_gate_passed": safety_gate_passed,
        "quality_gate_passed": quality_gate_passed,
        "failures": failures,
        "missing_artifacts": missing,
        "suffix_choice_records": len(suffix_records),
        "suffix_choice_by_split": dict(sorted(by_split.items())),
        "suffix_choice_exact_by_split": dict(sorted(exact_by_split.items())),
        "target_pair_records": len(target_records),
        "target_pair_exact_rows": target_exact,
        "high_confidence_wrong_rows": len(high_conf_wrong),
        "high_confidence_wrong_examples": high_conf_wrong[:10],
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "If passed, reconnect suffix_choice predictions to the denoise generation manifest; otherwise inspect high-confidence wrong suffix-choice rows." if quality_gate_passed else "Inspect suffix-choice control failures before any further generation probe."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "run_dir": str(RUN_DIR.relative_to(ROOT))},
        "decision": "Audited structured suffix-choice control probe; decoder CE and denoise CE remain closed.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9415 Suffix Choice Control Probe Audit", "", f"Passed: `{audit['passed']}`", f"Safety gate passed: `{audit['safety_gate_passed']}`", f"Quality gate passed: `{audit['quality_gate_passed']}`", f"Exact by split: `{audit['suffix_choice_exact_by_split']}`", f"Target-pair exact: `{target_exact}` / `{len(target_records)}`", f"High-confidence wrong rows: `{len(high_conf_wrong)}`", "", "Decoder CE, denoise CE, runtime, Gemma, harness, and checkpoint export remain closed.", ""]), encoding="utf-8")
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    reg_rows = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = reg_rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(reg_rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {"safety": safety_gate_passed, "quality": quality_gate_passed, "exact_by_split": dict(sorted(exact_by_split.items())), "target_pair_exact": f"{target_exact}/{len(target_records)}"}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
