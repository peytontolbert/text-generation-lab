#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "legacy_src") not in sys.path:
    sys.path.insert(0, str(ROOT / "legacy_src"))
SUMMARY = ROOT / "runs" / "summaries" / "stage8650_target_config_compatibility_audit.json"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / "stage8650_target_config_compatibility_audit"
TARGET_CONFIG = ROOT / "configs" / "model" / "agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_POINTER = ROOT / "configs" / "tokenizer" / "agentkernel_bpe_1506_recovered_pointer.json"
AGGREGATE_CONTRACT = ROOT / "configs" / "software_maintainer" / "aggregate_structured_curriculum_contract_stage8649.json"
AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = json.loads(TARGET_CONFIG.read_text(encoding="utf-8"))
    token = json.loads(TOKENIZER_POINTER.read_text(encoding="utf-8"))
    aggregate = json.loads(AGGREGATE_CONTRACT.read_text(encoding="utf-8"))
    model_cfg = target["model_config"]
    target_count = int(target["parameter_count"])
    d_model = int(model_cfg.get("d_model", 640))
    d_ff = int(model_cfg.get("d_ff", 2048))
    n_layers = int(model_cfg.get("n_layers", 6))
    vocab_size = int(model_cfg.get("vocab_size", 1506))
    retrieval_head_dim = int(model_cfg.get("retrieval_head_dim", 128))
    agent_intent_labels = int(model_cfg.get("agent_intent_labels", 18))
    agent_controller_dim = int(model_cfg.get("agent_controller_dim", 128))
    scalar_invariant_rank = int(model_cfg.get("scalar_invariant_rank", 32))
    structured_head_dims = {
        "surface_role": 8,
        "repair_surface": 8,
        "action_label": 12,
        "evidence_state": 6,
        "decoder_budget_ok": 2,
        "decode_allowed": 2,
        "build_mode": 5,
        "allowed_import_policy": 4,
        "blocked_import_policy": 4,
        "repo_dependency_policy": 5,
        "action_sequence": 64,
        "file_plan": 64,
        "symbol_binding": 6,
        "edit_localization": 7,
        "patch_operator": 12,
        "verifier_repair": 9,
    }
    embed = vocab_size * d_model * 2
    encoder_layer = (4 * d_model * d_model) + (3 * d_model * d_ff) + (4 * d_model)
    decoder_layer = (8 * d_model * d_model) + (6 * d_model * d_ff) + (8 * d_model)
    norms = 4 * d_model
    retrieval = 2 * d_model * retrieval_head_dim
    policy = 7 * (d_model + 1)
    intent = (d_model + 1) * agent_intent_labels
    controller = (d_model + 1) * agent_controller_dim
    scalar = d_model * scalar_invariant_rank
    structured = sum((d_model + 1) * dim for dim in structured_head_dims.values())
    estimate = int(embed + n_layers * (encoder_layer + decoder_layer) + norms + retrieval + policy + intent + controller + scalar + structured)
    ratio = estimate / target_count
    token_json = Path(token["primary_recovered_paths"]["tokenizer_json"])
    token_config = Path(token["primary_recovered_paths"]["tokenizer_config"])

    errors: list[str] = []
    gates: dict[str, bool] = {
        "target_config_present": TARGET_CONFIG.is_file(),
        "aggregate_contract_passed": bool(aggregate.get("passed")),
        "target_vocab_matches_tokenizer": int(model_cfg.get("vocab_size")) == int(token.get("vocab_size")) == 1506,
        "tokenizer_hash_ok": token_json.is_file() and token_config.is_file() and sha256(token_json) == token["sha256"]["tokenizer_json"] and sha256(token_config) == token["sha256"]["tokenizer_config"],
        "target_d_model_expected": int(model_cfg.get("d_model")) == 640,
        "target_layers_expected": int(model_cfg.get("n_layers")) == 6,
        "target_heads_expected": int(model_cfg.get("n_heads")) == 10,
        "target_rope_expected": float(model_cfg.get("rope_theta")) == 1_000_000.0,
        "target_retrieval_head_expected": int(model_cfg.get("retrieval_head_dim")) == 128,
        "target_policy_heads_enabled": bool(model_cfg.get("agent_policy_heads")) is True,
        "target_intent_labels_expected": int(model_cfg.get("agent_intent_labels")) == 18,
        "parameter_estimate_close": 0.995 <= ratio <= 1.005,
    }
    head_cards: dict[str, Any] = {}
    for field, vocab in aggregate.get("global_label_vocabs", {}).items():
        capacity = int(structured_head_dims.get(field, 0))
        label_count = int(vocab.get("label_count", 0))
        fits = label_count <= capacity
        head_cards[field] = {"label_count": label_count, "target_head_capacity": capacity, "fits": fits}
        if not fits:
            gates[f"head_capacity_{field}"] = False
            errors.append(f"target head capacity too small for {field}: {label_count}>{capacity}")
    for key, value in gates.items():
        if not value and not key.startswith("head_capacity_"):
            errors.append(f"gate failed: {key}")
    card = {
        "stage": 8650,
        "stage_name": "stage8650_target_config_compatibility_audit",
        "passed": not errors,
        "authority": AUTHORITY_CLOSED,
        "model_execution_authorized": False,
        "decoder_ce_training_authorized": False,
        "target_config": str(TARGET_CONFIG.relative_to(ROOT)),
        "tokenizer_pointer": str(TOKENIZER_POINTER.relative_to(ROOT)),
        "aggregate_contract": str(AGGREGATE_CONTRACT.relative_to(ROOT)),
        "metrics": {
            "estimated_parameter_count": estimate,
            "target_parameter_count": target_count,
            "estimate_to_target_ratio": ratio,
            "target_vocab_size": model_cfg.get("vocab_size"),
            "tokenizer_vocab_size": token.get("vocab_size"),
        },
        "head_cards": head_cards,
        "gates": gates,
        "errors": errors,
        "next_best_step": "Add explicit no-destructive-training preflight and then prepare a non-executing structured probe enablement card; no dataset recovery/mining yet.",
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_DIR / "target_config_compatibility_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
