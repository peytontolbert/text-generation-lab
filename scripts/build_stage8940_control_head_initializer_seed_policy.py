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
STAGE = 8940
NAME = "stage8940_control_head_initializer_seed_policy"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CONTROL_HEAD_INITIALIZER_SEED_POLICY_STAGE8940.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
POLICY = OUT_DIR / "control_head_initializer_seed_policy.json"
POLICY_ROWS = OUT_DIR / "control_head_initializer_policy_rows.jsonl"
SOURCE_ROWS = ROOT / "runs/local/artifacts/stage8918_converter_key_mapping_init_policy_contract/converter_key_mapping_contract_rows.jsonl"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8939_bitnet_layout_decoder_contract.json"

BASE_SEED = 20260706
FORBIDDEN_OPERATIONS = [
    "initialize_module_parameters",
    "sample_random_values",
    "write_initialized_state_dict",
    "load_checkpoint",
    "save_checkpoint",
    "model.forward",
    "train_step",
]
INITIALIZER_RULES = {
    "retrieval_query_head.weight": {"weight_init": "xavier_uniform_future", "bias_init": "none", "fan_policy": "target_shape"},
    "retrieval_doc_head.weight": {"weight_init": "xavier_uniform_future", "bias_init": "none", "fan_policy": "target_shape"},
    "agent_policy_heads.*.weight/bias": {"weight_init": "xavier_uniform_future", "bias_init": "zeros_future", "fan_policy": "per_policy_head_vocab"},
    "agent_intent_head.weight/bias": {"weight_init": "xavier_uniform_future", "bias_init": "zeros_future", "fan_policy": "target_shape"},
    "agent_controller.weight/bias": {"weight_init": "xavier_uniform_future", "bias_init": "zeros_future", "fan_policy": "target_shape"},
    "scalar_invariant.weight": {"weight_init": "xavier_uniform_future", "bias_init": "none", "fan_policy": "target_shape"},
    "structured_heads.*.weight/bias": {"weight_init": "xavier_uniform_future", "bias_init": "zeros_future", "fan_policy": "per_structured_field_vocab"},
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_rows(path: Path = SOURCE_ROWS) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def scoped_seed(target_key: str) -> int:
    digest = hashlib.sha256(f"{BASE_SEED}:{target_key}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def build_policy_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        if row.get("policy") != "target_only_head_initialization_required":
            continue
        target_key = str(row.get("target_key"))
        rule = INITIALIZER_RULES.get(target_key, {"weight_init": "manual_review_required", "bias_init": "manual_review_required", "fan_policy": "unknown"})
        out.append({
            "target_key": target_key,
            "target_shape": row.get("target_shape"),
            "source_artifact": row.get("source_artifact"),
            "source_key": row.get("source_key"),
            "initializer_policy": rule,
            "base_seed": BASE_SEED,
            "scoped_seed": scoped_seed(target_key),
            "seed_algorithm": "sha256(base_seed:target_key) first_u32",
            "initialization_authorized": False,
            "checkpoint_write_authorized": False,
            "model_forward_authorized": False,
            "training_authorized": False,
        })
    return out


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def build_policy(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_rows()
    rows = build_policy_rows(source)
    seeds = [row["scoped_seed"] for row in rows]
    checks = {
        "source_stage8939_passed": load_json(SOURCE_SUMMARY).get("passed") is True,
        "source_policy_rows_exist": len(source) >= 150,
        "expected_target_only_rows": len(rows) == 7,
        "all_initializer_rules_present": all(row["initializer_policy"]["weight_init"] != "manual_review_required" for row in rows),
        "scoped_seeds_unique": len(seeds) == len(set(seeds)),
        "no_initialization_authorized": all(row["initialization_authorized"] is False for row in rows),
        "no_checkpoint_write_authorized": all(row["checkpoint_write_authorized"] is False for row in rows),
        "no_model_forward_authorized": all(row["model_forward_authorized"] is False for row in rows),
        "no_training_authorized": all(row["training_authorized"] is False for row in rows),
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "CONTROL_HEAD_INITIALIZER_SEED_POLICY_METADATA_ONLY",
        "base_seed": BASE_SEED,
        "initializer_rules": INITIALIZER_RULES,
        "policy_rows": rows,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "checks": checks,
        "metrics": {
            "source_rows": len(source),
            "policy_rows": len(rows),
            "unique_scoped_seeds": len(set(seeds)),
            "training_authorized": False,
            "data_mining_authorized": False,
            "runtime_authorized_flag": False,
            "model_execution_authorized_now": False,
            "initialization_authorized": False,
            "checkpoint_load_authorized": False,
            "checkpoint_write_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Control-head initializer seed policy is recovered as metadata only. Future initialization must use scoped deterministic seeds and recorded initializer rules, but no initialization, checkpoint load/write, forward, or training is authorized here.",
    }


def validate_policy(policy: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in policy["checks"].items() if value is not True]
    if any((policy.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8939, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in ["initialization_authorized", "checkpoint_load_authorized", "checkpoint_write_authorized"]:
        if policy["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    policy = build_policy(registry)
    failures = validate_policy(policy, registry)
    rows = policy.pop("policy_rows")
    POLICY.write_text(json.dumps(policy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_jsonl(POLICY_ROWS, rows)
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
        "artifacts": {"policy": str(POLICY.relative_to(ROOT)), "policy_rows": str(POLICY_ROWS.relative_to(ROOT))},
        "decision": policy["decision"],
        "next_best_step": "Recover positional embedding merge/ignore policy or materialization-specific module delta/shape telemetry. Do not initialize heads or write checkpoints.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8940 Control Head Initializer Seed Policy",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage records deterministic future initializer policy for target-only recovered heads. It does not initialize parameters, sample random values, load or write checkpoints, run a model, train, mine data, or execute runtime.",
        "",
        f"Policy rows: `{policy['metrics']['policy_rows']}`",
        f"Unique scoped seeds: `{policy['metrics']['unique_scoped_seeds']}`",
        "",
    ]), encoding="utf-8")
    rows_registry = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows_registry.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": summary["next_best_step"]})
    rows_registry = sorted(rows_registry, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows_registry
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(rows_registry),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8940 Control Head Initializer Seed Policy"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8940 records deterministic future initializer policy for recovered target-only control heads. It assigns scoped per-key seeds and initializer rules but opens no initialization, checkpoint load/write, forward execution, or training authority.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
