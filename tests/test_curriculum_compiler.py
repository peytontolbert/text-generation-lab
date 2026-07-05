from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPILER = ROOT / "scripts" / "curriculum_compiler.py"
AUDIT = ROOT / "scripts" / "audit_curriculum_compiler_outputs.py"


def write_rows(path: Path) -> None:
    rows = [
        {"row_id": "s", "split": "train", "route": "KEEP_STRUCTURED"},
        {"row_id": "d", "split": "train", "route": "KEEP_BOUNDED_DECODER"},
        {"row_id": "r", "split": "eval", "route": "USE_FOR_DENOISE_REPAIR"},
        {"row_id": "h", "split": "strict_eval", "route": "HOLD_LONG_OUTPUT"},
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_compiler_blocks_decoder_and_denoise_by_default(tmp_path: Path) -> None:
    inp = tmp_path / "rows.jsonl"
    out = tmp_path / "compiled"
    audit = tmp_path / "audit.json"
    write_rows(inp)
    subprocess.run([sys.executable, str(COMPILER), "--input", str(inp), "--output-dir", str(out)], check=True, text=True, capture_output=True)
    subprocess.run([sys.executable, str(AUDIT), str(out), "--output", str(audit)], check=True, text=True, capture_output=True)
    card = json.loads((out / "compile_card.json").read_text())
    assert card["loss_counts"]["decoder_ce"] == 0
    assert card["loss_counts"]["denoise_ce"] == 0
    audit_card = json.loads(audit.read_text())
    assert audit_card["passed"] is True


def test_compiler_allows_decoder_when_explicit(tmp_path: Path) -> None:
    inp = tmp_path / "rows.jsonl"
    out = tmp_path / "compiled"
    audit = tmp_path / "audit.json"
    write_rows(inp)
    subprocess.run([sys.executable, str(COMPILER), "--input", str(inp), "--output-dir", str(out), "--allow-decoder"], check=True, text=True, capture_output=True)
    subprocess.run([sys.executable, str(AUDIT), str(out), "--output", str(audit), "--allow-decoder"], check=True, text=True, capture_output=True)
    card = json.loads((out / "compile_card.json").read_text())
    assert card["loss_counts"]["decoder_ce"] == 1
    assert card["loss_counts"]["denoise_ce"] == 0


def test_compiler_requires_recovered_gate_status_when_enabled(tmp_path: Path) -> None:
    inp = tmp_path / "rows.jsonl"
    out = tmp_path / "compiled"
    rows = [
        {"row_id": "missing_gates", "split": "train", "route": "KEEP_STRUCTURED"},
        {
            "row_id": "gate_clean",
            "split": "train",
            "route": "KEEP_STRUCTURED",
            "gate_status": {
                "source_inventory_lineage": True,
                "source_provenance": True,
                "contamination_leakage_detector": True,
                "golden_locked_eval_suite": True,
                "drift_canary_regression_monitor": True,
                "cluster_slice_near_duplicate_detector": True,
                "dataset_junk_ood_ranker_v1": True,
            },
        },
    ]
    inp.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    subprocess.run(
        [sys.executable, str(COMPILER), "--input", str(inp), "--output-dir", str(out), "--require-recovered-gates"],
        check=True,
        text=True,
        capture_output=True,
    )
    card = json.loads((out / "compile_card.json").read_text())
    assert card["gate_rejected_rows"] == 1
    assert card["objective_counts"]["human_review"] == 1
    assert card["objective_counts"]["structured_state"] == 1
    assert card["loss_counts"]["build_mode_ce"] == 1
    human_rows = (out / "human_review.jsonl").read_text(encoding="utf-8")
    assert "missing_or_failed_recovered_gates" in human_rows
    assert "contamination_leakage_detector" in card["required_recovered_gate_references"]

