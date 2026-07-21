import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12526_private_executor_binding_source_audit.py"


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


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_prior_blocked_artifacts(root: Path, count: int = 343) -> None:
    stage12525 = root / "runs/local/artifacts/stage12525_private_executor_readiness_manifest_builder"
    stage12510 = root / "runs/local/artifacts/stage12510_ai_env_private_extraction_executor_readiness_audit"
    write_json(
        stage12525 / "summary.json",
        {
            "record_type": "stage12525_private_executor_readiness_manifest_builder_summary_v1",
            "decision": "blocked_unproven_private_executor_readiness_no_manifests_written",
            "manifest_slot_count_required": count,
            "preserved_slot_identity_count": count,
            "readiness_blocker_codes": [
                "no_authorized_stage12503_return_writer_configured",
                "stage12510_executor_blockers_present",
                "trusted_ai_env_private_extractor_binding_missing",
            ],
            "private_executor_readiness_manifests_written": False,
            "stage12516_candidate_row_count": 0,
            "stage12503_return_records_written": 0,
            "training_rows_emitted": 0,
            "admitted_rows": 0,
            "public_safe_status_only": True,
        },
    )
    write_jsonl(
        stage12525 / "private_executor_readiness_manifest_blockers.jsonl",
        [
            {
                "record_type": "stage12525_private_executor_readiness_manifest_blocker_v1",
                "blocker_codes": [
                    "no_authorized_stage12503_return_writer_configured",
                    "trusted_ai_env_private_extractor_binding_missing",
                ],
                "manifests_written": False,
                "public_safe_status_only": True,
            }
            for _ in range(count)
        ],
    )
    write_json(
        stage12510 / "ai_env_private_extraction_executor_readiness_contract.json",
        {
            "record_type": "stage12510_ai_env_private_extraction_executor_readiness_contract_v1",
            "executor_binding_env": "STAGE12510_AI_ENV_PRIVATE_EXTRACTOR",
            "stage12510_does_not_execute_work_orders": True,
            "stage12510_does_not_write_stage12503_returns": True,
            "public_artifact_policy": "hashes_enums_status_only_no_raw_paths_commands_diffs_source_or_verifier_output",
        },
    )
    write_jsonl(
        stage12510 / "ai_env_private_extraction_executor_blockers.jsonl",
        [
            {
                "record_type": "stage12510_ai_env_private_extraction_executor_blocker_v1",
                "blocker_codes": [
                    "trusted_ai_env_private_extractor_binding_missing",
                    "no_authorized_stage12503_return_writer_configured",
                ],
                "public_safe_status_only": True,
            }
        ],
    )
    write_jsonl(
        stage12510 / "executor_candidate_classifications.jsonl",
        [
            {
                "record_type": "stage12510_executor_candidate_classification_v1",
                "stage_ref": "stage12503_private_semantic_extraction_return_validator",
                "classification": "validator_not_executor",
                "stage12509_compatible_executor": False,
                "public_safe_status_only": True,
            }
        ],
    )


def test_no_candidate_binding_sources_emits_missing_checklist(tmp_path: Path) -> None:
    stage12526 = load_module(SCRIPT, "stage12526")
    write_prior_blocked_artifacts(tmp_path)

    summary = stage12526.build(tmp_path)

    assert summary["decision"] == "blocked_missing_trusted_binding_and_authorized_writer_sources_checklist_emitted"
    assert summary["candidate_binding_source_count"] == 0
    assert summary["missing_binding_checklist_count"] >= 2
    assert summary["preserved_slot_count_context"] == 343
    assert summary["stage12521_readiness_manifests_written"] is False
    assert summary["stage12516_candidate_row_count"] == 0
    assert summary["stage12503_return_records_written"] == 0
    assert summary["training_rows_emitted"] == 0

    out = tmp_path / "runs/local/artifacts/stage12526_private_executor_binding_source_audit"
    assert read_jsonl(out / "candidate_binding_source_worklist.jsonl") == []
    checklist = read_jsonl(out / "missing_binding_checklist.jsonl")
    codes = {row["missing_binding_code"] for row in checklist}
    assert "trusted_ai_env_private_extractor_binding_missing" in codes
    assert "no_authorized_stage12503_return_writer_configured" in codes
    assert not (
        tmp_path
        / "runs/local/artifacts/stage12521_private_causal_evidence_executor_handoff_contract/"
        "private_executor_resolver_readiness_manifest.json"
    ).exists()


def test_temp_root_candidate_source_detection_emits_public_safe_worklist(tmp_path: Path) -> None:
    stage12526 = load_module(SCRIPT, "stage12526_candidates")
    write_prior_blocked_artifacts(tmp_path)
    write_json(
        tmp_path / "configs/stage12526_ai_env_private_executor_binding_manifest.json",
        {
            "record_type": "unit_public_safe_name_only_fixture",
            "public_safe_status_only": True,
        },
    )
    write_json(
        tmp_path / "runs/local/artifacts/unit_authorized_return_writer_config/authorized_return_writer_config.json",
        {
            "record_type": "unit_public_safe_name_only_fixture",
            "public_safe_status_only": True,
        },
    )

    summary = stage12526.build(tmp_path)

    assert summary["decision"] == "candidate_binding_sources_found_public_safe_worklist_no_readiness_fabricated"
    assert summary["candidate_binding_source_count"] == 2
    assert summary["missing_binding_checklist_count"] == 0
    assert summary["stage12521_readiness_manifests_written"] is False
    assert summary["executor_return_records_written"] == 0
    assert summary["admitted_rows"] == 0

    out = tmp_path / "runs/local/artifacts/stage12526_private_executor_binding_source_audit"
    worklist = read_jsonl(out / "candidate_binding_source_worklist.jsonl")
    assert {row["candidate_name"] for row in worklist} == {
        "authorized_return_writer_config.json",
        "stage12526_ai_env_private_executor_binding_manifest.json",
    }
    assert all(row["contents_read"] is False for row in worklist)
    assert all(row["trusted_binding_proven"] is False for row in worklist)
    assert all(row["authorized_return_writer_proven"] is False for row in worklist)
    assert read_jsonl(out / "missing_binding_checklist.jsonl") == []
