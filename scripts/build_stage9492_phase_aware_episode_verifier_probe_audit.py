#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9492
NAME = "stage9492_phase_aware_episode_verifier_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9491_phase_aware_episode_verifier_preflight_audit.json"
RUN_DIR = ROOT / "runs/local/artifacts/stage9492_phase_aware_episode_verifier_target_100m_probe"
EXECUTION = RUN_DIR / "execution_result.json"
BEST_STATE = RUN_DIR / "best_structured_state_selection.json"
LOGITS = RUN_DIR / "row_field_logits.jsonl"
AUDIT = RUN_DIR / "stage9492_phase_aware_episode_verifier_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PHASE_AWARE_EPISODE_VERIFIER_PROBE_AUDIT_STAGE9492.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def main() -> None:
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    result = load_json(EXECUTION)
    best = load_json(BEST_STATE)
    logits = load_jsonl(LOGITS)
    failures: list[str] = []
    safety_failures: list[str] = []

    if source.get("passed") is not True or not source.get("metrics", {}).get("execution_authorized_for_next_stage"):
        safety_failures.append("source_stage9491_not_authorized")
    impl = result.get("implementation") if isinstance(result.get("implementation"), dict) else {}
    if impl.get("probe_scale") != "target_100m":
        safety_failures.append("not_target_100m_execution")
    if result.get("runtime_executed") or result.get("gemma_executed") or result.get("harness_executed"):
        safety_failures.append("forbidden_external_execution")
    if result.get("final_checkpoint_exported"):
        safety_failures.append("final_checkpoint_exported")
    checkpoint_like = sorted(
        str(path.relative_to(RUN_DIR))
        for path in RUN_DIR.rglob("*")
        if path.is_file() and path.suffix in {".pt", ".pth", ".bin", ".safetensors", ".ckpt"}
    )
    if checkpoint_like:
        safety_failures.append("checkpoint_like_artifacts_written")

    final_eval = result.get("eval", {}).get("eval", {}) if isinstance(result.get("eval"), dict) else {}
    final_strict = result.get("eval", {}).get("strict_eval", {}) if isinstance(result.get("eval"), dict) else {}
    if final_eval.get("joint_proxy_exact") != 1.0:
        failures.append("final_eval_not_exact")
    if final_strict.get("joint_proxy_exact") != 1.0:
        failures.append("final_strict_not_exact")
    if best.get("restored") is not True:
        failures.append("no_jointly_exact_best_state_to_restore")

    wrong_rows = [row for row in logits if row.get("correct") is False]
    wrong_by_field_split = Counter(
        f"{row.get('split')}::{row.get('field')}::{row.get('target')}=>{row.get('pred')}"
        for row in wrong_rows
    )
    high_conf_wrong = [row for row in wrong_rows if row.get("high_confidence_wrong")]
    failures.extend(safety_failures)
    audit = {
        "passed": not failures,
        "safety_passed": not safety_failures,
        "quality_passed": not [failure for failure in failures if failure not in safety_failures],
        "failures": failures,
        "safety_failures": safety_failures,
        "source_stage": "stage9491_phase_aware_episode_verifier_preflight_audit",
        "probe_scale": impl.get("probe_scale"),
        "estimated_parameter_count": impl.get("estimated_parameter_count"),
        "mode": result.get("mode"),
        "fields": result.get("fields"),
        "train_rows": result.get("train_rows"),
        "eval_rows": result.get("eval_rows"),
        "strict_rows": result.get("strict_rows"),
        "final_eval_joint_proxy_exact": final_eval.get("joint_proxy_exact"),
        "final_strict_joint_proxy_exact": final_strict.get("joint_proxy_exact"),
        "final_eval_field_exact": final_eval.get("field_exact"),
        "final_strict_field_exact": final_strict.get("field_exact"),
        "wrong_rows": wrong_rows,
        "wrong_by_field_split": dict(sorted(wrong_by_field_split.items())),
        "high_confidence_wrong_rows": high_conf_wrong,
        "best_state_selection": best,
        "checkpoint_like_artifacts": checkpoint_like,
        "diagnosis": "Safe quality failure. Combined observe-phase verifier heads collapsed toward majority/default classes on the tiny 66-row set. Target-prefix alone is learnable, but all verifier labels together need either deterministic verifier-feature overlays or per-head staged curricula before rejoining.",
        "authority": dict(AUTHORITY_CLOSED),
        "model_execution_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "execution_result": str(EXECUTION.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Phase-aware observe verifier probe failed quality safely; do not widen. Split verifier heads or add deterministic verifier-feature overlay before rejoin.",
        "next_best_step": "Build Stage9493 per-head verifier curriculum queue: keep target-prefix as passed, isolate boundary/failure/outcome/value heads with deterministic verifier features and balanced eval/strict cells.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9492 Phase-Aware Episode Verifier Probe Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Safety passed: `{audit['safety_passed']}`",
        f"Quality passed: `{audit['quality_passed']}`",
        f"Final eval joint: `{audit['final_eval_joint_proxy_exact']}`",
        f"Final strict joint: `{audit['final_strict_joint_proxy_exact']}`",
        f"Wrong rows: `{len(wrong_rows)}`",
        f"High-confidence wrong rows: `{len(high_conf_wrong)}`",
        "",
        audit["diagnosis"],
        "",
    ]))
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "safety_passed": audit["safety_passed"], "wrong_rows": len(wrong_rows), "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
