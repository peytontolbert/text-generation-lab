#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import subprocess
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9676
NAME = "stage9676_slot_specific_micro_support_preexecution"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9675_neutral_slot_prior_denoise_probe_audit.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9674_neutral_slot_prior_denoise_preexecution/neutral_slot_prior_denoise_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "slot_specific_micro_support_denoise_manifest.jsonl"
RUN_DIR = OUT_DIR / "contract_preflight"
AUDIT = OUT_DIR / "slot_specific_micro_support_preexecution_audit.json"
COMMAND_JSON = OUT_DIR / "stage9677_slot_specific_micro_support_denoise_probe_command.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SLOT_SPECIFIC_MICRO_SUPPORT_PREEXECUTION_STAGE9676.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")
OUTPUT_DIR = ROOT / "runs/local/artifacts/stage9677_slot_specific_micro_support_denoise_probe"
GENERATION_PREFIX_FIELD = "model_input.active_generation_prefix_span"

PASSING_SLOTS = {"approved_library_entry", "local_name"}
FAILING_TRAIN_SUPPORT_SLOTS = {
    "callable_endpoint",
    "concrete_value",
    "constant_value",
    "dependency_handle",
    "file_path",
    "method_invocation_target",
    "project_path",
}

AUTHORITY_RUN = dict(AUTHORITY_CLOSED)
AUTHORITY_RUN["model_execution_authorized_next"] = True
AUTHORITY_RUN["denoise_ce_training_authorized_next"] = True


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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


def active_losses(row: dict[str, Any]) -> list[str]:
    return sorted(key for key, value in (row.get("loss_mask") or {}).items() if bool(value))


def force_denoise_only(row: dict[str, Any]) -> None:
    mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
    row["loss_mask"] = {key: False for key in mask}
    row["loss_mask"].update({"decoder_ce": False, "structured_aux": False, "denoise_ce": True, "runtime_reward": False})
    row["authority"] = dict(AUTHORITY_CLOSED)


def prepare_original_row(row: dict[str, Any]) -> dict[str, Any]:
    patched = copy.deepcopy(row)
    patched["source_stage9674_row_id"] = row.get("row_id")
    patched["objective_family"] = "slot_specific_micro_support_residual_denoise"
    patched["route"] = "USE_FOR_DENOISE_REPAIR_WITH_SLOT_MICRO_SUPPORT"
    model_input = patched.get("model_input") if isinstance(patched.get("model_input"), dict) else {}
    model_input = dict(model_input)
    model_input.update({
        "slot_micro_support_package": "stage9676",
        "slot_micro_support_row_kind": "original",
        "slot_micro_support_train_only": patched.get("split") == "train",
    })
    patched["model_input"] = model_input
    anti = patched.get("anti_cheat") if isinstance(patched.get("anti_cheat"), dict) else {}
    anti = dict(anti)
    anti.update({
        "stage9676_slot_micro_support": True,
        "support_rows_train_only": True,
        "heldout_targets_not_copied_to_support": True,
        "decoder_ce_closed": True,
        "runtime_closed": True,
    })
    patched["anti_cheat"] = anti
    force_denoise_only(patched)
    return patched


def support_row(source: dict[str, Any], support_index: int) -> dict[str, Any]:
    row = copy.deepcopy(source)
    slot = str((row.get("neutral_slot_prior") or {}).get("slot_object") or "unknown")
    row["row_id"] = f"stage9676_slot_micro_support_{support_index:04d}"
    row["source_stage9674_row_id"] = source.get("row_id")
    row["split"] = "train"
    row["source_kind"] = "real_train_row_micro_support"
    row["objective_family"] = "slot_specific_micro_support_residual_denoise"
    row["route"] = "USE_FOR_DENOISE_REPAIR_WITH_SLOT_MICRO_SUPPORT"
    model_input = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
    model_input = dict(model_input)
    model_input.update({
        "slot_micro_support_package": "stage9676",
        "slot_micro_support_row_kind": "train_duplicate_weight",
        "slot_micro_support_family": slot,
        "slot_micro_support_train_only": True,
        "slot_micro_support_source_split": source.get("split"),
    })
    row["model_input"] = model_input
    anti = row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}
    anti = dict(anti)
    anti.update({
        "stage9676_slot_micro_support": True,
        "support_rows_train_only": True,
        "support_source_split": source.get("split"),
        "support_from_heldout_row": False,
        "decoder_ce_closed": True,
        "runtime_closed": True,
    })
    row["anti_cheat"] = anti
    force_denoise_only(row)
    return row


def synthetic_small_constant_support(template: dict[str, Any], support_index: int, target: str) -> dict[str, Any]:
    row = copy.deepcopy(template)
    row["row_id"] = f"stage9676_slot_micro_support_{support_index:04d}"
    row["source_stage9674_row_id"] = template.get("row_id")
    row["split"] = "train"
    row["source_kind"] = "synthetic_diagnostic_small_constant_support"
    row["objective_family"] = "slot_specific_micro_support_residual_denoise"
    row["route"] = "USE_FOR_DENOISE_REPAIR_WITH_SLOT_MICRO_SUPPORT"
    row["target"] = {
        "decoder_text": target,
        "source_stage": STAGE,
        "target_authority": "synthetic_diagnostic_train_only_small_constant_support",
    }
    row["corrupted_output"] = "Select the small constant that should preserve the assertion"
    model_input = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
    model_input = dict(model_input)
    model_input.update({
        "active_generation_prefix_span": "Select the small constant that",
        "active_generation_prefix_words": 5,
        "slot_micro_support_package": "stage9676",
        "slot_micro_support_row_kind": "synthetic_train_analog",
        "slot_micro_support_family": "small_constant",
        "slot_micro_support_train_only": True,
        "slot_micro_support_source_split": template.get("split"),
        "clean_target_visible_in_model_input": False,
        "remaining_suffix_hidden_from_model_input": True,
    })
    row["model_input"] = model_input
    row["neutral_slot_prior"] = {
        "slot_object": "small_constant",
        "slot_relation": "expected_assertion_behavior",
        "slot_constraint": "keep_value_small",
    }
    anti = row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}
    anti = dict(anti)
    anti.update({
        "stage9676_slot_micro_support": True,
        "support_rows_train_only": True,
        "support_source_split": template.get("split"),
        "support_from_heldout_row": False,
        "synthetic_support_not_exact_heldout_target": True,
        "decoder_ce_closed": True,
        "runtime_closed": True,
    })
    row["anti_cheat"] = anti
    force_denoise_only(row)
    return row


def command(*, contract_only: bool, train_rows: int, total_rows: int) -> list[str]:
    cmd = [
        "env", f"TMPDIR={TMPDIR}", f"TEMP={TMPDIR}", f"TMP={TMPDIR}",
        "conda", "run", "-n", "trellis", "python", str(TRAINER),
        "--repo-root", str(ROOT), "--manifest", str(MANIFEST),
        "--mode", "denoise_repair_probe", "--probe-scale", "target_100m", "--implementation", "transformer",
        "--model-config", str(MODEL_CONFIG), "--tokenizer-json", str(TOKENIZER_JSON),
        "--tokenizer-config", str(TOKENIZER_CONFIG), "--tokenizer-hashlock", str(TOKENIZER_HASHLOCK),
        "--max-train-rows", str(train_rows), "--max-eval-rows", "3", "--max-strict-rows", "3",
        "--max-steps", "120", "--batch-size", "2", "--learning-rate", "1e-5",
        "--max-encoder-tokens", "512", "--max-decoder-tokens", "96",
        "--decoder-ce-weight", "0.0", "--structured-aux-weight", "0.0", "--denoise-weight", "1.0", "--eos-loss-weight", "1.0",
        "--enable-generation-audit", "--max-generation-rows", str(total_rows), "--max-generation-tokens", "96",
        "--generation-prefix-field", GENERATION_PREFIX_FIELD, "--generation-audit-splits", "train,eval,strict_eval",
        "--require-loss-mask-enforcement-audit", "--no-final-checkpoint-export", "--cleanup-checkpoints-after-probe", "--skip-final-model-save", "1",
        "--output-dir", str(RUN_DIR if contract_only else OUTPUT_DIR),
        "--run-id", "stage9676_slot_specific_micro_support_contract" if contract_only else "stage9677_slot_specific_micro_support_denoise_probe",
    ]
    if contract_only:
        cmd.extend(["--contract-only", "--max-steps", "0"])
    else:
        cmd.append("--execution-authorized-for-recovery-probe")
    return cmd


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "authority": summary["authority"],
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
    original_rows = [prepare_original_row(row) for row in load_jsonl(SOURCE_MANIFEST)]
    rows = list(original_rows)

    train_by_slot: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in original_rows:
        slot = str((row.get("neutral_slot_prior") or {}).get("slot_object") or "unknown")
        if row.get("split") == "train":
            train_by_slot[slot].append(row)

    support_index = 0
    support_rows: list[dict[str, Any]] = []
    for slot in sorted(FAILING_TRAIN_SUPPORT_SLOTS):
        for source_row in train_by_slot.get(slot, []):
            support_rows.append(support_row(source_row, support_index))
            support_index += 1

    small_constant_templates = [
        row for row in original_rows
        if str((row.get("neutral_slot_prior") or {}).get("slot_object")) == "small_constant"
    ]
    if small_constant_templates:
        support_rows.append(synthetic_small_constant_support(
            small_constant_templates[0],
            support_index,
            "Select the small constant that preserves the checked assertion behavior. Keep the value small",
        ))
        support_index += 1
        support_rows.append(synthetic_small_constant_support(
            small_constant_templates[0],
            support_index,
            "Select the small constant that maintains the verifier assertion behavior. Keep the value small",
        ))
    rows.extend(support_rows)
    write_jsonl(MANIFEST, rows)

    failures: list[str] = []
    source_metrics = source.get("metrics") if isinstance(source.get("metrics"), dict) else {}
    if source.get("passed") is not False or source_metrics.get("safety_passed") is not True:
        failures.append("stage9675_not_expected_safe_failed_source")
    if int(source_metrics.get("exact_match_rows") or 0) != 6 or int(source_metrics.get("degenerate_repetition_rows") or 0) != 1:
        failures.append("stage9675_failure_profile_changed")

    split_counts = Counter(str(row.get("split")) for row in rows)
    slot_counts = Counter(str((row.get("neutral_slot_prior") or {}).get("slot_object")) for row in rows)
    support_slot_counts = Counter(str((row.get("neutral_slot_prior") or {}).get("slot_object")) for row in support_rows)
    loss_counts = Counter(loss for row in rows for loss in active_losses(row))
    train_rows = split_counts.get("train", 0)
    total_rows = len(rows)
    if split_counts.get("eval") != 3 or split_counts.get("strict_eval") != 3:
        failures.append("heldout_split_counts_changed")
    if any(row.get("split") != "train" for row in support_rows):
        failures.append("support_rows_not_train_only")
    if dict(loss_counts) != {"denoise_ce": total_rows}:
        failures.append("loss_counts_not_denoise_only")
    if any(slot in support_slot_counts for slot in PASSING_SLOTS):
        failures.append("support_added_for_already_passing_slots")
    if "small_constant" not in support_slot_counts:
        failures.append("small_constant_no_train_support")

    original_eval_strict_targets = {
        target_text(row)
        for row in original_rows
        if row.get("split") in {"eval", "strict_eval"}
    }
    support_target_texts = {target_text(row) for row in support_rows}
    heldout_template_overlap = sorted(original_eval_strict_targets & support_target_texts)
    synthetic_support_texts = {
        target_text(row)
        for row in support_rows
        if row.get("source_kind") == "synthetic_diagnostic_small_constant_support"
    }
    copied_heldout_synthetic_targets = sorted(original_eval_strict_targets & synthetic_support_texts)
    if copied_heldout_synthetic_targets:
        failures.append("heldout_target_copied_to_synthetic_support")

    bad_prefix: list[str] = []
    target_visible: list[str] = []
    symbolic_prior_rows: list[str] = []
    heldout_support_sources: list[str] = []
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
        if row.get("source_kind") in {"real_train_row_micro_support", "synthetic_diagnostic_small_constant_support"}:
            source_split = str((row.get("model_input") or {}).get("slot_micro_support_source_split") or "")
            if source_split != "train" and row.get("source_kind") != "synthetic_diagnostic_small_constant_support":
                heldout_support_sources.append(row_id)
    if bad_prefix:
        failures.append("prefix_contract_failures")
    if target_visible:
        failures.append("full_target_visible_in_model_input")
    if symbolic_prior_rows:
        failures.append("symbolic_suffix_prior_still_visible")
    if heldout_support_sources:
        failures.append("real_support_from_heldout_row")
    if any(any((row.get("authority") or {}).get(key) for key in AUTHORITY_CLOSED) for row in rows):
        failures.append("authority_rows_present")

    if not failures:
        contract = subprocess.run(command(contract_only=True, train_rows=train_rows, total_rows=total_rows), cwd=ROOT, text=True, capture_output=True, check=False)
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
        "rows": total_rows,
        "original_rows": len(original_rows),
        "support_rows": len(support_rows),
        "train_rows": train_rows,
        "split_counts": dict(sorted(split_counts.items())),
        "slot_object_counts": dict(sorted(slot_counts.items())),
        "support_slot_counts": dict(sorted(support_slot_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "heldout_template_overlap_from_train_support": heldout_template_overlap,
        "copied_heldout_synthetic_targets": copied_heldout_synthetic_targets,
        "prefix_bad_rows": bad_prefix,
        "full_target_visible_rows": target_visible,
        "symbolic_prior_rows": symbolic_prior_rows,
        "heldout_support_source_rows": heldout_support_sources,
        "contract_returncode": None if contract is None else contract.returncode,
        "contract_passed": card.get("passed"),
        "contract_loss_counts": card.get("loss_counts"),
        "model_execution_attempted": card.get("model_execution_attempted"),
        "authority": AUTHORITY_RUN if not failures else dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    COMMAND_JSON.write_text(json.dumps({
        "command": command(contract_only=False, train_rows=train_rows, total_rows=total_rows),
        "cwd": str(ROOT),
        "env": "trellis",
        "tmpdir": str(TMPDIR),
        "authority": audit["authority"],
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    next_step = "If Stage9676 passes, execute Stage9677 slot-specific micro-support denoise probe and audit exact/contentful/repetition by slot."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": audit["authority"],
        "metrics": {**{key: bool(audit["authority"].get(key, False)) for key in AUTHORITY_CLOSED}, **audit},
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "command": str(COMMAND_JSON.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
            "manifest": str(MANIFEST.relative_to(ROOT)),
            "run_dir": str(RUN_DIR.relative_to(ROOT)),
        },
        "decision": "Prepared train-only slot-specific micro-support for failing neutral-slot suffix spans while keeping eval/strict rows held out.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9676 Slot-Specific Micro-Support Preexecution",
        "",
        f"Passed: `{audit['passed']}`",
        f"Rows: `{audit['rows']}`",
        f"Original rows: `{audit['original_rows']}`",
        f"Support rows: `{audit['support_rows']}`",
        f"Split counts: `{audit['split_counts']}`",
        f"Support slot counts: `{audit['support_slot_counts']}`",
        "",
        "This package keeps the Stage9674 eval/strict rows held out and adds train-only support for the Stage9675 failing slot families. The small-constant support rows are synthetic diagnostic analogs, not copied heldout targets.",
        "",
        "Only `denoise_ce` is active. Decoder CE, runtime, Gemma, harness, scoring, checkpoint export, and promotion remain closed.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": audit["passed"],
        "failures": failures,
        "rows": total_rows,
        "support_rows": len(support_rows),
        "support_slot_counts": dict(sorted(support_slot_counts.items())),
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
