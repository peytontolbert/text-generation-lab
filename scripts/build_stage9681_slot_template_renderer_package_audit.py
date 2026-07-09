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
STAGE = 9681
NAME = "stage9681_slot_template_renderer_package_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9680_slot_template_renderer_reconnect_design.json"
SOURCE_DESIGN = ROOT / "runs/local/artifacts/stage9680_slot_template_renderer_reconnect_design/slot_template_renderer_reconnect_design.json"
SOURCE_RENDERED = ROOT / "runs/local/artifacts/stage9680_slot_template_renderer_reconnect_design/slot_template_renderer_heldout_predictions.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKAGE = OUT_DIR / "slot_template_renderer_package_v1.json"
AUDIT = OUT_DIR / "slot_template_renderer_package_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SLOT_TEMPLATE_RENDERER_PACKAGE_AUDIT_STAGE9681.md"
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
    design = load_json(SOURCE_DESIGN)
    rendered_rows = load_jsonl(SOURCE_RENDERED)
    template_map = design.get("template_map") if isinstance(design.get("template_map"), dict) else {}
    package = {
        "package_name": "slot_template_renderer_package_v1",
        "source_stage": 9680,
        "controller_source_stage": 9679,
        "render_mode": "deterministic_template_lookup",
        "input_field": "predicted_slot_template_label",
        "output_field": "rendered_text",
        "template_count": len(template_map),
        "template_map": template_map,
        "fallback_policy": {
            "unknown_label": "ABSTAIN_TEMPLATE_NOT_FOUND",
            "low_confidence_label": "ABSTAIN_OR_RETRIEVE_MORE",
            "confidence_threshold_recommended": 0.90,
        },
        "forbidden_runtime_behaviors": [
            "decoder_generation",
            "denoise_generation",
            "runtime_execution",
            "gemma_execution",
            "harness_execution",
            "checkpoint_export",
        ],
        "authority": dict(AUTHORITY_CLOSED),
    }
    PACKAGE.write_text(json.dumps(package, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    rerender_failures: list[dict[str, Any]] = []
    internal_token_rows: list[str] = []
    for row in rendered_rows:
        predicted = str(row.get("predicted_template_label") or "")
        rendered = str((template_map.get(predicted) or {}).get("template_text") or "")
        expected = str(row.get("expected_text") or "")
        if rendered != expected:
            rerender_failures.append({
                "row_id": row.get("row_id"),
                "predicted_template_label": predicted,
                "rendered": rendered,
                "expected": expected,
            })
        if any(token in rendered for token in ["<MTC", "<COPY:", "POLICY_", "AUTHORITY_"]):
            internal_token_rows.append(str(row.get("row_id")))

    failures: list[str] = []
    if source_summary.get("passed") is not True or design.get("passed") is not True:
        failures.append("stage9680_not_passed")
    if len(template_map) != 10:
        failures.append("template_count_not_10")
    if len(rendered_rows) != 6:
        failures.append("heldout_render_rows_not_6")
    if rerender_failures:
        failures.append("package_rerender_not_exact")
    if internal_token_rows:
        failures.append("internal_token_rows")
    if any(package["authority"].values()):
        failures.append("authority_not_closed")

    audit = {
        "passed": not failures,
        "failures": failures,
        "template_count": len(template_map),
        "heldout_rows": len(rendered_rows),
        "rerender_exact_rows": len(rendered_rows) - len(rerender_failures),
        "rerender_failures": rerender_failures,
        "internal_token_rows": internal_token_rows,
        "fallback_policy": package["fallback_policy"],
        "forbidden_runtime_behaviors": package["forbidden_runtime_behaviors"],
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Use the Stage9681 renderer package as the non-generative reconnect path; next build a controller+renderer integration preflight before any denoise generation retry."
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
            "package": str(PACKAGE.relative_to(ROOT)),
        },
        "decision": "Packaged deterministic slot-template renderer v1 as the safe reconnect path after denoise generation failed.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9681 Slot Template Renderer Package Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Template count: `{audit['template_count']}`",
        f"Heldout rerender exact: `{audit['rerender_exact_rows']}` / `{audit['heldout_rows']}`",
        "",
        "This freezes the deterministic renderer package produced from Stage9679 controller labels and Stage9680 template mapping. It is a non-generative fallback for fixed residual slot phrases.",
        "",
        "Decoder generation, denoise generation, runtime, Gemma, harness, checkpoint export, merge, and promotion remain closed.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": audit["passed"],
        "failures": failures,
        "template_count": len(template_map),
        "rerender_exact_rows": audit["rerender_exact_rows"],
        "heldout_rows": audit["heldout_rows"],
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
