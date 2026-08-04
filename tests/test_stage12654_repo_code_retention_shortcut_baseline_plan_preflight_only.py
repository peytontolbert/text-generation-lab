import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12654_repo_code_retention_shortcut_baseline_plan_preflight_only.py"
SPEC = importlib.util.spec_from_file_location("stage12654", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)

def read_json(path: Path):
    return json.loads(path.read_text())

def stable(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()

def assert_false(record):
    for field in stage.FALSE_FIELDS:
        assert record[field] is False

EXPECTED_ARTIFACTS=["contract.json","digest_pointer.json","private/repo_code_retention_shortcut_baseline_plan_packet.json","summary.json"]

def test_load_inputs_pins_stage12653():
    loaded=stage.load_inputs()
    assert loaded["summary"] == read_json(stage.S12653_SUMMARY)
    assert len(loaded["manifest"]) == 280

def test_build_baseline_plan_reserves_eval_and_shortcut_checks():
    plan=stage.build_baseline_plan(stage.load_inputs()["manifest"])
    assert plan["retention_eval_rows"] == 64
    assert plan["strict_eval_rows_reserved_not_admitted"] == 63
    assert plan["train_rows_for_shortcut_shadow_baseline"] == 153
    assert "lane_label_ablation" in plan["shortcut_baseline_checks"]
    assert plan["training_allowed"] is False
    assert plan["model_forward_allowed"] is False

def test_packet_resolves_only_baseline_blocker_no_training():
    summary,contract,private,pointer=stage.build_packet(stage.load_inputs())
    assert summary["decision"] == "RETENTION_SHORTCUT_BASELINE_PLAN_MATERIALIZED_NO_TRAINING"
    assert summary["retention_eval_and_shortcut_baseline_plan_materialized"] is True
    assert summary["remaining_authorization_blocker_count"] == 5
    assert "retention_eval_and_shortcut_baseline_plan_not_materialized" not in summary["remaining_authorization_blockers"]
    assert summary["training_allowed"] is False
    assert summary["optimizer_step_authorized"] is False
    assert pointer["contract_sha256"] == stable(contract)
    for record in (summary,contract,private,pointer):
        assert_false(record)

def test_build_writes_artifacts(tmp_path):
    out=tmp_path/"artifacts"/stage.STAGE
    summary_path=tmp_path/"summaries"/f"{stage.STAGE}.json"
    summary=stage.build(out, summary_path)
    emitted=sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())
    assert emitted == EXPECTED_ARTIFACTS
    assert summary == read_json(summary_path)

def test_generated_artifacts_match_current():
    emitted=sorted(p.relative_to(stage.OUT).as_posix() for p in stage.OUT.rglob("*") if p.is_file())
    assert emitted == EXPECTED_ARTIFACTS
    summary=read_json(stage.OUT/"summary.json")
    assert summary == read_json(stage.SUMMARY)
    contract=read_json(stage.OUT/"contract.json")
    pointer=read_json(stage.OUT/"digest_pointer.json")
    private=read_json(stage.OUT/"private/repo_code_retention_shortcut_baseline_plan_packet.json")
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_packet_sha256"] == stable(private)
    for record in (summary,contract,pointer,private):
        assert_false(record)

def test_public_artifacts_sanitized():
    for path in [stage.OUT/"summary.json", stage.SUMMARY, stage.OUT/"contract.json", stage.OUT/"digest_pointer.json"]:
        encoded=json.dumps(read_json(path), sort_keys=True)
        assert not [needle for needle in stage.FORBIDDEN if needle in encoded]
