from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9702_native_feature_ablation_trainer_patch_audit.py"
    spec = importlib.util.spec_from_file_location("stage9702", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9702_trainer_support_is_present():
    mod = _load()
    support = mod.trainer_support()
    assert support["cli_flag_present"] is True
    assert support["contract_card_field_present"] is True
    assert support["structured_probe_argument_present"] is True
    assert support["native_mode_present"] is True
    assert support["query_kind_group_present"] is True


def test_stage9702_smoke_emits_native_ablation_rows_only():
    mod = _load()
    smoke = mod.smoke_metrics()
    assert smoke["mode"] == "symbol_binding_probe"
    assert smoke["probe_scale"] == "tiny_transformer_runtime_path"
    assert smoke["full_100m_target_execution_authorized"] is False
    assert smoke["required_artifacts_written"] is True
    assert smoke["native_feature_ablation_audit_required"] is True
    assert smoke["native_feature_ablation_rows"] == 32
    assert smoke["feature_ablation_rows"] == 32
    assert smoke["ablation_modes"] == ["native_grouped_mask_rerun"]
    assert set(smoke["feature_groups"]) == {
        "query_kind",
        "intent_features",
        "import_dependency_evidence",
        "graph_evidence",
        "surface_role_features",
        "verifier_feedback",
    }


def test_stage9702_smoke_keeps_closed_boundaries_and_frozen_decoder():
    mod = _load()
    smoke = mod.smoke_metrics()
    assert smoke["runtime_executed"] is False
    assert smoke["gemma_executed"] is False
    assert smoke["harness_executed"] is False
    assert smoke["final_checkpoint_exported"] is False
    buckets = smoke["delta_norm_by_bucket"]
    assert buckets["decoder"] == 0.0
    assert buckets["decoder_attention"] == 0.0
    assert buckets["decoder_mlp"] == 0.0
    assert buckets["embeddings"] == 0.0
    assert buckets["lm_head"] == 0.0
