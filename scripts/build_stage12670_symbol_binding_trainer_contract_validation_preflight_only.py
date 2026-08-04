#!/usr/bin/env python3
# Bind heldout identities for the reviewed symbol-binding lane and validate the current trainer contract without execution.
from __future__ import annotations

import argparse
import collections
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12670_symbol_binding_trainer_contract_validation_preflight_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

S12669_SUMMARY = ROOT / "runs/summaries/stage12669_split_schedule_independent_review_only.json"
S12669_AUDIT = ROOT / "runs/local/artifacts/stage12669_split_schedule_independent_review_only/split_schedule_review_audit.json"
S12668_SYMBOL = ROOT / "runs/local/artifacts/stage12668_combined_curriculum_loss_and_schedule_binding_preflight_only/private/symbol_binding_probe_candidate_manifest.jsonl"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"

EXPECTED_HASHES = {
    "stage12669_summary": "517ecddf07be01f5d95279d28ea63dfbe67ccca756bf48b39c2aa4561408f0ba",
    "stage12669_audit": "aa297d385b65f290445b8f082a0a9d854a96bdfdd4f2d5061b7b22a1c96fe940",
    "symbol_lane": "e2fdcb7354e9a6ba259eed5ab3c4e9256718db21c109808e25b4ee655a4d36f5",
}

FALSE_FIELDS = (
    "implementation_ready", "stage12671_allowed", "training_allowed", "training_run_allowed",
    "training_admitted", "gpu_allocation_requested", "cuda2_training_allowed", "vm_runner_execution_allowed",
    "runtime_authorized", "replay_trustworthy", "level_3_materialized", "model_execution_authorized_next",
    "optimizer_step_authorized", "source_emission_authorized", "body_emission_authorized",
    "sealed_eval_admitted", "sealed_eval_eligible", "strict_eval_admitted",
)
UPSTREAM_FALSE_FIELDS = tuple(field for field in FALSE_FIELDS if field != "stage12671_allowed") + ("stage12670_allowed",)

PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "input_text", "target_text", "query_text", "model_input", "root_id", "state_id",
    "episode_id", "source_lineage", "source_row_id", "jsonl", "placeholder", "PLACEHOLDER", "TODO", "TBD",
)
PRIVATE_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "\x00", "Answer: placeholder", "PLACEHOLDER", "placeholder", "TODO", "TBD",
    "input_text", "target_text", "query_text", "model_input", "source_lineage", "source_row_id",
    "root_candidate_id", "training_candidate_id",
)

EXPECTED_SPLITS = {"eval": 19, "strict_eval": 16, "train": 23}
EXPECTED_ACTIONS = {
    "ABSTAIN_UNBOUND": 13,
    "BIND_CALL_TO_SYMBOL": 16,
    "BIND_IMPORT_TO_MODULE": 13,
    "BIND_TEST_TO_SYMBOL": 9,
    "RETRIEVE_MORE": 7,
}


class Stage12670ValidationError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12670ValidationError("json_object_required:" + path.name)
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise Stage12670ValidationError(f"row_object_required:{line_number}")
            rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n"
    with path.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def fsync_dir(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def false_fields() -> dict[str, bool]:
    return {field: False for field in FALSE_FIELDS}


def check_false(record: Mapping[str, Any], label: str, fields: tuple[str, ...]) -> None:
    for field in fields:
        if record.get(field) is not False:
            raise Stage12670ValidationError(f"{label}_gate_drift:{field}")


def assert_no_forbidden(value: Any, label: str, needles: tuple[str, ...]) -> None:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True) if not isinstance(value, str) else value
    for needle in needles:
        if needle in encoded:
            raise Stage12670ValidationError(f"{label}_leak:{needle}")


def count(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(collections.Counter(str(row.get(key)) for row in rows).items()))


def enabled_loss(row: Mapping[str, Any]) -> str:
    enabled = [str(key) for key, value in (row.get("loss_mask") or {}).items() if bool(value)]
    if len(enabled) != 1:
        raise Stage12670ValidationError("expected_exactly_one_enabled_loss")
    return enabled[0]


def load_inputs() -> dict[str, Any]:
    for label, path in (
        ("stage12669_summary", S12669_SUMMARY),
        ("stage12669_audit", S12669_AUDIT),
        ("symbol_lane", S12668_SYMBOL),
    ):
        if sha256_bytes(path.read_bytes()) != EXPECTED_HASHES[label]:
            raise Stage12670ValidationError("pin_drift:" + label)
    summary = read_json(S12669_SUMMARY)
    audit = read_json(S12669_AUDIT)
    check_false(summary, "stage12669_summary", UPSTREAM_FALSE_FIELDS)
    check_false(audit, "stage12669_audit", UPSTREAM_FALSE_FIELDS)
    if summary.get("next_required_action") != STAGE:
        raise Stage12670ValidationError("stage12669_next_action_drift")
    return {"summary": summary, "audit": audit, "symbol_rows": read_jsonl(S12668_SYMBOL)}


def identity_bound_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    assert_no_forbidden(rows, "source_symbol_rows", PRIVATE_FORBIDDEN_SUBSTRINGS)
    if len(rows) != 58 or count(rows, "split") != EXPECTED_SPLITS:
        raise Stage12670ValidationError("symbol_lane_count_drift")
    out = []
    for row in rows:
        if enabled_loss(row) != "symbol_binding_ce":
            raise Stage12670ValidationError("symbol_loss_drift")
        target = row.get("target") if isinstance(row.get("target"), dict) else {}
        action = str(target.get("binding_action") or "")
        if not action:
            raise Stage12670ValidationError("binding_action_missing")
        provenance = row.get("source_provenance") if isinstance(row.get("source_provenance"), dict) else {}
        source_record = str(provenance.get("source_record_sha256") or "")
        if not source_record:
            raise Stage12670ValidationError("source_record_hash_missing")
        item = json.loads(json.dumps(row, sort_keys=True, ensure_ascii=True))
        item["repo_family"] = "source_backed_symbol_binding_knowledge"
        item["root_identity"] = "symbol_binding_" + hashlib.sha256(source_record.encode("ascii")).hexdigest()[:24]
        item["contract_validation_identity_bound"] = True
        out.append(item)
    if count(out, "target") == {}:
        raise Stage12670ValidationError("unexpected_empty_target_count")
    if dict(collections.Counter(str((row.get("target") or {}).get("binding_action") or "") for row in out)) != EXPECTED_ACTIONS:
        raise Stage12670ValidationError("binding_action_vocab_drift")
    assert_no_forbidden(out, "identity_bound_symbol_rows", PRIVATE_FORBIDDEN_SUBSTRINGS)
    return out


def trainer_module():
    if str(ROOT / "scripts") not in sys.path:
        sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("stage12670_trainer_contract", TRAINER)
    if spec is None or spec.loader is None:
        raise Stage12670ValidationError("trainer_import_failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validation_args(manifest: Path, output_dir: Path) -> argparse.Namespace:
    resolved_output = output_dir.resolve()
    root_text = str(ROOT.resolve())
    validation_repo_root = ROOT if str(resolved_output).startswith(root_text + "/") else resolved_output.parent
    return argparse.Namespace(
        repo_root=validation_repo_root,
        output_dir=output_dir,
        manifest=manifest,
        mode="symbol_binding_probe",
        max_train_rows=64,
        max_eval_rows=64,
        max_strict_rows=64,
        max_steps=0,
        max_decoder_tokens=64,
        eos_loss_weight=1.0,
        phase2_max_train_rows=0,
        phase2_max_eval_rows=0,
        phase2_max_strict_rows=0,
        phase2_max_steps=0,
        phase2_max_decoder_tokens=0,
        phase3_max_train_rows=0,
        phase3_max_eval_rows=0,
        phase3_max_strict_rows=0,
        phase3_max_steps=0,
        phase3_max_decoder_tokens=0,
        decoder_ce_weight=0.0,
        structured_aux_weight=1.0,
        denoise_weight=0.0,
        bounded_choice_aux_weight=0.0,
        bounded_choice_root_group_aux_weight=0.0,
        bounded_choice_contrast_weight=0.0,
        bounded_choice_contrast_margin=0.05,
        bounded_choice_verifier_value_listwise_weight=0.0,
        bounded_choice_same_role_listwise_weight=0.0,
        bounded_choice_aux_source="decoder_first_step",
        bounded_decoder_train_sampler="cyclic",
        bounded_choice_train_head_only=False,
        require_loss_mask_enforcement_audit=True,
        require_native_feature_ablation_audit=False,
        require_counterfactual_obligation_audit=False,
        no_final_checkpoint_export=True,
        cleanup_checkpoints_after_probe=False,
        skip_final_model_save=1,
        restore_best_structured_state=False,
        eval_interval=0,
        contract_only=False,
        implementation="transformer",
        probe_scale="tiny_transformer",
        model_config=None,
        tokenizer_json=None,
        tokenizer_config=None,
        tokenizer_hashlock=None,
        enable_generation_audit=False,
        max_generation_rows=0,
        max_generation_tokens=0,
        generation_prefix_field=None,
        generation_audit_splits="eval,strict_eval",
        generation_repetition_guard=False,
        generation_repetition_guard_top_k=16,
        runtime_model_save_dir=None,
        allow_runtime_model_save_for_harness=False,
        initialize_from_runtime_model=None,
        preservation_reference_runtime_model=None,
        preservation_kl_weight=0.0,
        preservation_exempt_flag="preservation_exempt",
        phase2_manifest=None,
        phase3_manifest=None,
        phase2_learning_rate=None,
        structured_trainable_profile="full_non_decoder",
        phase2_structured_trainable_profile=None,
    )


def sanitize_contract_card(card: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "passed": bool(card.get("passed")),
        "errors": list(card.get("errors") or []),
        "mode": str(card.get("mode") or ""),
        "rows": int(card.get("rows") or 0),
        "split_counts": dict(card.get("split_counts") or {}),
        "loss_counts": {key: value for key, value in dict(card.get("loss_counts") or {}).items() if value},
        "authority_rows": int(card.get("authority_rows") or 0),
        "unsafe_loss_rows": int(card.get("unsafe_loss_rows") or 0),
        "implementation": str(card.get("implementation") or ""),
        "probe_scale": str(card.get("probe_scale") or ""),
        "model_execution_attempted": bool(card.get("model_execution_attempted")),
        "final_checkpoint_export_disabled": bool(card.get("final_checkpoint_export_disabled")),
        "final_model_save_skipped": bool(card.get("final_model_save_skipped")),
        "training_execution_authorized": False,
    }


def validate_identity_bound_manifest(manifest: Path, output_dir: Path) -> dict[str, Any]:
    module = trainer_module()
    rows = module.load_manifest(manifest)
    card = module.validate_contract(validation_args(manifest, output_dir), rows)
    sanitized = sanitize_contract_card(card)
    if not sanitized["passed"]:
        raise Stage12670ValidationError("trainer_contract_validation_failed")
    if sanitized["model_execution_attempted"]:
        raise Stage12670ValidationError("model_execution_attempted")
    assert_no_forbidden(sanitized, "sanitized_contract_card", PUBLIC_FORBIDDEN_SUBSTRINGS)
    return sanitized


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    inputs = load_inputs()
    rows = identity_bound_rows(inputs["symbol_rows"])
    manifest = out / "private/identity_bound_symbol_binding_probe_candidate_manifest.jsonl"
    write_jsonl(manifest, rows)
    contract_card = validate_identity_bound_manifest(manifest, out / "private/trainer_contract_validation_output")
    action_counts = dict(sorted(collections.Counter(str((row.get("target") or {}).get("binding_action") or "") for row in rows).items()))
    audit = {
        "record_type": "stage12670_symbol_binding_contract_validation_audit_v1",
        "stage": STAGE,
        "validation_decision": "PASS_SYMBOL_BINDING_TRAINER_CONTRACT_VALIDATION_NO_EXECUTION",
        "identity_bound_rows": len(rows),
        "split_counts": count(rows, "split"),
        "binding_action_counts": action_counts,
        "trainer_contract_card": contract_card,
        "identity_binding_materialized": True,
        "symbol_binding_lane_contract_validated": True,
        "training_execution_authorized": False,
        "next_required_action": "stage12671_symbol_binding_lane_independent_review_only",
        **false_fields(),
    }
    checks = [
        {"check_id": "stage12669_pins", "status": "pass"},
        {"check_id": "heldout_identity_binding", "status": "pass"},
        {"check_id": "trainer_contract_validation", "status": "pass"},
        {"check_id": "model_execution", "status": "blocked", "detail": "no execution authorization requested"},
        {"check_id": "training_authority", "status": "blocked", "detail": "separate training admission remains required"},
    ]
    summary = {
        "record_type": "stage12670_public_symbol_binding_contract_validation_summary_v1",
        "stage": STAGE,
        "decision": audit["validation_decision"],
        "identity_bound_rows": len(rows),
        "split_counts": audit["split_counts"],
        "binding_action_counts": action_counts,
        "trainer_contract_validation_passed": True,
        "symbol_binding_lane_contract_validated": True,
        "dataset_rows_admitted": True,
        "combined_dataset_rows_admitted": True,
        "next_required_action": audit["next_required_action"],
        **false_fields(),
    }
    private = {
        "record_type": "stage12670_private_symbol_binding_contract_validation_packet_v1",
        "stage": STAGE,
        "stage12669_summary_sha256": EXPECTED_HASHES["stage12669_summary"],
        "stage12669_audit_sha256": EXPECTED_HASHES["stage12669_audit"],
        "source_symbol_lane_sha256": EXPECTED_HASHES["symbol_lane"],
        "identity_bound_manifest_sha256": sha256_bytes(manifest.read_bytes()),
        "audit_sha256": stable_hash(audit),
        "checks_sha256": stable_hash(checks),
        **false_fields(),
    }
    contract = {
        "record_type": "stage12670_symbol_binding_contract_validation_contract_v1",
        "stage": STAGE,
        "decision": summary["decision"],
        "upstream_stage": "stage12669_split_schedule_independent_review_only",
        "recommended_next_stage": summary["next_required_action"],
        "identity_bound_manifest_sha256": private["identity_bound_manifest_sha256"],
        "private_packet_sha256": stable_hash(private),
        "audit_sha256": stable_hash(audit),
        **false_fields(),
    }
    pointer = {
        "record_type": "stage12670_digest_pointer_v1",
        "stage": STAGE,
        "summary_sha256": stable_hash(summary),
        "contract_sha256": stable_hash(contract),
        "private_packet_sha256": stable_hash(private),
        "audit_sha256": stable_hash(audit),
        **false_fields(),
    }
    for label, record in (("summary", summary), ("audit", audit), ("contract", contract), ("pointer", pointer), ("private", private)):
        assert_no_forbidden(record, label, PUBLIC_FORBIDDEN_SUBSTRINGS)
    assert_no_forbidden(rows, "identity_bound_manifest", PRIVATE_FORBIDDEN_SUBSTRINGS)
    write_json(out / "summary.json", summary)
    write_json(out / "symbol_binding_contract_validation_audit.json", audit)
    write_jsonl(out / "private/symbol_binding_contract_validation_checks.jsonl", checks)
    write_json(out / "private/symbol_binding_contract_validation_packet.json", private)
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(summary_path, summary)
    fsync_dir(out)
    fsync_dir(summary_path.parent)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True, ensure_ascii=True))
