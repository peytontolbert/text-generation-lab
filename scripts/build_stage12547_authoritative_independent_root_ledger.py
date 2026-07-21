#!/usr/bin/env python3
"""Build the fail-closed Stage12547 independent-root progress ledger.

Only materialized rows can establish progress.  Stage headline counters, work
orders, requested floors, and task projections are retained as discrepancies,
never promoted to roots.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12547_authoritative_independent_root_ledger"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
TARGET_ROOTS = 500

SOURCE_FILES = {
    "stage12241": ROOT / "runs/local/artifacts/stage12241_maintainer_500_root_campaign_contract/maintainer_500_root_campaign_contract.json",
    "stage12248": ROOT / "runs/local/artifacts/stage12248_root_supply_discrepancy_audit/root_supply_discrepancy_audit.json",
    "stage12448": ROOT / "runs/local/artifacts/stage12448_executor_shard_scale_and_admission_control/stage12448_executor_shard_scale_and_admission_control.json",
    "stage12533": ROOT / "runs/local/artifacts/stage12533_legacy_collapse_group_countable_repair/legacy_collapse_group_countable_repair.json",
}
MATERIALIZED_FILES = {
    "stage12448_executor_lane_orders": ROOT / "runs/local/artifacts/stage12448_executor_shard_scale_and_admission_control/executor_lane_orders.jsonl",
    "stage12533_countable_rows": ROOT / "runs/local/artifacts/stage12533_legacy_collapse_group_countable_repair/train_support_only_repaired_countable_rows.jsonl",
    "stage12533_demoted_rows": ROOT / "runs/local/artifacts/stage12533_legacy_collapse_group_countable_repair/demoted_legacy_collapse_train_support_rows.jsonl",
    "stage12533_replacement_candidates": ROOT / "runs/local/artifacts/stage12533_legacy_collapse_group_countable_repair/public_local_exact_replacement_candidates.jsonl",
}

ROOT_ID_FIELDS = ("canonical_root_id", "root_id_hash", "source_root_label_hash")
LINEAGE_FIELDS = ("canonical_lineage_id", "root_lineage_key_hash", "lineage_key_hash")
STATE_BEFORE_FIELDS = ("state_before_summary_codes", "state_before", "state_before_hash")
ACTION_FIELDS = ("observed_action_digest", "observed_action", "action_digest", "patch_application_or_no_patch_reason")
OBSERVATION_FIELDS = ("observation_status_class", "verifier_status", "verifier_output_class", "verifier_identity_hash")
STATE_DELTA_FIELDS = ("state_delta_codes", "state_after_summary_codes", "state_delta", "state_after")
SAME_SOURCE_FIELDS = ("same_source_lineage_proof", "same_source_proof", "source_lineage_checked")

KNOWN_SOURCE_NATIVE_ALIAS_GROUPS = {
    "source_episode:stage12201_episode_e547aba70f65a981": {
        "0e1d4e5d1b1f67ea75049c5f",
        "e91dbb35c01782aa28493abb",
    },
}
ZERO_CREDIT_CATEGORIES = (
    "sealed_transition",
    "causal_repair_patch_trace",
    "safe_refactor",
)



def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: expected JSON object")
            rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def present(row: dict[str, Any], fields: tuple[str, ...]) -> bool:
    return any(row.get(field) not in (None, "", [], {}, False) for field in fields)


def truthy_claim(row: dict[str, Any], fields: tuple[str, ...]) -> bool:
    return any(row.get(field) is True for field in fields)


def evidence_tokens(row: dict[str, Any], fields: tuple[str, ...]) -> list[str]:
    return [str(row[field]).strip() for field in fields if row.get(field) not in (None, "")]


def causal_proof_on_one_row(row: dict[str, Any]) -> tuple[bool, list[str]]:
    """Require structural patch-effect proof, not merely populated proof slots."""
    missing: list[str] = []
    for name, fields in (
        ("state_before", STATE_BEFORE_FIELDS),
        ("observed_action", ACTION_FIELDS),
        ("observation", OBSERVATION_FIELDS),
        ("state_delta", STATE_DELTA_FIELDS),
    ):
        if not present(row, fields):
            missing.append(name)

    if row.get("same_source_lineage_proof") is not True:
        missing.append("same_source_lineage_proof_not_explicit")
    if str(row.get("source_provenance_class") or "") not in {
        "external_repo_commit_pair",
        "source_native_external_repair",
    }:
        missing.append("external_source_provenance_not_proven")
    if row.get("controlled_fixture_like") is not False or row.get("synthetic_source") is not False:
        missing.append("nonfixture_nonsynthetic_source_not_proven")

    before_status = str(row.get("verifier_before_status") or "").upper()
    after_status = str(row.get("verifier_after_status") or "").upper()
    if before_status not in {"FAIL", "FAIL_CURRENT_STATE"}:
        missing.append("before_status_not_behavior_failure")
    if after_status not in {"PASS", "PASS_CURRENT_STATE"}:
        missing.append("after_status_not_pass")

    before_verifier = str(row.get("verifier_before_identity_hash") or "")
    after_verifier = str(row.get("verifier_after_identity_hash") or "")
    if not before_verifier or before_verifier != after_verifier:
        missing.append("same_verifier_identity_not_proven")
    before_test_tree = str(row.get("test_tree_before_hash") or "")
    after_test_tree = str(row.get("test_tree_after_hash") or "")
    if not before_test_tree or before_test_tree != after_test_tree:
        missing.append("immutable_test_tree_not_proven")
    if row.get("patch_changed_test_files_count") != 0:
        missing.append("patch_may_change_tests")
    if str(row.get("patch_apply_status") or "").upper() not in {"APPLIED", "PASS"}:
        missing.append("patch_application_not_proven")
    if row.get("revert_restores_failure") is not True:
        missing.append("revert_does_not_restore_failure")

    events = row.get("ordered_events")
    event_names: list[str] = []
    if isinstance(events, list):
        for event in events:
            if isinstance(event, dict):
                event_names.append(str(event.get("event_type") or "").upper())
            else:
                event_names.append(str(event).upper())
    required_order = ["BEFORE_VERIFIER_RESULT", "PATCH_APPLY", "AFTER_VERIFIER_RESULT"]
    positions = []
    for required in required_order:
        try:
            positions.append(event_names.index(required))
        except ValueError:
            positions.append(-1)
    if any(position < 0 for position in positions) or positions != sorted(positions):
        missing.append("ordered_before_patch_after_events_not_proven")

    if row.get("protected_overlap_audit_pass") is not True or row.get("protected_overlap_count") != 0:
        missing.append("protected_eval_overlap_not_cleared")
    return not missing, sorted(set(missing))


class UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def add(self, token: str) -> None:
        self.parent.setdefault(token, token)

    def find(self, token: str) -> str:
        parent = self.parent[token]
        if parent != token:
            self.parent[token] = self.find(parent)
        return self.parent[token]

    def union(self, left: str, right: str) -> None:
        self.add(left)
        self.add(right)
        a, b = self.find(left), self.find(right)
        if a != b:
            self.parent[max(a, b)] = min(a, b)


def identity_tokens(row: dict[str, Any]) -> tuple[list[str], list[str]]:
    roots = sorted({f"root:{value}" for value in evidence_tokens(row, ROOT_ID_FIELDS)})
    lineages = sorted({f"lineage:{value}" for value in evidence_tokens(row, LINEAGE_FIELDS)})
    return roots, lineages


def is_candidate_row(row: dict[str, Any], source_name: str) -> bool:
    if source_name == "stage12448_executor_lane_orders":
        return False
    return bool(
        identity_tokens(row)[0]
        or identity_tokens(row)[1]
        or any(key in row for key in ("countable_train_support", "strict_eval_eligible", "level3_admitted"))
    )


def classify_root(rows: list[dict[str, Any]]) -> tuple[str, list[str]]:
    causal_claim_fields = ("level3_admitted", "patch_trace_admitted", "repair_claim_admitted")
    causal_claims = [row for row in rows if truthy_claim(row, causal_claim_fields)]
    proof_results = [causal_proof_on_one_row(row) for row in causal_claims]
    reasons: list[str] = []
    if any(proved for proved, _ in proof_results):
        return "causal_repair_patch_trace", reasons
    if causal_claims:
        reasons.append("causal_claim_missing_structural_patch_effect_proof")
        reasons.extend(sorted({reason for _, missing in proof_results for reason in missing}))

    if any(row.get("strict_eval_eligible") is True or row.get("source_heldout_admissible") is True for row in rows):
        return "sealed_transition", reasons

    text = " ".join(str(value).lower() for row in rows for value in row.values() if isinstance(value, str))
    if any(row.get("safe_refactor_admitted") is True for row in rows) or "pass_to_pass" in text or "safe_refactor" in text:
        return "safe_refactor", reasons

    negative_statuses = {"INSUFFICIENT_EVIDENCE", "ABSTAIN", "ENV_BLOCKED", "NOT_COMPARABLE"}
    if any(str(row.get("verifier_status") or "").upper() in negative_statuses for row in rows) or any(
        token in text for token in ("abstain", "environment_or_dependency_blocked", "not_comparable")
    ):
        return "negative", reasons
    return "verifier_observation_auxiliary", reasons


def one_value(rows: list[dict[str, Any]], field: str, default: str = "unknown") -> str:
    values = sorted({str(row[field]) for row in rows if row.get(field) not in (None, "")})
    return values[0] if len(values) == 1 else default


def build_ledger(materialized: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    indexed: list[tuple[str, int, dict[str, Any]]] = []
    controls: list[dict[str, Any]] = []
    uf = UnionFind()

    for source_name, rows in sorted(materialized.items()):
        for index, row in enumerate(rows, 1):
            if not is_candidate_row(row, source_name):
                controls.append({"source_materialization": source_name, "source_row_number": index, "reason": "non_root_control_or_projection_order"})
                continue
            roots, lineages = identity_tokens(row)
            tokens = roots + lineages
            for token in tokens:
                uf.add(token)
            for token in tokens[1:]:
                uf.union(tokens[0], token)
            indexed.append((source_name, index, row))

    grouped: dict[str, list[tuple[str, int, dict[str, Any]]]] = defaultdict(list)
    unresolved: list[dict[str, Any]] = []
    for source_name, index, row in indexed:
        roots, lineages = identity_tokens(row)
        tokens = roots + lineages
        if not tokens:
            unresolved.append({"source_materialization": source_name, "source_row_number": index, "reason": "missing_root_and_lineage_identity", "row": row})
            continue
        grouped[uf.find(tokens[0])].append((source_name, index, row))

    ledger: list[dict[str, Any]] = []
    for component_rows in grouped.values():
        rows = [entry[2] for entry in component_rows]
        root_tokens = sorted({token for row in rows for token in identity_tokens(row)[0]})
        lineage_tokens = sorted({token for row in rows for token in identity_tokens(row)[1]})
        if len(lineage_tokens) > 1:
            for source_name, index, row in component_rows:
                unresolved.append({"source_materialization": source_name, "source_row_number": index, "reason": "ambiguous_multiple_lineages_for_identity_component", "lineage_tokens": lineage_tokens, "row": row})
            continue

        canonical = (lineage_tokens or root_tokens)[0].split(":", 1)[1]
        category, category_reasons = classify_root(rows)
        claimed_causal = any(truthy_claim(row, ("level3_admitted", "patch_trace_admitted", "repair_claim_admitted")) for row in rows)
        causal_rows = [row for row in rows if causal_proof_on_one_row(row)[0]]
        countable_rows = [row for row in rows if row.get("countable_train_support") is True and row.get("collapse_demoted_from_countable") is not True]
        source_refs = sorted({f"{source}:{index}" for source, index, _ in component_rows})
        row = {
            "canonical_identity": canonical,
            "identity_basis": "lineage" if lineage_tokens else "root",
            "root_aliases": [token.split(":", 1)[1] for token in root_tokens],
            "lineage_aliases": [token.split(":", 1)[1] for token in lineage_tokens],
            "category": category,
            "category_reasons": category_reasons,
            "language_family": one_value(rows, "language_family"),
            "split": one_value(rows, "split", one_value(rows, "bucket")),
            "repo_family_hash": one_value(rows, "repo_family_hash"),
            "source_stages": sorted({str(row.get("source_stage") or row.get("stage") or "unknown") for row in rows}),
            "source_materializations": sorted({source for source, _, _ in component_rows}),
            "source_row_refs": source_refs,
            "materialized_row_count": len(rows),
            "countable_projection_row_count": len(countable_rows),
            "demoted_projection_row_count": sum(row.get("collapse_demoted_from_countable") is True for row in rows),
            "claimed_level3_or_repair": claimed_causal,
            "same_row_causal_proof_present": bool(causal_rows),
            "level3_repair_credit": category == "causal_repair_patch_trace",
            "training_allowed": False,
        }
        ledger.append(row)

    ledger.sort(key=lambda row: row["canonical_identity"])
    unresolved.sort(key=lambda row: (row["source_materialization"], row["source_row_number"]))
    category_counts = Counter(row["category"] for row in ledger)
    language_counts = Counter(row["language_family"] for row in ledger)
    split_counts = Counter(row["split"] for row in ledger)
    return {
        "ledger": ledger,
        "unresolved": unresolved,
        "controls": controls,
        "coverage": {
            "category": dict(sorted(category_counts.items())),
            "language": dict(sorted(language_counts.items())),
            "split": dict(sorted(split_counts.items())),
        },
    }




def canonicalize_known_aliases(ledger: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_identity = {str(row["canonical_identity"]): dict(row) for row in ledger}
    alias_audit: list[dict[str, Any]] = []
    for source_native_id, aliases in sorted(KNOWN_SOURCE_NATIVE_ALIAS_GROUPS.items()):
        present_aliases = sorted(alias for alias in aliases if alias in by_identity)
        if len(present_aliases) < 2:
            alias_audit.append({
                "source_native_identity": source_native_id,
                "alias_identities": present_aliases,
                "decision": "alias_group_not_fully_present",
            })
            continue
        rows = [by_identity.pop(alias) for alias in present_aliases]
        canonical = hashlib.sha256(source_native_id.encode("utf-8")).hexdigest()[:24]
        categories = sorted({row["category"] for row in rows})
        merged = {
            **rows[0],
            "canonical_identity": canonical,
            "identity_basis": "source_native_episode_alias",
            "root_aliases": sorted({alias for row in rows for alias in row.get("root_aliases", [])}),
            "lineage_aliases": sorted({alias for row in rows for alias in row.get("lineage_aliases", [])}),
            "category": categories[0] if len(categories) == 1 else "mixed_auxiliary_requires_review",
            "category_reasons": sorted({reason for row in rows for reason in row.get("category_reasons", [])}),
            "language_family": rows[0]["language_family"] if len({row["language_family"] for row in rows}) == 1 else "unknown",
            "split": rows[0]["split"] if len({row["split"] for row in rows}) == 1 else "unknown",
            "source_stages": sorted({stage for row in rows for stage in row.get("source_stages", [])}),
            "source_materializations": sorted({source for row in rows for source in row.get("source_materializations", [])}),
            "source_row_refs": sorted({ref for row in rows for ref in row.get("source_row_refs", [])}),
            "materialized_row_count": sum(int(row.get("materialized_row_count") or 0) for row in rows),
            "countable_projection_row_count": sum(int(row.get("countable_projection_row_count") or 0) for row in rows),
            "demoted_projection_row_count": sum(int(row.get("demoted_projection_row_count") or 0) for row in rows),
            "claimed_level3_or_repair": any(row.get("claimed_level3_or_repair") is True for row in rows),
            "same_row_causal_proof_present": any(row.get("same_row_causal_proof_present") is True for row in rows),
            "level3_repair_credit": any(row.get("level3_repair_credit") is True for row in rows),
            "training_allowed": False,
        }
        by_identity[canonical] = merged
        alias_audit.append({
            "source_native_identity_digest": hashlib.sha256(source_native_id.encode("utf-8")).hexdigest(),
            "alias_identities": present_aliases,
            "canonical_identity": canonical,
            "decision": "aliases_merged",
        })
    return sorted(by_identity.values(), key=lambda row: row["canonical_identity"]), alias_audit


def legacy_root_status_counts(ledger: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "legacy_flagged_countable_auxiliary_roots": sum(
            int(row.get("countable_projection_row_count") or 0) > 0 for row in ledger
        ),
        "legacy_demoted_only_roots_pending_reaudit": sum(
            int(row.get("countable_projection_row_count") or 0) == 0
            and int(row.get("demoted_projection_row_count") or 0) > 0
            for row in ledger
        ),
        "accepted_causal_repair_roots": sum(row.get("level3_repair_credit") is True for row in ledger),
    }


def category_coverage_with_zeros(ledger: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(row.get("category") or "unknown") for row in ledger)
    for category in ZERO_CREDIT_CATEGORIES:
        counts.setdefault(category, 0)
    return dict(sorted(counts.items()))
def claimed_counter_discrepancies(sources: dict[str, dict[str, Any]], authoritative: int, materialized_rows: int) -> list[dict[str, Any]]:
    claims = [
        ("stage12241.verifier_observation_auxiliary.current_safe_candidate_rows", sources.get("stage12241", {}).get("lane_quotas", {}).get("verifier_observation_auxiliary", {}).get("current_safe_candidate_rows"), "candidate_rows_not_independent_roots"),
        ("stage12248.headline.stage12242_candidate_backlog_total_reported", sources.get("stage12248", {}).get("headline", {}).get("stage12242_candidate_backlog_total_reported"), "inherited_backlog_counter_not_materialized_identity_count"),
        ("stage12448.current_countable_supply_before_future_ingest", sources.get("stage12448", {}).get("current_countable_supply_before_future_ingest"), "inherited_supply_counter_not_materialized_identity_count"),
        ("stage12533.countable_train_support.current_countable_total", sources.get("stage12533", {}).get("countable_train_support", {}).get("current_countable_total"), "row_projection_counter_not_independent_root_count"),
        ("stage12533.source_train_support_rows", sources.get("stage12533", {}).get("source_train_support_rows"), "materialized_row_counter_not_independent_root_count"),
    ]
    output = []
    for name, claim, reason in claims:
        output.append({
            "claimed_counter": name,
            "claimed_value": claim,
            "authoritative_unique_root_count": authoritative,
            "claimed_minus_authoritative": claim - authoritative if isinstance(claim, int) else None,
            "materialized_surviving_row_count": materialized_rows,
            "reason": reason,
        })
    return output



def demotion_reaudit(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_lineage: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("collapse_demoted_from_countable") is True and row.get("root_lineage_key_hash"):
            by_lineage[str(row["root_lineage_key_hash"])].append(row)
    audit: list[dict[str, Any]] = []
    generic = {"candidate_0", "candidate_selected_test_backed"}
    for lineage, group in sorted(by_lineage.items()):
        generic_outside_candidate = any(
            str(row.get("target_semantic_value") or "") in generic
            and str(row.get("task_projection") or "") != "transition_candidate_selection"
            for row in group
        )
        targets = {str(row.get("target_semantic_value") or "") for row in group}
        single_target_across_three = len(group) >= 3 and len(targets) == 1
        false_positive = not generic_outside_candidate and not single_target_across_three
        audit.append({
            "root_lineage_key_hash": lineage,
            "demoted_projection_row_count": len(group),
            "generic_target_outside_candidate_selection": generic_outside_candidate,
            "single_target_across_three_plus_rows": single_target_across_three,
            "distinct_target_count": len(targets),
            "reaudit_decision": (
                "legacy_group_rule_false_positive_restoration_requires_separate_admission"
                if false_positive
                else "demotion_supported"
            ),
            "restoration_authorized": False,
            "training_allowed": False,
        })
    return audit


def main() -> int:
    sources = {name: read_json(path) for name, path in SOURCE_FILES.items()}
    materialized = {name: read_jsonl(path) for name, path in MATERIALIZED_FILES.items()}
    result = build_ledger(materialized)
    stage_local_ledger = result["ledger"]
    canonical_ledger, alias_audit = canonicalize_known_aliases(stage_local_ledger)
    status_counts = legacy_root_status_counts(canonical_ledger)
    demotion_audit = demotion_reaudit(materialized.get("stage12533_countable_rows", []))

    stage_local_count = len(stage_local_ledger)
    canonical_count = len(canonical_ledger)
    causal_count = status_counts["accepted_causal_repair_roots"]
    surviving_rows = len(materialized.get("stage12533_countable_rows", []))
    discrepancies = claimed_counter_discrepancies(sources, canonical_count, surviving_rows)
    missing_inputs = [
        str(path.relative_to(ROOT))
        for path in list(SOURCE_FILES.values()) + list(MATERIALIZED_FILES.values())
        if not path.exists()
    ]
    language_counts = Counter(str(row.get("language_family") or "unknown") for row in canonical_ledger)
    split_counts = Counter(str(row.get("split") or "unknown") for row in canonical_ledger)
    false_positive_demotions = sum(
        row["reaudit_decision"].startswith("legacy_group_rule_false_positive")
        for row in demotion_audit
    )

    summary = {
        "stage": STAGE,
        "record_type": "authoritative_independent_root_progress_ledger_v2",
        "decision": "training_blocked_zero_accepted_causal_roots_and_legacy_accounting_superseded",
        "claim_boundary": (
            "Metadata-only reconciliation. Materialized candidate roots, legacy countable flags, "
            "demotion re-audit, and accepted causal campaign roots are separate counters. "
            "No projection, inherited scalar, work order, or requested floor grants root admission."
        ),
        "training_allowed": False,
        "admission_allowed": False,
        "target_unique_roots": TARGET_ROOTS,
        "stage_local_identifiable_root_count": stage_local_count,
        "canonical_materialized_candidate_root_count": canonical_count,
        "canonical_candidate_gap_to_500": max(0, TARGET_ROOTS - canonical_count),
        "legacy_flagged_countable_auxiliary_root_count": status_counts["legacy_flagged_countable_auxiliary_roots"],
        "legacy_demoted_only_root_count_pending_reaudit": status_counts["legacy_demoted_only_roots_pending_reaudit"],
        "legacy_demotion_false_positive_candidate_root_count": false_positive_demotions,
        "legacy_demotion_restoration_authorized": False,
        "accepted_causal_campaign_root_count": causal_count,
        "accepted_causal_campaign_gap_to_500": max(0, TARGET_ROOTS - causal_count),
        "materialized_projection_row_count": surviving_rows,
        "projection_rows_removed_by_canonical_identity_deduplication": max(0, surviving_rows - canonical_count),
        "source_native_alias_merge_count": sum(row.get("decision") == "aliases_merged" for row in alias_audit),
        "unresolved_identity_row_count": len(result["unresolved"]),
        "non_root_control_row_count": len(result["controls"]),
        "coverage": {
            "category": category_coverage_with_zeros(canonical_ledger),
            "language": dict(sorted(language_counts.items())),
            "split": dict(sorted(split_counts.items())),
        },
        "level3_repair_credit_count": causal_count,
        "same_row_causal_proof_rule": (
            "state_before + observed_action + observation + state_delta/after + "
            "same_source proof must coexist on one materialized source row"
        ),
        "missing_inputs": missing_inputs,
        "input_complete": not missing_inputs,
        "counter_discrepancies": discrepancies,
        "next_acquisition_lane": (
            "fresh_non_bears_non_python_external_patch_effect_roots_with_same_verifier_"
            "before_fail_patch_apply_after_pass_proof"
        ),
        "artifact_refs": {
            "canonical_root_ledger": display_path(OUT / "authoritative_independent_root_ledger.jsonl"),
            "source_native_alias_audit": display_path(OUT / "source_native_alias_audit.jsonl"),
            "legacy_demotion_reaudit": display_path(OUT / "legacy_demotion_reaudit.jsonl"),
            "unresolved_identity_rows": display_path(OUT / "unresolved_identity_rows.jsonl"),
            "non_root_control_rows": display_path(OUT / "non_root_control_rows.jsonl"),
            "claimed_counter_discrepancies": display_path(OUT / "claimed_counter_discrepancies.json"),
        },
    }
    summary["summary_hash"] = hashlib.sha256(
        json.dumps(summary, sort_keys=True).encode("utf-8")
    ).hexdigest()[:24]

    write_jsonl(OUT / "authoritative_independent_root_ledger.jsonl", canonical_ledger)
    write_jsonl(OUT / "source_native_alias_audit.jsonl", alias_audit)
    write_jsonl(OUT / "legacy_demotion_reaudit.jsonl", demotion_audit)
    write_jsonl(OUT / "unresolved_identity_rows.jsonl", result["unresolved"])
    write_jsonl(OUT / "non_root_control_rows.jsonl", result["controls"])
    write_json(OUT / "claimed_counter_discrepancies.json", discrepancies)
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY, summary)
    print(SUMMARY)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
