from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9713_symbol_binding_retrieval_test_evidence_execution_audit.py"
    spec = importlib.util.spec_from_file_location("stage9713", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9713_execution_boundary_stayed_closed():
    mod = _load()
    result = mod.load_json(mod.RUN / "execution_result.json")
    deltas = mod.load_json(mod.RUN / "module_delta_norms.json")
    assert result["required_artifacts_written"] is True
    assert result["runtime_executed"] is False
    assert result["gemma_executed"] is False
    assert result["harness_executed"] is False
    assert result["final_checkpoint_exported"] is False
    assert deltas["decoder_delta_norm"] == 0.0


def test_stage9713_improved_but_quality_failed_on_test_and_retrieve():
    mod = _load()
    result = mod.load_json(mod.RUN / "execution_result.json")
    eval_exact = result["eval"]["eval"]["field_exact"]["symbol_binding"]["exact"]
    strict_exact = result["eval"]["strict_eval"]["field_exact"]["symbol_binding"]["exact"]
    assert eval_exact == 0.45454545454545453
    assert strict_exact == 0.4090909090909091
    assert strict_exact < 0.85
    stats = mod.per_label(mod.load_jsonl(mod.RUN / "row_field_logits.jsonl"))
    assert stats["BIND_TEST_TO_SYMBOL"]["exact"] == 0.0
    assert stats["RETRIEVE_MORE"]["exact"] == 0.0
    assert stats["BIND_IMPORT_TO_MODULE"]["exact"] == 1.0
