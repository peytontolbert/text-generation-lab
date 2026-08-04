#!/usr/bin/env python3
# Materialize canonical adapter-candidate rows for the combined curriculum without authorizing trainer execution.
from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12667_combined_curriculum_trainer_contract_adapter_preflight_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

S12666_SUMMARY = ROOT / "runs/summaries/stage12666_combined_curriculum_training_authorization_preflight_only.json"
S12666_AUDIT = ROOT / "runs/local/artifacts/stage12666_combined_curriculum_training_authorization_preflight_only/authorization_audit.json"
S12664_COMBINED = ROOT / "runs/local/artifacts/stage12664_repo_code_and_structured_state_pack_composition_preflight_only/private/combined_curriculum_trainer_manifest.jsonl"
S12656_EXAMPLES = ROOT / "runs/local/artifacts/stage12656_repo_code_symbol_binding_shortcut_resilience_preflight_only/private/shortcut_resilient_repo_code_training_examples.jsonl"

EXPECTED_HASHES = {
    "stage12666_summary": "5e56f7cb0f65264764417a11e198a43fce2d6c24c31393a457f8c4fd46fcc134",
    "stage12666_audit": "73c7b0848befbe4f50c19fbb50966362b44639e55174c8ea9e436057d5641ddb",
    "stage12664_combined": "52298e8c5c94e64377b8e251217e2116fcb6d92bcfa6fa21f980c8d17d5f7323",
    "stage12656_examples": "aa869c73128a7c64868483dd5e3bdb70ab00286f33c4a30d694c4dc4cbc1f872",
}

FALSE_FIELDS = (
    "implementation_ready", "stage12668_allowed", "training_allowed", "training_run_allowed",
    "training_admitted", "gpu_allocation_requested", "cuda2_training_allowed", "vm_runner_execution_allowed",
    "runtime_authorized", "replay_trustworthy", "level_3_materialized", "model_execution_authorized_next",
    "optimizer_step_authorized", "source_emission_authorized", "body_emission_authorized",
    "sealed_eval_admitted", "sealed_eval_eligible", "strict_eval_admitted",
)
UPSTREAM_FALSE_FIELDS = tuple(field for field in FALSE_FIELDS if field not in {"stage12668_allowed"}) + ("stage12667_allowed",)

PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "input_text", "target_text", "query_text", "model_input", "root_id", "state_id",
    "episode_id", "source_lineage", "source_row_id", "jsonl", "placeholder", "PLACEHOLDER", "TODO", "TBD",
)
PRIVATE_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "\x00", "Answer: placeholder", "PLACEHOLDER", "placeholder", "TODO", "TBD",
    "input_text", "target_text", "query_text", "model_input", "source_lineage", "source_row_id",
    "root_candidate_id", "training_candidate_id",
)

EXPECTED_SPLITS = {"eval": 374, "strict_eval": 370, "train": 1701}
EXPECTED_LAYERS = {"repo_code_knowledge": 258, "structured_repo_state": 2187}
EXPECTED_OBJECTIVES = {
    "repo_code_capability_ce": 200,
    "source_backed_symbol_binding_ce": 58,
    "structured_repo_state.evidence_role": 729,
    "structured_repo_state.evidence_route": 729,
    "structured_repo_state.hypothesis_status": 729,
}
SUPPORTED_LOSS_KEYS = {
    "surface_role_ce", "repair_surface_ce", "build_mode_ce", "allowed_import_policy_ce",
    "blocked_import_policy_ce", "repo_dependency_policy_ce", "action_sequence_ce",
    "file_plan_ce", "symbol_binding_ce", "edit_localization_ce", "patch_operator_ce",
    "verifier_repair_ce", "suffix_choice_ce", "episode_repair_outcome_ce",
    "episode_failure_type_ce", "episode_boundary_match_ce", "episode_target_prefix_match_ce",
    "episode_step_value_mse", "decoder_ce", "denoise_ce", "runtime_reward",
}
CANONICAL_REQUIRED_FIELDS = {
    "row_id", "split", "language_family", "input_state", "target", "loss_mask",
    "authority", "source_provenance", "anti_cheat_contract",
}


class Stage12667AdapterError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12667AdapterError("json_object_required:" + path.name)
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise Stage12667AdapterError(f"row_object_required:{line_number}")
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
            raise Stage12667AdapterError(f"{label}_gate_drift:{field}")


def assert_no_forbidden(value: Any, label: str, needles: tuple[str, ...]) -> None:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True) if not isinstance(value, str) else value
    for needle in needles:
        if needle in encoded:
            raise Stage12667AdapterError(f"{label}_leak:{needle}")


def count(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(collections.Counter(str(row.get(key)) for row in rows).items()))


def load_inputs() -> dict[str, Any]:
    for label, path in (
        ("stage12666_summary", S12666_SUMMARY),
        ("stage12666_audit", S12666_AUDIT),
        ("stage12664_combined", S12664_COMBINED),
        ("stage12656_examples", S12656_EXAMPLES),
    ):
        if sha256_bytes(path.read_bytes()) != EXPECTED_HASHES[label]:
            raise Stage12667AdapterError("pin_drift:" + label)
    summary = read_json(S12666_SUMMARY)
    audit = read_json(S12666_AUDIT)
    check_false(summary, "stage12666_summary", UPSTREAM_FALSE_FIELDS)
    check_false(audit, "stage12666_audit", UPSTREAM_FALSE_FIELDS)
    if summary.get("next_required_action") != STAGE:
        raise Stage12667AdapterError("stage12666_next_action_drift")
    return {"summary": summary, "audit": audit, "combined": read_jsonl(S12664_COMBINED), "examples": read_jsonl(S12656_EXAMPLES)}


def enabled_loss_keys(mask: Mapping[str, Any]) -> list[str]:
    return sorted(str(key) for key, value in mask.items() if bool(value))


def parse_language_family(prompt: str) -> str:
    for line in prompt.splitlines():
        if line.startswith("language_families="):
            values = [part for part in line.split("=", 1)[1].split(",") if part]
            if len(values) == 1:
                return values[0]
            if values:
                return "multi_language"
    return "unknown_language_family"


def authority() -> dict[str, bool]:
    return {
        "training_allowed": False,
        "training_run_allowed": False,
        "optimizer_step_authorized": False,
        "runtime_authorized": False,
        "source_emission_authorized": False,
        "body_emission_authorized": False,
    }


def anti_cheat_contract(layer: str) -> dict[str, bool]:
    return {
        "target_label_not_visible_before_options": True,
        "no_empty_template_targets": True,
        "no_raw_path_or_lineage_surface": True,
        "repo_code_private_text_hydrated": layer == "repo_code_knowledge",
        "structured_state_label_surface_bounded": layer == "structured_repo_state",
    }


def repo_example_by_source_record_sha(examples: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_hash: dict[str, dict[str, Any]] = {}
    for row in examples:
        digest = str(row.get("source_row_sha256") or "")
        if not digest:
            raise Stage12667AdapterError("repo_example_missing_source_record_hash")
        if digest in by_hash:
            raise Stage12667AdapterError("repo_example_source_record_hash_duplicate")
        by_hash[digest] = row
    return by_hash


def adapt_repo_row(row: Mapping[str, Any], example: Mapping[str, Any]) -> dict[str, Any]:
    prompt = str(example.get("model_input") or "")
    target = str(example.get("target_text") or "")
    if not prompt or not target:
        raise Stage12667AdapterError("repo_example_missing_prompt_or_target")
    return {
        "row_id": row["combined_manifest_row_id"],
        "split": row["split"],
        "language_family": parse_language_family(prompt),
        "input_state": {
            "curriculum_layer": row["curriculum_layer"],
            "training_objective": row["training_objective"],
            "prompt_surface": prompt,
        },
        "target": {
            "decoder_text": target,
            "semantic_value": str(row["training_objective"]),
        },
        "loss_mask": dict(row["loss_mask"]),
        "loss_weight": row["loss_weight"],
        "authority": authority(),
        "source_provenance": {
            "source_stage": row["source_stage"],
            "source_example_sha256": row["source_example_sha256"],
            "source_record_sha256": row["source_row_sha256"],
        },
        "anti_cheat_contract": anti_cheat_contract(str(row["curriculum_layer"])),
        "adapter_status": "canonical_fields_materialized_loss_binding_pending",
    }


def adapt_structured_row(row: Mapping[str, Any]) -> dict[str, Any]:
    state = row.get("input_state") if isinstance(row.get("input_state"), dict) else {}
    label = str(row.get("target_label") or "")
    if not state or not label:
        raise Stage12667AdapterError("structured_row_missing_state_or_label")
    return {
        "row_id": row["combined_manifest_row_id"],
        "split": row["split"],
        "language_family": str(state.get("language_family") or "unknown_language_family"),
        "input_state": state,
        "target": {
            "bounded_choice_target_label": label,
            "semantic_value": label,
        },
        "loss_mask": dict(row["loss_mask"]),
        "loss_weight": row["loss_weight"],
        "authority": authority(),
        "source_provenance": {
            "source_stage": row["source_stage"],
            "source_record_sha256": stable_hash({
                "row_id": row["combined_manifest_row_id"],
                "input_state": state,
                "target": label,
                "objective": row["training_objective"],
            }),
        },
        "anti_cheat_contract": anti_cheat_contract(str(row["curriculum_layer"])),
        "adapter_status": "canonical_fields_materialized_loss_binding_pending",
    }


def adapt_rows(combined: list[dict[str, Any]], examples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_hash = repo_example_by_source_record_sha(examples)
    rows: list[dict[str, Any]] = []
    for row in combined:
        layer = row.get("curriculum_layer")
        if layer == "repo_code_knowledge":
            example = by_hash.get(str(row.get("source_row_sha256") or ""))
            if example is None:
                raise Stage12667AdapterError("repo_example_source_record_hash_missing")
            rows.append(adapt_repo_row(row, example))
        elif layer == "structured_repo_state":
            rows.append(adapt_structured_row(row))
        else:
            raise Stage12667AdapterError("unexpected_curriculum_layer:" + str(layer))
    assert_no_forbidden(rows, "adapter_candidate_rows", PRIVATE_FORBIDDEN_SUBSTRINGS)
    return rows


def adapter_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) != 2445:
        raise Stage12667AdapterError("adapter_row_count_drift")
    if count(rows, "split") != EXPECTED_SPLITS:
        raise Stage12667AdapterError("adapter_split_count_drift")
    missing = [row["row_id"] for row in rows if CANONICAL_REQUIRED_FIELDS.difference(row)]
    if missing:
        raise Stage12667AdapterError("canonical_required_fields_missing")
    loss_counts: collections.Counter[str] = collections.Counter()
    unsupported_rows = 0
    no_supported_loss_rows = 0
    for row in rows:
        enabled = enabled_loss_keys(row["loss_mask"])
        loss_counts.update(enabled)
        supported = [key for key in enabled if key in SUPPORTED_LOSS_KEYS]
        if any(key not in SUPPORTED_LOSS_KEYS for key in enabled):
            unsupported_rows += 1
        if not supported:
            no_supported_loss_rows += 1
    return {
        "adapter_candidate_rows": len(rows),
        "split_counts": count(rows, "split"),
        "language_family_counts": count(rows, "language_family"),
        "enabled_loss_counts": dict(sorted(loss_counts.items())),
        "unsupported_loss_key_rows": unsupported_rows,
        "rows_with_no_supported_loss_key": no_supported_loss_rows,
        "canonical_required_fields_present": True,
        "all_authority_gates_closed": all(all(value is False for value in row["authority"].values()) for row in rows),
        "adapter_manifest_trainer_runnable": False,
    }


def build_packet() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    loaded = load_inputs()
    if count(loaded["combined"], "curriculum_layer") != EXPECTED_LAYERS:
        raise Stage12667AdapterError("combined_layer_count_drift")
    if count(loaded["combined"], "training_objective") != EXPECTED_OBJECTIVES:
        raise Stage12667AdapterError("combined_objective_count_drift")
    rows = adapt_rows(loaded["combined"], loaded["examples"])
    audit = adapter_audit(rows)
    blockers = [
        "unsupported_loss_keys_require_trainer_registration_or_loss_mapping_review",
        "mixed_objective_schedule_requires_mode_specific_trainer_invocations",
        "explicit_training_run_authorization_still_required",
    ]
    matrix = [
        {"check_id": "stage12666_pins", "status": "pass"},
        {"check_id": "repo_code_private_sidecar_hydration", "status": "pass"},
        {"check_id": "canonical_required_fields", "status": "pass"},
        {"check_id": "authority_gates_closed", "status": "pass"},
        {"check_id": "loss_key_trainer_binding", "status": "blocked", "detail": blockers[0]},
        {"check_id": "mixed_objective_schedule_binding", "status": "blocked", "detail": blockers[1]},
        {"check_id": "training_execution_authority", "status": "blocked", "detail": blockers[2]},
    ]
    summary = {
        "record_type": "stage12667_public_trainer_contract_adapter_preflight_summary_v1",
        "stage": STAGE,
        "decision": "ADAPTER_CANDIDATE_MATERIALIZED_BLOCKED_LOSS_AND_SCHEDULE_BINDING",
        "adapter_candidate_rows": audit["adapter_candidate_rows"],
        "repo_code_rows": EXPECTED_LAYERS["repo_code_knowledge"],
        "structured_repo_state_rows": EXPECTED_LAYERS["structured_repo_state"],
        "split_counts": audit["split_counts"],
        "canonical_required_fields_present": True,
        "unsupported_loss_key_rows": audit["unsupported_loss_key_rows"],
        "rows_with_no_supported_loss_key": audit["rows_with_no_supported_loss_key"],
        "adapter_manifest_trainer_runnable": False,
        "dataset_rows_admitted": True,
        "combined_dataset_rows_admitted": True,
        "authorization_blockers": blockers,
        "next_required_action": "stage12668_combined_curriculum_loss_and_schedule_binding_preflight_only",
        **false_fields(),
    }
    public_audit = {
        "record_type": "stage12667_trainer_contract_adapter_audit_v1",
        "stage": STAGE,
        "decision": summary["decision"],
        **audit,
        "authorization_blockers": blockers,
        "next_required_action": summary["next_required_action"],
        **false_fields(),
    }
    for label, record in (("summary", summary), ("audit", public_audit)):
        assert_no_forbidden(record, label, PUBLIC_FORBIDDEN_SUBSTRINGS)
    return summary, public_audit, matrix, rows


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    summary, audit, matrix, rows = build_packet()
    private = {
        "record_type": "stage12667_private_trainer_contract_adapter_packet_v1",
        "stage": STAGE,
        "stage12666_summary_sha256": EXPECTED_HASHES["stage12666_summary"],
        "stage12666_audit_sha256": EXPECTED_HASHES["stage12666_audit"],
        "combined_manifest_sha256": EXPECTED_HASHES["stage12664_combined"],
        "repo_code_examples_sha256": EXPECTED_HASHES["stage12656_examples"],
        "adapter_candidate_manifest_sha256": stable_hash(rows),
        "audit_sha256": stable_hash(audit),
        **false_fields(),
    }
    contract = {
        "record_type": "stage12667_trainer_contract_adapter_contract_v1",
        "stage": STAGE,
        "decision": summary["decision"],
        "upstream_stage": "stage12666_combined_curriculum_training_authorization_preflight_only",
        "recommended_next_stage": summary["next_required_action"],
        "private_packet_sha256": stable_hash(private),
        "audit_sha256": stable_hash(audit),
        "adapter_candidate_manifest_sha256": stable_hash(rows),
        "adapter_manifest_trainer_runnable": False,
        "training_authorization_preflight_passed": False,
        **false_fields(),
    }
    pointer = {
        "record_type": "stage12667_digest_pointer_v1",
        "stage": STAGE,
        "summary_sha256": stable_hash(summary),
        "contract_sha256": stable_hash(contract),
        "private_packet_sha256": stable_hash(private),
        "audit_sha256": stable_hash(audit),
        "adapter_candidate_manifest_sha256": stable_hash(rows),
        **false_fields(),
    }
    for label, record in (("contract", contract), ("pointer", pointer), ("private", private)):
        assert_no_forbidden(record, label, PUBLIC_FORBIDDEN_SUBSTRINGS)
    write_json(out / "summary.json", summary)
    write_json(out / "adapter_audit.json", audit)
    write_jsonl(out / "private/adapter_checks.jsonl", matrix)
    write_jsonl(out / "private/combined_curriculum_canonical_adapter_candidate_manifest.jsonl", rows)
    write_json(out / "private/trainer_contract_adapter_packet.json", private)
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(summary_path, summary)
    fsync_dir(out)
    fsync_dir(summary_path.parent)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True, ensure_ascii=True))
