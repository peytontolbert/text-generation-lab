#!/usr/bin/env python3
from __future__ import annotations

import json
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9699
NAME = "stage9699_symbol_binding_postrun_diagnostics"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9698_symbol_binding_target_100m_structured_tiny_probe_audit.json"
RUN_DIR = ROOT / "runs/local/artifacts/stage9698_symbol_binding_target_100m_structured_tiny_probe/symbol_binding_probe_after_alias_patch"
MANIFEST = ROOT / "runs/local/artifacts/stage9695_multisurface_structured_tiny_execution_review/tiny_structured_manifests/symbol_binding_tiny.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DIAGNOSTICS = OUT_DIR / "symbol_binding_postrun_diagnostics.json"
PATCH_QUEUE = OUT_DIR / "stage9700_symbol_binding_repair_queue.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SYMBOL_BINDING_POSTRUN_DIAGNOSTICS_STAGE9699.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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


def target_label(row: dict[str, Any]) -> str | None:
    clean = row.get("clean_state") if isinstance(row.get("clean_state"), dict) else {}
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    return clean.get("binding_action") or clean.get("symbol_binding") or target.get("binding_action") or target.get("symbol_binding") or row.get("binding_action")


def query_kind(row: dict[str, Any]) -> str:
    query = row.get("query") if isinstance(row.get("query"), dict) else {}
    graph = row.get("graph_input") if isinstance(row.get("graph_input"), dict) else {}
    return str(query.get("query_kind") or graph.get("query_kind") or "unknown")


def manifest_balance(rows: list[dict[str, Any]]) -> dict[str, Any]:
    split_label: dict[str, Counter[str]] = defaultdict(Counter)
    split_query: dict[str, Counter[str]] = defaultdict(Counter)
    labels: Counter[str] = Counter()
    queries: Counter[str] = Counter()
    for row in rows:
        split = str(row.get("split") or "unknown")
        label = target_label(row) or "MISSING_LABEL"
        kind = query_kind(row)
        labels[label] += 1
        queries[kind] += 1
        split_label[split][label] += 1
        split_query[split][kind] += 1
    label_set = set(labels)
    missing_by_split = {
        split: sorted(label_set - set(counter))
        for split, counter in split_label.items()
    }
    return {
        "rows": len(rows),
        "label_counts": dict(labels),
        "query_kind_counts": dict(queries),
        "split_label_counts": {split: dict(counter) for split, counter in split_label.items()},
        "split_query_kind_counts": {split: dict(counter) for split, counter in split_query.items()},
        "missing_labels_by_split": missing_by_split,
        "labels_missing_from_eval_or_strict": sorted(
            label
            for label in label_set
            if split_label.get("eval", Counter()).get(label, 0) == 0
            or split_label.get("strict_eval", Counter()).get(label, 0) == 0
        ),
    }


def prediction_diagnostics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_split_target: dict[str, Counter[str]] = defaultdict(Counter)
    by_split_pred: dict[str, Counter[str]] = defaultdict(Counter)
    confusion: dict[str, Counter[str]] = defaultdict(Counter)
    confidences = [float(row.get("confidence", 0.0)) for row in rows]
    margins = [float(row.get("margin", 0.0)) for row in rows]
    wrong = [row for row in rows if not row.get("correct")]
    for row in rows:
        split = str(row.get("split") or "unknown")
        target = str(row.get("target"))
        pred = str(row.get("pred"))
        by_split_target[split][target] += 1
        by_split_pred[split][pred] += 1
        confusion[target][pred] += 1
    total = len(rows)
    correct = sum(1 for row in rows if row.get("correct"))
    pred_counts = Counter(str(row.get("pred")) for row in rows)
    max_pred_count = max(pred_counts.values()) if pred_counts else 0
    return {
        "rows": total,
        "exact": correct / total if total else 0.0,
        "by_split_target": {split: dict(counter) for split, counter in by_split_target.items()},
        "by_split_pred": {split: dict(counter) for split, counter in by_split_pred.items()},
        "confusion": {target: dict(counter) for target, counter in confusion.items()},
        "prediction_counts": dict(pred_counts),
        "prediction_collapse_label": pred_counts.most_common(1)[0][0] if pred_counts else None,
        "prediction_collapse_rate": max_pred_count / total if total else 0.0,
        "confidence_mean": statistics.fmean(confidences) if confidences else 0.0,
        "margin_mean": statistics.fmean(margins) if margins else 0.0,
        "wrong_count": len(wrong),
        "wrong_confidence_mean": statistics.fmean(float(row.get("confidence", 0.0)) for row in wrong) if wrong else 0.0,
        "wrong_margin_min": min((float(row.get("margin", 0.0)) for row in wrong), default=0.0),
        "wrong_margin_max": max((float(row.get("margin", 0.0)) for row in wrong), default=0.0),
        "high_confidence_wrong_rows": sum(1 for row in wrong if row.get("high_confidence_wrong")),
    }


def loss_diagnostics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    losses = [float(row.get("loss", 0.0)) for row in rows]
    correct = [int((row.get("field_correct") or {}).get("symbol_binding", 0)) for row in rows]
    if not losses:
        return {"rows": 0}
    return {
        "rows": len(rows),
        "first_loss": losses[0],
        "last_loss": losses[-1],
        "min_loss": min(losses),
        "max_loss": max(losses),
        "mean_loss": statistics.fmean(losses),
        "loss_increased_from_first_to_last": losses[-1] > losses[0],
        "correct_by_step": correct,
        "last_three_correct_total": sum(correct[-3:]),
    }


def gradient_diagnostics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"rows": 0}
    keys = ["total_grad_norm", "encoder_grad_norm", "structured_head_grad_norm", "decoder_grad_norm"]
    result: dict[str, Any] = {"rows": len(rows)}
    for key in keys:
        vals = [float(row.get(key, 0.0)) for row in rows]
        result[key] = {"min": min(vals), "mean": statistics.fmean(vals), "max": max(vals)}
    result["decoder_grad_nonzero_rows"] = sum(1 for row in rows if float(row.get("decoder_grad_norm", 0.0)) != 0.0)
    return result


def patch_rows(balance: dict[str, Any], predictions: dict[str, Any], losses: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        {
            "patch_id": "stage9700_split_label_coverage",
            "priority": 1,
            "issue": "eval_or_strict_missing_symbol_binding_labels",
            "evidence": {"labels_missing_from_eval_or_strict": balance["labels_missing_from_eval_or_strict"]},
            "recommended_action": "Recompile symbol_binding_tiny with every binding label represented in train/eval/strict, or drop unsupported labels from the capped probe contract.",
        },
        {
            "patch_id": "stage9700_prediction_collapse_counterbalance",
            "priority": 2,
            "issue": "all_eval_strict_predictions_collapsed_to_single_label",
            "evidence": {
                "collapse_label": predictions["prediction_collapse_label"],
                "collapse_rate": predictions["prediction_collapse_rate"],
                "confusion": predictions["confusion"],
            },
            "recommended_action": "Add same-query-kind and same-degree-profile contrastive rows where non-call labels are correct, especially RETRIEVE_MORE and BIND_TEST_TO_SYMBOL.",
        },
        {
            "patch_id": "stage9700_short_schedule_underfit_check",
            "priority": 3,
            "issue": "tiny_probe_loss_increased_late",
            "evidence": losses,
            "recommended_action": "After data balance is repaired, run a contract-only schedule review for a slightly longer structured-only probe with checkpoint selection, still no decoder CE.",
        },
        {
            "patch_id": "stage9700_native_feature_ablation_upgrade",
            "priority": 4,
            "issue": "feature_ablation_is_proxy_not_native_mask_rerun",
            "evidence": {"feature_ablation_artifact": "feature_ablation_attribution.jsonl"},
            "recommended_action": "Upgrade the next structured probe telemetry to perform real grouped feature masking reruns for graph/query/import/test evidence.",
        },
    ]
    return rows


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    manifest_rows = load_jsonl(MANIFEST)
    logit_rows = load_jsonl(RUN_DIR / "row_field_logits.jsonl")
    loss_rows = load_jsonl(RUN_DIR / "loss_by_step.jsonl")
    grad_rows = load_jsonl(RUN_DIR / "row_gradient_norms.jsonl")
    feature_rows = load_jsonl(RUN_DIR / "feature_ablation_attribution.jsonl")

    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9698_not_passed")
    if not manifest_rows:
        failures.append("manifest_rows_missing")
    if not logit_rows:
        failures.append("row_field_logits_missing")
    balance = manifest_balance(manifest_rows)
    predictions = prediction_diagnostics(logit_rows)
    losses = loss_diagnostics(loss_rows)
    gradients = gradient_diagnostics(grad_rows)
    proxy_ablation_rows = sum(
        1
        for row in feature_rows
        for item in row.get("feature_attribution", [])
        if item.get("ablation_mode") == "deterministic_presence_proxy"
    )
    queue = patch_rows(balance, predictions, losses)
    PATCH_QUEUE.write_text("\n".join(json.dumps(row, sort_keys=True) for row in queue) + "\n", encoding="utf-8")

    diagnostics = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "quality_passed": False,
        "promotion_ready": False,
        "failures": failures,
        "source_stage9698_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "run_dir": str(RUN_DIR.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "manifest_balance": balance,
        "prediction_diagnostics": predictions,
        "loss_diagnostics": losses,
        "gradient_diagnostics": gradients,
        "feature_ablation_proxy_rows": proxy_ablation_rows,
        "feature_ablation_native_rerun_available": False,
        "repair_queue": str(PATCH_QUEUE.relative_to(ROOT)),
        "authority": dict(AUTHORITY_CLOSED),
    }
    DIAGNOSTICS.write_text(json.dumps(diagnostics, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    next_step = (
        "Build Stage9700 symbol-binding repair compiler: rebalance split label coverage, add non-call contrastive rows, "
        "and upgrade native grouped feature ablations before any additional target-100M execution."
    )
    summary = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "quality_passed": False,
        "promotion_ready": False,
        "created_at_unix": int(time.time()),
        "artifacts": {
            "diagnostics": str(DIAGNOSTICS.relative_to(ROOT)),
            "repair_queue": str(PATCH_QUEUE.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "metrics": {
            "manifest_rows": balance["rows"],
            "labels_missing_from_eval_or_strict": balance["labels_missing_from_eval_or_strict"],
            "prediction_collapse_label": predictions["prediction_collapse_label"],
            "prediction_collapse_rate": predictions["prediction_collapse_rate"],
            "eval_strict_exact": predictions["exact"],
            "loss_increased_from_first_to_last": losses.get("loss_increased_from_first_to_last"),
            "decoder_grad_nonzero_rows": gradients.get("decoder_grad_nonzero_rows"),
            "feature_ablation_native_rerun_available": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": next_step,
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9699 Symbol-Binding Post-Run Diagnostics",
                "",
                "Stage9699 diagnoses the first target-100M source-backed symbol-binding probe. It does not authorize more execution.",
                "",
                "## Findings",
                "",
                f"- Eval+strict exact: `{predictions['exact']}`",
                f"- Prediction collapse: `{predictions['prediction_collapse_label']}` at `{predictions['prediction_collapse_rate']}`",
                f"- Labels missing from eval or strict: `{balance['labels_missing_from_eval_or_strict']}`",
                f"- Loss increased from first to last step: `{losses.get('loss_increased_from_first_to_last')}`",
                f"- Decoder gradient nonzero rows: `{gradients.get('decoder_grad_nonzero_rows')}`",
                "- Feature ablation telemetry is present but currently proxy-based, not native grouped masking.",
                "",
                "## Repair Direction",
                "",
                "Stage9700 should recompile the symbol-binding surface with complete split label coverage, add non-call contrastive rows, and upgrade native grouped feature ablations before any further target-100M execution.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
