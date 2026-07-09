#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9680
NAME = "stage9680_slot_template_renderer_reconnect_design"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9679_slot_template_controller_probe_audit.json"
CONTROLLER_MANIFEST = ROOT / "runs/local/artifacts/stage9678_slot_template_controller_preexecution/slot_template_controller_manifest.jsonl"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9674_neutral_slot_prior_denoise_preexecution/neutral_slot_prior_denoise_manifest.jsonl"
CONTROLLER_RUN_DIR = ROOT / "runs/local/artifacts/stage9679_slot_template_controller_probe"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DESIGN = OUT_DIR / "slot_template_renderer_reconnect_design.json"
RENDERED_HELDOUT = OUT_DIR / "slot_template_renderer_heldout_predictions.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SLOT_TEMPLATE_RENDERER_RECONNECT_DESIGN_STAGE9680.md"
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


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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
    controller_rows = load_jsonl(CONTROLLER_MANIFEST)
    source_rows = load_jsonl(SOURCE_MANIFEST)
    logits = [row for row in load_jsonl(CONTROLLER_RUN_DIR / "row_field_logits.jsonl") if row.get("field") == "suffix_choice"]
    source_by_id = {str(row.get("row_id")): row for row in source_rows}
    controller_by_id = {str(row.get("row_id")): row for row in controller_rows}

    template_map: dict[str, dict[str, str]] = {}
    template_conflicts: dict[str, list[str]] = {}
    for row in controller_rows:
        source = source_by_id.get(str(row.get("source_stage9674_row_id")), {})
        label = str((row.get("target") or {}).get("suffix_choice") or "")
        text = target_text(source)
        if not label or not text:
            continue
        previous = template_map.get(label, {}).get("template_text")
        if previous and previous != text:
            template_conflicts.setdefault(label, [previous]).append(text)
        template_map[label] = {
            "template_text": text,
            "template_text_sha256": sha256_text(text),
            "renderer_source": "stage9674_clean_target_template_table_not_model_input",
        }

    rendered_rows: list[dict[str, Any]] = []
    for record in logits:
        controller_row = controller_by_id.get(str(record.get("row_id")), {})
        source = source_by_id.get(str(controller_row.get("source_stage9674_row_id")), {})
        predicted = str(record.get("pred") or "")
        target_label = str(record.get("target") or "")
        expected_text = target_text(source)
        rendered_text = template_map.get(predicted, {}).get("template_text", "")
        rendered_rows.append({
            "row_id": record.get("row_id"),
            "source_stage9674_row_id": controller_row.get("source_stage9674_row_id"),
            "split": record.get("split"),
            "predicted_template_label": predicted,
            "target_template_label": target_label,
            "label_correct": bool(record.get("correct")),
            "rendered_text": rendered_text,
            "expected_text": expected_text,
            "render_exact": rendered_text == expected_text,
            "controller_confidence": record.get("confidence"),
            "controller_margin": record.get("margin"),
            "render_source": "deterministic_template_table",
        })
    write_jsonl(RENDERED_HELDOUT, rendered_rows)

    heldout_rows = [row for row in rendered_rows if row.get("split") in {"eval", "strict_eval"}]
    render_exact_rows = sum(1 for row in heldout_rows if row.get("render_exact"))
    label_exact_rows = sum(1 for row in heldout_rows if row.get("label_correct"))
    failures: list[str] = []
    if source_summary.get("passed") is not True:
        failures.append("stage9679_not_passed")
    if len(template_map) != 10:
        failures.append("template_count_not_10")
    if template_conflicts:
        failures.append("template_label_conflicts")
    if len(heldout_rows) != 6:
        failures.append("heldout_prediction_rows_not_6")
    if label_exact_rows != len(heldout_rows):
        failures.append("controller_label_miss_on_heldout")
    if render_exact_rows != len(heldout_rows):
        failures.append("deterministic_render_not_exact_on_heldout")
    if any(row.get("rendered_text", "").strip() == "" for row in heldout_rows):
        failures.append("empty_rendered_text")
    internal_tokens = ["<MTC", "<COPY:", "POLICY_", "AUTHORITY_"]
    if any(token in (rendered.get("rendered_text") or "") for rendered in heldout_rows for token in internal_tokens):
        failures.append("internal_token_in_rendered_text")

    design = {
        "passed": not failures,
        "failures": failures,
        "source_stage": 9679,
        "mode": "deterministic_slot_template_renderer_reconnect_design",
        "template_count": len(template_map),
        "template_conflicts": template_conflicts,
        "heldout_prediction_rows": len(heldout_rows),
        "heldout_label_exact_rows": label_exact_rows,
        "heldout_render_exact_rows": render_exact_rows,
        "heldout_render_exact_rate": render_exact_rows / len(heldout_rows) if heldout_rows else None,
        "renderer_inputs": [
            "predicted_slot_template_label_from_stage9679_controller",
            "deterministic_template_table",
        ],
        "renderer_forbidden_inputs": [
            "raw_decoder_generation",
            "denoise_generation",
            "runtime",
            "gemma",
            "harness",
            "full_target_text_in_model_input",
        ],
        "template_map": template_map,
        "authority": dict(AUTHORITY_CLOSED),
    }
    DESIGN.write_text(json.dumps(design, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Build Stage9681 deterministic slot-template renderer audit package or integrate renderer output as a non-generative fallback before any further denoise reconnect."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": design["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **design},
        "artifacts": {
            "design": str(DESIGN.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
            "rendered_heldout": str(RENDERED_HELDOUT.relative_to(ROOT)),
        },
        "decision": "Designed deterministic slot-template rendering from the passing Stage9679 controller; this avoids reopening denoise generation for fixed residual slot phrases.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9680 Slot Template Renderer Reconnect Design",
        "",
        f"Passed: `{design['passed']}`",
        f"Template count: `{design['template_count']}`",
        f"Heldout render exact: `{render_exact_rows}` / `{len(heldout_rows)}`",
        "",
        "Stage9679 proved the 100M structured head can select the residual slot-template label. Stage9680 designs the safer reconnect: render the bounded answer from a deterministic template table instead of reopening denoise/free-form generation for these fixed phrases.",
        "",
        "No model execution, decoder CE, denoise CE, runtime, Gemma, harness, checkpoint export, merge, or promotion is authorized here.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": design["passed"],
        "failures": failures,
        "template_count": len(template_map),
        "heldout_render_exact_rows": render_exact_rows,
        "heldout_rows": len(heldout_rows),
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
