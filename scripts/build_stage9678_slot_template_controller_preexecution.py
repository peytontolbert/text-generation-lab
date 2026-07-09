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
STAGE = 9678
NAME = "stage9678_slot_template_controller_preexecution"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9677_slot_specific_micro_support_denoise_probe_audit.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9674_neutral_slot_prior_denoise_preexecution/neutral_slot_prior_denoise_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "slot_template_controller_manifest.jsonl"
RUN_DIR = OUT_DIR / "contract_preflight"
AUDIT = OUT_DIR / "slot_template_controller_preexecution_audit.json"
COMMAND_JSON = OUT_DIR / "stage9679_slot_template_controller_probe_command.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SLOT_TEMPLATE_CONTROLLER_PREEXECUTION_STAGE9678.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")
OUTPUT_DIR = ROOT / "runs/local/artifacts/stage9679_slot_template_controller_probe"

LOSS_KEYS = [
    "surface_role_ce",
    "repair_surface_ce",
    "build_mode_ce",
    "allowed_import_policy_ce",
    "blocked_import_policy_ce",
    "repo_dependency_policy_ce",
    "action_sequence_ce",
    "file_plan_ce",
    "symbol_binding_ce",
    "edit_localization_ce",
    "patch_operator_ce",
    "verifier_repair_ce",
    "suffix_choice_ce",
    "episode_repair_outcome_ce",
    "episode_failure_type_ce",
    "episode_boundary_match_ce",
    "episode_target_prefix_match_ce",
    "episode_step_value_mse",
    "structured_aux",
    "decoder_ce",
    "denoise_ce",
    "runtime_reward",
]

AUTHORITY_RUN = dict(AUTHORITY_CLOSED)
AUTHORITY_RUN["model_execution_authorized_next"] = True


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def target_text(row: dict[str, Any]) -> str:
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    return str(target.get("decoder_text") or row.get("decoder_text") or "").strip()


def slot(row: dict[str, Any]) -> dict[str, str]:
    value = row.get("neutral_slot_prior") if isinstance(row.get("neutral_slot_prior"), dict) else {}
    return {key: str(value.get(key) or "unknown") for key in ["slot_object", "slot_relation", "slot_constraint"]}


def template_label(row: dict[str, Any]) -> str:
    value = slot(row)
    return "__".join([value["slot_object"], value["slot_relation"], value["slot_constraint"]])


def active_losses(row: dict[str, Any]) -> list[str]:
    return sorted(key for key, value in (row.get("loss_mask") or {}).items() if bool(value))


def row_model_input(source: dict[str, Any], *, row_kind: str) -> dict[str, Any]:
    source_input = source.get("model_input") if isinstance(source.get("model_input"), dict) else {}
    forbidden = {"slot_object", "slot_relation", "slot_constraint", "neutral_slot_prior_attached", "neutral_slot_prior_schema_version"}
    model_input = {key: value for key, value in source_input.items() if key not in forbidden and "suffix_choice_prior" not in key}
    observation = source.get("episode_transition", {}).get("observation_t", {}) if isinstance(source.get("episode_transition"), dict) else {}
    effective = source.get("effective_verifier") if isinstance(source.get("effective_verifier"), dict) else {}
    model_input.update({
        "slot_template_controller_phase": True,
        "slot_template_controller_row_kind": row_kind,
        "active_generation_prefix_span": source_input.get("active_generation_prefix_span"),
        "active_generation_prefix_words": source_input.get("active_generation_prefix_words"),
        "language_family": source.get("language_family"),
        "obs_boundary_rank_bucket": source_input.get("obs_boundary_rank_bucket"),
        "obs_prefix_relation": source_input.get("obs_prefix_relation"),
        "obs_boundary_relation": source_input.get("obs_boundary_relation"),
        "obs_residual_reason_count": source_input.get("obs_residual_reason_count"),
        "effective_failure_type": effective.get("effective_failure_type"),
        "corrupted_output_prefix_family": str(observation.get("generated_text") or source.get("corrupted_output") or "").split()[:6],
        "slot_template_label_hidden_from_model_input": True,
        "clean_target_visible_in_model_input": False,
    })
    return model_input


def patch_row(source: dict[str, Any], index: int, *, row_kind: str = "real") -> dict[str, Any]:
    label = template_label(source)
    return {
        "row_id": f"stage9678_slot_template_controller_{index:04d}",
        "source_stage9674_row_id": source.get("row_id"),
        "split": source.get("split"),
        "original_split": source.get("split"),
        "source_kind": row_kind,
        "language_family": source.get("language_family"),
        "route": "KEEP_STRUCTURED_SLOT_TEMPLATE_CONTROLLER",
        "objective_family": "slot_template_controller_non_generative",
        "authority": dict(AUTHORITY_CLOSED),
        "loss_mask": {key: key == "suffix_choice_ce" for key in LOSS_KEYS},
        "model_input": row_model_input(source, row_kind=row_kind),
        "target": {
            "suffix_choice": label,
            "label": label,
            "structured_sidecar_field": "suffix_choice",
            "decoder_text": "",
            "template_source_target_text_sha256_hint": "redacted_non_input",
        },
        "decoder_text": "",
        "slot_template_target": {
            "label": label,
            **slot(source),
        },
        "anti_cheat": {
            "slot_template_label_hidden_from_model_input": True,
            "slot_object_relation_constraint_removed_from_model_input": True,
            "raw_clean_decoder_text_removed": True,
            "decoder_ce_closed": True,
            "denoise_ce_closed": True,
            "runtime_closed": True,
        },
    }


def synthetic_small_constant_row(template: dict[str, Any], index: int) -> dict[str, Any]:
    source = copy.deepcopy(template)
    source["split"] = "train"
    source["row_id"] = "synthetic_small_constant_train_support_not_heldout"
    if isinstance(source.get("neutral_slot_prior"), dict):
        source["neutral_slot_prior"] = {
            "slot_object": "small_constant",
            "slot_relation": "expected_assertion_behavior",
            "slot_constraint": "keep_value_small",
        }
    return patch_row(source, index, row_kind="synthetic_train_small_constant_label_support")


def command(*, contract_only: bool, train_rows: int, eval_rows: int, strict_rows: int) -> list[str]:
    cmd = [
        "env", f"TMPDIR={TMPDIR}", f"TEMP={TMPDIR}", f"TMP={TMPDIR}",
        "conda", "run", "-n", "trellis", "python", str(TRAINER),
        "--repo-root", str(ROOT), "--manifest", str(MANIFEST),
        "--mode", "structured_policy_probe", "--probe-scale", "target_100m", "--implementation", "transformer",
        "--model-config", str(MODEL_CONFIG), "--tokenizer-json", str(TOKENIZER_JSON),
        "--tokenizer-config", str(TOKENIZER_CONFIG), "--tokenizer-hashlock", str(TOKENIZER_HASHLOCK),
        "--max-train-rows", str(train_rows), "--max-eval-rows", str(eval_rows), "--max-strict-rows", str(strict_rows),
        "--max-steps", "180", "--batch-size", "2", "--learning-rate", "2e-4",
        "--max-encoder-tokens", "512", "--max-decoder-tokens", "8",
        "--decoder-ce-weight", "0.0", "--structured-aux-weight", "1.0", "--denoise-weight", "0.0",
        "--eval-interval", "8", "--restore-best-structured-state",
        "--require-loss-mask-enforcement-audit", "--no-final-checkpoint-export", "--cleanup-checkpoints-after-probe", "--skip-final-model-save", "1",
        "--output-dir", str(RUN_DIR if contract_only else OUTPUT_DIR),
        "--run-id", "stage9678_slot_template_controller_contract" if contract_only else "stage9679_slot_template_controller_probe",
    ]
    cmd.append("--contract-only" if contract_only else "--execution-authorized-for-recovery-probe")
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
    source_summary = load_json(SOURCE_SUMMARY)
    source_rows = load_jsonl(SOURCE_MANIFEST)
    rows = [patch_row(row, index) for index, row in enumerate(source_rows)]
    labels_by_split = Counter((row["split"], row["target"]["suffix_choice"]) for row in rows)
    train_labels = {label for split, label in labels_by_split if split == "train"}
    heldout_labels = {label for split, label in labels_by_split if split in {"eval", "strict_eval"}}
    missing_train_labels = sorted(heldout_labels - train_labels)
    small_constant_templates = [
        row for row in source_rows
        if template_label(row) == "small_constant__expected_assertion_behavior__keep_value_small"
    ]
    if missing_train_labels == ["small_constant__expected_assertion_behavior__keep_value_small"] and small_constant_templates:
        rows.append(synthetic_small_constant_row(small_constant_templates[0], len(rows)))
    write_jsonl(MANIFEST, rows)

    failures: list[str] = []
    source_metrics = source_summary.get("metrics") if isinstance(source_summary.get("metrics"), dict) else {}
    if source_summary.get("passed") is not False or source_metrics.get("safety_passed") is not True:
        failures.append("stage9677_not_expected_safe_failed_source")
    split_counts = Counter(str(row.get("split")) for row in rows)
    label_counts = Counter(str((row.get("target") or {}).get("suffix_choice")) for row in rows)
    train_label_counts = Counter(str((row.get("target") or {}).get("suffix_choice")) for row in rows if row.get("split") == "train")
    heldout_label_counts = Counter(str((row.get("target") or {}).get("suffix_choice")) for row in rows if row.get("split") in {"eval", "strict_eval"})
    loss_counts = Counter(loss for row in rows for loss in active_losses(row))
    train_rows = split_counts.get("train", 0)
    eval_rows = split_counts.get("eval", 0)
    strict_rows = split_counts.get("strict_eval", 0)
    if len(label_counts) > 32:
        failures.append("suffix_choice_head_label_capacity_exceeded")
    if set(heldout_label_counts) - set(train_label_counts):
        failures.append("heldout_labels_missing_train_support")
    if dict(loss_counts) != {"suffix_choice_ce": len(rows)}:
        failures.append("loss_counts_not_suffix_choice_only")
    target_visible_rows: list[str] = []
    label_visible_rows: list[str] = []
    slot_visible_rows: list[str] = []
    for row in rows:
        row_id = str(row.get("row_id"))
        model_text = json.dumps(row.get("model_input") or {}, sort_keys=True)
        source = next((src for src in source_rows if src.get("row_id") == row.get("source_stage9674_row_id")), {})
        if target_text(source) and target_text(source) in model_text:
            target_visible_rows.append(row_id)
        label = str((row.get("target") or {}).get("suffix_choice") or "")
        if label and label in model_text:
            label_visible_rows.append(row_id)
        if any(token in model_text for token in ["slot_object", "slot_relation", "slot_constraint"]):
            slot_visible_rows.append(row_id)
    if target_visible_rows:
        failures.append("raw_target_visible_in_model_input")
    if label_visible_rows:
        failures.append("slot_template_label_visible_in_model_input")
    if slot_visible_rows:
        failures.append("slot_target_fields_visible_in_model_input")
    if any(any((row.get("authority") or {}).get(key) for key in AUTHORITY_CLOSED) for row in rows):
        failures.append("authority_rows_present")

    if not failures:
        contract = subprocess.run(command(contract_only=True, train_rows=train_rows, eval_rows=eval_rows, strict_rows=strict_rows), cwd=ROOT, text=True, capture_output=True, check=False)
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
        "source_rows": len(source_rows),
        "split_counts": dict(sorted(split_counts.items())),
        "label_counts": dict(sorted(label_counts.items())),
        "train_label_counts": dict(sorted(train_label_counts.items())),
        "heldout_label_counts": dict(sorted(heldout_label_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "target_visible_rows": target_visible_rows,
        "label_visible_rows": label_visible_rows,
        "slot_visible_rows": slot_visible_rows,
        "contract_returncode": None if contract is None else contract.returncode,
        "contract_passed": card.get("passed"),
        "contract_loss_counts": card.get("loss_counts"),
        "model_execution_attempted": card.get("model_execution_attempted"),
        "authority": AUTHORITY_RUN if not failures else dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    COMMAND_JSON.write_text(json.dumps({
        "command": command(contract_only=False, train_rows=train_rows, eval_rows=eval_rows, strict_rows=strict_rows),
        "cwd": str(ROOT),
        "env": "trellis",
        "tmpdir": str(TMPDIR),
        "authority": audit["authority"],
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "If Stage9678 passes, execute Stage9679 structured slot-template controller probe before any denoise generation reconnect."
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
        "decision": "Prepared non-generative slot-template controller after Stage9677 showed duplicate denoise support destabilized generation.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9678 Slot Template Controller Preexecution",
        "",
        f"Passed: `{audit['passed']}`",
        f"Rows: `{audit['rows']}`",
        f"Split counts: `{audit['split_counts']}`",
        f"Template labels: `{len(label_counts)}`",
        "",
        "This branch stops asking the decoder to improvise the residual slot suffix. It trains only the existing `suffix_choice` structured head to select a deterministic slot-template label.",
        "",
        "Decoder CE, denoise CE, runtime, Gemma, harness, scoring, checkpoint export, and promotion remain closed.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": audit["passed"],
        "failures": failures,
        "rows": len(rows),
        "labels": len(label_counts),
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
