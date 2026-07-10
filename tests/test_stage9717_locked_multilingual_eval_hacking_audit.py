from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9717_locked_multilingual_eval_hacking_audit.py"
    spec = importlib.util.spec_from_file_location("stage9717_eval_hacking", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9717_real_locked_suite_is_balanced_and_complete():
    mod = _load()
    contract = mod.load_json(mod.SOURCE_CONTRACT)
    suite = mod.load_json(mod.SOURCE_PACKS)
    exclusions = mod.load_jsonl(mod.SOURCE_EXCLUSIONS)
    validation = mod.load_json(mod.SOURCE_VALIDATION)
    audit = mod.audit_suite(contract, suite["benchmark_packs"], exclusions, validation)
    assert audit["passed"] is True
    assert audit["packs"] == 72
    assert audit["expected_cells"] == 72
    assert audit["mode_counts"] == {
        "full_product_harness": 36,
        "standalone_100m_weights": 36,
    }
    assert audit["language_counts"] == {
        "c_cpp": 18,
        "python": 18,
        "rust": 18,
        "web_js_ts_html": 18,
    }
    assert audit["skill_counts"]["symbol_binding"] == 8
    assert audit["challenge_matrix"]["covered_challenge_families"] == audit["challenge_matrix"]["total_challenge_families"]


def test_stage9717_fails_when_pack_loses_required_anti_cheat_requirement():
    mod = _load()
    contract = mod.load_json(mod.SOURCE_CONTRACT)
    suite = mod.load_json(mod.SOURCE_PACKS)
    exclusions = mod.load_jsonl(mod.SOURCE_EXCLUSIONS)
    validation = mod.load_json(mod.SOURCE_VALIDATION)
    packs = [dict(pack) for pack in suite["benchmark_packs"]]
    packs[0]["anti_cheat_requirements"] = list(packs[0]["anti_cheat_requirements"][:-1])
    audit = mod.audit_suite(contract, packs, exclusions, validation)
    assert audit["passed"] is False
    assert "pack_missing_anti_cheat_requirements" in audit["failures"]


def test_stage9717_fails_when_cell_is_missing():
    mod = _load()
    contract = mod.load_json(mod.SOURCE_CONTRACT)
    suite = mod.load_json(mod.SOURCE_PACKS)
    exclusions = mod.load_jsonl(mod.SOURCE_EXCLUSIONS)
    validation = mod.load_json(mod.SOURCE_VALIDATION)
    packs = list(suite["benchmark_packs"][:-1])
    audit = mod.audit_suite(contract, packs, exclusions[:-1], validation)
    assert audit["passed"] is False
    assert "missing_acceptance_cells" in audit["failures"]
    assert len(audit["missing_cells"]) == 1
