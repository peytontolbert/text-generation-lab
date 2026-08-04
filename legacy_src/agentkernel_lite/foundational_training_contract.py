from __future__ import annotations

import hashlib
import io
import json
import math
import os
import random
import stat
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import torch

SCHEMA = "foundational_code_ce_optimizer_v1"
TOP_LEVEL_KEYS = {
    "schema", "authority", "dataset", "model", "optimizer", "schedule",
    "batching", "precision", "gradients", "evaluation", "checkpoint", "provenance",
}
CHECKPOINT_KEYS = {
    "schema", "model_state", "optimizer_state", "scheduler_state", "sampler_state",
    "python_rng_state", "torch_cpu_rng_state", "torch_cuda_rng_states",
    "completed_microbatches", "pending_accumulation_microbatches", "pending_active_tokens", "optimizer_steps", "train_tokens_seen",
    "best_eval_metric", "best_eval_checkpoint", "provenance",
}
CHECKPOINT_SCHEMA = "foundational_code_ce_checkpoint_v1"
BOUND_SOURCE_TREE_SHA256 = "c69c0709c807f96a3fcd0c1751bd6e814cc04575a1d57849ca434ef802553d0a"
PROVENANCE_KEYS = {
    "dataset_generation_id", "manifest_sha256", "provenance_sha256", "catalog_sha256",
    "tokenizer_json_sha256", "tokenizer_config_sha256", "model_config_sha256",
    "optimizer_contract_sha256", "source_tree_sha256", "initialization_state_sha256",
}


class FoundationalTrainingContractError(ValueError):
    pass


def _open_parent_dirfd(path: Path) -> tuple[int, str]:
    if not path.is_absolute():
        raise FoundationalTrainingContractError("artifact path must be absolute")
    leaf = path.name
    if leaf in {"", ".", ".."}:
        raise FoundationalTrainingContractError("invalid artifact leaf name")
    directory_flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    current_fd = os.open("/", directory_flags)
    try:
        for component in path.parent.parts[1:]:
            if component in {"", ".", ".."}:
                raise FoundationalTrainingContractError("non-canonical artifact parent")
            next_fd = os.open(component, directory_flags, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
        return current_fd, leaf
    except Exception:
        os.close(current_fd)
        raise


def _read_regular_nofollow(path: Path) -> bytes:
    parent_fd, leaf = _open_parent_dirfd(path)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(leaf, flags, dir_fd=parent_fd)
        try:
            metadata = os.fstat(fd)
            if not stat.S_ISREG(metadata.st_mode):
                raise FoundationalTrainingContractError(f"not a regular file: {path}")
            chunks: list[bytes] = []
            while True:
                chunk = os.read(fd, 1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
            return b"".join(chunks)
        finally:
            os.close(fd)
    finally:
        os.close(parent_fd)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def load_recipe(path: Path) -> tuple[dict[str, Any], str]:
    payload = _read_regular_nofollow(path)
    try:
        recipe = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FoundationalTrainingContractError(f"invalid recipe JSON: {exc}") from exc
    validate_recipe(recipe)
    return recipe, sha256_bytes(payload)


def validate_bound_artifacts(recipe: Mapping[str, Any], repo_root: Path) -> dict[str, str]:
    validate_recipe(recipe)
    checks = {
        "model_config_sha256": (repo_root / str(recipe["model"]["config_path"]), recipe["model"]["config_sha256"]),
        "training_data_source_sha256": (repo_root / "legacy_src/agentkernel_lite/training_data.py", recipe["provenance"]["training_data_source_sha256"]),
        "training_loop_source_sha256": (repo_root / "legacy_src/agentkernel_lite/training_loop.py", recipe["provenance"]["training_loop_source_sha256"]),
    }
    actual: dict[str, str] = {}
    for label, (path, expected) in checks.items():
        digest = sha256_bytes(_read_regular_nofollow(path))
        if digest != expected:
            raise FoundationalTrainingContractError(f"bound artifact hash mismatch: {label}")
        actual[label] = digest
    return actual


def validate_instantiated_model(model: torch.nn.Module, recipe: Mapping[str, Any], repo_root: Path) -> str:
    validate_bound_artifacts(recipe, repo_root)
    config_payload = json.loads(_read_regular_nofollow(repo_root / str(recipe["model"]["config_path"])))
    expected_config = config_payload["model_config"]
    model_config = getattr(model, "config", None)
    required_attributes = ("vocab_size", "d_model", "d_ff", "n_layers", "n_heads")
    for attribute in required_attributes:
        if getattr(model_config, attribute, None) != expected_config[attribute]:
            raise FoundationalTrainingContractError(f"instantiated model config mismatch: {attribute}")
    parameter_count = sum(parameter.numel() for parameter in model.parameters())
    if parameter_count != int(config_payload["parameter_count"]):
        raise FoundationalTrainingContractError("instantiated model parameter count mismatch")
    return model_initialization_sha256(model)


def _require_exact_keys(value: Mapping[str, Any], keys: set[str], context: str) -> None:
    if set(value) != keys:
        missing = sorted(keys - set(value))
        extra = sorted(set(value) - keys)
        raise FoundationalTrainingContractError(
            f"{context} schema mismatch; missing={missing}, extra={extra}"
        )


def validate_recipe(recipe: Mapping[str, Any]) -> None:
    _require_exact_keys(recipe, TOP_LEVEL_KEYS, "recipe")
    if recipe["schema"] != SCHEMA:
        raise FoundationalTrainingContractError("unsupported foundational recipe schema")

    authority = recipe["authority"]
    _require_exact_keys(
        authority,
        {"contract_validated", "execution_admitted", "model_authority_required", "training_authority_required"},
        "authority",
    )
    if authority != {
        "contract_validated": True,
        "execution_admitted": False,
        "model_authority_required": True,
        "training_authority_required": True,
    }:
        raise FoundationalTrainingContractError("recipe must remain fail-closed")

    dataset = recipe["dataset"]
    _require_exact_keys(
        dataset,
        {
            "generation_id", "manifest_sha256", "provenance_sha256", "catalog_sha256",
            "train_rows", "eval_rows", "strict_rows_loaded", "train_encoder_tokens",
            "train_decoder_tokens", "eval_encoder_tokens", "eval_decoder_tokens",
        },
        "dataset",
    )
    expected_dataset = {
        "generation_id": "594cbbdc08af0cc409eceda1",
        "manifest_sha256": "3f677fb3d9108632a208b34f9eb98b2ee2a6687b3a401cd5229d653e71ae5994",
        "provenance_sha256": "f5b3c921035ea6d5d77c5f3bc06576be3ea556bc8ea49c4669e69fd28664a5c8",
        "catalog_sha256": "ec8e5eee9bc7cb366ca3c0f844913ca52ee72fecd920be4fdde764b7b3431b09",
        "train_rows": 16000,
        "eval_rows": 2000,
        "strict_rows_loaded": 0,
        "train_encoder_tokens": 12669005,
        "train_decoder_tokens": 892050,
        "eval_encoder_tokens": 1613990,
        "eval_decoder_tokens": 103733,
    }
    if dataset != expected_dataset:
        raise FoundationalTrainingContractError("dataset identity or measured token totals drifted")

    model = recipe["model"]
    _require_exact_keys(
        model,
        {
            "implementation", "config_path", "config_sha256", "trainable_parameters",
            "initialization_policy", "initialization_seed", "initialization_state_sha256_required_before_first_step",
        },
        "model",
    )
    if model["implementation"] != "transformer_recovered_target_baseline":
        raise FoundationalTrainingContractError("unreviewed model implementation")
    if model["config_sha256"] != "dda55307003800072d98070a4f744ebd0f8262c5680fa1b0f74c5724b32f5a77":
        raise FoundationalTrainingContractError("model config hash drifted")
    if model["trainable_parameters"] != "full_model":
        raise FoundationalTrainingContractError("foundational recipe requires full-model training")
    if model["initialization_policy"] != "fresh_seeded" or not isinstance(model["initialization_seed"], int):
        raise FoundationalTrainingContractError("invalid initialization policy")
    if model["initialization_state_sha256_required_before_first_step"] is not True:
        raise FoundationalTrainingContractError("initial state hash must be captured before training")

    optimizer = recipe["optimizer"]
    _require_exact_keys(
        optimizer,
        {
            "type", "learning_rate", "betas", "eps", "weight_decay",
            "decay_rule", "no_decay_rule", "complete_disjoint_partition",
        },
        "optimizer",
    )
    if optimizer != {
        "type": "adamw",
        "learning_rate": 0.0003,
        "betas": [0.9, 0.95],
        "eps": 1e-08,
        "weight_decay": 0.1,
        "decay_rule": "trainable_ndim_ge_2_except_normalization",
        "no_decay_rule": "bias_normalization_or_trainable_ndim_lt_2",
        "complete_disjoint_partition": True,
    }:
        raise FoundationalTrainingContractError("optimizer recipe drifted")

    schedule = recipe["schedule"]
    _require_exact_keys(
        schedule,
        {"unit", "total_train_tokens", "warmup_tokens", "decay", "minimum_learning_rate_ratio"},
        "schedule",
    )
    if schedule["unit"] != "non_padding_decoder_tokens" or schedule["decay"] != "cosine":
        raise FoundationalTrainingContractError("schedule must be decoder-token cosine")
    if not (0 < schedule["warmup_tokens"] < schedule["total_train_tokens"]):
        raise FoundationalTrainingContractError("invalid token schedule bounds")
    if not (0.0 <= schedule["minimum_learning_rate_ratio"] <= 1.0):
        raise FoundationalTrainingContractError("invalid minimum LR ratio")

    batching = recipe["batching"]
    _require_exact_keys(
        batching,
        {
            "micro_batch_size", "gradient_accumulation_steps", "maximum_gradient_accumulation_steps", "target_effective_decoder_tokens",
            "loss_normalization", "sampler", "seed",
        },
        "batching",
    )
    if batching["micro_batch_size"] <= 0 or batching["gradient_accumulation_steps"] <= 0 or batching["maximum_gradient_accumulation_steps"] < batching["gradient_accumulation_steps"] or batching["target_effective_decoder_tokens"] <= 0:
        raise FoundationalTrainingContractError("invalid batch or accumulation size")
    if batching["loss_normalization"] != "sum_over_active_tokens_then_divide_accumulated_active_tokens":
        raise FoundationalTrainingContractError("variable-token loss normalization is required")
    if batching["sampler"] != "deterministic_seeded_epoch_permutation":
        raise FoundationalTrainingContractError("deterministic sampler is required")

    precision = recipe["precision"]
    if precision != {
        "mode": "bf16",
        "device": "cuda:2",
        "autocast": True,
        "gradient_scaler": False,
        "fp32_fallback_requires_separate_contract": True,
    }:
        raise FoundationalTrainingContractError("precision policy drifted")

    gradients = recipe["gradients"]
    if gradients != {"clip_global_norm": 1.0, "reject_nonfinite_loss_or_gradients": True}:
        raise FoundationalTrainingContractError("gradient policy drifted")

    evaluation = recipe["evaluation"]
    if evaluation != {
        "selection_split": "eval",
        "selection_metric": "minimum_token_weighted_decoder_ce",
        "strict_eval_loaded_by_training_process": False,
        "strict_eval_used_for_selection": False,
        "stop_rule": "total_token_budget",
    }:
        raise FoundationalTrainingContractError("evaluation policy must remain eval-only")

    checkpoint = recipe["checkpoint"]
    _require_exact_keys(
        checkpoint,
        {
            "cadence_train_tokens", "atomic_publication", "full_training_state",
            "resume_equivalence_required", "same_directory_temporary", "fsync_file_and_parent",
        },
        "checkpoint",
    )
    if any(
        checkpoint[key] is not True
        for key in (
            "atomic_publication", "full_training_state", "resume_equivalence_required",
            "same_directory_temporary", "fsync_file_and_parent",
        )
    ):
        raise FoundationalTrainingContractError("checkpoint durability contract drifted")

    provenance = recipe["provenance"]
    _require_exact_keys(
        provenance,
        {
            "tokenizer_json_sha256", "tokenizer_config_sha256", "model_config_sha256",
            "training_data_source_sha256", "training_loop_source_sha256",
            "source_tree_hash_required_at_run_admission",
        },
        "provenance",
    )
    if provenance["tokenizer_json_sha256"] != "c268a145d01e26047d7773d9888c13902ab0cbf0e59da333ba2b686fec4ae324":
        raise FoundationalTrainingContractError("tokenizer JSON hash drifted")
    if provenance["tokenizer_config_sha256"] != "0987f58448a3163615eb167d93973fa209d7ccb12dd5c7a35c1e8ab166299be0":
        raise FoundationalTrainingContractError("tokenizer config hash drifted")
    if provenance["model_config_sha256"] != model["config_sha256"]:
        raise FoundationalTrainingContractError("model provenance mismatch")
    if provenance["source_tree_hash_required_at_run_admission"] is not True:
        raise FoundationalTrainingContractError("run admission must bind the final source tree")


def adamw_parameter_groups(
    model: torch.nn.Module,
    recipe: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    validate_recipe(recipe)
    decay: list[torch.nn.Parameter] = []
    no_decay: list[torch.nn.Parameter] = []
    decay_names: list[str] = []
    no_decay_names: list[str] = []
    trainable_names: list[str] = []
    normalization_parameter_ids: set[int] = set()
    for module in model.modules():
        module_class = module.__class__.__name__.lower()
        if isinstance(module, torch.nn.LayerNorm) or module_class.endswith("norm") or module_class.endswith("normalization"):
            normalization_parameter_ids.update(id(parameter) for parameter in module.parameters(recurse=False))
    for name, parameter in model.named_parameters():
        if not parameter.requires_grad:
            continue
        trainable_names.append(name)
        is_normalization_parameter = id(parameter) in normalization_parameter_ids
        if parameter.ndim < 2 or name.endswith(".bias") or is_normalization_parameter:
            no_decay.append(parameter)
            no_decay_names.append(name)
        else:
            decay.append(parameter)
            decay_names.append(name)
    if not trainable_names:
        raise FoundationalTrainingContractError("model has no trainable parameters")
    if set(decay_names) & set(no_decay_names):
        raise FoundationalTrainingContractError("optimizer groups overlap")
    if set(decay_names) | set(no_decay_names) != set(trainable_names):
        raise FoundationalTrainingContractError("optimizer groups are incomplete")
    optimizer = recipe["optimizer"]
    groups = [
        {"params": decay, "weight_decay": float(optimizer["weight_decay"]), "group_name": "decay"},
        {"params": no_decay, "weight_decay": 0.0, "group_name": "no_decay"},
    ]
    return groups, {
        "trainable_parameter_names": trainable_names,
        "decay_parameter_names": decay_names,
        "no_decay_parameter_names": no_decay_names,
        "complete": True,
        "disjoint": True,
    }


def token_lr_multiplier(train_tokens_seen: int, schedule: Mapping[str, Any]) -> float:
    if train_tokens_seen < 0:
        raise FoundationalTrainingContractError("train_tokens_seen cannot be negative")
    warmup = int(schedule["warmup_tokens"])
    total = int(schedule["total_train_tokens"])
    minimum = float(schedule["minimum_learning_rate_ratio"])
    if train_tokens_seen < warmup:
        return float(train_tokens_seen) / float(warmup)
    if train_tokens_seen >= total:
        return minimum
    progress = float(train_tokens_seen - warmup) / float(total - warmup)
    cosine = 0.5 * (1.0 + math.cos(math.pi * progress))
    return minimum + (1.0 - minimum) * cosine


@dataclass
class DeterministicEpochSampler:
    row_count: int
    seed: int
    epoch: int = 0
    cursor: int = 0

    def _permutation(self) -> list[int]:
        values = list(range(self.row_count))
        random.Random(self.seed + self.epoch).shuffle(values)
        return values

    def take(self, count: int) -> list[int]:
        if self.row_count <= 0 or count < 0:
            raise FoundationalTrainingContractError("invalid sampler dimensions")
        result: list[int] = []
        while len(result) < count:
            permutation = self._permutation()
            available = self.row_count - self.cursor
            taking = min(count - len(result), available)
            result.extend(permutation[self.cursor:self.cursor + taking])
            self.cursor += taking
            if self.cursor == self.row_count:
                self.epoch += 1
                self.cursor = 0
        return result

    def state_dict(self) -> dict[str, int]:
        return {"row_count": self.row_count, "seed": self.seed, "epoch": self.epoch, "cursor": self.cursor}

    @classmethod
    def from_state_dict(cls, state: Mapping[str, Any]) -> "DeterministicEpochSampler":
        if set(state) != {"row_count", "seed", "epoch", "cursor"}:
            raise FoundationalTrainingContractError("invalid sampler state schema")
        sampler = cls(**{key: int(value) for key, value in state.items()})
        if sampler.row_count <= 0 or sampler.epoch < 0 or not (0 <= sampler.cursor < sampler.row_count):
            raise FoundationalTrainingContractError("invalid sampler state values")
        return sampler


def build_adamw(model: torch.nn.Module, recipe: Mapping[str, Any]) -> tuple[torch.optim.AdamW, dict[str, Any]]:
    groups, audit = adamw_parameter_groups(model, recipe)
    config = recipe["optimizer"]
    optimizer = torch.optim.AdamW(
        groups,
        lr=float(config["learning_rate"]),
        betas=tuple(float(value) for value in config["betas"]),
        eps=float(config["eps"]),
    )
    return optimizer, audit


class TokenCosineScheduler:
    def __init__(self, optimizer: torch.optim.Optimizer, schedule: Mapping[str, Any]) -> None:
        self.optimizer = optimizer
        self.schedule = dict(schedule)
        self.train_tokens_seen = 0
        self.base_learning_rates = [float(group["lr"]) for group in optimizer.param_groups]
        self._apply()

    def _apply(self) -> None:
        multiplier = token_lr_multiplier(self.train_tokens_seen, self.schedule)
        for group, base in zip(self.optimizer.param_groups, self.base_learning_rates):
            group["lr"] = base * multiplier

    def step_tokens(self, active_tokens: int) -> None:
        if active_tokens <= 0:
            raise FoundationalTrainingContractError("scheduler requires positive active tokens")
        self.train_tokens_seen += int(active_tokens)
        self._apply()

    def state_dict(self) -> dict[str, Any]:
        return {"train_tokens_seen": self.train_tokens_seen, "base_learning_rates": self.base_learning_rates}

    def load_state_dict(self, state: Mapping[str, Any]) -> None:
        if set(state) != {"train_tokens_seen", "base_learning_rates"}:
            raise FoundationalTrainingContractError("invalid scheduler state")
        rates = state["base_learning_rates"]
        if not isinstance(rates, list) or len(rates) != len(self.optimizer.param_groups):
            raise FoundationalTrainingContractError("scheduler base LR count mismatch")
        self.train_tokens_seen = int(state["train_tokens_seen"])
        self.base_learning_rates = [float(value) for value in rates]
        self._apply()



@dataclass
class TokenAccumulationController:
    minimum_microbatches: int
    target_active_tokens: int
    maximum_microbatches: int
    completed_microbatches: int = 0
    active_tokens: int = 0

    def add(self, active_tokens: int) -> None:
        if active_tokens <= 0:
            raise FoundationalTrainingContractError("microbatch requires positive active tokens")
        self.completed_microbatches += 1
        self.active_tokens += int(active_tokens)
        if self.completed_microbatches > self.maximum_microbatches:
            raise FoundationalTrainingContractError("maximum accumulation microbatches exceeded")


    def ready(self) -> bool:
        return self.completed_microbatches >= self.minimum_microbatches and self.active_tokens >= self.target_active_tokens

    def reset(self) -> None:
        self.completed_microbatches = 0
        self.active_tokens = 0


def backward_active_token_sum(loss_sum: torch.Tensor, active_tokens: int, controller: TokenAccumulationController) -> None:
    if loss_sum.ndim != 0 or not torch.isfinite(loss_sum):
        raise FoundationalTrainingContractError("nonfinite or nonscalar token-sum loss")
    loss_sum.backward()
    controller.add(active_tokens)


def finalize_accumulated_step(
    model: torch.nn.Module,
    optimizer: torch.optim.Optimizer,
    scheduler: TokenCosineScheduler,
    controller: TokenAccumulationController,
    *,
    clip_global_norm: float,
) -> float:
    if not controller.ready():
        raise FoundationalTrainingContractError("token accumulation target has not been reached")
    for parameter in model.parameters():
        if parameter.grad is not None:
            parameter.grad.div_(float(controller.active_tokens))
            if not torch.isfinite(parameter.grad).all():
                raise FoundationalTrainingContractError("nonfinite accumulated gradient")
    norm = float(torch.nn.utils.clip_grad_norm_(model.parameters(), float(clip_global_norm)))
    if not math.isfinite(norm):
        raise FoundationalTrainingContractError("nonfinite gradient norm")
    active_tokens = controller.active_tokens
    optimizer.step()
    optimizer.zero_grad(set_to_none=True)
    scheduler.step_tokens(active_tokens)
    controller.reset()
    return norm



@dataclass
class EvalCheckpointSelector:
    best_metric: float | None = None
    best_checkpoint: str | None = None

    def consider(self, *, split: str, token_weighted_decoder_ce: float, checkpoint: str) -> bool:
        if split != "eval":
            raise FoundationalTrainingContractError("only eval may select foundational checkpoints")
        if not math.isfinite(token_weighted_decoder_ce):
            raise FoundationalTrainingContractError("eval metric must be finite")
        if self.best_metric is None or token_weighted_decoder_ce < self.best_metric:
            self.best_metric = float(token_weighted_decoder_ce)
            self.best_checkpoint = str(checkpoint)
            return True
        return False


def restore_checkpoint_state(
    payload: Mapping[str, Any],
    *,
    model: torch.nn.Module,
    optimizer: torch.optim.Optimizer,
    scheduler: TokenCosineScheduler,
) -> DeterministicEpochSampler:
    validate_checkpoint_payload(payload)
    model.load_state_dict(payload["model_state"], strict=True)
    optimizer.load_state_dict(payload["optimizer_state"])
    scheduler.load_state_dict(payload["scheduler_state"])
    random.setstate(payload["python_rng_state"])
    torch.set_rng_state(payload["torch_cpu_rng_state"])
    if torch.cuda.is_available():
        torch.cuda.set_rng_state_all(payload["torch_cuda_rng_states"])
    return DeterministicEpochSampler.from_state_dict(payload["sampler_state"])


def bound_source_tree_sha256(recipe: Mapping[str, Any]) -> str:
    validate_recipe(recipe)
    identity = {
        "manifest": recipe["dataset"]["manifest_sha256"],
        "provenance": recipe["dataset"]["provenance_sha256"],
        "catalog": recipe["dataset"]["catalog_sha256"],
        "tokenizer_json": recipe["provenance"]["tokenizer_json_sha256"],
        "tokenizer_config": recipe["provenance"]["tokenizer_config_sha256"],
        "model_config": recipe["model"]["config_sha256"],
        "training_data": recipe["provenance"]["training_data_source_sha256"],
        "training_loop": recipe["provenance"]["training_loop_source_sha256"],
    }
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("ascii")
    return sha256_bytes(encoded)


def model_initialization_sha256(model: torch.nn.Module) -> str:
    buffer = io.BytesIO()
    torch.save({name: tensor.detach().cpu() for name, tensor in sorted(model.state_dict().items())}, buffer)
    return sha256_bytes(buffer.getvalue())


def foundational_bf16_autocast(recipe: Mapping[str, Any], model: torch.nn.Module):
    validate_recipe(recipe)
    if not torch.cuda.is_available() or torch.cuda.device_count() <= 2:
        raise FoundationalTrainingContractError("foundational bf16 contract requires CUDA device 2")
    model_devices = {parameter.device for parameter in model.parameters()}
    if model_devices != {torch.device("cuda:2")}:
        raise FoundationalTrainingContractError("all model parameters must be on CUDA device 2")
    with torch.cuda.device(2):
        if not torch.cuda.is_bf16_supported():
            raise FoundationalTrainingContractError("CUDA device 2 does not support bf16")
    return torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=True)


def build_checkpoint_payload(
    *,
    model_state: Mapping[str, Any],
    optimizer_state: Mapping[str, Any],
    scheduler_state: Mapping[str, Any],
    sampler_state: Mapping[str, Any],
    completed_microbatches: int,
    pending_accumulation_microbatches: int,
    pending_active_tokens: int,
    optimizer_steps: int,
    train_tokens_seen: int,
    best_eval_metric: float | None,
    best_eval_checkpoint: str | None,
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    payload = {
        "schema": CHECKPOINT_SCHEMA,
        "model_state": dict(model_state),
        "optimizer_state": dict(optimizer_state),
        "scheduler_state": dict(scheduler_state),
        "sampler_state": dict(sampler_state),
        "python_rng_state": random.getstate(),
        "torch_cpu_rng_state": torch.get_rng_state(),
        "torch_cuda_rng_states": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else [],
        "completed_microbatches": int(completed_microbatches),
        "pending_accumulation_microbatches": int(pending_accumulation_microbatches),
        "pending_active_tokens": int(pending_active_tokens),
        "optimizer_steps": int(optimizer_steps),
        "train_tokens_seen": int(train_tokens_seen),
        "best_eval_metric": best_eval_metric,
        "best_eval_checkpoint": best_eval_checkpoint,
        "provenance": dict(provenance),
    }
    validate_checkpoint_payload(payload)
    return payload


def validate_checkpoint_payload(payload: Mapping[str, Any], expected_provenance: Mapping[str, Any] | None = None) -> None:
    _require_exact_keys(payload, CHECKPOINT_KEYS, "checkpoint")
    if payload["schema"] != CHECKPOINT_SCHEMA:
        raise FoundationalTrainingContractError("unsupported checkpoint schema")
    for key in ("completed_microbatches", "pending_accumulation_microbatches", "pending_active_tokens", "optimizer_steps", "train_tokens_seen"):
        if not isinstance(payload[key], int) or payload[key] < 0:
            raise FoundationalTrainingContractError(f"invalid checkpoint counter: {key}")
    if payload["pending_accumulation_microbatches"] != 0 or payload["pending_active_tokens"] != 0:
        raise FoundationalTrainingContractError("checkpoints are allowed only at clean optimizer-step boundaries")
    model_state = payload["model_state"]
    if not isinstance(model_state, Mapping) or not model_state or any(not isinstance(value, torch.Tensor) for value in model_state.values()):
        raise FoundationalTrainingContractError("checkpoint model state must contain tensors")
    optimizer_state = payload["optimizer_state"]
    if not isinstance(optimizer_state, Mapping) or set(optimizer_state) != {"state", "param_groups"} or not optimizer_state["param_groups"]:
        raise FoundationalTrainingContractError("checkpoint optimizer state is incomplete")
    scheduler_state = payload["scheduler_state"]
    if not isinstance(scheduler_state, Mapping) or set(scheduler_state) != {"train_tokens_seen", "base_learning_rates"}:
        raise FoundationalTrainingContractError("checkpoint scheduler state is incomplete")
    scheduler_tokens = scheduler_state["train_tokens_seen"]
    if not isinstance(scheduler_tokens, int) or scheduler_tokens < 0 or scheduler_tokens != payload["train_tokens_seen"]:
        raise FoundationalTrainingContractError("scheduler and checkpoint token counters disagree")
    if payload["completed_microbatches"] < payload["optimizer_steps"]:
        raise FoundationalTrainingContractError("microbatch counter cannot trail optimizer steps")
    if (payload["best_eval_metric"] is None) != (payload["best_eval_checkpoint"] is None):
        raise FoundationalTrainingContractError("best eval metric and checkpoint must be set together")
    if not isinstance(payload["torch_cpu_rng_state"], torch.Tensor):
        raise FoundationalTrainingContractError("checkpoint CPU RNG state is invalid")
    if not isinstance(payload["torch_cuda_rng_states"], list) or any(not isinstance(value, torch.Tensor) for value in payload["torch_cuda_rng_states"]):
        raise FoundationalTrainingContractError("checkpoint CUDA RNG states are invalid")
    if payload["best_eval_metric"] is not None and not isinstance(payload["best_eval_metric"], (int, float)):
        raise FoundationalTrainingContractError("checkpoint best eval metric is invalid")
    if payload["best_eval_checkpoint"] is not None and not isinstance(payload["best_eval_checkpoint"], str):
        raise FoundationalTrainingContractError("checkpoint best eval checkpoint is invalid")
    provenance = payload["provenance"]
    if not isinstance(provenance, Mapping):
        raise FoundationalTrainingContractError("checkpoint provenance is invalid")
    _require_exact_keys(provenance, PROVENANCE_KEYS, "checkpoint provenance")
    if provenance["dataset_generation_id"] != "594cbbdc08af0cc409eceda1":
        raise FoundationalTrainingContractError("checkpoint dataset generation mismatch")
    for key in PROVENANCE_KEYS - {"dataset_generation_id"}:
        value = provenance[key]
        if not isinstance(value, str) or len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise FoundationalTrainingContractError(f"checkpoint provenance digest invalid: {key}")
    expected_fixed_provenance = {
        "dataset_generation_id": "594cbbdc08af0cc409eceda1",
        "manifest_sha256": "3f677fb3d9108632a208b34f9eb98b2ee2a6687b3a401cd5229d653e71ae5994",
        "provenance_sha256": "f5b3c921035ea6d5d77c5f3bc06576be3ea556bc8ea49c4669e69fd28664a5c8",
        "catalog_sha256": "ec8e5eee9bc7cb366ca3c0f844913ca52ee72fecd920be4fdde764b7b3431b09",
        "tokenizer_json_sha256": "c268a145d01e26047d7773d9888c13902ab0cbf0e59da333ba2b686fec4ae324",
        "tokenizer_config_sha256": "0987f58448a3163615eb167d93973fa209d7ccb12dd5c7a35c1e8ab166299be0",
        "model_config_sha256": "dda55307003800072d98070a4f744ebd0f8262c5680fa1b0f74c5724b32f5a77",
        "optimizer_contract_sha256": "36d64f5e1448cfe8d3f24ffa9087598b74ecb4a83741520c45a65a489d7b6125",
        "source_tree_sha256": BOUND_SOURCE_TREE_SHA256,
    }
    for key, expected in expected_fixed_provenance.items():
        if provenance[key] != expected:
            raise FoundationalTrainingContractError(f"checkpoint provenance is not bound to canonical artifacts: {key}")
    DeterministicEpochSampler.from_state_dict(payload["sampler_state"])
    if expected_provenance is not None and provenance != dict(expected_provenance):
        raise FoundationalTrainingContractError("checkpoint provenance mismatch")


def publish_checkpoint_atomic(path: Path, payload: Mapping[str, Any]) -> str:
    validate_checkpoint_payload(payload)
    parent_fd, leaf = _open_parent_dirfd(path)
    buffer = io.BytesIO()
    torch.save(dict(payload), buffer)
    data = buffer.getvalue()
    temporary = f".{leaf}.tmp-{uuid.uuid4().hex}"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    temp_created = False
    destination_linked = False
    publication_succeeded = False
    published_identity: tuple[int, int] | None = None
    original_identity: os.stat_result | None = None
    try:
        fd = os.open(temporary, flags, 0o600, dir_fd=parent_fd)
        temp_created = True
        try:
            original_identity = os.fstat(fd)
            offset = 0
            while offset < len(data):
                offset += os.write(fd, data[offset:])
            os.fsync(fd)
        finally:
            os.close(fd)
        check_fd = os.open(temporary, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=parent_fd)
        try:
            current_identity = os.fstat(check_fd)
            expected_identity = (original_identity.st_dev, original_identity.st_ino)
            if (current_identity.st_dev, current_identity.st_ino) != expected_identity:
                raise FoundationalTrainingContractError("checkpoint temporary inode changed before publication")
            if not stat.S_ISREG(current_identity.st_mode):
                raise FoundationalTrainingContractError("checkpoint temporary is not regular")
            os.link(temporary, leaf, src_dir_fd=parent_fd, dst_dir_fd=parent_fd, follow_symlinks=False)
            destination_linked = True
            destination_fd = os.open(leaf, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=parent_fd)
            try:
                destination_identity = os.fstat(destination_fd)
                published_identity = (destination_identity.st_dev, destination_identity.st_ino)
                if published_identity != expected_identity:
                    raise FoundationalTrainingContractError("published checkpoint inode does not match verified temporary")
            finally:
                os.close(destination_fd)
            os.fsync(parent_fd)
        finally:
            os.close(check_fd)
        os.unlink(temporary, dir_fd=parent_fd)
        temp_created = False
        os.fsync(parent_fd)
        publication_succeeded = True
        return sha256_bytes(data)
    finally:
        if destination_linked and not publication_succeeded and published_identity is not None:
            try:
                destination_fd = os.open(leaf, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=parent_fd)
                try:
                    current = os.fstat(destination_fd)
                    if (current.st_dev, current.st_ino) == published_identity:
                        os.unlink(leaf, dir_fd=parent_fd)
                        os.fsync(parent_fd)
                finally:
                    os.close(destination_fd)
            except FileNotFoundError:
                pass
        if temp_created:
            try:
                os.unlink(temporary, dir_fd=parent_fd)
                os.fsync(parent_fd)
            except FileNotFoundError:
                pass
        os.close(parent_fd)


def load_checkpoint(
    path: Path,
    *,
    expected_sha256: str,
    expected_provenance: Mapping[str, Any],
) -> dict[str, Any]:
    data = _read_regular_nofollow(path)
    if sha256_bytes(data) != expected_sha256:
        raise FoundationalTrainingContractError("checkpoint SHA-256 mismatch")
    payload = torch.load(io.BytesIO(data), map_location="cpu", weights_only=True)
    if not isinstance(payload, dict):
        raise FoundationalTrainingContractError("checkpoint payload is not a mapping")
    validate_checkpoint_payload(payload, expected_provenance)
    return payload
