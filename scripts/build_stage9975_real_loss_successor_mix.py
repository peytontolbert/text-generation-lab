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
STAGE = 9975
NAME = "stage9975_real_loss_successor_mix"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
BLEND = OUT_DIR / "real_loss_successor_structured_state.jsonl"
AUDIT = OUT_DIR / "real_loss_successor_mix_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REAL_LOSS_SUCCESSOR_MIX_STAGE9975.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

BASE_STRUCTURED = ROOT / "runs/local/artifacts/stage9962_blended_weak_language_successor_mix/blended_weak_language_successor_structured_state.jsonl"
LOSS_PACKET = ROOT / "runs/local/artifacts/stage9974_real_same_manifest_loss_recovery_packet/real_same_manifest_loss_recovery_rows.jsonl"
BASE_AUDIT = ROOT / "runs/local/artifacts/stage9962_blended_weak_language_successor_mix/blended_weak_language_successor_mix_audit.json"
LOSS_AUDIT = ROOT / "runs/local/artifacts/stage9974_real_same_manifest_loss_recovery_packet/real_same_manifest_loss_recovery_packet.json"


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
    loss_rows = read_jsonl(LOSS_PACKET)
    base_audit = load_json(BASE_AUDIT)
    loss_audit = load_json(LOSS_AUDIT)
    failures: list[str] = []

    blended = [*base_rows, *loss_rows]
    write_jsonl(BLEND, blended)

    loss_counts = Counter(str(row.get("expected_enabled_loss") or "") for row in blended)
    split_counts = Counter(str(row.get("split") or "") for row in blended)
    skill_counts = Counter(str(row.get("source_skill_area") or "") for row in blended)
    language_counts = Counter(str(row.get("language_family") or "unknown") for row in blended)
    reason_counts = Counter(str(row.get("recovery_reason") or "") for row in blended if row.get("recovery_reason"))

    metrics = {
        "base_structured_rows": len(base_rows),
        "loss_rows_added": len(loss_rows),
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
        "loss_rows_present": sum(1 for row in blended if row.get("recovery_reason")),
        "loss_reason_counts": dict(sorted(reason_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "skill_counts": dict(sorted(skill_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "base_gate_rejected_rows": base_audit.get("metrics", {}).get("base_gate_rejected_rows"),
        "loss_packet_rows": loss_audit.get("metrics", {}).get("rows"),
    }

    if metrics["base_structured_rows"] != 452:
        failures.append("base_structured_rows_not_452")
    if metrics["loss_rows_added"] != 32:
        failures.append("loss_rows_added_not_32")
    if metrics["blended_structured_rows"] != 484:
        failures.append("blended_structured_rows_not_484")
    if metrics["edit_localization_rows_before"] != 120:
        failures.append("edit_localization_rows_before_not_120")
    if metrics["edit_localization_rows_after"] != 152:
        failures.append("edit_localization_rows_after_not_152")
    if metrics["python_edit_rows_after"] != 40:
        failures.append("python_edit_rows_after_not_40")
    if metrics["c_cpp_edit_rows_after"] != 46:
        failures.append("c_cpp_edit_rows_after_not_46")
    if metrics["rust_edit_rows_after"] != 21:
        failures.append("rust_edit_rows_after_not_21")
    if metrics["web_edit_rows_after"] != 45:
        failures.append("web_edit_rows_after_not_45")
    if metrics["loss_rows_present"] != 32:
        failures.append("loss_rows_present_not_32")
    if metrics["loss_counts"].get("edit_localization_ce") != 152:
        failures.append("edit_localization_ce_not_152")

    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "training_recommendation": {
            "next_cycle_input": display(BLEND),
            "blend_strategy": "append the real stage9974 post-Gemma loss packet to the stage9962 successor mix and preserve the existing weak-language/web anchors",
            "expected_edit_localization_row_delta": metrics["edit_localization_rows_after"] - metrics["edit_localization_rows_before"],
            "why": "this focuses the next cycle on the actual observed losing python rows and the c_cpp strict regression while retaining the existing rust/web wins.",
        },
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_blend()
    AUDIT.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Use this real-loss successor mix as the next 100M edit-localization training input, then rerun the same-manifest comparison to check whether python and c_cpp strict recover without giving back rust or web."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {"blend": display(BLEND), "audit": display(AUDIT), "doc": display(DOC)},
        "decision": "Built a real-loss successor mix that appends the actual stage9974 post-comparison recovery rows to the stage9962 weak-language successor mix, concentrating the next cycle on python and c_cpp strict failures.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9975 Real Loss Successor Mix",
        "",
        f"Passed: `{summary['passed']}`",
        f"Base structured rows: `{built['metrics']['base_structured_rows']}`",
        f"Loss rows added: `{built['metrics']['loss_rows_added']}`",
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
