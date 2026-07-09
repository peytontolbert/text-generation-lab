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
STAGE = 9682
NAME = "stage9682_controller_renderer_integration_preflight"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9681_slot_template_renderer_package_audit.json"
PACKAGE = ROOT / "runs/local/artifacts/stage9681_slot_template_renderer_package_audit/slot_template_renderer_package_v1.json"
CONTROLLER_RUN_DIR = ROOT / "runs/local/artifacts/stage9679_slot_template_controller_probe"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PREFLIGHT = OUT_DIR / "controller_renderer_integration_preflight.json"
PREVIEW = OUT_DIR / "controller_renderer_integration_preview.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CONTROLLER_RENDERER_INTEGRATION_PREFLIGHT_STAGE9682.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": summary["next_best_step"],
    })
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
    source_summary = load_json(SOURCE_SUMMARY)
    package = load_json(PACKAGE)
    execution = load_json(CONTROLLER_RUN_DIR / "execution_result.json")
    logits = [row for row in load_jsonl(CONTROLLER_RUN_DIR / "row_field_logits.jsonl") if row.get("field") == "suffix_choice"]
    template_map = package.get("template_map") if isinstance(package.get("template_map"), dict) else {}
    preview_rows: list[dict[str, Any]] = []
    unknown_label_rows: list[str] = []
    low_confidence_rows: list[str] = []
    internal_token_rows: list[str] = []
    for row in logits:
        pred = str(row.get("pred") or "")
        template = template_map.get(pred)
        rendered = str((template or {}).get("template_text") or "")
        confidence = float(row.get("confidence") or 0.0)
        if not template:
            unknown_label_rows.append(str(row.get("row_id")))
        if confidence < 0.90:
            low_confidence_rows.append(str(row.get("row_id")))
        if any(token in rendered for token in ["<MTC", "<COPY:", "POLICY_", "AUTHORITY_"]):
            internal_token_rows.append(str(row.get("row_id")))
        preview_rows.append({
            "row_id": row.get("row_id"),
            "split": row.get("split"),
            "predicted_template_label": pred,
            "target_template_label": row.get("target"),
            "label_correct": row.get("correct"),
            "confidence": confidence,
            "margin": row.get("margin"),
            "rendered_text": rendered,
            "render_source": "stage9681_slot_template_renderer_package_v1",
            "would_use_renderer": bool(template and confidence >= 0.90),
        })
    write_jsonl(PREVIEW, preview_rows)

    heldout = [row for row in preview_rows if row.get("split") in {"eval", "strict_eval"}]
    heldout_correct = sum(1 for row in heldout if row.get("label_correct"))
    heldout_use_renderer = sum(1 for row in heldout if row.get("would_use_renderer"))
    failures: list[str] = []
    if source_summary.get("passed") is not True:
        failures.append("stage9681_not_passed")
    if package.get("template_count") != 10:
        failures.append("template_package_count_not_10")
    if execution.get("mode") != "structured_policy_probe" or ((execution.get("eval") or {}).get("eval") or {}).get("joint_proxy_exact") != 1.0:
        failures.append("stage9679_controller_not_passing")
    if len(heldout) != 6:
        failures.append("heldout_preview_rows_not_6")
    if heldout_correct != len(heldout):
        failures.append("heldout_label_not_exact")
    if heldout_use_renderer != len(heldout):
        failures.append("heldout_renderer_gate_not_all_true")
    if unknown_label_rows:
        failures.append("unknown_label_rows")
    if low_confidence_rows:
        failures.append("low_confidence_rows")
    if internal_token_rows:
        failures.append("internal_token_rows")
    if execution.get("runtime_executed") or execution.get("gemma_executed") or execution.get("harness_executed") or execution.get("final_checkpoint_exported"):
        failures.append("forbidden_stage9679_execution_or_export")

    preflight = {
        "passed": not failures,
        "failures": failures,
        "controller_stage": 9679,
        "renderer_package_stage": 9681,
        "preview_rows": len(preview_rows),
        "heldout_rows": len(heldout),
        "heldout_label_correct_rows": heldout_correct,
        "heldout_renderer_gate_true_rows": heldout_use_renderer,
        "unknown_label_rows": unknown_label_rows,
        "low_confidence_rows": low_confidence_rows,
        "internal_token_rows": internal_token_rows,
        "integration_policy": {
            "if_confidence_at_least": 0.90,
            "and_label_known": True,
            "then": "render_deterministic_template",
            "else": "abstain_or_route_to_retrieve_more",
        },
        "closed_paths": [
            "decoder_generation",
            "denoise_generation",
            "runtime",
            "gemma",
            "harness",
            "checkpoint_export",
            "promotion",
        ],
        "authority": dict(AUTHORITY_CLOSED),
    }
    PREFLIGHT.write_text(json.dumps(preflight, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Use controller+renderer as the fixed-slot residual repair path; next return to broader denoise only for non-template residuals with a repetition guard."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": preflight["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **preflight},
        "artifacts": {
            "doc": str(DOC.relative_to(ROOT)),
            "preflight": str(PREFLIGHT.relative_to(ROOT)),
            "preview": str(PREVIEW.relative_to(ROOT)),
        },
        "decision": "Controller+renderer integration preflight passed as the non-generative path for fixed residual slot templates.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9682 Controller Renderer Integration Preflight",
        "",
        f"Passed: `{preflight['passed']}`",
        f"Heldout label correct: `{heldout_correct}` / `{len(heldout)}`",
        f"Heldout renderer gate true: `{heldout_use_renderer}` / `{len(heldout)}`",
        "",
        "This preflight wires the passing Stage9679 structured controller to the Stage9681 deterministic renderer package. It is still non-generative and does not authorize decoder/denoise/runtime/Gemma/harness/export.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": preflight["passed"],
        "failures": failures,
        "heldout_label_correct_rows": heldout_correct,
        "heldout_rows": len(heldout),
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
