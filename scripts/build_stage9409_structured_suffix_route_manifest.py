#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
import time
from collections import Counter
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9409
NAME = "stage9409_structured_suffix_route_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9408_minimal_phrase_disambiguation_failure_diagnosis.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9397_heldout_contrastive_suffix_support_manifest/heldout_contrastive_suffix_support_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "structured_suffix_route_manifest.jsonl"
AUDIT = OUT_DIR / "structured_suffix_route_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "STRUCTURED_SUFFIX_ROUTE_MANIFEST_STAGE9409.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def target_text(row: dict) -> str:
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    for value in (target.get("decoder_text"), row.get("decoder_text"), row.get("clean_target")):
        if isinstance(value, str):
            return value
    return ""


ROUTE_RULES = [
    ("expected assertion behavior", ("assertion_constant_route", "assertion_behavior_preservation")),
    ("current repair invariant", ("current_invariant_route", "repair_invariant_preservation")),
    ("allowed dependency constraint", ("dependency_constraint_route", "dependency_policy_preservation")),
    ("localized repair step", ("localized_repair_route", "localized_step_preservation")),
    ("wrapper plan", ("wrapper_plan_route", "adapter_plan_preservation")),
    ("verified patch operator", ("verified_patch_operator_route", "operator_target_preservation")),
    ("repaired state", ("repaired_state_route", "state_slot_preservation")),
    ("localized edit target", ("localized_edit_target_route", "edit_target_preservation")),
    ("patch inside the whitelist", ("whitelist_patch_route", "whitelist_constraint_preservation")),
    ("checked symbol evidence", ("checked_symbol_evidence_route", "symbol_evidence_preservation")),
]


def route_for(text: str) -> tuple[str, str]:
    lowered = text.lower()
    for needle, route in ROUTE_RULES:
        if needle in lowered:
            return route
    return ("generic_suffix_route", "generic_suffix_preservation")


def stable_id(row: dict) -> str:
    digest = hashlib.sha256(str(row.get("row_id", "")).encode("utf-8")).hexdigest()[:16]
    return f"stage9409_structured_suffix_route_{digest}"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    base_rows = load_jsonl(SOURCE_MANIFEST)
    rows: list[dict] = []
    failures: list[str] = []
    for base in base_rows:
        row = copy.deepcopy(base)
        text = target_text(row)
        family, objective = route_for(text)
        model_input = row.setdefault("model_input", {})
        if not isinstance(model_input, dict):
            failures.append("bad_model_input")
            model_input = {}
            row["model_input"] = model_input
        model_input.update(
            {
                "suffix_route_schema_version": "stage9409_structured_suffix_route_v1",
                "suffix_route_family": family,
                "suffix_route_objective": objective,
                "suffix_route_control_visible": True,
                "suffix_route_control_is_not_target_text": True,
                "suffix_route_branch_source": "stage9397",
            }
        )
        row["row_id"] = stable_id(row)
        row["source_stage9397_row_id"] = base.get("row_id")
        row["objective_family"] = "structured_suffix_route_denoise_bridge"
        rows.append(row)

    split_counts = Counter(str(row.get("split")) for row in rows)
    route_counts = Counter(str((row.get("model_input") or {}).get("suffix_route_family")) for row in rows)
    loss_counts = Counter()
    authority_rows = 0
    decoder_ce_rows = 0
    exact_target_in_input_rows = 0
    for row in rows:
        loss_mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        for key, value in loss_mask.items():
            if value:
                loss_counts[key] += 1
        authority = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        if any(bool(authority.get(key)) for key in AUTHORITY_CLOSED):
            authority_rows += 1
        if loss_mask.get("decoder_ce"):
            decoder_ce_rows += 1
        text = target_text(row)
        encoder_blob = json.dumps(row.get("model_input") or {}, sort_keys=True)
        if text and text in encoder_blob:
            exact_target_in_input_rows += 1

    if source.get("passed") is not True:
        failures.append("source_stage9408_not_passed")
    if len(rows) != 31 or dict(split_counts) != {"eval": 9, "strict_eval": 7, "train": 15}:
        failures.append("unexpected_rows_or_splits")
    if loss_counts.get("denoise_ce") != 31 or len(loss_counts) != 1:
        failures.append("loss_mask_not_denoise_only")
    if authority_rows or decoder_ce_rows:
        failures.append("authority_or_decoder_ce_open")
    if exact_target_in_input_rows:
        failures.append("exact_target_text_in_model_input")
    if route_counts.get("assertion_constant_route", 0) < 3 or route_counts.get("current_invariant_route", 0) < 3:
        failures.append("target_routes_undercovered")

    write_jsonl(MANIFEST, rows)
    audit = {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "route_counts": dict(sorted(route_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "authority_rows": authority_rows,
        "decoder_ce_rows": decoder_ce_rows,
        "exact_target_in_input_rows": exact_target_in_input_rows,
        "source_basis": "stage9397",
        "excluded_bases": ["stage9401", "stage9405"],
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Added structured suffix-route controls to the Stage9397 basis without adding phrase-text support rows.",
        "next_best_step": "Run a tiny denoise-only probe to test whether visible suffix route controls recover heldout continuations without repetition.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9409 Structured Suffix Route Manifest",
                "",
                f"Passed: `{audit['passed']}`",
                f"Rows: `{len(rows)}`",
                f"Splits: `{dict(sorted(split_counts.items()))}`",
                f"Routes: `{dict(sorted(route_counts.items()))}`",
                "",
                "This branches from Stage9397 and excludes the interfering Stage9401/9405 rows. It adds route controls to model input but does not add new suffix target prose.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    reg_rows = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = reg_rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(reg_rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {"rows": len(rows), "splits": dict(sorted(split_counts.items())), "routes": dict(sorted(route_counts.items()))}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
