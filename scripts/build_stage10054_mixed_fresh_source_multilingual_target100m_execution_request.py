#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10054
NAME = "stage10054_mixed_fresh_source_multilingual_target100m_execution_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST = OUT_DIR / "mixed_fresh_source_multilingual_target100m_execution_request.json"
SURFACE_REQUEST = OUT_DIR / "surface_requests" / "edit_localization.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "MIXED_FRESH_SOURCE_MULTILINGUAL_TARGET100M_EXECUTION_REQUEST_STAGE10054.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
MANIFEST = ROOT / "runs/local/artifacts/stage10053_mixed_fresh_source_multilingual_successor_packet/mixed_fresh_source_multilingual_successor_manifest.jsonl"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage10053_mixed_fresh_source_multilingual_successor_packet.json"
BASELINE_RESULT = ROOT / "runs/local/artifacts/stage10040_expanded_source_heldout_target100m_probe/edit_localization_probe/execution_result.json"

FUTURE_RUN_ID = "stage10054_mixed_fresh_source_multilingual_target100m_probe"
FUTURE_OUTPUT_DIR = "runs/local/artifacts/stage10054_mixed_fresh_source_multilingual_target100m_probe/edit_localization_probe"
REQUIRED_RUN_ARTIFACTS = [
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


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


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


def trainer_command(split_counts: dict[str, int]) -> list[str]:
    return [
        "python",
        "legacy_src/scripts/train_agentkernel_lite_encdec.py",
        "--repo-root",
        str(ROOT),
        "--manifest",
        display(MANIFEST),
        "--mode",
        "edit_localization_probe",
        "--probe-scale",
        "target_100m",
        "--implementation",
        "transformer",
        "--model-config",
        "configs/model/agentkernel_100m_seq2seq_recovered_target.json",
        "--tokenizer-json",
        "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json",
        "--tokenizer-config",
        "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json",
        "--tokenizer-hashlock",
        "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json",
        "--max-train-rows",
        str(split_counts.get("train", 0)),
        "--max-eval-rows",
        str(split_counts.get("eval", 0)),
        "--max-strict-rows",
        str(split_counts.get("strict_eval", 0)),
        "--max-steps",
        "64",
        "--batch-size",
        "2",
        "--learning-rate",
        "5e-5",
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
        "--require-loss-mask-enforcement-audit",
        "--no-final-checkpoint-export",
        "--cleanup-checkpoints-after-probe",
        "--skip-final-model-save",
        "1",
        "--output-dir",
        FUTURE_OUTPUT_DIR,
        "--run-id",
        FUTURE_RUN_ID,
        "--execution-authorized-for-recovery-probe",
    ]


def build_request() -> dict[str, Any]:
    rows = load_jsonl(MANIFEST)
    source_summary = load_json(SOURCE_SUMMARY)
    baseline = load_json(BASELINE_RESULT)
    failures: list[str] = []

    language_counts = Counter(str(row.get("language_family") or "") for row in rows)
    split_counts = Counter(str(row.get("split") or "") for row in rows)
    stage10047_train_rows = sum(1 for row in rows if str(row.get("stage10047_role") or "") == "train")
    stage10053_train_rows = sum(1 for row in rows if str(row.get("stage10053_role") or "") == "train")
    stage10053_web_train_rows = sum(1 for row in rows if str(row.get("language_family") or "") == "web_js_ts_html" and str(row.get("stage10053_role") or "") == "train")
    heldout_rows = int(split_counts.get("eval", 0) + split_counts.get("strict_eval", 0))

    metrics = {
        "rows": len(rows),
        "language_counts": dict(sorted(language_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "heldout_compare_rows": heldout_rows,
        "stage10047_train_rows": stage10047_train_rows,
        "stage10053_train_rows": stage10053_train_rows,
        "stage10053_web_train_rows_added": stage10053_web_train_rows,
    }
    if metrics["rows"] != 119:
        failures.append("rows_not_119")
    if split_counts.get("train") != 64:
        failures.append("train_rows_not_64")
    if split_counts.get("eval") != 38:
        failures.append("eval_rows_not_38")
    if split_counts.get("strict_eval") != 17:
        failures.append("strict_rows_not_17")
    if language_counts.get("python") != 27:
        failures.append("python_rows_not_27")
    if language_counts.get("c_cpp") != 37:
        failures.append("c_cpp_rows_not_37")
    if language_counts.get("rust") != 13:
        failures.append("rust_rows_not_13")
    if language_counts.get("web_js_ts_html") != 42:
        failures.append("web_rows_not_42")
    if stage10047_train_rows != 8:
        failures.append("stage10047_train_rows_not_8")
    if stage10053_train_rows != 16:
        failures.append("stage10053_train_rows_not_16")
    if stage10053_web_train_rows != 7:
        failures.append("stage10053_web_train_rows_not_7")
    if heldout_rows != 55:
        failures.append("heldout_compare_rows_not_55")
    if source_summary.get("passed") is not True:
        failures.append("stage10053_not_passed")
    if baseline.get("runtime_executed") is not True:
        failures.append("stage10040_runtime_not_executed")

    req = {
        "surface": "edit_localization",
        "request_status": "awaiting_explicit_execution_authorization",
        "manifest": display(MANIFEST),
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "expected_loss": "edit_localization_ce",
        "output_dir": FUTURE_OUTPUT_DIR,
        "run_id": FUTURE_RUN_ID,
        "command": trainer_command(dict(split_counts)),
        "required_runtime_artifacts": list(REQUIRED_RUN_ARTIFACTS),
        "required_contract_invariants": {
            "source_stage10053_passed": bool(source_summary.get("passed") is True),
            "source_stage10040_runtime_executed": bool(baseline.get("runtime_executed") is True),
            "source_stage10040_manifest_rows": baseline.get("train_rows", 0) + baseline.get("eval_rows", 0) + baseline.get("strict_rows", 0),
            "stage10047_train_rows": stage10047_train_rows,
            "stage10053_train_rows": stage10053_train_rows,
            "stage10053_web_train_rows_added": stage10053_web_train_rows,
            "same_compare_rows_preserved": heldout_rows,
        },
        "authority": dict(AUTHORITY_CLOSED),
    }

    SURFACE_REQUEST.parent.mkdir(parents=True, exist_ok=True)
    SURFACE_REQUEST.write_text(json.dumps(req, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "source_artifacts": {
            "stage10053_packet_summary": display(SOURCE_SUMMARY),
            "baseline_execution_result": display(BASELINE_RESULT),
        },
        "execution_constraints": {
            "execution_authorized_now": False,
            "model_execution_authorized_now": False,
            "decoder_ce_training_authorized_now": False,
            "requires_explicit_execution_authorization": True,
            "same_manifest_comparison_required_after_run": True,
            "fresh_source_rows_replace_canonical_anchor_duplication": True,
        },
        "surface_requests": [{**req, "request_path": display(SURFACE_REQUEST)}],
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_request()
    REQUEST.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Use this request to run one target-100M edit-localization probe on the mixed fresh-source successor manifest, then audit the same 55 heldout rows against the existing stage10040 baseline and Gemma outputs."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {
            "request": display(REQUEST),
            "surface_request": display(SURFACE_REQUEST),
            "doc": display(DOC),
        },
        "decision": "Prepared the explicit execution request for the mixed fresh-source multilingual successor so the next real probe can test whether fresh source-backed c_cpp, rust, and web repairs preserve the stage10047 Python gain.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage10054 Mixed Fresh Source Multilingual Target100M Execution Request",
                "",
                f"Passed: `{summary['passed']}`",
                "",
                summary["decision"],
                "",
                f"Next: {next_step}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
