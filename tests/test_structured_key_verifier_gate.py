import argparse
import importlib.util
from pathlib import Path


def _load_gate_module():
    root = Path(__file__).resolve().parents[1]
    path = root / "legacy_src" / "scripts" / "gate_agentkernel_lite_structured_key_verifier.py"
    spec = importlib.util.spec_from_file_location("gate_agentkernel_lite_structured_key_verifier", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_structured_key_verifier_gate_rejects_ambiguous_candidates():
    module = _load_gate_module()
    result = {
        "answer_top1_accuracy": 1.0,
        "evaluated_pairs": 2,
        "operation_gated": True,
        "structured_key_hard_filter": True,
        "structured_key_hard_filter_stats": {
            "correct_in_exact_key_candidates": 2,
            "correct_missing_from_exact_key_candidates": 0,
            "exact_key_candidate_max": 2,
            "exact_key_candidate_total": 3,
            "queries_with_exact_key_candidate": 2,
            "queries_with_multiple_exact_key_candidates": 1,
            "queries_without_exact_key_candidate": 0,
            "top1_damaged_by_hard_filter": 0,
        },
        "top1_accuracy": 1.0,
    }
    args = argparse.Namespace(min_answer_top1=1.0, min_exact_top1=1.0)

    failures = module._failures(result, args)

    assert any("multiple exact-key candidates" in failure for failure in failures)
    assert any("exact-key candidate total" in failure for failure in failures)
