import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12527_private_binding_review_queue.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_stage12526_fixture(root: Path, rows: list[dict], checklist: list[dict] | None = None) -> None:
    out = root / "runs/local/artifacts/stage12526_private_executor_binding_source_audit"
    write_json(
        out / "summary.json",
        {
            "record_type": "stage12526_private_executor_binding_source_audit_summary_v1",
            "decision": "unit_fixture",
            "candidate_binding_source_count": len(rows),
            "preserved_slot_count_context": 343,
            "stage12525_preserved_slot_identity_count": 343,
            "stage12525_manifest_slot_count_required": 343,
            "prior_blocker_codes": [
                "no_authorized_stage12503_return_writer_configured",
                "trusted_ai_env_private_extractor_binding_missing",
            ],
            "stage12521_readiness_manifests_written": False,
            "stage12516_candidate_row_count": 0,
            "stage12503_return_records_written": 0,
            "training_rows_emitted": 0,
            "admitted_rows": 0,
            "public_safe_status_only": True,
        },
    )
    write_jsonl(out / "candidate_binding_source_worklist.jsonl", rows)
    write_jsonl(out / "missing_binding_checklist.jsonl", checklist or [])


def candidate(candidate_id: str, name: str, parent: str, suffix: str, classification: str) -> dict:
    return {
        "record_type": "stage12526_public_safe_candidate_binding_source_v1",
        "candidate_binding_source_id_hash": candidate_id,
        "candidate_name": name,
        "candidate_parent_name": parent,
        "candidate_suffix": suffix,
        "classification": classification,
        "contents_read": False,
        "trusted_binding_proven": False,
        "authorized_return_writer_proven": False,
        "public_safe_metadata_only": True,
        "stage12521_readiness_manifest_count": 0,
        "stage12516_candidate_row_count": 0,
        "stage12503_return_records_written": 0,
        "training_rows_emitted": 0,
        "admitted_rows": 0,
        "executor_return_records_written": 0,
    }


def test_empty_worklist_emits_missing_private_review_checklist(tmp_path: Path) -> None:
    stage12527 = load_module(SCRIPT, "stage12527_empty")
    write_stage12526_fixture(
        tmp_path,
        [],
        [
            {
                "record_type": "stage12526_missing_binding_checklist_item_v1",
                "missing_binding_code": "trusted_ai_env_private_extractor_binding_missing",
                "public_safe_metadata_only": True,
                "readiness_claimed": False,
            }
        ],
    )

    summary = stage12527.build(tmp_path)

    assert summary["decision"] == "blocked_no_stage12526_candidates_missing_private_review_checklist_emitted"
    assert summary["private_review_queue_count"] == 0
    assert summary["missing_private_review_checklist_count"] >= 1
    assert summary["preserved_slot_count_context"] == 343
    assert summary["stage12521_readiness_manifests_written"] is False
    assert summary["stage12516_candidate_row_count"] == 0
    assert summary["stage12503_return_records_written"] == 0
    assert summary["training_rows_emitted"] == 0

    out = tmp_path / "runs/local/artifacts/stage12527_private_binding_review_queue"
    assert read_jsonl(out / "private_review_queue.jsonl") == []
    missing = read_jsonl(out / "missing_private_review_checklist.jsonl")
    assert {row["missing_binding_code"] for row in missing} >= {"trusted_ai_env_private_extractor_binding_missing"}
    assert not (
        tmp_path
        / "runs/local/artifacts/stage12521_private_causal_evidence_executor_handoff_contract/"
        "private_executor_resolver_readiness_manifest.json"
    ).exists()


def test_temp_worklist_ranks_candidates_and_keeps_readiness_counters_zero(tmp_path: Path) -> None:
    stage12527 = load_module(SCRIPT, "stage12527_rank")
    rows = [
        candidate(
            "cccccccccccccccccccccccc",
            "generic_private_executor_config.json",
            "stage_unit_generic",
            ".json",
            "private_executor_config_candidate_name",
        ),
        candidate(
            "bbbbbbbbbbbbbbbbbbbbbbbb",
            "stage12521_trusted_binding_manifest.json",
            "stage12521_private_causal_evidence_executor_handoff_contract",
            ".json",
            "trusted_binding_candidate_name",
        ),
        candidate(
            "aaaaaaaaaaaaaaaaaaaaaaaa",
            "authorized_return_writer_config.json",
            "stage_unit_authorized_return_writer",
            ".json",
            "authorized_return_writer_candidate_name",
        ),
    ]
    write_stage12526_fixture(tmp_path, rows)

    summary = stage12527.build(tmp_path)

    assert summary["decision"] == "public_safe_private_review_queue_emitted_no_readiness_claimed"
    assert summary["private_review_queue_count"] == 3
    assert summary["missing_private_review_checklist_count"] == 0
    assert summary["candidate_class_counts"] == {
        "authorized_return_writer_candidate_name": 1,
        "private_executor_config_candidate_name": 1,
        "trusted_binding_candidate_name": 1,
    }
    assert summary["stage12521_readiness_manifest_count"] == 0
    assert summary["executor_return_records_written"] == 0
    assert summary["admitted_rows"] == 0

    out = tmp_path / "runs/local/artifacts/stage12527_private_binding_review_queue"
    queue = read_jsonl(out / "private_review_queue.jsonl")
    assert [row["candidate_binding_source_id_hash"] for row in queue] == [
        "aaaaaaaaaaaaaaaaaaaaaaaa",
        "bbbbbbbbbbbbbbbbbbbbbbbb",
        "cccccccccccccccccccccccc",
    ]
    assert all("candidate_name" not in row for row in queue)
    assert all("candidate_ref_hash" not in row for row in queue)
    assert all(row["candidate_contents_read"] is False for row in queue)
    assert all(row["readiness_claimed"] is False for row in queue)
    assert all(row["stage12516_candidate_row_count"] == 0 for row in queue)
    assert all(row["stage12503_return_records_written"] == 0 for row in queue)
    assert all(row["training_rows_emitted"] == 0 for row in queue)

    criteria = read_json(out / "review_criteria.json")
    assert criteria["accept_criteria"]
    assert criteria["reject_criteria"]
