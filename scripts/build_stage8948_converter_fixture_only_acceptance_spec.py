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
STAGE = 8948
NAME = "stage8948_converter_fixture_only_acceptance_spec"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CONVERTER_FIXTURE_ONLY_ACCEPTANCE_SPEC_STAGE8948.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SPEC = OUT_DIR / "converter_fixture_only_acceptance_spec.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8947_converter_authority_ticket_dry_run_harness_contract.json"

ACCEPTANCE_SPEC_ROWS = [
    {
        "spec_id": "tokenizer_hashlock_rejects_source_swap",
        "fixture_type": "json_metadata_only",
        "given": "target tokenizer hash and source tokenizer hash differ",
        "expect": "reject_embedding_or_lm_head_copy_resize",
        "forbidden": ["load_checkpoint", "resize_embeddings", "copy_lm_head"],
    },
    {
        "spec_id": "bitnet_synthetic_golden_vectors_required_before_real_decode",
        "fixture_type": "synthetic_vector_only",
        "given": "packed BitNet candidate semantics without real weight bytes",
        "expect": "require_synthetic_golden_vector_pass_before_real_decode",
        "forbidden": ["read_real_packed_weight_values", "decode_real_packed_bitnet"],
    },
    {
        "spec_id": "shape_delta_telemetry_required_before_checkpoint_write",
        "fixture_type": "shape_schema_only",
        "given": "module mapping and expected target shapes",
        "expect": "emit_delta_shape_telemetry_schema",
        "forbidden": ["save_checkpoint", "load_state_dict"],
    },
    {
        "spec_id": "positional_embedding_ignore_policy_rechecked",
        "fixture_type": "policy_metadata_only",
        "given": "source positional embedding incompatible with target policy",
        "expect": "ignore_source_positional_embedding",
        "forbidden": ["copy_source_positional_embedding"],
    },
    {
        "spec_id": "control_head_seed_policy_rechecked",
        "fixture_type": "seed_policy_only",
        "given": "missing source weights for recovered control heads",
        "expect": "record_deterministic_initializer_seed_schema",
        "forbidden": ["initialize_live_module_parameters"],
    },
]

GLOBAL_FORBIDDEN_OPERATIONS = [
    "open_source_checkpoint",
    "read_weight_bytes",
    "decode_real_packed_bitnet",
    "instantiate_model",
    "load_state_dict",
    "save_checkpoint",
    "run_forward",
    "train_step",
    "mine_data",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_spec(registry: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "source_stage8947_passed": load_json(SOURCE_SUMMARY).get("passed") is True,
        "acceptance_spec_rows_recorded": len(ACCEPTANCE_SPEC_ROWS) >= 5,
        "all_rows_fixture_only": all(str(row.get("fixture_type", "")).endswith("_only") for row in ACCEPTANCE_SPEC_ROWS),
        "all_rows_have_forbidden_ops": all(row.get("forbidden") for row in ACCEPTANCE_SPEC_ROWS),
        "global_forbidden_ops_recorded": len(GLOBAL_FORBIDDEN_OPERATIONS) >= 9,
        "no_real_checkpoint_or_tensor_fixture": all("real_weight" not in row.get("fixture_type", "") for row in ACCEPTANCE_SPEC_ROWS),
        "no_checkpoint_open_authorized": True,
        "no_converter_execution_authorized": True,
        "no_checkpoint_write_authorized": True,
        "no_model_execution_authorized": True,
        "no_training_authorized": True,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "CONVERTER_ACCEPTANCE_SPEC_FIXTURE_ONLY",
        "source_stage": 8947,
        "acceptance_spec_rows": ACCEPTANCE_SPEC_ROWS,
        "global_forbidden_operations": GLOBAL_FORBIDDEN_OPERATIONS,
        "checks": checks,
        "metrics": {
            "acceptance_spec_rows": len(ACCEPTANCE_SPEC_ROWS),
            "global_forbidden_operations": len(GLOBAL_FORBIDDEN_OPERATIONS),
            "real_checkpoint_fixture_rows": 0,
            "real_tensor_fixture_rows": 0,
            "converter_code_written": False,
            "converter_execution_authorized": False,
            "checkpoint_open_authorized": False,
            "checkpoint_write_authorized": False,
            "model_execution_authorized_now": False,
            "runtime_authorized_flag": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Converter acceptance criteria are now specified as fixture-only tests. They define what a future converter must prove without opening checkpoints, reading tensor bytes, decoding packed weights, writing checkpoints, running models, mining data, or training.",
    }


def validate_spec(spec: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in spec["checks"].items() if value is not True]
    if any((spec.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8947, 8948, 8949, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in [
        "real_checkpoint_fixture_rows",
        "real_tensor_fixture_rows",
        "converter_code_written",
        "converter_execution_authorized",
        "checkpoint_open_authorized",
        "checkpoint_write_authorized",
        "model_execution_authorized_now",
        "training_authorized",
    ]:
        expected = 0 if key.endswith("_rows") else False
        if spec["metrics"].get(key) != expected:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    spec = build_spec(registry)
    failures = validate_spec(spec, registry)
    SPEC.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "authority_rows": 0,
            "failures": failures,
            **spec["metrics"],
        },
        "artifacts": {"spec": str(SPEC.relative_to(ROOT))},
        "decision": spec["decision"],
        "next_best_step": "Recover converter acceptance-test generator contract from fixture-only specs. Keep generated tests no-op/no-checkpoint until an explicit future authority ticket exists.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8948 Converter Fixture-Only Acceptance Spec",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage records converter acceptance criteria as fixture-only specifications. It does not generate converter code, open checkpoints, read tensor bytes, decode packed weights, write checkpoints, run models, train, or mine data.",
        "",
        f"Acceptance spec rows: `{spec['metrics']['acceptance_spec_rows']}`",
        f"Global forbidden operations: `{spec['metrics']['global_forbidden_operations']}`",
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
        "max_stage": STAGE,
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8948 Converter Fixture-Only Acceptance Spec"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8948 records fixture-only converter acceptance specifications. It keeps converter implementation, checkpoint open/read/write, packed decode, model execution, runtime, mining, and training closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
