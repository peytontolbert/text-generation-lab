from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9278_continuation_bridge_denoise_probe_audit.py"
    spec = importlib.util.spec_from_file_location("stage9278", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9278_bridge_metrics_detect_remaining_bridge_failure():
    mod = _load()
    audit = mod.audit_run()
    assert audit["passed"] is True
    assert audit["safety_gate_passed"] is True
    assert audit["quality_gate_passed"] is False
    assert audit["generation_prefix_start_rate"] == 1.0
    assert audit["bridge_rows_checked"] == 13
    assert audit["bridge_start_rate"] == 0.0
    assert audit["contentful_generation_rate"] > audit["previous_contentful_generation_rate"]
    assert audit["unterminated_generation_rate"] < audit["previous_unterminated_generation_rate"]
    assert audit["degenerate_repetition_rate"] < audit["previous_degenerate_repetition_rate"]
    assert audit["generated_internal_token_rows"] == 0


def test_stage9278_keeps_forbidden_surfaces_closed():
    mod = _load()
    audit = mod.audit_run()
    assert audit["runtime_executed"] is False
    assert audit["gemma_executed"] is False
    assert audit["harness_executed"] is False
    assert audit["final_checkpoint_exported"] is False
