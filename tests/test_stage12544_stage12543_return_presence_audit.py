import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12544_stage12543_return_presence_audit.py"
SUMMARY = ROOT / "runs/summaries/stage12544_stage12543_return_presence_audit.json"
PRESENCE = ROOT / "runs/local/artifacts/stage12544_stage12543_return_presence_audit/stage12544_stage12543_return_presence_rows.jsonl"
WORKLIST = ROOT / "runs/local/artifacts/stage12544_stage12543_return_presence_audit/stage12544_missing_executor_return_worklist.jsonl"


def load_builder():
    spec = importlib.util.spec_from_file_location("stage12544_builder", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_stage12544_blocks_until_stage12543_executor_returns_exist():
    module = load_builder()
    summary = module.build()

    assert summary["stage"] == "stage12544_stage12543_return_presence_audit"
    assert summary["decision"] == "blocked_waiting_for_stage12543_executor_returns"
    assert summary["stage12543_remaining_shortfall"] == {"FAIL_CURRENT_STATE": 1, "INSUFFICIENT_EVIDENCE": 1}
    assert summary["stage12543_work_items"] == 6
    assert summary["return_files_present"] == 0
    assert summary["return_rows_ingested"] == 0
    assert summary["new_preflight_row_count"] == 0
    assert summary["new_countable_train_support_count"] == 0
    assert summary["missing_return_work_items"] == 6
    assert summary["training_allowed"] is False
    assert summary["countable_train_support"] is False
    assert summary["level3_admitted"] is False
    assert summary["patch_trace_admitted"] is False
    assert summary["repair_claim_admitted"] is False


def test_stage12544_presence_rows_and_worklist_are_hash_only_non_admitting():
    module = load_builder()
    module.build()
    presence = module.read_jsonl(PRESENCE)
    worklist = module.read_jsonl(WORKLIST)

    assert len(presence) == 6
    assert len(worklist) == 6
    assert all(row["return_present"] is False for row in presence)
    assert all(row["candidate_row_emitted"] is False for row in presence)
    assert all(row["training_allowed"] is False for row in presence)
    assert all(row["countable_train_support"] is False for row in presence)
    assert {row["target_status_needed"] for row in worklist} == {"FAIL_CURRENT_STATE", "INSUFFICIENT_EVIDENCE"}
    for row in worklist:
        assert row["missing_return_reason"] == "stage12543_executor_return_file_absent"
        assert row["raw_public_content_allowed"] is False
        assert row["selected_or_exact_test_scope_allowed"] is False
        assert row["controlled_fixture_like_allowed"] is False
        assert row["stage_synthetic_repo_family_allowed"] is False
        assert row["projection_or_transition_derived_label_allowed"] is False
        assert "verifier_output_hash" in row["required_public_return_fields"]
        assert "command_observation_join_hash" in row["required_public_return_fields"]


def test_stage12544_return_filenames_are_specific_not_globbed():
    module = load_builder()

    assert module.RETURN_FILENAMES == [
        "stage12543_executor_returns.jsonl",
        "stage12543_remaining_gap_executor_returns.jsonl",
        "private_stage12543_executor_returns.jsonl",
    ]



def test_partial_return_file_only_marks_matching_work_item(tmp_path, monkeypatch):
    module = load_builder()
    work_items = module.read_jsonl(module.STAGE12543_WORK_ITEMS)
    first_id = work_items[0]["work_item_id"]
    return_file = tmp_path / "stage12543_executor_returns.jsonl"
    return_file.write_text(
        "\n".join([
            "{bad json",
            '{"work_item_id":"unknown-id"}',
            '{"work_item_id":"' + first_id + '"}',
            '{"work_item_id":"' + first_id + '"}',
        ]) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "return_paths", lambda: [return_file])
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "OUT", tmp_path / "audit_out")
    monkeypatch.setattr(module, "SUMMARY", tmp_path / "summary.json")
    summary = module.build()
    presence = module.read_jsonl(module.OUT / module.RETURN_PRESENCE_NAME)
    worklist = module.read_jsonl(module.OUT / module.MISSING_RETURN_WORKLIST_NAME)

    assert summary["decision"] == "partial_returns_present_still_blocked"
    assert summary["return_rows_ingested"] == 2
    assert summary["return_row_validation"]["malformed_rows"] == 1
    assert summary["return_row_validation"]["unknown_id_rows"] == 1
    assert summary["return_row_validation"]["duplicate_rows"] == 1
    assert sum(row["return_present"] for row in presence) == 1
    assert len(worklist) == 5
    assert first_id not in {row["work_item_id"] for row in worklist}


def test_complete_matching_returns_do_not_admit_candidates(tmp_path, monkeypatch):
    module = load_builder()
    work_items = module.read_jsonl(module.STAGE12543_WORK_ITEMS)
    return_file = tmp_path / "stage12543_executor_returns.jsonl"
    return_file.write_text(
        "".join('{"work_item_id":"' + row["work_item_id"] + '"}\n' for row in work_items),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "return_paths", lambda: [return_file])
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "OUT", tmp_path / "audit_out")
    monkeypatch.setattr(module, "SUMMARY", tmp_path / "summary.json")
    summary = module.build()
    presence = module.read_jsonl(module.OUT / module.RETURN_PRESENCE_NAME)

    assert summary["decision"] == "returns_complete_presence_only"
    assert summary["missing_return_work_items"] == 0
    assert all(row["return_present"] is True for row in presence)
    assert summary["training_allowed"] is False
    assert summary["countable_train_support"] is False
