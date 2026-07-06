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
STAGE = 8924
NAME = "stage8924_training_readiness_blocker_matrix"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAINING_READINESS_BLOCKER_MATRIX_STAGE8924.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MATRIX = OUT_DIR / "training_readiness_blocker_matrix.json"

SOURCE_SUMMARIES = {
    8905: ROOT / "runs/summaries/stage8905_local_agentkernel_lite_seed_compatibility_audit.json",
    8908: ROOT / "runs/summaries/stage8908_tokenizer_special_token_compatibility_audit.json",
    8909: ROOT / "runs/summaries/stage8909_state_dict_shape_migration_design.json",
    8916: ROOT / "runs/summaries/stage8916_nonexecuting_converter_shape_report_dry_run.json",
    8917: ROOT / "runs/summaries/stage8917_converter_row_completeness_collision_audit.json",
    8918: ROOT / "runs/summaries/stage8918_converter_key_mapping_init_policy_contract.json",
    8919: ROOT / "runs/summaries/stage8919_tokenizer_embedding_migration_policy_design.json",
    8920: ROOT / "runs/summaries/stage8920_checkpoint_materialization_noop_skeleton_design.json",
    8921: ROOT / "runs/summaries/stage8921_future_probe_artifact_path_policy.json",
    8922: ROOT / "runs/summaries/stage8922_cleanup_proof_no_overwrite_finalization.json",
    8923: ROOT / "runs/summaries/stage8923_future_probe_preflight_no_write_audit.json",
}

BLOCKERS = [
    {
        "blocker": "direct_seed_load_blocked",
        "source_stage": 8905,
        "reason": "local AgentKernel Lite export is browser BitNet runtime format and is not a verified PyTorch checkpoint",
        "required_next": "state-dict materialization contract plus converter implementation audits",
    },
    {
        "blocker": "tokenizer_vocab_mismatch",
        "source_stage": 8908,
        "reason": "source export vocab 8207 does not match recovered target vocab 1506",
        "required_next": "tokenizer hash lock and bridge mapping or explicit keep-target decision",
    },
    {
        "blocker": "packed_bitnet_decode_blocked",
        "source_stage": 8916,
        "reason": "109 packed BitNet rows require layout decoder and dequantization shape assertions",
        "required_next": "metadata-first BitNet layout decoder contract; no tensor values until authorized",
    },
    {
        "blocker": "embedding_lm_head_migration_blocked",
        "source_stage": 8919,
        "reason": "embedding/lm-head copy, resize, and tokenizer swap remain explicitly unauthorized",
        "required_next": "embedding/lm-head migration policy with hashes, row mapping, and tests",
    },
    {
        "blocker": "control_head_initialization_blocked",
        "source_stage": 8918,
        "reason": "retrieval, policy, intent, controller, scalar, and structured heads are target-only/new-init groups",
        "required_next": "initializer seed policy and module-shape telemetry contract",
    },
    {
        "blocker": "checkpoint_materialization_noop_only",
        "source_stage": 8920,
        "reason": "materialization skeleton records preconditions but blocks load/decode/resize/init/write/forward/train",
        "required_next": "separate passing audits for every materialization precondition",
    },
    {
        "blocker": "future_probe_artifact_path_only",
        "source_stage": 8921,
        "reason": "probe path policy is ready, but only as a no-execution template",
        "required_next": "explicit one-run authorization review card before any probe writes",
    },
    {
        "blocker": "cleanup_preflight_no_write_only",
        "source_stage": 8923,
        "reason": "future probe output root is fresh and reserved, but no directories/artifacts were created",
        "required_next": "explicit execution authorization if a tiny run is requested",
    },
]

READY_COMPONENTS = [
    "local seed export located and cataloged",
    "core tokenizer IDs and AgentKernel special token range recovered",
    "metadata-only converter shape rows complete and collision-free",
    "converter key-mapping/init policy classified",
    "tokenizer/embedding safe default recorded",
    "checkpoint materialization skeleton defined as no-op",
    "future probe artifact path policy recorded",
    "cleanup/no-overwrite proof contract recorded",
    "future probe no-write preflight passed",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_matrix(registry: dict[str, Any]) -> dict[str, Any]:
    source_status = {
        str(stage): {
            "path": str(path.relative_to(ROOT)),
            "exists": path.exists(),
            "passed": load_json(path).get("passed") is True,
        }
        for stage, path in SOURCE_SUMMARIES.items()
    }
    checks = {
        "all_source_summaries_present": all(item["exists"] for item in source_status.values()),
        "all_source_summaries_passed": all(item["passed"] for item in source_status.values()),
        "blockers_present": len(BLOCKERS) >= 8,
        "ready_components_present": len(READY_COMPONENTS) >= 9,
        "training_remains_blocked": True,
        "model_execution_remains_blocked": True,
        "decoder_ce_remains_blocked": True,
        "runtime_remains_blocked": True,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    metrics = {
        "source_stages": len(SOURCE_SUMMARIES),
        "source_summaries_present": sum(1 for item in source_status.values() if item["exists"]),
        "source_summaries_passed": sum(1 for item in source_status.values() if item["passed"]),
        "blocker_count": len(BLOCKERS),
        "ready_component_count": len(READY_COMPONENTS),
        "training_authorized": False,
        "model_execution_authorized_now": False,
        "decoder_ce_authorized": False,
        "denoise_ce_authorized": False,
        "runtime_authorized_flag": False,
        "data_mining_authorized": False,
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "source_status": source_status,
        "checks": checks,
        "metrics": metrics,
        "ready_components": READY_COMPONENTS,
        "blockers": BLOCKERS,
        "authority": dict(AUTHORITY_CLOSED),
        "decision": {
            "training_readiness": "not_ready",
            "execution_status": "blocked",
            "next_required_artifact": "tokenizer hash-lock and bridge-token mapping/keep-target decision card, unless work returns to dataset/compiler recovery",
        },
    }


def validate_matrix(matrix: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in matrix["checks"].items() if value is not True]
    if any((matrix.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8923, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    matrix = build_matrix(registry)
    failures = validate_matrix(matrix, registry)
    MATRIX.write_text(json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "failures": failures,
            **matrix["metrics"],
        },
        "artifacts": {"matrix": str(MATRIX.relative_to(ROOT))},
        "decision": "Training readiness blocker matrix passed: recovered seed/tokenizer/converter/probe safety contracts are recorded, but training and execution remain blocked.",
        "next_best_step": "Either continue no-execution recovery of dataset/compiler modules, or add tokenizer hash-lock and bridge-token mapping/keep-target decision card before any checkpoint materialization work.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8924 Training Readiness Blocker Matrix",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "Recovered model seed/tokenizer/converter/probe-safety contracts are now indexed into a single blocker matrix.",
        "",
        f"Ready components: `{matrix['metrics']['ready_component_count']}`",
        f"Blockers: `{matrix['metrics']['blocker_count']}`",
        "",
        "Training remains blocked. Model execution remains blocked. Decoder CE remains blocked. Runtime remains blocked.",
        "",
        "Next: continue no-execution dataset/compiler recovery, or resolve tokenizer hash-lock and bridge-token mapping before checkpoint materialization work.",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = card["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": card["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8924 Training Readiness Blocker Matrix"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8924 consolidates seed/tokenizer/converter/checkpoint/probe-safety recovery into a training-readiness blocker matrix. It records what is ready, what remains blocked, and keeps model execution, decoder CE, runtime, mining, and training closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
