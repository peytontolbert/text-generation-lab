#!/usr/bin/env python3
"""Quarantine deterministic supervision that is not semantically learnable."""

from __future__ import annotations

import collections
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "runs/local/artifacts/stage12686_deterministic_training_data_semantic_quarantine"
SUMMARY = ROOT / "runs/summaries/stage12686_deterministic_training_data_semantic_quarantine.json"
SOURCES = {
    "stage12680_candidates": ROOT / "runs/local/artifacts/stage12680_deep_repo_code_knowledge_adapter_and_shortcut_preflight_only/private/deep_repo_code_knowledge_adapter_candidates.jsonl",
    "stage12680_existing_quarantine": ROOT / "runs/local/artifacts/stage12680_deep_repo_code_knowledge_adapter_and_shortcut_preflight_only/private/deep_repo_code_knowledge_shortcut_quarantine.jsonl",
    "stage12662_structured_state": ROOT / "runs/local/artifacts/stage12662_structured_repo_state_training_admission_preflight_only/private/structured_repo_state_trainer_manifest.jsonl",
    "stage12656_repo_code": ROOT / "runs/local/artifacts/stage12656_repo_code_symbol_binding_shortcut_resilience_preflight_only/private/shortcut_resilient_repo_code_training_examples.jsonl",
    "stage12685_precise_links": ROOT / "runs/local/artifacts/stage12685_precise_link_provenance_import_and_adapter_repair_preflight_only/private/trainer_pairs.jsonl",
}
EXPECTED_SOURCE_ROWS = {
    "stage12680_candidates": 97_462,
    "stage12680_existing_quarantine": 22_538,
    "stage12662_structured_state": 2_187,
    "stage12656_repo_code": 280,
    "stage12685_precise_links": 31_412,
}
EXPECTED_SOURCE_SHA256 = {
    "stage12656_repo_code": "aa869c73128a7c64868483dd5e3bdb70ab00286f33c4a30d694c4dc4cbc1f872",
    "stage12662_structured_state": "bd5045315a9676d9c5e5ce49e11cb9843a524820e6507260e9ed58415bc4acd8",
    "stage12680_candidates": "7808edc1286fa46fa4cdb709b4c4e779ba8b91fec705ea62c5b0331f49d9798c",
    "stage12680_existing_quarantine": "fdb2e55328543ab04cfd22522b76ec9c970549492d0daa7872c9939f6706cda1",
    "stage12685_precise_links": "d386c6a762e953c028f637fc09f8e078f11f96d34a167e37ab494aa77ad84084",
}
AUTHORITY = {
    "implementation_ready": False,
    "level_3_materialized": False,
    "model_execution_authorized": False,
    "replay_trustworthy": False,
    "sealed_eval_admitted": False,
    "strict_eval_admitted": False,
    "training_admitted": False,
}


class Stage12686Error(ValueError):
    pass


def stable(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if any(not isinstance(row, dict) for row in rows):
        raise Stage12686Error(f"non_object_row:{path.name}")
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def row_ref(row: dict[str, Any]) -> str:
    for key in ("row_id", "example_id", "source_row_id", "training_candidate_id"):
        value = row.get(key)
        if isinstance(value, str) and value:
            return value
    return "sha256:" + stable(row)[:24]


def objective(row: dict[str, Any]) -> str:
    state = row.get("input_state") if isinstance(row.get("input_state"), dict) else {}
    return str(row.get("objective_family") or row.get("training_objective") or state.get("objective_family") or "unknown")


def ledger_row(source: str, row: dict[str, Any], *, reason: str, status: str) -> dict[str, Any]:
    source_hash = stable(row)
    return {
        "ledger_id": stable([source, source_hash, reason, status])[:32],
        "source_dataset": source,
        "source_row_ref_sha256": stable(["source_row_ref", row_ref(row)]),
        "source_row_sha256": source_hash,
        "split": str(row.get("split") or "unknown"),
        "objective": objective(row),
        "reason": reason,
        "status": status,
        "training_admitted": False,
        "strict_eval_admitted": False,
        "sealed_eval_admitted": False,
    }


def build(output_dir: Path = ARTIFACT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    source_sha256 = {name: file_sha256(path) for name, path in SOURCES.items()}
    if source_sha256 != EXPECTED_SOURCE_SHA256:
        raise Stage12686Error(f"source_hash_drift:{source_sha256}")
    loaded = {name: read_jsonl(path) for name, path in SOURCES.items()}
    counts = {name: len(rows) for name, rows in loaded.items()}
    if counts != EXPECTED_SOURCE_ROWS:
        raise Stage12686Error(f"source_count_drift:{counts}")

    quarantine: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []

    for row in loaded["stage12680_candidates"]:
        quarantine.append(ledger_row("stage12680", row, reason="no_model_visible_source_evidence", status="quarantined"))
    for row in loaded["stage12680_existing_quarantine"]:
        quarantine.append(ledger_row("stage12680", row, reason="existing_duplicate_target_shortcut_quarantine", status="quarantined"))
    for row in loaded["stage12662_structured_state"]:
        quarantine.append(ledger_row("stage12662", row, reason="objective_specific_constant_taxonomy_label", status="quarantined"))

    for row in loaded["stage12656_repo_code"]:
        if objective(row) == "repo_code_capability_ce":
            quarantine.append(ledger_row("stage12656", row, reason="deterministic_summary_copy_target", status="quarantined"))
        else:
            review.append(ledger_row("stage12656", row, reason="balanced_symbol_binding_semantic_review_required", status="review_required"))

    for row in loaded["stage12685_precise_links"]:
        family = objective(row)
        state = row.get("input_state") if isinstance(row.get("input_state"), dict) else {}
        if family == "language_pattern_symbol_definition_relation":
            quarantine.append(ledger_row("stage12685", row, reason="regex_match_is_not_parser_verified_definition", status="quarantined"))
        elif family == "doc_build_literal_symbol_association":
            quarantine.append(ledger_row("stage12685", row, reason="lexical_overlap_is_not_semantic_link", status="quarantined"))
        elif family == "python_ast_symbol_definition_relation" and state.get("candidate_a") == state.get("candidate_b"):
            quarantine.append(ledger_row("stage12685", row, reason="model_visible_candidates_indistinguishable", status="quarantined"))
        elif family == "python_ast_symbol_definition_relation":
            review.append(ledger_row("stage12685", row, reason="independent_positive_and_negative_endpoint_reparse_required", status="review_required"))
        else:
            raise Stage12686Error(f"unknown_stage12685_objective:{family}")

    quarantine_counts = collections.Counter(row["source_dataset"] for row in quarantine)
    quarantine_reasons = collections.Counter(row["reason"] for row in quarantine)
    review_counts = collections.Counter(row["source_dataset"] for row in review)
    review_splits = collections.Counter((row["source_dataset"], row["split"]) for row in review)
    if len(quarantine) != 136_371 or len(review) != 17_508:
        raise Stage12686Error(f"classification_count_drift:quarantine={len(quarantine)}:review={len(review)}")
    classified = quarantine + review
    if len({row["ledger_id"] for row in classified}) != len(classified):
        raise Stage12686Error("duplicate_ledger_id")
    if len({(row["source_dataset"], row["source_row_sha256"]) for row in classified}) != len(classified):
        raise Stage12686Error("duplicate_classified_source_row")
    if any(row["training_admitted"] is not False for row in quarantine + review):
        raise Stage12686Error("authority_drift")

    private_dir = output_dir / "private"
    quarantine_path = private_dir / "semantic_quarantine_ledger.jsonl"
    review_path = private_dir / "semantic_review_candidate_ledger.jsonl"
    write_jsonl(quarantine_path, quarantine)
    write_jsonl(review_path, review)
    ledger_contract = {
        quarantine_path.name: {"rows": len(quarantine), "sha256": file_sha256(quarantine_path)},
        review_path.name: {"rows": len(review), "sha256": file_sha256(review_path)},
    }
    summary = {
        "stage": 12686,
        "decision": "BLOCKED_TRAINING_DATA_SEMANTIC_REBUILD_AND_INDEPENDENT_REPARSE_REQUIRED",
        "source_rows": counts,
        "source_sha256": source_sha256,
        "quarantined_unique_rows": len(quarantine),
        "quarantine_counts": dict(sorted(quarantine_counts.items())),
        "quarantine_reason_counts": dict(sorted(quarantine_reasons.items())),
        "review_required_unique_rows": len(review),
        "review_counts": dict(sorted(review_counts.items())),
        "review_split_counts": {f"{source}:{split}": count for (source, split), count in sorted(review_splits.items())},
        "training_eligible_rows": 0,
        "semantic_nonadmission_ledger_contract": ledger_contract,
        "uniqueness_proof": {
            "classified_rows": len(classified),
            "distinct_ledger_ids": len({row["ledger_id"] for row in classified}),
            "distinct_source_dataset_row_hashes": len({(row["source_dataset"], row["source_row_sha256"]) for row in classified}),
        },
        "superseded_lineages_covered_without_double_counting": ["stage12674", "stage12676", "stage12678", "stage12680"],
        "authority": dict(AUTHORITY),
    }
    write_json(output_dir / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True))
