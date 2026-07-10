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
STAGE = 10070
NAME = "stage10070_canonical_label_aligned_target100m_execution_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST = OUT_DIR / "canonical_label_aligned_target100m_execution_request.json"
SURFACE_REQUEST = OUT_DIR / "surface_requests" / "edit_localization.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CANONICAL_LABEL_ALIGNED_TARGET100M_EXECUTION_REQUEST_STAGE10070.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
MANIFEST = ROOT / "runs/local/artifacts/stage10069_canonical_label_aligned_multilingual_successor_packet/canonical_label_aligned_multilingual_manifest.jsonl"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage10069_canonical_label_aligned_multilingual_successor_packet.json"

FUTURE_RUN_ID = "stage10070_canonical_label_aligned_target100m_probe"
FUTURE_OUTPUT_DIR = "runs/local/artifacts/stage10070_canonical_label_aligned_target100m_probe/edit_localization_probe"
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
    failures: list[str] = []
    language_counts = Counter(str(row.get("language_family") or "") for row in rows)
    split_counts = Counter(str(row.get("split") or "") for row in rows)
    heldout_rows = int(split_counts.get("eval", 0) + split_counts.get("strict_eval", 0))
    metrics = {
        "rows": len(rows),
        "language_counts": dict(sorted(language_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "heldout_compare_rows": heldout_rows,
    }
    if metrics["rows"] != 142:
        failures.append("rows_not_142")
    if split_counts.get("train") != 87:
        failures.append("train_rows_not_87")
    if split_counts.get("eval") != 38:
        failures.append("eval_rows_not_38")
    if split_counts.get("strict_eval") != 17:
        failures.append("strict_rows_not_17")
    if heldout_rows != 55:
        failures.append("heldout_rows_not_55")
    if source_summary.get("passed") is not True:
        failures.append("stage10069_not_passed")

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
            "source_stage10069_passed": bool(source_summary.get("passed") is True),
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
        "source_artifacts": {"stage10069_packet_summary": display(SOURCE_SUMMARY)},
        "surface_requests": [{**req, "request_path": display(SURFACE_REQUEST)}],
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_request()
    REQUEST.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Run one target-100m edit-localization probe on the canonical-label multilingual manifest, then execute the matching same-manifest Gemma queue."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {"request": display(REQUEST), "surface_request": display(SURFACE_REQUEST), "doc": display(DOC)},
        "decision": "Prepared the execution request for the canonical-label multilingual manifest so the next probe can test whether label-semantic alignment repairs the cross-language collapse without changing the visible encoder surface.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage10070 Canonical Label Aligned Target100M Execution Request",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        summary["decision"],
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
