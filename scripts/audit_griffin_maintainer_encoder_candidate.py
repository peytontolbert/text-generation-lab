#!/usr/bin/env python3
"""Audit a dormant Griffin encoder candidate without constructing a model."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/model/agentkernel_100m_griffin_encoder_candidate.json"
DEFAULT_OUTPUT = ROOT / "runs/local/artifacts/griffin_maintainer_encoder_candidate_audit/summary.json"
CURRENT_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
CHECKPOINT_CONFIG = Path("/arxiv/models/recurrentgemma-2b-it/config.json")
CHECKPOINT_INDEX = CHECKPOINT_CONFIG.with_name("model.safetensors.index.json")
MODEL_SOURCE = ROOT / "legacy_src/agentkernel_lite/modeling_transformer.py"
EXPECTED_AUTHORITY_KEYS = {
    "implementation_ready", "level_3_materialized", "model_execution_authorized",
    "replay_trustworthy", "sealed_eval_admitted", "stage12595_allowed",
    "strict_eval_admitted", "training_admitted",
}


class GriffinCandidateAuditError(ValueError):
    """Raised when the static candidate contract is internally inconsistent."""


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise GriffinCandidateAuditError(f"expected JSON object: {path}")
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def current_structured_dims() -> dict[str, int]:
    tree = ast.parse(MODEL_SOURCE.read_text(encoding="utf-8"), filename=str(MODEL_SOURCE))
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "DEFAULT_STRUCTURED_HEAD_DIMS" and node.value is not None:
                value = ast.literal_eval(node.value)
                return {str(name): int(width) for name, width in value.items()}
    raise GriffinCandidateAuditError("DEFAULT_STRUCTURED_HEAD_DIMS not found in live model source")


def current_transformer_counts(payload: dict[str, Any]) -> dict[str, int]:
    cfg = payload["model_config"]
    d = int(cfg["d_model"])
    f = int(cfg["d_ff"])
    layers = int(cfg["n_layers"])
    vocab = int(cfg["vocab_size"])
    retrieval_dim = int(cfg.get("retrieval_head_dim") or 0)
    structured_dims = current_structured_dims()
    encoder_layer = 4 * d * d + 3 * d * f + 4 * d
    decoder_layer = 8 * d * d + 6 * d * f + 8 * d
    embeddings = 2 * vocab * d
    norms = 4 * d
    retrieval = 2 * d * retrieval_dim
    policy = 7 * (d + 1)
    intent = (d + 1) * int(cfg["agent_intent_labels"])
    controller = (d + 1) * int(cfg["agent_controller_dim"])
    scalar = d * int(cfg["scalar_invariant_rank"])
    structured = sum((d + 1) * width for width in structured_dims.values())
    queries = len(structured_dims) * d
    total = embeddings + layers * (encoder_layer + decoder_layer) + norms
    total += retrieval + policy + intent + controller + scalar + structured + queries
    encoder = vocab * d + layers * encoder_layer + 2 * d
    return {"total": total, "encoder": encoder, "retained_non_encoder": total - encoder}


def griffin_encoder_count(
    *, d_model: int, mlp_width: int, lru_width: int, heads: int,
    head_dim: int, kv_heads: int, conv_width: int, recurrent_layers: int,
    attention_layers: int, vocab_size: int,
) -> dict[str, int]:
    if lru_width % heads:
        raise GriffinCandidateAuditError("lru_width must be divisible by num_attention_heads")
    if heads * head_dim != d_model:
        raise GriffinCandidateAuditError("num_attention_heads * head_dim must equal d_model")
    shared_channel_and_norms = 3 * d_model * mlp_width + 2 * mlp_width + 3 * d_model
    recurrent_temporal = (
        3 * d_model * lru_width
        + 2 * lru_width * lru_width // heads
        + (conv_width + 6) * lru_width
        + d_model
    )
    attention_temporal = (
        2 * d_model * d_model
        + 2 * d_model * kv_heads * head_dim
        + d_model
    )
    recurrent_layer = recurrent_temporal + shared_channel_and_norms
    attention_layer = attention_temporal + shared_channel_and_norms
    embedding_and_final_norm = vocab_size * d_model + d_model
    total = (
        embedding_and_final_norm
        + recurrent_layers * recurrent_layer
        + attention_layers * attention_layer
    )
    return {
        "embedding_and_final_norm": embedding_and_final_norm,
        "shared_channel_and_norms_per_layer": shared_channel_and_norms,
        "recurrent_temporal_per_layer": recurrent_temporal,
        "attention_temporal_per_layer": attention_temporal,
        "recurrent_layer": recurrent_layer,
        "attention_layer": attention_layer,
        "total": total,
    }


def audit(candidate: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    architecture = candidate["architecture"]
    schedule = architecture["schedule"]
    recurrent_layers = schedule.count("recurrent")
    attention_layers = schedule.count("attention")
    if schedule != ["recurrent", "recurrent", "attention"] * 2:
        raise GriffinCandidateAuditError("candidate schedule must be (R,R,A)x2")
    if int(architecture["num_layers"]) != len(schedule):
        raise GriffinCandidateAuditError("num_layers must match schedule length")
    authority = candidate.get("authority")
    if not isinstance(authority, dict) or set(authority) != EXPECTED_AUTHORITY_KEYS:
        raise GriffinCandidateAuditError("candidate authority schema mismatch")
    if any(value is not False for value in authority.values()):
        raise GriffinCandidateAuditError("candidate authority must remain closed")

    if int(architecture["d_model"]) != int(current["model_config"]["d_model"]):
        raise GriffinCandidateAuditError("candidate d_model must match retained decoder and heads")

    base = current_transformer_counts(current)
    common = {
        "d_model": int(architecture["d_model"]),
        "heads": int(architecture["num_attention_heads"]),
        "head_dim": int(architecture["head_dim"]),
        "kv_heads": int(architecture["num_key_value_heads"]),
        "conv_width": int(architecture["conv1d_width"]),
        "recurrent_layers": recurrent_layers,
        "attention_layers": attention_layers,
        "vocab_size": int(current["model_config"]["vocab_size"]),
    }
    alternatives: dict[str, Any] = {}
    reference_limit = int(candidate["parameter_audit"]["strict_complete_model_limit"])
    for width in candidate["parameter_audit"]["lru_widths"]:
        counts = griffin_encoder_count(
            mlp_width=int(architecture["effective_mlp_width"]),
            lru_width=int(width),
            **common,
        )
        complete = base["retained_non_encoder"] + counts["total"]
        alternatives[str(width)] = {
            "griffin_encoder_parameters": counts["total"],
            "complete_model_parameters": complete,
            "margin_below_reference_limit": reference_limit - complete,
            "strict_sub_reference_limit": complete < reference_limit,
        }

    selected = str(architecture["lru_width"])
    if selected not in alternatives:
        raise GriffinCandidateAuditError("selected lru_width must be an audited option")
    if int(architecture["hf_intermediate_size"]) // 2 != int(architecture["effective_mlp_width"]):
        raise GriffinCandidateAuditError("HF intermediate_size must encode the requested effective MLP width")
    if int(architecture["effective_mlp_width"]) != 3 * int(architecture["d_model"]):
        raise GriffinCandidateAuditError("candidate must retain a true 3x effective MLP")
    if int(architecture["effective_mlp_expansion"]) != 3:
        raise GriffinCandidateAuditError("effective_mlp_expansion must be 3")

    teacher = candidate.get("teacher")
    expected_checkpoint_dir = str(CHECKPOINT_CONFIG.parent)
    if not isinstance(teacher, dict) or teacher.get("local_checkpoint") != expected_checkpoint_dir:
        raise GriffinCandidateAuditError("teacher checkpoint contract mismatch")
    if teacher.get("counts_toward_100m_parameter_budget") is not False:
        raise GriffinCandidateAuditError("teacher must remain outside the 100M-scale claim")
    if teacher.get("roles") != ["frozen_teacher", "distillation_sidecar"]:
        raise GriffinCandidateAuditError("teacher roles contract mismatch")

    checkpoint: dict[str, Any] = {"path": expected_checkpoint_dir, "available": False}
    if CHECKPOINT_CONFIG.is_file() and CHECKPOINT_INDEX.is_file():
        checkpoint_payload = read_json(CHECKPOINT_CONFIG)
        index_payload = read_json(CHECKPOINT_INDEX)
        weight_map = index_payload.get("weight_map")
        shard_names = sorted(set(weight_map.values())) if isinstance(weight_map, dict) else []
        shard_paths = [CHECKPOINT_CONFIG.parent / name for name in shard_names]
        complete = bool(shard_paths) and all(path.is_file() for path in shard_paths)
        checkpoint.update({
            "available": complete,
            "config_sha256": sha256_file(CHECKPOINT_CONFIG),
            "index_sha256": sha256_file(CHECKPOINT_INDEX),
            "weight_shard_content_identity_bound": False,
            "weight_shards": [{"name": path.name, "size_bytes": path.stat().st_size} for path in shard_paths if path.is_file()],
            "hidden_size": checkpoint_payload.get("hidden_size"),
            "num_hidden_layers": checkpoint_payload.get("num_hidden_layers"),
            "vocab_size": checkpoint_payload.get("vocab_size"),
            "counts_toward_100m_parameter_budget": False,
            "allowed_roles": ["frozen_teacher", "distillation_sidecar"],
        })

    return {
        "schema_version": 1,
        "decision": "STATIC_GRIFFIN_ENCODER_CANDIDATE_READY_RUNTIME_INTEGRATION_BLOCKED",
        "candidate_config_sha256": sha256_json(candidate),
        "current_config_sha256": sha256_json(current),
        "live_model_source_sha256": sha256_file(MODEL_SOURCE),
        "current_model": {
            **base,
            "claimed_total": int(current["parameter_count"]),
            "claim_minus_local_estimator": int(current["parameter_count"]) - base["total"],
        },
        "schedule": {"blocks": schedule, "recurrent_layers": recurrent_layers, "attention_layers": attention_layers},
        "alternatives": alternatives,
        "selected_lru_width": int(selected),
        "selected_complete_model_parameters": alternatives[selected]["complete_model_parameters"],
        "checkpoint": checkpoint,
        "runtime_blockers": candidate["runtime_blockers"],
        "authority": candidate["authority"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    summary = audit(read_json(args.config), read_json(CURRENT_CONFIG))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
