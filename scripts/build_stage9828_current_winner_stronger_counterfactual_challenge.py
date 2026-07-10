#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

try:
    from counterfactual_obligation_audit import audit_rows as audit_counterfactual_rows
except ModuleNotFoundError:
    from scripts.counterfactual_obligation_audit import audit_rows as audit_counterfactual_rows  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9828
NAME = "stage9828_current_winner_stronger_counterfactual_challenge"
SOURCE = ROOT / "runs/local/artifacts/stage9813_web_isolated_disambiguator_surface/web_isolated_disambiguator_surface.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "current_winner_stronger_counterfactual_challenge.jsonl"
AUDIT = OUT_DIR / "current_winner_stronger_counterfactual_challenge_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CURRENT_WINNER_STRONGER_COUNTERFACTUAL_CHALLENGE_STAGE9828.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
REQUIRED = {
    "POSITIVE_ORIGINAL",
    "EVIDENCE_REMOVED",
    "CONTRADICTORY_EVIDENCE_OR_UNSAFE_TWIN",
    "MIXED_REPLAY",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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


def strict_rows() -> list[dict[str, Any]]:
    rows = load_jsonl(SOURCE)
    return [row for row in rows if str(row.get("split") or "") == "strict_eval"]


def _clone(row: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(row))


def _group_id(row: dict[str, Any]) -> str:
    return f"cf::{row['language_family']}::{row['row_id']}"


def _visible_text_safe(row: dict[str, Any]) -> bool:
    state = row.get("input_state") if isinstance(row.get("input_state"), dict) else {}
    fields = [
        str(state.get("task_observation") or ""),
        str(state.get("visible_locality_evidence") or ""),
        " ".join(str(x) for x in (state.get("candidate_choices") or [])),
    ]
    return all("TARGET_" not in text for text in fields)


def build_rows() -> list[dict[str, Any]]:
    roots = strict_rows()
    output: list[dict[str, Any]] = []
    for idx, row in enumerate(roots):
        donor = roots[(idx + 1) % len(roots)]
        gid = _group_id(row)
        base_meta = {
            "counterfactual_group_id": gid,
            "objective_family": "edit_localization_counterfactual_guard",
            "counterfactual_root_row_id": row["row_id"],
            "counterfactual_language_family": row["language_family"],
            "counterfactual_source_stage": 9813,
            "counterfactual_challenge_stage": STAGE,
            "counterfactual_required_obligations": sorted(REQUIRED),
        }

        original = _clone(row)
        original.update(base_meta)
        original["row_id"] = f"{row['row_id']}::positive_original"
        original["obligation_type"] = "POSITIVE_ORIGINAL"
        original["counterfactual_role"] = "positive_original"
        original["counterfactual_expected_behavior"] = "prediction_should_match_original_target"
        output.append(original)

        removed = _clone(row)
        removed.update(base_meta)
        removed["row_id"] = f"{row['row_id']}::evidence_removed"
        removed["obligation_type"] = "EVIDENCE_REMOVED"
        removed["counterfactual_role"] = "evidence_removed"
        removed["counterfactual_expected_behavior"] = "performance_should_drop_or_model_should_request_more_evidence"
        removed_state = removed.get("input_state") if isinstance(removed.get("input_state"), dict) else {}
        removed_state["visible_locality_evidence"] = ""
        removed_state["context_config_visible"] = False
        removed_state["context_entrypoint_visible"] = False
        removed_state["context_symbol_names_visible"] = False
        removed_state["context_tests_visible"] = False
        removed_state["task_observation"] = str(removed_state.get("task_observation") or "") + " Counterfactual note: supporting locality details are unavailable."
        removed["input_state"] = removed_state
        output.append(removed)

        contradictory = _clone(row)
        contradictory.update(base_meta)
        contradictory["row_id"] = f"{row['row_id']}::contradictory_evidence"
        contradictory["obligation_type"] = "CONTRADICTORY_EVIDENCE_OR_UNSAFE_TWIN"
        contradictory["counterfactual_role"] = "contradictory_evidence"
        contradictory["counterfactual_expected_behavior"] = "prediction_should_follow_substituted_causal_evidence"
        contradictory["counterfactual_donor_row_id"] = donor["row_id"]
        contradictory_state = contradictory.get("input_state") if isinstance(contradictory.get("input_state"), dict) else {}
        donor_state = donor.get("input_state") if isinstance(donor.get("input_state"), dict) else {}
        contradictory_state["visible_locality_evidence"] = donor_state.get("visible_locality_evidence")
        contradictory_state["task_observation"] = donor_state.get("task_observation")
        contradictory_state["context_config_visible"] = donor_state.get("context_config_visible")
        contradictory_state["context_entrypoint_visible"] = donor_state.get("context_entrypoint_visible")
        contradictory_state["context_symbol_names_visible"] = donor_state.get("context_symbol_names_visible")
        contradictory_state["context_tests_visible"] = donor_state.get("context_tests_visible")
        contradictory["input_state"] = contradictory_state
        contradictory_target = contradictory.get("target") if isinstance(contradictory.get("target"), dict) else {}
        donor_target = donor.get("target") if isinstance(donor.get("target"), dict) else {}
        contradictory_target["decoder_text"] = donor_target.get("decoder_text")
        contradictory_target["edit_localization"] = donor_target.get("edit_localization")
        contradictory_target["target_ref"] = donor_target.get("target_ref")
        contradictory["target"] = contradictory_target
        contradictory_clean = contradictory.get("clean_state") if isinstance(contradictory.get("clean_state"), dict) else {}
        donor_clean = donor.get("clean_state") if isinstance(donor.get("clean_state"), dict) else {}
        contradictory_clean["edit_localization"] = donor_clean.get("edit_localization")
        contradictory_clean["edit_localization_target"] = donor_clean.get("edit_localization_target")
        contradictory_clean["edit_localization_target_hidden"] = donor_clean.get("edit_localization_target_hidden")
        contradictory["clean_state"] = contradictory_clean
        output.append(contradictory)

        mixed = _clone(row)
        mixed.update(base_meta)
        mixed["row_id"] = f"{row['row_id']}::mixed_replay"
        mixed["obligation_type"] = "MIXED_REPLAY"
        mixed["counterfactual_role"] = "mixed_replay"
        mixed["counterfactual_expected_behavior"] = "prediction_should_ignore_decoy_and_resist_label_proxy_shortcuts"
        mixed["counterfactual_wrong_label"] = donor_target.get("decoder_text")
        mixed_state = mixed.get("input_state") if isinstance(mixed.get("input_state"), dict) else {}
        wrong_label = str(donor_target.get("decoder_text") or "")
        mixed_state["task_observation"] = str(mixed_state.get("task_observation") or "") + f" Stale unrelated reviewer note mentions option {wrong_label}; ignore irrelevant references."
        mixed_state["visible_locality_evidence"] = str(mixed_state.get("visible_locality_evidence") or "") + " Counterfactual mix: one decoy hint is intentionally irrelevant."
        mixed["input_state"] = mixed_state
        output.append(mixed)

    return output


def build_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    cf = audit_counterfactual_rows(rows, required=REQUIRED)
    obligation_counts = Counter(str(row.get("obligation_type") or "") for row in rows)
    lang_counts = Counter(str(row.get("language_family") or "") for row in rows)
    visible_target_literal_rows = [str(row.get("row_id") or "") for row in rows if not _visible_text_safe(row)]
    failures: list[str] = []
    if len(rows) != 80:
        failures.append(f"rows_not_80:{len(rows)}")
    if len({str(row.get('counterfactual_group_id') or '') for row in rows}) != 20:
        failures.append("groups_not_20")
    for obligation in sorted(REQUIRED):
        if obligation_counts.get(obligation) != 20:
            failures.append(f"obligation_count_mismatch:{obligation}:{obligation_counts.get(obligation, 0)}")
    if visible_target_literal_rows:
        failures.append("visible_target_literals_present")
    if not cf.get("counterfactual_obligations_complete"):
        failures.append("counterfactual_obligations_incomplete")
    return {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "groups": len({str(row.get('counterfactual_group_id') or '') for row in rows}),
        "obligation_counts": dict(sorted(obligation_counts.items())),
        "language_counts": dict(sorted(lang_counts.items())),
        "visible_target_literal_rows": visible_target_literal_rows,
        "counterfactual_obligation_card": cf,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    write_jsonl(MANIFEST, rows)
    audit = build_audit(rows)
    write_json(AUDIT, audit)
    next_step = "Use the stage9828 challenge manifest as the rerun surface for the current same-surface multilingual winner so causal flips, evidence removal, and mixed decoys are measured on the exact packet that currently beats Gemma."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "rows": audit["rows"], "groups": audit["groups"], "obligation_counts": audit["obligation_counts"], "language_counts": audit["language_counts"], "failures": audit["failures"]},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Built a stronger same-packet counterfactual challenge bank for the current multilingual winner with complete sibling-group obligations across original, evidence-removed, contradictory-evidence, and mixed-replay variants.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9828 Current Winner Stronger Counterfactual Challenge",
                "",
                f"Passed: `{audit['passed']}`",
                f"Rows: `{audit['rows']}`",
                f"Groups: `{audit['groups']}`",
                f"Obligation counts: `{audit['obligation_counts']}`",
                f"Language counts: `{audit['language_counts']}`",
                "",
                "This stage upgrades the current same-surface multilingual winner from weak inherited probes to a real rerun-ready challenge bank with explicit clustered siblings.",
                "",
                f"Next: {next_step}",
                "",
            ]
        ) + "\n",
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "rows": audit["rows"], "groups": audit["groups"], "failures": audit["failures"]}, indent=2, sort_keys=True))
    if audit["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
