import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12642_repo_code_knowledge_completion_audit_only.py"
SPEC = importlib.util.spec_from_file_location("stage12642", SCRIPT)
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


def true_fields(record):
    return {key for key, value in record.items() if value is True}


ALLOWED_TRUE = {
    "repo_code_knowledge_substrate_recovered",
    "repo_code_knowledge_completion_audit_only",
    "stage12642_repo_code_knowledge_completion_audit_performed",
    "vm_branch_remains_paused",
}
EXPECTED_ARTIFACTS = [
    "contract.json",
    "digest_pointer.json",
    "private/repo_code_knowledge_completion_audit_only.json",
    "summary.json",
]


def test_audit_inputs_distinguishes_recovered_substrate_from_complete_training_stage():
    inputs = stage.load_inputs()
    audit = stage.audit_inputs(inputs)
    assert audit["repo_code_knowledge_substrate_recovered"] is True
    assert audit["repo_code_knowledge_stage_complete"] is False
    assert audit["repository_inventory_repos_indexed"] == 500
    assert audit["dataset_files_indexed"] == 2530
    assert audit["graph_seed_rows"] == 200
    assert audit["catalog_rows"] == 200
    assert audit["model_ready_training_rows"] == 0
    assert audit["symbol_binding_audit_passed"] is False
    assert audit["symbol_binding_shortcut_feature_cells"] == 1
    assert "repo_code_ce_training_manifest_not_materialized" in audit["completion_blockers"]


def test_packet_blocks_completion_training_and_admission():
    summary, contract, private = stage.build_packet(stage.load_inputs())
    assert summary["decision"] == "REPO_CODE_KNOWLEDGE_SUBSTRATE_RECOVERED_STAGE_NOT_COMPLETE_NO_TRAINING"
    assert summary["repo_code_knowledge_substrate_recovered"] is True
    assert summary["repo_code_knowledge_stage_complete"] is False
    assert summary["repo_code_ce_manifest_materialized"] is False
    assert summary["repo_code_rows_admitted"] is False
    assert summary["training_allowed"] is False
    assert summary["dataset_rows_admitted"] is False
    assert true_fields(summary) == ALLOWED_TRUE
    assert true_fields(contract) == ALLOWED_TRUE
    assert true_fields(private) == ALLOWED_TRUE
    for record in (summary, contract, private):
        assert_false_boundaries(record)


def test_build_writes_completion_audit_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == EXPECTED_ARTIFACTS
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")


def test_generated_artifacts_match_current_completion_audit():
    out = stage.OUT
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == EXPECTED_ARTIFACTS
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/repo_code_knowledge_completion_audit_only.json")
    assert summary == external
    assert summary["repo_code_knowledge_stage_complete"] is False
    assert summary["training_allowed"] is False
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_repo_code_knowledge_completion_audit_sha256"] == stable(private)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_public_artifacts_have_no_private_paths_or_training_authority():
    for path in [stage.OUT / "summary.json", stage.SUMMARY, stage.OUT / "contract.json", stage.OUT / "digest_pointer.json"]:
        record = read_json(path)
        encoded = json.dumps(record, sort_keys=True)
        assert not [needle for needle in stage.PUBLIC_FORBIDDEN_SUBSTRINGS if needle in encoded]
        assert record.get("training_allowed") is not True
        assert record.get("dataset_rows_admitted") is not True
        assert record.get("repo_code_knowledge_stage_complete") is not True
