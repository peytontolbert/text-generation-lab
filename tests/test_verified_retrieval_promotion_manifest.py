import argparse
import importlib.util
import json
from pathlib import Path


def _load_module():
    root = Path(__file__).resolve().parents[1]
    path = root / "legacy_src" / "scripts" / "promote_agentkernel_lite_verified_retrieval_bundle.py"
    spec = importlib.util.spec_from_file_location("promote_agentkernel_lite_verified_retrieval_bundle", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_verified_retrieval_promotion_manifest_rejects_gate_mismatch(tmp_path):
    module = _load_module()
    bundle = tmp_path / "bundle"
    (bundle / "model").mkdir(parents=True)
    (bundle / "tokenizer").mkdir(parents=True)
    _write_json(
        bundle / "agentkernel_lite_encdec_manifest.json",
        {
            "dataset_manifest_path": str(tmp_path / "dataset.json"),
            "model_config": {"d_model": 12, "n_layers": 1, "retrieval_head_dim": 16},
            "model_dir": str(bundle / "model"),
            "parameter_count": 123,
            "tokenizer_dir": str(bundle / "tokenizer"),
        },
    )
    eval_path = tmp_path / "eval.json"
    gate_path = tmp_path / "gate.json"
    stats = {
        "correct_in_exact_key_candidates": 2,
        "correct_missing_from_exact_key_candidates": 0,
        "exact_key_candidate_max": 1,
        "exact_key_candidate_total": 2,
        "queries_with_exact_key_candidate": 2,
        "queries_with_multiple_exact_key_candidates": 0,
        "queries_without_exact_key_candidate": 0,
        "top1_damaged_by_hard_filter": 0,
    }
    _write_json(
        eval_path,
        {
            "answer_top1_accuracy": 1.0,
            "evaluated_pairs": 2,
            "mean_reciprocal_rank": 1.0,
            "operation_gated": True,
            "structured_key_hard_filter": True,
            "structured_key_hard_filter_stats": stats,
            "top1_accuracy": 1.0,
        },
    )
    _write_json(gate_path, {"eval_json": str(tmp_path / "other_eval.json"), "passed": True})
    args = argparse.Namespace(
        bundle_dir=str(bundle),
        bundle_manifest="",
        checkpoint="",
        eval_json=str(eval_path),
        output_json=str(tmp_path / "out.json"),
        training_run_id="test",
        verifier_gate_json=str(gate_path),
    )

    try:
        module.build_manifest(args)
    except RuntimeError as exc:
        assert "gate eval_json does not match" in str(exc)
    else:
        raise AssertionError("expected promotion manifest build to fail")


def test_verified_retrieval_promotion_manifest_records_runtime_contract(tmp_path):
    module = _load_module()
    bundle = tmp_path / "bundle"
    (bundle / "model").mkdir(parents=True)
    (bundle / "tokenizer").mkdir(parents=True)
    _write_json(bundle / "checkpoints" / "latest.json", {"checkpoint_path": str(bundle / "checkpoints" / "step.pt")})
    _write_json(
        bundle / "agentkernel_lite_encdec_manifest.json",
        {
            "dataset_manifest_path": str(tmp_path / "dataset.json"),
            "model_config": {
                "d_model": 12,
                "moe_apply_encoder": True,
                "moe_num_experts": 4,
                "moe_top_k": 1,
                "n_layers": 1,
                "retrieval_head_dim": 16,
                "vocab_size": 848,
            },
            "model_dir": str(bundle / "model"),
            "parameter_count": 25852,
            "tokenizer_dir": str(bundle / "tokenizer"),
        },
    )
    eval_path = tmp_path / "eval.json"
    gate_path = tmp_path / "gate.json"
    stats = {
        "correct_in_exact_key_candidates": 2,
        "correct_missing_from_exact_key_candidates": 0,
        "exact_key_candidate_max": 1,
        "exact_key_candidate_total": 2,
        "neural_top1_masked_by_hard_filter": 1,
        "queries_with_exact_key_candidate": 2,
        "queries_with_multiple_exact_key_candidates": 0,
        "queries_without_exact_key_candidate": 0,
        "top1_damaged_by_hard_filter": 0,
    }
    _write_json(
        eval_path,
        {
            "answer_top1_accuracy": 1.0,
            "evaluated_pairs": 2,
            "mean_reciprocal_rank": 1.0,
            "operation_gated": True,
            "structured_key_hard_filter": True,
            "structured_key_hard_filter_stats": stats,
            "top1_accuracy": 1.0,
            "verified_density": {
                "answer_verified_bits_per_training_token": 0.12,
                "answer_verified_bits_per_million_params": 42.0,
                "exact_verified_bits_per_training_token": 0.12,
                "exact_verified_bits_per_million_params": 42.0,
            },
        },
    )
    _write_json(gate_path, {"eval_json": str(eval_path), "passed": True})
    args = argparse.Namespace(
        bundle_dir=str(bundle),
        bundle_manifest="",
        checkpoint="",
        eval_json=str(eval_path),
        output_json=str(tmp_path / "out.json"),
        training_run_id="test",
        verifier_gate_json=str(gate_path),
    )

    manifest = module.build_manifest(args)

    assert manifest["promotion_status"] == "promoted"
    assert manifest["runtime_contract"]["requires_structured_key_hard_filter"] is True
    assert manifest["metrics"]["answer_top1"] == 1.0
    assert manifest["structured_key_hard_filter_stats"]["top1_damaged_by_hard_filter"] == 0


def test_residual_replay_can_include_eval_only_misses(tmp_path):
    root = Path(__file__).resolve().parents[1]
    path = root / "legacy_src" / "scripts" / "build_retrieval_residual_replay_dataset.py"
    spec = importlib.util.spec_from_file_location("build_retrieval_residual_replay_dataset", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    train_path = tmp_path / "train.jsonl"
    eval_path = tmp_path / "eval.jsonl"
    details_path = tmp_path / "details.jsonl"
    manifest_path = tmp_path / "manifest.json"
    _write_jsonl(train_path, [{"source_id": "train_ok", "source_type": "base", "retrieval_doc_text": "base"}])
    _write_jsonl(
        eval_path,
        [
            {"source_id": "eval_miss", "source_type": "eval", "retrieval_doc_text": "correct"},
            {"source_id": "eval_neighbor", "source_type": "eval", "retrieval_doc_text": "wrong"},
        ],
    )
    _write_jsonl(
        details_path,
        [{"source_id": "eval_miss", "predicted_source_id": "eval_neighbor", "top1": False}],
    )
    _write_json(
        manifest_path,
        {
            "eval_dataset_path": str(eval_path),
            "manifest_path": str(manifest_path),
            "train_dataset_path": str(train_path),
        },
    )
    args = argparse.Namespace(
        dataset_manifest=str(manifest_path),
        details_jsonl=str(details_path),
        include_eval_misses=1,
        include_predicted_near_misses=1,
        mix_original_train=0,
        output_dir=str(tmp_path / "out"),
        repeat_failures=2,
        repeat_near_misses=1,
    )

    manifest = module.build(args)

    assert manifest["missed_eval_source_ids"] == 1
    assert manifest["near_miss_eval_source_ids"] == 1
    assert manifest["train_examples"] == 3
