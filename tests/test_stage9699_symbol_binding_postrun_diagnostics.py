from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9699_symbol_binding_postrun_diagnostics.py"
    spec = importlib.util.spec_from_file_location("stage9699", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9699_manifest_balance_exposes_split_gap():
    mod = _load()
    rows = mod.load_jsonl(mod.MANIFEST)
    balance = mod.manifest_balance(rows)
    assert balance["rows"] == 64
    assert balance["label_counts"]["BIND_IMPORT_TO_MODULE"] == 7
    assert "BIND_IMPORT_TO_MODULE" in balance["labels_missing_from_eval_or_strict"]
    assert balance["split_label_counts"]["train"]["BIND_IMPORT_TO_MODULE"] == 7
    assert balance["split_label_counts"]["eval"].get("BIND_IMPORT_TO_MODULE", 0) == 0
    assert balance["split_label_counts"]["strict_eval"].get("BIND_IMPORT_TO_MODULE", 0) == 0


def test_stage9699_prediction_diagnostics_capture_call_collapse():
    mod = _load()
    rows = mod.load_jsonl(mod.RUN_DIR / "row_field_logits.jsonl")
    diagnostics = mod.prediction_diagnostics(rows)
    assert diagnostics["rows"] == 32
    assert diagnostics["exact"] == 0.3125
    assert diagnostics["prediction_collapse_label"] == "BIND_CALL_TO_SYMBOL"
    assert diagnostics["prediction_collapse_rate"] == 1.0
    assert diagnostics["high_confidence_wrong_rows"] == 0
    assert diagnostics["by_split_pred"]["eval"] == {"BIND_CALL_TO_SYMBOL": 16}
    assert diagnostics["by_split_pred"]["strict_eval"] == {"BIND_CALL_TO_SYMBOL": 16}


def test_stage9699_loss_and_gradient_diagnostics_keep_decoder_closed():
    mod = _load()
    loss_rows = mod.load_jsonl(mod.RUN_DIR / "loss_by_step.jsonl")
    grad_rows = mod.load_jsonl(mod.RUN_DIR / "row_gradient_norms.jsonl")
    losses = mod.loss_diagnostics(loss_rows)
    gradients = mod.gradient_diagnostics(grad_rows)
    assert losses["rows"] == 8
    assert losses["loss_increased_from_first_to_last"] is True
    assert losses["last_three_correct_total"] == 0
    assert gradients["rows"] == 16
    assert gradients["decoder_grad_nonzero_rows"] == 0
    assert gradients["structured_head_grad_norm"]["mean"] > 0.0
