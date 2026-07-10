from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9723_multilingual_verifier_repair_target100m_contract_preflight.py"
    spec = importlib.util.spec_from_file_location("stage9723", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _load_stage9722():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9722_multilingual_verifier_repair_tiny_package.py"
    spec = importlib.util.spec_from_file_location("stage9722", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9723_command_is_contract_only_and_verifier_repair():
    mod = _load()
    cmd = mod.command()
    joined = ' '.join(cmd)
    assert '--contract-only' in cmd
    assert '--mode verifier_repair_probe' in joined
    assert '--probe-scale target_100m' in joined
    assert '--decoder-ce-weight 0.0' in joined
    assert '--structured-aux-weight 1.0' in joined


def test_stage9723_manifest_is_64_rows_multilingual():
    stage9722 = _load_stage9722()
    rows = stage9722.load_jsonl(stage9722.SOURCE)
    selected, failures = stage9722.select_rows(rows)
    assert failures == []
    stage9722.write_jsonl(stage9722.MANIFEST, selected)

    mod = _load()
    rows = mod.read_jsonl(mod.MANIFEST)
    assert len(rows) == 64
    langs = {row['language_family'] for row in rows}
    assert langs == {'python', 'rust', 'c_cpp', 'web_js_ts_html'}
