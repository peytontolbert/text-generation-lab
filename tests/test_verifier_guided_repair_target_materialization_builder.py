import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from verifier_guided_repair_target_materialization_builder import (
    build_card,
    build_materialization_controls,
    read_jsonl,
)

SOURCE = Path("runs/local/artifacts/stage8788_source_backed_verifier_repair_candidate_manifest/source_backed_verifier_repair_candidate_manifest.jsonl")


def test_verifier_guided_materialization_keeps_targets_out_of_manifest():
    rows = read_jsonl(SOURCE)[:18]
    manifest, target_store = build_materialization_controls(rows)
    assert len(manifest) == 18
    assert len(target_store) == 18
    manifest_text = "\n".join(json.dumps(row, sort_keys=True) for row in manifest)
    for target in target_store:
        assert target["decoder_text"] not in manifest_text
        assert target["target_store_only_not_model_input"] is True
    assert all(row["clean_state"]["denoise_ce_eligible_now"] is False for row in manifest)
    assert all(row["clean_state"]["runtime_verifier_execution_eligible_now"] is False for row in manifest)


def test_verifier_guided_materialization_card_closes_authority_and_losses():
    rows = read_jsonl(SOURCE)[:36]
    manifest, target_store = build_materialization_controls(rows)
    card = build_card(manifest, target_store)
    assert card["rows"] == 36
    assert card["materialized_rows"] == 36
    assert card["target_store_rows"] == 36
    assert card["authority_rows"] == 0
    assert card["target_store_authority_rows"] == 0
    assert card["training_loss_rows"] == 0
    assert card["denoise_ce_eligible_now_rows"] == 0
    assert card["runtime_verifier_execution_eligible_now_rows"] == 0
    assert card["target_text_copied_to_manifest_rows"] == 0
    assert card["target_ref_unique_rows"] == card["target_store_rows"]
    assert card["internal_token_target_store_rows"] == 0
    assert card["html_target_store_rows"] == 0
    assert card["repetition_target_store_rows"] == 0
