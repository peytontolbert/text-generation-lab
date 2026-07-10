from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9752_supported_standalone_review_packets.py"
    spec = importlib.util.spec_from_file_location("stage9752", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9752_materializes_prefilled_review_packets_for_supported_cells():
    mod = _load()
    built = mod.build_review_packets(
        mod.load_json(mod.QUEUE),
        mod.load_json(mod.TRUTHFUL),
        mod.load_json(mod.ANTI_HACK),
        mod.load_json(mod.ACCEPTANCE_LEDGER),
    )
    metrics = built["metrics"]
    packets = built["review_packets"]
    assert built["failures"] == []
    assert metrics["review_packets"] == 13
    assert metrics["languages"] == ["c_cpp", "python", "rust", "web_js_ts_html"]
    assert metrics["challenge_family_count"] == 6
    assert metrics["all_packets_ready_for_gemma_when_authorized"] is True
    first = packets[0]
    assert first["cell_key"] == "standalone_100m_weights::python::symbol_binding"
    assert first["same_surface_packet"]["eval_exact"] == 0.3125
    assert first["merge_ready_bundle_template"]["same_surface_comparison"]["present"] is True
    assert first["merge_ready_bundle_template"]["same_surface_comparison"]["score_100m"] == 0.3125
    assert first["merge_ready_bundle_template"]["anti_cheat_attachment"]["stage9717_gate_passed"] is True
    assert first["merge_ready_bundle_template"]["evidence_artifacts"]["same_prompt_surface_gemma12b_outputs"] is None
    assert len(first["expert_maintainer_review_template"]["subskills_required"]) == 16
    assert first["anti_cheat_review_template"]["challenge_families"] == [
        "hidden_reference_materialization",
        "target_and_teacher_leakage",
        "label_proxy_shortcuts",
        "metadata_and_graph_shortcuts",
        "generation_quality_collapse",
        "cross_model_surface_fairness",
    ]
