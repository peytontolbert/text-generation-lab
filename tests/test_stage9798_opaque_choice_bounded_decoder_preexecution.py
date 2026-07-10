from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9798_opaque_choice_bounded_decoder_preexecution.py"
    spec = importlib.util.spec_from_file_location("stage9798", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9798_contract_is_ready_for_stage9797_manifest():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    prev_path = root / "scripts/build_stage9797_opaque_choice_bounded_decoder_manifest.py"
    prev_spec = importlib.util.spec_from_file_location("stage9797", prev_path)
    prev_mod = importlib.util.module_from_spec(prev_spec)
    assert prev_spec and prev_spec.loader
    prev_spec.loader.exec_module(prev_mod)
    rows = prev_mod.build_rows()
    prev_mod.write_jsonl(prev_mod.MANIFEST, rows)
    mod = _load()
    audit = mod.audit()
    assert audit["passed"] is True
    assert audit["manifest_rows"] == 60
    assert audit["split_counts"] == {"eval": 20, "strict_eval": 20, "train": 20}
    assert audit["language_counts"] == {"c_cpp": 15, "python": 15, "rust": 15, "web_js_ts_html": 15}
    assert audit["loss_counts"]["decoder_ce"] == 60
    assert all(v == 0 for k, v in audit["loss_counts"].items() if k != "decoder_ce")
