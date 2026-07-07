from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9215_repo_local_bounded_decoder_one_run_ticket_audit.py"
    spec = importlib.util.spec_from_file_location("stage9215_audit", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_negative_cases_cover_bounded_decoder_specific_failures():
    mod = _load()
    ticket = {
        "execution_authorized_now": False,
        "command_materialized": False,
        "allowed_operations_now": [],
        "denied_operations_now": list(mod.DENIED_NOW_OPERATIONS),
        "authority": dict(mod.AUTHORITY_CLOSED),
        "future_output_dir": str(mod.ROOT / "runs/local/probes/example"),
        "required_limits": {
            "decoder_ce_weight": 1.0,
            "denoise_weight": 0.0,
            "max_eval_rows": 16,
        },
    }
    case_names = {case["case"] for case in mod.negative_cases(ticket)}
    assert "execution_authorized_now_true" in case_names
    assert "denoise_weight_opened" in case_names
    assert "decoder_ce_weight_closed_wrongly" in case_names
    assert "eval_cap_too_large" in case_names
    assert "future_output_dir_arxiv" in case_names


def test_all_negative_results_are_rejected_for_real_ticket():
    mod = _load()
    ticket = mod.load_json(mod.SOURCE_TICKET)
    source_9213 = mod.load_json(mod.SOURCE_9213)
    source_8956 = mod.load_json(mod.SOURCE_8956)
    matrix = mod.load_json(mod.MATRIX)
    review = mod.bounded_review(matrix)
    results = mod.run_negative_cases(ticket, source_9213, source_8956, matrix, review)
    assert results
    assert all(item["rejected"] for item in results)
