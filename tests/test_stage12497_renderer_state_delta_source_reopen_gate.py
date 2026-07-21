from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12497_renderer_state_delta_source_reopen_gate.py"
STAGE12496_SCRIPT = ROOT / "scripts/build_stage12496_policy_label_review_return_validator.py"
RETURN_FILE = (
    ROOT
    / "runs/local/artifacts/stage12495_independent_policy_label_and_action_set_review/"
    "independent_policy_label_review_returns.jsonl"
)
OUT = ROOT / "runs/local/artifacts/stage12497_renderer_state_delta_source_reopen_gate"
SUMMARY = ROOT / "runs/summaries/stage12497_renderer_state_delta_source_reopen_gate.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_stage12497_blocks_without_validated_policy_labels() -> None:
    old = RETURN_FILE.read_text(encoding="utf-8") if RETURN_FILE.exists() else None
    try:
        if RETURN_FILE.exists():
            RETURN_FILE.unlink()
        subprocess.run([sys.executable, str(STAGE12496_SCRIPT)], cwd=ROOT, check=True)
        subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)

        summary = read_json(SUMMARY)
        guardrail = read_json(OUT / "guardrail_scan.json")
        work_items = read_jsonl(OUT / "renderer_state_delta_source_reopen_work_items.jsonl")
        blocked = read_jsonl(OUT / "blocked_gate_refs.jsonl")

        assert summary["decision"] == "blocked_stage12496_zero_accepted_returns"
        assert summary["stage12496_accepted_return_count"] == 0
        assert summary["stage12496_missing_return_count"] == 56
        assert summary["input_validated_policy_label_count"] == 0
        assert summary["renderer_contract_missing_count"] == 56
        assert summary["state_delta_review_missing_count"] == 56
        assert summary["source_reopen_missing_count"] == 56
        assert summary["event_local_input_count"] == 32
        assert summary["event_local_promoted_count"] == 0
        assert summary["validated_stage12497_row_count"] == 0
        assert summary["blocked_stage12497_row_count"] == 1
        assert work_items == []
        assert len(blocked) == 1
        assert "stage12496_zero_accepted_returns" in blocked[0]["reason_codes"]
        assert "training_packaging_premature" in blocked[0]["reason_codes"]
        assert guardrail["scan_passed"] is True
        assert summary["raw_leak_count"] == guardrail["raw_leak_count"] == 0
        assert summary["training_allowed"] is False
        assert summary["admission_allowed"] is False
        assert summary["training_rows_emitted"] == 0
        assert summary["admitted_rows"] == 0
    finally:
        if old is not None:
            RETURN_FILE.write_text(old, encoding="utf-8")
