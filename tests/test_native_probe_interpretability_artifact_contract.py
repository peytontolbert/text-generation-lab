from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from native_probe_interpretability_artifact_contract import audit_artifact_dir


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, row: object) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def write_structured_artifacts(out: Path) -> None:
    out.mkdir()
    append_jsonl(out / "loss_by_step.jsonl", {"step": 1, "loss": 1.0, "grad_norm": 0.5})
    append_jsonl(out / "eval_loss_by_checkpoint.jsonl", {"split": "strict_eval", "rows": 1, "field_exact": {"build_mode": {"exact": 1.0}}})
    append_jsonl(out / "row_field_logits.jsonl", {"row_id": "r1", "field": "build_mode", "target": "A", "pred": "A", "confidence": 0.9, "entropy": 0.1, "top_k": [{"label": "A", "prob": 0.9}], "high_confidence_wrong": False})
    append_jsonl(out / "row_field_losses.jsonl", {"split": "strict_eval", "field": "build_mode", "loss": 0.1, "exact": 1.0})
    append_jsonl(out / "row_gradient_norms.jsonl", {"row_id": "r1", "total_grad_norm": 1.0, "grad_norm_by_bucket": {"structured_heads": 1.0}, "gradient_scope": "batch_shared"})
    append_jsonl(out / "activation_summary.jsonl", {"row_id": "r1", "layers": {"field_head_input": {"l2_norm": 1.0}}, "activation_cache_present": True})
    append_jsonl(out / "feature_ablation_attribution.jsonl", {"row_id": "r1", "field": "build_mode", "feature_attribution": [{"feature_group": "intent", "gold_prob_drop": 0.5}], "top_feature_group": "intent"})
    append_jsonl(out / "activation_patch_recovery.jsonl", {"row_id": "r1", "field": "build_mode", "patched_layer": "field_head_input", "logit_recovery_fraction": 1.0})
    append_jsonl(out / "row_dynamics_history.jsonl", {"row_id": "r1", "confidence_history": [0.9], "forgetting_events": 0, "prediction_flip_count": 0})
    write_json(out / "module_delta_norms.json", {"delta_norm_by_bucket": {"structured_heads": 0.1}, "decoder_delta_norm": 0.0, "total_delta_norm": 0.1})
    write_json(out / "field_exact_by_cell.json", {"build_mode": {"cell": {"exact": 1.0}}})
    write_json(out / "field_label_vocabs.json", {"build_mode": {"A": 0}})
    write_json(out / "structured_confusion_matrix.json", {"build_mode": {"A": {"A": 1}}})
    write_json(out / "failure_bucket_card.json", {"mode": "structured_policy_probe", "eval": {}})
    write_json(out / "cleanup_proof.json", {"cleanup_executed": False, "run_id": "r"})


def test_structured_artifact_contract_passes_schema_complete_outputs(tmp_path: Path) -> None:
    out = tmp_path / "artifacts"
    write_structured_artifacts(out)
    card = audit_artifact_dir(out, mode="structured_aux_probe")
    assert card["passed"] is True
    assert card["nonempty_jsonl_artifacts"] >= 8


def test_artifact_contract_fails_empty_jsonl(tmp_path: Path) -> None:
    out = tmp_path / "artifacts"
    write_structured_artifacts(out)
    (out / "row_field_logits.jsonl").write_text("", encoding="utf-8")
    card = audit_artifact_dir(out, mode="structured_aux_probe")
    assert card["passed"] is False
    assert any("empty jsonl artifact: row_field_logits.jsonl" in error for error in card["errors"])


def test_bounded_artifact_contract_requires_real_token_positions(tmp_path: Path) -> None:
    out = tmp_path / "bounded"
    out.mkdir()
    append_jsonl(out / "loss_by_step.jsonl", {"step": 1, "loss": 1.0, "grad_norm": 0.5})
    append_jsonl(out / "eval_loss_by_checkpoint.jsonl", {"split": "eval", "rows": 1, "loss": 1.0})
    append_jsonl(out / "row_token_loss.jsonl", {"row_id": "r1", "positions": [{"position": 0, "loss": 1.2}], "mean_loss": 1.2, "token_count": 1})
    append_jsonl(out / "row_gradient_norms.jsonl", {"row_id": "r1", "total_grad_norm": 1.0, "grad_norm_by_bucket": {"decoder": 1.0}, "gradient_scope": "batch_shared"})
    append_jsonl(out / "activation_summary.jsonl", {"row_id": "r1", "layers": {"decoder_logits": {"l2_norm": 1.0}}, "activation_cache_present": True})
    append_jsonl(out / "row_dynamics_history.jsonl", {"row_id": "r1", "loss_history": [1.2], "forgetting_events": 0, "prediction_flip_count": 0})
    for name, value in {
        "module_delta_norms.json": {"delta_norm_by_bucket": {"decoder": 0.1}, "decoder_delta_norm": 0.1, "total_delta_norm": 0.1},
        "internal_token_logit_summary.json": {"rows": 1, "total_internal_token_probability_mass": 0.0},
        "eos_length_audit.json": {"rows_checked": 1, "max_decoder_tokens": 16},
        "short_output_probe.json": {"generated_rows": 0},
        "repetition_probe.json": {"generated_rows": 0},
        "internal_leak_probe.json": {"target_internal_token_rows": 0},
        "sample_generation_audit.json": {"generated_rows": 0},
        "failure_bucket_card.json": {"failure_rows": 0},
        "cleanup_proof.json": {"cleanup_executed": False, "run_id": "r"},
    }.items():
        write_json(out / name, value)
    card = audit_artifact_dir(out, mode="bounded_decoder_ce_probe")
    assert card["passed"] is True
