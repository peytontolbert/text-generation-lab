from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

torch = pytest.importorskip('torch')
pytest.importorskip('torch.nn')


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'legacy_src'))
    path = root / 'legacy_src/agentkernel_lite/modeling_transformer.py'
    spec = importlib.util.spec_from_file_location('stage_structured_field_attention_modeling_transformer', path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules['stage_structured_field_attention_modeling_transformer'] = module
    spec.loader.exec_module(module)
    return module


def test_structured_field_representation_respects_attention_mask_shape():
    mod = _load()
    cfg = mod.AgentKernelLiteTransformerConfig(vocab_size=32, d_model=8, d_ff=16, n_layers=1, n_heads=2)
    model = mod.AgentKernelLiteTransformerSeq2Seq(cfg)
    memory = torch.randn(2, 3, cfg.d_model)
    pooled = torch.randn(2, cfg.d_model)
    attention_mask = torch.tensor([[True, True, False], [True, False, False]])
    input_ids = torch.tensor([[1, 2, 0], [3, 0, 0]])
    query = model.structured_field_queries['edit_localization']
    rep = model._structured_field_representation(memory, pooled, attention_mask, input_ids, query)
    assert rep.shape == (2, cfg.d_model)
    assert torch.isfinite(rep).all()


def test_estimate_parameter_count_includes_structured_field_queries():
    mod = _load()
    cfg = mod.AgentKernelLiteTransformerConfig(vocab_size=32, d_model=8, d_ff=16, n_layers=1, n_heads=2)
    count = mod.estimate_transformer_parameter_count(cfg)
    query_params = len(cfg.structured_head_dims) * cfg.d_model
    assert count >= query_params
