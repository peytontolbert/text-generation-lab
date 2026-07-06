#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from counterfactual_obligation_audit import audit_rows
from curriculum_compiler import compile_rows
from dataset_junk_ood_ranker_v1 import rank_rows_v1, read_jsonl
from manifest_path_validator import validate_manifest_input_path
from objective_row_judge import judge_row
from shortcut_baseline_audit import audit_shortcuts

AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}

FORBIDDEN_FLAG_NAMES = {
    "mine",
    "train",
    "allow_runtime",
    "allow_decoder_ce",
    "allow_denoise_ce",
    "load_model",
    "write_checkpoint",
    "emit_source_body",
    "gemma",
    "harness",
    "score",
}


def synthetic_rows() -> list[dict[str, Any]]:
    base = {
        "objective_family": "synthetic_compiler_contract",
        "split": "train",
        "gate_status": {
            "source_inventory_lineage": True,
            "source_provenance": True,
            "contamination_leakage_detector": True,
            "golden_locked_eval_suite": True,
            "drift_canary_regression_monitor": True,
            "cluster_slice_near_duplicate_detector": True,
            "dataset_junk_ood_ranker_v1": True,
            "schema_drift_detector": True,
        },
    }
    return [
        {**base, "row_id": "cli_syn_structured", "semantic_key": "cli_g1", "obligation_type": "POSITIVE_ORIGINAL", "encoder": "bounded structured row", "target": "recover action", "decode_allowed": False, "decoder_budget_ok": True},
        {**base, "row_id": "cli_syn_retrieve", "semantic_key": "cli_g1", "obligation_type": "EVIDENCE_REMOVED_OR_RETRIEVE", "encoder": "missing evidence", "target": "retrieve", "missing_evidence": True, "evidence_state": "missing", "decode_allowed": False, "decoder_budget_ok": True},
        {**base, "row_id": "cli_syn_boundary", "semantic_key": "cli_g1", "obligation_type": "CONTRASTIVE_BOUNDARY_SIBLING", "encoder": "long output requested", "target": "x " * 900, "decode_allowed": True, "decoder_budget_ok": False},
    ]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def compile_contract_rows(rows: list[dict[str, Any]], *, output_dir: Path, decoder_token_cap: int, shortcut_ceiling: float, require_recovered_gates: bool) -> dict[str, Any]:
    judged = [judge_row(row, decoder_token_cap=decoder_token_cap) for row in rows]
    ranked_card = rank_rows_v1(rows, max_decoder_tokens=decoder_token_cap)
    ranked = ranked_card["ranked_rows"]
    shortcut = audit_shortcuts(rows, target_field="obligation_type", feature_fields=["decode_allowed", "decoder_budget_ok", "evidence_state"], ceiling=shortcut_ceiling)
    counterfactual = audit_rows(rows)
    buckets, compile_card = compile_rows(ranked, allow_decoder=False, allow_denoise=False, allow_runtime=False, require_recovered_gates=require_recovered_gates)
    patch_queue: list[dict[str, Any]] = []
    if shortcut["training_blocked_by_shortcut_dominance"]:
        patch_queue.append({"reason": "shortcut_dominance", "card": "shortcut_baseline_card.json"})
    if not counterfactual["counterfactual_obligations_complete"]:
        patch_queue.append({"reason": "counterfactual_obligation_missing", "card": "counterfactual_obligation_card.json"})
    audit_card = {
        "rows": len(rows),
        "judged_rows": len(judged),
        "ranked_rows": len(ranked),
        "compiled_rows": sum(len(v) for v in buckets.values()),
        "decoder_ce_loss_rows": compile_card["loss_counts"].get("decoder_ce", 0),
        "denoise_ce_loss_rows": compile_card["loss_counts"].get("denoise_ce", 0),
        "runtime_reward_rows": compile_card["loss_counts"].get("runtime_reward", 0),
        "patch_queue_rows": len(patch_queue),
        "training_authorized": False,
        "data_mining_authorized": False,
        "runtime_authorized": False,
        "authority": dict(AUTHORITY_CLOSED),
    }
    write_jsonl(output_dir / "normalized_input_rows.jsonl", rows)
    write_jsonl(output_dir / "judged_rows.jsonl", judged)
    write_jsonl(output_dir / "ranked_rows.jsonl", ranked)
    write_json(output_dir / "shortcut_baseline_card.json", shortcut)
    write_json(output_dir / "counterfactual_obligation_card.json", counterfactual)
    for objective, objective_rows in buckets.items():
        write_jsonl(output_dir / "objective_manifests" / f"{objective}.jsonl", objective_rows)
    write_json(output_dir / "compile_card.json", compile_card)
    write_jsonl(output_dir / "dataset_patch_queue.jsonl", patch_queue)
    write_json(output_dir / "compiler_audit_card.json", audit_card)
    return audit_card


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="No-mining compiler wrapper for software-maintenance curriculum rows.")
    parser.add_argument("--input", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--mode", choices=["synthetic_dry_run", "manifest_no_mining_audit_only"], required=True)
    parser.add_argument("--decoder-token-cap", type=int, default=768)
    parser.add_argument("--shortcut-ceiling", type=float, default=0.8)
    parser.add_argument("--require-recovered-gates", action="store_true")
    parser.add_argument("--synthetic-only", action="store_true")
    parser.add_argument("--no-decoder-ce", action="store_true", required=True)
    parser.add_argument("--no-denoise-ce", action="store_true", required=True)
    parser.add_argument("--no-runtime", action="store_true", required=True)
    parser.add_argument("--no-mining", action="store_true", required=True)
    parser.add_argument("--no-model-execution", action="store_true", required=True)
    for name in sorted(FORBIDDEN_FLAG_NAMES):
        parser.add_argument(f"--{name.replace('_', '-')}", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    forbidden_enabled = [name for name in FORBIDDEN_FLAG_NAMES if getattr(args, name)]
    if forbidden_enabled:
        raise SystemExit(f"forbidden flags enabled: {', '.join(sorted(forbidden_enabled))}")
    if args.mode == "synthetic_dry_run":
        rows = synthetic_rows()
    else:
        if args.synthetic_only:
            raise SystemExit("--synthetic-only is only valid with synthetic_dry_run")
        if args.input is None:
            raise SystemExit("--input is required for manifest_no_mining_audit_only")
        path_card = validate_manifest_input_path(args.input, must_exist=True)
        if not path_card["allowed"]:
            raise SystemExit("manifest path rejected: " + ", ".join(path_card["failures"]))
        rows = read_jsonl(args.input)
    card = compile_contract_rows(
        rows,
        output_dir=args.output_dir,
        decoder_token_cap=args.decoder_token_cap,
        shortcut_ceiling=args.shortcut_ceiling,
        require_recovered_gates=args.require_recovered_gates,
    )
    print(json.dumps(card, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
