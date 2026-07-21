import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12546_stage12543_private_source_binding_resolver.py"


def load_builder():
    spec = importlib.util.spec_from_file_location("stage12546_binding", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_stage12546_recomputes_all_salted_source_bindings_uniquely():
    module = load_builder()
    work_items = module.read_jsonl(module.STAGE12543_WORK_ITEMS)
    source_rows = module.read_jsonl(module.STAGE12209_LOG_INDEX)

    for item in work_items:
        repo_rows = [
            row for row in source_rows
            if module.stage12543_repo_hash(str(row.get("repo_family") or ""))
            == item["repo_family_hash"]
        ]
        resolved = {
            module.stage12543_line_hash(int(row["__line_no"]), str(row["repo_family"]))
            for row in repo_rows
        }
        assert set(item["source_log_line_hashes"]) <= resolved


def test_stage12546_emits_private_bindings_and_hash_only_public_audit(tmp_path):
    module = load_builder()
    module.OUT = tmp_path / "out"
    module.SUMMARY = tmp_path / "summary.json"
    summary = module.build()

    private_rows = module.read_jsonl(module.OUT / module.PRIVATE_BINDINGS_NAME)
    public_rows = module.read_jsonl(module.OUT / module.PUBLIC_BINDINGS_NAME)
    assert len(private_rows) == 6
    assert len(public_rows) == 6
    assert all(row["execution_authorized"] is False for row in private_rows)
    assert all(row["training_allowed"] is False for row in public_rows)
    assert all(len(row["repo_commit_digest"]) in {64, 7} for row in public_rows)

    public_text = (module.OUT / module.PUBLIC_BINDINGS_NAME).read_text(encoding="utf-8")
    for forbidden in ('"repo_root"', '"cwd"', '"command"', '"repo_family"', '"source_record_path"'):
        assert forbidden not in public_text

    assert any(row.get("repo_root") for row in private_rows)
    assert any(row.get("candidate_commands") for row in private_rows)
    assert summary["execution_performed"] is False
    assert summary["new_preflight_row_count"] == 0
    assert summary["new_countable_train_support_count"] == 0
    assert summary["authoritative_countable_root_progress_delta"] == 0


def test_stage12546_does_not_reuse_consumed_or_invalid_source_results(tmp_path):
    module = load_builder()
    module.OUT = tmp_path / "out"
    module.SUMMARY = tmp_path / "summary.json"
    summary = module.build()
    private_rows = module.read_jsonl(module.OUT / module.PRIVATE_BINDINGS_NAME)

    blocker_codes = {
        blocker
        for row in private_rows
        for command in row["candidate_commands"]
        for blocker in command["blocker_codes"]
    }
    assert "already_consumed_stage12541_source" in blocker_codes
    assert "environment_or_invalid_command_failure" in blocker_codes
    assert "selected_or_exact_test_scope" in blocker_codes
    assert summary["execution_ready_target_counts"] == {}
    assert summary["decision"] == "private_bindings_resolved_no_admissible_commands_no_execution"


def test_stage12546_public_artifacts_are_fixed_schema_no_free_text(tmp_path):
    module = load_builder()
    module.OUT = tmp_path / "out"
    module.SUMMARY = tmp_path / "summary.json"
    module.build()

    rows = module.read_jsonl(module.OUT / module.PUBLIC_BINDINGS_NAME)
    allowed_outcomes = {
        "binding_blocked",
        "no_admissible_command",
        "multiple_admissible_commands_manual_selection_required",
        "binding_resolved_execution_candidate",
    }
    assert all(row["binding_outcome"] in allowed_outcomes for row in rows)
    assert all(isinstance(row["binding_blocker_codes"], list) for row in rows)
    assert all(row["repair_claim_admitted"] is False for row in rows)
    assert all(row["level3_admitted"] is False for row in rows)


def test_stage12546_private_manifest_is_not_mislabeled_training_data(tmp_path):
    module = load_builder()
    module.OUT = tmp_path / "out"
    module.SUMMARY = tmp_path / "summary.json"
    module.build()
    rows = module.read_jsonl(module.OUT / module.PRIVATE_BINDINGS_NAME)

    for row in rows:
        assert row["training_allowed"] is False
        assert row["countable_train_support"] is False
        assert row["patch_trace_admitted"] is False
        assert row["fail_to_pass_claim_admitted"] is False
        assert row["execution_authorized"] is False
