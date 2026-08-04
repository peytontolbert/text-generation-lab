from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_or_run_stage12582_model_capability_rebase.py"


def load_module():
    spec = importlib.util.spec_from_file_location("stage12582", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_emits_exact_transition_capability_request():
    module = load_module()
    summary = module.build()
    assert summary["passed_data_contract"] is True
    request = json.loads(module.REQUEST.read_text())
    config = json.loads(module.CONFIG.read_text())
    assert request["execute_now"] is False
    assert request["training_executed"] is False
    assert request["reviewer_approval_required"] is True
    assert "--execute" in request["exact_execution_command"]
    assert "--approval-file" in request["exact_execution_command"]
    assert config["model"]["initialization_weights_sha256"] == "13bd2cf952d86261593c5044d59018084bdb1675feed57d72b7300fe5d256c88"
    assert config["scorer"]["selected_source"] == "encoder_option_cross_encoder"
    assert config["scorer"]["train_base_model"] is True
    assert config["scorer"]["head_only"] is False
    assert config["sampler"]["name"] == "task_balanced"
    assert config["early_stopping"]["patience_chunks"] == 3


def test_manifests_are_disjoint_and_action_transition_only():
    module = load_module()
    module.build()
    train = module.read_jsonl(module.TRAIN_MANIFEST)
    eval_rows = module.read_jsonl(module.EVAL_MANIFEST)
    strict = module.read_jsonl(module.STRICT_MANIFEST)
    assert (len(train), len(eval_rows), len(strict)) == (5176, 248, 356)
    assert {row["task_type"] for row in train} == module.TASKS
    assert not ({module.root_key(row) for row in train} & {module.root_key(row) for row in eval_rows})
    assert not ({module.root_key(row) for row in train} & {module.root_key(row) for row in strict})
    assert all(row["loss_mask"] == {"decoder_ce": True} for row in train)
    assert all(row["stage12582_objective"].startswith("transition_local") for row in train)


def test_gpu_contract_rejects_any_non_gpu2_mask(monkeypatch):
    module = load_module()
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0,2")
    monkeypatch.setenv("NVIDIA_VISIBLE_DEVICES", "2")
    monkeypatch.setenv("AGENTKERNEL_TRAIN_DEVICE", "cuda:0")
    monkeypatch.setenv("AGENTKERNEL_EVAL_DEVICE", "cuda:0")
    try:
        module.require_gpu2()
    except SystemExit as exc:
        assert "GPU2-only" in str(exc)
    else:
        raise AssertionError("non-exclusive GPU mask was accepted")


def test_training_requires_explicit_review_file(tmp_path, monkeypatch):
    module = load_module()
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "2")
    monkeypatch.setenv("NVIDIA_VISIBLE_DEVICES", "2")
    monkeypatch.setenv("AGENTKERNEL_TRAIN_DEVICE", "cuda:0")
    monkeypatch.setenv("AGENTKERNEL_EVAL_DEVICE", "cuda:0")
    missing = tmp_path / "approval.json"
    try:
        module.execute(missing)
    except SystemExit as exc:
        assert "approval" in str(exc)
    else:
        raise AssertionError("training was not blocked without reviewer approval")


def test_chunk_command_updates_base_and_keeps_preservation():
    module = load_module()
    argv, _, _ = module.trainer_argv(module.INIT_RUNTIME, 1)
    assert "--bounded-choice-train-head-only" not in argv
    assert argv[argv.index("--bounded-choice-aux-source") + 1] == "encoder_option_cross_encoder"
    assert argv[argv.index("--bounded-decoder-train-sampler") + 1] == "task_balanced"
    assert argv[argv.index("--preservation-reference-runtime-model") + 1] == str(module.INIT_RUNTIME)
    assert argv[argv.index("--max-steps") + 1] == "64"
