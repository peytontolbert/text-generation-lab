import copy
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12649_repo_code_training_pack_materialization_preflight_only.py"
SPEC = importlib.util.spec_from_file_location("stage12649", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def read_json(path: Path):
    return json.loads(path.read_text())


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def stable(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def assert_false_boundaries(record):
    for field in stage.FALSE_FIELDS:
        assert field in record
        assert record[field] is False


EXPECTED_ARTIFACTS = [
    "contract.json",
    "digest_pointer.json",
    "private/repo_code_training_examples.jsonl",
    "private/repo_code_training_pack_materialization_packet.json",
    "summary.json",
]


def test_load_inputs_pins_stage12648_and_sources():
    loaded = stage.load_inputs()
    assert loaded["stage12648_summary"] == read_json(stage.S12648_SUMMARY)
    assert loaded["stage12648_summary"]["decision"] == "BLOCKED_TRAINING_PACK_MATERIALIZATION_REQUIRED"
    assert len(loaded["admitted"]) == 280
    assert len(loaded["ce_rows"]) == 200
    assert len(loaded["repaired_rows"]) == 80
    assert len(loaded["quarantine_rows"]) == 45


def test_materialize_training_examples_joins_admitted_hashes_to_real_rows():
    examples = stage.materialize_training_examples(stage.load_inputs())
    assert len(examples) == 280
    assert stage.component_counts(examples) == stage.EXPECTED_COUNTS
    assert stage.split_counts(examples) == stage.EXPECTED_SPLITS
    assert sum(1 for row in examples if row["loss_mask"].get("repo_code_ce") is True) == 200
    assert sum(1 for row in examples if row["loss_mask"].get("symbol_binding_ce") is True) == 80
    assert all(row["optimizer_ready"] is True for row in examples)
    assert all(row["training_allowed"] is False for row in examples)
    assert all(row["model_input"].strip() for row in examples)
    assert all(row["target_text"].strip() for row in examples)
    assert not any("/data/" in json.dumps(row) or "/arxiv/" in json.dumps(row) for row in examples)
    assert not any("source_row_id" in json.dumps(row) or "source_ref" in json.dumps(row) for row in examples)


def test_training_pack_audit_marks_pack_materialized_but_training_closed():
    examples = stage.materialize_training_examples(stage.load_inputs())
    audit = stage.audit_examples(examples)
    assert audit["training_pack_materialized"] is True
    assert audit["training_examples_materialized"] is True
    assert audit["model_ready_training_rows"] == 280
    assert audit["repo_code_ce_training_examples"] == 200
    assert audit["symbol_binding_training_examples"] == 80
    assert audit["quarantined_rows_in_training_pack"] == 0
    assert audit["placeholder_training_rows"] == 0
    assert audit["raw_path_training_rows"] == 0
    assert audit["unique_source_row_hashes"] == 280
    assert audit["unique_model_input_hashes"] >= 120


def test_packet_claim_boundary_materializes_pack_without_authorizing_training():
    summary, contract, private, pointer, examples = stage.build_packet(stage.load_inputs())
    assert summary["decision"] == "TRAINING_PACK_MATERIALIZED_REVIEW_REQUIRED_NO_TRAINING"
    assert summary["training_pack_materialized"] is True
    assert summary["training_examples_materialized"] is True
    assert summary["model_ready_training_rows"] == 280
    assert summary["training_allowed"] is False
    assert summary["training_run_allowed"] is False
    assert summary["optimizer_step_authorized"] is False
    assert summary["strict_eval_admitted"] is False
    assert summary["sealed_eval_admitted"] is False
    assert summary["level_3_materialized"] is False
    assert summary["next_required_action"] == "stage12650_repo_code_training_pack_independent_review_only"
    assert contract["private_packet_sha256"] == stable(private)
    assert pointer["training_examples_sha256"] == stable(examples)
    for record in (summary, contract, private, pointer):
        assert_false_boundaries(record)


def test_build_writes_training_pack_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == EXPECTED_ARTIFACTS
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")
    examples = read_jsonl(out / "private/repo_code_training_examples.jsonl")
    assert len(examples) == 280
    assert stable(examples) == summary["training_examples_sha256"]


def test_generated_artifacts_match_current_training_pack_materialization():
    emitted = sorted(path.relative_to(stage.OUT).as_posix() for path in stage.OUT.rglob("*") if path.is_file())
    assert emitted == EXPECTED_ARTIFACTS
    summary = read_json(stage.OUT / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(stage.OUT / "contract.json")
    pointer = read_json(stage.OUT / "digest_pointer.json")
    private = read_json(stage.OUT / "private/repo_code_training_pack_materialization_packet.json")
    examples = read_jsonl(stage.OUT / "private/repo_code_training_examples.jsonl")
    assert summary == external
    assert summary["model_ready_training_rows"] == 280
    assert summary["training_allowed"] is False
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_packet_sha256"] == stable(private)
    assert pointer["training_examples_sha256"] == stable(examples)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_public_artifacts_have_no_private_text_or_authority():
    for path in [stage.OUT / "summary.json", stage.SUMMARY, stage.OUT / "contract.json", stage.OUT / "digest_pointer.json"]:
        record = read_json(path)
        encoded = json.dumps(record, sort_keys=True)
        assert not [needle for needle in stage.PUBLIC_FORBIDDEN_SUBSTRINGS if needle in encoded]
        assert record.get("training_allowed") is not True
        assert record.get("training_run_allowed") is not True
        assert record.get("optimizer_step_authorized") is not True
        assert record.get("strict_eval_admitted") is not True
        assert record.get("sealed_eval_admitted") is not True
        assert record.get("level_3_materialized") is not True


def test_materialization_rejects_quarantined_or_missing_source_rows():
    loaded = stage.load_inputs()
    quarantined_hash = loaded["quarantine_rows"][0]["row_sha256"]
    bad = copy.deepcopy(loaded)
    symbol_index = next(i for i, row in enumerate(bad["admitted"]) if row["admission_family"] == "source_backed_symbol_binding")
    bad["admitted"][symbol_index]["source_row_sha256"] = quarantined_hash
    try:
        stage.materialize_training_examples(bad)
    except stage.Stage12649TrainingPackError as exc:
        assert "quarantined_row_admitted_to_training_pack" in str(exc)
    else:
        raise AssertionError("expected quarantined row rejection")

    missing = copy.deepcopy(loaded)
    missing["admitted"][0]["source_row_sha256"] = "0" * 64
    try:
        stage.materialize_training_examples(missing)
    except stage.Stage12649TrainingPackError as exc:
        assert "missing_repo_code_source_row" in str(exc)
    else:
        raise AssertionError("expected missing source row rejection")
