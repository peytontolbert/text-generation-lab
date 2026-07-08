#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9478
NAME = "stage9478_episode_step_full_best_state_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9477_episode_step_full_best_state_preflight_audit.json"
RUN_DIR = ROOT / "runs/local/artifacts/stage9478_episode_step_full_best_state_target_100m_probe"
EXECUTION = RUN_DIR / "execution_result.json"
BEST_STATE = RUN_DIR / "best_structured_state_selection.json"
EVAL_LOG = RUN_DIR / "eval_loss_by_checkpoint.jsonl"
AUDIT = RUN_DIR / "stage9478_full_best_state_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_STEP_FULL_BEST_STATE_PROBE_AUDIT_STAGE9478.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> None:
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    result = load_json(EXECUTION)
    best = load_json(BEST_STATE)
    eval_rows = load_jsonl(EVAL_LOG)
    failures: list[str] = []
    safety_failures: list[str] = []

    if source.get("passed") is not True or not source.get("metrics", {}).get("execution_authorized_for_next_stage"):
        safety_failures.append("source_stage9477_not_authorized")
    impl = result.get("implementation") if isinstance(result.get("implementation"), dict) else {}
    if impl.get("probe_scale") != "target_100m":
        safety_failures.append("not_target_100m_execution")
    if result.get("runtime_executed") or result.get("gemma_executed") or result.get("harness_executed"):
        safety_failures.append("forbidden_external_execution")
    if result.get("final_checkpoint_exported"):
        safety_failures.append("final_checkpoint_exported")
    if best.get("checkpoint_exported") is not False or best.get("promotion_ready") is not False:
        safety_failures.append("best_state_export_or_promotion_open")

    by_step: dict[object, dict[str, dict]] = {}
    for row in eval_rows:
        by_step.setdefault(row.get("step", "final"), {})[str(row.get("split"))] = row
    both_exact = []
    eval_exact_strict_miss = []
    strict_exact_eval_miss = []
    for step, pair in by_step.items():
        if "eval" not in pair or "strict_eval" not in pair:
            continue
        card = {
            "step": step,
            "eval_joint": pair["eval"].get("joint_proxy_exact"),
            "strict_joint": pair["strict_eval"].get("joint_proxy_exact"),
            "eval_field_exact": pair["eval"].get("field_exact"),
            "strict_field_exact": pair["strict_eval"].get("field_exact"),
            "eval_loss": pair["eval"].get("loss"),
            "strict_loss": pair["strict_eval"].get("loss"),
        }
        if card["eval_joint"] == 1.0 and card["strict_joint"] == 1.0:
            both_exact.append(card)
        elif card["eval_joint"] == 1.0:
            eval_exact_strict_miss.append(card)
        elif card["strict_joint"] == 1.0:
            strict_exact_eval_miss.append(card)

    final_eval = result.get("eval", {}).get("eval", {}) if isinstance(result.get("eval"), dict) else {}
    final_strict = result.get("eval", {}).get("strict_eval", {}) if isinstance(result.get("eval"), dict) else {}
    eval_fields = final_eval.get("field_exact") if isinstance(final_eval.get("field_exact"), dict) else {}
    strict_fields = final_strict.get("field_exact") if isinstance(final_strict.get("field_exact"), dict) else {}
    failed_eval_fields = [field for field, card in sorted(eval_fields.items()) if isinstance(card, dict) and card.get("exact") != 1.0]
    failed_strict_fields = [field for field, card in sorted(strict_fields.items()) if isinstance(card, dict) and card.get("exact") != 1.0]

    if final_eval.get("joint_proxy_exact") != 1.0:
        failures.append("final_eval_not_joint_exact")
    if final_strict.get("joint_proxy_exact") != 1.0:
        failures.append("final_strict_not_joint_exact")
    if best.get("restored") is not True:
        failures.append("no_jointly_exact_best_state_to_restore")
    if not both_exact:
        failures.append("no_jointly_exact_interval")

    checkpoint_like = sorted(
        str(path.relative_to(RUN_DIR))
        for path in RUN_DIR.rglob("*")
        if path.is_file() and path.suffix in {".pt", ".pth", ".bin", ".safetensors", ".ckpt"}
    )
    if checkpoint_like:
        safety_failures.append("checkpoint_like_artifacts_written")

    failures.extend(safety_failures)
    audit = {
        "passed": not failures,
        "safety_passed": not safety_failures,
        "quality_passed": not [failure for failure in failures if failure not in safety_failures],
        "failures": failures,
        "safety_failures": safety_failures,
        "source_stage": "stage9477_episode_step_full_best_state_preflight_audit",
        "probe_scale": impl.get("probe_scale"),
        "estimated_parameter_count": impl.get("estimated_parameter_count"),
        "mode": result.get("mode"),
        "train_rows": result.get("train_rows"),
        "eval_rows": result.get("eval_rows"),
        "strict_rows": result.get("strict_rows"),
        "final_eval_joint_proxy_exact": final_eval.get("joint_proxy_exact"),
        "final_strict_joint_proxy_exact": final_strict.get("joint_proxy_exact"),
        "failed_eval_fields": failed_eval_fields,
        "failed_strict_fields": failed_strict_fields,
        "both_exact_checkpoints": both_exact,
        "eval_exact_strict_miss": eval_exact_strict_miss,
        "strict_exact_eval_miss": strict_exact_eval_miss,
        "best_state_selection": best,
        "checkpoint_like_artifacts": checkpoint_like,
        "diagnosis": "Full five-head episode-step structured probe is safe but not quality-passing. Eval and strict become exact at different intervals; the final residual is eval episode_target_prefix_match. Next patch should balance/counterbalance target-prefix supervision or split full five-head objective from diagnosis heads.",
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
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "execution_result": str(EXECUTION.relative_to(ROOT)), "best_state_selection": str(BEST_STATE.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Full five-head episode-step probe failed quality safely; do not widen execution or reopen decoder CE. Repair target-prefix/split balance first.",
        "next_best_step": "Build Stage9479 target-prefix balance/contrastive repair manifest or split the full five-head objective so diagnosis heads stay stable while boundary/prefix heads get targeted curriculum.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9478 Episode-Step Full Best-State Probe Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Safety passed: `{audit['safety_passed']}`",
        f"Quality passed: `{audit['quality_passed']}`",
        f"Final eval joint: `{audit['final_eval_joint_proxy_exact']}`",
        f"Final strict joint: `{audit['final_strict_joint_proxy_exact']}`",
        f"Failed eval fields: `{failed_eval_fields}`",
        f"Both-exact intervals: `{both_exact}`",
        "",
        audit["diagnosis"],
        "",
        "Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.",
        "",
    ]))
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    reg_rows = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = reg_rows
    registry["passed"] = bool(reg_rows)
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(reg_rows)}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "failures": failures, "failed_eval_fields": failed_eval_fields}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
