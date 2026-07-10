#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9891
NAME = "stage9891_current_margin_locality_signal_lift_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9890_current_margin_position_debiased_probe_audit.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9888_current_margin_position_bias_diagnostics/current_margin_position_debiased_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "current_margin_locality_signal_lift_manifest.jsonl"
AUDIT = OUT_DIR / "current_margin_locality_signal_lift_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CURRENT_MARGIN_LOCALITY_SIGNAL_LIFT_MANIFEST_STAGE9891.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

LOCALITY_RESOLUTION = {
    "symbol_owner_visible": "Visible locality resolution: behavior owner is a specific symbol or definition.",
    "file_responsibility_visible": "Visible locality resolution: ownership is file-level, not a specific symbol.",
    "configuration_control_visible": "Visible locality resolution: behavior is controlled by configuration rather than code ownership.",
    "test_expectation_visible": "Visible locality resolution: the failure is in the visible test expectation, not product behavior.",
    "entry_behavior_visible": "Visible locality resolution: the failure is localized to startup or entry behavior.",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
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


def build_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen_resolutions = Counter()
    by_target = defaultdict(Counter)
    for row in rows:
        cloned = json.loads(json.dumps(row))
        corrupted = cloned.get("corrupted_state") if isinstance(cloned.get("corrupted_state"), dict) else {}
        signal = str(corrupted.get("locality_signal") or "")
        resolution = LOCALITY_RESOLUTION.get(signal)
        input_state = cloned.get("input_state") if isinstance(cloned.get("input_state"), dict) else {}
        anti = cloned.get("anti_cheat") if isinstance(cloned.get("anti_cheat"), dict) else {}
        anti["stage9891_locality_signal_lifted"] = bool(resolution)
        anti["stage9891_locality_signal_raw_token_exposed"] = False
        anti["stage9891_locality_signal_source"] = "corrupted_state.locality_signal"
        cloned["anti_cheat"] = anti
        if resolution:
            input_state["visible_locality_resolution"] = resolution
            cloned["input_state"] = input_state
            seen_resolutions[resolution] += 1
            tgt = str(((cloned.get("target") or {}).get("decoder_text")) or "")
            by_target[tgt][resolution] += 1
        out.append(cloned)
    audit = {
        "rows": len(out),
        "lifted_rows": sum(seen_resolutions.values()),
        "resolution_counts": dict(sorted(seen_resolutions.items())),
        "target_resolution_counts": {k: dict(sorted(v.items())) for k, v in sorted(by_target.items())},
        "all_rows_lifted": len(out) > 0 and sum(seen_resolutions.values()) == len(out),
    }
    return out, audit


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    rows = read_jsonl(SOURCE_MANIFEST)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9890_not_passed")
    if not rows:
        failures.append("missing_source_rows")
    out_rows, lift_audit = build_rows(rows)
    write_jsonl(MANIFEST, out_rows)
    if not lift_audit["all_rows_lifted"]:
        failures.append("not_all_rows_received_locality_resolution")
    write_json(
        AUDIT,
        {
            "passed": not failures,
            "failures": failures,
            "lift_audit": lift_audit,
            "authority": dict(AUTHORITY_CLOSED),
        },
    )
    next_step = "Run Stage9892 on the locality-signal-lifted current-frontier manifest and compare whether K exact recovers without reintroducing shortcut-sensitive packet artifacts."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": failures, **lift_audit},
        "artifacts": {
            "manifest": str(MANIFEST.relative_to(ROOT)),
            "audit": str(AUDIT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Lifted the normalized locality resolution already present in upstream corrupted-state evidence into the model-visible current-frontier packet, without exposing raw label tokens or source identifiers.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(SUMMARY, summary)
    DOC.write_text(
        "\n".join(
            [
                "# Stage9891 Current Margin Locality Signal Lift Manifest",
                "",
                f"Passed: `{summary['passed']}`",
                f"Lifted rows: `{lift_audit['lifted_rows']}`",
                f"Resolution counts: `{lift_audit['resolution_counts']}`",
                "",
                summary["decision"],
                "",
                f"Next: {next_step}",
                "",
            ]
        ) + "\n",
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "failures": failures, "lifted_rows": lift_audit["lifted_rows"]}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
