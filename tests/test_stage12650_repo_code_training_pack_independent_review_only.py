import copy
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12650_repo_code_training_pack_independent_review_only.py"
SPEC = importlib.util.spec_from_file_location("stage12650", SCRIPT)
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
    "private/repo_code_training_pack_independent_review_packet.json",
    "summary.json",
]


def test_load_stage12649_pins_pack_artifacts_and_examples():
    loaded = stage.load_stage12649()
    assert loaded["summary"] == read_json(stage.S12649_SUMMARY)
    assert len(loaded["examples"]) == 280
    assert len(loaded["admitted"]) == 280
    assert len(loaded["ce_rows"]) == 200
    assert len(loaded["repaired_rows"]) == 80
    assert len(loaded["quarantine_rows"]) == 45
    assert stable(loaded["examples"]) == stage.EXPECTED_HASHES["stage12649_examples_semantic"]
    assert loaded["summary"]["decision"] == "TRAINING_PACK_MATERIALIZED_REVIEW_REQUIRED_NO_TRAINING"
    assert loaded["summary"]["training_allowed"] is False


def test_review_training_pack_accepts_real_sanitized_examples():
    audit = stage.review_training_pack(stage.load_stage12649())
    assert audit["training_pack_reviewed"] is True
    assert audit["training_pack_review_passed"] is True
    assert audit["model_ready_training_rows"] == 280
    assert audit["repo_code_ce_training_examples"] == 200
    assert audit["symbol_binding_training_examples"] == 80
    assert audit["training_split_counts"] == stage.EXPECTED_SPLITS
    assert audit["training_objective_counts"] == stage.EXPECTED_OBJECTIVES
    assert audit["placeholder_training_rows"] == 0
    assert audit["raw_path_training_rows"] == 0
    assert audit["private_lineage_training_rows"] == 0
    assert audit["admitted_row_joins_verified"] == 280
    assert audit["reviewed_source_joins_verified"] == 280
    assert audit["training_text_renders_verified"] == 280
    assert audit["review_blocker_count"] == 0


def test_review_packet_passes_review_without_authorizing_training():
    summary, contract, private, pointer = stage.build_packet(stage.load_stage12649())
    assert summary["decision"] == "TRAINING_PACK_REVIEW_PASSED_SEPARATE_TRAINING_ADMISSION_REQUIRED"
    assert summary["training_pack_reviewed"] is True
    assert summary["training_pack_review_passed"] is True
    assert summary["training_allowed"] is False
    assert summary["training_run_allowed"] is False
    assert summary["optimizer_step_authorized"] is False
    assert summary["strict_eval_admitted"] is False
    assert summary["sealed_eval_admitted"] is False
    assert summary["level_3_materialized"] is False
    assert summary["next_required_action"] == "stage12651_separate_training_admission_preflight_only"
    assert contract["private_packet_sha256"] == stable(private)
    assert pointer["contract_sha256"] == stable(contract)
    for record in (summary, contract, private, pointer):
        assert_false_boundaries(record)


def test_build_writes_review_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == EXPECTED_ARTIFACTS
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")
    assert summary["model_ready_training_rows"] == 280


def test_generated_artifacts_match_current_review():
    emitted = sorted(path.relative_to(stage.OUT).as_posix() for path in stage.OUT.rglob("*") if path.is_file())
    assert emitted == EXPECTED_ARTIFACTS
    summary = read_json(stage.OUT / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(stage.OUT / "contract.json")
    pointer = read_json(stage.OUT / "digest_pointer.json")
    private = read_json(stage.OUT / "private/repo_code_training_pack_independent_review_packet.json")
    assert summary == external
    assert summary["training_pack_review_passed"] is True
    assert summary["training_allowed"] is False
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_packet_sha256"] == stable(private)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_public_review_artifacts_do_not_expose_training_text_or_private_paths():
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


def test_review_rejects_placeholder_leak_and_loss_mask_drift():
    loaded = stage.load_stage12649()
    bad = copy.deepcopy(loaded)
    bad["examples"][0]["model_input"] += "\nPLACEHOLDER"
    try:
        stage.review_training_pack(bad)
    except stage.Stage12650ReviewError as exc:
        assert "unsafe_text" in str(exc)
    else:
        raise AssertionError("expected placeholder leak rejection")

    bad = copy.deepcopy(loaded)
    bad["examples"][0]["loss_mask"] = {"repo_code_ce": True, "symbol_binding_ce": True}
    try:
        stage.review_training_pack(bad)
    except stage.Stage12650ReviewError as exc:
        assert "loss_mask_drift" in str(exc)
    else:
        raise AssertionError("expected loss mask drift rejection")


def test_review_rejects_private_path_or_training_gate_drift():
    loaded = stage.load_stage12649()
    bad = copy.deepcopy(loaded)
    bad["examples"][0]["target_text"] += " /arxiv/leak"
    try:
        stage.review_training_pack(bad)
    except stage.Stage12650ReviewError as exc:
        assert "unsafe_text" in str(exc)
    else:
        raise AssertionError("expected private path rejection")

    bad = copy.deepcopy(loaded)
    bad["examples"][0]["training_allowed"] = True
    try:
        stage.review_training_pack(bad)
    except stage.Stage12650ReviewError as exc:
        assert "training_example_gate_drift" in str(exc)
    else:
        raise AssertionError("expected training gate drift rejection")


def test_review_rejects_missing_admitted_or_source_join():
    loaded = stage.load_stage12649()
    bad = copy.deepcopy(loaded)
    bad["examples"][0]["source_row_sha256"] = "0" * 64
    try:
        stage.review_training_pack(bad)
    except stage.Stage12650ReviewError as exc:
        assert "missing_repo_code_source_join" in str(exc)
    else:
        raise AssertionError("expected missing source join rejection")

    bad = copy.deepcopy(loaded)
    bad["admitted"][0]["split"] = "wrong"
    try:
        stage.review_training_pack(bad)
    except stage.Stage12650ReviewError as exc:
        assert "admitted_row_binding_drift" in str(exc)
    else:
        raise AssertionError("expected admitted row binding rejection")


def test_review_rejects_training_text_render_drift():
    loaded = stage.load_stage12649()
    bad = copy.deepcopy(loaded)
    bad["examples"][0]["target_text"] += " changed"
    try:
        stage.review_training_pack(bad)
    except stage.Stage12650ReviewError as exc:
        assert "training_text_render_drift" in str(exc)
    else:
        raise AssertionError("expected training text render drift rejection")
