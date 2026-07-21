from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12514_causal_proof_revalidation_gate.py"
OUT = ROOT / "runs/local/artifacts/stage12514_causal_proof_revalidation_gate"
SUMMARY = ROOT / "runs/summaries/stage12514_causal_proof_revalidation_gate.json"


def load_stage12514():
    spec = importlib.util.spec_from_file_location("stage12514", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def slot_update_row() -> dict:
    return {
        "record_type": "stage12504_closed_loop_proof_slot_update_v1",
        "slot_update_id_hash": "1" * 24,
        "validated_extraction_id_hash": "2" * 24,
        "request_id_hash": "3" * 24,
        "work_item_id_hash": "4" * 24,
        "packet_id_hash": "5" * 24,
        "root_or_window_hash": "6" * 24,
        "source_stage": "stage12374_python_task_specific_selected_test_rerender",
        "source_kind": "selected_test_bounded_transition_support",
        "task_family": "transition_next_action",
        "language_family": "python",
        "proof_slot_updates": {
            "same_source_causal_lineage": {"validated_present": True},
            "authoritative_state_before": {"validated_present": False},
            "state_delta_or_state_after": {"validated_present": False},
            "patch_apply_status": {"validated_present": False},
            "stop_continue": {"validated_present": False},
        },
        "training_rows_emitted": 0,
        "admitted_rows": 0,
    }


def test_stage12514_current_production_demotes_locator_only_lineage() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)
    summary = read_json(SUMMARY)
    records = read_jsonl(OUT / "causal_proof_revalidation_records.jsonl")
    contract = read_json(OUT / "causal_proof_revalidation_contract.json")

    assert summary["decision"] == "causal_proof_revalidation_demoted_locator_only_lineage_training_and_admission_blocked"
    assert summary["input_slot_update_count"] == 49
    assert summary["revalidation_record_count"] == 49
    assert summary["demoted_slot_counts"] == {"same_source_causal_lineage": 49}
    assert summary["corrected_causal_slot_validated_count"] == 0
    assert summary["corrected_blocker_code_counts"]["same_source_lineage_locator_only_not_causal"] == 49
    assert summary["training_rows_emitted"] == 0
    assert summary["admitted_rows"] == 0
    assert summary["level3_admitted"] == 0
    assert summary["patch_trace_admitted"] == 0
    assert summary["raw_leak_count"] == 0
    assert len(records) == 49
    assert all("same_source_causal_lineage" in row["demoted_slots"] for row in records)
    assert contract["demote_locator_only_lineage"] is True


def test_stage12514_tmp_demotes_seen_lineage_and_blocks_all_causal_slots(tmp_path: Path) -> None:
    stage12514 = load_stage12514()
    ledger = tmp_path / "runs/local/artifacts/stage12504_closed_loop_slot_update_from_validated_private_extraction_status/closed_loop_proof_slot_update_ledger.jsonl"
    write_jsonl(ledger, [slot_update_row()])

    summary = stage12514.build(tmp_path)
    records = read_jsonl(tmp_path / "runs/local/artifacts/stage12514_causal_proof_revalidation_gate/causal_proof_revalidation_records.jsonl")

    assert summary["input_slot_update_count"] == 1
    assert summary["demoted_slot_counts"] == {"same_source_causal_lineage": 1}
    assert summary["corrected_causal_slot_validated_count"] == 0
    assert records[0]["corrected_causal_slots_validated"] == []
    assert "same_source_lineage_locator_only_not_causal" in records[0]["corrected_residual_blocker_codes"]
    assert "external_patch_effect_proof_missing" in records[0]["corrected_residual_blocker_codes"]
    assert records[0]["training_rows_emitted"] == 0
    assert records[0]["admitted_rows"] == 0


def test_stage12514_no_ledger_emits_empty_safe_summary(tmp_path: Path) -> None:
    stage12514 = load_stage12514()
    summary = stage12514.build(tmp_path)

    assert summary["input_slot_update_count"] == 0
    assert summary["revalidation_record_count"] == 0
    assert summary["corrected_causal_slot_validated_count"] == 0
    assert summary["training_rows_emitted"] == 0
    assert summary["admitted_rows"] == 0
