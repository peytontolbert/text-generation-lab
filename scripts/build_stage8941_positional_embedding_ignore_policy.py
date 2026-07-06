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
STAGE = 8941
NAME = "stage8941_positional_embedding_ignore_policy"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "POSITIONAL_EMBEDDING_IGNORE_POLICY_STAGE8941.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
POLICY = OUT_DIR / "positional_embedding_ignore_policy.json"
SOURCE_ROWS = ROOT / "runs/local/artifacts/stage8918_converter_key_mapping_init_policy_contract/converter_key_mapping_contract_rows.jsonl"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8940_control_head_initializer_seed_policy.json"

FORBIDDEN_OPERATIONS = [
    "copy_source_positional_embedding",
    "read_binary_tensor_values",
    "add_target_positional_module",
    "mutate_model_architecture",
    "load_checkpoint",
    "save_checkpoint",
    "model.forward",
    "train_step",
]
REQUIRED_FUTURE_REOPEN_GATES = [
    "target_architecture_declares_learned_encoder_positional_embedding",
    "target_key_exists_in_state_dict_schema",
    "position_length_policy_matches_encoder_max_length",
    "rotary_or_relative_position_conflict_audit",
    "copy_or_interpolate_policy",
    "module_delta_telemetry_guard",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_rows(path: Path = SOURCE_ROWS) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def positional_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("policy") == "source_only_positional_embedding_policy_required"]


def build_policy(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_rows()
    rows = positional_rows(source)
    policy_rows = []
    for row in rows:
        policy_rows.append({
            "source_artifact": row.get("source_artifact"),
            "source_key": row.get("source_key"),
            "source_shape": row.get("source_shape"),
            "target_key": row.get("target_key"),
            "target_shape": row.get("target_shape"),
            "policy": "ignore_source_only_positional_embedding_by_default",
            "reason": "No recovered target key/schema row exists for this learned encoder positional embedding artifact.",
            "copy_authorized": False,
            "architecture_mutation_authorized": False,
            "checkpoint_write_authorized": False,
            "model_forward_authorized": False,
            "training_authorized": False,
        })
    checks = {
        "source_stage8940_passed": load_json(SOURCE_SUMMARY).get("passed") is True,
        "source_rows_exist": len(source) >= 150,
        "exactly_one_positional_source_only_row": len(rows) == 1,
        "positional_row_has_no_target_key": len(rows) == 1 and rows[0].get("target_key") is None,
        "default_policy_is_ignore": len(policy_rows) == 1 and policy_rows[0]["policy"] == "ignore_source_only_positional_embedding_by_default",
        "no_copy_authorized": all(row["copy_authorized"] is False for row in policy_rows),
        "no_architecture_mutation_authorized": all(row["architecture_mutation_authorized"] is False for row in policy_rows),
        "no_checkpoint_write_authorized": all(row["checkpoint_write_authorized"] is False for row in policy_rows),
        "no_training_authorized": all(row["training_authorized"] is False for row in policy_rows),
        "future_reopen_gates_recorded": len(REQUIRED_FUTURE_REOPEN_GATES) >= 6,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "POSITIONAL_EMBEDDING_IGNORE_POLICY_METADATA_ONLY",
        "policy_rows": policy_rows,
        "required_future_reopen_gates": REQUIRED_FUTURE_REOPEN_GATES,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "checks": checks,
        "metrics": {
            "source_rows": len(source),
            "positional_policy_rows": len(policy_rows),
            "training_authorized": False,
            "data_mining_authorized": False,
            "runtime_authorized_flag": False,
            "model_execution_authorized_now": False,
            "positional_copy_authorized": False,
            "architecture_mutation_authorized": False,
            "checkpoint_load_authorized": False,
            "checkpoint_write_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Source-only encoder positional embedding is ignored by default because no recovered target key exists. Copy, architecture mutation, checkpoint load/write, forward, and training remain blocked unless future architecture gates pass.",
    }


def validate_policy(policy: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in policy["checks"].items() if value is not True]
    if any((policy.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8940, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in ["positional_copy_authorized", "architecture_mutation_authorized", "checkpoint_write_authorized"]:
        if policy["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    policy = build_policy(registry)
    failures = validate_policy(policy, registry)
    POLICY.write_text(json.dumps(policy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "failures": failures,
            **policy["metrics"],
        },
        "artifacts": {"policy": str(POLICY.relative_to(ROOT))},
        "decision": policy["decision"],
        "next_best_step": "Recover materialization-specific module delta/shape telemetry and refresh checkpoint precondition matrix. Do not load or write checkpoints.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8941 Positional Embedding Ignore Policy",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage records the default policy for the source-only learned encoder positional embedding artifact: ignore it unless a future architecture audit proves a compatible recovered target key/module exists. It does not copy tensors, mutate architecture, load/write checkpoints, run a model, train, or execute runtime.",
        "",
        f"Policy rows: `{policy['metrics']['positional_policy_rows']}`",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8941 Positional Embedding Ignore Policy"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8941 records the default ignore policy for the source-only learned encoder positional embedding artifact. It opens no tensor copy, architecture mutation, checkpoint load/write, model execution, or training authority.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
