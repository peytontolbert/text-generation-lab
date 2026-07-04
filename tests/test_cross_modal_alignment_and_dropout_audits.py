import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from cross_modal_alignment_audit import audit_alignment_row, audit_alignment_rows
from modality_dropout_ablation_audit import audit_ablation_card, audit_ablation_cards


def aligned_row():
    return {
        "row_id": "r1",
        "modalities": {
            "source_text": {"source_hash": "h1", "path": "src/app.py", "node_id": "file_1"},
            "cst_ast": {"source_hash": "h1", "nodes": [{"node_id": "n1", "path": "src/app.py"}], "edges": [{"src": "n1", "dst": "n1"}]},
            "symbol_table": {"source_hash": "h1", "symbols": [{"symbol_id": "s1", "path": "src/app.py"}], "edges": [{"src": "s1", "dst": "dep_x"}]},
            "import_export_graph": {"source_hash": "h1", "dependencies": [{"dependency_id": "dep_x", "path": "src/app.py"}]},
            "type_signature_map": {"source_hash": "h1", "signatures": [{"signature_id": "t1", "path": "src/app.py"}]},
            "call_graph": {"source_hash": "h1", "call_nodes": [{"call_node_id": "call_x", "path": "src/app.py"}], "edges": [{"src": "call_x", "dst": "call_y"}]},
            "data_flow_graph": {"source_hash": "h1", "data_nodes": [{"data_node_id": "d1", "path": "src/app.py"}], "edges": [{"src": "d1", "dst": "d1"}]},
            "control_flow_graph": {"source_hash": "h1", "control_nodes": [{"control_node_id": "c1", "path": "src/app.py"}], "edges": [{"src": "c1", "dst": "c1"}]},
        },
    }


def test_cross_modal_alignment_passes_for_consistent_packets():
    card = audit_alignment_row(aligned_row())
    assert card["passed"] is True
    assert card["missing_modalities"] == []


def test_cross_modal_alignment_flags_missing_hash_and_path_failures():
    row = aligned_row()
    row["modalities"].pop("call_graph")
    row["modalities"]["symbol_table"]["source_hash"] = "other"
    row["modalities"]["type_signature_map"]["signatures"][0]["path"] = "other.py"
    card = audit_alignment_row(row)
    assert card["passed"] is False
    assert "missing_modalities" in card["failures"]
    assert "source_hash_mismatch" in card["failures"]


def test_cross_modal_alignment_rows_reports_failure_counts():
    good = aligned_row()
    bad = aligned_row()
    bad["modalities"] = {}
    card = audit_alignment_rows([good, bad])
    assert card["passed"] is False
    assert card["failing_rows"] == 1
    assert card["failure_counts"]["missing_modalities"] == 1


def test_modality_dropout_audit_passes_when_full_beats_modalities():
    card = audit_ablation_card({
        "objective": "symbol_binding",
        "full_score": 0.91,
        "majority_baseline": 0.33,
        "modality_scores": {"symbol_table": 0.70, "call_graph": 0.62, "runtime_trace": 0.58},
        "combo_scores": {"symbol_plus_call": 0.74},
        "dropout_scores": {"drop_symbol_table": 0.76, "drop_call_graph": 0.80},
    })
    assert card["passed"] is True
    assert card["lift_over_strongest_modality"] > 0.1


def test_modality_dropout_audit_blocks_single_modality_shortcut():
    card = audit_ablation_card({
        "objective": "patch_operator",
        "full_score": 0.90,
        "majority_baseline": 0.33,
        "modality_scores": {"surface_marker": 0.86, "patch_history": 0.60},
        "dropout_scores": {"drop_surface_marker": 0.88},
    })
    assert card["passed"] is False
    assert "single_modality_shortcut" in card["failures"]
    assert "dropout_not_sensitive" in card["failures"]


def test_modality_dropout_audit_rows_summarizes_failures():
    good = {"full_score": 0.9, "majority_baseline": 0.3, "modality_scores": {"a": 0.7}, "dropout_scores": {"drop_a": 0.7}}
    bad = {"full_score": 0.8, "majority_baseline": 0.3, "modality_scores": {"a": 0.79}}
    card = audit_ablation_cards([good, bad])
    assert card["passed"] is False
    assert card["failing_cards"] == 1
    assert card["failure_counts"]["insufficient_multimodal_lift"] == 1
