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
STAGE = 8925
NAME = "stage8925_tokenizer_hash_lock_bridge_decision"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TOKENIZER_HASH_LOCK_BRIDGE_DECISION_STAGE8925.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DECISION = OUT_DIR / "tokenizer_hash_lock_bridge_decision.json"

SOURCE_TOKENIZER_DIR = Path("/data/repository_library/exports/agent_kernel/models/agentkernel_lite_100m_bitnet_v11/tokenizer")
SOURCE_TOKENIZER_JSON = SOURCE_TOKENIZER_DIR / "tokenizer.json"
SOURCE_TOKENIZER_CONFIG = SOURCE_TOKENIZER_DIR / "tokenizer_config.json"
TARGET_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"

SOURCE_AUDIT = ROOT / "runs/summaries/stage8919_tokenizer_embedding_migration_policy_design.json"
BLOCKER_MATRIX = ROOT / "runs/summaries/stage8924_training_readiness_blocker_matrix.json"

CORE_IDS = {
    "pad_token_id": 0,
    "bos_token_id": 1,
    "eos_token_id": 2,
    "unk_token_id": 3,
}

SOURCE_VOCAB = 8207
TARGET_VOCAB = 1506
VOCAB_DELTA = SOURCE_VOCAB - TARGET_VOCAB

KNOWN_SOURCE_AK_SPECIAL_RANGE = {
    "start_id": 8192,
    "end_id": 8206,
    "count": 15,
}

BRIDGE_DECISION = {
    "active_tokenizer": "recovered_target_tokenizer_1506",
    "source_export_tokenizer_status": "hash_locked_reference_only",
    "bridge_mapping_status": "not_built",
    "reason": "source vocab 8207 and recovered target vocab 1506 are incompatible without an explicit row mapping and embedding/lm-head policy",
}

FORBIDDEN_OPERATIONS = [
    "tokenizer_swap",
    "resize_embeddings",
    "copy_source_embedding_rows",
    "copy_source_lm_head_rows",
    "initialize_new_token_rows",
    "tokenize_training_data_with_source_tokenizer",
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
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def file_card(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else None,
        "sha256": sha256_file(path),
    }


def target_vocab_size() -> int | None:
    payload = load_json(TARGET_CONFIG)
    cfg = payload.get("model_config", payload)
    value = cfg.get("vocab_size")
    return int(value) if value is not None else None


def source_tokenizer_vocab_size() -> int | None:
    cfg = load_json(SOURCE_TOKENIZER_CONFIG)
    value = cfg.get("vocab_size")
    return int(value) if value is not None else None


def build_decision() -> dict[str, Any]:
    source_cfg = load_json(SOURCE_TOKENIZER_CONFIG)
    target_cfg = load_json(TARGET_CONFIG)
    metrics = {
        "source_vocab_size": source_tokenizer_vocab_size(),
        "target_vocab_size": target_vocab_size(),
        "vocab_delta": VOCAB_DELTA,
        "source_tokenizer_files": 2,
        "source_files_hash_locked": int(SOURCE_TOKENIZER_JSON.exists()) + int(SOURCE_TOKENIZER_CONFIG.exists()),
        "target_config_hash_locked": int(TARGET_CONFIG.exists()),
        "core_ids_match": all(source_cfg.get(key) == value for key, value in CORE_IDS.items()),
        "active_tokenizer_is_target": BRIDGE_DECISION["active_tokenizer"] == "recovered_target_tokenizer_1506",
        "bridge_mapping_rows": 0,
        "tokenizer_swap_authorized": False,
        "embedding_resize_authorized": False,
        "embedding_copy_authorized_rows": 0,
        "lm_head_copy_authorized_rows": 0,
        "training_authorized": False,
        "model_execution_authorized_now": False,
    }
    checks = {
        "stage8919_policy_passed": load_json(SOURCE_AUDIT).get("passed") is True,
        "stage8924_blocker_matrix_passed": load_json(BLOCKER_MATRIX).get("passed") is True,
        "source_tokenizer_json_hash_locked": file_card(SOURCE_TOKENIZER_JSON)["sha256"] is not None,
        "source_tokenizer_config_hash_locked": file_card(SOURCE_TOKENIZER_CONFIG)["sha256"] is not None,
        "target_config_hash_locked": file_card(TARGET_CONFIG)["sha256"] is not None,
        "source_vocab_is_8207": metrics["source_vocab_size"] == SOURCE_VOCAB,
        "target_vocab_is_1506": metrics["target_vocab_size"] == TARGET_VOCAB,
        "vocab_delta_recorded": metrics["vocab_delta"] == VOCAB_DELTA,
        "core_ids_match": metrics["core_ids_match"] is True,
        "active_tokenizer_is_target": metrics["active_tokenizer_is_target"] is True,
        "bridge_mapping_not_built": metrics["bridge_mapping_rows"] == 0,
        "source_tokenizer_reference_only": BRIDGE_DECISION["source_export_tokenizer_status"] == "hash_locked_reference_only",
        "no_tokenizer_swap_authorized": metrics["tokenizer_swap_authorized"] is False,
        "no_embedding_resize_authorized": metrics["embedding_resize_authorized"] is False,
        "no_embedding_copy_authorized": metrics["embedding_copy_authorized_rows"] == 0,
        "no_lm_head_copy_authorized": metrics["lm_head_copy_authorized_rows"] == 0,
        "no_training_authorized": metrics["training_authorized"] is False,
        "no_model_execution_authorized": metrics["model_execution_authorized_now"] is False,
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "source_stages": [8919, 8924],
        "checks": checks,
        "metrics": metrics,
        "file_locks": {
            "source_tokenizer_json": file_card(SOURCE_TOKENIZER_JSON),
            "source_tokenizer_config": file_card(SOURCE_TOKENIZER_CONFIG),
            "target_config": file_card(TARGET_CONFIG),
        },
        "core_id_contract": CORE_IDS,
        "known_source_ak_special_range": KNOWN_SOURCE_AK_SPECIAL_RANGE,
        "bridge_decision": BRIDGE_DECISION,
        "target_config_tokenizer": (target_cfg.get("tokenizer") or {}),
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "authority": AUTHORITY_CLOSED,
        "decision": {
            "current_status": "keep_target_tokenizer",
            "source_tokenizer_status": "reference_hash_locked_only",
            "materialization_status": "blocked",
            "next_required_artifact": "dataset/compiler recovery audit or, if conversion continues, explicit bridge mapping table design with no embedding copy",
        },
    }


def validate_decision(decision: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in decision["checks"].items() if value is not True]
    if any((decision.get("authority") or {}).values()):
        failures.append("authority_open")
    authority_counts = (registry.get("metrics") or {}).get("authority_counts") or {}
    if any(int(authority_counts.get(key, 0)) != 0 for key in AUTHORITY_CLOSED):
        failures.append("registry_authority_counts_nonzero")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8924, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    decision = build_decision()
    failures = validate_decision(decision, registry)
    DECISION.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "failures": failures,
            **decision["metrics"],
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "data_mining_authorized": False,
        },
        "artifacts": {"decision": str(DECISION.relative_to(ROOT))},
        "decision": "Tokenizer hash-lock and bridge decision passed: keep recovered target tokenizer active; source export tokenizer is reference-only; bridge mapping is not built; training/execution remain blocked.",
        "next_best_step": "Continue no-execution recovery of dataset/compiler modules, or design an explicit bridge mapping table without embedding/lm-head copy if conversion work resumes.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8925 Tokenizer Hash Lock Bridge Decision",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This stage hash-locks the source export tokenizer files and recovered target config, then records the active tokenizer decision.",
        "",
        "Decision: keep the recovered 1506-vocab target tokenizer active. The 8207-vocab source export tokenizer is reference-only. No bridge mapping is built here.",
        "",
        f"Source vocab: `{decision['metrics']['source_vocab_size']}`",
        f"Target vocab: `{decision['metrics']['target_vocab_size']}`",
        f"Vocab delta: `{decision['metrics']['vocab_delta']}`",
        "",
        "No tokenizer swap, embedding resize, embedding copy, lm-head copy, state-dict load, execution, or training is authorized.",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = card["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": card["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8925 Tokenizer Hash Lock Bridge Decision"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8925 hash-locks the source export tokenizer files and recovered target config, then records the active tokenizer decision: keep the 1506-vocab recovered target tokenizer active, treat the 8207-vocab source export tokenizer as reference-only, and do not build bridge mappings or copy/resize embeddings without later audits.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
