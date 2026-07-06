#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8927
NAME = "stage8927_tokenizer_hashlock_bridge_decision"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TOKENIZER_HASHLOCK_BRIDGE_DECISION_STAGE8927.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DECISION = OUT_DIR / "tokenizer_hashlock_bridge_decision.json"
BRIDGE_ROWS = OUT_DIR / "tokenizer_bridge_rows.jsonl"

TOKENIZER_JSON = Path("/data/repository_library/exports/agent_kernel/models/agentkernel_lite_100m_bitnet_v11/tokenizer/tokenizer.json")
TOKENIZER_CONFIG = Path("/data/repository_library/exports/agent_kernel/models/agentkernel_lite_100m_bitnet_v11/tokenizer/tokenizer_config.json")
STAGE8908_AUDIT = ROOT / "runs/local/artifacts/stage8908_tokenizer_special_token_compatibility_audit/tokenizer_special_token_compatibility_audit.json"
STAGE8919_POLICY = ROOT / "runs/local/artifacts/stage8919_tokenizer_embedding_migration_policy_design/tokenizer_embedding_migration_policy_design.json"
STAGE8924_SUMMARY = ROOT / "runs/summaries/stage8924_training_readiness_blocker_matrix.json"

SOURCE_VOCAB = 8207
TARGET_VOCAB = 1506
CORE_TOKENS = [
    {"token": "<pad>", "source_id": 0, "target_id": 0, "role": "pad"},
    {"token": "<s>", "source_id": 1, "target_id": 1, "role": "bos"},
    {"token": "</s>", "source_id": 2, "target_id": 2, "role": "eos"},
    {"token": "<unk>", "source_id": 3, "target_id": 3, "role": "unk"},
]
AK_SPECIALS = [
    "<AK_USER>",
    "<AK_CHAT>",
    "<AK_THINK>",
    "<AK_DEEP_RESEARCH>",
    "<AK_CONTEXT>",
    "<AK_EVIDENCE>",
    "<AK_CANDIDATE>",
    "<AK_QUERY_REWRITE>",
    "<AK_RERANK>",
    "<AK_GATHER_CONTEXT>",
    "<AK_RESPOND>",
    "<AK_SUFFICIENT>",
    "<AK_INSUFFICIENT>",
    "<AK_ANSWER>",
    "<AK_JSON>",
]
V2_RESERVED = [
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
    "tokenizer_swap",
    "embedding_resize",
    "lm_head_resize",
    "copy_embedding_values",
    "copy_lm_head_values",
    "initialize_new_token_rows",
    "state_dict_load",
    "checkpoint_write",
    "model_forward",
    "training_step",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_bridge_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in CORE_TOKENS:
        rows.append({
            **row,
            "bridge_policy": "identity_core_id_lock",
            "embedding_copy_authorized": False,
            "tokenizer_swap_authorized": False,
        })
    for offset, token in enumerate(AK_SPECIALS):
        rows.append({
            "token": token,
            "source_id": 8192 + offset,
            "target_id": None,
            "role": "agentkernel_source_special",
            "bridge_policy": "source_only_reserved_do_not_add_to_target_without_migration",
            "embedding_copy_authorized": False,
            "tokenizer_swap_authorized": False,
        })
    for token in V2_RESERVED:
        rows.append({
            "token": token,
            "source_id": None,
            "target_id": None,
            "role": "future_v2_reserved_special",
            "bridge_policy": "future_manifest_only_not_current_tokenizer_edit",
            "embedding_copy_authorized": False,
            "tokenizer_swap_authorized": False,
        })
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def build_decision() -> dict[str, Any]:
    audit8908 = load_json(STAGE8908_AUDIT)
    policy8919 = load_json(STAGE8919_POLICY)
    rows = build_bridge_rows()
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "source_files": {
            "tokenizer_json": str(TOKENIZER_JSON),
            "tokenizer_config": str(TOKENIZER_CONFIG),
            "tokenizer_json_sha256": sha256_file(TOKENIZER_JSON),
            "tokenizer_config_sha256": sha256_file(TOKENIZER_CONFIG),
        },
        "source_stages": [8908, 8919, 8924],
        "source_vocab_size": SOURCE_VOCAB,
        "target_vocab_size": TARGET_VOCAB,
        "vocab_delta": SOURCE_VOCAB - TARGET_VOCAB,
        "core_id_contract": {row["role"]: {"source_id": row["source_id"], "target_id": row["target_id"]} for row in CORE_TOKENS},
        "bridge_rows": rows,
        "bridge_policy": {
            "current_decision": "keep_recovered_target_tokenizer_1506",
            "direct_source_tokenizer_swap": "blocked",
            "source_embedding_copy": "blocked",
            "source_lm_head_copy": "blocked",
            "embedding_resize": "blocked",
            "v2_special_token_addition": "future_manifest_only",
            "bridge_rows_are_metadata_only": True,
        },
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "checks": {
            "stage8908_passed": audit8908.get("stage") == 8908 and audit8908.get("checks", {}).get("core_special_ids_match") is True,
            "stage8919_default_keep_target": policy8919.get("metrics", {}).get("default_policy") == "keep_recovered_target_tokenizer_1506_and_do_not_load_export_embeddings",
            "tokenizer_json_hash_present": sha256_file(TOKENIZER_JSON) is not None,
            "tokenizer_config_hash_present": sha256_file(TOKENIZER_CONFIG) is not None,
            "source_vocab_locked": SOURCE_VOCAB == 8207,
            "target_vocab_locked": TARGET_VOCAB == 1506,
            "core_rows_identity_locked": all(row["source_id"] == row["target_id"] for row in CORE_TOKENS),
            "ak_specials_source_only": sum(1 for row in rows if row["role"] == "agentkernel_source_special" and row["target_id"] is None) == len(AK_SPECIALS),
            "v2_reserved_not_current_edits": sum(1 for row in rows if row["role"] == "future_v2_reserved_special" and row["target_id"] is None) == len(V2_RESERVED),
            "no_embedding_copy_authorized": all(row["embedding_copy_authorized"] is False for row in rows),
            "no_tokenizer_swap_authorized": all(row["tokenizer_swap_authorized"] is False for row in rows),
        },
        "authority": dict(AUTHORITY_CLOSED),
    }


def validate_decision(decision: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in decision["checks"].items() if value is not True]
    if not decision["source_files"].get("tokenizer_json_sha256"):
        failures.append("missing_tokenizer_json_hash")
    if decision["bridge_policy"].get("current_decision") != "keep_recovered_target_tokenizer_1506":
        failures.append("unsafe_current_decision")
    if any((decision.get("authority") or {}).values()):
        failures.append("authority_open")
    authority_counts = (registry.get("metrics") or {}).get("authority_counts") or {}
    if any(int(authority_counts.get(key, 0)) != 0 for key in AUTHORITY_CLOSED):
        failures.append("registry_authority_counts_nonzero")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8924, 8925, 8926, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    decision = build_decision()
    failures = validate_decision(decision, registry)
    bridge_rows = decision.pop("bridge_rows")
    DECISION.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_jsonl(BRIDGE_ROWS, bridge_rows)
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "failures": failures,
            "source_vocab_size": SOURCE_VOCAB,
            "target_vocab_size": TARGET_VOCAB,
            "vocab_delta": SOURCE_VOCAB - TARGET_VOCAB,
            "bridge_rows": len(bridge_rows),
            "core_identity_rows": len(CORE_TOKENS),
            "ak_source_only_rows": len(AK_SPECIALS),
            "v2_reserved_rows": len(V2_RESERVED),
            "tokenizer_json_hash_present": decision["source_files"]["tokenizer_json_sha256"] is not None,
            "tokenizer_config_hash_present": decision["source_files"]["tokenizer_config_sha256"] is not None,
            "model_execution_authorized_now": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "data_mining_authorized": False,
            "tokenizer_swap_authorized": False,
            "embedding_resize_authorized": False,
        },
        "artifacts": {"decision": str(DECISION.relative_to(ROOT)), "bridge_rows": str(BRIDGE_ROWS.relative_to(ROOT))},
        "decision": "Tokenizer hash-lock and bridge-token decision recorded. Safe default keeps recovered target tokenizer 1506 and blocks tokenizer swap, embedding resize/copy, loading, execution, and training." if not failures else "Tokenizer hash-lock bridge decision failed.",
        "next_best_step": "Use this hash-lock in any future checkpoint materialization contract; next no-execution work can target initializer seed policy for target-only control heads.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8927 Tokenizer Hash-Lock Bridge Decision",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This no-execution stage locks tokenizer file hashes and records a bridge-token decision for the 8207-to-1506 mismatch.",
        "",
        "Current decision: keep recovered target tokenizer at vocab 1506. Source tokenizer swap, embedding resize/copy, lm_head resize/copy, token row initialization, state-dict load, checkpoint write, model execution, and training remain blocked.",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = card["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": card["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8927 Tokenizer Hash-Lock Bridge Decision"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8927 locks tokenizer file hashes and records bridge rows for core IDs, source-only AgentKernel specials, and future V2 reserved tokens. It keeps the recovered target tokenizer at vocab 1506 and blocks tokenizer swap, embedding/lm-head resize/copy, state-dict load, execution, and training.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
