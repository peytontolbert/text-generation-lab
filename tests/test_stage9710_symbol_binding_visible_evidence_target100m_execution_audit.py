from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9710_symbol_binding_visible_evidence_target100m_execution_audit.py"
    spec = importlib.util.spec_from_file_location("stage9710", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9710_execution_result_kept_closed_boundary():
    mod = _load()
    result = mod.load_json(mod.RUN / "execution_result.json")
    deltas = mod.load_json(mod.RUN / "module_delta_norms.json")
    assert result["required_artifacts_written"] is True
    assert result["structured_batch_sampler"] == "label_balanced_by_primary_field"
    assert result["native_feature_ablation_rows"] == 44
    assert result["runtime_executed"] is False
    assert result["gemma_executed"] is False
    assert result["harness_executed"] is False
    assert result["final_checkpoint_exported"] is False
    assert deltas["decoder_delta_norm"] == 0.0
    for bucket in ["decoder", "decoder_attention", "decoder_mlp", "embeddings", "lm_head"]:
        assert deltas["delta_norm_by_bucket"].get(bucket, 0.0) == 0.0


def test_stage9710_quality_not_passed_and_failure_is_semantic():
    mod = _load()
    result = mod.load_json(mod.RUN / "execution_result.json")
    eval_exact = result["eval"]["eval"]["field_exact"]["symbol_binding"]["exact"]
    strict_exact = result["eval"]["strict_eval"]["field_exact"]["symbol_binding"]["exact"]
    assert eval_exact == 0.4090909090909091
    assert strict_exact == 0.3181818181818182
    assert eval_exact < 0.85
    assert strict_exact < 0.85
    confusion = mod.confusion_pairs(mod.load_json(mod.RUN / "structured_confusion_matrix.json"))
    assert confusion["BIND_TEST_TO_SYMBOL->ABSTAIN_UNBOUND"] == 5
    assert confusion["RETRIEVE_MORE->BIND_CALL_TO_SYMBOL"] == 14


def test_stage9710_ablation_summary_reads_nested_feature_attribution():
    mod = _load()
    rows = mod.load_jsonl(mod.RUN / "feature_ablation_attribution.jsonl")
    summary = mod.ablation_summary(rows)
    assert summary["rows"] == 44
    assert summary["top_feature_group_counts"]
    assert "graph_evidence" in summary["avg_gold_logit_drop_by_group"]
