from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9721_symbol_binding_standalone_comparison_package.py"
    spec = importlib.util.spec_from_file_location("stage9721_package", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9721_builds_four_prefilled_bundles():
    mod = _load()
    ledger = mod.load_json(mod.SOURCE_LEDGER)
    manifest = mod.load_jsonl(mod.SOURCE_MANIFEST)
    execution = mod.load_json(mod.SOURCE_EXECUTION)
    logits = mod.load_jsonl(mod.SOURCE_LOGITS)
    packets = mod.build_language_packets(manifest, logits)
    bundles = mod.build_prefilled_bundles(ledger["records"], packets, execution)
    assert len(bundles) == 4
    assert {bundle["language_family"] for bundle in bundles} == {"python", "rust", "c_cpp", "web_js_ts_html"}
    assert all(bundle["mode"] == "standalone_100m_weights" for bundle in bundles)


def test_stage9721_packets_report_current_python_only_coverage():
    mod = _load()
    packets = mod.build_language_packets(mod.load_jsonl(mod.SOURCE_MANIFEST), mod.load_jsonl(mod.SOURCE_LOGITS))
    assert {lang: packet["rows"] for lang, packet in packets.items()} == {
        "python": 64,
        "rust": 0,
        "c_cpp": 0,
        "web_js_ts_html": 0,
    }
    assert {lang: packet["logit_rows"] for lang, packet in packets.items()} == {
        "python": 32,
        "rust": 0,
        "c_cpp": 0,
        "web_js_ts_html": 0,
    }


def test_stage9721_prefilled_bundles_only_fill_python_100m_side():
    mod = _load()
    ledger = mod.load_json(mod.SOURCE_LEDGER)
    manifest = mod.load_jsonl(mod.SOURCE_MANIFEST)
    execution = mod.load_json(mod.SOURCE_EXECUTION)
    logits = mod.load_jsonl(mod.SOURCE_LOGITS)
    packets = mod.build_language_packets(manifest, logits)
    bundles = mod.build_prefilled_bundles(ledger["records"], packets, execution)
    for bundle in bundles:
        cmp = bundle["same_surface_comparison"]
        if bundle["language_family"] == "python":
            assert cmp["present"] is True
            assert cmp["prompt_surface_hash_100m"]
            assert cmp["score_100m"] is not None
            assert bundle["evidence_artifacts"]["language_slice_scores"]
            assert bundle["evidence_artifacts"]["telemetry_bundle"]
        else:
            assert cmp["present"] is False
            assert cmp["score_100m"] is None
