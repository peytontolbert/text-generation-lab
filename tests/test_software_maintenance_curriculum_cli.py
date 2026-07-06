from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/software_maintenance_curriculum_cli.py"


def base_cmd(out: Path) -> list[str]:
    return [
        sys.executable,
        str(SCRIPT),
        "--output-dir",
        str(out),
        "--no-decoder-ce",
        "--no-denoise-ce",
        "--no-runtime",
        "--no-mining",
        "--no-model-execution",
    ]


def test_cli_synthetic_dry_run_writes_required_outputs(tmp_path: Path) -> None:
    out = tmp_path / "compiler"
    result = subprocess.run(base_cmd(out) + ["--mode", "synthetic_dry_run", "--synthetic-only"], check=True, text=True, capture_output=True)
    card = json.loads(result.stdout)
    assert card["rows"] == 3
    assert card["decoder_ce_loss_rows"] == 0
    assert card["denoise_ce_loss_rows"] == 0
    assert card["runtime_reward_rows"] == 0
    assert (out / "judged_rows.jsonl").exists()
    assert (out / "ranked_rows.jsonl").exists()
    assert (out / "compile_card.json").exists()
    assert (out / "compiler_audit_card.json").exists()


def test_cli_rejects_forbidden_training_flag(tmp_path: Path) -> None:
    out = tmp_path / "compiler"
    result = subprocess.run(base_cmd(out) + ["--mode", "synthetic_dry_run", "--synthetic-only", "--train"], text=True, capture_output=True)
    assert result.returncode != 0
    assert "forbidden flags enabled" in result.stderr or "forbidden flags enabled" in result.stdout


def test_cli_requires_closed_safety_flags(tmp_path: Path) -> None:
    out = tmp_path / "compiler"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--output-dir",
            str(out),
            "--mode",
            "synthetic_dry_run",
            "--synthetic-only",
        ],
        text=True,
        capture_output=True,
    )
    assert result.returncode != 0
    assert "--no-decoder-ce" in result.stderr


def test_cli_manifest_no_mining_mode_uses_input_rows(tmp_path: Path) -> None:
    inp = ROOT / "runs" / "local" / "manifests" / "test_cli_manifest_no_mining_rows.jsonl"
    inp.parent.mkdir(parents=True, exist_ok=True)
    try:
        inp.write_text(
            json.dumps(
                {
                    "row_id": "m1",
                    "semantic_key": "g1",
                    "obligation_type": "POSITIVE_ORIGINAL",
                    "encoder": "structured",
                    "target": "action",
                    "decode_allowed": False,
                    "decoder_budget_ok": True,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        out = tmp_path / "compiler"
        result = subprocess.run(base_cmd(out) + ["--mode", "manifest_no_mining_audit_only", "--input", str(inp)], check=True, text=True, capture_output=True)
        card = json.loads(result.stdout)
        assert card["rows"] == 1
        assert card["data_mining_authorized"] is False
        assert card["training_authorized"] is False
    finally:
        if inp.exists():
            inp.unlink()


def test_cli_manifest_mode_rejects_unfocused_input_path(tmp_path: Path) -> None:
    inp = tmp_path / "rows.jsonl"
    inp.write_text("{}\n", encoding="utf-8")
    out = tmp_path / "compiler"
    result = subprocess.run(base_cmd(out) + ["--mode", "manifest_no_mining_audit_only", "--input", str(inp)], text=True, capture_output=True)
    assert result.returncode != 0
    assert "manifest path rejected" in result.stderr or "manifest path rejected" in result.stdout
