import copy
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12643_repo_code_ce_manifest_preflight_only.py"
SPEC = importlib.util.spec_from_file_location("stage12643", SCRIPT)
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


def true_fields(record):
    return {key for key, value in record.items() if value is True}


ALLOWED_TRUE = {
    "repo_code_ce_candidate_manifest_materialized",
    "stage12643_repo_code_ce_manifest_preflight_performed",
    "repo_code_knowledge_substrate_recovered",
}
EXPECTED_ARTIFACTS = [
    "contract.json",
    "digest_pointer.json",
    "private/repo_code_ce_candidate_manifest.jsonl",
    "private/repo_code_ce_manifest_preflight_packet.json",
    "summary.json",
]


def test_candidate_manifest_rows_are_concrete_schema_complete_and_private():
    inputs = stage.load_inputs()
    candidates = stage.build_candidates(inputs["catalog_rows"], inputs["graph_rows"])
    audit = stage.audit_candidates(candidates)
    assert audit["candidate_rows"] == 200
    assert audit["schema_complete_candidate_rows"] == 200
    assert audit["no_placeholder_candidate_rows"] == 200
    assert audit["no_raw_path_candidate_rows"] == 200
    assert audit["authority_blocked_candidate_rows"] == 200
    assert audit["heldout_preserved"] is True
    assert audit["cross_split_duplicate_opaque_repo_ids"] == 0
    assert audit["shortcut_audit"]["local_manifest_shortcut_screen_passed"] is True
    assert audit["shortcut_audit"]["global_shortcut_preflight_passed"] is False
    assert audit["shortcut_audit"]["target_label_in_id_rows"] == 0
    assert audit["shortcut_audit"]["repo_path_in_model_input_rows"] == 0
    assert audit["shortcut_audit"]["raw_source_included_rows"] == 0
    assert audit["split_counts"] == {"eval": 40, "strict_eval": 39, "train": 121}
    for row in candidates:
        assert set(stage.REQUIRED_ROW_FIELDS).issubset(row)
        assert row["record_type"] == "stage12643_private_repo_code_ce_candidate_manifest_row_v1"
        assert row["objective_family"] == "repo_code_ce_manifest_preflight"
        assert row["admission"]["admitted"] is False
        assert row["admission"]["training_allowed"] is False
        assert row["admission"]["local_manifest_shortcut_screen_passed"] is True
        assert row["admission"]["global_shortcut_preflight_passed"] is False
        assert "shortcut_preflight_passed" not in row["admission"]
        assert row["authority"] == stage.NO_AUTHORITY
        assert row["loss_mask"] == stage.NO_LOSS
        encoded = json.dumps(row, sort_keys=True)
        assert "/arxiv/" not in encoded
        assert "/data/" not in encoded
        assert "Answer:" not in encoded
        assert "PLACEHOLDER" not in encoded
        assert row["target"]["compact_maintenance_text"].startswith("repo_code_knowledge languages=")


def test_packet_blocks_training_and_preserves_heldout_splits():
    summary, contract, private, candidates = stage.build_packet(stage.load_inputs())
    assert len(candidates) == 200
    assert summary["decision"] == "REPO_CODE_CE_CANDIDATE_MANIFEST_BUILT_NOT_ADMITTED_NO_TRAINING"
    assert summary["repo_code_ce_candidate_manifest_materialized"] is True
    assert summary["repo_code_ce_manifest_materialized"] is False
    assert summary["repo_code_knowledge_stage_complete"] is False
    assert summary["training_allowed"] is False
    assert summary["dataset_rows_admitted"] is False
    assert summary["model_ready_training_rows"] == 0
    assert summary["repo_code_ce_training_rows_admitted"] == 0
    assert summary["heldout_preserved"] is True
    assert contract["shortcut_audit"]["local_manifest_shortcut_screen_passed"] is True
    assert contract["shortcut_audit"]["global_shortcut_preflight_passed"] is False
    assert contract["shortcut_audit"]["target_label_in_id_rows"] == 0
    assert contract["shortcut_audit"]["repo_path_in_model_input_rows"] == 0
    assert contract["shortcut_audit"]["raw_source_included_rows"] == 0
    assert summary["split_counts"] == {"eval": 40, "strict_eval": 39, "train": 121}
    assert summary["stage8675_shortcut_issue_resolved"] is False
    assert summary["stage8675_shortcut_issue_quarantined"] is False
    assert true_fields(summary) == ALLOWED_TRUE | {"heldout_preserved", "independent_review_required_next"}
    assert true_fields(contract) == ALLOWED_TRUE | {"heldout_preserved"}
    assert true_fields(private) == ALLOWED_TRUE
    for record in (summary, contract, private):
        assert_false_boundaries(record)


def test_build_writes_preflight_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == EXPECTED_ARTIFACTS
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")
    candidates = read_jsonl(out / "private/repo_code_ce_candidate_manifest.jsonl")
    assert len(candidates) == summary["candidate_rows"]
    assert stable(candidates) == summary["candidate_manifest_sha256"]


def test_generated_artifacts_match_current_preflight():
    out = stage.OUT
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == EXPECTED_ARTIFACTS
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/repo_code_ce_manifest_preflight_packet.json")
    candidates = read_jsonl(out / "private/repo_code_ce_candidate_manifest.jsonl")
    assert summary == external
    assert summary["training_allowed"] is False
    assert summary["dataset_rows_admitted"] is False
    assert summary["repo_code_ce_manifest_materialized"] is False
    assert summary["repo_code_ce_candidate_manifest_materialized"] is True
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_packet_sha256"] == stable(private)
    assert pointer["candidate_manifest_sha256"] == stable(candidates)
    assert summary["candidate_manifest_sha256"] == stable(candidates)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_public_artifacts_have_no_private_paths_row_ids_or_training_authority():
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
        assert record.get("repo_code_ce_manifest_materialized") is not True


def test_shortcut_audit_rejects_path_source_and_label_leakage():
    inputs = stage.load_inputs()
    catalog_rows = copy.deepcopy(inputs["catalog_rows"])
    graph_rows = copy.deepcopy(inputs["graph_rows"])
    catalog_rows[0]["model_input"]["repo_path"] = "/arxiv/repositories/leaky"
    try:
        stage.build_candidates(catalog_rows, graph_rows)
    except stage.RepoCodeCeManifestPreflightError as exc:
        assert "row_leak_or_placeholder:/arxiv/" in str(exc)
    else:
        raise AssertionError("expected raw path leakage rejection")

    catalog_rows = copy.deepcopy(inputs["catalog_rows"])
    catalog_rows[0]["anti_cheat"]["target_label_in_id"] = True
    try:
        stage.build_candidates(catalog_rows, graph_rows)
    except stage.RepoCodeCeManifestPreflightError as exc:
        assert "catalog_target_label_in_id" in str(exc)
    else:
        raise AssertionError("expected target-label leakage rejection")


def test_shortcut_audit_counts_candidate_content_leakage():
    inputs = stage.load_inputs()
    candidates = stage.build_candidates(inputs["catalog_rows"], inputs["graph_rows"])
    leaking = copy.deepcopy(candidates)
    leaking[0]["row_id"] += "_" + leaking[0]["target"]["curriculum_uses"][0]
    leaking[1]["input"]["repo_path"] = "/arxiv/repositories/leaky"
    audit = stage.audit_candidates(leaking)
    assert audit["shortcut_audit"]["target_label_in_id_rows"] == 1
    assert audit["shortcut_audit"]["repo_path_in_model_input_rows"] == 1
    assert audit["shortcut_audit"]["raw_source_included_rows"] == 1
    assert audit["shortcut_audit"]["local_manifest_shortcut_screen_passed"] is False


def test_heldout_and_graph_alignment_are_required():
    inputs = stage.load_inputs()
    catalog_rows = copy.deepcopy(inputs["catalog_rows"])
    graph_rows = copy.deepcopy(inputs["graph_rows"])
    graph_rows[0]["split"] = "train" if catalog_rows[0]["split"] != "train" else "eval"
    try:
        stage.build_candidates(catalog_rows, graph_rows)
    except stage.RepoCodeCeManifestPreflightError as exc:
        assert "split_mismatch" in str(exc)
    else:
        raise AssertionError("expected split mismatch rejection")

    catalog_rows = copy.deepcopy(inputs["catalog_rows"])
    graph_rows = copy.deepcopy(inputs["graph_rows"])
    for row in catalog_rows:
        row["split"] = "train"
    for row in graph_rows:
        row["split"] = "train"
    candidates = stage.build_candidates(catalog_rows, graph_rows)
    audit = stage.audit_candidates(candidates)
    assert audit["heldout_preserved"] is False

    inputs = stage.load_inputs()
    catalog_rows = copy.deepcopy(inputs["catalog_rows"])
    graph_rows = copy.deepcopy(inputs["graph_rows"])
    split_a = catalog_rows[0]["split"]
    other_index = next(i for i, row in enumerate(catalog_rows) if row["split"] != split_a)
    duplicate_repo = catalog_rows[0]["model_input"]["opaque_repo_id"]
    catalog_rows[other_index]["model_input"]["opaque_repo_id"] = duplicate_repo
    for node in graph_rows[other_index]["graph_input"]["nodes"]:
        if node["node_type"] == "repo":
            node["features"]["opaque_repo_id"] = duplicate_repo
            break
    modified = copy.deepcopy(inputs)
    modified["catalog_rows"] = catalog_rows
    modified["graph_rows"] = graph_rows
    try:
        stage.build_packet(modified)
    except stage.RepoCodeCeManifestPreflightError as exc:
        assert "heldout_not_preserved" in str(exc) or "heldout_repo_overlap" in str(exc)
    else:
        raise AssertionError("expected cross-split opaque repo overlap rejection")
