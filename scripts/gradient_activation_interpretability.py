from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from training_telemetry_metrics import softmax
except ModuleNotFoundError:  # pragma: no cover - CLI fallback
    from scripts.training_telemetry_metrics import softmax  # type: ignore


def _flatten(values: Any) -> list[float]:
    if values is None:
        return []
    if isinstance(values, (int, float)):
        return [float(values)]
    if isinstance(values, Mapping):
        out: list[float] = []
        for key in sorted(values):
            out.extend(_flatten(values[key]))
        return out
    if isinstance(values, Iterable) and not isinstance(values, (str, bytes)):
        out: list[float] = []
        for item in values:
            out.extend(_flatten(item))
        return out
    return []


def l2_norm(values: Any) -> float:
    flat = _flatten(values)
    return math.sqrt(sum(value * value for value in flat))


def vector_stats(values: Any) -> dict[str, Any]:
    flat = _flatten(values)
    if not flat:
        return {"count": 0, "mean": 0.0, "l2_norm": 0.0, "max_abs": 0.0}
    return {
        "count": len(flat),
        "mean": float(sum(flat) / len(flat)),
        "l2_norm": l2_norm(flat),
        "max_abs": float(max(abs(value) for value in flat)),
    }


def _module_name(parameter_name: str) -> str:
    parts = parameter_name.split(".")
    if not parts:
        return parameter_name
    if parts[0] in {"encoder", "decoder", "shared", "lm_head", "structured_heads", "structured_aux"}:
        return parts[0]
    return parts[0]


def row_gradient_norm_card(row_id: str, gradients: Mapping[str, Any]) -> dict[str, Any]:
    by_parameter: dict[str, float] = {}
    by_module_sq: dict[str, float] = {}
    for name, values in gradients.items():
        norm = l2_norm(values)
        by_parameter[name] = norm
        module = _module_name(name)
        by_module_sq[module] = by_module_sq.get(module, 0.0) + norm * norm
    by_module = {module: math.sqrt(total) for module, total in sorted(by_module_sq.items())}
    total_norm = math.sqrt(sum(norm * norm for norm in by_parameter.values()))
    return {
        "row_id": row_id,
        "parameter_count": len(by_parameter),
        "total_grad_norm": total_norm,
        "grad_norm_by_module": by_module,
        "grad_norm_by_parameter": dict(sorted(by_parameter.items())),
        "decoder_grad_norm": by_module.get("decoder", 0.0),
    }


def module_delta_norms(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    names = sorted(set(before) | set(after))
    by_parameter: dict[str, float] = {}
    by_module_sq: dict[str, float] = {}
    missing_before: list[str] = []
    missing_after: list[str] = []
    for name in names:
        if name not in before:
            missing_before.append(name)
        if name not in after:
            missing_after.append(name)
        left = _flatten(before.get(name, []))
        right = _flatten(after.get(name, []))
        width = max(len(left), len(right))
        left += [0.0] * (width - len(left))
        right += [0.0] * (width - len(right))
        delta = [r - l for l, r in zip(left, right)]
        norm = l2_norm(delta)
        by_parameter[name] = norm
        module = _module_name(name)
        by_module_sq[module] = by_module_sq.get(module, 0.0) + norm * norm
    by_module = {module: math.sqrt(total) for module, total in sorted(by_module_sq.items())}
    return {
        "parameter_count": len(names),
        "total_delta_norm": math.sqrt(sum(norm * norm for norm in by_parameter.values())),
        "delta_norm_by_module": by_module,
        "delta_norm_by_parameter": by_parameter,
        "decoder_delta_norm": by_module.get("decoder", 0.0),
        "missing_before": missing_before,
        "missing_after": missing_after,
    }


def activation_cache_summary(row_id: str, activations: Mapping[str, Any]) -> dict[str, Any]:
    layer_stats = {name: vector_stats(values) for name, values in sorted(activations.items())}
    return {
        "row_id": row_id,
        "layers": layer_stats,
        "layer_count": len(layer_stats),
        "activation_cache_present": bool(layer_stats),
    }


def _gold_index(labels: list[str], gold_label: str) -> int:
    if gold_label not in labels:
        raise ValueError(f"gold label {gold_label!r} is not in labels")
    return labels.index(gold_label)


def feature_ablation_attribution(
    row_id: str,
    field: str,
    baseline_logits: Iterable[float],
    ablated_logits_by_feature: Mapping[str, Iterable[float]],
    labels: list[str],
    gold_label: str,
) -> dict[str, Any]:
    gold = _gold_index(labels, gold_label)
    base_logits = [float(x) for x in baseline_logits]
    base_probs = softmax(base_logits)
    base_gold_prob = base_probs[gold] if gold < len(base_probs) else 0.0
    base_gold_logit = base_logits[gold] if gold < len(base_logits) else 0.0
    rows = []
    for feature, logits_iter in sorted(ablated_logits_by_feature.items()):
        logits = [float(x) for x in logits_iter]
        probs = softmax(logits)
        gold_prob = probs[gold] if gold < len(probs) else 0.0
        gold_logit = logits[gold] if gold < len(logits) else 0.0
        rows.append({
            "feature_group": feature,
            "gold_prob_drop": float(base_gold_prob - gold_prob),
            "gold_logit_drop": float(base_gold_logit - gold_logit),
            "ablated_gold_prob": gold_prob,
            "ablated_gold_logit": gold_logit,
        })
    rows.sort(key=lambda row: (row["gold_prob_drop"], row["gold_logit_drop"]), reverse=True)
    return {
        "row_id": row_id,
        "field": field,
        "gold_label": gold_label,
        "baseline_gold_prob": base_gold_prob,
        "baseline_gold_logit": base_gold_logit,
        "feature_attribution": rows,
        "top_feature_group": rows[0]["feature_group"] if rows else None,
    }


def activation_patch_recovery_card(
    row_id: str,
    field: str,
    clean_logits: Iterable[float],
    corrupt_logits: Iterable[float],
    patched_logits: Iterable[float],
    labels: list[str],
    gold_label: str,
    *,
    patched_layer: str,
) -> dict[str, Any]:
    gold = _gold_index(labels, gold_label)
    clean = [float(x) for x in clean_logits]
    corrupt = [float(x) for x in corrupt_logits]
    patched = [float(x) for x in patched_logits]
    clean_gold = clean[gold] if gold < len(clean) else 0.0
    corrupt_gold = corrupt[gold] if gold < len(corrupt) else 0.0
    patched_gold = patched[gold] if gold < len(patched) else 0.0
    denominator = clean_gold - corrupt_gold
    recovery = 0.0 if abs(denominator) < 1e-12 else (patched_gold - corrupt_gold) / denominator
    pred_index = max(range(len(patched)), key=lambda idx: patched[idx]) if patched else None
    return {
        "row_id": row_id,
        "field": field,
        "patched_layer": patched_layer,
        "gold_label": gold_label,
        "patched_prediction": labels[pred_index] if pred_index is not None and pred_index < len(labels) else None,
        "clean_gold_logit": clean_gold,
        "corrupt_gold_logit": corrupt_gold,
        "patched_gold_logit": patched_gold,
        "logit_recovery_fraction": float(recovery),
        "recovered_prediction": pred_index == gold,
    }


def interpretability_bundle_card(
    *,
    row_gradient: Mapping[str, Any],
    module_delta: Mapping[str, Any],
    activation_summary: Mapping[str, Any],
    feature_ablation: Mapping[str, Any],
    activation_patch: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "passed": bool(
            row_gradient.get("total_grad_norm", 0.0) >= 0.0
            and module_delta.get("decoder_delta_norm", 0.0) >= 0.0
            and activation_summary.get("activation_cache_present")
            and feature_ablation.get("top_feature_group")
            and "logit_recovery_fraction" in activation_patch
        ),
        "row_gradient_norms_present": "total_grad_norm" in row_gradient,
        "module_delta_norms_present": "total_delta_norm" in module_delta,
        "activation_cache_summary_present": bool(activation_summary.get("activation_cache_present")),
        "feature_ablation_present": bool(feature_ablation.get("feature_attribution")),
        "activation_patch_present": "logit_recovery_fraction" in activation_patch,
        "authority": {
            "model_execution": False,
            "training": False,
            "runtime": False,
            "source_body_emission": False,
        },
    }


def _sample() -> dict[str, Any]:
    row_grad = row_gradient_norm_card("r1", {"encoder.layer0.weight": [0.1, 0.2], "structured_heads.action.weight": [0.3]})
    delta = module_delta_norms({"encoder.layer0.weight": [1.0, 2.0], "decoder.block.weight": [0.5]}, {"encoder.layer0.weight": [1.1, 2.0], "decoder.block.weight": [0.5]})
    activation = activation_cache_summary("r1", {"encoder.0": [0.1, -0.2, 0.3], "field_head_input": [1.0, 0.0]})
    ablation = feature_ablation_attribution("r1", "build_mode", [0.1, 2.0, 0.0], {"import_evidence": [0.1, 0.4, 0.0], "language": [0.1, 1.9, 0.0]}, ["SCRATCH", "IMPORT", "WRAP"], "IMPORT")
    patch = activation_patch_recovery_card("r1", "build_mode", [0.0, 3.0], [2.0, 0.0], [0.5, 2.5], ["SCRATCH", "IMPORT"], "IMPORT", patched_layer="encoder.final")
    return {
        "row_gradient": row_grad,
        "module_delta": delta,
        "activation_summary": activation,
        "feature_ablation": ablation,
        "activation_patch": patch,
        "bundle": interpretability_bundle_card(row_gradient=row_grad, module_delta=delta, activation_summary=activation, feature_ablation=ablation, activation_patch=patch),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Emit a deterministic gradient/activation interpretability sample card without model execution.")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    card = _sample()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
