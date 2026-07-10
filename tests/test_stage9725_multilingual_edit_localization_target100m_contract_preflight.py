from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9725_multilingual_edit_localization_target100m_contract_preflight.py"
    spec = importlib.util.spec_from_file_location("stage9725", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _load_stage9724():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9724_multilingual_edit_localization_tiny_package.py"
    spec = importlib.util.spec_from_file_location("stage9724", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9725_command_is_contract_only_and_edit_localization():
    mod = _load()
    cmd = mod.command()
    joined = " ".join(cmd)
    assert "--contract-only" in cmd
    assert "--mode edit_localization_probe" in joined
    assert "--probe-scale target_100m" in joined
    assert "--decoder-ce-weight 0.0" in joined
    assert "--structured-aux-weight 1.0" in joined


def test_stage9725_manifest_is_64_rows_multilingual():
    stage9724 = _load_stage9724()
    rows = stage9724.load_jsonl(stage9724.SOURCE)
    selected, failures = stage9724.select_rows(rows)
    assert failures == []
    stage9724.write_jsonl(stage9724.MANIFEST, selected)

    mod = _load()
    rows = mod.read_jsonl(mod.MANIFEST)
    assert len(rows) == 64
    langs = {row["language_family"] for row in rows}
    assert langs == {"python", "rust", "c_cpp", "web_js_ts_html"}
