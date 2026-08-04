from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12686_deterministic_training_data_semantic_quarantine.py"


def load_module():
    spec = importlib.util.spec_from_file_location("stage12686", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_semantic_quarantine_counts_and_authority(tmp_path: Path) -> None:
    module = load_module()
    summary = module.build(tmp_path / "artifact", tmp_path / "summary.json")

    assert summary["quarantined_unique_rows"] == 136_371
    assert summary["quarantine_counts"] == {
        "stage12656": 200,
        "stage12662": 2_187,
        "stage12680": 120_000,
        "stage12685": 13_984,
    }
    assert summary["review_required_unique_rows"] == 17_508
    assert summary["review_counts"] == {"stage12656": 80, "stage12685": 17_428}
    assert summary["training_eligible_rows"] == 0
    assert all(value is False for value in summary["authority"].values())
    assert summary["source_sha256"] == module.EXPECTED_SOURCE_SHA256
    assert summary["semantic_nonadmission_ledger_contract"] == {
        "semantic_quarantine_ledger.jsonl": {
            "rows": 136_371,
            "sha256": "990aa75ba1bec31412375b398952f522ab4d7975fa31aa37d05d2484ee47772f",
        },
        "semantic_review_candidate_ledger.jsonl": {
            "rows": 17_508,
            "sha256": "90eb65bde505363063ccfc6b379e427943faa80b867a2e802e4259ff196b0fc2",
        },
    }
    assert summary["uniqueness_proof"] == {
        "classified_rows": 153_879,
        "distinct_ledger_ids": 153_879,
        "distinct_source_dataset_row_hashes": 153_879,
    }


def test_precise_link_quarantine_and_review_boundaries(tmp_path: Path) -> None:
    module = load_module()
    module.build(tmp_path / "artifact", tmp_path / "summary.json")
    quarantine = read_jsonl(tmp_path / "artifact/private/semantic_quarantine_ledger.jsonl")
    review = read_jsonl(tmp_path / "artifact/private/semantic_review_candidate_ledger.jsonl")

    precise_quarantine = [row for row in quarantine if row["source_dataset"] == "stage12685"]
    reasons = {}
    for row in precise_quarantine:
        reasons[row["reason"]] = reasons.get(row["reason"], 0) + 1
    assert reasons == {
        "lexical_overlap_is_not_semantic_link": 2_744,
        "model_visible_candidates_indistinguishable": 6,
        "regex_match_is_not_parser_verified_definition": 11_234,
    }
    assert sum(row["split"] == "train" for row in review if row["source_dataset"] == "stage12685") == 13_321
    assert sum(row["split"] == "eval" for row in review if row["source_dataset"] == "stage12685") == 2_817
    assert sum(row["split"] == "strict_eval" for row in review if row["source_dataset"] == "stage12685") == 1_290


def test_private_ledgers_contain_no_model_text_or_targets(tmp_path: Path) -> None:
    module = load_module()
    module.build(tmp_path / "artifact", tmp_path / "summary.json")
    for name in ("semantic_quarantine_ledger.jsonl", "semantic_review_candidate_ledger.jsonl"):
        text = (tmp_path / "artifact/private" / name).read_text(encoding="utf-8")
        assert '"input_state"' not in text
        assert '"model_input"' not in text
        assert '"target"' not in text
        assert '"expected_output"' not in text
        assert '"source_row_ref"' not in text
        assert "PLACEHOLDER" not in text.upper()


def test_source_hash_drift_fails_closed(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    monkeypatch.setitem(module.EXPECTED_SOURCE_SHA256, "stage12656_repo_code", "0" * 64)
    try:
        module.build(tmp_path / "artifact", tmp_path / "summary.json")
    except module.Stage12686Error as exc:
        assert "source_hash_drift" in str(exc)
    else:
        raise AssertionError("same-count source replacement was not rejected")
