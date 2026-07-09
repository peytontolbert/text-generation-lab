#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9702
NAME = "stage9702_native_feature_ablation_trainer_patch_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9701_symbol_binding_rebalanced_contract_preflight.json"
SMOKE_DIR = ROOT / "runs/local/artifacts/stage9702_native_feature_ablation_trainer_patch/smoke_probe"
TRAINER_SCRIPT = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
TRAINING_LOOP = ROOT / "legacy_src/agentkernel_lite/training_loop.py"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "native_feature_ablation_trainer_patch_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "NATIVE_FEATURE_ABLATION_TRAINER_PATCH_STAGE9702.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def trainer_support() -> dict[str, Any]:
    script = TRAINER_SCRIPT.read_text(encoding="utf-8")
    loop = TRAINING_LOOP.read_text(encoding="utf-8")
    return {
        "cli_flag_present": "--require-native-feature-ablation-audit" in script,
        "contract_card_field_present": "native_feature_ablation_audit_required" in script,
        "structured_probe_argument_present": "require_native_feature_ablation_audit" in loop,
        "native_mode_present": "native_grouped_mask_rerun" in loop,
        "query_kind_group_present": '"query_kind"' in loop,
    }


def smoke_metrics() -> dict[str, Any]:
    result = load_json(SMOKE_DIR / "execution_result.json")
    deltas = load_json(SMOKE_DIR / "module_delta_norms.json")
    rows = load_jsonl(SMOKE_DIR / "feature_ablation_attribution.jsonl")
    modes = sorted({item.get("ablation_mode") for row in rows for item in row.get("feature_attribution", [])})
    groups = sorted({item.get("feature_group") for row in rows for item in row.get("feature_attribution", [])})
    return {
        "smoke_dir": str(SMOKE_DIR.relative_to(ROOT)),
        "execution_result_present": bool(result),
        "required_artifacts_written": result.get("required_artifacts_written") is True,
        "native_feature_ablation_audit_required": result.get("native_feature_ablation_audit_required") is True,
        "native_feature_ablation_rows": result.get("native_feature_ablation_rows"),
        "mode": result.get("mode"),
        "fields": result.get("fields"),
        "probe_scale": (result.get("implementation") or {}).get("probe_scale"),
        "full_100m_target_execution_authorized": (result.get("implementation") or {}).get("full_100m_target_execution_authorized") is True,
        "runtime_executed": result.get("runtime_executed") is True,
        "gemma_executed": result.get("gemma_executed") is True,
        "harness_executed": result.get("harness_executed") is True,
        "final_checkpoint_exported": result.get("final_checkpoint_exported") is True,
        "decoder_delta_norm": deltas.get("decoder_delta_norm"),
        "delta_norm_by_bucket": deltas.get("delta_norm_by_bucket") or {},
        "feature_ablation_rows": len(rows),
        "ablation_modes": modes,
        "feature_groups": groups,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    support = trainer_support()
    smoke = smoke_metrics()
    failures: list[str] = []
    if source.get("data_contract_passed") is not True:
        failures.append("stage9701_data_contract_not_passed")
    for key, value in support.items():
        if value is not True:
            failures.append(f"trainer_support_missing:{key}")
    if smoke.get("mode") != "symbol_binding_probe":
        failures.append("smoke_mode_not_symbol_binding_probe")
    if smoke.get("probe_scale") != "tiny_transformer_runtime_path":
        failures.append("smoke_not_tiny_transformer_runtime_path")
    if smoke.get("full_100m_target_execution_authorized"):
        failures.append("smoke_unexpectedly_authorized_full_100m")
    if smoke.get("native_feature_ablation_rows") != 32 or smoke.get("feature_ablation_rows") != 32:
        failures.append("native_ablation_row_count_not_32")
    if smoke.get("ablation_modes") != ["native_grouped_mask_rerun"]:
        failures.append(f"unexpected_ablation_modes:{smoke.get('ablation_modes')}")
    required_groups = {"query_kind", "intent_features", "import_dependency_evidence", "graph_evidence", "surface_role_features", "verifier_feedback"}
    if set(smoke.get("feature_groups") or []) != required_groups:
        failures.append(f"unexpected_feature_groups:{smoke.get('feature_groups')}")
    for closed_key in ["runtime_executed", "gemma_executed", "harness_executed", "final_checkpoint_exported"]:
        if smoke.get(closed_key):
            failures.append(f"closed_boundary_opened:{closed_key}")
    buckets = smoke.get("delta_norm_by_bucket") or {}
    for bucket in ["decoder", "decoder_attention", "decoder_mlp", "embeddings", "lm_head"]:
        if float(buckets.get(bucket, 0.0) or 0.0) != 0.0:
            failures.append(f"frozen_bucket_moved:{bucket}")

    next_step = "Run Stage9703 target-100M contract-only preflight on the Stage9700 repaired manifest with --require-native-feature-ablation-audit; do not execute until that preflight passes."
    audit = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "quality_passed": False,
        "promotion_ready": False,
        "failures": failures,
        "source_stage9701_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "trainer_support": support,
        "smoke_metrics": smoke,
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": next_step,
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "quality_passed": False,
        "promotion_ready": False,
        "created_at_unix": int(time.time()),
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "smoke_dir": str(SMOKE_DIR.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "metrics": {
            "native_feature_ablation_rows": smoke.get("native_feature_ablation_rows"),
            "ablation_modes": smoke.get("ablation_modes"),
            "feature_groups": smoke.get("feature_groups"),
            "decoder_delta_norm": smoke.get("decoder_delta_norm"),
            "full_100m_target_execution_authorized": smoke.get("full_100m_target_execution_authorized"),
        },
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": next_step,
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9702 Native Feature-Ablation Trainer Patch",
        "",
        "Stage9702 patches the structured trainer so `--require-native-feature-ablation-audit` emits native grouped mask-rerun attribution rows instead of deterministic proxy rows.",
        "",
        "## Result",
        "",
        f"- Passed: `{not failures}`",
        f"- Native ablation rows: `{smoke.get('native_feature_ablation_rows')}`",
        f"- Ablation modes: `{smoke.get('ablation_modes')}`",
        f"- Full target-100M authorized in smoke: `{smoke.get('full_100m_target_execution_authorized')}`",
        f"- Decoder delta norm: `{smoke.get('decoder_delta_norm')}`",
        "",
        "## Next",
        "",
        next_step,
        "",
    ]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
