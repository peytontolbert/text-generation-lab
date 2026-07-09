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
STAGE = 9565
NAME = "stage9565_residual_denoise_target_rendering_diagnosis"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9564_residual_denoise_target_100m_tiny_probe.json"
EXECUTION_MANIFEST = ROOT / "runs/local/artifacts/stage9562_residual_denoise_execution_authorization_review/residual_denoise_execution_candidate_manifest.jsonl"
RUN_DIR = ROOT / "runs/local/artifacts/stage9564_residual_denoise_target_100m_tiny_probe/denoise_repair_probe"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DIAGNOSIS = OUT_DIR / "residual_denoise_target_rendering_diagnosis.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESIDUAL_DENOISE_TARGET_RENDERING_DIAGNOSIS_STAGE9565.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def target_text(row: dict[str, Any]) -> str:
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    if isinstance(target.get("decoder_text"), str):
        return target["decoder_text"]
    if isinstance(row.get("decoder_text"), str):
        return row["decoder_text"]
    return str(target.get("target_ref") or row.get("target_ref") or target.get("label") or "")


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [
        row
        for row in registry.get("rows", [])
        if row.get("stage") != STAGE and row.get("stage_name") != NAME
    ]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": dict(AUTHORITY_CLOSED),
            "next_best_step": summary["next_best_step"],
        }
    )
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


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)

    source = load_json(SOURCE_SUMMARY)
    rows = load_jsonl(EXECUTION_MANIFEST)
    loss_rows = load_jsonl(RUN_DIR / "row_token_loss.jsonl")
    step_rows = load_jsonl(RUN_DIR / "loss_by_step.jsonl")
    quality = load_json(RUN_DIR / "denoise_repair_quality_audit.json")
    execution = load_json(RUN_DIR / "execution_result.json")
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9564_not_safety_passed")
    if len(rows) != 41:
        failures.append("manifest_row_count_not_41")
    missing_rendered_target_rows = [str(row.get("row_id")) for row in rows if not target_text(row).strip()]
    eos_only_loss_rows = [
        row.get("row_id")
        for row in loss_rows
        if int(row.get("token_count", 0)) == 1 and int(row.get("eos_position", -1)) == 0
    ]
    zero_loss_steps = [row.get("step") for row in step_rows if float(row.get("loss", 0.0)) == 0.0]
    zero_grad_steps = [row.get("step") for row in step_rows if float(row.get("grad_norm", 0.0)) == 0.0]
    diagnosis_matches = (
        len(missing_rendered_target_rows) == 41
        and len(loss_rows) > 0
        and len(eos_only_loss_rows) == len(loss_rows)
    )
    if not diagnosis_matches:
        failures.append("diagnosis_did_not_match_expected_eos_only_pattern")

    diagnosis = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "execution_manifest": str(EXECUTION_MANIFEST.relative_to(ROOT)),
        "run_dir": str(RUN_DIR.relative_to(ROOT)),
        "manifest_rows": len(rows),
        "missing_rendered_target_rows": len(missing_rendered_target_rows),
        "missing_rendered_target_row_examples": missing_rendered_target_rows[:20],
        "row_token_loss_rows": len(loss_rows),
        "eos_only_loss_rows": len(eos_only_loss_rows),
        "loss_steps": len(step_rows),
        "zero_loss_steps": len(zero_loss_steps),
        "zero_grad_steps": len(zero_grad_steps),
        "contentful_generation_rate": quality.get("contentful_generation_rate"),
        "generated_rows": quality.get("generated_rows"),
        "target_prefix_match_rate": quality.get("target_prefix_match_rate"),
        "execution_required_artifacts_written": execution.get("required_artifacts_written"),
        "safety_result": "stage9564_execution_safety_passed",
        "learnability_result": "failed_empty_target_rendering",
        "required_patch": "render residual denoise targets into target.label or target.decoder_text before rerunning denoise CE",
        "model_execution_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "runtime_authorized": False,
        "promotion_ready": False,
        "authority": dict(AUTHORITY_CLOSED),
    }
    DIAGNOSIS.write_text(json.dumps(diagnosis, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": diagnosis["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **diagnosis},
        "artifacts": {"diagnosis": str(DIAGNOSIS.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Diagnosed Stage9564 as a safety-pass but learnability-fail run: all 41 denoise rows lacked a rendered target consumed by the trainer, so the target collapsed to EOS-only.",
        "next_best_step": "Build Stage9566 target-rendered residual-denoise manifest that writes a bounded target.label or target.decoder_text, rerun contract-only preflight, then rerun the tiny probe.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9565 Residual Denoise Target Rendering Diagnosis",
                "",
                f"Passed: `{diagnosis['passed']}`",
                f"Manifest rows: `{len(rows)}`",
                f"Missing rendered target rows: `{len(missing_rendered_target_rows)}`",
                f"EOS-only token-loss rows: `{len(eos_only_loss_rows)}`",
                f"Zero-loss steps: `{len(zero_loss_steps)}`",
                f"Zero-grad steps: `{len(zero_grad_steps)}`",
                "",
                "Stage9564 proved execution safety, not learnability. The trainer consumes `target.decoder_text`, row `decoder_text`, `target_ref`, or `target.label`; these rows only carried `repair_bucket` and `failure_type`.",
                "The next patch must render a bounded denoise target before another denoise CE run.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": diagnosis["passed"], "missing_rendered_target_rows": len(missing_rendered_target_rows), "zero_loss_steps": len(zero_loss_steps), "failures": failures}, indent=2, sort_keys=True))
    if not diagnosis["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
