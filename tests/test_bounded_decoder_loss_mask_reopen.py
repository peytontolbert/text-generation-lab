from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "scripts" / "build_stage8568_v27_bounded_decoder_ce_loss_mask_reopen_design.py"
AUDIT = ROOT / "scripts" / "audit_stage8569_v27_bounded_decoder_ce_loss_mask_reopen_design_audit.py"


def write_candidates(path: Path, *, unsafe: bool = False) -> None:
    rows = []
    for index, split in enumerate(["train", "eval", "strict_eval"]):
        rows.append(
            {
                "row_id": f"c{index}",
                "split": split,
                "route": "KEEP_BOUNDED_DECODER",
                "decode_allowed": True,
                "decoder_budget_ok": not unsafe,
                "decoder_token_len": 128 if not unsafe else 900,
                "copied_target_text_in_input": False,
                "authority": {"model_execution_authorized_next": False},
            }
        )
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def test_loss_mask_reopen_build_and_audit_pass(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.jsonl"
    rows = tmp_path / "rows.jsonl"
    card = tmp_path / "card.json"
    audit = tmp_path / "audit.json"
    write_candidates(candidates)
    subprocess.run(
        [
            sys.executable,
            str(BUILD),
            "--candidates",
            str(candidates),
            "--rows-output",
            str(rows),
            "--card-output",
            str(card),
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    subprocess.run([sys.executable, str(AUDIT), str(rows), "--output", str(audit)], check=True, text=True, capture_output=True)
    payload = json.loads(audit.read_text())
    assert payload["passed"] is True
    assert payload["gates"]["decoder_ce_only"] is True
    emitted = [json.loads(line) for line in rows.read_text().splitlines() if line]
    assert emitted
    assert all(row["loss_mask"]["decoder_ce"] is True for row in emitted)
    assert all(row["loss_mask"]["runtime_reward"] is False for row in emitted)


def test_loss_mask_reopen_rejects_over_budget_candidates(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.jsonl"
    rows = tmp_path / "rows.jsonl"
    card = tmp_path / "card.json"
    write_candidates(candidates, unsafe=True)
    result = subprocess.run(
        [
            sys.executable,
            str(BUILD),
            "--candidates",
            str(candidates),
            "--rows-output",
            str(rows),
            "--card-output",
            str(card),
        ],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 1
    payload = json.loads(card.read_text())
    assert payload["passed"] is False
    assert payload["selected_rows"] == 0
