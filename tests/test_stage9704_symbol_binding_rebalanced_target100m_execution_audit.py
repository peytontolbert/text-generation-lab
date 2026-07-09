from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9704_symbol_binding_rebalanced_target100m_execution_audit.py"
    spec = importlib.util.spec_from_file_location("stage9704", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9704_execution_result_safe_but_not_quality_passed():
    mod = _load()
    result = mod.load_json(mod.RUN_DIR / "execution_result.json")
    assert result["required_artifacts_written"] is True
    assert result["implementation"]["estimated_parameter_count"] == 102703145
    assert result["native_feature_ablation_audit_required"] is True
    assert result["native_feature_ablation_rows"] == 32
    assert result["runtime_executed"] is False
    assert result["gemma_executed"] is False
    assert result["harness_executed"] is False
    assert result["final_checkpoint_exported"] is False
    assert result["eval"]["eval"]["field_exact"]["symbol_binding"]["exact"] == 0.25
    assert result["eval"]["strict_eval"]["field_exact"]["symbol_binding"]["exact"] == 0.25


def test_stage9704_native_ablation_and_frozen_decoder_contracts():
    mod = _load()
    rows = mod.load_jsonl(mod.RUN_DIR / "feature_ablation_attribution.jsonl")
    modes = {item["ablation_mode"] for row in rows for item in row["feature_attribution"]}
    assert len(rows) == 32
    assert modes == {"native_grouped_mask_rerun"}
    deltas = mod.load_json(mod.RUN_DIR / "module_delta_norms.json")
    buckets = deltas["delta_norm_by_bucket"]
    assert buckets["decoder"] == 0.0
    assert buckets["decoder_attention"] == 0.0
    assert buckets["decoder_mlp"] == 0.0
    assert buckets["embeddings"] == 0.0
    assert buckets["lm_head"] == 0.0


def test_stage9704_scheduler_exposure_diagnoses_missing_retrieve_more():
    mod = _load()
    rows = mod.load_jsonl(mod.MANIFEST)
    exposure = mod.current_scheduler_exposure(rows, max_steps=8, batch_size=2)
    assert exposure["train_rows"] == 32
    assert exposure["unique_train_rows_seen"] == 16
    assert exposure["used_label_counts"]["BIND_CALL_TO_SYMBOL"] == 8
    assert "RETRIEVE_MORE" in exposure["missing_train_labels_in_used_batches"]
    assert "RETRIEVE_MORE" in exposure["underexposed_labels"]
