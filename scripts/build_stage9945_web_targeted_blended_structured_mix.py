#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9945
NAME = "stage9945_web_targeted_blended_structured_mix"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
BLEND = OUT_DIR / "web_targeted_blended_structured_state.jsonl"
AUDIT = OUT_DIR / "web_targeted_blended_structured_mix_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "WEB_TARGETED_BLENDED_STRUCTURED_MIX_STAGE9945.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

BASE_STRUCTURED = ROOT / "runs/local/artifacts/stage9857_v27_validity_weighted_multisurface_compiler_refresh/compiled/structured_state.jsonl"
WEB_PACKET = ROOT / "runs/local/artifacts/stage9944_web_targeted_refresh_packet/compiled/structured_state.jsonl"
BASE_COMPILE_CARD = ROOT / "runs/local/artifacts/stage9857_v27_validity_weighted_multisurface_compiler_refresh/compiled/compile_card.json"
WEB_AUDIT = ROOT / "runs/local/artifacts/stage9944_web_targeted_refresh_packet/web_targeted_refresh_audit.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


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


def build_blend() -> dict[str, Any]:
    base_rows = read_jsonl(BASE_STRUCTURED)
    web_rows = read_jsonl(WEB_PACKET)
    base_card = load_json(BASE_COMPILE_CARD)
    web_audit = load_json(WEB_AUDIT)
    failures: list[str] = []

    blended = [*base_rows, *web_rows]
    write_jsonl(BLEND, blended)

    loss_counts = Counter(str(row.get("expected_enabled_loss") or "") for row in blended)
    split_counts = Counter(str(row.get("split") or "") for row in blended)
    skill_counts = Counter(str(row.get("source_skill_area") or "") for row in blended)
    language_counts = Counter(str(row.get("language_family") or "unknown") for row in blended)
    web_edit_before = sum(
        1 for row in base_rows
        if row.get("language_family") == "web_js_ts_html" and row.get("source_skill_area") == "edit_localization"
    )
    web_edit_after = sum(
        1 for row in blended
        if row.get("language_family") == "web_js_ts_html" and row.get("source_skill_area") == "edit_localization"
    )
    targeted_rows = sum(1 for row in blended if (row.get("anti_cheat") or {}).get("stage9944_target_surface"))
    weight_sum = sum(int(row.get("curriculum_priority_weight") or 0) for row in blended if row.get("curriculum_priority_weight") is not None)

    metrics = {
        "base_structured_rows": len(base_rows),
        "targeted_web_rows_added": len(web_rows),
        "blended_structured_rows": len(blended),
        "web_edit_rows_before": web_edit_before,
        "web_edit_rows_after": web_edit_after,
        "targeted_web_rows_present": targeted_rows,
        "targeted_web_weight_sum": weight_sum,
        "loss_counts": dict(sorted(loss_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "skill_counts": dict(sorted(skill_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "base_gate_rejected_rows": base_card.get("gate_rejected_rows"),
        "web_packet_gate_rejected_rows": web_audit.get("metrics", {}).get("compiler_gate_rejected_rows"),
    }

    if metrics["base_structured_rows"] != 392:
        failures.append("base_structured_rows_not_392")
    if metrics["targeted_web_rows_added"] != 12:
        failures.append("targeted_web_rows_added_not_12")
    if metrics["blended_structured_rows"] != 404:
        failures.append("blended_structured_rows_not_404")
    if metrics["web_edit_rows_before"] != 15:
        failures.append("web_edit_rows_before_not_15")
    if metrics["web_edit_rows_after"] != 27:
        failures.append("web_edit_rows_after_not_27")
    if metrics["targeted_web_rows_present"] != 12:
        failures.append("targeted_web_rows_present_not_12")
    if metrics["targeted_web_weight_sum"] != 30:
        failures.append("targeted_web_weight_sum_not_30")
    if metrics["loss_counts"].get("edit_localization_ce") != 72:
        failures.append("edit_localization_ce_not_72")
    if metrics["base_gate_rejected_rows"] != 0:
        failures.append("base_gate_rejected_rows_nonzero")
    if metrics["web_packet_gate_rejected_rows"] != 0:
        failures.append("web_packet_gate_rejected_rows_nonzero")

    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "training_recommendation": {
            "next_cycle_input": display(BLEND),
            "blend_strategy": "append the targeted web packet to the current structured-state mix and preserve curriculum_priority_weight during sampling",
            "expected_web_edit_row_delta": web_edit_after - web_edit_before,
            "why": "this raises web edit-localization coverage from 15 to 27 rows while preserving the current multilingual structured mix",
        },
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_blend()
    AUDIT.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Use this blended structured-state mix as the next 100M edit-localization training input so web_js_ts_html gets 12 additional targeted rows without changing the current anti-cheat structure."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {"blend": display(BLEND), "audit": display(AUDIT), "doc": display(DOC)},
        "decision": "Built a blended successor structured-state mix that appends the targeted web refresh packet to the current validity-weighted compiler output, materially increasing the web edit-localization share in the next training input.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9945 Web Targeted Blended Structured Mix",
        "",
        f"Passed: `{summary['passed']}`",
        f"Base structured rows: `{built['metrics']['base_structured_rows']}`",
        f"Targeted web rows added: `{built['metrics']['targeted_web_rows_added']}`",
        f"Blended structured rows: `{built['metrics']['blended_structured_rows']}`",
        f"Web edit rows before: `{built['metrics']['web_edit_rows_before']}`",
        f"Web edit rows after: `{built['metrics']['web_edit_rows_after']}`",
        "",
        summary["decision"],
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
