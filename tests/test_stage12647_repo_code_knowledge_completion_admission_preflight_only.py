import copy
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12647_repo_code_knowledge_completion_admission_preflight_only.py"
SPEC = importlib.util.spec_from_file_location("stage12647", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def read_json(path: Path):
    return json.loads(path.read_text())


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def stable(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def assert_no_training_boundaries(record):
    for field in stage.FORBIDDEN_TRUE_FIELDS:
        assert field in record
        assert record[field] is False


EXPECTED_ARTIFACTS = [
    "contract.json",
    "digest_pointer.json",
    "private/admitted_repo_code_knowledge_rows.jsonl",
    "private/repo_code_knowledge_completion_admission_packet.json",
    "summary.json",
]


def test_load_inputs_pins_reviewed_sources():
    inputs = stage.load_inputs()
    assert inputs["stage12642"]["repo_code_knowledge_substrate_recovered"] is True
    assert inputs["stage12644_summary"]["candidate_rows_independently_reviewed"] == 200
    assert inputs["stage12646_summary"]["repaired_rows_reviewed"] == 80
    assert len(inputs["ce_rows"]) == 200
    assert len(inputs["repaired_rows"]) == 80
    assert len(inputs["quarantine_rows"]) == 45


def test_audit_inputs_clears_known_completion_blockers():
    audit = stage.audit_inputs(stage.load_inputs())
    assert audit["repo_code_ce_rows_reviewed_for_admission"] == 200
    assert audit["symbol_binding_rows_reviewed_for_admission"] == 80
    assert audit["quarantined_rows_excluded"] == 45
    assert audit["repo_code_ce_split_counts"] == {"eval": 40, "strict_eval": 39, "train": 121}
    assert audit["symbol_binding_split_counts"] == {"eval": 24, "strict_eval": 24, "train": 32}
    assert audit["admitted_split_counts"] == {"eval": 64, "strict_eval": 63, "train": 153}
    assert audit["ce_cross_split_duplicate_opaque_repo_ids"] == 0
    assert audit["symbol_shortcut_feature_cells_after_recompute"] == 0


def test_private_admitted_records_are_concrete_hash_only_and_no_training():
    inputs = stage.load_inputs()
    admitted = stage.admitted_records(inputs)
    assert len(admitted) == 280
    assert len({row["source_row_sha256"] for row in admitted}) == 280
    counts = {}
    for row in admitted:
        counts[row["admission_family"]] = counts.get(row["admission_family"], 0) + 1
        assert row["repo_code_knowledge_admitted"] is True
        assert row["training_allowed"] is False
        encoded = json.dumps(row, sort_keys=True)
        assert "/arxiv/" not in encoded
        assert "/data/" not in encoded
        assert "source_row_id" not in encoded
    assert counts == {"repo_code_ce": 200, "source_backed_symbol_binding": 80}


def test_packet_completes_repo_code_knowledge_but_not_training_or_eval():
    summary, contract, private, pointer, admitted = stage.build_packet(stage.load_inputs())
    assert summary["decision"] == "REPO_CODE_KNOWLEDGE_COMPLETION_ADMISSION_PREFLIGHT_PASSED_NO_TRAINING"
    assert summary["repo_code_knowledge_stage_complete"] is True
    assert summary["repo_code_rows_admitted"] is True
    assert summary["dataset_rows_admitted"] is True
    assert summary["new_rows_admitted"] is True
    assert summary["repo_code_knowledge_rows_admitted"] == 280
    assert summary["quarantined_rows_excluded"] == 45
    assert summary["model_ready_training_rows"] == 0
    assert summary["training_allowed"] is False
    assert summary["training_run_allowed"] is False
    assert summary["strict_eval_admitted"] is False
    assert summary["sealed_eval_admitted"] is False
    assert summary["level_3_materialized"] is False
    assert summary["separate_training_admission_required"] is True
    assert summary["next_required_action"] == "separate_training_admission_preflight_only"
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_packet_sha256"] == stable(private)
    assert pointer["admitted_manifest_sha256"] == stable(admitted)
    for record in (summary, contract, private, pointer):
        assert_no_training_boundaries(record)


def test_build_writes_completion_admission_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == EXPECTED_ARTIFACTS
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")
    assert len(read_jsonl(out / "private/admitted_repo_code_knowledge_rows.jsonl")) == 280


def test_generated_artifacts_match_current_completion_admission():
    out = stage.OUT
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == EXPECTED_ARTIFACTS
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/repo_code_knowledge_completion_admission_packet.json")
    admitted = read_jsonl(out / "private/admitted_repo_code_knowledge_rows.jsonl")
    assert summary == external
    assert summary["repo_code_knowledge_stage_complete"] is True
    assert summary["dataset_rows_admitted"] is True
    assert summary["training_allowed"] is False
    assert summary["strict_eval_admitted"] is False
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_packet_sha256"] == stable(private)
    assert pointer["admitted_manifest_sha256"] == stable(admitted)
    for record in (summary, contract, pointer, private):
        assert_no_training_boundaries(record)


def test_public_artifacts_have_no_private_leaks_and_no_training_authority():
    public_paths = [
        stage.OUT / "summary.json",
        stage.SUMMARY,
        stage.OUT / "contract.json",
        stage.OUT / "digest_pointer.json",
    ]
    for path in public_paths:
        record = read_json(path)
        encoded = json.dumps(record, sort_keys=True)
        assert not [needle for needle in stage.PUBLIC_FORBIDDEN_SUBSTRINGS if needle in encoded]
        assert record.get("training_allowed") is not True
        assert record.get("training_run_allowed") is not True
        assert record.get("strict_eval_admitted") is not True
        assert record.get("sealed_eval_admitted") is not True
        assert record.get("level_3_materialized") is not True


def test_admission_rejects_unreviewed_or_quarantined_row_regressions():
    inputs = stage.load_inputs()
    bad = copy.deepcopy(inputs)
    bad["stage12646_summary"]["repaired_shortcut_feature_cells"] = 1
    try:
        stage.audit_inputs(bad)
    except stage.Stage12647AdmissionError as exc:
        assert "symbol_shortcut_regression" in str(exc) or "stage12646" in str(exc)
    else:
        raise AssertionError("expected shortcut regression rejection")

    bad = copy.deepcopy(inputs)
    bad["quarantine_rows"][0]["row_sha256"] = stage.stable_hash(bad["repaired_rows"][0])
    try:
        stage.audit_inputs(bad)
    except stage.Stage12647AdmissionError as exc:
        assert "quarantined_rows_admitted" in str(exc)
    else:
        raise AssertionError("expected quarantined row admission rejection")
