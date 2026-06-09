#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch


def _load_state(checkpoint: dict) -> tuple[dict, str | None]:
    for key in ("model_state_dict", "state_dict", "model"):
        value = checkpoint.get(key)
        if isinstance(value, dict):
            return value, key
    return checkpoint, None


def _resize_head(weight: torch.Tensor, target_dim: int, mode: str, noise_scale: float, generator: torch.Generator) -> torch.Tensor:
    if weight.ndim != 2:
        raise ValueError(f"expected 2D retrieval head weight, got shape={tuple(weight.shape)}")
    source_dim, d_model = weight.shape
    if source_dim > target_dim:
        return weight[:target_dim].clone()
    if source_dim == target_dim:
        return weight.clone()

    out = weight.new_empty((target_dim, d_model))
    out[:source_dim] = weight
    remaining = target_dim - source_dim
    if mode == "zeros":
        out[source_dim:] = 0
    elif mode == "repeat":
        repeats = weight.repeat((remaining + source_dim - 1) // source_dim, 1)[:remaining]
        out[source_dim:] = repeats
    elif mode == "repeat_noise":
        repeats = weight.repeat((remaining + source_dim - 1) // source_dim, 1)[:remaining]
        noise = torch.randn(repeats.shape, generator=generator, dtype=repeats.dtype) * noise_scale
        out[source_dim:] = repeats + noise.to(device=repeats.device)
    elif mode == "noise":
        std = float(weight.detach().float().std().item()) if weight.numel() else 0.01
        noise = torch.randn((remaining, d_model), generator=generator, dtype=weight.dtype) * (std * noise_scale)
        out[source_dim:] = noise.to(device=weight.device)
    else:
        raise ValueError(f"unknown mode: {mode}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-checkpoint", required=True)
    parser.add_argument("--output-checkpoint", required=True)
    parser.add_argument("--target-head-dim", type=int, required=True)
    parser.add_argument("--mode", choices=("zeros", "repeat", "repeat_noise", "noise"), default="repeat_noise")
    parser.add_argument("--noise-scale", type=float, default=0.01)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()

    input_path = Path(args.input_checkpoint)
    output_path = Path(args.output_checkpoint)
    checkpoint = torch.load(input_path, map_location="cpu")
    state, state_key = _load_state(checkpoint)
    generator = torch.Generator(device="cpu")
    generator.manual_seed(int(args.seed))

    changed: dict[str, dict[str, object]] = {}
    for name in ("retrieval_query_head.weight", "retrieval_doc_head.weight"):
        if name not in state:
            raise KeyError(f"missing {name} in {input_path}")
        old = state[name]
        new = _resize_head(old, int(args.target_head_dim), args.mode, float(args.noise_scale), generator)
        state[name] = new
        changed[name] = {"old_shape": list(old.shape), "new_shape": list(new.shape)}

    if isinstance(checkpoint, dict) and state_key is not None:
        checkpoint[state_key] = state
    else:
        checkpoint = state

    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(checkpoint, output_path)
    summary = {
        "artifact_kind": "retrieval_head_dim_transplant",
        "input_checkpoint": str(input_path),
        "output_checkpoint": str(output_path),
        "target_head_dim": int(args.target_head_dim),
        "mode": args.mode,
        "noise_scale": float(args.noise_scale),
        "seed": int(args.seed),
        "changed": changed,
    }
    summary_path = output_path.with_suffix(output_path.suffix + ".json")
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
