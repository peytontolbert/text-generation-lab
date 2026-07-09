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
STAGE = 9683
NAME = "stage9683_fixed_template_residual_router"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9682_controller_renderer_integration_preflight.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9674_neutral_slot_prior_denoise_preexecution/neutral_slot_prior_denoise_manifest.jsonl"
RENDERER_PACKAGE = ROOT / "runs/local/artifacts/stage9681_slot_template_renderer_package_audit/slot_template_renderer_package_v1.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
FIXED_MANIFEST = OUT_DIR / "fixed_template_residual_manifest.jsonl"
NON_TEMPLATE_QUEUE = OUT_DIR / "non_template_residual_denoise_queue.jsonl"
AUDIT = OUT_DIR / "fixed_template_residual_router_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "FIXED_TEMPLATE_RESIDUAL_ROUTER_STAGE9683.md"
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


def slot_label(row: dict[str, Any]) -> str:
    slot = row.get("neutral_slot_prior") if isinstance(row.get("neutral_slot_prior"), dict) else {}
    return "__".join([
        str(slot.get("slot_object") or "unknown"),
        str(slot.get("slot_relation") or "unknown"),
        str(slot.get("slot_constraint") or "unknown"),
    ])


def target_text(row: dict[str, Any]) -> str:
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    return str(target.get("decoder_text") or row.get("decoder_text") or "").strip()


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
    source_rows = load_jsonl(SOURCE_MANIFEST)
    package = load_json(RENDERER_PACKAGE)
    template_map = package.get("template_map") if isinstance(package.get("template_map"), dict) else {}

    fixed_rows: list[dict[str, Any]] = []
    non_template_rows: list[dict[str, Any]] = []
    render_mismatches: list[str] = []
    for index, row in enumerate(source_rows):
        label = slot_label(row)
        template = template_map.get(label)
        if template:
            rendered = str(template.get("template_text") or "")
            expected = target_text(row)
            if rendered != expected:
                render_mismatches.append(str(row.get("row_id")))
            fixed_rows.append({
                "row_id": f"stage9683_fixed_template_residual_{index:04d}",
                "source_stage9674_row_id": row.get("row_id"),
                "split": row.get("split"),
                "language_family": row.get("language_family"),
                "route": "FIXED_TEMPLATE_RENDERER_HANDLED",
                "objective_family": "non_generative_slot_template_render",
                "slot_template_label": label,
                "rendered_text": rendered,
                "render_source": "stage9681_slot_template_renderer_package_v1",
                "original_target_text": expected,
                "render_exact": rendered == expected,
                "loss_mask": {
                    "decoder_ce": False,
                    "denoise_ce": False,
                    "runtime_reward": False,
                    "structured_aux": False,
                    "suffix_choice_ce": False,
                },
                "authority": dict(AUTHORITY_CLOSED),
            })
        else:
            non_template_rows.append({
                "row_id": f"stage9683_non_template_residual_{index:04d}",
                "source_stage9674_row_id": row.get("row_id"),
                "split": row.get("split"),
                "language_family": row.get("language_family"),
                "route": "NON_TEMPLATE_DENOISE_RETRY_CANDIDATE",
                "objective_family": "future_repetition_guarded_denoise",
                "slot_template_label": label,
                "reason": "slot_template_label_not_in_renderer_package",
                "loss_mask": {
                    "decoder_ce": False,
                    "denoise_ce": False,
                    "runtime_reward": False,
                    "structured_aux": False,
                    "suffix_choice_ce": False,
                },
                "authority": dict(AUTHORITY_CLOSED),
            })
    write_jsonl(FIXED_MANIFEST, fixed_rows)
    write_jsonl(NON_TEMPLATE_QUEUE, non_template_rows)

    failures: list[str] = []
    if source_summary.get("passed") is not True:
        failures.append("stage9682_not_passed")
    if len(source_rows) != 26:
        failures.append("source_row_count_not_26")
    if len(fixed_rows) != 26:
        failures.append("not_all_current_residuals_fixed_template_handled")
    if non_template_rows:
        failures.append("non_template_queue_not_empty_for_current_residual_set")
    if render_mismatches:
        failures.append("fixed_template_render_mismatches")
    if any(any((row.get("authority") or {}).values()) for row in fixed_rows + non_template_rows):
        failures.append("authority_rows_present")

    audit = {
        "passed": not failures,
        "failures": failures,
        "source_rows": len(source_rows),
        "fixed_template_rows": len(fixed_rows),
        "non_template_queue_rows": len(non_template_rows),
        "render_mismatch_rows": render_mismatches,
        "decision": "current_residual_slot_rows_routed_to_non_generative_renderer",
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Treat Stage9674/9675 fixed-slot residuals as renderer-handled; only build repetition-guarded denoise for future non-template residual rows."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
            "fixed_manifest": str(FIXED_MANIFEST.relative_to(ROOT)),
            "non_template_queue": str(NON_TEMPLATE_QUEUE.relative_to(ROOT)),
        },
        "decision": "Routed the current fixed-template residual set out of denoise retry; no current rows require repetition-guarded denoise.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9683 Fixed Template Residual Router",
        "",
        f"Passed: `{audit['passed']}`",
        f"Fixed-template rows: `{audit['fixed_template_rows']}`",
        f"Non-template denoise queue rows: `{audit['non_template_queue_rows']}`",
        "",
        "The current residual slot rows are all covered by the deterministic renderer path. They should not be recycled into another denoise generation retry.",
        "",
        "No training, model execution, decoder CE, denoise CE, runtime, Gemma, harness, export, merge, or promotion is authorized.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": audit["passed"],
        "failures": failures,
        "fixed_template_rows": len(fixed_rows),
        "non_template_queue_rows": len(non_template_rows),
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
