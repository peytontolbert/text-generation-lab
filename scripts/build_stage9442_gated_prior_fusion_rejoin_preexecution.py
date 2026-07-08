#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9442
NAME = "stage9442_gated_prior_fusion_rejoin_preexecution"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9441_gated_prior_fusion_rejoin_manifest.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9441_gated_prior_fusion_rejoin_manifest/gated_prior_fusion_rejoin_manifest.jsonl"
OUTPUT_DIR = ROOT / "runs/local/artifacts/stage9443_gated_prior_fusion_rejoin_probe"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "suffix_choice_prior_fusion_denoise_preexecution_audit.json"
COMMAND_JSON = OUT_DIR / "stage9443_gated_prior_fusion_rejoin_probe_command.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "GATED_PRIOR_FUSION_REJOIN_PREEXECUTION_STAGE9442.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")

AUTHORITY_RUN = dict(AUTHORITY_CLOSED)
AUTHORITY_RUN["model_execution_authorized_next"] = True
AUTHORITY_RUN["denoise_ce_training_authorized_next"] = True

COMMAND = [
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
    "48",
    "--max-eval-rows",
    "1",
    "--max-strict-rows",
    "1",
    "--max-steps",
    "90",
    "--batch-size",
    "2",
    "--learning-rate",
    "1e-5",
    "--max-encoder-tokens",
    "256",
    "--max-decoder-tokens",
    "768",
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
    "50",
    "--max-generation-tokens",
    "128",
    "--generation-prefix-field",
    "model_input.active_generation_prefix_span",
    "--generation-audit-splits",
    "train,eval,strict_eval",
    "--require-loss-mask-enforcement-audit",
    "--no-final-checkpoint-export",
    "--cleanup-checkpoints-after-probe",
    "--skip-final-model-save",
    "1",
    "--execution-authorized-for-recovery-probe",
    "--output-dir",
    str(OUTPUT_DIR),
    "--run-id",
    "stage9443_gated_prior_fusion_rejoin_probe",
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def has_pair(flag: str, value: str) -> bool:
    return any(COMMAND[index] == flag and COMMAND[index + 1] == value for index in range(len(COMMAND) - 1))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)

    source = load_json(SOURCE_SUMMARY)
    rows = load_jsonl(MANIFEST)
    splits = Counter(str(row.get("split")) for row in rows)
    routes = Counter(str(row.get("route")) for row in rows)
    prior_sources = Counter(str(row.get("suffix_choice_prior_source")) for row in rows)
    unsafe_rows: list[str] = []
    missing_prefix: list[str] = []
    for row in rows:
        row_id = str(row.get("row_id"))
        loss = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        auth = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        model_input = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        target = str(row.get("clean_target") or ((row.get("target") or {}).get("decoder_text") if isinstance(row.get("target"), dict) else "") or "")
        prefix = str(model_input.get("active_generation_prefix_span") or "")
        if loss.get("decoder_ce") or loss.get("runtime_reward") or not loss.get("denoise_ce"):
            unsafe_rows.append(row_id)
        if any(bool(auth.get(key)) for key in AUTHORITY_CLOSED):
            unsafe_rows.append(row_id)
        if not model_input.get("suffix_choice_prior_attached"):
            unsafe_rows.append(row_id)
        if not prefix or not target.startswith(prefix):
            missing_prefix.append(row_id)

    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9441_not_passed")
    if len(rows) != 50:
        failures.append("bad_manifest_row_count")
    if dict(splits) != {"eval": 1, "strict_eval": 1, "train": 48}:
        failures.append("bad_split_counts")
    if dict(prior_sources) != {"gold_train_suffix_choice_support": 48, "stage9419_correct_controller_prior": 2}:
        failures.append("bad_prior_source_counts")
    if routes != Counter({"USE_FOR_DENOISE_REPAIR_WITH_GATED_SUFFIX_CHOICE_PRIOR": 46, "USE_FOR_DENOISE_REPAIR_ANTI_REPETITION_WITH_GATED_PRIOR": 4}):
        failures.append("bad_route_counts")
    if unsafe_rows:
        failures.append("unsafe_manifest_rows")
    if missing_prefix:
        failures.append("missing_prefix_rows")
    if not str(OUTPUT_DIR.resolve()).startswith(str((ROOT / "runs/local/artifacts").resolve())) or "/arxiv" in str(OUTPUT_DIR):
        failures.append("unsafe_output_dir")
    for flag, value in {
        "--mode": "denoise_repair_probe",
        "--probe-scale": "target_100m",
        "--max-train-rows": "48",
        "--max-eval-rows": "1",
        "--max-strict-rows": "1",
        "--max-steps": "90",
        "--decoder-ce-weight": "0.0",
        "--structured-aux-weight": "0.0",
        "--denoise-weight": "1.0",
        "--generation-prefix-field": "model_input.active_generation_prefix_span",
    }.items():
        if not has_pair(flag, value):
            failures.append(f"missing_pair:{flag}={value}")
    for flag in [
        "--execution-authorized-for-recovery-probe",
        "--require-loss-mask-enforcement-audit",
        "--no-final-checkpoint-export",
        "--cleanup-checkpoints-after-probe",
        "--enable-generation-audit",
    ]:
        if flag not in COMMAND:
            failures.append(f"missing_flag:{flag}")

    audit = {
        "passed": not failures,
        "failures": failures,
        "manifest_rows": len(rows),
        "split_counts": dict(sorted(splits.items())),
        "route_counts": dict(sorted(routes.items())),
        "prior_source_counts": dict(sorted(prior_sources.items())),
        "unsafe_rows": sorted(set(unsafe_rows)),
        "missing_prefix_rows": missing_prefix,
        "command_ready": not failures,
        "authority": AUTHORITY_RUN if not failures else dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    COMMAND_JSON.write_text(json.dumps({"command": COMMAND, "cwd": str(ROOT), "env": "trellis", "tmpdir": str(TMPDIR)}, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": audit["authority"],
        "metrics": {**{key: bool(audit["authority"].get(key, False)) for key in AUTHORITY_CLOSED}, "command_ready": audit["command_ready"], "manifest_rows": audit["manifest_rows"], "split_counts": audit["split_counts"], "prior_source_counts": audit["prior_source_counts"], "failures": len(failures)},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "command": str(COMMAND_JSON.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Prepared a 50-row gated prior-fusion rejoin denoise probe; decoder CE remains closed.",
        "next_best_step": "Execute Stage9443 gated prior-fusion rejoin denoise probe under trellis and audit whether anti-repetition improves without reopening low-confidence heldout failures.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join(["# Stage9442 Gated Prior Fusion Rejoin Preexecution", "", f"Passed: `{audit['passed']}`", f"Rows: `{len(rows)}`", f"Splits: `{dict(sorted(splits.items()))}`", f"Prior sources: `{dict(sorted(prior_sources.items()))}`", "", "Only the Stage9443 gated prior-fusion rejoin denoise probe is authorized. Decoder CE, runtime, Gemma, harness, scoring, and promotion remain closed.", ""]))

    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    registry_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    registry_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": summary["authority"], "next_best_step": summary["next_best_step"]})
    registry_rows = sorted(registry_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    authority_counts = {key: 0 for key in AUTHORITY_CLOSED}
    for row in registry_rows:
        auth = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        for key in authority_counts:
            authority_counts[key] += int(bool(auth.get(key, False)))
    registry["rows"] = registry_rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry_rows), "authority_counts": authority_counts}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
