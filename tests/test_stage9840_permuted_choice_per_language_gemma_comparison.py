from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'scripts'))
    path = root / 'scripts/build_stage9840_permuted_choice_per_language_gemma_comparison.py'
    spec = importlib.util.spec_from_file_location('stage9840', path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9840_build_audit_counts_per_language_wins():
    mod = _load()
    hundred = [
        {'language_family':'python','split':'eval','correct':True},
        {'language_family':'python','split':'strict_eval','correct':True},
        {'language_family':'rust','split':'eval','correct':True},
        {'language_family':'rust','split':'strict_eval','correct':False},
        {'language_family':'c_cpp','split':'eval','correct':False},
        {'language_family':'c_cpp','split':'strict_eval','correct':False},
        {'language_family':'web_js_ts_html','split':'eval','correct':True},
        {'language_family':'web_js_ts_html','split':'strict_eval','correct':False},
    ]
    gemma = [
        {'language_family':'python','split':'eval','correct':False},
        {'language_family':'python','split':'strict_eval','correct':True},
        {'language_family':'rust','split':'eval','correct':False},
        {'language_family':'rust','split':'strict_eval','correct':True},
        {'language_family':'c_cpp','split':'eval','correct':False},
        {'language_family':'c_cpp','split':'strict_eval','correct':False},
        {'language_family':'web_js_ts_html','split':'eval','correct':True},
        {'language_family':'web_js_ts_html','split':'strict_eval','correct':True},
    ]
    audit = mod.build_audit(hundred, gemma)
    assert audit['wins_100m'] == 2
    assert audit['wins_gemma'] == 2
    assert audit['ties'] == 4
