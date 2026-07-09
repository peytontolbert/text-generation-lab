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
STAGE = 9672
NAME = "stage9672_suffix_choice_prior_fused_denoise_preexecution"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9671_suffix_choice_sidecar_probe_audit.json"
SOURCE_DENOISE = ROOT / "runs/local/artifacts/stage9668_prefix_primed_sidecar_residual_denoise_preexecution/prefix_primed_sidecar_residual_denoise_manifest.jsonl"
SIDECAR = ROOT / "runs/local/artifacts/stage9670_suffix_choice_sidecar_preexecution/suffix_choice_sidecar_manifest.jsonl"
LOGITS = ROOT / "runs/local/artifacts/stage9671_suffix_choice_sidecar_probe/row_field_logits.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "suffix_choice_prior_fused_denoise_manifest.jsonl"
RUN_DIR = OUT_DIR / "contract_preflight"
AUDIT = OUT_DIR / "suffix_choice_prior_fused_denoise_preexecution_audit.json"
COMMAND_JSON = OUT_DIR / "stage9673_suffix_choice_prior_fused_denoise_probe_command.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SUFFIX_CHOICE_PRIOR_FUSED_DENOISE_PREEXECUTION_STAGE9672.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")
OUTPUT_DIR = ROOT / "runs/local/artifacts/stage9673_suffix_choice_prior_fused_denoise_probe"
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


def suffix_choice(row: dict[str, Any]) -> str:
    transition = row.get("episode_transition") if isinstance(row.get("episode_transition"), dict) else {}
    state_tp1 = transition.get("state_t_plus_1") if isinstance(transition.get("state_t_plus_1"), dict) else {}
    return str(state_tp1.get("target_suffix_choice") or "")


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
        "stage9672_suffix_choice_prior_fused_denoise_contract" if contract_only else "stage9673_suffix_choice_prior_fused_denoise_probe",
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
    denoise_rows = load_jsonl(SOURCE_DENOISE)
    sidecar_rows = load_jsonl(SIDECAR)
    logits = [row for row in load_jsonl(LOGITS) if row.get("field") == "suffix_choice"]
    sidecar_by_source = {str(row.get("source_stage9668_row_id")): row for row in sidecar_rows}
    logit_by_sidecar_id = {str(row.get("row_id")): row for row in logits}
    out_rows: list[dict[str, Any]] = []
    join_failures: list[str] = []
    for index, source_row in enumerate(denoise_rows):
        source_id = str(source_row.get("row_id"))
        sidecar = sidecar_by_source.get(source_id)
        if not sidecar:
            join_failures.append(source_id)
            continue
        choice = suffix_choice(source_row)
        row = copy.deepcopy(source_row)
        row["row_id"] = f"stage9672_suffix_prior_fused_denoise_{index:04d}"
        row["source_stage9668_row_id"] = source_id
        row["source_stage9670_sidecar_row_id"] = sidecar.get("row_id")
        row["objective_family"] = "suffix_choice_prior_fused_residual_denoise"
        row["route"] = "USE_FOR_DENOISE_REPAIR_WITH_SUFFIX_CHOICE_PRIOR"
        model_input = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        model_input = dict(model_input)
        if sidecar.get("split") == "train":
            prior = {"label": choice, "target": choice, "confidence": 1.0, "margin": None, "source": "gold_train_suffix_choice_sidecar_prior"}
        else:
            logit = logit_by_sidecar_id.get(str(sidecar.get("row_id")))
            if not logit or logit.get("pred") != choice or not logit.get("correct"):
                join_failures.append(f"{source_id}:missing_or_wrong_controller_prior")
                continue
            prior = {
                "label": logit.get("pred"),
                "target": logit.get("target"),
                "confidence": logit.get("confidence"),
                "margin": logit.get("margin"),
                "source": "stage9671_heldout_controller_prior",
            }
        model_input.update(
            {
                "suffix_choice_prior_attached": True,
                "suffix_choice_prior_schema_version": "stage9672_suffix_choice_prior_fusion_v1",
                "suffix_choice_prior_label": prior["label"],
                "suffix_choice_prior_confidence": prior.get("confidence"),
                "suffix_choice_prior_margin": prior.get("margin"),
                "suffix_choice_prior_source": prior["source"],
                "suffix_choice_prior_is_controller_signal": True,
                "suffix_choice_prior_source_row_id": sidecar.get("row_id"),
            }
        )
        row["model_input"] = model_input
        row["suffix_choice_prior"] = prior
        row["suffix_choice_prior_source"] = prior["source"]
        mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        mask = {key: False for key in mask}
        mask.update({"decoder_ce": False, "structured_aux": False, "denoise_ce": True, "runtime_reward": False})
        row["loss_mask"] = mask
        row["authority"] = dict(AUTHORITY_CLOSED)
        anti = row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}
        anti = dict(anti)
        anti.update({"suffix_choice_prior_attached": True, "decoder_ce_closed": True, "runtime_closed": True, "clean_target_only_in_target_decoder_text": True})
        row["anti_cheat"] = anti
        out_rows.append(row)
    write_jsonl(MANIFEST, out_rows)
    split_counts = Counter(str(row.get("split")) for row in out_rows)
    prior_counts = Counter(str(row.get("suffix_choice_prior_source")) for row in out_rows)
    loss_counts = Counter(loss for row in out_rows for loss in active_losses(row))
    prefix_bad: list[str] = []
    target_visible: list[str] = []
    unsafe_rows: list[str] = []
    for row in out_rows:
        row_id = str(row.get("row_id"))
        target = target_text(row)
        prefix = str(nested_value(row, GENERATION_PREFIX_FIELD) or "")
        if not prefix or prefix == target or not target.startswith(prefix) or len(prefix.split()) > 8 or len(prefix) > 96:
            prefix_bad.append(row_id)
        if target and target in json.dumps(row.get("model_input") or {}, sort_keys=True):
            target_visible.append(row_id)
        if active_losses(row) != ["denoise_ce"] or any((row.get("authority") or {}).get(key) for key in AUTHORITY_CLOSED):
            unsafe_rows.append(row_id)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9671_not_passed")
    if join_failures:
        failures.append("join_failures_present")
    if len(out_rows) != 26:
        failures.append("row_count_not_26")
    if dict(split_counts) != {"train": 20, "eval": 3, "strict_eval": 3}:
        failures.append("split_counts_wrong")
    if dict(loss_counts) != {"denoise_ce": 26}:
        failures.append("loss_counts_not_denoise_only")
    if prefix_bad:
        failures.append("prefix_contract_failures")
    if target_visible:
        failures.append("full_target_visible_in_model_input")
    if unsafe_rows:
        failures.append("unsafe_rows_present")
    run_cmd = command(contract_only=False)
    if "--generation-prefix-field" not in run_cmd or GENERATION_PREFIX_FIELD not in run_cmd:
        failures.append("run_command_missing_generation_prefix")
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
        "join_failures": join_failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "rows": len(out_rows),
        "split_counts": dict(sorted(split_counts.items())),
        "prior_source_counts": dict(sorted(prior_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "prefix_bad_rows": prefix_bad,
        "full_target_visible_rows": target_visible,
        "unsafe_rows": unsafe_rows,
        "contract_returncode": None if contract is None else contract.returncode,
        "contract_passed": contract_card.get("passed"),
        "contract_generation_prefix_field": contract_card.get("generation_prefix_field"),
        "contract_loss_counts": contract_card.get("loss_counts"),
        "model_execution_attempted": contract_card.get("model_execution_attempted"),
        "authority": AUTHORITY_RUN if not failures else dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    COMMAND_JSON.write_text(json.dumps({"command": run_cmd, "cwd": str(ROOT), "env": "trellis", "tmpdir": str(TMPDIR), "authority": audit["authority"]}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "If Stage9672 passes, execute Stage9673 suffix-choice-prior fused denoise probe and compare exact/prefix metrics against Stage9669."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": audit["authority"],
        "metrics": {**{key: bool(audit["authority"].get(key, False)) for key in AUTHORITY_CLOSED}, **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "command": str(COMMAND_JSON.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "manifest": str(MANIFEST.relative_to(ROOT)), "run_dir": str(RUN_DIR.relative_to(ROOT))},
        "decision": "Prepared a suffix-choice-prior fused denoise generation package using gold train priors and Stage9671 heldout controller priors.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9672 Suffix Choice Prior Fused Denoise Preexecution", "", f"Passed: `{audit['passed']}`", f"Rows: `{audit['rows']}`", f"Splits: `{audit['split_counts']}`", f"Prior sources: `{audit['prior_source_counts']}`", "", "This reconnects the passed suffix-choice sidecar as a visible prior for denoise generation. The full target remains hidden from model input; denoise CE is the only active loss.", "", f"Next: {next_step}", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "failures": failures, "rows": len(out_rows), "next_best_step": next_step}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
