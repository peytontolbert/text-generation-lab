from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from golden_locked_eval_suite import builder_exclusion_decision, load_locked_source_ids_from_exclusions, validate_pack, validate_suite


def good_pack() -> dict:
    return {
        "task_pack_id": "locked_x",
        "source_id": "src_x",
        "lineage_hash": "abc",
        "split_role": "locked_regression",
        "train_eligible": False,
        "promotion_only": True,
        "slice_tags": ["swe_bench"],
        "thresholds": {"no_regression_required": True},
        "blocked_training_reason": "locked_eval_source_never_mined_into_training",
    }


def test_validate_pack_accepts_locked_regression_pack() -> None:
    record = validate_pack(good_pack())
    assert record["passed"] is True


def test_validate_pack_rejects_train_eligible_pack() -> None:
    pack = good_pack()
    pack["train_eligible"] = True
    record = validate_pack(pack)
    assert "train_eligible_not_false" in record["failures"]


def test_validate_pack_requires_thresholds_and_source() -> None:
    pack = good_pack()
    pack.pop("thresholds")
    pack.pop("source_id")
    record = validate_pack(pack)
    assert "missing_thresholds" in record["failures"]
    assert "missing_source_id" in record["failures"]


def test_validate_suite_emits_locked_source_ids() -> None:
    card = validate_suite([good_pack()])
    assert card["passed"] is True
    assert card["locked_source_ids"] == ["src_x"]


def test_builder_exclusion_blocks_locked_sources() -> None:
    decision = builder_exclusion_decision({"row_id": "r", "source_id": "src_x"}, {"src_x"})
    assert decision["blocked_from_training"] is True


def test_builder_exclusion_allows_non_locked_source() -> None:
    decision = builder_exclusion_decision({"row_id": "r", "source_id": "src_y"}, {"src_x"})
    assert decision["blocked_from_training"] is False



def test_builder_exclusion_blocks_nested_source_lineage() -> None:
    row = {
        "row_id": "nested",
        "source_lineage": {
            "graph_nodes_source_id": "src_locked",
            "graph_spans_source_id": "src_open",
        },
    }
    decision = builder_exclusion_decision(row, {"src_locked"})
    assert decision["blocked_from_training"] is True
    assert decision["matched_locked_source_ids"] == ["src_locked"]


def test_load_locked_source_ids_from_exclusions(tmp_path: Path) -> None:
    path = tmp_path / "exclusions.jsonl"
    path.write_text(
        '{"source_id":"locked_a","blocked_from_training":true}\n'
        '{"source_id":"open_b","blocked_from_training":false}\n',
        encoding="utf-8",
    )
    assert load_locked_source_ids_from_exclusions(path) == {"locked_a"}
