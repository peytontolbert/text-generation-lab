#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9791
NAME = "stage9791_edit_localization_opaque_choice_target100m_contract_preflight"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9790_edit_localization_opaque_choice_surface.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9790_edit_localization_opaque_choice_surface/edit_localization_opaque_choice_surface.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
RUN_DIR = OUT_DIR / "contract_run"
AUDIT = OUT_DIR / "edit_localization_opaque_choice_target100m_contract_preflight_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EDIT_LOCALIZATION_OPAQUE_CHOICE_TARGET100M_CONTRACT_PREFLIGHT_STAGE9791.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")
REQUIRED = [
    "probe_contract_audit.json",
    "loss_by_step.jsonl",
    "eval_loss_by_checkpoint.jsonl",
    "row_field_logits.jsonl",
    "row_field_losses.jsonl",
    "row_gradient_norms.jsonl",
    "activation_summary.jsonl",
    "feature_ablation_attribution.jsonl",
    "activation_patch_recovery.jsonl",
    "row_dynamics_history.jsonl",
    "field_exact_by_cell.json",
    "field_label_vocabs.json",
    "structured_confusion_matrix.json",
    "module_delta_norms.json",
    "failure_bucket_card.json",
    "cleanup_proof.json",
]
TARGET_LOSS = "edit_localization_ce"
TARGET_MODE = "edit_localization_probe"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def command() -> list[str]:
    return [
        sys.executable,
        str(TRAINER),
        "--repo-root",
        str(ROOT),
        "--manifest",
        str(MANIFEST.relative_to(ROOT)),
        "--mode",
        TARGET_MODE,
        "--probe-scale",
        "target_100m",
        "--implementation",
        "transformer",
        "--model-config",
        str(MODEL_CONFIG.relative_to(ROOT)),
        "--tokenizer-json",
        str(TOKENIZER_JSON.relative_to(ROOT)),
        "--tokenizer-config",
        str(TOKENIZER_CONFIG.relative_to(ROOT)),
        "--tokenizer-hashlock",
        str(TOKENIZER_HASHLOCK.relative_to(ROOT)),
        "--max-train-rows",
        "20",
        "--max-eval-rows",
        "20",
        "--max-strict-rows",
        "20",
        "--max-steps",
        "0",
        "--batch-size",
        "2",
        "--learning-rate",
        "5e-5",
        "--max-encoder-tokens",
        "512",
        "--max-decoder-tokens",
        "4",
        "--decoder-ce-weight",
        "0.0",
        "--structured-aux-weight",
        "1.0",
        "--denoise-weight",
        "0.0",
        "--require-loss-mask-enforcement-audit",
        "--no-final-checkpoint-export",
        "--cleanup-checkpoints-after-probe",
        "--skip-final-model-save",
        "1",
        "--output-dir",
        str(RUN_DIR.relative_to(ROOT)),
        "--run-id",
        NAME,
        "--contract-only",
    ]


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": dict(AUTHORITY_CLOSED),
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
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    env = dict(os.environ)
    env.update({"TMPDIR": str(TMPDIR), "TEMP": str(TMPDIR), "TMP": str(TMPDIR)})
    run = subprocess.run(command(), cwd=ROOT, env=env, text=True, capture_output=True, check=False)
    contract = load_json(RUN_DIR / "probe_contract_audit.json")
    rows = read_jsonl(MANIFEST)
    missing = [name for name in REQUIRED if not (RUN_DIR / name).exists()]
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9790_not_passed")
    if run.returncode != 0:
        failures.append("trainer_contract_failed")
    if len(rows) != 60:
        failures.append("manifest_row_count_not_60")
    if contract.get("passed") is not True:
        failures.append("probe_contract_not_passed")
    if contract.get("probe_scale") != "target_100m" or contract.get("implementation") != "transformer":
        failures.append("target100m_transformer_contract_mismatch")
    if contract.get("model_execution_attempted") is not False:
        failures.append("model_execution_attempted")
    losses = contract.get("loss_counts") if isinstance(contract.get("loss_counts"), dict) else {}
    if losses.get(TARGET_LOSS) != 60:
        failures.append("expected_loss_count_mismatch")
    if [key for key, value in losses.items() if value and key != TARGET_LOSS]:
        failures.append("forbidden_loss_enabled")
    if missing:
        failures.append("missing_required_artifacts")
    audit = {
        "passed": not failures,
        "failures": failures,
        "trainer_returncode": run.returncode,
        "rows": len(rows),
        "loss_counts": losses,
        "missing_required_artifacts": missing,
        "contract": contract,
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Execute one real target-100M multilingual run on the Stage9790 opaque-choice package, then compare it against Gemma on the same strict-eval rows before reopening any broader win claim."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "rows": len(rows), "loss_counts": losses, "failures": failures},
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "run_dir": str(RUN_DIR.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Validated the Stage9790 opaque-choice edit-localization package under target-100M contract-only preflight without opening model execution claims.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9791 Edit Localization Opaque Choice Target-100M Contract Preflight",
                "",
                f"Passed: `{summary['passed']}`",
                f"Rows: `{len(rows)}`",
                f"Loss counts: `{losses}`",
                "",
                "This is contract-only and validates the Stage9790 opaque-choice edit-localization package under target-100M settings without opening model execution claims.",
                "",
                f"Next: {next_step}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(
        json.dumps(
            {
                "stage": STAGE,
                "passed": summary["passed"],
                "rows": len(rows),
                "loss_counts": losses,
                "failures": failures,
                "next_best_step": next_step,
            },
            indent=2,
            sort_keys=True,
        )
    )
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
