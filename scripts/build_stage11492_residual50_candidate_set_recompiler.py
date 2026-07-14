#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"

STAGE = 11492
NAME = "stage11492_residual50_candidate_set_recompiler"
OUT = ART / NAME
SUMMARY = OUT / "residual50_candidate_set_recompiler.json"
ROWS_OUT = OUT / "residual50_candidate_set_rows.jsonl"
GROUPS_OUT = OUT / "residual50_candidate_set_groups.jsonl"
QUARANTINE_OUT = OUT / "residual50_candidate_set_quarantine_rows.jsonl"

RESIDUAL50 = ART / "stage11481_residual50_ready_package_with_rust_counters/residual50_ready_rows.jsonl"
STAGE11491 = ART / "stage11491_residual50_listwise_group_compiler/residual50_listwise_group_compiler.json"
FILTERED_VALIDATION = ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_validation.jsonl"
FILTERED_STRICT = ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
RESIDUAL_BANK = ART / "stage11442_targeted_residual_role_support_package/semantic_candidate_residual_bank.jsonl"

ROLE_PRIORITY = {
    "verifier_and_test_constraint": 0,
    "symptom_or_call_path_analogue": 1,
    "candidate_change_surface": 2,
    "nearby_definition_or_usage_context": 3,
}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def sha16(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def row_id(row: dict[str, Any]) -> str:
    return str(row.get("row_id") or "")


def root_key(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("source_root_id") or row.get("root_lineage_key") or row.get("row_id") or "")


def prompt_text(row: dict[str, Any]) -> str:
    return str(row.get("input_text") or row.get("prompt_text") or row.get("prompt") or "")


def evidence_state_text(row: dict[str, Any]) -> str:
    text = prompt_text(row)
    text = re.split(r"\nOptions:\n", text, maxsplit=1)[0]
    return "\n".join(line.rstrip() for line in text.splitlines()).strip()


def state_hash(row: dict[str, Any]) -> str:
    return sha16(evidence_state_text(row))


def group_key(row: dict[str, Any]) -> str:
    return f"{root_key(row)}::state::{state_hash(row)}"


def options(row: dict[str, Any]) -> list[dict[str, str]]:
    source = row.get("standalone_projection_source") if isinstance(row.get("standalone_projection_source"), dict) else {}
    raw = source.get("opaque_options") or row.get("opaque_options") or []
    out: list[dict[str, str]] = []
    for option in raw:
        if not isinstance(option, dict):
            continue
        label = str(option.get("label") or "").strip()
        value = str(option.get("value") or "").strip()
        if label and value:
            out.append({"label": label, "value": value})
    return out


def normalized_role(value: str) -> str:
    mapping = {
        "SUPPORTING_CANDIDATE_CHANGE_SURFACE": "candidate_change_surface",
        "DECISIVE_VERIFIER_TEST_CONSTRAINT": "verifier_and_test_constraint",
        "DECISIVE_SELECTED_TEST_CONSTRAINT": "verifier_and_test_constraint",
        "DECISIVE_BUILD_VERIFIER_CONSTRAINT": "verifier_and_test_constraint",
        "OBSERVED_VERIFIER_LOG": "symptom_or_call_path_analogue",
        "OBSERVED_VERIFIER_PASS_LOG": "symptom_or_call_path_analogue",
        "OBSERVED_VERIFIER_FAILURE_LOG": "symptom_or_call_path_analogue",
        "SUPPORTING_SYMPTOM_OR_CALL_PATH": "symptom_or_call_path_analogue",
        "DISTRACTOR_BACKGROUND_CONTEXT": "nearby_definition_or_usage_context",
    }
    return mapping.get(value, value)


def target_value(row: dict[str, Any]) -> str:
    target = str(row.get("bounded_choice_target_label") or row.get("target_text") or row.get("decoder_text") or "").strip()
    for option in options(row):
        if option["label"] == target:
            return option["value"]
    return ""


def target_role(row: dict[str, Any]) -> str:
    return normalized_role(target_value(row))


def option_roles(row: dict[str, Any]) -> set[str]:
    return {normalized_role(option["value"]) for option in options(row)}


def choose_representative(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return sorted(rows, key=lambda row: (ROLE_PRIORITY.get(target_role(row), 99), row_id(row)))[0]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    residual50 = read_jsonl(RESIDUAL50)
    stage11491 = read_json(STAGE11491)
    protected = read_jsonl(FILTERED_VALIDATION) + read_jsonl(FILTERED_STRICT) + read_jsonl(RESIDUAL_BANK)
    protected_row_ids = {row_id(row) for row in protected}
    protected_roots = {root_key(row) for row in protected}

    by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in residual50:
        by_group[group_key(row)].append(row)

    selected_rows: list[dict[str, Any]] = []
    quarantine_rows: list[dict[str, Any]] = []
    group_records: list[dict[str, Any]] = []
    quarantine_reasons = Counter()
    role_counts = Counter()
    language_counts = Counter()
    option_role_coverage = Counter()

    for key, rows in sorted(by_group.items()):
        representative = choose_representative(rows)
        selected_id = row_id(representative)
        candidate_set_id = f"cs_{sha16(key)}"
        group_target_roles = Counter(target_role(row) for row in rows)
        selected_role = target_role(representative)
        row_overlap = sorted(row_id(row) for row in rows if row_id(row) in protected_row_ids)
        root_overlap = sorted({root_key(row) for row in rows if root_key(row) in protected_roots})
        option_roles_for_rep = sorted(option_roles(representative))
        has_required_hard_negative = any(role in option_roles_for_rep and role != selected_role for role in ("candidate_change_surface", "verifier_and_test_constraint", "symptom_or_call_path_analogue"))
        admissible = bool(options(representative)) and not row_overlap and not root_overlap and has_required_hard_negative

        group_records.append(
            {
                "candidate_set_id": candidate_set_id,
                "root_id": root_key(representative),
                "state_hash": state_hash(representative),
                "input_rows": len(rows),
                "selected_row_id": selected_id,
                "selected_target_role": selected_role,
                "input_target_roles": dict(sorted(group_target_roles.items())),
                "option_roles": option_roles_for_rep,
                "admissible_candidate_set": admissible,
                "row_ids": [row_id(row) for row in rows],
                "quarantined_sibling_row_ids": [row_id(row) for row in rows if row_id(row) != selected_id],
                "protected_row_overlaps": row_overlap,
                "protected_root_overlaps": root_overlap,
            }
        )

        for row in rows:
            payload = dict(row)
            source = dict(payload.get("standalone_projection_source") or {})
            source["candidate_set_id"] = candidate_set_id
            source["listwise_group_id"] = candidate_set_id
            source["listwise_state_hash"] = state_hash(representative)
            source["listwise_target_role"] = target_role(row)
            source["candidate_set_recompile_policy"] = "role_priority_dedupe_verifier_then_symptom_then_candidate"
            payload["standalone_projection_source"] = source
            payload["candidate_set_id"] = candidate_set_id
            payload["listwise_group_id"] = candidate_set_id
            payload["listwise_state_hash"] = state_hash(representative)
            payload["listwise_target_role"] = target_role(row)
            payload["candidate_set_recompile_policy"] = "role_priority_dedupe_verifier_then_symptom_then_candidate"
            if row_id(row) == selected_id and admissible:
                selected_rows.append(payload)
                role_counts[target_role(row)] += 1
                language_counts[str(row.get("language_family") or "unknown")] += 1
                for role in option_roles_for_rep:
                    option_role_coverage[role] += 1
            else:
                reasons = []
                if row_id(row) != selected_id:
                    reasons.append("contradictory_sibling_quarantined_by_role_priority")
                if row_overlap:
                    reasons.append("protected_row_overlap")
                if root_overlap:
                    reasons.append("protected_root_overlap")
                if not options(representative):
                    reasons.append("missing_options")
                if not has_required_hard_negative:
                    reasons.append("missing_required_hard_negative_role")
                if row_id(row) == selected_id and not reasons:
                    reasons.append("candidate_set_not_admissible")
                for reason in reasons:
                    quarantine_reasons[reason] += 1
                q = dict(payload)
                q["candidate_set_quarantine_reasons"] = reasons
                q["candidate_set_selected_row_id"] = selected_id
                quarantine_rows.append(q)

    write_jsonl(ROWS_OUT, selected_rows)
    write_jsonl(GROUPS_OUT, group_records)
    write_jsonl(QUARANTINE_OUT, quarantine_rows)

    candidate_sets = len(selected_rows)
    language_ok = all(language_counts.get(lang, 0) > 0 for lang in ("python", "c_cpp", "rust"))
    minimum_groups_ok = candidate_sets >= 30
    no_protected_overlap = not any(record["protected_row_overlaps"] or record["protected_root_overlaps"] for record in group_records)
    has_core_roles = all(option_role_coverage.get(role, 0) > 0 for role in ("candidate_change_surface", "verifier_and_test_constraint", "symptom_or_call_path_analogue"))
    passed = minimum_groups_ok and language_ok and no_protected_overlap and has_core_roles
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": passed,
        "decision": "residual50_candidate_sets_ready_for_listwise_probe" if passed else "residual50_candidate_sets_still_blocked",
        "metrics": {
            "input_rows": len(residual50),
            "input_state_groups": len(by_group),
            "candidate_set_rows": len(selected_rows),
            "quarantined_rows": len(quarantine_rows),
            "quarantine_reasons": dict(sorted(quarantine_reasons.items())),
            "selected_target_role_counts": dict(sorted(role_counts.items())),
            "selected_language_counts": dict(sorted(language_counts.items())),
            "option_role_coverage_counts": dict(sorted(option_role_coverage.items())),
            "minimum_groups_ok": minimum_groups_ok,
            "language_ok": language_ok,
            "no_protected_overlap": no_protected_overlap,
            "has_core_roles": has_core_roles,
        },
        "recompile_policy": [
            "Group rows by root_id plus visible evidence-state hash.",
            "For conflicting groups, keep one representative row using priority: verifier_and_test_constraint, symptom_or_call_path_analogue, candidate_change_surface, then context.",
            "Keep hard negatives inside the selected row's opaque_options; quarantine contradictory sibling labels.",
            "Attach candidate_set_id/listwise_group_id to selected rows and source metadata.",
        ],
        "caveats": [
            "This repairs training geometry by dropping contradictory sibling labels; it is a support package, not promotable heldout evidence.",
            "The selected candidate_set rows are still compact bounded-choice rows; they do not prove freeform repair capability.",
        ],
        "next_stage_contract": {
            "recommended_stage": "stage11493_residual50_candidate_set_listwise_probe_request",
            "goal": "train one controlled probe on the repaired candidate-set rows with Stage11444 initialization and selected product scorer",
            "promotion_requires": [
                "old canary strict 23/23",
                "filtered strict 22/22",
                "filtered validation >=20/22",
                "old validation >=21/23",
                "residual bank >=6/10",
                "full bounded-choice coverage",
            ],
            "if_probe_fails": "Stop Residual-50 training probes and implement a new scorer head/objective consumed directly at evaluation.",
        },
        "stage11491_reference": {
            "decision": stage11491.get("decision"),
            "training_admissible": stage11491.get("training_admissible"),
        },
        "source_artifacts": {
            "residual50_rows": rel(RESIDUAL50),
            "stage11491": rel(STAGE11491),
            "filtered_validation": rel(FILTERED_VALIDATION),
            "filtered_strict": rel(FILTERED_STRICT),
            "residual_bank": rel(RESIDUAL_BANK),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "candidate_set_rows": rel(ROWS_OUT),
            "candidate_set_groups": rel(GROUPS_OUT),
            "quarantine_rows": rel(QUARANTINE_OUT),
        },
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"passed": passed, "decision": summary["decision"], "metrics": summary["metrics"], "next_stage_contract": summary["next_stage_contract"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
