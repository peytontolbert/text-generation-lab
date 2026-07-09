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
STAGE = 9674
NAME = "stage9674_neutral_slot_prior_denoise_preexecution"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9673_suffix_choice_prior_fused_denoise_probe_audit.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9668_prefix_primed_sidecar_residual_denoise_preexecution/prefix_primed_sidecar_residual_denoise_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "neutral_slot_prior_denoise_manifest.jsonl"
RUN_DIR = OUT_DIR / "contract_preflight"
AUDIT = OUT_DIR / "neutral_slot_prior_denoise_preexecution_audit.json"
COMMAND_JSON = OUT_DIR / "stage9675_neutral_slot_prior_denoise_probe_command.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "NEUTRAL_SLOT_PRIOR_DENOISE_PREEXECUTION_STAGE9674.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")
OUTPUT_DIR = ROOT / "runs/local/artifacts/stage9675_neutral_slot_prior_denoise_probe"
GENERATION_PREFIX_FIELD = "model_input.active_generation_prefix_span"

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


def nested_value(row: dict[str, Any], path: str) -> Any:
    value: Any = row
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def target_text(row: dict[str, Any]) -> str:
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    return str(target.get("decoder_text") or row.get("decoder_text") or "").strip()


def neutral_slot(target: str) -> dict[str, str]:
    lowered = target.lower()
    if lowered.startswith("return the method invocation target"):
        return {"slot_object": "method_invocation_target", "slot_relation": "localized_repair_step", "slot_constraint": "keep_response"}
    if lowered.startswith("return the project path"):
        return {"slot_object": "project_path", "slot_relation": "relevant_repair_region", "slot_constraint": "if_evidence_missing_guard"}
    if lowered.startswith("return the constant value"):
        return {"slot_object": "constant_value", "slot_relation": "checked_verifier_condition", "slot_constraint": "no_new_value"}
    if lowered.startswith("choose the approved library entry"):
        return {"slot_object": "approved_library_entry", "slot_relation": "wrapper_plan", "slot_constraint": "focused_answer"}
    if lowered.startswith("choose the concrete value"):
        return {"slot_object": "concrete_value", "slot_relation": "current_repair_invariant", "slot_constraint": "no_new_value"}
    if lowered.startswith("select the file path"):
        return {"slot_object": "file_path", "slot_relation": "localized_edit_target", "slot_constraint": "path_reference"}
    if lowered.startswith("select the small constant"):
        return {"slot_object": "small_constant", "slot_relation": "expected_assertion_behavior", "slot_constraint": "keep_value_small"}
    if lowered.startswith("emit the local name"):
        return {"slot_object": "local_name", "slot_relation": "repaired_state_receiver", "slot_constraint": "focused_answer"}
    if lowered.startswith("select the callable endpoint"):
        return {"slot_object": "callable_endpoint", "slot_relation": "verified_patch_operator", "slot_constraint": "use_repo_reference"}
    if lowered.startswith("emit the dependency handle"):
        return {"slot_object": "dependency_handle", "slot_relation": "whitelist_patch", "slot_constraint": "use_symbol"}
    return {"slot_object": "unknown", "slot_relation": "unknown", "slot_constraint": "unknown"}


def active_losses(row: dict[str, Any]) -> list[str]:
    return sorted(key for key, value in (row.get("loss_mask") or {}).items() if bool(value))


def command(*, contract_only: bool) -> list[str]:
    cmd = [
        "env", f"TMPDIR={TMPDIR}", f"TEMP={TMPDIR}", f"TMP={TMPDIR}",
        "conda", "run", "-n", "trellis", "python", str(TRAINER),
        "--repo-root", str(ROOT), "--manifest", str(MANIFEST),
        "--mode", "denoise_repair_probe", "--probe-scale", "target_100m", "--implementation", "transformer",
        "--model-config", str(MODEL_CONFIG), "--tokenizer-json", str(TOKENIZER_JSON),
        "--tokenizer-config", str(TOKENIZER_CONFIG), "--tokenizer-hashlock", str(TOKENIZER_HASHLOCK),
        "--max-train-rows", "20", "--max-eval-rows", "3", "--max-strict-rows", "3",
        "--max-steps", "80", "--batch-size", "2", "--learning-rate", "1e-5",
        "--max-encoder-tokens", "512", "--max-decoder-tokens", "96",
        "--decoder-ce-weight", "0.0", "--structured-aux-weight", "0.0", "--denoise-weight", "1.0", "--eos-loss-weight", "1.0",
        "--enable-generation-audit", "--max-generation-rows", "26", "--max-generation-tokens", "96",
        "--generation-prefix-field", GENERATION_PREFIX_FIELD, "--generation-audit-splits", "train,eval,strict_eval",
        "--require-loss-mask-enforcement-audit", "--no-final-checkpoint-export", "--cleanup-checkpoints-after-probe", "--skip-final-model-save", "1",
        "--output-dir", str(RUN_DIR if contract_only else OUTPUT_DIR),
        "--run-id", "stage9674_neutral_slot_prior_denoise_contract" if contract_only else "stage9675_neutral_slot_prior_denoise_probe",
    ]
    if contract_only:
        cmd.extend(["--contract-only", "--max-steps", "0"])
    else:
        cmd.append("--execution-authorized-for-recovery-probe")
    return cmd


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": summary["authority"], "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    rows: list[dict[str, Any]] = []
    for idx, source_row in enumerate(load_jsonl(SOURCE_MANIFEST)):
        target = target_text(source_row)
        slot = neutral_slot(target)
        row = copy.deepcopy(source_row)
        row["row_id"] = f"stage9674_neutral_slot_prior_denoise_{idx:04d}"
        row["source_stage9668_row_id"] = source_row.get("row_id")
        row["objective_family"] = "neutral_slot_prior_residual_denoise"
        row["route"] = "USE_FOR_DENOISE_REPAIR_WITH_NEUTRAL_SLOT_PRIOR"
        model_input = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        model_input = dict(model_input)
        for key in list(model_input):
            if "suffix_choice_prior" in key:
                model_input.pop(key, None)
        model_input.update({
            "neutral_slot_prior_attached": True,
            "neutral_slot_prior_schema_version": "stage9674_neutral_slot_prior_v1",
            **slot,
        })
        row["model_input"] = model_input
        mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        mask = {key: False for key in mask}
        mask.update({"decoder_ce": False, "structured_aux": False, "denoise_ce": True, "runtime_reward": False})
        row["loss_mask"] = mask
        row["authority"] = dict(AUTHORITY_CLOSED)
        row["neutral_slot_prior"] = slot
        anti = row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}
        anti = dict(anti)
        anti.update({"literal_suffix_choice_prior_removed": True, "neutral_slot_prior_attached": True, "decoder_ce_closed": True, "runtime_closed": True})
        row["anti_cheat"] = anti
        rows.append(row)
    write_jsonl(MANIFEST, rows)
    split_counts = Counter(str(row.get("split")) for row in rows)
    slot_counts = Counter(str((row.get("neutral_slot_prior") or {}).get("slot_object")) for row in rows)
    loss_counts = Counter(loss for row in rows for loss in active_losses(row))
    failures: list[str] = []
    source_metrics = source.get("metrics") if isinstance(source.get("metrics"), dict) else {}
    if source.get("passed") is not False or source_metrics.get("safety_passed") is not True or source_metrics.get("regressed_vs_stage9669") is not True:
        failures.append("stage9673_not_expected_safe_failed_prior_branch")
    if len(rows) != 26:
        failures.append("row_count_not_26")
    if dict(split_counts) != {"train": 20, "eval": 3, "strict_eval": 3}:
        failures.append("split_counts_wrong")
    if dict(loss_counts) != {"denoise_ce": 26}:
        failures.append("loss_counts_not_denoise_only")
    bad_prefix: list[str] = []
    target_visible: list[str] = []
    symbolic_prior_rows: list[str] = []
    for row in rows:
        row_id = str(row.get("row_id"))
        target = target_text(row)
        prefix = str(nested_value(row, GENERATION_PREFIX_FIELD) or "")
        model_text = json.dumps(row.get("model_input") or {}, sort_keys=True)
        if not prefix or prefix == target or not target.startswith(prefix) or len(prefix.split()) > 8 or len(prefix) > 96:
            bad_prefix.append(row_id)
        if target and target in model_text:
            target_visible.append(row_id)
        if "suffix_choice_prior_label" in model_text or "localized_repair_step__" in model_text or "wrapper_plan__" in model_text:
            symbolic_prior_rows.append(row_id)
    if bad_prefix:
        failures.append("prefix_contract_failures")
    if target_visible:
        failures.append("full_target_visible_in_model_input")
    if symbolic_prior_rows:
        failures.append("symbolic_suffix_prior_still_visible")
    if any(any((row.get("authority") or {}).get(key) for key in AUTHORITY_CLOSED) for row in rows):
        failures.append("authority_rows_present")
    if not failures:
        contract = subprocess.run(command(contract_only=True), cwd=ROOT, text=True, capture_output=True, check=False)
        if contract.returncode != 0:
            failures.append("contract_preflight_failed")
    else:
        contract = None
    card = load_json(RUN_DIR / "probe_contract_audit.json")
    if card and card.get("passed") is not True:
        failures.append("contract_card_not_passed")
    audit = {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "slot_object_counts": dict(sorted(slot_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "prefix_bad_rows": bad_prefix,
        "full_target_visible_rows": target_visible,
        "symbolic_prior_rows": symbolic_prior_rows,
        "contract_returncode": None if contract is None else contract.returncode,
        "contract_passed": card.get("passed"),
        "contract_generation_prefix_field": card.get("generation_prefix_field"),
        "contract_loss_counts": card.get("loss_counts"),
        "model_execution_attempted": card.get("model_execution_attempted"),
        "authority": AUTHORITY_RUN if not failures else dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    COMMAND_JSON.write_text(json.dumps({"command": command(contract_only=False), "cwd": str(ROOT), "env": "trellis", "tmpdir": str(TMPDIR), "authority": audit["authority"]}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "If Stage9674 passes, execute Stage9675 neutral-slot prior denoise probe and compare against Stage9669/9673."
    summary = {"stage": STAGE, "stage_name": NAME, "name": NAME, "passed": audit["passed"], "authority": audit["authority"], "metrics": {**{key: bool(audit["authority"].get(key, False)) for key in AUTHORITY_CLOSED}, **audit}, "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "command": str(COMMAND_JSON.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "manifest": str(MANIFEST.relative_to(ROOT)), "run_dir": str(RUN_DIR.relative_to(ROOT))}, "decision": "Prepared neutral slot-prior denoise reconnect after rejecting literal suffix-choice prior labels.", "next_best_step": next_step, "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9674 Neutral Slot Prior Denoise Preexecution", "", f"Passed: `{audit['passed']}`", f"Rows: `{audit['rows']}`", f"Slot object counts: `{audit['slot_object_counts']}`", "", "This removes literal suffix-choice labels from denoise generation input and replaces them with neutral slot features. Denoise CE is the only active loss.", "", f"Next: {next_step}", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "failures": failures, "rows": len(rows), "next_best_step": next_step}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
