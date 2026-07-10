#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from curriculum_compiler import compile_rows
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
    from golden_locked_eval_suite import load_locked_source_ids_from_exclusions
except ModuleNotFoundError:
    from scripts.curriculum_compiler import compile_rows  # type: ignore
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from scripts.golden_locked_eval_suite import load_locked_source_ids_from_exclusions  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9944
NAME = "stage9944_web_targeted_refresh_packet"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "web_targeted_refresh_manifest.jsonl"
AUDIT = OUT_DIR / "web_targeted_refresh_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "WEB_TARGETED_REFRESH_PACKET_STAGE9944.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
COMPILED_DIR = OUT_DIR / "compiled"
LOCKED_EXCLUSIONS = ROOT / "runs/local/artifacts/stage9685_locked_multilingual_task_pack_skeleton/v27_locked_source_exclusions.jsonl"

SOURCE = ROOT / "runs/local/artifacts/stage9833_permuted_choice_execution_manifest/permuted_choice_execution_manifest.jsonl"

WEAK_SURFACES = {
    "test_surface": {"weight": 3, "error_family": "test_vs_product_disambiguation"},
    "entrypoint_or_invocation_surface": {"weight": 3, "error_family": "entrypoint_vs_config_disambiguation"},
    "implementation_file_surface": {"weight": 3, "error_family": "file_scope_vs_symbol_scope_disambiguation"},
}
ANCHOR_SURFACE = {"symbol_definition_or_implementation_surface": {"weight": 1, "error_family": "symbol_owner_anchor"}}


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


def _choice_map(row: dict[str, Any]) -> dict[str, str]:
    choices = (row.get("input_state") or {}).get("candidate_choices") or []
    mapping: dict[str, str] = {}
    for item in choices:
        if isinstance(item, str) and item.startswith("option ") and ": " in item:
            label = item[7]
            mapping[label] = item.split(": ", 1)[1].strip()
    return mapping


def _target_surface(row: dict[str, Any]) -> str:
    target = (row.get("target") or {}).get("edit_localization") if isinstance(row.get("target"), dict) else row.get("target")
    return _choice_map(row).get(str(target), "unknown")


def _normalize_row(row: dict[str, Any], target_surface: str, weight: int, error_family: str) -> dict[str, Any]:
    out = json.loads(json.dumps(row))
    out["row_id"] = f"stage9944_{row.get('row_id')}"
    out["source_row_id"] = row.get("row_id")
    out["expected_enabled_loss"] = "edit_localization_ce"
    out["source_skill_area"] = "edit_localization"
    out["locked_guard_refresh_stage"] = NAME
    out["authority"] = dict(AUTHORITY_CLOSED)
    anti = out.get("anti_cheat") if isinstance(out.get("anti_cheat"), dict) else {}
    anti["stage9944_targeted_web_refresh"] = True
    anti["stage9944_target_surface"] = target_surface
    out["anti_cheat"] = anti
    out["curriculum_priority_weight"] = weight
    out["curriculum_refresh_family"] = error_family
    out["curriculum_refresh_scope"] = "web_js_ts_html_edit_localization_targeted_refresh"
    return out


def build_rows() -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    source_rows = [row for row in read_jsonl(SOURCE) if row.get("language_family") == "web_js_ts_html"]
    failures: list[str] = []
    selected: list[dict[str, Any]] = []

    for row in source_rows:
        surface = _target_surface(row)
        if surface in WEAK_SURFACES:
            meta = WEAK_SURFACES[surface]
            selected.append(_normalize_row(row, surface, meta["weight"], meta["error_family"]))
        elif surface in ANCHOR_SURFACE:
            meta = ANCHOR_SURFACE[surface]
            selected.append(_normalize_row(row, surface, meta["weight"], meta["error_family"]))

    surface_counts = Counter(str(row.get("anti_cheat", {}).get("stage9944_target_surface", "")) for row in selected)
    split_counts = Counter(str(row.get("split") or "") for row in selected)
    weight_sum = sum(int(row.get("curriculum_priority_weight") or 0) for row in selected)

    if surface_counts.get("test_surface", 0) != 3:
        failures.append("test_surface_rows_not_3")
    if surface_counts.get("entrypoint_or_invocation_surface", 0) != 3:
        failures.append("entrypoint_surface_rows_not_3")
    if surface_counts.get("implementation_file_surface", 0) != 3:
        failures.append("implementation_file_surface_rows_not_3")
    if surface_counts.get("symbol_definition_or_implementation_surface", 0) != 3:
        failures.append("symbol_anchor_rows_not_3")
    if split_counts.get("train", 0) != 4 or split_counts.get("eval", 0) != 4 or split_counts.get("strict_eval", 0) != 4:
        failures.append("split_counts_not_4_each")

    audit = {
        "rows": len(selected),
        "surface_counts": dict(sorted(surface_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "weight_sum": weight_sum,
    }
    return selected, audit, failures


def compile_packet(rows: list[dict[str, Any]]) -> dict[str, Any]:
    locked_source_ids = load_locked_source_ids_from_exclusions(LOCKED_EXCLUSIONS)
    buckets, card = compile_rows(
        rows,
        allow_decoder=False,
        allow_denoise=False,
        allow_runtime=False,
        require_recovered_gates=True,
        locked_source_ids=locked_source_ids,
    )
    COMPILED_DIR.mkdir(parents=True, exist_ok=True)
    for objective, bucket_rows in buckets.items():
        write_jsonl(COMPILED_DIR / f"{objective}.jsonl", bucket_rows)
    (COMPILED_DIR / "compile_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return card


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    rows, audit_metrics, failures = build_rows()
    write_jsonl(MANIFEST, rows)
    compile_card = compile_packet(rows)
    audit = {
        "passed": not failures,
        "failures": failures,
        "metrics": {
            **audit_metrics,
            "compiler_gate_rejected_rows": compile_card.get("gate_rejected_rows"),
            "compiler_locked_source_exclusion_rows": compile_card.get("locked_source_exclusion_rows"),
            "compiler_loss_counts": compile_card.get("loss_counts"),
        },
        "training_recommendation": {
            "mix_strategy": "blend this packet into the next 100M edit-localization cycle with weak-surface oversampling preserved by curriculum_priority_weight",
            "focus_surfaces": sorted(WEAK_SURFACES.keys()),
            "anchor_surface": "symbol_definition_or_implementation_surface",
            "why": "web_js_ts_html currently misses every test, entrypoint, and implementation-file row while only solving symbol-owner rows",
        },
        "authority": dict(AUTHORITY_CLOSED),
    }
    if compile_card.get("gate_rejected_rows") != 0:
        audit["failures"].append("compiler_gate_rejected_rows_nonzero")
    if compile_card.get("locked_source_exclusion_rows") != 0:
        audit["failures"].append("compiler_locked_source_exclusion_rows_nonzero")
    audit["passed"] = not audit["failures"]
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    next_step = (
        "Blend this targeted web refresh packet into the next valid 100M edit-localization cycle so test-surface, entrypoint-surface, and implementation-file rows are oversampled while symbol-owner rows remain as anchors."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit["metrics"], "failures": audit["failures"]},
        "artifacts": {
            "manifest": display(MANIFEST),
            "compiled_dir": display(COMPILED_DIR),
            "compile_card": display(COMPILED_DIR / "compile_card.json"),
            "audit": display(AUDIT),
            "doc": display(DOC),
        },
        "decision": "Built a targeted web refresh packet from the live edit-localization source manifest that isolates the three currently missed web semantics and preserves one symbol-owner anchor row per split under the existing opaque-choice anti-cheat structure.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9944 Web Targeted Refresh Packet",
        "",
        f"Passed: `{summary['passed']}`",
        f"Rows: `{audit['metrics']['rows']}`",
        f"Surface counts: `{audit['metrics']['surface_counts']}`",
        f"Split counts: `{audit['metrics']['split_counts']}`",
        f"Weight sum: `{audit['metrics']['weight_sum']}`",
        "",
        summary["decision"],
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": audit["metrics"], "failures": audit["failures"]}, indent=2, sort_keys=True))
    if audit["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
