from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9275_prefix_copy_denoise_probe_audit.py"
    spec = importlib.util.spec_from_file_location("stage9275", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9275_anchor_prefix_metrics_detect_start_and_contains():
    mod = _load()
    prefixes = mod.prefix_map()
    row_id, prefix = next(iter(prefixes.items()))
    samples = {
        "samples": [
            {"row_id": row_id, "generated_text": prefix + " continued"},
            {"row_id": row_id, "generated_text": "noise " + prefix + " later"},
            {"row_id": row_id, "generated_text": "noise only"},
        ]
    }
    metrics = mod.anchor_prefix_metrics(samples)
    assert metrics["anchor_prefix_rows_checked"] == 3
    assert metrics["anchor_prefix_start_rows"] == 1
    assert metrics["anchor_prefix_contains_rows"] == 2
    assert metrics["anchor_prefix_start_rate"] == 1 / 3
    assert metrics["anchor_prefix_contains_rate"] == 2 / 3
    assert metrics["anchor_prefix_miss_examples"][0]["row_id"] == row_id


def test_stage9275_audit_records_safe_but_quality_failed_probe():
    mod = _load()
    audit = mod.audit_run()
    assert audit["passed"] is True
    assert audit["safety_gate_passed"] is True
    assert audit["quality_gate_passed"] is False
    assert audit["rows"] == 21
    assert audit["target_prefix_match_rate"] == 0.0
    assert audit["anchor_prefix_start_rate"] == 0.0
    assert audit["generated_internal_token_rows"] == 0
    assert audit["runtime_executed"] is False
    assert audit["gemma_executed"] is False
    assert audit["harness_executed"] is False
    assert audit["final_checkpoint_exported"] is False
