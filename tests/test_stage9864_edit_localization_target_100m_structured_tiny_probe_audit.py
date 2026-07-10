from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9864_edit_localization_target_100m_structured_tiny_probe_audit.py"
    spec = importlib.util.spec_from_file_location("stage9864", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9864_metrics_present_and_multilingual_surface_is_real():
    mod = _load()
    assert mod.SUCCESS_DIR.exists()
    artifacts = mod.artifact_status()
    missing = [name for name, status in artifacts.items() if not status["exists"] or status["bytes"] <= 0]
    assert missing == []
    metrics = mod.extract_metrics()
    assert metrics["mode"] == "edit_localization_probe"
    assert metrics["probe_scale"] == "target_100m"
    assert metrics["estimated_parameter_count"] == 102717225
    assert metrics["fields"] == ["edit_localization"]
    assert metrics["train_rows"] == 20
    assert metrics["eval_rows"] == 16
    assert metrics["strict_rows"] == 16
    assert metrics["required_artifacts_written"] is True
    assert metrics["multilingual_surface_readiness_passed"] is True
    telemetry = mod.telemetry_counts()
    assert telemetry["loss_by_step_rows"] == 16
    assert telemetry["row_field_logits_rows"] > 0


def test_stage9864_closed_boundaries_and_detected_label_collapse():
    mod = _load()
    metrics = mod.extract_metrics()
    assert metrics["final_checkpoint_exported"] is False
    assert metrics["runtime_executed"] is True
    assert metrics["gemma_executed"] is False
    assert metrics["harness_executed"] is False
    assert metrics["eval_edit_localization_exact"] == 0.0
    assert metrics["strict_edit_localization_exact"] == 0.0
    collapse = metrics["collapse"]
    assert collapse["dominant_label"] == "E"
    assert collapse["collapsed_to_single_label"] is True
    buckets = metrics["delta_norm_by_bucket"]
    assert buckets.get("decoder", 0.0) == 0.0
    assert buckets.get("decoder_attention", 0.0) == 0.0
    assert buckets.get("decoder_mlp", 0.0) == 0.0
    assert buckets.get("embeddings", 0.0) == 0.0
    assert buckets.get("lm_head", 0.0) == 0.0
