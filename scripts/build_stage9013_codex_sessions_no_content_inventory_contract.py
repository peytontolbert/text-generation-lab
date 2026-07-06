#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9013
NAME = "stage9013_codex_sessions_no_content_inventory_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CODEX_SESSIONS_NO_CONTENT_INVENTORY_CONTRACT_STAGE9013.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "codex_sessions_no_content_inventory_contract.json"

SOURCE_SUMMARY_CANDIDATES = [
    ROOT / "runs/summaries/stage9012_codex_sessions_multidataset_mining_contract.json",
    ROOT / "runs/local/artifacts/recovered_unregistered_drafts/stage9012_codex_sessions_multidataset_mining_contract/stage9012_codex_sessions_multidataset_mining_contract.summary.json",
]
SOURCE_CONTRACT_CANDIDATES = [
    ROOT / "runs/local/artifacts/stage9012_codex_sessions_multidataset_mining_contract/codex_sessions_multidataset_mining_contract.json",
    ROOT / "runs/local/artifacts/recovered_unregistered_drafts/stage9012_codex_sessions_multidataset_mining_contract/generated_artifacts/codex_sessions_multidataset_mining_contract.json",
]
SOURCE_SUMMARY = next((p for p in SOURCE_SUMMARY_CANDIDATES if p.exists()), SOURCE_SUMMARY_CANDIDATES[0])
SOURCE_CONTRACT = next((p for p in SOURCE_CONTRACT_CANDIDATES if p.exists()), SOURCE_CONTRACT_CANDIDATES[0])

INVENTORY_SCOPE = [
    "expand_source_roots_without_following_symlinks",
    "record_root_exists_boolean",
    "record_file_count_by_extension",
    "record_total_bytes_by_extension",
    "record_mtime_range_by_root",
    "record_relative_path_hashes_only",
    "record_no_message_body_hashes",
    "record_no_tool_output_content",
]

ALLOWED_METADATA_FIELDS = [
    "source_root_label",
    "source_root_exists",
    "relative_path_hash",
    "extension",
    "file_size_bytes",
    "mtime_utc",
    "depth",
]

FORBIDDEN_CONTENT_FIELDS = [
    "message_text",
    "assistant_text",
    "tool_output_text",
    "command_text",
    "patch_text",
    "file_body",
    "session_json_payload",
    "raw_path",
]

REQUIRED_OUTPUTS = [
    "session_inventory_root_card.json",
    "session_inventory_counts_by_root.json",
    "session_inventory_extension_counts.json",
    "session_inventory_relative_path_hashes.jsonl",
    "no_content_read_proof.json",
    "next_session_parser_ticket_input.json",
]

FORBIDDEN_OPERATIONS = [
    "READ_SESSION_FILE_CONTENT_NOW",
    "PARSE_SESSION_JSON_NOW",
    "COPY_SESSION_FILES_NOW",
    "HASH_MESSAGE_BODIES_NOW",
    "WRITE_TO_ARXIV",
    "EMIT_TRAINING_ROWS",
    "TRAIN_MODEL",
    "RUN_MODEL",
    "RUN_RUNTIME",
    "AUTHORIZE_DECODER_CE",
    "AUTHORIZE_DENOISE_CE",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_contract(registry: dict[str, Any]) -> dict[str, Any]:
    source_summary = load_json(SOURCE_SUMMARY)
    source_contract = load_json(SOURCE_CONTRACT)
    checks = {
        "source_stage9012_present": SOURCE_SUMMARY.exists() and SOURCE_CONTRACT.exists(),
        "source_stage9012_passed": source_summary.get("passed") is True,
        "source_stage9012_keeps_mining_closed": (source_summary.get("metrics") or {}).get("session_mining_authorized_now") is False,
        "source_stage9012_has_roots": len(source_contract.get("session_source_roots") or []) >= 3,
        "inventory_scope_recorded": len(INVENTORY_SCOPE) >= 8,
        "allowed_metadata_fields_recorded": len(ALLOWED_METADATA_FIELDS) >= 7,
        "forbidden_content_fields_recorded": len(FORBIDDEN_CONTENT_FIELDS) >= 8,
        "required_outputs_recorded": len(REQUIRED_OUTPUTS) >= 6,
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 11,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "CODEX_SESSIONS_NO_CONTENT_INVENTORY_CONTRACT_NO_READ",
        "session_source_roots": source_contract.get("session_source_roots") or [],
        "inventory_scope": INVENTORY_SCOPE,
        "allowed_metadata_fields": ALLOWED_METADATA_FIELDS,
        "forbidden_content_fields": FORBIDDEN_CONTENT_FIELDS,
        "required_outputs": REQUIRED_OUTPUTS,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "checks": checks,
        "metrics": {
            "inventory_scope_rules": len(INVENTORY_SCOPE),
            "allowed_metadata_fields": len(ALLOWED_METADATA_FIELDS),
            "forbidden_content_fields": len(FORBIDDEN_CONTENT_FIELDS),
            "required_outputs": len(REQUIRED_OUTPUTS),
            "source_roots": len(source_contract.get("session_source_roots") or []),
            "session_inventory_authorized_now": False,
            "session_file_content_read_now": False,
            "session_json_parsed_now": False,
            "session_files_copied_now": False,
            "message_body_hashing_authorized_now": False,
            "training_rows_emitted_now": False,
            "arxiv_write_authorized": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "model_execution_attempted": False,
            "runtime_authorized_flag": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Codex session inventory is specified as a future no-content preflight. This stage records metadata-only scope and forbidden content fields, but does not traverse, parse, copy, mine, or train.",
    }


def validate_contract(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for required in ["relative_path_hash", "file_size_bytes", "mtime_utc"]:
        if required not in card.get("allowed_metadata_fields", []):
            failures.append(f"missing_metadata_field:{required}")
    for forbidden in ["message_text", "tool_output_text", "patch_text", "session_json_payload"]:
        if forbidden not in card.get("forbidden_content_fields", []):
            failures.append(f"missing_forbidden_content:{forbidden}")
    for key in [
        "session_inventory_authorized_now",
        "session_file_content_read_now",
        "session_json_parsed_now",
        "session_files_copied_now",
        "message_body_hashing_authorized_now",
        "training_rows_emitted_now",
        "arxiv_write_authorized",
        "training_authorized",
        "data_mining_authorized",
        "model_execution_attempted",
        "runtime_authorized_flag",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_contract(registry)
    failures = validate_contract(card)
    CONTRACT.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **card["metrics"]},
        "artifacts": {"contract": str(CONTRACT.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "If approved later, instantiate a metadata-only session inventory ticket that records counts and path hashes only. Do not parse session JSON or copy content.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9013 Codex Sessions No-Content Inventory Contract",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage defines a future no-content inventory preflight for Codex sessions. It does not traverse roots, parse JSON, read message bodies, copy files, mine rows, write `/arxiv`, or train.",
        "",
        f"Allowed metadata fields: `{summary['metrics']['allowed_metadata_fields']}`",
        f"Forbidden content fields: `{summary['metrics']['forbidden_content_fields']}`",
        f"Session inventory authorized now: `{summary['metrics']['session_inventory_authorized_now']}`",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))),
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
