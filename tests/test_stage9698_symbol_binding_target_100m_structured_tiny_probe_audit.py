from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9698_symbol_binding_target_100m_structured_tiny_probe_audit.py"
    spec = importlib.util.spec_from_file_location("stage9698", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9698_success_artifacts_and_metrics_present():
    mod = _load()
    assert mod.SUCCESS_DIR.exists()
    artifacts = mod.artifact_status()
    missing = [name for name, status in artifacts.items() if not status["exists"] or status["bytes"] <= 0]
    assert missing == []
    metrics = mod.extract_metrics()
    assert metrics["mode"] == "symbol_binding_probe"
    assert metrics["probe_scale"] == "target_100m"
    assert metrics["estimated_parameter_count"] == 102703145
    assert metrics["fields"] == ["symbol_binding"]
    assert metrics["train_rows"] == 32
    assert metrics["eval_rows"] == 16
    assert metrics["strict_rows"] == 16
    assert metrics["required_artifacts_written"] is True
    assert metrics["loss_counts"]["symbol_binding_ce"] == 64


def test_stage9698_closed_boundaries_and_quality_not_promoted():
    mod = _load()
    metrics = mod.extract_metrics()
    assert metrics["final_checkpoint_exported"] is False
    assert metrics["runtime_executed"] is False
    assert metrics["gemma_executed"] is False
    assert metrics["harness_executed"] is False
    assert metrics["eval_symbol_binding_exact"] == 0.3125
    assert metrics["strict_symbol_binding_exact"] == 0.3125
    buckets = metrics["delta_norm_by_bucket"]
    assert buckets["decoder"] == 0.0
    assert buckets["decoder_attention"] == 0.0
    assert buckets["decoder_mlp"] == 0.0
    assert buckets["embeddings"] == 0.0
    assert buckets["lm_head"] == 0.0
    assert metrics["structured_head_delta_norm"] > 0.0
