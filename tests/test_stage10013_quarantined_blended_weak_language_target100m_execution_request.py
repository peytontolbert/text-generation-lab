from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage10013_quarantined_blended_weak_language_target100m_execution_request.py"
    spec = importlib.util.spec_from_file_location("stage10013", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_request_preserves_quarantined_edit_localization_counts():
    mod = _load()
    built = mod.build_request()
    assert built["passed"] is True
    assert built["metrics"]["surface_requests"] == 4
    assert built["metrics"]["edit_localization_rows"] == 112
    assert built["metrics"]["edit_localization_python_rows"] == 19
    assert built["metrics"]["edit_localization_c_cpp_rows"] == 27
    assert built["metrics"]["edit_localization_web_rows"] == 45
    edit_row = next(row for row in built["surface_requests"] if row["surface"] == "edit_localization")
    assert edit_row["request_status"] == "awaiting_explicit_execution_authorization"
    assert edit_row["required_contract_invariants"]["source_stage10011_contract_passed"] is True
    assert edit_row["required_contract_invariants"]["source_stage10011_model_execution_attempted"] is False


def test_surface_request_extracts_output_dir_and_run_id():
    mod = _load()
    req = mod._surface_request(
        card={
            "surface": "symbol_binding",
            "manifest": "runs/local/artifacts/mock/symbol_binding.jsonl",
            "rows": 80,
            "split_counts": {"train": 32, "eval": 22, "strict_eval": 26, "other": 0},
            "language_counts": {"python": 20, "rust": 20, "c_cpp": 20, "web_js_ts_html": 20},
            "expected_loss": "symbol_binding_ce",
        },
        command=[
            "python",
            "legacy_src/scripts/train_agentkernel_lite_encdec.py",
            "--manifest",
            "runs/local/artifacts/mock/symbol_binding.jsonl",
            "--output-dir",
            "runs/local/artifacts/stage10013_symbol_binding/probe",
            "--run-id",
            "stage10013_symbol_binding_probe",
        ],
        stage10011_row={
            "contract_passed": True,
            "model_execution_attempted": False,
            "unsafe_loss_rows": 0,
            "missing_required_contract_artifacts": [],
        },
    )
    assert req["output_dir"] == "runs/local/artifacts/stage10013_symbol_binding/probe"
    assert req["run_id"] == "stage10013_symbol_binding_probe"
    assert "probe_contract_audit.json" in req["required_runtime_artifacts"]
