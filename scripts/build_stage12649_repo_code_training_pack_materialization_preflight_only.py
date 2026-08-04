#!/usr/bin/env python3
# Materialize optimizer-ready repo/code training examples from reviewed admitted rows without authorizing training.
from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12649_repo_code_training_pack_materialization_preflight_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

S12648 = ROOT / "runs/local/artifacts/stage12648_separate_training_admission_preflight_only"
S12648_SUMMARY = ROOT / "runs/summaries/stage12648_separate_training_admission_preflight_only.json"
S12647 = ROOT / "runs/local/artifacts/stage12647_repo_code_knowledge_completion_admission_preflight_only"
S12647_ADMITTED = S12647 / "private/admitted_repo_code_knowledge_rows.jsonl"
S12643_ROWS = ROOT / "runs/local/artifacts/stage12643_repo_code_ce_manifest_preflight_only/private/repo_code_ce_candidate_manifest.jsonl"
S12645_REPAIRED = ROOT / "runs/local/artifacts/stage12645_stage8675_symbol_binding_shortcut_quarantine_reselect/private/repaired_source_backed_symbol_binding_candidate_manifest.jsonl"
S12645_QUARANTINE = ROOT / "runs/local/artifacts/stage12645_stage8675_symbol_binding_shortcut_quarantine_reselect/private/quarantined_source_backed_symbol_binding_rows.jsonl"
S12648_SCRIPT = ROOT / "scripts/build_stage12648_separate_training_admission_preflight_only.py"
S12648_TESTS = ROOT / "tests/test_stage12648_separate_training_admission_preflight_only.py"

EXPECTED_HASHES = {
    "stage12648_summary": "5a0429da6198e94ffd1bcfc9a31ff9c442b0429a83c94e0c07b686c4bc7fd387",
    "stage12648_contract": "b5b579a2e6d127b809a3aa3c54c8d2ee112fcedc9eb6f520d9b9859d0dea2bdb",
    "stage12648_pointer": "1fb4cb06f5c22b89d4b64a0e4b214a254613f7dde0485f55c0dad93b52016971",
    "stage12648_private": "cf2a141a0472fb6184fe295d87d2ffb7500fb1c1c609bc8e38e1f6dfa584d537",
    "stage12648_script_bytes": "12405ed73cb6b77e39add4693f561a9ebd6cfb4e8b49bff4dd1d4c90eab7fe6e",
    "stage12648_tests_bytes": "5cd979e34ef552b065d7cbdda8338266610cfcc954fe68d5f66dfde0627d1147",
    "stage12647_admitted_rows_bytes": "7872bcff8627577be0a8270bdda1760ecae8a2c1f197d0a6a0317958277e3d65",
    "stage12643_rows_bytes": "c627f00695a725359ed88e9a1c1977cc8f25e416953ab902dbe82bdf751e7d42",
    "stage12645_repaired_rows_bytes": "2a2d0ff20ceffae0fb44ec90a09d98200a03f49d1f52703b2c0193d0acf548ae",
    "stage12645_quarantine_rows_bytes": "c90048df65d7174189340e7c79d6f9d2ac0d5cd0df86f5bd10f597d9a21d413e",
}
EXPECTED_STAGE12648_ARTIFACTS = [
    "contract.json",
    "digest_pointer.json",
    "private/separate_training_admission_preflight_only.json",
    "summary.json",
]
EXPECTED_COUNTS = {"repo_code_ce": 200, "source_backed_symbol_binding": 80}
EXPECTED_SPLITS = {"eval": 64, "strict_eval": 63, "train": 153}
FALSE_FIELDS = (
    "training_admission_allowed",
    "training_allowed",
    "training_run_allowed",
    "training_admitted",
    "strict_eval_admitted",
    "sealed_eval_admitted",
    "strict_eval_eligible",
    "sealed_eval_eligible",
    "implementation_ready",
    "stage12595_allowed",
    "replay_trustworthy",
    "level_3_materialized",
    "gpu_allocation_requested",
    "cuda2_training_allowed",
    "vm_runner_execution_allowed",
    "runtime_authorized",
    "model_execution_authorized_next",
    "source_emission_authorized",
    "body_emission_authorized",
    "decoder_ce_training_authorized_next",
    "transition_head_training_authorized_next",
    "promotion_ready",
    "optimizer_step_authorized",
)
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/",
    "/arxiv/",
    "jsonl",
    "row_id",
    "source_row_id",
    "source_ref",
    "old_source_ref_path",
    "raw_stream",
    "stdout.raw",
    "stderr.raw",
    "repository_root",
    "patch_path",
    "production_path",
)
TRAINING_TEXT_FORBIDDEN = (
    "/data/",
    "/arxiv/",
    "\x00",
    "Answer:",
    "PLACEHOLDER",
    "placeholder",
    "TODO",
    "TBD",
    "<fill",
    "source_ref",
    "source_row_id",
    "raw_stream",
    "stdout.raw",
    "stderr.raw",
)


class Stage12649TrainingPackError(RuntimeError):
    pass


def stable_hash(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(data).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12649TrainingPackError("json_object_required:" + path.name)
    return value


def read_jsonl_bytes(data: bytes) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(data.decode("utf-8").splitlines(), start=1):
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise Stage12649TrainingPackError(f"jsonl_object_required:{line_number}")
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
            stream.write(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii") + b"\n")
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


def check_false(record: Mapping[str, Any], label: str) -> None:
    for field in FALSE_FIELDS:
        if record.get(field) is not False:
            raise Stage12649TrainingPackError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise Stage12649TrainingPackError(f"{label}_public_leak:{needle}")


def assert_text_sanitized(text: str, label: str) -> None:
    if not isinstance(text, str) or not text.strip():
        raise Stage12649TrainingPackError(f"{label}_empty_text")
    for needle in TRAINING_TEXT_FORBIDDEN:
        if needle in text:
            raise Stage12649TrainingPackError(f"{label}_unsafe_text:{needle}")


def split_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(collections.Counter(str(row.get("split")) for row in rows).items()))


def component_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(collections.Counter(str(row.get("admission_family")) for row in rows).items()))


def load_inputs() -> dict[str, Any]:
    emitted = sorted(path.relative_to(S12648).as_posix() for path in S12648.rglob("*") if path.is_file())
    if emitted != EXPECTED_STAGE12648_ARTIFACTS:
        raise Stage12649TrainingPackError("stage12648_artifact_manifest_drift")
    summary = read_json(S12648 / "summary.json")
    if summary != read_json(S12648_SUMMARY):
        raise Stage12649TrainingPackError("stage12648_external_summary_mismatch")
    contract = read_json(S12648 / "contract.json")
    pointer = read_json(S12648 / "digest_pointer.json")
    private = read_json(S12648 / "private/separate_training_admission_preflight_only.json")
    for label, value in (
        ("stage12648_summary", summary),
        ("stage12648_contract", contract),
        ("stage12648_pointer", pointer),
        ("stage12648_private", private),
    ):
        if stable_hash(value) != EXPECTED_HASHES[label]:
            raise Stage12649TrainingPackError("pin_drift:" + label)
    for label, data in (
        ("stage12648_script_bytes", S12648_SCRIPT.read_bytes()),
        ("stage12648_tests_bytes", S12648_TESTS.read_bytes()),
    ):
        if sha256_bytes(data) != EXPECTED_HASHES[label]:
            raise Stage12649TrainingPackError("pin_drift:" + label)
    if summary.get("decision") != "BLOCKED_TRAINING_PACK_MATERIALIZATION_REQUIRED":
        raise Stage12649TrainingPackError("stage12648_not_at_pack_materialization_blocker")
    if summary.get("repo_code_knowledge_stage_complete") is not True or summary.get("dataset_rows_admitted") is not True:
        raise Stage12649TrainingPackError("repo_code_admission_not_complete")
    check_false(summary, "stage12648_summary")
    for label, record in (("contract", contract), ("pointer", pointer)):
        check_false(record, "stage12648_" + label)
        assert_public_sanitized(record, "stage12648_" + label)

    admitted_bytes = S12647_ADMITTED.read_bytes()
    ce_bytes = S12643_ROWS.read_bytes()
    repaired_bytes = S12645_REPAIRED.read_bytes()
    quarantine_bytes = S12645_QUARANTINE.read_bytes()
    for label, data in (
        ("stage12647_admitted_rows_bytes", admitted_bytes),
        ("stage12643_rows_bytes", ce_bytes),
        ("stage12645_repaired_rows_bytes", repaired_bytes),
        ("stage12645_quarantine_rows_bytes", quarantine_bytes),
    ):
        if sha256_bytes(data) != EXPECTED_HASHES[label]:
            raise Stage12649TrainingPackError("pin_drift:" + label)
    admitted = read_jsonl_bytes(admitted_bytes)
    ce_rows = read_jsonl_bytes(ce_bytes)
    repaired_rows = read_jsonl_bytes(repaired_bytes)
    quarantine_rows = read_jsonl_bytes(quarantine_bytes)
    return {
        "stage12648_summary": summary,
        "admitted": admitted,
        "ce_rows": ce_rows,
        "repaired_rows": repaired_rows,
        "quarantine_rows": quarantine_rows,
    }


def compact_list(values: Any) -> str:
    if not isinstance(values, list):
        return "none"
    return ",".join(str(value) for value in values) if values else "none"


def compact_counts(values: Mapping[str, Any]) -> str:
    return ",".join(f"{key}={values[key]}" for key in sorted(values)) if values else "none"


def make_repo_code_example(admitted: Mapping[str, Any], source: Mapping[str, Any]) -> dict[str, Any]:
    inp = source.get("input") or {}
    target = source.get("target") or {}
    graph_shape = inp.get("graph_shape") or {}
    model_input = "\n".join([
        "objective=repo_code_capability_ce",
        f"opaque_repo_id={inp.get('opaque_repo_id')}",
        f"language_families={compact_list(inp.get('language_families'))}",
        f"build_system_families={compact_list(inp.get('build_system_families'))}",
        f"repo_size_bucket={inp.get('repo_size_bucket')}",
        f"test_coverage_bucket={inp.get('test_coverage_bucket')}",
        f"has_docs={inp.get('has_docs')}",
        f"has_tests={inp.get('has_tests')}",
        f"scan_truncated={inp.get('scan_truncated')}",
        f"graph_nodes={graph_shape.get('node_count')}",
        f"graph_edges={graph_shape.get('edge_count')}",
        f"node_type_counts={compact_counts(graph_shape.get('node_type_counts') or {})}",
        f"edge_type_counts={compact_counts(graph_shape.get('edge_type_counts') or {})}",
        "predict=compact_maintenance_text",
    ])
    target_text = str(target.get("compact_maintenance_text") or "")
    return build_training_example(admitted, model_input, target_text, "repo_code_capability_ce", {"repo_code_ce": True, "symbol_binding_ce": False})


def file_features(graph: Mapping[str, Any]) -> dict[str, Any]:
    for node in graph.get("nodes") or []:
        if node.get("node_type") == "file":
            features = node.get("features") or {}
            return dict(sorted(features.items()))
    return {}


def make_symbol_example(admitted: Mapping[str, Any], source: Mapping[str, Any]) -> dict[str, Any]:
    graph = source.get("graph_input") or {}
    query = source.get("query") or {}
    query_features = query.get("features") or {}
    clean_state = source.get("clean_state") or {}
    model_input = "\n".join([
        "objective=source_backed_symbol_binding_ce",
        f"query_kind={query.get('query_kind')}",
        f"source_file_is_test={query_features.get('source_file_is_test')}",
        f"query_feature_keys={compact_list(sorted(query_features.keys()))}",
        f"file_features={compact_counts(file_features(graph))}",
        f"graph_node_types={compact_counts(collections.Counter(str(node.get('node_type')) for node in graph.get('nodes') or []))}",
        f"graph_edge_types={compact_counts(collections.Counter(str(edge.get('edge_type')) for edge in graph.get('edges') or []))}",
        f"route={source.get('route')}",
        "predict=binding_action_and_target_presence",
    ])
    target_text = "; ".join([
        f"binding_action={clean_state.get('binding_action')}",
        f"target_node_presence={clean_state.get('target_node_presence')}",
        f"target_node_kind={clean_state.get('target_node_kind')}",
    ])
    return build_training_example(admitted, model_input, target_text, "source_backed_symbol_binding_ce", {"repo_code_ce": False, "symbol_binding_ce": True})


def build_training_example(admitted: Mapping[str, Any], model_input: str, target_text: str, training_objective: str, loss_mask: Mapping[str, bool]) -> dict[str, Any]:
    assert_text_sanitized(model_input, "model_input")
    assert_text_sanitized(target_text, "target_text")
    if len(model_input) < 80 or len(target_text) < 20:
        raise Stage12649TrainingPackError("training_text_too_small")
    row = {
        "record_type": "stage12649_private_repo_code_training_example_v1",
        "example_id": str(admitted.get("admitted_row_id")).replace("stage12647_", "stage12649_training_"),
        "admission_family": admitted.get("admission_family"),
        "source_stage": admitted.get("source_stage"),
        "source_row_sha256": admitted.get("source_row_sha256"),
        "split": admitted.get("split"),
        "training_objective": training_objective,
        "model_input": model_input,
        "target_text": target_text,
        "loss_mask": dict(loss_mask),
        "optimizer_ready": True,
        "repo_code_training_pack_materialized": True,
        "training_allowed": False,
    }
    if not any(row["loss_mask"].values()):
        raise Stage12649TrainingPackError("inactive_loss_mask")
    return row


def materialize_training_examples(inputs: Mapping[str, Any]) -> list[dict[str, Any]]:
    admitted = list(inputs["admitted"])
    ce_by_hash = {stable_hash(row): row for row in inputs["ce_rows"]}
    repaired_by_hash = {stable_hash(row): row for row in inputs["repaired_rows"]}
    quarantine_hashes = {str(row.get("row_sha256")) for row in inputs["quarantine_rows"]}
    if len(ce_by_hash) != 200 or len(repaired_by_hash) != 80:
        raise Stage12649TrainingPackError("source_hash_collision")
    if set(repaired_by_hash) & quarantine_hashes:
        raise Stage12649TrainingPackError("quarantined_rows_in_repaired_source")
    if len(admitted) != 280 or split_counts(admitted) != EXPECTED_SPLITS or component_counts(admitted) != EXPECTED_COUNTS:
        raise Stage12649TrainingPackError("admitted_ledger_count_split_drift")
    examples: list[dict[str, Any]] = []
    used_source_hashes: set[str] = set()
    for row in admitted:
        family = row.get("admission_family")
        source_hash = str(row.get("source_row_sha256"))
        used_source_hashes.add(source_hash)
        if source_hash in quarantine_hashes:
            raise Stage12649TrainingPackError("quarantined_row_admitted_to_training_pack")
        if family == "repo_code_ce":
            source = ce_by_hash.get(source_hash)
            if source is None:
                raise Stage12649TrainingPackError("missing_repo_code_source_row")
            examples.append(make_repo_code_example(row, source))
        elif family == "source_backed_symbol_binding":
            source = repaired_by_hash.get(source_hash)
            if source is None:
                raise Stage12649TrainingPackError("missing_symbol_source_row")
            examples.append(make_symbol_example(row, source))
        else:
            raise Stage12649TrainingPackError("unknown_admission_family")
    if len(used_source_hashes) != 280 or len(examples) != 280:
        raise Stage12649TrainingPackError("training_example_source_collision")
    for example in examples:
        assert_text_sanitized(example["model_input"], "model_input")
        assert_text_sanitized(example["target_text"], "target_text")
        if example.get("training_allowed") is not False:
            raise Stage12649TrainingPackError("example_training_gate_drift")
    return examples


def audit_examples(examples: list[dict[str, Any]]) -> dict[str, Any]:
    if len(examples) != 280:
        raise Stage12649TrainingPackError("training_example_count_drift")
    counts = component_counts(examples)
    splits = split_counts(examples)
    if counts != EXPECTED_COUNTS or splits != EXPECTED_SPLITS:
        raise Stage12649TrainingPackError("training_example_distribution_drift")
    source_hashes = {str(example["source_row_sha256"]) for example in examples}
    input_hashes = {stable_hash(example["model_input"]) for example in examples}
    target_hashes = {stable_hash(example["target_text"]) for example in examples}
    if len(source_hashes) != 280:
        raise Stage12649TrainingPackError("duplicate_source_hashes")
    if len(input_hashes) < 120:
        raise Stage12649TrainingPackError("model_input_diversity_too_low")
    if len(target_hashes) < 50:
        raise Stage12649TrainingPackError("target_diversity_too_low")
    return {
        "training_examples_materialized": True,
        "training_pack_materialized": True,
        "model_ready_training_rows": 280,
        "repo_code_ce_training_examples": counts["repo_code_ce"],
        "symbol_binding_training_examples": counts["source_backed_symbol_binding"],
        "training_split_counts": splits,
        "optimizer_ready_rows": sum(1 for example in examples if example.get("optimizer_ready") is True),
        "repo_code_ce_loss_mask_rows": sum(1 for example in examples if example.get("loss_mask", {}).get("repo_code_ce") is True),
        "symbol_binding_ce_loss_mask_rows": sum(1 for example in examples if example.get("loss_mask", {}).get("symbol_binding_ce") is True),
        "quarantined_rows_in_training_pack": 0,
        "placeholder_training_rows": 0,
        "raw_path_training_rows": 0,
        "unique_source_row_hashes": len(source_hashes),
        "unique_model_input_hashes": len(input_hashes),
        "unique_target_text_hashes": len(target_hashes),
    }


def build_packet(inputs: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    examples = materialize_training_examples(inputs)
    audit = audit_examples(examples)
    examples_hash = stable_hash(examples)
    true_fields = {
        "repo_code_knowledge_stage_complete": True,
        "dataset_rows_admitted": True,
        "repo_code_rows_admitted": True,
        "repo_code_training_pack_materialized": True,
        "training_pack_materialized": True,
        "training_examples_materialized": True,
        "separate_training_admission_required": True,
        "training_pack_independent_review_required": True,
    }
    private = {
        "record_type": "stage12649_private_repo_code_training_pack_materialization_packet_v1",
        **false_fields(),
        **true_fields,
        "reviewed_input_hashes": EXPECTED_HASHES,
        "training_pack_audit": audit,
        "training_examples_sha256": examples_hash,
        "claim_boundary": {
            "training_pack": "materialized_optimizer_ready_examples",
            "training": "not_authorized_independent_pack_review_required",
            "strict_eval": "not_admitted",
            "sealed_eval": "not_admitted",
            "level_3": "not_materialized",
        },
    }
    contract = {
        "record_type": "stage12649_public_repo_code_training_pack_materialization_contract_v1",
        **false_fields(),
        **true_fields,
        **audit,
        "training_examples_sha256": examples_hash,
        "private_packet_sha256": stable_hash(private),
        "training_allowed": False,
        "training_run_allowed": False,
        "optimizer_step_authorized": False,
        "next_required_action": "stage12650_repo_code_training_pack_independent_review_only",
    }
    summary = {
        "record_type": "stage12649_public_repo_code_training_pack_materialization_summary_v1",
        **false_fields(),
        **true_fields,
        **audit,
        "stage": STAGE,
        "decision": "TRAINING_PACK_MATERIALIZED_REVIEW_REQUIRED_NO_TRAINING",
        "repo_code_knowledge_rows_admitted": 280,
        "training_examples_sha256": examples_hash,
        "private_packet_sha256": stable_hash(private),
        "contract_sha256": stable_hash(contract),
        "training_allowed": False,
        "training_run_allowed": False,
        "optimizer_step_authorized": False,
        "next_required_action": "stage12650_repo_code_training_pack_independent_review_only",
    }
    pointer = {
        "record_type": "stage12649_public_repo_code_training_pack_materialization_pointer_v1",
        **false_fields(),
        **true_fields,
        "contract_sha256": stable_hash(contract),
        "private_packet_sha256": stable_hash(private),
        "training_examples_sha256": examples_hash,
    }
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer)):
        check_false(record, label)
        assert_public_sanitized(record, label)
    check_false(private, "private")
    return summary, contract, private, pointer, examples


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    summary, contract, private, pointer, examples = build_packet(load_inputs())
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/repo_code_training_pack_materialization_packet.json", private)
    write_jsonl(out / "private/repo_code_training_examples.jsonl", examples)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    fsync_dir(out / "private")
    fsync_dir(out)
    fsync_dir(summary_path.parent)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
