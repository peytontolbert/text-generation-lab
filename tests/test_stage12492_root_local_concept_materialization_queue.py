from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12492_root_local_concept_materialization_queue.py"
OUT = ROOT / "runs/local/artifacts/stage12492_root_local_concept_materialization_queue"
SUMMARY = ROOT / "runs/summaries/stage12492_root_local_concept_materialization_queue.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_stage12492_emits_root_local_work_queue_without_admission() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)

    summary = read_json(SUMMARY)
    guardrail = read_json(OUT / "guardrail_scan.json")
    rows = read_jsonl(OUT / "root_local_concept_materialization_work_items.jsonl")

    assert summary["decision"] == "root_local_concept_materialization_queue_ready_no_training_no_admission"
    assert summary["work_item_count"] == len(rows)
    assert summary["work_item_count"] > 0
    assert summary["target_root_count_floor"] == sum(row["target_root_count"] for row in rows)
    assert summary["target_row_floor"] == sum(row["target_row_floor"] for row in rows)
    assert summary["target_language_family_count"] == 4
    assert guardrail["scan_passed"] is True
    assert guardrail["raw_leak_count"] == 0
    assert summary["training_allowed"] is False
    assert summary["admission_allowed"] is False
    assert summary["training_rows_emitted"] == 0
    assert summary["external_repair_credit_count"] == 0

    for row in rows:
        assert row["claim_boundary"] == {
            "materialization_work_item": True,
            "reviewed_train_support": False,
            "proof_grade_repair": False,
        }
        assert row["training_allowed"] is False
        assert row["admission_allowed"] is False
        assert row["external_repair_credit_count"] == 0
        assert row["target_language_families"] == ["python", "rust", "c_cpp", "web_js_ts_html"]
        assert row["blocked_until"]
        assert "candidate_action_set_hash" in row["required_model_visible_fields"]
        assert "independent_policy_label_hash" in row["required_model_visible_fields"]
