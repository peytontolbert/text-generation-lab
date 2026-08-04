#!/usr/bin/env python3
"""Independently review Stage12683 repaired precise-link rows."""
from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12684_precise_link_semantic_repair_independent_review_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
UPSTREAM = ROOT / "runs/local/artifacts/stage12683_precise_link_semantic_repair_preflight_only"

INPUTS = {
    "stage12683_summary": ROOT / "runs/summaries/stage12683_precise_link_semantic_repair_preflight_only.json",
    "stage12683_audit": UPSTREAM / "precise_link_semantic_repair_audit.json",
    "stage12683_contract": UPSTREAM / "contract.json",
    "stage12683_pointer": UPSTREAM / "digest_pointer.json",
    "stage12683_private_packet": UPSTREAM / "private/precise_link_semantic_repair_packet.json",
    "stage12683_checks": UPSTREAM / "private/precise_link_semantic_repair_checks.jsonl",
    "stage12683_rows": UPSTREAM / "private/precise_link_semantic_repair_rows.jsonl",
    "stage12683_builder": ROOT / "scripts/build_stage12683_precise_link_semantic_repair_preflight_only.py",
    "stage12683_tests": ROOT / "tests/test_stage12683_precise_link_semantic_repair_preflight_only.py",
}
EXPECTED_HASHES = {
    "stage12683_summary": "b54ffa7660d2243835a7ff61c8e847decbe3a37c1b65d59898e2c8a7e2318d4c",
    "stage12683_audit": "0a7931ffcfa03ca5a3d864bb53e07e0fc9227c794026a879750c18db408444b3",
    "stage12683_contract": "13784ebe738e64608c2eaa78c3cf13d87e052f65e77f45df83dc44b7e26c1a00",
    "stage12683_pointer": "3be9736bd76a19bfdd70902427fcd1a2508efef885357565037cb04405d77482",
    "stage12683_private_packet": "207d8a63552ce1022c7440d65787d7a746d7da00a2c870b32353a951061d4fcc",
    "stage12683_checks": "d23b7f9cb060250561ea3b0f95553e3615dea3ae99e13716fbfa0cf9e9a6439e",
    "stage12683_rows": "3253d8af1543b1242eab6f223ee08fe35da88294663e859c1921bc8c446c9b8d",
    "stage12683_builder": "0e63bba99d5d5c66b7f4420da1fbd0efade62eb4dabfb37aa338766b2329c2ce",
    "stage12683_tests": "e5f9bb90a1d5284bfd39ca30115c4480a8c8d6aee046c2babd0208d449067a14",
}
EXPECTED_OBJECTIVES = {
    "doc_build_literal_symbol_association": 11514,
    "language_pattern_symbol_definition_relation": 38576,
    "python_absolute_import_symbol_resolution": 4114,
    "python_ast_symbol_definition_relation": 63688,
}
EXPECTED_SPLITS = {"eval": 18228, "strict_eval": 14348, "train": 85316}
RELATION_PAIRS = {
    "doc_build_literal_symbol_association": {
        "literal_symbol_associates_candidate", "candidate_is_not_unique_definition_file_for_literal"
    },
    "language_pattern_symbol_definition_relation": {
        "language_pattern_observed_symbol_definition", "language_pattern_did_not_observe_symbol_definition"
    },
    "python_absolute_import_symbol_resolution": {
        "absolute_import_resolves_candidate", "absolute_import_does_not_resolve_candidate"
    },
    "python_ast_symbol_definition_relation": {
        "python_ast_observed_symbol_definition", "python_ast_did_not_observe_symbol_definition"
    },
}
FALSE_FIELDS = (
    "implementation_ready", "stage12685_allowed", "training_allowed", "training_run_allowed",
    "training_admitted", "gpu_allocation_requested", "cuda2_training_allowed", "vm_runner_execution_allowed",
    "runtime_authorized", "replay_trustworthy", "level_3_materialized", "model_execution_authorized_next",
    "optimizer_step_authorized", "source_emission_authorized", "body_emission_authorized",
    "sealed_eval_admitted", "sealed_eval_eligible", "strict_eval_admitted", "strict_eval_eligible",
    "strict_eval_authorized", "sealed_eval_authorized", "loss_authorized", "compiler_execution_authorized",
    "gemma_execution_authorized_next",
)
UPSTREAM_FALSE_FIELDS = tuple(field for field in FALSE_FIELDS if field != "stage12685_allowed") + ("stage12684_allowed",)
FORBIDDEN = ("/data/", "/arxiv/", "PLACEHOLDER", "placeholder", "TODO", "TBD", "Answer:", "<fill", "\x00")


class Stage12684ReviewError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12684ReviewError("json_object_required:" + path.name)
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise Stage12684ReviewError(f"jsonl_object_required:{line_number}")
            rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n"
    with path.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii") + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def false_fields() -> dict[str, bool]:
    return {field: False for field in FALSE_FIELDS}


def scalar_values(value: Any) -> set[str]:
    if isinstance(value, Mapping):
        result: set[str] = set()
        for item in value.values():
            result.update(scalar_values(item))
        return result
    if isinstance(value, list):
        result = set()
        for item in value:
            result.update(scalar_values(item))
        return result
    return {str(value)} if isinstance(value, (str, int, float, bool)) else set()


def check_false(record: Mapping[str, Any], label: str, fields: tuple[str, ...]) -> None:
    for field in fields:
        if record.get(field) is not False:
            raise Stage12684ReviewError(f"{label}_gate_drift:{field}")


def assert_no_forbidden(value: Any, label: str) -> None:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True)
    for needle in FORBIDDEN:
        if needle in encoded:
            raise Stage12684ReviewError(f"{label}_forbidden_substring:{needle}")


def load_inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    for label, path in INPUTS.items():
        if sha256_bytes(path.read_bytes()) != EXPECTED_HASHES[label]:
            raise Stage12684ReviewError("pin_drift:" + label)
    summary = read_json(INPUTS["stage12683_summary"])
    audit = read_json(INPUTS["stage12683_audit"])
    contract = read_json(INPUTS["stage12683_contract"])
    for label, record in (("summary", summary), ("audit", audit), ("contract", contract)):
        check_false(record, "stage12683_" + label, UPSTREAM_FALSE_FIELDS)
    if summary.get("recommended_next_stage") != STAGE or audit.get("next_required_action") != STAGE:
        raise Stage12684ReviewError("stage12683_next_action_drift")
    rows = read_jsonl(INPUTS["stage12683_rows"])
    if len(rows) != 117892:
        raise Stage12684ReviewError("row_count_drift")
    return summary, audit, contract, rows


def review_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    objective_counts = dict(sorted(collections.Counter(str(row.get("objective_family")) for row in rows).items()))
    split_counts = dict(sorted(collections.Counter(str(row.get("split")) for row in rows).items()))
    if objective_counts != EXPECTED_OBJECTIVES or split_counts != EXPECTED_SPLITS:
        raise Stage12684ReviewError("count_drift")
    row_ids: set[str] = set()
    semantic: collections.Counter[str] = collections.Counter()
    input_targets: dict[str, set[str]] = collections.defaultdict(set)
    repo_splits: dict[str, set[str]] = collections.defaultdict(set)
    pairs: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    metrics = collections.Counter()
    for key in (
        "duplicate_row_ids", "schema_error_rows", "unsupported_relation_rows", "authority_open_rows",
        "raw_source_body_rows", "absolute_path_rows", "target_file_identity_rows", "forbidden_marker_rows",
        "target_leak_rows", "source_traceable_rows", "split_endpoint_traceable_rows",
        "target_derived_occurrence_proof_rows", "import_rows", "import_rows_missing_module_context",
        "import_positive_rows", "import_positive_rows_missing_package_root_provenance",
        "definition_rows", "definition_rows_missing_declaration_shape",
        "lexical_rows", "lexical_scope_errors",
    ):
        metrics[key] = 0
    for row in rows:
        row_id = str(row.get("row_id"))
        metrics["duplicate_row_ids"] += row_id in row_ids
        row_ids.add(row_id)
        input_state, expected, evidence = row.get("input_state"), row.get("expected_output"), row.get("evidence")
        authority, quality = row.get("authority"), row.get("quality")
        if not all(isinstance(value, dict) for value in (input_state, expected, evidence, authority, quality)):
            metrics["schema_error_rows"] += 1
            continue
        objective, split = str(row.get("objective_family")), str(row.get("split"))
        relation = str(expected.get("relationship"))
        metrics["unsupported_relation_rows"] += relation not in RELATION_PAIRS.get(objective, set())
        metrics["authority_open_rows"] += any(value is not False for value in authority.values())
        metrics["raw_source_body_rows"] += evidence.get("raw_source_body_included") is not False
        metrics["absolute_path_rows"] += evidence.get("absolute_path_included") is not False
        metrics["target_file_identity_rows"] += evidence.get("target_file_identity_included") is not False
        encoded = json.dumps(row, sort_keys=True, ensure_ascii=True)
        metrics["forbidden_marker_rows"] += any(needle in encoded for needle in FORBIDDEN)
        metrics["target_leak_rows"] += bool(scalar_values(expected) & (scalar_values(input_state) | scalar_values(evidence)))
        provenance = {**input_state, **evidence}
        has_source_digest = bool(provenance.get("source_file_digest") or provenance.get("reference_file_digest"))
        has_source_location = bool(provenance.get("source_span") or provenance.get("source_line"))
        metrics["source_traceable_rows"] += has_source_digest and has_source_location
        metrics["split_endpoint_traceable_rows"] += has_source_digest and bool(provenance.get("candidate_file_digest"))
        # The pinned Stage12683 builder hashes `relation` into this field, so every proof is target-derived.
        metrics["target_derived_occurrence_proof_rows"] += bool(evidence.get("occurrence_proof_digest"))
        repo_splits[str(input_state.get("repository_context_id"))].add(split)
        semantic[stable_hash({"objective": objective, "split": split, "input": input_state, "target": expected, "evidence": evidence})] += 1
        input_targets[stable_hash({"objective": objective, "input": input_state})].add(stable_hash(expected))
        pairs[str(evidence.get("contrast_pair_digest"))].append(row)
        if objective == "python_absolute_import_symbol_resolution":
            metrics["import_rows"] += 1
            metrics["import_rows_missing_module_context"] += not bool(input_state.get("imported_module"))
            is_positive = relation == "absolute_import_resolves_candidate"
            metrics["import_positive_rows"] += is_positive
            package_root_keys = {"package_root", "package_root_digest", "module_search_roots", "resolver_context"}
            metrics["import_positive_rows_missing_package_root_provenance"] += is_positive and not bool(
                package_root_keys & set(provenance)
            )
        elif objective in {"python_ast_symbol_definition_relation", "language_pattern_symbol_definition_relation"}:
            metrics["definition_rows"] += 1
            metrics["definition_rows_missing_declaration_shape"] += not bool(input_state.get("declaration_shape"))
        elif objective == "doc_build_literal_symbol_association":
            metrics["lexical_rows"] += 1
            metrics["lexical_scope_errors"] += input_state.get("association_scope") != "literal_token_only" or quality.get("lexical_association_only") is not True
    malformed_pairs = candidate_only_pairs = 0
    for values in pairs.values():
        if len(values) != 2:
            malformed_pairs += 1
            continue
        left, right = values
        left_base, right_base = dict(left["input_state"]), dict(right["input_state"])
        left_candidate, right_candidate = left_base.pop("candidate_file", None), right_base.pop("candidate_file", None)
        valid = (
            left["objective_family"] == right["objective_family"]
            and left["split"] == right["split"]
            and left_base == right_base
            and left_candidate != right_candidate
            and {left["expected_output"]["relationship"], right["expected_output"]["relationship"]}
            == RELATION_PAIRS[left["objective_family"]]
        )
        if valid:
            candidate_only_pairs += 1
        else:
            malformed_pairs += 1
    def majority_accuracy(key_fields: Iterable[Any]) -> float:
        buckets: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
        for row, key in zip(rows, key_fields):
            bucket = stable_hash([row["objective_family"], key])
            buckets[bucket][row["expected_output"]["relationship"]] += 1
        return sum(max(counts.values()) for counts in buckets.values()) / len(rows)

    candidate_context_accuracy = majority_accuracy(row["input_state"]["candidate_file"] for row in rows)
    symbol_context_accuracy = majority_accuracy(
        {key: value for key, value in row["input_state"].items() if key != "candidate_file"}
        for row in rows
    )
    row_id_parity_accuracy = majority_accuracy(
        int(str(row["row_id"]).rsplit("_", 1)[-1]) % 2 for row in rows
    )
    return {
        "rows_reviewed": len(rows),
        "objective_counts": objective_counts,
        "split_counts": split_counts,
        **{key: int(value) for key, value in sorted(metrics.items())},
        "semantic_duplicate_excess_rows": sum(count - 1 for count in semantic.values() if count > 1),
        "identical_input_multiple_target_groups": sum(1 for targets in input_targets.values() if len(targets) > 1),
        "cross_split_repository_context_groups": sum(1 for splits in repo_splits.values() if len(splits) > 1),
        "contrast_pair_groups": len(pairs),
        "candidate_only_valid_contrast_pairs": candidate_only_pairs,
        "malformed_contrast_pairs": malformed_pairs,
        "independently_auditable_source_rows": int(metrics["source_traceable_rows"]),
        "independently_auditable_split_endpoint_rows": int(metrics["split_endpoint_traceable_rows"]),
        "candidate_context_majority_accuracy": round(candidate_context_accuracy, 6),
        "symbol_context_majority_accuracy": round(symbol_context_accuracy, 6),
        "objective_aware_row_id_parity_accuracy": round(row_id_parity_accuracy, 6),
    }


def build_packet() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    upstream_summary, upstream_audit, upstream_contract, rows = load_inputs()
    review = review_rows(rows)
    structural_passed = all(review.get(key, 0) == 0 for key in (
        "duplicate_row_ids", "schema_error_rows", "unsupported_relation_rows", "authority_open_rows",
        "raw_source_body_rows", "absolute_path_rows", "target_file_identity_rows", "forbidden_marker_rows",
        "target_leak_rows", "semantic_duplicate_excess_rows", "identical_input_multiple_target_groups",
        "cross_split_repository_context_groups", "malformed_contrast_pairs", "import_rows_missing_module_context",
        "definition_rows_missing_declaration_shape", "lexical_scope_errors",
    ))
    provenance_passed = review["independently_auditable_source_rows"] == review["rows_reviewed"]
    split_audit_passed = review["independently_auditable_split_endpoint_rows"] == review["rows_reviewed"]
    import_resolution_passed = review["import_positive_rows_missing_package_root_provenance"] == 0
    target_metadata_passed = review["target_derived_occurrence_proof_rows"] == 0
    row_id_shortcut_passed = review["objective_aware_row_id_parity_accuracy"] <= 0.5
    candidate_context_passed = review["candidate_context_majority_accuracy"] <= 0.55
    decision = "BLOCKED_PRECISE_LINK_TARGET_DERIVED_METADATA_PROVENANCE_IMPORT_AND_SHORTCUT_CONTEXT"
    next_stage = "stage12685_precise_link_provenance_import_and_adapter_repair_preflight_only"
    summary = {
        "record_type": "stage12684_public_precise_link_semantic_repair_independent_review_summary_v1",
        "stage": STAGE,
        "decision": decision,
        "upstream_stage": upstream_summary["stage"],
        "upstream_rows_sha256": upstream_contract["rows_sha256"],
        "rows_reviewed": review["rows_reviewed"],
        "structural_review_passed": structural_passed,
        "pair_validity_review_passed": review["malformed_contrast_pairs"] == 0,
        "scoped_claim_review_passed": review["definition_rows_missing_declaration_shape"] == 0 and review["lexical_scope_errors"] == 0,
        "source_provenance_review_passed": provenance_passed,
        "split_isolation_independently_auditable": split_audit_passed,
        "absolute_import_resolution_review_passed": import_resolution_passed,
        "import_positive_rows_requiring_repair": review["import_positive_rows_missing_package_root_provenance"],
        "source_untraceable_rows": review["rows_reviewed"] - review["independently_auditable_source_rows"],
        "split_endpoint_untraceable_rows": review["rows_reviewed"] - review["independently_auditable_split_endpoint_rows"],
        "target_derived_metadata_review_passed": target_metadata_passed,
        "target_derived_occurrence_proof_rows": review["target_derived_occurrence_proof_rows"],
        "trainer_row_id_shortcut_review_passed": row_id_shortcut_passed,
        "objective_aware_row_id_parity_accuracy": review["objective_aware_row_id_parity_accuracy"],
        "candidate_context_shortcut_review_passed": candidate_context_passed,
        "candidate_context_majority_accuracy": review["candidate_context_majority_accuracy"],
        "symbol_context_majority_accuracy": review["symbol_context_majority_accuracy"],
        "training_admission_review_passed": False,
        "training_source_rows_admitted": 0,
        "recommended_next_stage": next_stage,
        **false_fields(),
    }
    audit = {
        "record_type": "stage12684_precise_link_semantic_repair_independent_review_audit_v1",
        "stage": STAGE,
        "decision": decision,
        "input_hashes": EXPECTED_HASHES,
        "upstream_semantic_claim_policy": upstream_audit["semantic_claim_policy"],
        "review": review,
        "findings": {
            "ast_definition_scope": "internally_consistent_parser-observation contrast; exact source occurrence is not retained",
            "pattern_definition_scope": "honestly pattern-scoped; exact regex match occurrence is not retained",
            "absolute_import_scope": "module text is exposed but repository suffix matching lacks pinned package-root and source-span proof",
            "doc_build_scope": "honestly lexical-only; exact token occurrence is not retained",
            "split_scope": "repository context is isolated, but file-content endpoints are absent from the review packet",
            "target_derived_metadata": "the pinned builder hashes the expected relationship into occurrence_proof_digest",
            "row_id_shortcut": "objective-aware row-id parity predicts the target perfectly",
            "candidate_context_shortcut": "coarse candidate metadata alone predicts substantially above chance",
        },
        "next_required_action": next_stage,
        "training_source_rows_admitted": 0,
        **false_fields(),
    }
    checks = [
        {"check_id": "stage12683_physical_hash_pins", "status": "passed", "count": len(EXPECTED_HASHES)},
        {"check_id": "schema_hygiene_authority", "status": "passed" if structural_passed else "blocked", "count": 0},
        {"check_id": "complete_candidate_only_contrast_pairs", "status": "passed" if review["malformed_contrast_pairs"] == 0 else "blocked", "count": review["malformed_contrast_pairs"]},
        {"check_id": "scoped_definition_and_lexical_claims", "status": "passed", "count": review["definition_rows"] + review["lexical_rows"]},
        {"check_id": "per_row_source_provenance", "status": "blocked", "count": summary["source_untraceable_rows"]},
        {"check_id": "independent_content_split_recomputation", "status": "blocked", "count": review["rows_reviewed"]},
        {"check_id": "absolute_import_package_resolution", "status": "blocked", "count": review["import_positive_rows_missing_package_root_provenance"]},
        {"check_id": "target_derived_occurrence_metadata", "status": "blocked", "count": review["target_derived_occurrence_proof_rows"]},
        {"check_id": "trainer_row_id_stripping", "status": "blocked", "count": review["rows_reviewed"]},
        {"check_id": "candidate_context_shortcut_repair", "status": "blocked", "count": review["rows_reviewed"]},
        {"check_id": "training_authority", "status": "blocked", "count": 0},
    ]
    for label, value in (("summary", summary), ("audit", audit), ("checks", checks)):
        assert_no_forbidden(value, label)
    return summary, audit, checks


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    summary, audit, checks = build_packet()
    private = {"record_type": "stage12684_private_review_packet_v1", "stage": STAGE, "audit_sha256": stable_hash(audit), "checks_sha256": stable_hash(checks), **false_fields()}
    contract = {"record_type": "stage12684_review_contract_v1", "stage": STAGE, "decision": summary["decision"], "upstream_rows_sha256": summary["upstream_rows_sha256"], "audit_sha256": stable_hash(audit), "private_packet_sha256": stable_hash(private), "recommended_next_stage": summary["recommended_next_stage"], **false_fields()}
    pointer = {"record_type": "stage12684_digest_pointer_v1", "stage": STAGE, "summary_sha256": stable_hash(summary), "contract_sha256": stable_hash(contract), "private_packet_sha256": stable_hash(private), "audit_sha256": stable_hash(audit), **false_fields()}
    for label, value in (("private", private), ("contract", contract), ("pointer", pointer)):
        assert_no_forbidden(value, label)
    write_json(out / "summary.json", summary)
    write_json(out / "precise_link_semantic_repair_independent_review_audit.json", audit)
    write_jsonl(out / "private/precise_link_semantic_repair_independent_review_checks.jsonl", checks)
    write_json(out / "private/precise_link_semantic_repair_independent_review_packet.json", private)
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True, ensure_ascii=True))
