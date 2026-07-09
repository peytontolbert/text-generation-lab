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
STAGE = 9668
NAME = "stage9668_prefix_primed_sidecar_residual_denoise_preexecution"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9667_sidecar_gated_residual_denoise_probe_audit.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9666_sidecar_gated_residual_denoise_preexecution/sidecar_gated_residual_denoise_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "prefix_primed_sidecar_residual_denoise_manifest.jsonl"
RUN_DIR = OUT_DIR / "denoise_contract"
AUDIT = OUT_DIR / "prefix_primed_sidecar_residual_denoise_preexecution_audit.json"
COMMAND_JSON = OUT_DIR / "stage9669_prefix_primed_sidecar_residual_denoise_probe_command.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PREFIX_PRIMED_SIDECAR_RESIDUAL_DENOISE_PREEXECUTION_STAGE9668.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")
OUTPUT_DIR = ROOT / "runs/local/artifacts/stage9669_prefix_primed_sidecar_residual_denoise_probe"
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


def prefix_from_target(target: str, max_words: int = 5) -> str:
    words = target.split()
    if len(words) <= max_words:
        return ""
    prefix = " ".join(words[:max_words])
    while len(prefix) > 96 and max_words > 1:
        max_words -= 1
        prefix = " ".join(words[:max_words])
    return prefix


def active_losses(row: dict[str, Any]) -> list[str]:
    mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
    return sorted(key for key, value in mask.items() if bool(value))


def patch_row(source: dict[str, Any], index: int) -> dict[str, Any] | None:
    clean = target_text(source)
    prefix = prefix_from_target(clean)
    if not prefix:
        return None
    row = copy.deepcopy(source)
    row["row_id"] = f"stage9668_prefix_primed_sidecar_residual_denoise_{index:04d}"
    row["source_stage9666_row_id"] = source.get("row_id")
    row["objective_family"] = "prefix_primed_sidecar_gated_residual_denoise"
    row["route"] = "KEEP_PREFIX_PRIMED_SIDECAR_GATED_RESIDUAL_DENOISE"
    mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
    mask = {key: False for key in mask}
    mask.update({"decoder_ce": False, "structured_aux": False, "denoise_ce": True, "runtime_reward": False})
    row["loss_mask"] = mask
    model_input = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
    model_input = dict(model_input)
    for key in [
        "target",
        "target_text",
        "clean_target",
        "decoder_text",
        "remaining_suffix",
        "target_suffix",
        "first_suffix_word",
        "state_t_plus_1_decoder_text",
    ]:
        model_input.pop(key, None)
    model_input.update(
        {
            "active_generation_prefix_span": prefix,
            "active_generation_prefix_words": len(prefix.split()),
            "active_generation_prefix_source": "stage9668_clean_target_prefix_scaffold",
            "prefix_visible_suffix_hidden": True,
            "clean_target_visible_in_model_input": False,
            "remaining_suffix_hidden_from_model_input": True,
            "target_surface_family": "natural_bounded_sidecar_residual_repair_text",
            "sidecar_gated_denoise_phase": True,
            "prefix_primed_sidecar_denoise_phase": True,
        }
    )
    row["model_input"] = model_input
    anti = row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}
    anti = dict(anti)
    anti.update(
        {
            "decoder_ce_closed": True,
            "runtime_closed": True,
            "full_clean_target_in_model_input": False,
            "prefix_visible_but_suffix_hidden": True,
            "generation_prefix_is_not_full_target": prefix != clean,
            "clean_target_only_in_target_decoder_text": True,
            "post_prefix_loss_mask_required": True,
        }
    )
    row["anti_cheat"] = anti
    row["generation_prefix_field"] = GENERATION_PREFIX_FIELD
    return row


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
        "20",
        "--max-eval-rows",
        "3",
        "--max-strict-rows",
        "3",
        "--max-steps",
        "80",
        "--batch-size",
        "2",
        "--learning-rate",
        "1e-5",
        "--max-encoder-tokens",
        "512",
        "--max-decoder-tokens",
        "96",
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
        "26",
        "--max-generation-tokens",
        "96",
        "--generation-prefix-field",
        GENERATION_PREFIX_FIELD,
        "--generation-audit-splits",
        "train,eval,strict_eval",
        "--require-loss-mask-enforcement-audit",
        "--no-final-checkpoint-export",
        "--cleanup-checkpoints-after-probe",
        "--skip-final-model-save",
        "1",
        "--output-dir",
        str(RUN_DIR if contract_only else OUTPUT_DIR),
        "--run-id",
        "stage9668_prefix_primed_sidecar_residual_denoise_contract" if contract_only else "stage9669_prefix_primed_sidecar_residual_denoise_probe",
    ]
    if contract_only:
        cmd.extend(["--contract-only", "--max-steps", "0"])
    else:
        cmd.append("--execution-authorized-for-recovery-probe")
    return cmd


def has_pair(cmd: list[str], flag: str, value: str) -> bool:
    return any(cmd[i] == flag and i + 1 < len(cmd) and cmd[i + 1] == value for i in range(len(cmd)))


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": summary["authority"],
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


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    rows = [row for idx, source_row in enumerate(load_jsonl(SOURCE_MANIFEST)) if (row := patch_row(source_row, idx)) is not None]
    write_jsonl(MANIFEST, rows)
    split_counts = Counter(str(row.get("split")) for row in rows)
    language_counts = Counter(str(row.get("language_family")) for row in rows)
    bucket_counts = Counter(str((row.get("residual_repair_route") or {}).get("repair_bucket")) for row in rows)
    prefix_bad: list[dict[str, str]] = []
    target_visible: list[str] = []
    unsafe_rows: list[str] = []
    for row in rows:
        row_id = str(row.get("row_id"))
        target = target_text(row)
        prefix = str(nested_value(row, GENERATION_PREFIX_FIELD) or "")
        model_input_text = json.dumps(row.get("model_input") or {}, sort_keys=True)
        if not prefix:
            prefix_bad.append({"row_id": row_id, "reason": "missing_prefix"})
        elif len(prefix.split()) > 8 or len(prefix) > 96:
            prefix_bad.append({"row_id": row_id, "reason": "prefix_over_cap", "prefix": prefix})
        elif prefix == target:
            prefix_bad.append({"row_id": row_id, "reason": "prefix_is_full_target"})
        elif not target.startswith(prefix):
            prefix_bad.append({"row_id": row_id, "reason": "prefix_not_target_start", "prefix": prefix})
        if target and target in model_input_text:
            target_visible.append(row_id)
        if active_losses(row) != ["denoise_ce"]:
            unsafe_rows.append(row_id)
        if any(bool((row.get("authority") or {}).get(key)) for key in AUTHORITY_CLOSED):
            unsafe_rows.append(row_id)
    failures: list[str] = []
    if source.get("passed") is not False or not bool((source.get("metrics") or {}).get("safety_passed")):
        failures.append("stage9667_not_safe_quality_failure")
    if len(rows) != 26:
        failures.append("row_count_not_26")
    if dict(split_counts) != {"train": 20, "eval": 3, "strict_eval": 3}:
        failures.append("split_counts_wrong")
    if prefix_bad:
        failures.append("prefix_contract_failures")
    if target_visible:
        failures.append("full_target_visible_in_model_input")
    if unsafe_rows:
        failures.append("unsafe_or_wrong_loss_rows")
    run_cmd = command(contract_only=False)
    required_pairs = {
        "--mode": "denoise_repair_probe",
        "--probe-scale": "target_100m",
        "--max-train-rows": "20",
        "--max-eval-rows": "3",
        "--max-strict-rows": "3",
        "--generation-prefix-field": GENERATION_PREFIX_FIELD,
        "--denoise-weight": "1.0",
        "--decoder-ce-weight": "0.0",
        "--structured-aux-weight": "0.0",
    }
    for flag, value in required_pairs.items():
        if not has_pair(run_cmd, flag, value):
            failures.append(f"missing_run_pair:{flag}={value}")
    for flag in [
        "--execution-authorized-for-recovery-probe",
        "--require-loss-mask-enforcement-audit",
        "--no-final-checkpoint-export",
        "--cleanup-checkpoints-after-probe",
        "--enable-generation-audit",
    ]:
        if flag not in run_cmd:
            failures.append(f"missing_run_flag:{flag}")
    contract_cmd = command(contract_only=True)
    run = subprocess.run(contract_cmd, cwd=ROOT, text=True, capture_output=True, check=False) if not failures else None
    if run is not None and run.returncode != 0:
        failures.append("contract_command_failed")
    card = load_json(RUN_DIR / "probe_contract_audit.json")
    if not card and not failures:
        failures.append("missing_probe_contract_audit")
    elif card and card.get("passed") is not True:
        failures.append("probe_contract_not_passed")
    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "source_manifest": str(SOURCE_MANIFEST.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "rows": len(rows),
        "split_counts": dict(split_counts),
        "language_counts": dict(language_counts),
        "repair_bucket_counts": dict(bucket_counts),
        "generation_prefix_field": GENERATION_PREFIX_FIELD,
        "prefix_bad_rows": prefix_bad,
        "full_target_visible_rows": target_visible,
        "unsafe_rows": unsafe_rows,
        "active_loss_counts": dict(Counter(",".join(active_losses(row)) for row in rows)),
        "contract_passed": card.get("passed"),
        "contract_loss_counts": card.get("loss_counts"),
        "contract_generation_prefix_field": card.get("generation_prefix_field"),
        "model_execution_attempted": card.get("model_execution_attempted"),
        "run_command_ready": not failures,
        "authority": AUTHORITY_RUN if not failures else dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    COMMAND_JSON.write_text(
        json.dumps({"command": run_cmd, "cwd": str(ROOT), "env": "trellis", "tmpdir": str(TMPDIR), "authority": audit["authority"]}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    next_step = "If Stage9668 passes, execute Stage9669 prefix-primed sidecar residual denoise target-100M probe and audit exact/contentful/leak/repetition metrics."
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
        "decision": "Prepared prefix-primed sidecar residual denoise package with short clean prefixes visible and suffix/full target hidden from model input." if audit["passed"] else "Prefix-primed sidecar residual denoise preexecution failed; do not execute.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9668 Prefix-Primed Sidecar Residual Denoise Preexecution",
                "",
                f"Passed: `{audit['passed']}`",
                f"Rows: `{audit['rows']}`",
                f"Splits: `{audit['split_counts']}`",
                f"Generation prefix field: `{GENERATION_PREFIX_FIELD}`",
                f"Prefix bad rows: `{audit['prefix_bad_rows']}`",
                "",
                "This patches the Stage9667 failure mode by exposing only a short clean target prefix to generation while training denoise CE on the post-prefix suffix. The full clean target remains only in `target.decoder_text`.",
                "",
                "Decoder CE, runtime, source/body emission, Gemma, harness, scoring, final checkpoint export, controller merge, and promotion remain closed.",
                "",
                f"Next: {next_step}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "failures": failures, "rows": len(rows), "next_best_step": next_step}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
