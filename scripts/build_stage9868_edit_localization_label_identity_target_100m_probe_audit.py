#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9868
NAME = "stage9868_edit_localization_label_identity_target_100m_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9867_edit_localization_label_identity_probe.json"
SUCCESS_DIR = ROOT / "runs/local/artifacts/stage9868_edit_localization_label_identity_target_100m_probe/edit_localization_probe"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "edit_localization_label_identity_target_100m_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EDIT_LOCALIZATION_LABEL_IDENTITY_TARGET_100M_PROBE_STAGE9868.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
REQUIRED_ARTIFACTS = [
    "probe_contract_audit.json",
    "execution_result.json",
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


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def artifact_status() -> dict[str, Any]:
    return {name: {"exists": (SUCCESS_DIR / name).exists(), "bytes": (SUCCESS_DIR / name).stat().st_size if (SUCCESS_DIR / name).exists() else 0} for name in REQUIRED_ARTIFACTS}


def telemetry_counts() -> dict[str, int]:
    return {
        "loss_by_step_rows": count_jsonl(SUCCESS_DIR / "loss_by_step.jsonl"),
        "row_field_logits_rows": count_jsonl(SUCCESS_DIR / "row_field_logits.jsonl"),
        "row_gradient_norms_rows": count_jsonl(SUCCESS_DIR / "row_gradient_norms.jsonl"),
    }


def extract_metrics() -> dict[str, Any]:
    execution = load_json(SUCCESS_DIR / "execution_result.json")
    contract = load_json(SUCCESS_DIR / "probe_contract_audit.json")
    vocab = load_json(SUCCESS_DIR / "field_label_vocabs.json")
    matrix = load_json(SUCCESS_DIR / "structured_confusion_matrix.json")
    evals = execution.get("eval") or {}
    eval_split = evals.get("eval") or {}
    strict_split = evals.get("strict_eval") or {}
    implementation = execution.get("implementation") or {}
    edit_vocab = (vocab.get("edit_localization") or {}) if isinstance(vocab, dict) else {}
    edit_matrix = (matrix.get("edit_localization") or {}) if isinstance(matrix, dict) else {}
    labels_in_order = [label for label, _ in sorted(edit_vocab.items(), key=lambda item: int(item[1]))]
    first_label = labels_in_order[0] if labels_in_order else None
    last_label = labels_in_order[-1] if labels_in_order else None
    collapsed_to_first_label = bool(first_label and all(set(preds.keys()) == {first_label} for preds in edit_matrix.values() if isinstance(preds, dict)))
    collapsed_to_last_label = bool(last_label and all(set(preds.keys()) == {last_label} for preds in edit_matrix.values() if isinstance(preds, dict)))
    return {
        "mode": execution.get("mode"),
        "probe_scale": implementation.get("probe_scale") or contract.get("probe_scale"),
        "estimated_parameter_count": implementation.get("estimated_parameter_count"),
        "eval_edit_localization_exact": ((eval_split.get("field_exact") or {}).get("edit_localization") or {}).get("exact"),
        "strict_edit_localization_exact": ((strict_split.get("field_exact") or {}).get("edit_localization") or {}).get("exact"),
        "runtime_executed": execution.get("runtime_executed") is True,
        "required_artifacts_written": execution.get("required_artifacts_written") is True,
        "multilingual_surface_readiness_passed": ((contract.get("multilingual_surface_readiness") or {}).get("passed") is True),
        "first_vocab_label": first_label,
        "field_vocab": edit_vocab,
        "confusion_matrix": edit_matrix,
        "last_vocab_label": last_label,
        "collapsed_to_first_vocab_label": collapsed_to_first_label,
        "collapsed_to_last_vocab_label": collapsed_to_last_label,
    }


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    artifacts = artifact_status()
    metrics = extract_metrics()
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9867_not_passed")
    missing = [name for name, status in artifacts.items() if not status["exists"] or status["bytes"] <= 0]
    failures.extend(f"missing_or_empty_artifact:{name}" for name in missing)
    if metrics.get("mode") != "edit_localization_probe":
        failures.append("unexpected_probe_mode")
    if metrics.get("probe_scale") != "target_100m":
        failures.append("unexpected_probe_scale")
    if not metrics.get("runtime_executed"):
        failures.append("runtime_not_executed")
    if not metrics.get("required_artifacts_written"):
        failures.append("required_artifacts_not_written")
    if not metrics.get("multilingual_surface_readiness_passed"):
        failures.append("multilingual_surface_readiness_failed")
    if metrics.get("first_vocab_label") != "K":
        failures.append("unexpected_first_vocab_label")
    if metrics.get("last_vocab_label") != "Z":
        failures.append("unexpected_last_vocab_label")
    if not metrics.get("collapsed_to_last_vocab_label"):
        failures.append("did_not_collapse_to_last_vocab_label")
    next_step = "Build the next edit-localization intervention around the head/objective itself: e.g. binary-vs-rest decomposition, per-class logit calibration, or explicit logit-bias diagnostics, because serializer and label-identity changes preserved a collapse to the max-index class rather than fixing multilingual exactness."
    audit = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "quality_passed": False,
        "failures": failures,
        "artifact_status": artifacts,
        "telemetry_counts": telemetry_counts(),
        "metrics": metrics,
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": next_step,
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "quality_passed": False,
        "promotion_ready": False,
        "created_at_unix": int(time.time()),
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "successful_probe_output_dir": str(SUCCESS_DIR.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "metrics": {
            "eval_edit_localization_exact": metrics.get("eval_edit_localization_exact"),
            "strict_edit_localization_exact": metrics.get("strict_edit_localization_exact"),
            "first_vocab_label": metrics.get("first_vocab_label"),
            "last_vocab_label": metrics.get("last_vocab_label"),
            "collapsed_to_first_vocab_label": metrics.get("collapsed_to_first_vocab_label"),
            "collapsed_to_last_vocab_label": metrics.get("collapsed_to_last_vocab_label"),
        },
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": next_step,
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9868 Edit-Localization Label-Identity Target-100M Probe Audit",
        "",
        f"Passed: `{summary['passed']}`",
        f"Eval exact: `{metrics.get('eval_edit_localization_exact')}`",
        f"Strict exact: `{metrics.get('strict_edit_localization_exact')}`",
        f"First vocab label: `{metrics.get('first_vocab_label')}`",
        f"Last vocab label: `{metrics.get('last_vocab_label')}`",
        f"Collapsed to first vocab label: `{metrics.get('collapsed_to_first_vocab_label')}`",
        f"Collapsed to last vocab label: `{metrics.get('collapsed_to_last_vocab_label')}`",
        "",
        f"Next: {next_step}",
        "",
    ]) + "\n", encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "collapsed_to_first_vocab_label": metrics.get("collapsed_to_first_vocab_label")}, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
