from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9802_opaque_choice_option_token_preexecution.py"
    spec = importlib.util.spec_from_file_location("stage9802", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9802_contract_is_ready_for_option_token_manifest():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    prev_path = root / "scripts/build_stage9801_opaque_choice_option_token_decoder_manifest.py"
    prev_spec = importlib.util.spec_from_file_location("stage9801", prev_path)
    prev_mod = importlib.util.module_from_spec(prev_spec)
    assert prev_spec and prev_spec.loader
    prev_spec.loader.exec_module(prev_mod)
    rows = prev_mod.build_rows()
    prev_mod.write_jsonl(prev_mod.MANIFEST, rows)
    audit_prev = prev_mod.audit_rows(rows)
    prev_mod.SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    prev_mod.SUMMARY.write_text(__import__("json").dumps({"passed": audit_prev["passed"]}, indent=2) + "\n", encoding="utf-8")
    mod = _load()
    audit = mod.audit()
    assert audit["passed"] is True
    assert audit["manifest_rows"] == 60
    assert audit["split_counts"] == {"eval": 20, "strict_eval": 20, "train": 20}
    assert audit["language_counts"] == {"c_cpp": 15, "python": 15, "rust": 15, "web_js_ts_html": 15}
    assert audit["loss_counts"]["decoder_ce"] == 60
