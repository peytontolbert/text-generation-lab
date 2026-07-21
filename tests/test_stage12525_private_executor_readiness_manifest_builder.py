import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12525_private_executor_readiness_manifest_builder.py"
STAGE12524_SCRIPT = ROOT / "scripts/build_stage12524_private_executor_invocation_readiness_audit.py"


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


def h(prefix: str, idx: int) -> str:
    return f"{prefix}{idx:023x}"[-24:]


def slot_ref(stage12525, idx: int) -> dict:
    slot = stage12525.FULL_SEVEN_SLOTS[(idx - 1) % len(stage12525.FULL_SEVEN_SLOTS)]
    return {
        "expanded_slot_id_hash": h("e", idx),
        "revalidation_id_hash": h("r", idx),
        "request_id_hash": h("q", idx),
        "work_item_id_hash": h("w", idx),
        "packet_id_hash": h("p", idx),
        "root_or_window_hash": h("o", idx),
        "acquisition_work_order_id_hash": h("a", idx),
        "source_stage": "stage_unit_safe_source",
        "source_kind": "selected_test_bounded_transition_support",
        "language_family": "python",
        "task_family": "transition_next_action",
        "evidence_slot": slot,
        "proof_class": "same_source_causal_lineage",
        "public_safe_status_only": True,
    }


def write_stage12521_stage12523_fixture(root: Path, stage12525, count: int = 343) -> list[dict]:
    refs = [slot_ref(stage12525, idx) for idx in range(1, count + 1)]
    stage12521 = root / "runs/local/artifacts/stage12521_private_causal_evidence_executor_handoff_contract"
    stage12523 = root / "runs/local/artifacts/stage12523_private_executor_return_fixture_contract"
    write_jsonl(
        stage12521 / "private_causal_evidence_executor_handoff_shards.jsonl",
        [
            {
                "record_type": "stage12521_private_causal_evidence_executor_handoff_shard_v1",
                "executor_handoff_shard_id_hash": h("s", 1),
                "priority_rank": 1,
                "language_family": "python",
                "task_family": "transition_next_action",
                "source_stage_name": "stage_unit_safe_source",
                "evidence_slot": "mixed_unit_slots",
                "slot_ref_count": len(refs),
                "slot_refs": refs,
                "public_safe_status_only": True,
            }
        ],
    )
    write_json(
        stage12521 / "summary.json",
        {
            "record_type": "stage12521_private_causal_evidence_executor_handoff_summary_v1",
            "input_expanded_slot_count": count,
            "handoff_shard_count": 1,
            "handoff_slot_ref_count": count,
            "candidate_return_records_written": 0,
            "training_rows_emitted": 0,
            "admitted_rows": 0,
            "public_safe_status_only": True,
        },
    )
    write_jsonl(
        stage12523 / "private_executor_return_fixture_contract_slots.jsonl",
        [
            {
                "record_type": "stage12523_private_executor_return_fixture_contract_slot_v1",
                "fixture_contract_slot_id_hash": h("f", idx),
                **ref,
                "executor_return_filename_contract": "private_causal_evidence_executor_returns.jsonl",
                "public_safe_status_only": True,
            }
            for idx, ref in enumerate(refs, start=1)
        ],
    )
    write_json(
        stage12523 / "private_executor_return_acquisition_runbook.json",
        {
            "record_type": "stage12523_private_executor_return_acquisition_runbook_v1",
            "executor_return_file_must_be_placed_under_stage12521": "private_causal_evidence_executor_returns.jsonl",
            "executor_return_rows_must_match_contract_slots": count,
            "adapter_to_run_after_real_returns": "stage12522_private_causal_evidence_executor_return_adapter",
            "stage12516_candidate_output_ref_after_adapter_only": (
                "runs/local/artifacts/stage12515_private_causal_evidence_acquisition_work_orders/"
                "private_causal_evidence_return_candidates.jsonl"
            ),
            "public_safe_status_only": True,
        },
    )
    write_json(
        stage12523 / "summary.json",
        {
            "record_type": "stage12523_private_executor_return_fixture_contract_summary_v1",
            "fixture_contract_slot_count": count,
            "training_rows_emitted": 0,
            "public_safe_status_only": True,
        },
    )
    return refs


def write_stage12524_blocked_fixture(root: Path, count: int) -> None:
    out = root / "runs/local/artifacts/stage12524_private_executor_invocation_readiness_audit"
    write_json(
        out / "summary.json",
        {
            "record_type": "stage12524_private_executor_invocation_readiness_summary_v1",
            "readiness_blocker_codes": ["private_executor_manifest_missing", "private_resolver_manifest_missing"],
            "readiness_blocker_row_count": count,
            "input_stage12521_slot_ref_count": count,
            "input_stage12523_contract_slot_count": count,
            "executor_return_records_written": 0,
            "stage12516_candidate_row_count": 0,
            "stage12503_return_records_written": 0,
            "training_rows_emitted": 0,
            "admitted_rows": 0,
            "public_safe_status_only": True,
        },
    )
    write_jsonl(
        out / "private_executor_invocation_readiness_blockers.jsonl",
        [
            {
                "record_type": "stage12524_private_executor_invocation_readiness_blocker_v1",
                "blocker_codes": ["private_executor_manifest_missing", "private_resolver_manifest_missing"],
                "public_safe_status_only": True,
            }
            for _ in range(count)
        ],
    )


def write_stage12510_summary(root: Path, *, ready: bool) -> None:
    write_json(
        root / "runs/local/artifacts/stage12510_ai_env_private_extraction_executor_readiness_audit/summary.json",
        {
            "record_type": "stage12510_ai_env_private_extraction_executor_readiness_summary_v1",
            "input_work_order_count": 49,
            "executor_ready_count": 49 if ready else 0,
            "executor_blocker_count": 0 if ready else 49,
            "authorized_executor_binding_count": 1 if ready else 0,
            "blocker_code_counts": {}
            if ready
            else {
                "no_authorized_stage12503_return_writer_configured": 49,
                "trusted_ai_env_private_extractor_binding_missing": 49,
            },
            "stage12503_return_records_written": 0,
            "training_rows_emitted": 0,
            "admitted_rows": 0,
            "public_safe_status_only": True,
        },
    )


def write_stage12513_summary(root: Path) -> None:
    write_json(
        root / "runs/local/artifacts/stage12513_conservative_ai_env_private_semantic_candidate_extractor/summary.json",
        {
            "record_type": "stage12513_conservative_candidate_extractor_summary_v1",
            "candidate_output_written": True,
            "candidate_return_count": 1,
            "blocker_count": 0,
            "stage12503_return_records_written": 0,
            "training_rows_emitted": 0,
            "admitted_rows": 0,
            "public_safe_status_only": True,
        },
    )


def test_missing_unproven_inputs_block_with_no_manifests(tmp_path: Path) -> None:
    stage12525 = load_module(SCRIPT, "stage12525")
    write_stage12521_stage12523_fixture(tmp_path, stage12525)
    write_stage12524_blocked_fixture(tmp_path, 343)
    write_stage12510_summary(tmp_path, ready=False)
    write_stage12513_summary(tmp_path)

    summary = stage12525.build(tmp_path)

    assert summary["decision"] == "blocked_unproven_private_executor_readiness_no_manifests_written"
    assert summary["private_executor_readiness_manifests_written"] is False
    assert summary["readiness_blocker_codes"] == [
        "no_authorized_stage12503_return_writer_configured",
        "stage12510_executor_blockers_present",
        "trusted_ai_env_private_extractor_binding_missing",
    ]
    stage12521 = tmp_path / "runs/local/artifacts/stage12521_private_causal_evidence_executor_handoff_contract"
    assert not (stage12521 / "private_executor_resolver_readiness_manifest.json").exists()
    assert not (stage12521 / "private_executor_runtime_readiness_manifest.json").exists()
    blockers = read_jsonl(
        tmp_path
        / "runs/local/artifacts/stage12525_private_executor_readiness_manifest_builder/private_executor_readiness_manifest_blockers.jsonl"
    )
    assert len(blockers) == 343
    assert blockers[0]["candidate_return_records_written"] == 0
    assert blockers[0]["training_rows_emitted"] == 0
    assert blockers[0]["admitted_rows"] == 0


def test_temp_root_proven_inputs_write_manifests_and_stage12524_becomes_ready(tmp_path: Path) -> None:
    stage12525 = load_module(SCRIPT, "stage12525")
    stage12524 = load_module(STAGE12524_SCRIPT, "stage12524")
    write_stage12521_stage12523_fixture(tmp_path, stage12525)
    write_stage12524_blocked_fixture(tmp_path, 343)
    write_stage12510_summary(tmp_path, ready=True)
    write_stage12513_summary(tmp_path)

    summary = stage12525.build(tmp_path)

    assert summary["decision"] == "ready_public_safe_private_executor_readiness_manifests_written"
    assert summary["readiness_blocker_codes"] == []
    assert summary["private_resolver_manifest_written"] is True
    assert summary["private_executor_manifest_written"] is True
    assert summary["expected_stage12521_return_row_count"] == 343

    stage12521 = tmp_path / "runs/local/artifacts/stage12521_private_causal_evidence_executor_handoff_contract"
    resolver = read_json(stage12521 / "private_executor_resolver_readiness_manifest.json")
    executor = read_json(stage12521 / "private_executor_runtime_readiness_manifest.json")
    assert resolver["record_type"] == "stage12524_private_executor_resolver_readiness_manifest_v1"
    assert resolver["private_resolver_ready"] is True
    assert resolver["private_locator_inputs_available"] is True
    assert resolver["resolver_slot_count"] == 343
    assert executor["record_type"] == "stage12524_private_executor_runtime_readiness_manifest_v1"
    assert executor["private_executor_ready"] is True
    assert executor["supports_stage12516_return_schema"] is True
    assert executor["executor_slot_count"] == 343
    assert executor["expected_executor_return_filename"] == "private_causal_evidence_executor_returns.jsonl"
    assert executor["candidate_return_records_written"] == 0
    assert executor["stage12516_candidate_row_count"] == 0
    assert executor["stage12503_return_records_written"] == 0
    assert executor["training_rows_emitted"] == 0
    assert executor["admitted_rows"] == 0

    stage12524_summary = stage12524.build(tmp_path)
    assert stage12524_summary["executor_invocation_ready"] is True
    assert stage12524_summary["readiness_blocker_codes"] == []
    assert stage12524_summary["expected_stage12521_return_row_count"] == 343
    assert stage12524_summary["executor_return_records_written"] == 0
    assert stage12524_summary["stage12516_candidate_row_count"] == 0
    assert stage12524_summary["stage12503_return_records_written"] == 0
