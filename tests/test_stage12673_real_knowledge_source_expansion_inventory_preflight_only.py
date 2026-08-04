from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12673_real_knowledge_source_expansion_inventory_preflight_only.py"
SPEC = importlib.util.spec_from_file_location("stage12673", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def stable(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def assert_execution_gates_closed(record):
    for field in stage.FALSE_FIELDS:
        assert record[field] is False


def test_load_inputs_pins_real_knowledge_sources() -> None:
    upstream, rows_by_source = stage.load_inputs()
    assert upstream["knowledge_stage_rows_reviewed"] == 258
    assert rows_by_source["symbol_binding_counterfactual_candidates"]
    assert len(rows_by_source["symbol_binding_counterfactual_candidates"]) == 1068
    assert len(rows_by_source["repo_capability_catalog_seed"]) == 200
    assert len(rows_by_source["repo_state_graph_seed"]) == 200


def test_source_inventory_records_counts_and_maturity() -> None:
    _, rows_by_source = stage.load_inputs()
    inventory = {row["source_family"]: row for row in stage.source_inventory(rows_by_source)}
    assert inventory["symbol_binding_counterfactual_candidates"]["source_backing"] == "source_backed_candidate"
    assert inventory["source_backed_symbol_binding_shortcut_repair"]["source_backing"] == "source_backed_candidate"
    assert inventory["repo_capability_catalog_seed"]["source_backing"] == "source_backed_candidate"
    assert inventory["repo_span_retrieval_docs_sample"]["source_backing"] == "source_material_needs_label_builder"
    assert inventory["repo_state_cache_metadata_fixture"]["source_backing"] == "source_material_needs_label_builder"
    assert inventory["symbol_binding_counterfactual_candidates"]["template_marker_hits"] == 0
    assert inventory["symbol_binding_counterfactual_candidates"]["split_counts"] == {
        "eval": 200,
        "strict_eval": 202,
        "train": 666,
    }


def test_build_packet_pivots_from_tiny_seed_to_real_knowledge_inventory() -> None:
    summary, audit, checks = stage.build_packet()
    assert summary["decision"] == "REAL_KNOWLEDGE_SOURCE_EXPANSION_INVENTORY_MATERIALIZED_NO_TRAINING"
    assert summary["current_knowledge_seed_rows"] == 258
    assert summary["knowledge_seed_insufficient_for_frontier_100m"] is True
    assert summary["target_real_knowledge_dataset_required"] is True
    assert summary["candidate_source_rows_inventory_total"] == 1646
    assert summary["source_backed_candidate_rows_inventory_total"] == 1548
    assert summary["source_material_rows_needing_label_builder"] == 90
    assert summary["training_source_rows_admitted"] == 0
    assert audit["recommended_next_stage"] == "stage12674_real_knowledge_candidate_materialization_preflight_only"
    assert [row["check_id"] for row in checks if row["status"] == "blocked"] == [
        "training_authority",
        "expanded_label_materialization",
    ]
    assert_execution_gates_closed(summary)
    assert_execution_gates_closed(audit)


def test_public_records_are_sanitized() -> None:
    summary, audit, _ = stage.build_packet()
    for label, record in (("summary", summary), ("audit", audit)):
        stage.assert_no_forbidden(record, label)


def test_build_writes_real_knowledge_inventory_artifacts(tmp_path: Path) -> None:
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/real_knowledge_source_expansion_checks.jsonl",
        "private/real_knowledge_source_expansion_packet.json",
        "real_knowledge_source_expansion_audit.json",
        "summary.json",
    ]
    assert summary == read_json(summary_path)
    pointer = read_json(out / "digest_pointer.json")
    contract = read_json(out / "contract.json")
    private = read_json(out / "private/real_knowledge_source_expansion_packet.json")
    audit = read_json(out / "real_knowledge_source_expansion_audit.json")
    assert pointer["summary_sha256"] == stable(summary)
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_packet_sha256"] == stable(private)
    assert pointer["audit_sha256"] == stable(audit)
    assert sum(1 for _ in (out / "private/real_knowledge_source_expansion_checks.jsonl").open()) == 6


def test_generated_artifacts_match_current_stage() -> None:
    stage.build()
    summary = read_json(stage.OUT / "summary.json")
    external = read_json(stage.SUMMARY)
    audit = read_json(stage.OUT / "real_knowledge_source_expansion_audit.json")
    assert summary == external
    assert summary["candidate_source_rows_inventory_total"] == 1646
    assert summary["current_knowledge_seed_rows"] == 258
    assert audit["decision"] == summary["decision"]
    assert_execution_gates_closed(summary)
    assert_execution_gates_closed(audit)
