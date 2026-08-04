import copy
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12654_repo_code_retention_optimizer_binding_preflight_only.py"
SPEC = importlib.util.spec_from_file_location("stage12654", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def read_json(path: Path):
    return json.loads(path.read_text())


def stable(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def assert_false_boundaries(record):
    for field in stage.FALSE_FIELDS:
        assert field in record
        assert record[field] is False


EXPECTED_ARTIFACTS = [
    "contract.json",
    "digest_pointer.json",
    "private/repo_code_optimizer_trainer_binding_contract.json",
    "private/repo_code_retention_eval_shortcut_baseline_plan.json",
    "private/repo_code_retention_optimizer_binding_packet.json",
    "summary.json",
]


def test_load_inputs_pins_stage12653_and_manifest():
    loaded = stage.load_inputs()
    assert loaded["stage12653_summary"] == read_json(stage.S12653_SUMMARY)
    assert len(loaded["manifest"]) == 280
    assert stable(loaded["manifest"]) == stage.EXPECTED_HASHES["stage12651_manifest_semantic"]
    blockers = loaded["stage12653_summary"]["authorization_blockers"]
    assert "retention_eval_and_shortcut_baseline_plan_not_materialized" in blockers
    assert "optimizer_context_not_bound_to_trainer_implementation" in blockers


def test_retention_plan_materializes_eval_and_shortcut_baselines_without_eval_admission():
    plan = stage.build_retention_plan(stage.load_inputs()["manifest"])
    assert plan["retention_eval_and_shortcut_baseline_plan_materialized"] is True
    assert plan["retention_eval_allowed_next"] is False
    assert plan["shortcut_baseline_execution_allowed_next"] is False
    assert plan["train_rows_in_scope"] == 153
    assert plan["eval_rows_reserved_for_retention"] == 64
    assert plan["strict_eval_rows_reserved_not_admitted"] == 63
    assert len(plan["retention_metrics_plan"]) == 3
    assert len(plan["shortcut_baseline_plan"]) == 4
    assert all(item["must_be_beaten_before_training_admission"] for item in plan["shortcut_baseline_plan"])
    assert_false_boundaries(plan)


def test_optimizer_binding_uses_actual_trainer_and_keeps_execution_contract_blocked():
    loaded = stage.load_inputs()
    binding = stage.build_optimizer_binding(loaded["stage12653_summary"], loaded["manifest"])
    assert binding["optimizer_context_bound_to_trainer_implementation"] is True
    assert binding["trainer_implementation"] == "legacy_src/scripts/train_agentkernel_lite_encdec.py"
    assert binding["optimizer_and_context"]["optimizer"] == "AdamW"
    assert binding["optimizer_and_context"]["max_steps"] == 0
    assert binding["optimizer_and_context"]["model_execution"] == "not_authorized"
    assert binding["trainer_execution_contract_ready"] is False
    assert binding["unsupported_objectives_for_current_trainer_loss_keys"] == ["repo_code_capability_ce"]
    assert "--contract-only" in binding["contract_only_command_template"]
    assert "--execution-authorized-for-recovery-probe" not in binding["contract_only_command_template"]
    assert_false_boundaries(binding)


def test_packet_resolves_only_two_named_blockers_and_keeps_training_closed():
    summary, contract, private, pointer, docs = stage.build_packet(stage.load_inputs())
    assert summary["decision"] == "RETENTION_PLAN_AND_OPTIMIZER_BINDING_MATERIALIZED_REVIEW_REQUIRED_NO_TRAINING"
    assert summary["retention_eval_and_shortcut_baseline_plan_materialized"] is True
    assert summary["optimizer_context_bound_to_trainer_implementation"] is True
    assert set(summary["resolved_authorization_blockers"]) == set(stage.RESOLVED_BLOCKERS)
    assert set(summary["remaining_authorization_blockers"]) == set(stage.REMAINING_BLOCKERS)
    assert summary["remaining_authorization_blocker_count"] == 4
    assert summary["training_allowed"] is False
    assert summary["training_run_allowed"] is False
    assert summary["optimizer_step_authorized"] is False
    assert summary["strict_eval_admitted"] is False
    assert summary["sealed_eval_admitted"] is False
    assert summary["trainer_execution_contract_ready"] is False
    assert contract["private_packet_sha256"] == stable(private)
    assert pointer["retention_plan_sha256"] == stable(docs["retention_plan"])
    assert pointer["optimizer_binding_sha256"] == stable(docs["optimizer_binding"])
    for record in (summary, contract, private, pointer, docs["retention_plan"], docs["optimizer_binding"]):
        assert_false_boundaries(record)


def test_build_writes_preflight_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == EXPECTED_ARTIFACTS
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")


def test_generated_artifacts_match_current_preflight():
    emitted = sorted(path.relative_to(stage.OUT).as_posix() for path in stage.OUT.rglob("*") if path.is_file())
    assert emitted == EXPECTED_ARTIFACTS
    summary = read_json(stage.OUT / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(stage.OUT / "contract.json")
    pointer = read_json(stage.OUT / "digest_pointer.json")
    private = read_json(stage.OUT / "private/repo_code_retention_optimizer_binding_packet.json")
    retention = read_json(stage.OUT / "private/repo_code_retention_eval_shortcut_baseline_plan.json")
    optimizer = read_json(stage.OUT / "private/repo_code_optimizer_trainer_binding_contract.json")
    assert summary == external
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_packet_sha256"] == stable(private)
    assert pointer["retention_plan_sha256"] == stable(retention)
    assert pointer["optimizer_binding_sha256"] == stable(optimizer)
    for record in (summary, external, contract, pointer, private, retention, optimizer):
        assert_false_boundaries(record)


def test_public_artifacts_have_no_training_text_or_private_paths():
    for path in [stage.OUT / "summary.json", stage.SUMMARY, stage.OUT / "contract.json", stage.OUT / "digest_pointer.json"]:
        record = read_json(path)
        encoded = json.dumps(record, sort_keys=True)
        assert '"model_input":' not in encoded
        assert '"target_text":' not in encoded
        assert not [needle for needle in stage.FORBIDDEN_SUBSTRINGS if needle in encoded]
        assert record.get("training_allowed") is not True


def test_rejects_split_or_stage12653_blocker_drift():
    loaded = stage.load_inputs()
    bad_manifest = copy.deepcopy(loaded["manifest"])
    bad_manifest[0]["split"] = "train"
    try:
        stage.build_retention_plan(bad_manifest)
    except stage.Stage12654PreflightError as exc:
        assert "split_count_drift" in str(exc)
    else:
        raise AssertionError("expected split drift rejection")

    bad_summary = copy.deepcopy(loaded["stage12653_summary"])
    bad_summary["optimizer_run_contract"]["optimizer_and_context"] = {"optimizer": "AdamW"}
    try:
        stage.build_optimizer_binding(bad_summary, loaded["manifest"])
    except stage.Stage12654PreflightError as exc:
        assert "stage12653_unexpected_optimizer_binding_present" in str(exc)
    else:
        raise AssertionError("expected unexpected optimizer binding rejection")
