#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8918
NAME = "stage8918_converter_key_mapping_init_policy_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CONVERTER_KEY_MAPPING_INIT_POLICY_CONTRACT_STAGE8918.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "converter_key_mapping_init_policy_contract.json"
MAPPING_JSONL = OUT_DIR / "converter_key_mapping_contract_rows.jsonl"

STAGE8916_ROWS = ROOT / "runs/local/artifacts/stage8916_nonexecuting_converter_shape_report_dry_run/shape_report_rows_metadata_only.jsonl"
STAGE8917_SUMMARY = ROOT / "runs/summaries/stage8917_converter_row_completeness_collision_audit.json"

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

EXPECTED_COMPATIBLE_ROWS = 40
EXPECTED_EMBEDDING_MIGRATIONS = 2
EXPECTED_NEW_INIT_ROWS = 7
EXPECTED_BLOCKED_POLICY_ROWS = 119

FORBIDDEN_OPERATIONS = [
    "read_binary_tensor_values",
    "decode_packed_bitnet",
    "torch_load",
    "state_dict_load",
    "embedding_resize",
    "initialize_weights",
    "checkpoint_write",
    "model_forward",
    "training_step",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_rows(path: Path = STAGE8916_ROWS) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_contract_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    contract_rows: list[dict[str, Any]] = []
    for row in rows:
        status = row.get("status")
        if status == "compatible":
            future_action = "rename_copy_after_binary_converter_validation"
            policy = "compatible_dense_metadata_only"
        elif status == "needs_migration":
            future_action = "blocked_until_tokenizer_embedding_migration_contract"
            policy = "embedding_row_resize_policy_required"
        elif status == "new_init_required":
            future_action = "blocked_until_initializer_policy_and_seed_contract"
            policy = "target_only_head_initialization_required"
        elif status == "blocked" and str(row.get("source_artifact") or "").startswith("layers/"):
            future_action = "blocked_until_bitnet_layout_decoder_and_shape_assertions"
            policy = "packed_bitnet_converter_required"
        elif status == "blocked" and row.get("source_artifact") == "dense/enc_pos_embed_weight.f32.bin":
            future_action = "blocked_until_positional_embedding_merge_or_ignore_policy"
            policy = "source_only_positional_embedding_policy_required"
        else:
            future_action = "blocked_until_manual_review"
            policy = "unknown_policy_required"
        contract_rows.append(
            {
                "source_key": row.get("source_key"),
                "target_key": row.get("target_key"),
                "source_artifact": row.get("source_artifact"),
                "source_shape": row.get("source_shape"),
                "target_shape": row.get("target_shape"),
                "source_status": status,
                "policy": policy,
                "future_action": future_action,
                "binary_tensor_values_read": False,
                "load_authorized": False,
                "execution_authorized": False,
                "training_authorized": False,
            }
        )
    return contract_rows


def summarize(contract_rows: list[dict[str, Any]]) -> dict[str, Any]:
    policies = Counter(str(row["policy"]) for row in contract_rows)
    target_keys = [str(row["target_key"]) for row in contract_rows if row.get("target_key")]
    compatible = [row for row in contract_rows if row["policy"] == "compatible_dense_metadata_only"]
    embedding = [row for row in contract_rows if row["policy"] == "embedding_row_resize_policy_required"]
    new_init = [row for row in contract_rows if row["policy"] == "target_only_head_initialization_required"]
    blocked = [row for row in contract_rows if row["future_action"].startswith("blocked_")]
    return {
        "contract_rows": len(contract_rows),
        "compatible_mapping_rows": len(compatible),
        "embedding_migration_policy_rows": len(embedding),
        "new_init_policy_rows": len(new_init),
        "blocked_policy_rows": len(blocked),
        "policy_counts": dict(sorted(policies.items())),
        "target_key_collision_count": sum(1 for count in Counter(target_keys).values() if count > 1),
        "unknown_policy_rows": policies.get("unknown_policy_required", 0),
        "compatible_rows_missing_target": sum(1 for row in compatible if not row.get("target_key")),
        "load_authorized_rows": sum(1 for row in contract_rows if row.get("load_authorized")),
        "execution_authorized_rows": sum(1 for row in contract_rows if row.get("execution_authorized")),
        "training_authorized_rows": sum(1 for row in contract_rows if row.get("training_authorized")),
        "binary_tensor_value_rows": sum(1 for row in contract_rows if row.get("binary_tensor_values_read") is not False),
        "embedding_targets": sorted(str(row.get("target_key")) for row in embedding),
        "new_init_targets": sorted(str(row.get("target_key")) for row in new_init),
    }


def build_contract() -> dict[str, Any]:
    source_rows = load_rows()
    contract_rows = build_contract_rows(source_rows)
    metrics = summarize(contract_rows)
    checks = {
        "stage8917_summary_passed": load_json(STAGE8917_SUMMARY).get("passed") is True,
        "source_shape_report_exists": STAGE8916_ROWS.exists(),
        "expected_compatible_mapping_rows": metrics["compatible_mapping_rows"] == EXPECTED_COMPATIBLE_ROWS,
        "expected_embedding_migration_policy_rows": metrics["embedding_migration_policy_rows"] == EXPECTED_EMBEDDING_MIGRATIONS,
        "expected_new_init_policy_rows": metrics["new_init_policy_rows"] == EXPECTED_NEW_INIT_ROWS,
        "expected_blocked_policy_rows": metrics["blocked_policy_rows"] == EXPECTED_BLOCKED_POLICY_ROWS,
        "no_target_key_collisions": metrics["target_key_collision_count"] == 0,
        "no_unknown_policy_rows": metrics["unknown_policy_rows"] == 0,
        "compatible_rows_have_targets": metrics["compatible_rows_missing_target"] == 0,
        "no_binary_tensor_values_read": metrics["binary_tensor_value_rows"] == 0,
        "no_load_authorized_rows": metrics["load_authorized_rows"] == 0,
        "no_execution_authorized_rows": metrics["execution_authorized_rows"] == 0,
        "no_training_authorized_rows": metrics["training_authorized_rows"] == 0,
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "source_stage": 8917,
        "checks": checks,
        "metrics": metrics,
        "contract_rows": contract_rows,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "authority": AUTHORITY_CLOSED,
        "policy_notes": {
            "compatible_dense_metadata_only": "These rows may become rename/copy candidates only after a future binary converter validates dtype, file size, target shape, and target key.",
            "embedding_row_resize_policy_required": "Encoder/decoder embeddings require a tokenizer migration contract; no resize or copy is authorized here.",
            "target_only_head_initialization_required": "Recovered control heads require an initializer/seed policy; no initialization is performed here.",
            "packed_bitnet_converter_required": "Packed BitNet rows remain blocked until layout decoding, dequantization, and shape assertions are implemented and audited.",
            "source_only_positional_embedding_policy_required": "The browser export has learned encoder positional embeddings but the recovered target does not; merge/ignore policy is required.",
        },
    }


def validate_contract(contract: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in contract["checks"].items() if value is not True]
    authority_counts = (registry.get("metrics") or {}).get("authority_counts") or {}
    if any(authority_counts.get(key, 0) != 0 for key in AUTHORITY_CLOSED):
        failures.append("registry_authority_counts_nonzero")
    latest = (registry.get("metrics") or {}).get("latest_stage")
    if latest not in {8917, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    return failures


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    contract = build_contract()
    failures = validate_contract(contract, registry)
    CONTRACT.write_text(json.dumps({k: v for k, v in contract.items() if k != "contract_rows"}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_jsonl(MAPPING_JSONL, contract["contract_rows"])
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "failures": failures,
            **contract["metrics"],
            "model_execution_authorized_now": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "data_mining_authorized": False,
            "download_authorized": False,
        },
        "artifacts": {
            "contract": str(CONTRACT.relative_to(ROOT)),
            "contract_rows": str(MAPPING_JSONL.relative_to(ROOT)),
        },
        "decision": "Converter key-mapping/init policy contract passed; all loading, initialization, execution, and training remain blocked." if not failures else "Converter key-mapping/init policy contract failed.",
        "next_best_step": "Design a metadata-only tokenizer/embedding migration policy for the 8207-to-1506 vocab mismatch before any converter implementation or checkpoint materialization.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8918 Converter Key Mapping Init Policy Contract",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This stage classifies Stage8916 converter metadata rows into future-compatible mapping, embedding migration, target-only initialization, and blocked converter policies.",
        "",
        "It does not read tensor values, decode packed BitNet weights, load a state dict, resize embeddings, initialize new heads, execute, train, or write checkpoints.",
        "",
        f"Compatible mapping rows: `{contract['metrics']['compatible_mapping_rows']}`",
        f"Embedding migration rows: `{contract['metrics']['embedding_migration_policy_rows']}`",
        f"New-init rows: `{contract['metrics']['new_init_policy_rows']}`",
        f"Blocked policy rows: `{contract['metrics']['blocked_policy_rows']}`",
        "",
        "Next: design a metadata-only tokenizer/embedding migration policy for the 8207-to-1506 vocab mismatch.",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": card["passed"],
        "path": str(SUMMARY),
        "authority": AUTHORITY_CLOSED,
        "next_best_step": card["next_best_step"],
    })
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = card["passed"]
    registry["metrics"] = {
        **registry.get("metrics", {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": card["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8918 Converter Key Mapping Init Policy Contract"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + marker + "\n\nStage8918 classifies converter metadata rows into compatible mapping, embedding migration, target-only initialization, and blocked policies. It preserves the no-load/no-execution/no-training boundary and makes tokenizer/embedding migration the next blocker.\n", encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
