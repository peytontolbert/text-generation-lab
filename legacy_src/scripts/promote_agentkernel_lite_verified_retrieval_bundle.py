#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_existing(path_text: str, *, label: str) -> Path:
    path = Path(path_text).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"{label} does not exist: {path}")
    return path


def _latest_checkpoint(bundle_dir: Path) -> str:
    latest_path = bundle_dir / "checkpoints" / "latest.json"
    if latest_path.exists():
        latest = _load_json(latest_path)
        for key in ("checkpoint_path", "path", "checkpoint"):
            value = latest.get(key)
            if value:
                return str(Path(value).expanduser().resolve())
    checkpoints = sorted((bundle_dir / "checkpoints").glob("step_*.pt"))
    return str(checkpoints[-1].resolve()) if checkpoints else ""


def _gate_failures(eval_summary: dict[str, Any], gate_summary: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if not bool(gate_summary.get("passed")):
        failures.append("structured-key verifier gate did not pass")
    if gate_summary.get("eval_json") and Path(str(gate_summary["eval_json"])).resolve() != Path(
        str(eval_summary.get("_eval_json_path", ""))
    ).resolve():
        failures.append("gate eval_json does not match supplied eval summary")
    if float(eval_summary.get("top1_accuracy") or 0.0) < 1.0:
        failures.append("strict hard-filter exact top1 is below 1.0")
    if float(eval_summary.get("answer_top1_accuracy") or 0.0) < 1.0:
        failures.append("strict hard-filter answer top1 is below 1.0")
    if not bool(eval_summary.get("operation_gated")):
        failures.append("eval summary is not operation-gated")
    if not bool(eval_summary.get("structured_key_hard_filter")):
        failures.append("eval summary does not use structured-key hard filter")
    stats = dict(eval_summary.get("structured_key_hard_filter_stats", {}) or {})
    evaluated = int(eval_summary.get("evaluated_pairs") or 0)
    required_stats = {
        "queries_with_exact_key_candidate": evaluated,
        "queries_without_exact_key_candidate": 0,
        "queries_with_multiple_exact_key_candidates": 0,
        "exact_key_candidate_total": evaluated,
        "exact_key_candidate_max": 1,
        "correct_in_exact_key_candidates": evaluated,
        "correct_missing_from_exact_key_candidates": 0,
        "top1_damaged_by_hard_filter": 0,
    }
    for key, expected in required_stats.items():
        actual = int(stats.get(key) or 0)
        if actual != expected:
            failures.append(f"{key}={actual}, expected {expected}")
    return failures


def build_manifest(args: argparse.Namespace) -> dict[str, Any]:
    bundle_dir = _resolve_existing(args.bundle_dir, label="bundle dir")
    bundle_manifest_path = _resolve_existing(
        args.bundle_manifest or str(bundle_dir / "agentkernel_lite_encdec_manifest.json"),
        label="bundle manifest",
    )
    eval_json = _resolve_existing(args.eval_json, label="retrieval eval json")
    gate_json = _resolve_existing(args.verifier_gate_json, label="verifier gate json")

    bundle_manifest = _load_json(bundle_manifest_path)
    eval_summary = _load_json(eval_json)
    eval_summary["_eval_json_path"] = str(eval_json)
    gate_summary = _load_json(gate_json)
    failures = _gate_failures(eval_summary, gate_summary)
    if failures:
        raise RuntimeError("promotion rejected: " + "; ".join(failures))

    model_config = dict(bundle_manifest.get("model_config", {}) or {})
    density = dict(eval_summary.get("verified_density", {}) or {})
    stats = dict(eval_summary.get("structured_key_hard_filter_stats", {}) or {})
    dataset_manifest = eval_summary.get("dataset_manifest") or bundle_manifest.get("dataset_manifest_path") or ""
    manifest = {
        "artifact_kind": "agentkernel_lite_verified_retrieval_export_manifest",
        "model_family": "seq2seq_text",
        "model_stack": "transformer_10",
        "core_version": "agentkernel-model-core@0.1.0",
        "training_run_id": args.training_run_id,
        "created_at_unix": int(time.time()),
        "promotion_status": "promoted",
        "promotion_reason": (
            "strict operation-gated structured-key verifier passed with unique exact-key "
            "candidate coverage and zero hard-filter damage"
        ),
        "bundle_dir": str(bundle_dir),
        "bundle_manifest": str(bundle_manifest_path),
        "checkpoint": args.checkpoint or _latest_checkpoint(bundle_dir),
        "config": str(Path(bundle_manifest.get("model_dir", bundle_dir / "model")).resolve() / "config.json"),
        "tokenizer_or_codec": str(Path(bundle_manifest.get("tokenizer_dir", bundle_dir / "tokenizer")).resolve()),
        "dataset_manifest": str(Path(str(dataset_manifest)).expanduser().resolve()) if dataset_manifest else "",
        "eval_summary": str(eval_json),
        "verifier_gate": str(gate_json),
        "runtime_contract": {
            "retrieval_mode": "neural_embedding_then_operation_key_hard_filter",
            "requires_operation_gating": True,
            "requires_structured_key_hard_filter": True,
            "requires_unique_exact_key_candidate": True,
            "fallback_policy": "reject_promotion_if_key_filter_damages_top1_or_lacks_coverage",
        },
        "metrics": {
            "evaluated_pairs": int(eval_summary.get("evaluated_pairs") or 0),
            "exact_top1": float(eval_summary.get("top1_accuracy") or 0.0),
            "answer_top1": float(eval_summary.get("answer_top1_accuracy") or 0.0),
            "mean_reciprocal_rank": float(eval_summary.get("mean_reciprocal_rank") or 0.0),
            "answer_verified_bits_per_training_token": density.get("answer_verified_bits_per_training_token"),
            "exact_verified_bits_per_training_token": density.get("exact_verified_bits_per_training_token"),
            "answer_verified_bits_per_million_params": density.get("answer_verified_bits_per_million_params"),
            "exact_verified_bits_per_million_params": density.get("exact_verified_bits_per_million_params"),
        },
        "structured_key_hard_filter_stats": stats,
        "model": {
            "parameter_count": bundle_manifest.get("parameter_count"),
            "d_model": model_config.get("d_model"),
            "n_layers": model_config.get("n_layers"),
            "retrieval_head_dim": model_config.get("retrieval_head_dim"),
            "moe_apply_encoder": model_config.get("moe_apply_encoder"),
            "moe_num_experts": model_config.get("moe_num_experts"),
            "moe_top_k": model_config.get("moe_top_k"),
            "vocab_size": model_config.get("vocab_size"),
        },
        "source_artifacts": {
            "model_dir": bundle_manifest.get("model_dir"),
            "browser_bitnet_manifest_path": bundle_manifest.get("browser_bitnet_manifest_path"),
            "details_jsonl": str(eval_json).replace(".json", "_details.jsonl"),
        },
    }
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-dir", required=True)
    parser.add_argument("--bundle-manifest", default="")
    parser.add_argument("--eval-json", required=True)
    parser.add_argument("--verifier-gate-json", required=True)
    parser.add_argument("--training-run-id", default="")
    parser.add_argument("--checkpoint", default="")
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()
    manifest = build_manifest(args)
    output_path = Path(args.output_json).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
