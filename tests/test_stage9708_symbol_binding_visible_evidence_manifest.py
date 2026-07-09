from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9708_symbol_binding_visible_evidence_manifest.py"
    spec = importlib.util.spec_from_file_location("stage9708", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9708_adds_visible_candidate_graph_and_counterfactual_rows():
    mod = _load()
    source = mod.load_jsonl(mod.SOURCE_MANIFEST)
    rows = mod.build_rows(source)
    assert len(source) == 64
    assert len(rows) > len(source)
    assert len(rows) - len(source) == 28
    assert all((row.get("model_input") or {}).get("visible_binding_evidence_v1") for row in rows)
    assert any("__stage9708_cf_" in row["row_id"] for row in rows)
    node_types = Counter()
    edge_types = Counter()
    for row in rows:
        graph = row["graph_input"]
        node_types.update(node["node_type"] for node in graph["nodes"])
        edge_types.update(edge["edge_type"] for edge in graph["edges"])
    assert node_types["module_candidate"] > 0
    assert node_types["symbol_candidate"] > 0
    assert node_types["retrieval_gap_marker"] > 0
    assert edge_types["candidate_import_relation"] > 0
    assert edge_types["candidate_test_relation"] > 0
    assert edge_types["candidate_call_relation"] > 0


def test_stage9708_query_kind_shortcut_is_reduced_below_ceiling():
    mod = _load()
    source = mod.load_jsonl(mod.SOURCE_MANIFEST)
    rows = mod.build_rows(source)
    assert mod.grouped_baseline(source, mod.query_kind) > mod.QUERY_KIND_BASELINE_CEILING
    assert mod.grouped_baseline(rows, mod.query_kind) < mod.QUERY_KIND_BASELINE_CEILING


def test_stage9708_loss_and_authority_stay_closed():
    mod = _load()
    rows = mod.build_rows(mod.load_jsonl(mod.SOURCE_MANIFEST))
    assert mod.count_enabled_losses(rows) == Counter({"symbol_binding_ce": len(rows)})
    assert mod.authority_violations(rows) == []
    for row in rows:
        assert row["loss_mask"]["decoder_ce"] is False
        assert row["loss_mask"]["runtime_reward"] is False
        assert row["authority"]["runtime_authorized"] is False
        assert row["authority"]["gemma_execution_authorized_next"] is False


def test_stage9708_target_labels_not_added_to_model_input():
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
        text = repr(row.get("model_input") or {})
        for label in forbidden:
            assert label not in text
        assert (row.get("anti_cheat") or {}).get("stage9708_target_label_in_model_input") is False
