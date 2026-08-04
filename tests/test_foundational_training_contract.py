from __future__ import annotations

import copy
import random
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "legacy_src"))

import pytest
import torch
from torch import nn

from agentkernel_lite.foundational_training_contract import (
    DeterministicEpochSampler,
    FoundationalTrainingContractError,
    EvalCheckpointSelector,
    TokenAccumulationController,
    TokenCosineScheduler,
    adamw_parameter_groups,
    backward_active_token_sum,
    bound_source_tree_sha256,
    build_adamw,
    build_checkpoint_payload,
    load_checkpoint,
    load_recipe,
    publish_checkpoint_atomic,
    finalize_accumulated_step,
    restore_checkpoint_state,
    validate_bound_artifacts,
    validate_instantiated_model,
    token_lr_multiplier,
    validate_recipe,
)

RECIPE = ROOT / "configs/training/foundational_code_ce_optimizer_v1.json"


class TinyModel(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.embedding = nn.Embedding(16, 8)
        self.norm = nn.LayerNorm(8)
        self.projection = nn.Linear(8, 4)


def recipe() -> dict:
    return load_recipe(RECIPE)[0]


def test_canonical_recipe_is_strict_and_fail_closed() -> None:
    value, digest = load_recipe(RECIPE)
    assert len(digest) == 64
    assert value["authority"]["execution_admitted"] is False
    assert value["dataset"]["strict_rows_loaded"] == 0
    assert value["evaluation"]["strict_eval_loaded_by_training_process"] is False
    assert value["precision"]["device"] == "cuda:2"
    assert value["schedule"]["total_train_tokens"] == 5 * value["dataset"]["train_decoder_tokens"]


@pytest.mark.parametrize(
    ("section", "key", "value"),
    [
        ("authority", "execution_admitted", True),
        ("dataset", "strict_rows_loaded", 1),
        ("evaluation", "selection_split", "strict_eval"),
        ("precision", "device", "cuda:0"),
        ("optimizer", "betas", [0.9, 0.999]),
    ],
)
def test_recipe_tampering_fails_closed(section: str, key: str, value: object) -> None:
    mutated = copy.deepcopy(recipe())
    mutated[section][key] = value
    with pytest.raises(FoundationalTrainingContractError):
        validate_recipe(mutated)


def test_adamw_groups_are_complete_disjoint_and_exclude_norm_bias_from_decay() -> None:
    model = TinyModel()
    groups, audit = adamw_parameter_groups(model, recipe())
    assert audit["complete"] is True and audit["disjoint"] is True
    assert set(audit["decay_parameter_names"]) == {"embedding.weight", "projection.weight"}
    assert set(audit["no_decay_parameter_names"]) == {
        "norm.weight", "norm.bias", "projection.bias"
    }
    assert groups[0]["weight_decay"] == 0.1
    assert groups[1]["weight_decay"] == 0.0


def test_token_cosine_schedule_boundaries() -> None:
    schedule = recipe()["schedule"]
    assert token_lr_multiplier(0, schedule) == 0.0
    assert token_lr_multiplier(schedule["warmup_tokens"], schedule) == pytest.approx(1.0)
    middle = (schedule["warmup_tokens"] + schedule["total_train_tokens"]) // 2
    assert schedule["minimum_learning_rate_ratio"] < token_lr_multiplier(middle, schedule) < 1.0
    assert token_lr_multiplier(schedule["total_train_tokens"], schedule) == schedule["minimum_learning_rate_ratio"]


def test_sampler_resume_is_exact_across_epoch_boundary() -> None:
    uninterrupted = DeterministicEpochSampler(row_count=7, seed=31)
    expected = uninterrupted.take(19)

    first = DeterministicEpochSampler(row_count=7, seed=31)
    prefix = first.take(9)
    resumed = DeterministicEpochSampler.from_state_dict(first.state_dict())
    assert prefix + resumed.take(10) == expected


def test_checkpoint_roundtrip_and_provenance_hash_guards(tmp_path: Path) -> None:
    sampler = DeterministicEpochSampler(row_count=7, seed=31)
    sampler.take(3)
    value, contract_digest = load_recipe(RECIPE)
    provenance = {
        "dataset_generation_id": value["dataset"]["generation_id"],
        "manifest_sha256": value["dataset"]["manifest_sha256"],
        "provenance_sha256": value["dataset"]["provenance_sha256"],
        "catalog_sha256": value["dataset"]["catalog_sha256"],
        "tokenizer_json_sha256": value["provenance"]["tokenizer_json_sha256"],
        "tokenizer_config_sha256": value["provenance"]["tokenizer_config_sha256"],
        "model_config_sha256": value["model"]["config_sha256"],
        "optimizer_contract_sha256": contract_digest,
        "source_tree_sha256": bound_source_tree_sha256(value),
        "initialization_state_sha256": "c" * 64,
    }
    random.seed(17)
    torch.manual_seed(17)
    payload = build_checkpoint_payload(
        model_state={"weight": torch.arange(4)},
        optimizer_state={"state": {}, "param_groups": [{"lr": 0.0003}]},
        scheduler_state={"train_tokens_seen": 123, "base_learning_rates": [0.0003]},
        sampler_state=sampler.state_dict(),
        completed_microbatches=8,
        pending_accumulation_microbatches=0,
        pending_active_tokens=0,
        optimizer_steps=2,
        train_tokens_seen=123,
        best_eval_metric=1.25,
        best_eval_checkpoint="checkpoint-0002.pt",
        provenance=provenance,
    )
    path = tmp_path / "checkpoint.pt"
    digest = publish_checkpoint_atomic(path, payload)
    restored = load_checkpoint(path, expected_sha256=digest, expected_provenance=provenance)
    assert torch.equal(restored["model_state"]["weight"], torch.arange(4))
    assert restored["sampler_state"] == sampler.state_dict()
    assert not list(tmp_path.glob(".*.tmp-*"))

    with pytest.raises(FoundationalTrainingContractError, match="SHA-256"):
        load_checkpoint(path, expected_sha256="0" * 64, expected_provenance=provenance)
    with pytest.raises(FoundationalTrainingContractError, match="provenance"):
        load_checkpoint(
            path,
            expected_sha256=digest,
            expected_provenance={**provenance, "source_tree_sha256": "b" * 64},
        )


def test_recipe_loader_rejects_symlink(tmp_path: Path) -> None:
    link = tmp_path / "recipe.json"
    link.symlink_to(RECIPE)
    with pytest.raises((FoundationalTrainingContractError, OSError)):
        load_recipe(link)


def test_bound_model_and_trainer_artifacts_match_recipe() -> None:
    value = recipe()
    actual = validate_bound_artifacts(value, ROOT)
    assert actual["model_config_sha256"] == value["model"]["config_sha256"]
    assert actual["training_loop_source_sha256"] == value["provenance"]["training_loop_source_sha256"]


def test_build_adamw_consumes_all_recipe_hyperparameters() -> None:
    value = recipe()
    optimizer, audit = build_adamw(TinyModel(), value)
    assert audit["complete"] is True
    assert optimizer.defaults["lr"] == value["optimizer"]["learning_rate"]
    assert optimizer.defaults["betas"] == tuple(value["optimizer"]["betas"])
    assert optimizer.defaults["eps"] == value["optimizer"]["eps"]


def test_token_accumulation_matches_single_batch_update() -> None:
    torch.manual_seed(9)
    full_model = nn.Linear(2, 1, bias=False)
    micro_model = copy.deepcopy(full_model)
    value = recipe()
    full_optimizer, _ = build_adamw(full_model, value)
    micro_optimizer, _ = build_adamw(micro_model, value)
    full_scheduler = TokenCosineScheduler(full_optimizer, value["schedule"])
    micro_scheduler = TokenCosineScheduler(micro_optimizer, value["schedule"])
    warm_state = {
        "train_tokens_seen": value["schedule"]["warmup_tokens"],
        "base_learning_rates": [value["optimizer"]["learning_rate"]] * 2,
    }
    full_scheduler.load_state_dict(warm_state)
    micro_scheduler.load_state_dict(warm_state)
    inputs = torch.tensor([[1.0, 2.0], [2.0, 1.0], [3.0, -1.0], [-1.0, 3.0]])
    targets = torch.tensor([[1.0], [0.5], [-0.5], [1.5]])

    full_controller = TokenAccumulationController(1, 4, 1)
    full_loss_sum = ((full_model(inputs) - targets) ** 2).sum()
    backward_active_token_sum(full_loss_sum, 4, full_controller)
    finalize_accumulated_step(full_model, full_optimizer, full_scheduler, full_controller, clip_global_norm=100.0)

    micro_controller = TokenAccumulationController(2, 4, 2)
    for start in (0, 2):
        micro_loss_sum = ((micro_model(inputs[start:start + 2]) - targets[start:start + 2]) ** 2).sum()
        backward_active_token_sum(micro_loss_sum, 2, micro_controller)
    finalize_accumulated_step(micro_model, micro_optimizer, micro_scheduler, micro_controller, clip_global_norm=100.0)
    assert torch.allclose(full_model.weight, micro_model.weight, atol=1e-7)


def test_eval_selector_rejects_strict_and_selects_minimum() -> None:
    selector = EvalCheckpointSelector()
    assert selector.consider(split="eval", token_weighted_decoder_ce=2.0, checkpoint="a.pt")
    assert not selector.consider(split="eval", token_weighted_decoder_ce=3.0, checkpoint="b.pt")
    assert selector.consider(split="eval", token_weighted_decoder_ce=1.0, checkpoint="c.pt")
    assert selector.best_checkpoint == "c.pt"
    with pytest.raises(FoundationalTrainingContractError, match="only eval"):
        selector.consider(split="strict_eval", token_weighted_decoder_ce=0.1, checkpoint="strict.pt")


def test_checkpoint_publication_refuses_overwrite_and_cleans_temporary(tmp_path: Path) -> None:
    value = recipe()
    provenance = {
        "dataset_generation_id": value["dataset"]["generation_id"],
        "manifest_sha256": value["dataset"]["manifest_sha256"],
        "provenance_sha256": value["dataset"]["provenance_sha256"],
        "catalog_sha256": value["dataset"]["catalog_sha256"],
        "tokenizer_json_sha256": value["provenance"]["tokenizer_json_sha256"],
        "tokenizer_config_sha256": value["provenance"]["tokenizer_config_sha256"],
        "model_config_sha256": value["model"]["config_sha256"],
        "optimizer_contract_sha256": load_recipe(RECIPE)[1],
        "source_tree_sha256": bound_source_tree_sha256(value),
        "initialization_state_sha256": "c" * 64,
    }
    payload = build_checkpoint_payload(
        model_state={"weight": torch.arange(2)},
        optimizer_state={"state": {}, "param_groups": [{"lr": 0.0003}]},
        scheduler_state={"train_tokens_seen": 1, "base_learning_rates": [0.0003]},
        sampler_state=DeterministicEpochSampler(2, 1).state_dict(),
        completed_microbatches=1,
        pending_accumulation_microbatches=0,
        pending_active_tokens=0,
        optimizer_steps=1,
        train_tokens_seen=1,
        best_eval_metric=None,
        best_eval_checkpoint=None,
        provenance=provenance,
    )
    destination = tmp_path / "checkpoint.pt"
    publish_checkpoint_atomic(destination, payload)
    with pytest.raises(FileExistsError):
        publish_checkpoint_atomic(destination, payload)
    assert not list(tmp_path.glob(".*.tmp-*"))


def test_recipe_loader_rejects_symlink_parent(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    target = real / "recipe.json"
    target.write_bytes(RECIPE.read_bytes())
    alias = tmp_path / "alias"
    alias.symlink_to(real, target_is_directory=True)
    with pytest.raises(OSError):
        load_recipe(alias / "recipe.json")


def _complete_provenance() -> dict[str, str]:
    value, contract_digest = load_recipe(RECIPE)
    return {
        "dataset_generation_id": value["dataset"]["generation_id"],
        "manifest_sha256": value["dataset"]["manifest_sha256"],
        "provenance_sha256": value["dataset"]["provenance_sha256"],
        "catalog_sha256": value["dataset"]["catalog_sha256"],
        "tokenizer_json_sha256": value["provenance"]["tokenizer_json_sha256"],
        "tokenizer_config_sha256": value["provenance"]["tokenizer_config_sha256"],
        "model_config_sha256": value["model"]["config_sha256"],
        "optimizer_contract_sha256": contract_digest,
        "source_tree_sha256": bound_source_tree_sha256(value),
        "initialization_state_sha256": "c" * 64,
    }


def test_interrupted_resume_matches_uninterrupted_optimization() -> None:
    value = recipe()
    torch.manual_seed(44)
    initial = nn.Linear(2, 1)
    uninterrupted_model = copy.deepcopy(initial)
    interrupted_model = copy.deepcopy(initial)
    uninterrupted_optimizer, _ = build_adamw(uninterrupted_model, value)
    interrupted_optimizer, _ = build_adamw(interrupted_model, value)
    uninterrupted_scheduler = TokenCosineScheduler(uninterrupted_optimizer, value["schedule"])
    interrupted_scheduler = TokenCosineScheduler(interrupted_optimizer, value["schedule"])
    warm = {
        "train_tokens_seen": value["schedule"]["warmup_tokens"],
        "base_learning_rates": [value["optimizer"]["learning_rate"]] * 2,
    }
    uninterrupted_scheduler.load_state_dict(warm)
    interrupted_scheduler.load_state_dict(warm)
    uninterrupted_sampler = DeterministicEpochSampler(6, 77)
    interrupted_sampler = DeterministicEpochSampler(6, 77)
    inputs = torch.tensor([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0], [2.0, -1.0], [-1.0, 2.0], [0.5, 0.5]])
    targets = torch.tensor([[0.5], [-0.5], [0.0], [1.0], [-1.0], [0.25]])

    def update(model, optimizer, scheduler, sampler):
        indices = sampler.take(2)
        controller = TokenAccumulationController(1, 2, 1)
        loss_sum = ((model(inputs[indices]) - targets[indices]) ** 2).sum()
        backward_active_token_sum(loss_sum, 2, controller)
        finalize_accumulated_step(model, optimizer, scheduler, controller, clip_global_norm=100.0)
        return indices

    assert update(uninterrupted_model, uninterrupted_optimizer, uninterrupted_scheduler, uninterrupted_sampler) == update(
        interrupted_model, interrupted_optimizer, interrupted_scheduler, interrupted_sampler
    )
    payload = build_checkpoint_payload(
        model_state=interrupted_model.state_dict(),
        optimizer_state=interrupted_optimizer.state_dict(),
        scheduler_state=interrupted_scheduler.state_dict(),
        sampler_state=interrupted_sampler.state_dict(),
        completed_microbatches=2,
        pending_accumulation_microbatches=0,
        pending_active_tokens=0,
        optimizer_steps=1,
        train_tokens_seen=interrupted_scheduler.train_tokens_seen,
        best_eval_metric=1.0,
        best_eval_checkpoint="step-1.pt",
        provenance=_complete_provenance(),
    )
    resumed_model = copy.deepcopy(initial)
    resumed_optimizer, _ = build_adamw(resumed_model, value)
    resumed_scheduler = TokenCosineScheduler(resumed_optimizer, value["schedule"])
    resumed_sampler = restore_checkpoint_state(
        payload,
        model=resumed_model,
        optimizer=resumed_optimizer,
        scheduler=resumed_scheduler,
    )

    assert update(uninterrupted_model, uninterrupted_optimizer, uninterrupted_scheduler, uninterrupted_sampler) == update(
        resumed_model, resumed_optimizer, resumed_scheduler, resumed_sampler
    )
    for expected, actual in zip(uninterrupted_model.parameters(), resumed_model.parameters()):
        assert torch.equal(expected, actual)
    assert uninterrupted_scheduler.state_dict() == resumed_scheduler.state_dict()
    assert uninterrupted_sampler.state_dict() == resumed_sampler.state_dict()


def test_checkpoint_link_failure_cleans_temporary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = build_checkpoint_payload(
        model_state={"weight": torch.arange(2)},
        optimizer_state={"state": {}, "param_groups": [{"lr": 0.0003}]},
        scheduler_state={"train_tokens_seen": 1, "base_learning_rates": [0.0003]},
        sampler_state=DeterministicEpochSampler(2, 1).state_dict(),
        completed_microbatches=1,
        pending_accumulation_microbatches=0,
        pending_active_tokens=0,
        optimizer_steps=1,
        train_tokens_seen=1,
        best_eval_metric=None,
        best_eval_checkpoint=None,
        provenance=_complete_provenance(),
    )

    def fail_link(*args, **kwargs):
        raise OSError("injected link failure")

    monkeypatch.setattr("agentkernel_lite.foundational_training_contract.os.link", fail_link)
    with pytest.raises(OSError, match="injected"):
        publish_checkpoint_atomic(tmp_path / "checkpoint.pt", payload)
    assert not list(tmp_path.glob(".*.tmp-*"))
    assert not (tmp_path / "checkpoint.pt").exists()


def test_post_link_fsync_failure_rolls_back_destination(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = build_checkpoint_payload(
        model_state={"weight": torch.arange(2)},
        optimizer_state={"state": {}, "param_groups": [{"lr": 0.0003}]},
        scheduler_state={"train_tokens_seen": 1, "base_learning_rates": [0.0003]},
        sampler_state=DeterministicEpochSampler(2, 1).state_dict(),
        completed_microbatches=1,
        pending_accumulation_microbatches=0,
        pending_active_tokens=0,
        optimizer_steps=1,
        train_tokens_seen=1,
        best_eval_metric=None,
        best_eval_checkpoint=None,
        provenance=_complete_provenance(),
    )
    import agentkernel_lite.foundational_training_contract as module

    real_fsync = module.os.fsync
    calls = 0

    def fail_parent_fsync(fd: int) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected parent fsync failure")
        real_fsync(fd)

    monkeypatch.setattr(module.os, "fsync", fail_parent_fsync)
    destination = tmp_path / "checkpoint.pt"
    with pytest.raises(OSError, match="injected parent"):
        publish_checkpoint_atomic(destination, payload)
    assert not destination.exists()
    assert not list(tmp_path.glob(".*.tmp-*"))


def test_accumulation_cannot_step_before_both_thresholds() -> None:
    model = nn.Linear(2, 1)
    optimizer, _ = build_adamw(model, recipe())
    scheduler = TokenCosineScheduler(optimizer, recipe()["schedule"])
    controller = TokenAccumulationController(2, 4, 4)
    loss = (model(torch.ones(1, 2)) ** 2).sum()
    backward_active_token_sum(loss, 1, controller)
    with pytest.raises(FoundationalTrainingContractError, match="target has not been reached"):
        finalize_accumulated_step(model, optimizer, scheduler, controller, clip_global_norm=1.0)


def test_instantiated_tiny_model_cannot_claim_target_model_authority() -> None:
    with pytest.raises(FoundationalTrainingContractError, match="instantiated model"):
        validate_instantiated_model(TinyModel(), recipe(), ROOT)


def test_checkpoint_rejects_pending_accumulation_state() -> None:
    with pytest.raises(FoundationalTrainingContractError, match="clean optimizer-step boundaries"):
        build_checkpoint_payload(
            model_state={"weight": torch.arange(2)},
            optimizer_state={"state": {}, "param_groups": [{"lr": 0.0003}]},
            scheduler_state={"train_tokens_seen": 1, "base_learning_rates": [0.0003]},
            sampler_state=DeterministicEpochSampler(2, 1).state_dict(),
            completed_microbatches=1,
            pending_accumulation_microbatches=1,
            pending_active_tokens=2,
            optimizer_steps=1,
            train_tokens_seen=1,
            best_eval_metric=None,
            best_eval_checkpoint=None,
            provenance=_complete_provenance(),
        )
