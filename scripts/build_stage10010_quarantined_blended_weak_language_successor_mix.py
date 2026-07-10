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
STAGE = 10010
NAME = "stage10010_quarantined_blended_weak_language_successor_mix"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
BLEND = OUT_DIR / "quarantined_blended_weak_language_successor_structured_state.jsonl"
AUDIT = OUT_DIR / "quarantined_blended_weak_language_successor_mix_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "QUARANTINED_BLENDED_WEAK_LANGUAGE_SUCCESSOR_MIX_STAGE10010.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

BASE_STRUCTURED = ROOT / "runs/local/artifacts/stage10009_quarantined_blended_v27_mix/quarantined_blended_structured_state.jsonl"
RECOVERY_PACKET = ROOT / "runs/local/artifacts/stage9961_blended_weak_language_recovery_packet/compiled/structured_state.jsonl"
BASE_AUDIT = ROOT / "runs/local/artifacts/stage10009_quarantined_blended_v27_mix/quarantined_blended_v27_mix_audit.json"
RECOVERY_AUDIT = ROOT / "runs/local/artifacts/stage9961_blended_weak_language_recovery_packet/blended_weak_language_recovery_audit.json"


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


def _edit_rows(rows: list[dict[str, Any]], lang: str) -> int:
    return sum(
        1
        for row in rows
        if row.get("language_family") == lang and row.get("source_skill_area") == "edit_localization"
    )


def build_blend() -> dict[str, Any]:
    base_rows = read_jsonl(BASE_STRUCTURED)
    recovery_rows = read_jsonl(RECOVERY_PACKET)
    base_audit = load_json(BASE_AUDIT)
    recovery_audit = load_json(RECOVERY_AUDIT)
    failures: list[str] = []

    blended = [*base_rows, *recovery_rows]
    write_jsonl(BLEND, blended)

    loss_counts = Counter(str(row.get("expected_enabled_loss") or "") for row in blended)
    split_counts = Counter(str(row.get("split") or "") for row in blended)
    skill_counts = Counter(str(row.get("source_skill_area") or "") for row in blended)
    language_counts = Counter(str(row.get("language_family") or "unknown") for row in blended)

    metrics = {
        "base_structured_rows": len(base_rows),
        "recovery_rows_added": len(recovery_rows),
        "blended_structured_rows": len(blended),
        "edit_localization_rows_before": sum(1 for row in base_rows if row.get("source_skill_area") == "edit_localization"),
        "edit_localization_rows_after": sum(1 for row in blended if row.get("source_skill_area") == "edit_localization"),
        "python_edit_rows_before": _edit_rows(base_rows, "python"),
        "python_edit_rows_after": _edit_rows(blended, "python"),
        "c_cpp_edit_rows_before": _edit_rows(base_rows, "c_cpp"),
        "c_cpp_edit_rows_after": _edit_rows(blended, "c_cpp"),
        "rust_edit_rows_before": _edit_rows(base_rows, "rust"),
        "rust_edit_rows_after": _edit_rows(blended, "rust"),
        "web_edit_rows_before": _edit_rows(base_rows, "web_js_ts_html"),
        "web_edit_rows_after": _edit_rows(blended, "web_js_ts_html"),
        "recovery_rows_present": sum(1 for row in blended if (row.get("anti_cheat") or {}).get("stage9961_root_family")),
        "recovery_weight_sum": sum(
            int(row.get("curriculum_priority_weight") or 0)
            for row in blended
            if (row.get("anti_cheat") or {}).get("stage9961_root_family")
        ),
        "loss_counts": dict(sorted(loss_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "skill_counts": dict(sorted(skill_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "base_rows_removed_from_stale_blend": int((base_audit.get("metrics") or {}).get("rows_removed_from_active_blend") or 0),
        "base_gate_rejected_rows": 0,
        "recovery_gate_rejected_rows": recovery_audit.get("metrics", {}).get("compiler_gate_rejected_rows"),
    }

    if metrics["base_structured_rows"] != 396:
        failures.append("base_structured_rows_not_396")
    if metrics["recovery_rows_added"] != 48:
        failures.append("recovery_rows_added_not_48")
    if metrics["blended_structured_rows"] != 444:
        failures.append("blended_structured_rows_not_444")
    if metrics["edit_localization_rows_before"] != 64:
        failures.append("edit_localization_rows_before_not_64")
    if metrics["edit_localization_rows_after"] != 112:
        failures.append("edit_localization_rows_after_not_112")
    if metrics["python_edit_rows_after"] != 19:
        failures.append("python_edit_rows_after_not_19")
    if metrics["c_cpp_edit_rows_after"] != 27:
        failures.append("c_cpp_edit_rows_after_not_27")
    if metrics["rust_edit_rows_after"] != 21:
        failures.append("rust_edit_rows_after_not_21")
    if metrics["web_edit_rows_after"] != 45:
        failures.append("web_edit_rows_after_not_45")
    if metrics["recovery_rows_present"] != 48:
        failures.append("recovery_rows_present_not_48")
    if metrics["recovery_weight_sum"] != 147:
        failures.append("recovery_weight_sum_not_147")
    if metrics["loss_counts"].get("edit_localization_ce") != 112:
        failures.append("edit_localization_ce_not_112")
    if metrics["base_rows_removed_from_stale_blend"] != 8:
        failures.append("base_rows_removed_from_stale_blend_not_8")
    if metrics["recovery_gate_rejected_rows"] != 0:
        failures.append("recovery_gate_rejected_rows_nonzero")

    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "training_recommendation": {
            "next_cycle_input": display(BLEND),
            "blend_strategy": "append the stage9961 weak-language recovery packet to the quarantined blended v2.7 mix and preserve curriculum_priority_weight during sampling",
            "expected_edit_localization_row_delta": metrics["edit_localization_rows_after"] - metrics["edit_localization_rows_before"],
            "why": "this keeps the web recovery gains and weak-language replay roots while excluding unresolved Gemma-advantage rows from the training/eval path.",
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
        "Use this quarantined successor blended structured-state mix as the next 100M edit-localization training input so python, c_cpp, and web_js_ts_html weak roots are replayed together without reintroducing unresolved Gemma-advantage rows."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {"blend": display(BLEND), "audit": display(AUDIT), "doc": display(DOC)},
        "decision": "Built a quarantined weak-language successor mix that appends the stage9961 recovery rows to the stage10009 filtered v2.7 blend, preserving multilingual weak-root coverage while keeping unresolved Gemma-advantage eval rows out of the active path.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage10010 Quarantined Blended Weak-Language Successor Mix",
        "",
        f"Passed: `{summary['passed']}`",
        f"Base structured rows: `{built['metrics']['base_structured_rows']}`",
        f"Recovery rows added: `{built['metrics']['recovery_rows_added']}`",
        f"Blended structured rows: `{built['metrics']['blended_structured_rows']}`",
        f"Edit-localization rows after: `{built['metrics']['edit_localization_rows_after']}`",
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
