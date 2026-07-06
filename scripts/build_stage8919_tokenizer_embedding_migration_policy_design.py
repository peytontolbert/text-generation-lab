#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8919
NAME = "stage8919_tokenizer_embedding_migration_policy_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TOKENIZER_EMBEDDING_MIGRATION_POLICY_DESIGN_STAGE8919.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
POLICY = OUT_DIR / "tokenizer_embedding_migration_policy_design.json"

TOKENIZER_AUDIT = ROOT / "runs/local/artifacts/stage8908_tokenizer_special_token_compatibility_audit/tokenizer_special_token_compatibility_audit.json"
STAGE8918_SUMMARY = ROOT / "runs/summaries/stage8918_converter_key_mapping_init_policy_contract.json"

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

CORE_ID_CONTRACT = {"pad_token_id": 0, "bos_token_id": 1, "eos_token_id": 2, "unk_token_id": 3}
SOURCE_VOCAB = 8207
TARGET_VOCAB = 1506
VOCAB_DELTA = SOURCE_VOCAB - TARGET_VOCAB
EXPECTED_AK_RANGE = [8192, 8206]

MIGRATION_OPTIONS = [
    {
        "option": "adopt_source_tokenizer_and_resize_recovered_target",
        "status": "blocked_pending_checkpoint_materialization_contract",
        "requires": [
            "explicit_embedding_resize_policy",
            "lm_head_resize_policy",
            "tokenizer_hash_lock",
            "special_token_id_lock",
            "weight_copy_or_init_policy_for_rows_1506_8206",
            "round_trip_tokenization_regression",
        ],
    },
    {
        "option": "keep_recovered_target_tokenizer_1506_and_do_not_load_export_embeddings",
        "status": "safe_metadata_only_default",
        "requires": [
            "do_not_copy_source_embeddings",
            "do_not_copy_lm_head",
            "train_or_initialize_recovered_embeddings_under_future_probe",
        ],
    },
    {
        "option": "build_explicit_bridge_tokenizer",
        "status": "future_v2_design_only",
        "requires": [
            "token_mapping_table",
            "unknown_token_fallback_policy",
            "special_token_migration_manifest",
            "embedding_projection_or_reinitialization_audit",
        ],
    },
]

V2_SPECIAL_TOKEN_GAPS = [
    "<AK_OBSERVE>",
    "<AK_ORIENT>",
    "<AK_ACT>",
    "<AK_VERIFY>",
    "<AK_REPAIR>",
    "<AK_RETRIEVE>",
    "<AK_PATCH>",
    "<AK_TEST>",
    "<AK_ABORT>",
    "<AK_HOLD_LONG_OUTPUT>",
    "<AK_BOUND_DECODER>",
    "<AK_VTR>",
]

FORBIDDEN_OPERATIONS = [
    "resize_embeddings",
    "copy_embedding_values",
    "copy_lm_head_values",
    "initialize_new_token_rows",
    "load_tokenizer_into_training",
    "state_dict_load",
    "checkpoint_write",
    "model_forward",
    "training_step",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_policy() -> dict[str, Any]:
    tokenizer_audit = load_json(TOKENIZER_AUDIT)
    checks_from_audit = tokenizer_audit.get("checks") or {}
    metrics = {
        "source_vocab_size": checks_from_audit.get("export_vocab_size", SOURCE_VOCAB),
        "recovered_target_vocab_size": checks_from_audit.get("recovered_target_vocab_size", TARGET_VOCAB),
        "vocab_delta": VOCAB_DELTA,
        "core_special_ids_match": checks_from_audit.get("core_special_ids_match") is True,
        "ak_special_tokens_present": checks_from_audit.get("ak_special_tokens_present") is True,
        "ak_special_id_start": EXPECTED_AK_RANGE[0],
        "ak_special_id_end": EXPECTED_AK_RANGE[1],
        "v2_special_token_gap_count": len(tokenizer_audit.get("v2_special_token_gaps") or V2_SPECIAL_TOKEN_GAPS),
        "migration_options": len(MIGRATION_OPTIONS),
        "default_policy": "keep_recovered_target_tokenizer_1506_and_do_not_load_export_embeddings",
        "embedding_copy_authorized_rows": 0,
        "lm_head_copy_authorized_rows": 0,
        "embedding_resize_authorized": False,
        "tokenizer_swap_authorized": False,
        "state_dict_load_authorized": False,
    }
    checks = {
        "stage8908_tokenizer_audit_passed": tokenizer_audit.get("stage") == 8908 and checks_from_audit.get("vocab_matches_recovered_target") is False,
        "stage8918_contract_passed": load_json(STAGE8918_SUMMARY).get("passed") is True,
        "source_vocab_is_8207": metrics["source_vocab_size"] == SOURCE_VOCAB,
        "target_vocab_is_1506": metrics["recovered_target_vocab_size"] == TARGET_VOCAB,
        "vocab_delta_recorded": metrics["vocab_delta"] == VOCAB_DELTA,
        "core_special_ids_match": metrics["core_special_ids_match"] is True,
        "ak_special_tokens_present": metrics["ak_special_tokens_present"] is True,
        "v2_tokens_are_future_gaps_not_current_edits": metrics["v2_special_token_gap_count"] == len(V2_SPECIAL_TOKEN_GAPS),
        "default_policy_keeps_target_tokenizer": metrics["default_policy"] == "keep_recovered_target_tokenizer_1506_and_do_not_load_export_embeddings",
        "no_embedding_copy_authorized": metrics["embedding_copy_authorized_rows"] == 0,
        "no_lm_head_copy_authorized": metrics["lm_head_copy_authorized_rows"] == 0,
        "no_embedding_resize_authorized": metrics["embedding_resize_authorized"] is False,
        "no_tokenizer_swap_authorized": metrics["tokenizer_swap_authorized"] is False,
        "no_state_dict_load_authorized": metrics["state_dict_load_authorized"] is False,
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "source_stages": [8908, 8918],
        "checks": checks,
        "metrics": metrics,
        "core_id_contract": CORE_ID_CONTRACT,
        "ak_special_id_range": EXPECTED_AK_RANGE,
        "v2_special_token_gaps": V2_SPECIAL_TOKEN_GAPS,
        "migration_options": MIGRATION_OPTIONS,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "authority": AUTHORITY_CLOSED,
        "decision": {
            "current_policy": "keep recovered target tokenizer at vocab 1506 for now",
            "blocked_policy": "do not copy 8207-row embeddings/lm_head or resize until a future checkpoint materialization contract passes",
            "next_required_artifact": "tokenizer hash lock and bridge-token mapping table design, if future conversion remains desired",
        },
    }


def validate_policy(policy: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in policy["checks"].items() if value is not True]
    authority_counts = (registry.get("metrics") or {}).get("authority_counts") or {}
    if any(authority_counts.get(key, 0) != 0 for key in AUTHORITY_CLOSED):
        failures.append("registry_authority_counts_nonzero")
    latest = (registry.get("metrics") or {}).get("latest_stage")
    if latest not in {8918, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    policy = build_policy()
    failures = validate_policy(policy, registry)
    POLICY.write_text(json.dumps(policy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "failures": failures,
            **policy["metrics"],
            "model_execution_authorized_now": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "data_mining_authorized": False,
            "download_authorized": False,
        },
        "artifacts": {"policy": str(POLICY.relative_to(ROOT))},
        "decision": "Tokenizer/embedding migration policy recorded; export embedding copy, resize, tokenizer swap, loading, execution, and training remain blocked." if not failures else "Tokenizer/embedding migration policy failed.",
        "next_best_step": "Design a checkpoint materialization skeleton that can remain no-op until tokenizer hash, bridge mapping, and embedding/lm-head policies are explicitly authorized.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8919 Tokenizer Embedding Migration Policy Design",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This stage records the metadata-only policy for the 8207-to-1506 tokenizer/vocab mismatch.",
        "",
        "Default policy: keep the recovered target tokenizer at vocab 1506 and do not load/copy source export embeddings or lm_head rows.",
        "",
        "Blocked until future authorization: tokenizer swap, embedding resize, lm_head resize/copy, new token row initialization, state-dict load, checkpoint write, execution, and training.",
        "",
        f"Source vocab: `{policy['metrics']['source_vocab_size']}`",
        f"Recovered target vocab: `{policy['metrics']['recovered_target_vocab_size']}`",
        f"Vocab delta: `{policy['metrics']['vocab_delta']}`",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = card["passed"]
    registry["metrics"] = {**registry.get("metrics", {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": card["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8919 Tokenizer Embedding Migration Policy Design"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + marker + "\n\nStage8919 records the tokenizer/embedding migration policy for the 8207-to-1506 mismatch. The safe default is to keep the recovered target tokenizer and block export embedding/lm-head copy, resize, tokenizer swap, state-dict load, execution, and training until a future materialization contract exists.\n", encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
