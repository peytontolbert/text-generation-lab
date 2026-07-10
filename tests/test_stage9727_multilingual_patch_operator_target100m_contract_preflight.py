from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9727_multilingual_patch_operator_target100m_contract_preflight.py"
    spec = importlib.util.spec_from_file_location("stage9727", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _load_stage9726():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9726_multilingual_patch_operator_tiny_package.py"
    spec = importlib.util.spec_from_file_location("stage9726", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9727_command_is_contract_only_and_patch_operator():
    mod = _load()
    cmd = mod.command()
    joined = " ".join(cmd)
    assert "--contract-only" in cmd
    assert "--mode patch_operator_probe" in joined
    assert "--probe-scale target_100m" in joined
    assert "--decoder-ce-weight 0.0" in joined
    assert "--structured-aux-weight 1.0" in joined


def test_stage9727_manifest_is_64_rows_multilingual():
    stage9726 = _load_stage9726()
    rows = stage9726.load_jsonl(stage9726.SOURCE)
    selected, failures = stage9726.select_rows(rows)
    assert failures == []
    stage9726.write_jsonl(stage9726.MANIFEST, selected)

    mod = _load()
    rows = mod.read_jsonl(mod.MANIFEST)
    assert len(rows) == 64
    langs = {row["language_family"] for row in rows}
    assert langs == {"python", "rust", "c_cpp", "web_js_ts_html"}
