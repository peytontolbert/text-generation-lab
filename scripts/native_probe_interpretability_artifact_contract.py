from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


BOUNDED_JSONL_KEYS: dict[str, set[str]] = {
    "loss_by_step.jsonl": {"step", "loss", "grad_norm"},
    "eval_loss_by_checkpoint.jsonl": {"split", "rows", "loss"},
    "row_token_loss.jsonl": {"row_id", "positions", "mean_loss", "token_count"},
    "row_gradient_norms.jsonl": {"row_id", "total_grad_norm", "grad_norm_by_bucket", "gradient_scope"},
    "activation_summary.jsonl": {"row_id", "layers", "activation_cache_present"},
    "row_dynamics_history.jsonl": {"row_id", "loss_history", "forgetting_events", "prediction_flip_count"},
}

STRUCTURED_JSONL_KEYS: dict[str, set[str]] = {
    "loss_by_step.jsonl": {"step", "loss", "grad_norm"},
    "eval_loss_by_checkpoint.jsonl": {"split", "rows", "field_exact"},
    "row_field_logits.jsonl": {"row_id", "field", "target", "pred", "confidence", "entropy", "top_k", "high_confidence_wrong"},
    "row_field_losses.jsonl": {"split", "field", "loss", "exact"},
    "row_gradient_norms.jsonl": {"row_id", "total_grad_norm", "grad_norm_by_bucket", "gradient_scope"},
    "activation_summary.jsonl": {"row_id", "layers", "activation_cache_present"},
    "feature_ablation_attribution.jsonl": {"row_id", "field", "feature_attribution", "top_feature_group"},
    "activation_patch_recovery.jsonl": {"row_id", "field", "patched_layer", "logit_recovery_fraction"},
    "row_dynamics_history.jsonl": {"row_id", "confidence_history", "forgetting_events", "prediction_flip_count"},
}

BOUNDED_JSON_KEYS: dict[str, set[str]] = {
    "module_delta_norms.json": {"delta_norm_by_bucket", "decoder_delta_norm", "total_delta_norm"},
    "internal_token_logit_summary.json": {"rows", "total_internal_token_probability_mass"},
    "eos_length_audit.json": {"rows_checked", "max_decoder_tokens"},
    "short_output_probe.json": {"generated_rows"},
    "repetition_probe.json": {"generated_rows"},
    "internal_leak_probe.json": {"target_internal_token_rows"},
    "sample_generation_audit.json": {"generated_rows"},
    "failure_bucket_card.json": {"failure_rows"},
    "cleanup_proof.json": {"cleanup_executed", "run_id"},
}

STRUCTURED_JSON_KEYS: dict[str, set[str]] = {
    "module_delta_norms.json": {"delta_norm_by_bucket", "decoder_delta_norm", "total_delta_norm"},
    "field_exact_by_cell.json": set(),
    "field_label_vocabs.json": set(),
    "structured_confusion_matrix.json": set(),
    "failure_bucket_card.json": {"mode", "eval"},
    "cleanup_proof.json": {"cleanup_executed", "run_id"},
}


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid json: {path}: {exc}") from exc


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid jsonl: {path}:{line_number}: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"jsonl record is not object: {path}:{line_number}")
        rows.append(value)
    return rows


def _check_required_keys(record: dict[str, Any], keys: set[str]) -> list[str]:
    return sorted(key for key in keys if key not in record)


def audit_artifact_dir(path: Path, *, mode: str) -> dict[str, Any]:
    if mode not in {"bounded_decoder_ce_probe", "structured_aux_probe"}:
        raise ValueError(f"unsupported mode: {mode}")
    jsonl_keys = BOUNDED_JSONL_KEYS if mode == "bounded_decoder_ce_probe" else STRUCTURED_JSONL_KEYS
    json_keys = BOUNDED_JSON_KEYS if mode == "bounded_decoder_ce_probe" else STRUCTURED_JSON_KEYS
    errors: list[str] = []
    artifacts: dict[str, Any] = {}

    for name, required in jsonl_keys.items():
        artifact_path = path / name
        if not artifact_path.is_file():
            errors.append(f"missing artifact: {name}")
            continue
        rows = _read_jsonl(artifact_path)
        if not rows:
            errors.append(f"empty jsonl artifact: {name}")
            artifacts[name] = {"rows": 0}
            continue
        missing = _check_required_keys(rows[0], required)
        if missing:
            errors.append(f"artifact {name} first record missing keys: {missing}")
        artifacts[name] = {"rows": len(rows), "required_keys": sorted(required), "first_record_keys": sorted(rows[0])}
        if name == "row_field_logits.jsonl":
            top_k = rows[0].get("top_k")
            if not isinstance(top_k, list) or not top_k:
                errors.append("row_field_logits.jsonl top_k must be non-empty")
        if name == "row_token_loss.jsonl":
            positions = rows[0].get("positions")
            if not isinstance(positions, list) or not positions or "loss" not in positions[0]:
                errors.append("row_token_loss.jsonl positions must contain per-position loss")

    for name, required in json_keys.items():
        artifact_path = path / name
        if not artifact_path.is_file():
            errors.append(f"missing artifact: {name}")
            continue
        value = _read_json(artifact_path)
        if isinstance(value, dict):
            missing = _check_required_keys(value, required)
            if missing:
                errors.append(f"artifact {name} missing keys: {missing}")
            artifacts[name] = {"keys": sorted(value), "required_keys": sorted(required)}
        else:
            errors.append(f"json artifact is not object: {name}")

    module_delta = _read_json(path / "module_delta_norms.json") if (path / "module_delta_norms.json").is_file() else {}
    if mode != "bounded_decoder_ce_probe" and float(module_delta.get("decoder_delta_norm", 0.0)) > 1e-8:
        errors.append("structured probe moved decoder/lm-head parameters; decoder delta guard failed")

    return {
        "passed": not errors,
        "mode": mode,
        "artifact_dir": str(path),
        "errors": errors,
        "artifacts": artifacts,
        "nonempty_jsonl_artifacts": sum(1 for card in artifacts.values() if isinstance(card, dict) and card.get("rows", 0) > 0),
        "decoder_delta_norm": module_delta.get("decoder_delta_norm"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit native probe interpretability artifacts for non-empty, schema-complete telemetry.")
    parser.add_argument("artifact_dir", type=Path)
    parser.add_argument("--mode", choices=("bounded_decoder_ce_probe", "structured_aux_probe"), required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    card = audit_artifact_dir(args.artifact_dir, mode=args.mode)
    text = json.dumps(card, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    if not card["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
