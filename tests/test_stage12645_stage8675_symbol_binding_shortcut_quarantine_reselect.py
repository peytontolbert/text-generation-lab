import copy
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12645_stage8675_symbol_binding_shortcut_quarantine_reselect.py"
SPEC = importlib.util.spec_from_file_location("stage12645", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def read_json(path: Path):
    return json.loads(path.read_text())


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def stable(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def assert_false_boundaries(record):
    for field in stage.FALSE_FIELDS:
        assert field in record
        assert record[field] is False


EXPECTED_ARTIFACTS = [
    "contract.json",
    "digest_pointer.json",
    "private/quarantined_source_backed_symbol_binding_rows.jsonl",
    "private/repaired_source_backed_symbol_binding_candidate_manifest.jsonl",
    "private/stage8675_shortcut_quarantine_reselect_packet.json",
    "summary.json",
]


def test_load_inputs_pins_original_stage8674_and_stage8675_blocker():
    inputs = stage.load_inputs()
    stage.validate_inputs(inputs)
    assert len(inputs["rows"]) == 125
    original = stage.recompute_control_audit(inputs["rows"])
    assert original["shortcut_feature_cells"] == 1
    assert original["failures"] == ["shortcut_feature_cells:1"]
    assert original["shortcut"][0]["feature"] == "query_kind"
    assert original["shortcut"][0]["value"] == "test"
    assert original["shortcut"][0]["dist"] == {"BIND_TEST_TO_SYMBOL": 25, "RETRIEVE_MORE": 4}


def test_reselect_keeps_real_balanced_rows_and_quarantines_rest():
    rows = stage.load_inputs()["rows"]
    repaired, quarantined = stage.select_repaired_rows(rows)
    assert len(repaired) == 80
    assert len(quarantined) == 45
    repaired_actions = {}
    for row in repaired:
        repaired_actions[row["clean_state"]["binding_action"]] = repaired_actions.get(row["clean_state"]["binding_action"], 0) + 1
        assert row["route"] == "CANDIDATE_NEEDS_AUDIT"
        assert row["authority"] == stage.AUTHORITY_CLOSED
        assert row["loss_mask"] == stage.LOSS_MASK
    assert repaired_actions == {action: 16 for action in stage.ACTIONS}
    assert set(row["row_id"] for row in repaired).isdisjoint(row["row_id"] for row in quarantined)
    repaired_audit = stage.recompute_control_audit(repaired)
    assert repaired_audit["shortcut_feature_cells"] == 0
    assert repaired_audit["failures"] == []
    assert repaired_audit["actions"] == {action: 16 for action in stage.ACTIONS}
    assert repaired_audit["splits"] == {"eval": 24, "strict_eval": 24, "train": 32}


def test_quarantine_records_are_hash_only_and_no_admission():
    rows = stage.load_inputs()["rows"]
    _, quarantined = stage.select_repaired_rows(rows)
    records = stage.quarantine_records(quarantined)
    assert len(records) == 45
    for record in records:
        assert record["record_type"] == "stage12645_private_quarantined_stage8674_row_v1"
        assert len(record["row_sha256"]) == 64
        assert record["training_allowed"] is False
        assert record["dataset_rows_admitted"] is False
        encoded = json.dumps(record, sort_keys=True)
        assert "/arxiv/" not in encoded
        assert "/data/" not in encoded
        assert "source_row_id" not in encoded


def test_packet_quarantines_successor_but_does_not_admit_or_train():
    summary, contract, private, repaired, quarantine = stage.build_packet(stage.load_inputs())
    assert summary["decision"] == "STAGE8675_SHORTCUT_QUARANTINED_BY_SUCCESSOR_RESELECT_NO_ADMISSION_OR_TRAINING"
    assert summary["original_rows"] == 125
    assert summary["repaired_rows"] == 80
    assert summary["quarantined_rows"] == 45
    assert summary["original_shortcut_feature_cells"] == 1
    assert summary["repaired_shortcut_feature_cells"] == 0
    assert summary["repaired_failures"] == []
    assert summary["repaired_split_counts"] == {"eval": 24, "strict_eval": 24, "train": 32}
    assert summary["stage8675_original_audit_passed"] is False
    assert summary["stage8675_original_shortcut_issue_resolved"] is False
    assert summary["global_shortcut_preflight_passed"] is False
    assert summary["training_allowed"] is False
    assert summary["dataset_rows_admitted"] is False
    assert summary["symbol_binding_training_rows_admitted"] == 0
    assert summary["stage8675_successor_shortcut_issue_quarantined"] is True
    assert contract["private_packet_sha256"] == stable(private)
    assert summary["repaired_manifest_sha256"] == stable(repaired)
    assert summary["quarantine_manifest_sha256"] == stable(quarantine)
    for record in (summary, contract, private):
        assert_false_boundaries(record)


def test_build_writes_stage12645_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == EXPECTED_ARTIFACTS
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")
    assert len(read_jsonl(out / "private/repaired_source_backed_symbol_binding_candidate_manifest.jsonl")) == 80
    assert len(read_jsonl(out / "private/quarantined_source_backed_symbol_binding_rows.jsonl")) == 45


def test_generated_artifacts_match_current_stage12645():
    out = stage.OUT
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == EXPECTED_ARTIFACTS
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/stage8675_shortcut_quarantine_reselect_packet.json")
    repaired = read_jsonl(out / "private/repaired_source_backed_symbol_binding_candidate_manifest.jsonl")
    quarantine = read_jsonl(out / "private/quarantined_source_backed_symbol_binding_rows.jsonl")
    assert summary == external
    assert summary["repaired_rows"] == 80
    assert summary["quarantined_rows"] == 45
    assert summary["training_allowed"] is False
    assert summary["dataset_rows_admitted"] is False
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_packet_sha256"] == stable(private)
    assert pointer["repaired_manifest_sha256"] == stable(repaired)
    assert pointer["quarantine_manifest_sha256"] == stable(quarantine)
    assert stage.recompute_control_audit(repaired)["shortcut_feature_cells"] == 0
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_public_artifacts_have_no_private_paths_or_row_ids():
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
        assert record.get("dataset_rows_admitted") is not True
        assert record.get("global_shortcut_preflight_passed") is not True


def test_repaired_selection_rejects_regressions_that_recreate_shortcuts_or_unbalance_actions():
    rows = stage.load_inputs()["rows"]
    repaired, _ = stage.select_repaired_rows(rows)
    bad = copy.deepcopy(repaired)
    extra_test_rows = [
        row for row in rows
        if row["clean_state"]["binding_action"] == "BIND_TEST_TO_SYMBOL"
        and row["row_id"] not in {selected["row_id"] for selected in repaired}
    ]
    bad.extend(extra_test_rows[:1])
    audit = stage.recompute_control_audit(bad)
    assert audit["shortcut_feature_cells"] == 1
    assert "actions_not_balanced" in audit["failures"]
