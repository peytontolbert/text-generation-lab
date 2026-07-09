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
STAGE = 9670
NAME = "stage9670_suffix_choice_sidecar_preexecution"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9669_prefix_primed_sidecar_residual_denoise_probe_audit.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9668_prefix_primed_sidecar_residual_denoise_preexecution/prefix_primed_sidecar_residual_denoise_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "suffix_choice_sidecar_manifest.jsonl"
RUN_DIR = OUT_DIR / "contract_preflight"
AUDIT = OUT_DIR / "suffix_choice_sidecar_preexecution_audit.json"
COMMAND_JSON = OUT_DIR / "stage9671_suffix_choice_sidecar_probe_command.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SUFFIX_CHOICE_SIDECAR_PREEXECUTION_STAGE9670.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")
OUTPUT_DIR = ROOT / "runs/local/artifacts/stage9671_suffix_choice_sidecar_probe"

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
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def transition(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("episode_transition") if isinstance(row.get("episode_transition"), dict) else {}


def observation(row: dict[str, Any]) -> dict[str, Any]:
    t = transition(row)
    return t.get("observation_t") if isinstance(t.get("observation_t"), dict) else {}


def state_t(row: dict[str, Any]) -> dict[str, Any]:
    t = transition(row)
    return t.get("state_t") if isinstance(t.get("state_t"), dict) else {}


def state_tp1(row: dict[str, Any]) -> dict[str, Any]:
    t = transition(row)
    return t.get("state_t_plus_1") if isinstance(t.get("state_t_plus_1"), dict) else {}


def suffix_choice(row: dict[str, Any]) -> str:
    return str(state_tp1(row).get("target_suffix_choice") or "")


def diagnostic_split(source: dict[str, Any]) -> str:
    row_id = str(source.get("row_id"))
    choice = suffix_choice(source)
    if choice == "expected_assertion_behavior__keep_value_small":
        return "train"
    if row_id == "stage9668_prefix_primed_sidecar_residual_denoise_0001":
        return "eval"
    return str(source.get("split") or "train")


def patch_row(source: dict[str, Any], index: int) -> dict[str, Any]:
    choice = suffix_choice(source)
    obs = observation(source)
    state = state_t(source)
    bucket = str((source.get("residual_repair_route") or {}).get("repair_bucket") or "")
    failure = str((source.get("effective_verifier") or {}).get("effective_failure_type") or "")
    new_row = {
        "row_id": f"stage9670_suffix_choice_sidecar_{index:04d}",
        "source_stage9668_row_id": source.get("row_id"),
        "original_split": source.get("split"),
        "split": diagnostic_split(source),
        "language_family": source.get("language_family"),
        "route": "KEEP_SUFFIX_CHOICE_SIDECAR_DIAGNOSTIC",
        "objective_family": "suffix_choice_sidecar_post_prefix_discriminator",
        "authority": dict(AUTHORITY_CLOSED),
        "loss_mask": {key: key == "suffix_choice_ce" for key in LOSS_KEYS},
        "model_input": {
            "suffix_choice_sidecar": True,
            "active_generation_prefix_span": (source.get("model_input") or {}).get("active_generation_prefix_span"),
            "active_generation_prefix_words": (source.get("model_input") or {}).get("active_generation_prefix_words"),
            "language_family": source.get("language_family"),
            "repair_bucket": bucket,
            "failure_type_component_not_exact": "not_exact" in failure,
            "failure_type_component_target_prefix_miss": "target_prefix_miss" in failure,
            "failure_type_component_boundary_miss": "boundary_next_token_miss" in failure,
            "obs_boundary_rank_bucket": (source.get("model_input") or {}).get("obs_boundary_rank_bucket"),
            "obs_prefix_relation": (source.get("model_input") or {}).get("obs_prefix_relation"),
            "obs_boundary_relation": (source.get("model_input") or {}).get("obs_boundary_relation"),
            "obs_residual_reason_count": (source.get("model_input") or {}).get("obs_residual_reason_count"),
            "corrupted_output_visible": True,
            "corrupted_output_prefix_family": str(obs.get("generated_text") or "").split()[:5],
            "bridge_error_family": state.get("bridge_error_family"),
            "prefix_token_bucket": state.get("prefix_token_bucket"),
            "suffix_choice_label_hidden_from_model_input": True,
        },
        "target": {
            "suffix_choice": choice,
            "label": choice,
            "structured_sidecar_field": "suffix_choice",
            "decoder_text": "",
        },
        "decoder_text": "",
        "anti_cheat": {
            "suffix_choice_label_hidden_from_model_input": True,
            "decoder_ce_closed": True,
            "denoise_ce_closed": True,
            "runtime_closed": True,
            "raw_clean_decoder_text_removed": True,
        },
    }
    return new_row


def active_losses(row: dict[str, Any]) -> list[str]:
    return sorted(key for key, value in (row.get("loss_mask") or {}).items() if bool(value))


def command(*, contract_only: bool) -> list[str]:
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
        str(MANIFEST),
        "--mode",
        "structured_policy_probe",
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
        "20",
        "--max-eval-rows",
        "3",
        "--max-strict-rows",
        "3",
        "--max-steps",
        "180",
        "--batch-size",
        "2",
        "--learning-rate",
        "2e-4",
        "--max-encoder-tokens",
        "512",
        "--max-decoder-tokens",
        "8",
        "--decoder-ce-weight",
        "0.0",
        "--structured-aux-weight",
        "1.0",
        "--denoise-weight",
        "0.0",
        "--eval-interval",
        "8",
        "--restore-best-structured-state",
        "--require-loss-mask-enforcement-audit",
        "--no-final-checkpoint-export",
        "--cleanup-checkpoints-after-probe",
        "--skip-final-model-save",
        "1",
        "--output-dir",
        str(RUN_DIR if contract_only else OUTPUT_DIR),
        "--run-id",
        "stage9670_suffix_choice_sidecar_contract" if contract_only else "stage9671_suffix_choice_sidecar_probe",
    ]
    cmd.append("--contract-only" if contract_only else "--execution-authorized-for-recovery-probe")
    return cmd


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": summary["authority"], "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows)}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    source_rows = load_jsonl(SOURCE_MANIFEST)
    rows = [patch_row(row, idx) for idx, row in enumerate(source_rows)]
    write_jsonl(MANIFEST, rows)
    choice_counts = Counter(str((row.get("target") or {}).get("suffix_choice")) for row in rows)
    split_counts = Counter(str(row.get("split")) for row in rows)
    split_choice_counts = Counter((str(row.get("split")), str((row.get("target") or {}).get("suffix_choice"))) for row in rows)
    train_labels = {str((row.get("target") or {}).get("suffix_choice")) for row in rows if row.get("split") == "train"}
    eval_labels = {str((row.get("target") or {}).get("suffix_choice")) for row in rows if row.get("split") == "eval"}
    strict_labels = {str((row.get("target") or {}).get("suffix_choice")) for row in rows if row.get("split") == "strict_eval"}
    failures: list[str] = []
    source_metrics = source.get("metrics") if isinstance(source.get("metrics"), dict) else {}
    if source.get("passed") is not False or source_metrics.get("safety_passed") is not True:
        failures.append("stage9669_not_safe_failed_probe")
    if len(rows) != 26:
        failures.append("row_count_not_26")
    if dict(split_counts) != {"train": 20, "eval": 3, "strict_eval": 3}:
        failures.append("split_counts_wrong")
    if not eval_labels.issubset(train_labels) or not strict_labels.issubset(train_labels):
        failures.append("heldout_labels_not_supported_in_train")
    if len(choice_counts) > 32:
        failures.append("suffix_choice_vocab_over_32")
    if Counter(tuple(active_losses(row)) for row in rows) != {("suffix_choice_ce",): 26}:
        failures.append("loss_mask_not_suffix_choice_only")
    if any(any((row.get("authority") or {}).values()) for row in rows):
        failures.append("authority_rows_present")
    if any((row.get("target") or {}).get("decoder_text") or row.get("decoder_text") for row in rows):
        failures.append("decoder_text_rows_present")
    if any((row.get("target") or {}).get("suffix_choice") in json.dumps(row.get("model_input") or {}, sort_keys=True) for row in rows):
        failures.append("suffix_choice_label_leaked_to_model_input")
    if not failures:
        contract = subprocess.run(command(contract_only=True), cwd=ROOT, text=True, capture_output=True, check=False)
        if contract.returncode != 0:
            failures.append("contract_preflight_failed")
    else:
        contract = None
    contract_card = load_json(RUN_DIR / "probe_contract_audit.json")
    if contract_card and contract_card.get("passed") is not True:
        failures.append("contract_card_not_passed")
    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "source_manifest": str(SOURCE_MANIFEST.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "rows": len(rows),
        "choice_counts": dict(sorted(choice_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "split_choice_counts": {f"{split}:{choice}": count for (split, choice), count in sorted(split_choice_counts.items())},
        "train_labels": sorted(train_labels),
        "eval_labels": sorted(eval_labels),
        "strict_labels": sorted(strict_labels),
        "loss_counts": dict(Counter(loss for row in rows for loss in active_losses(row))),
        "contract_returncode": None if contract is None else contract.returncode,
        "contract_passed": contract_card.get("passed"),
        "contract_loss_counts": contract_card.get("loss_counts"),
        "model_execution_attempted": contract_card.get("model_execution_attempted"),
        "authority": AUTHORITY_RUN if not failures else dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    COMMAND_JSON.write_text(json.dumps({"command": command(contract_only=False), "cwd": str(ROOT), "env": "trellis", "tmpdir": str(TMPDIR), "authority": audit["authority"]}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "If Stage9670 passes, execute Stage9671 suffix-choice sidecar target-100M structured probe and audit heldout exactness before any further denoise generation."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": audit["authority"],
        "metrics": {**{key: bool(audit["authority"].get(key, False)) for key in AUTHORITY_CLOSED}, **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "command": str(COMMAND_JSON.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "manifest": str(MANIFEST.relative_to(ROOT)), "run_dir": str(RUN_DIR.relative_to(ROOT))},
        "decision": "Prepared a closed suffix_choice structured sidecar with diagnostic resplit so heldout labels have train support; decoder and denoise generation losses remain closed.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9670 Suffix Choice Sidecar Preexecution", "", f"Passed: `{audit['passed']}`", f"Rows: `{audit['rows']}`", f"Splits: `{audit['split_counts']}`", f"Choice counts: `{audit['choice_counts']}`", "", "This converts the Stage9669 post-prefix generation failures into a structured `suffix_choice_ce` sidecar diagnostic. A singleton eval-only label was moved to train and a multi-support train row moved to eval so heldout labels have train support.", "", "Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, export, merge, and promotion remain closed.", "", f"Next: {next_step}", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "failures": failures, "rows": len(rows), "next_best_step": next_step}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
