from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9711_symbol_binding_retrieval_test_evidence_repair.py"
    spec = importlib.util.spec_from_file_location("stage9711", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9711_adds_retrieval_gap_and_test_coverage_edges():
    mod = _load()
    rows = mod.build_rows(mod.load_jsonl(mod.SOURCE_MANIFEST))
    edge_types = Counter()
    node_types = Counter()
    for row in rows:
        graph = row["graph_input"]
        edge_types.update(edge["edge_type"] for edge in graph["edges"])
        node_types.update(node["node_type"] for node in graph["nodes"])
        assert (row.get("model_input") or {}).get("binding_relation_evidence_v2")
    assert edge_types["query_requires_retrieval_gap_resolution"] > 0
    assert edge_types["test_has_coverage_evidence"] > 0
    assert edge_types["coverage_points_to_symbol_candidate"] > 0
    assert node_types["coverage_evidence"] > 0
    assert node_types["coverage_gap_evidence"] > 0


def test_stage9711_shortcut_baselines_remain_below_ceiling():
    mod = _load()
    rows = mod.build_rows(mod.load_jsonl(mod.SOURCE_MANIFEST))
    baselines = mod.single_feature_baselines(rows)
    assert mod.grouped_baseline(rows, mod.query_kind) < mod.QUERY_KIND_BASELINE_CEILING
    assert next(iter(baselines.values())) < mod.SINGLE_FEATURE_BASELINE_CEILING


def test_stage9711_loss_and_authority_contracts_stay_closed():
    mod = _load()
    rows = mod.build_rows(mod.load_jsonl(mod.SOURCE_MANIFEST))
    assert mod.count_enabled_losses(rows) == Counter({"symbol_binding_ce": len(rows)})
    assert mod.authority_violations(rows) == []
    for row in rows:
        assert row["loss_mask"]["decoder_ce"] is False
        assert row["loss_mask"]["runtime_reward"] is False
        assert row["authority"]["runtime_authorized"] is False
        assert row["authority"]["gemma_execution_authorized_next"] is False


def test_stage9711_does_not_put_label_names_in_new_model_input_block():
    mod = _load()
    rows = mod.build_rows(mod.load_jsonl(mod.SOURCE_MANIFEST))
    forbidden = {
        "BIND_CALL_TO_SYMBOL",
        "BIND_IMPORT_TO_MODULE",
        "BIND_TEST_TO_SYMBOL",
        "RETRIEVE_MORE",
        "ABSTAIN_UNBOUND",
    }
    for row in rows:
        text = repr((row.get("model_input") or {}).get("binding_relation_evidence_v2"))
        for label in forbidden:
            assert label not in text
        assert (row.get("anti_cheat") or {}).get("stage9711_target_label_in_model_input") is False
