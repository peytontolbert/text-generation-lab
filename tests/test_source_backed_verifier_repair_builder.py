from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from source_backed_verifier_repair_builder import build_card, build_source_backed_rows, read_jsonl
NEUTRAL = ROOT / "runs/local/artifacts/stage8643_verifier_repair_neutral_manifest/verifier_repair_neutral_manifest.jsonl"
LINEAGE = ROOT / "configs/software_maintainer/source_inventory_lineage_registry_stage8663.json"


def test_source_backed_verifier_repair_rows_are_candidate_only() -> None:
    rows = build_source_backed_rows(read_jsonl(NEUTRAL)[:18], LINEAGE)
    assert rows
    assert {row["objective_family"] for row in rows} == {"source_backed_verifier_repair"}
    assert all(row["route"] == "CANDIDATE_NEEDS_AUDIT" for row in rows)
    assert all(not any(row["loss_mask"].values()) for row in rows)
    assert all(not any(row["authority"].values()) for row in rows)
    assert all(row["query"]["query_node_id_is_opaque"] is True for row in rows)
    assert all(row["anti_cheat"]["raw_log_body_in_model_input"] is False for row in rows)


def test_source_backed_verifier_repair_card_tracks_gate_status() -> None:
    rows = build_source_backed_rows(read_jsonl(NEUTRAL)[:27], LINEAGE)
    card = build_card(rows)
    assert card["rows"] == 27
    assert card["authority_rows"] == 0
    assert card["training_loss_rows"] == 0
    assert card["gate_status"]["complete_gate_status_rows"] == 27
