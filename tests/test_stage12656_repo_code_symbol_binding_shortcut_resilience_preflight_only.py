from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12656_repo_code_symbol_binding_shortcut_resilience_preflight_only.py"
SPEC = importlib.util.spec_from_file_location("stage12656", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def test_load_inputs_pins_exact_upstream_artifacts() -> None:
    loaded = stage.load_inputs()
    assert len(loaded["repaired_rows"]) == 80
    assert len(loaded["examples"]) == 280
    assert len(loaded["manifest"]) == 280
    assert loaded["summary"]["optimizer_context_bound_to_trainer_implementation"] is True
    assert loaded["summary"]["training_allowed"] is False


def test_enrichment_uses_shape_values_without_identity_or_lineage() -> None:
    source = stage.load_inputs()["repaired_rows"][0]
    text = stage.enriched_symbol_input(source)
    assert "query_features=call_shape.contains_underscore=False" in text
    assert "file_features=call_count_bucket=" in text
    assert "repo_languages=python=1" in text
    assert "bm25_recall_bucket=" in text
    for forbidden in stage.FORBIDDEN_SUBSTRINGS:
        assert forbidden not in text


def test_overlay_enriches_symbols_and_quarantines_remaining_cross_split_duplicates() -> None:
    built = stage.build_packet()
    examples = built["examples"]
    manifest = built["manifest"]
    packet = built["packet"]
    assert len(examples) == 280
    assert len(manifest) == 280
    assert packet["symbol_rows_enriched"] == 80
    assert packet["cross_split_duplicate_signature_groups"] == 7
    assert packet["cross_split_duplicate_signature_rows"] == 22
    assert packet["shortcut_quarantined_rows"] == 22
    assert packet["trainer_consumable_rows_after_hardening"] == 258
    assert packet["zero_weight_rows_after_hardening"] == 22
    symbol_examples = [row for row in examples if row["training_objective"] == "source_backed_symbol_binding_ce"]
    assert all(row["symbol_input_enriched_with_nonleaky_structure"] is True for row in symbol_examples)
    quarantined = [row for row in manifest if row["shortcut_signature_cross_split_duplicate"]]
    assert all(row["trainer_consumable"] is False for row in quarantined)
    assert all(row["loss_weight"] == 0.0 for row in quarantined)


def test_overlay_preserves_curriculum_counts_and_training_gates_closed() -> None:
    packet = stage.build_packet()["packet"]
    assert packet["objective_counts"] == stage.EXPECTED_COUNTS
    assert packet["split_counts"] == stage.EXPECTED_SPLITS
    assert packet["lane_counts"] == stage.EXPECTED_LANES
    assert packet["repo_code_curriculum_layer_complete"] is True
    for field in stage.FALSE_FIELDS:
        assert packet[field] is False
    assert packet["decision"] == "SYMBOL_BINDING_SHORTCUT_RESILIENCE_OVERLAY_MATERIALIZED_NO_TRAINING"


def test_build_writes_hardened_overlay_artifacts() -> None:
    summary = stage.build()
    assert summary["shortcut_resilience_overlay_materialized"] is True
    assert summary["training_allowed"] is False
    assert (stage.OUT / "private/shortcut_resilient_repo_code_training_examples.jsonl").exists()
    assert (stage.OUT / "private/shortcut_resilient_repo_code_curriculum_ingest_manifest.jsonl").exists()
    assert stage.SUMMARY.exists()
    assert json.loads(stage.SUMMARY.read_text()) == json.loads((stage.OUT / "summary.json").read_text())


def test_public_artifacts_do_not_expose_training_text_or_private_paths() -> None:
    stage.build()
    for path in (stage.OUT / "summary.json", stage.OUT / "contract.json", stage.OUT / "digest_pointer.json", stage.SUMMARY):
        text = Path(path).read_text()
        assert "model_input" not in text
        assert "target_text" not in text
        for forbidden in stage.PUBLIC_FORBIDDEN_SUBSTRINGS:
            assert forbidden not in text


def test_private_overlay_has_no_lineage_paths_or_placeholder_leaks() -> None:
    stage.build()
    for path in (
        stage.OUT / "private/shortcut_resilient_repo_code_training_examples.jsonl",
        stage.OUT / "private/shortcut_resilient_repo_code_curriculum_ingest_manifest.jsonl",
    ):
        text = path.read_text()
        for forbidden in stage.FORBIDDEN_SUBSTRINGS:
            assert forbidden not in text


def test_rejects_source_identity_leak_regression() -> None:
    source = dict(stage.load_inputs()["repaired_rows"][0])
    source["query"] = dict(source["query"])
    source["query"]["features"] = dict(source["query"]["features"])
    source["query"]["features"]["source_row_id"] = "stage8604_row_bad"
    with pytest.raises(stage.Stage12656ShortcutResilienceError, match="source_row_id"):
        stage.enriched_symbol_input(source)
