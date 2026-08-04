from __future__ import annotations

import copy
import importlib.util
import json
from collections import Counter
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12591_external_source_native_causal_replay_microbatch_preflight.py"
SPEC = importlib.util.spec_from_file_location("stage12591", SCRIPT)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def read_jsonl(name: str):
    path = mod.OUT / name
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def synthetic(bucket: str, repo: str, number: int):
    return {
        "candidate_id": f"candidate_{bucket}_{number}",
        "repo_family": repo,
        "repo_executor_ref": f"executor_repo_{number:024d}",
        "bucket": bucket,
        "source_evidence_ref": f"seed_{number:024d}",
        "lineage": {"same_row_frozen": True},
        "focused_verifier_adapter": "adapter",
        "focused_verifier_ref": f"verifier_{number:064d}",
        "structural_priority": [number, -1, repo],
    }


def test_generated_universe_reports_exact_deficit_without_padding() -> None:
    rows = read_jsonl("static_universe.jsonl")
    assert len(rows) == 19
    assert Counter(row["bucket"] for row in rows) == Counter(
        {"rust_cpp": 4, "python": 7, "js_ts_jvm": 8}
    )
    assert len({row["candidate_id"] for row in rows}) == 19
    assert len({row["repo_family"].casefold() for row in rows}) == 19
    summary = json.loads((mod.OUT / "summary.json").read_text(encoding="utf-8"))
    assert summary["no_padding"] is True
    assert summary["status"] == "UNIVERSE_DEFICIT_NO_REQUEST"
    assert summary["bucket_deficits"] == {"rust_cpp": 4, "python": 1, "js_ts_jvm": 0}
    assert summary["repo_family_count"] >= 12


def test_dirty_checkout_is_excluded_instead_of_used_as_padding() -> None:
    exclusions = read_jsonl("preflight_exclusions.jsonl")
    assert any(row["repo_family"] == "datafusion" and row["reason"] == "checkout_dirty" for row in exclusions)
    assert "datafusion" not in {row["repo_family"] for row in read_jsonl("static_universe.jsonl")}


def test_deficit_emits_no_request_slots() -> None:
    requests = read_jsonl("attempt_requests.jsonl")
    assert requests == []
    summary = json.loads((mod.OUT / "summary.json").read_text(encoding="utf-8"))
    assert summary["request_count"] == 0
    assert summary["request_bucket_counts"] == {}


def test_selector_dedupes_repos_and_fails_without_exact_bucket_slots() -> None:
    rows = []
    number = 0
    for bucket in mod.TARGET_BUCKET_COUNTS:
        for index in range(4):
            number += 1
            rows.append(synthetic(bucket, f"{bucket}_repo_{index}", number))
    rows.append(synthetic("python", "python_repo_0", 99))
    requests = mod.select_requests(rows)
    assert len(requests) == 12
    assert len({row["repo_family"] for row in requests}) == 12
    assert [row["request_slot"] for row in requests] == list(range(1, 13))
    assert Counter(row["bucket"] for row in requests) == Counter(mod.REQUEST_BUCKET_COUNTS)
    assert all(row["required_return_slots"] == list(mod.REQUEST_SLOTS) for row in requests)
    with pytest.raises(mod.GateError, match="exact_request_slots_unavailable"):
        mod.select_requests([row for row in rows if row["bucket"] != "rust_cpp"])


def test_future_denylist_and_stage12547_overlap_rejected(monkeypatch) -> None:
    declaration = mod.DECLARATIONS[0]
    seed = mod.source_rows()[(declaration[1], declaration[2])]
    record, rejection = mod.validate_declaration(declaration, seed, {declaration[1].casefold()})
    assert record is None
    assert rejection["reason"] == "protected_or_stage12547_overlap"


def test_no_outcome_ranking_no_authority_and_no_emitted_causal_rows() -> None:
    public = [
        read_jsonl("static_universe.jsonl"), read_jsonl("attempt_requests.jsonl"),
        json.loads((mod.OUT / "request_contract.json").read_text(encoding="utf-8")),
    ]
    mod.assert_public_schema(public)
    encoded = json.dumps(public, sort_keys=True).casefold()
    for forbidden in ("causal_candidate", "training_row", "projection", "authority", "rank_score"):
        assert forbidden not in encoded
    assert "structural_priority" in encoded
    assert "pre_outcome_evidence_only" in encoded


def test_filesystem_closure_and_stop_contract_are_complete() -> None:
    contract = json.loads((mod.OUT / "request_contract.json").read_text(encoding="utf-8"))
    closure = contract["filesystem_closure"]
    assert set(closure["snapshot_kinds"]) == set(mod.FILESYSTEM_SNAPSHOT_KINDS)
    assert closure["declared_cache_allowlist_required"] is True
    assert contract["maximum_attempts"] == 12
    assert contract["first_six_minimum_proof_complete"] == 3
    assert contract["environment_failure_limit_per_adapter"] == 2
    assert set(contract["stop_codes"]) == set(mod.STOP_CODES)
    assert contract["completion_default"] == "CONTINUE"
    assert contract["training_allowed"] is False


def test_request_semantics_forbid_weak_causal_credit() -> None:
    universe = []
    number = 0
    for bucket in mod.TARGET_BUCKET_COUNTS:
        for index in range(4):
            number += 1
            universe.append(synthetic(bucket, f"{bucket}_repo_{index}", number))
    for row in mod.select_requests(universe):
        assert row["repo_wide_tests_secondary_only"] is True
        assert row["repo_wide_tests_causal_credit"] is False
        assert row["generic_pass_to_pass_forbidden"] is True
        assert row["observed_action_imitation_forbidden"] is True
        assert row["sealed_pre_outcome_actions_required"] is True
        assert row["completion_default"] == "CONTINUE"
        assert row["training_allowed"] is False


def test_pinned_hash_guard_fails_closed(monkeypatch) -> None:
    changed = copy.deepcopy(mod.PINNED_INPUT_SHA256)
    changed["public_lane_worklist"] = "0" * 64
    monkeypatch.setattr(mod, "PINNED_INPUT_SHA256", changed)
    with pytest.raises(mod.GateError, match="pinned_input_hash_mismatch:public_lane_worklist"):
        mod.pin_inputs()


def test_public_schema_rejects_raw_paths_outcomes_and_authority() -> None:
    for unsafe in ({"raw_path": "/private/repo"}, {"observed_outcome": "pass"}, {"training_authority": False}):
        with pytest.raises(mod.GateError):
            mod.assert_public_schema(unsafe)
