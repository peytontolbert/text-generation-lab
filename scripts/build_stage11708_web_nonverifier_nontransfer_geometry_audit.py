#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
NAME = "stage11708_web_nonverifier_nontransfer_geometry_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_nonverifier_nontransfer_geometry_audit.json"
MISS_GEOMETRY = OUT / "web_nonverifier_miss_geometry_rows.jsonl"
SUPPORT_MATCHES = OUT / "web_nonverifier_support_geometry_matches.jsonl"

BRIDGED_ROWS = ART / "stage11690_original_web_canonical_bridge_audit/original_web_canonical_bridged_rows.jsonl"
MISS_CARDS = ART / "stage11703_web_transition_product_policy_integration_audit/web_transition_product_policy_remaining_misses.jsonl"
SUPPORT_ROWS = ART / "stage11704_web_remaining_nonverifier_support_package/web_remaining_nonverifier_support_rows.jsonl"
SUPPORT_FIT = ART / "stage11707_web_nonverifier_support_fit_delta_audit/web_nonverifier_support_fit_delta_rows.jsonl"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def options(row: dict[str, Any]) -> list[dict[str, Any]]:
    return [opt for opt in (row.get("opaque_options") or ((row.get("standalone_projection_source") or {}).get("opaque_options") or [])) if isinstance(opt, dict)]


def target_label(row: dict[str, Any]) -> str:
    return str(row.get("bounded_choice_target_label") or row.get("target_text") or (row.get("target") or {}).get("bounded_choice_target_label") or "").strip()


def opt_role(opt: dict[str, Any]) -> str:
    obj = opt.get("canonical_candidate_object") if isinstance(opt.get("canonical_candidate_object"), dict) else {}
    sem = opt.get("semantic_candidate") if isinstance(opt.get("semantic_candidate"), dict) else {}
    return str(opt.get("role") or obj.get("role") or sem.get("role") or opt.get("semantic_role") or "").strip()


def opt_value(opt: dict[str, Any]) -> str:
    obj = opt.get("canonical_candidate_object") if isinstance(opt.get("canonical_candidate_object"), dict) else {}
    sem = opt.get("semantic_candidate") if isinstance(opt.get("semantic_candidate"), dict) else {}
    return str(obj.get("value") or sem.get("canonical_value") or sem.get("option_value") or opt.get("value") or opt.get("text") or "").strip()


def option_for_label(row: dict[str, Any], label: str) -> dict[str, Any]:
    for opt in options(row):
        if str(opt.get("label") or "").strip() == str(label).strip():
            return opt
    return {}


def prompt(row: dict[str, Any]) -> str:
    return str(row.get("prompt") or row.get("input_text") or row.get("encoder_text") or row.get("text") or "")


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")


def role_signature(row: dict[str, Any]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted(Counter(opt_role(opt) for opt in options(row) if opt_role(opt)).items()))


def geometry(row: dict[str, Any], predicted_label: str | None = None) -> dict[str, Any]:
    target = target_label(row)
    target_opt = option_for_label(row, target)
    pred_opt = option_for_label(row, predicted_label or "")
    values = [opt_value(opt) for opt in options(row)]
    text = prompt(row).lower()
    return {
        "row_id": row.get("row_id"),
        "root_id": row.get("root_id"),
        "repo_id": row.get("repo_id") or row.get("repo_family"),
        "task_type": row.get("task_type"),
        "target_label": target,
        "target_role": opt_role(target_opt),
        "target_value": opt_value(target_opt),
        "predicted_label": predicted_label,
        "predicted_role": opt_role(pred_opt) if pred_opt else "",
        "predicted_value": opt_value(pred_opt) if pred_opt else "",
        "role_signature": role_signature(row),
        "candidate_change_count": sum(1 for opt in options(row) if opt_role(opt) == "candidate_change_surface"),
        "verifier_constraint_count": sum(1 for opt in options(row) if opt_role(opt) == "verifier_and_test_constraint"),
        "has_unrelated_utility_negative": any("unrelated" in norm(value) for value in values),
        "has_playwright_or_config_negative": any("playwright" in norm(value) or "config" in norm(value) for value in values),
        "has_concrete_file_path_target": "/" in opt_value(target_opt) or ".ts" in opt_value(target_opt) or ".tsx" in opt_value(target_opt),
        "has_target_source_mentioned": bool(opt_value(target_opt) and norm(opt_value(target_opt).split("::", 1)[0]) in norm(text)),
        "prompt_len": len(prompt(row)),
    }


def classify_miss(g: dict[str, Any]) -> str:
    if g["task_type"] == "symptom_localization" and g["target_role"] == "verifier_and_test_constraint" and g["predicted_role"] == "candidate_change_surface":
        return "schema_inconsistent_impl_as_verifier_vs_unrelated_surface"
    if g["task_type"] == "symptom_localization" and g["target_role"] == "candidate_change_surface" and g["predicted_role"] == "candidate_change_surface":
        return "same_role_source_localization_target_vs_neighbor"
    if g["task_type"] == "minimal_fix_selection" and g["target_role"] == "candidate_change_surface" and g["predicted_role"] == "candidate_change_surface":
        return "same_role_minimal_fix_target_vs_neighbor"
    return "other"


def support_match_lanes(row: dict[str, Any]) -> set[str]:
    g = geometry(row)
    lanes: set[str] = set()
    if g["task_type"] == "symptom_localization" and g["target_role"] == "verifier_and_test_constraint" and g["candidate_change_count"] >= 1:
        lanes.add("schema_inconsistent_impl_as_verifier_vs_unrelated_surface")
    if g["task_type"] == "symptom_localization" and g["target_role"] == "candidate_change_surface" and g["candidate_change_count"] >= 2:
        lanes.add("same_role_source_localization_target_vs_neighbor")
    if g["task_type"] == "minimal_fix_selection" and g["target_role"] == "candidate_change_surface" and g["candidate_change_count"] >= 2:
        lanes.add("same_role_minimal_fix_target_vs_neighbor")
    return lanes


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    bridged_by_id = {str(row.get("row_id")): row for row in load_jsonl(BRIDGED_ROWS)}
    miss_cards = load_jsonl(MISS_CARDS)
    support = load_jsonl(SUPPORT_ROWS)
    fit_by_id = {str(row.get("row_id")): row for row in load_jsonl(SUPPORT_FIT)}

    miss_rows: list[dict[str, Any]] = []
    for card in miss_cards:
        row = bridged_by_id[str(card["row_id"])]
        g = geometry(row, predicted_label=str(card.get("product_predicted_label") or ""))
        g["miss_family"] = classify_miss(g)
        miss_rows.append(g)
    write_jsonl(MISS_GEOMETRY, miss_rows)

    needed = Counter(row["miss_family"] for row in miss_rows)
    support_matches: list[dict[str, Any]] = []
    for row in support:
        lanes = support_match_lanes(row)
        if not lanes:
            continue
        fit = fit_by_id.get(str(row.get("row_id")), {})
        g = geometry(row, predicted_label=str(fit.get("probe_predicted_label") or ""))
        g["support_lanes"] = sorted(lanes)
        g["stage11704_lane"] = row.get("stage11704_lane")
        g["baseline_correct"] = fit.get("baseline_correct")
        g["probe_correct"] = fit.get("probe_correct")
        g["status_change"] = fit.get("status_change")
        support_matches.append(g)
    write_jsonl(SUPPORT_MATCHES, support_matches)

    support_by_family: dict[str, list[dict[str, Any]]] = {}
    for family in needed:
        support_by_family[family] = [row for row in support_matches if family in row["support_lanes"]]

    family_summary: dict[str, Any] = {}
    for family, rows in support_by_family.items():
        family_summary[family] = {
            "miss_rows": needed[family],
            "support_rows": len(rows),
            "support_roots": len({row.get("root_id") for row in rows}),
            "support_repos": dict(Counter(str(row.get("repo_id")) for row in rows).most_common()),
            "support_fit_probe_correct": sum(1 for row in rows if row.get("probe_correct") is True),
            "support_fit_baseline_correct": sum(1 for row in rows if row.get("baseline_correct") is True),
            "has_unrelated_utility_negative": sum(1 for row in rows if row.get("has_unrelated_utility_negative")),
            "has_concrete_file_path_target": sum(1 for row in rows if row.get("has_concrete_file_path_target")),
            "same_repo_family_as_miss": {
                repo: sum(1 for row in rows if str(row.get("repo_id")) == repo)
                for repo in sorted({str(m.get("repo_id")) for m in miss_rows if m["miss_family"] == family})
            },
        }

    blockers: list[str] = []
    schema_miss_count = needed.get("schema_inconsistent_impl_as_verifier_vs_unrelated_surface", 0)
    schema_support = family_summary.get("schema_inconsistent_impl_as_verifier_vs_unrelated_surface", {})
    if schema_miss_count and schema_support.get("support_rows", 0) < 20:
        blockers.append("too_few_impl_as_verifier_vs_unrelated_surface_support_rows")
    if schema_miss_count:
        blockers.append("heldout_openhands_symptom_target_role_is_verifier_constraint_while_value_is_implementation_symbol")
    if family_summary.get("same_role_source_localization_target_vs_neighbor", {}).get("same_repo_family_as_miss", {}).get("llama_stack", 0) == 0:
        blockers.append("no_exact_llama_stack_repo_family_same_role_source_support")
    if family_summary.get("same_role_minimal_fix_target_vs_neighbor", {}).get("same_repo_family_as_miss", {}).get("llama_stack", 0) == 0:
        blockers.append("no_exact_llama_stack_repo_family_minimal_fix_support")

    gates = {
        "all_misses_classified": all(row["miss_family"] != "other" for row in miss_rows),
        "support_exists_for_each_family": all(family_summary.get(family, {}).get("support_rows", 0) > 0 for family in needed),
        "stage11705_fit_support": sum(1 for row in support_matches if row.get("status_change") == "wrong_to_correct") > 0,
        "has_schema_blocker": "heldout_openhands_symptom_target_role_is_verifier_constraint_while_value_is_implementation_symbol" in blockers,
        "needs_higher_fidelity_materialization": bool(blockers),
    }
    decision = "nontransfer_explained_by_schema_and_high_fidelity_gap" if blockers else "nontransfer_unexplained_needs_scorer_change"
    summary = {
        "stage": 11708,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "miss_family_counts": dict(needed.most_common()),
        "family_summary": family_summary,
        "blockers": blockers,
        "gates": gates,
        "recommended_next": [
            "Do not rerun the same Stage11704 support mix.",
            "Normalize OpenHands symptom target role: implementation utility exercised by verifier should not be encoded only as verifier_and_test_constraint.",
            "Build high-fidelity disjoint analogues with the same candidate geometry: target implementation/file path, selected verifier, unrelated utility surface, and browser/config distractor.",
            "For Llama, materialize more exact repo-family same-role source/minimal-fix rows with concrete neighboring lib/component distractors.",
        ],
        "source_artifacts": {
            "bridged_rows": rel(BRIDGED_ROWS),
            "miss_cards": rel(MISS_CARDS),
            "support_rows": rel(SUPPORT_ROWS),
            "support_fit": rel(SUPPORT_FIT),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "miss_geometry": rel(MISS_GEOMETRY),
            "support_matches": rel(SUPPORT_MATCHES),
        },
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision, "miss_family_counts": summary["miss_family_counts"], "blockers": blockers, "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
