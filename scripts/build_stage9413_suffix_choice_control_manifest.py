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
STAGE = 9413
NAME = "stage9413_suffix_choice_control_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9412_structured_suffix_route_failure_diagnosis.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9409_structured_suffix_route_manifest/structured_suffix_route_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "suffix_choice_control_manifest.jsonl"
AUDIT = OUT_DIR / "suffix_choice_control_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SUFFIX_CHOICE_CONTROL_MANIFEST_STAGE9413.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

LOSS_MASK = {
    "surface_role_ce": False,
    "repair_surface_ce": False,
    "build_mode_ce": False,
    "allowed_import_policy_ce": False,
    "blocked_import_policy_ce": False,
    "repo_dependency_policy_ce": False,
    "action_sequence_ce": False,
    "file_plan_ce": False,
    "symbol_binding_ce": False,
    "edit_localization_ce": False,
    "patch_operator_ce": False,
    "verifier_repair_ce": False,
    "suffix_choice_ce": True,
    "decoder_ce": False,
    "denoise_ce": False,
    "runtime_reward": False,
}

CHOICE_RULES = [
    ("expected assertion behavior", "expected_assertion_behavior__keep_value_small"),
    ("current repair invariant", "current_repair_invariant__do_not_introduce"),
    ("allowed dependency constraint", "dependency_constraint__keep_output_limited"),
    ("localized repair step", "localized_repair_step__keep_response"),
    ("wrapper plan", "wrapper_plan__keep_answer_focused"),
    ("verified patch operator", "verified_patch_operator__use_repo"),
    ("repaired state", "repaired_state__keep_answer_focused"),
    ("localized edit target", "localized_edit_target__keep_path_reference"),
    ("patch inside the whitelist", "whitelist_patch__use_symbol"),
    ("checked symbol evidence", "checked_symbol_evidence__keep_decision_compatible"),
]


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


def suffix_choice_for(text: str) -> str:
    lowered = text.lower()
    for needle, choice in CHOICE_RULES:
        if needle in lowered:
            return choice
    return "generic_suffix_choice"


def stable_id(row: dict) -> str:
    digest = hashlib.sha256(str(row.get("row_id", "")).encode("utf-8")).hexdigest()[:16]
    return f"stage9413_suffix_choice_{digest}"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    source_rows = load_jsonl(SOURCE_MANIFEST)
    rows: list[dict] = []
    failures: list[str] = []
    for base in source_rows:
        row = copy.deepcopy(base)
        text = target_text(row)
        choice = suffix_choice_for(text)
        row["row_id"] = stable_id(base)
        row["source_stage9409_row_id"] = base.get("row_id")
        row["objective_family"] = "suffix_choice_control"
        row["loss_mask"] = dict(LOSS_MASK)
        clean = row.get("clean_state") if isinstance(row.get("clean_state"), dict) else {}
        clean["suffix_choice"] = choice
        row["clean_state"] = clean
        target = row.get("target") if isinstance(row.get("target"), dict) else {}
        target["suffix_choice"] = choice
        row["target"] = target
        model_input = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        model_input.update(
            {
                "suffix_choice_schema_version": "stage9413_suffix_choice_control_v1",
                "suffix_choice_target_hidden_from_model_input": True,
                "suffix_choice_control_objective": True,
                "suffix_choice_uses_prefix_and_route_only": True,
            }
        )
        row["model_input"] = model_input
        rows.append(row)

    split_counts = Counter(str(row.get("split")) for row in rows)
    choice_counts = Counter(str((row.get("clean_state") or {}).get("suffix_choice")) for row in rows)
    loss_counts = Counter()
    authority_rows = 0
    target_leak_rows = 0
    for row in rows:
        mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        for key, value in mask.items():
            if value:
                loss_counts[key] += 1
        authority = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        if any(bool(authority.get(key)) for key in AUTHORITY_CLOSED):
            authority_rows += 1
        choice = str((row.get("clean_state") or {}).get("suffix_choice"))
        model_blob = json.dumps(row.get("model_input") or {}, sort_keys=True)
        if choice and choice in model_blob:
            target_leak_rows += 1

    if source.get("passed") is not True:
        failures.append("source_stage9412_not_passed")
    if len(rows) != 31 or dict(split_counts) != {"eval": 9, "strict_eval": 7, "train": 15}:
        failures.append("unexpected_rows_or_splits")
    if loss_counts.get("suffix_choice_ce") != 31 or len(loss_counts) != 1:
        failures.append("loss_mask_not_suffix_choice_only")
    if authority_rows:
        failures.append("authority_open")
    if target_leak_rows:
        failures.append("suffix_choice_label_leaked_to_model_input")
    if choice_counts.get("expected_assertion_behavior__keep_value_small", 0) != 3:
        failures.append("expected_assertion_choice_coverage_bad")
    if choice_counts.get("current_repair_invariant__do_not_introduce", 0) != 3:
        failures.append("current_invariant_choice_coverage_bad")

    write_jsonl(MANIFEST, rows)
    audit = {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "choice_counts": dict(sorted(choice_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "authority_rows": authority_rows,
        "target_leak_rows": target_leak_rows,
        "source_basis": "stage9409_structured_suffix_route_manifest",
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
        "decision": "Materialized suffix-choice control rows with suffix_choice_ce only; decoder and denoise generation losses remain closed.",
        "next_best_step": "Run a structured-policy probe for suffix_choice exactness before reconnecting to denoise generation.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9413 Suffix Choice Control Manifest",
                "",
                f"Passed: `{audit['passed']}`",
                f"Rows: `{len(rows)}`",
                f"Splits: `{dict(sorted(split_counts.items()))}`",
                f"Choices: `{dict(sorted(choice_counts.items()))}`",
                "",
                "This is a structured control objective: `suffix_choice_ce` only. Decoder CE and denoise CE remain closed.",
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
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {"rows": len(rows), "splits": dict(sorted(split_counts.items())), "choices": dict(sorted(choice_counts.items()))}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
