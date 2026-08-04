#!/usr/bin/env python3
# Independently review the concrete repo/code training pack without admitting training.
from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12650_repo_code_training_pack_independent_review_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

S12649 = ROOT / "runs/local/artifacts/stage12649_repo_code_training_pack_materialization_preflight_only"
S12649_SUMMARY = ROOT / "runs/summaries/stage12649_repo_code_training_pack_materialization_preflight_only.json"
S12649_SCRIPT = ROOT / "scripts/build_stage12649_repo_code_training_pack_materialization_preflight_only.py"
S12649_TESTS = ROOT / "tests/test_stage12649_repo_code_training_pack_materialization_preflight_only.py"
S12647_ADMITTED = ROOT / "runs/local/artifacts/stage12647_repo_code_knowledge_completion_admission_preflight_only/private/admitted_repo_code_knowledge_rows.jsonl"
S12643_ROWS = ROOT / "runs/local/artifacts/stage12643_repo_code_ce_manifest_preflight_only/private/repo_code_ce_candidate_manifest.jsonl"
S12645_REPAIRED = ROOT / "runs/local/artifacts/stage12645_stage8675_symbol_binding_shortcut_quarantine_reselect/private/repaired_source_backed_symbol_binding_candidate_manifest.jsonl"
S12645_QUARANTINE = ROOT / "runs/local/artifacts/stage12645_stage8675_symbol_binding_shortcut_quarantine_reselect/private/quarantined_source_backed_symbol_binding_rows.jsonl"

EXPECTED_HASHES = {
    "stage12649_summary": "634695abded8642d794354ddb49a9a7d5ba8c626c25176ca3dcc734d92de69ea",
    "stage12649_contract": "fa1cd38059c3d321a21a97a8e7bc5f5c03f034632e8363a9e5958d4ba89d1e1b",
    "stage12649_pointer": "675656c5a15749d75742a728561040f3ead064f366813c4fbef38912555513cc",
    "stage12649_private_packet": "52ecd7c51bdb53b324fa8f91b658dd4fac00ce0c3f54d81173155d19acf88252",
    "stage12649_examples_bytes": "21ec4c4edd027a844042e0d04a4fa7e73611aea503302ecfa37e13dbe170261d",
    "stage12649_examples_semantic": "ab79d922b129853ad76fbdc2121296c0d75478d9f6fdcd28697587d683de62d1",
    "stage12649_script_bytes": "9dbfe82e9d6b0073ffd220f9d798c5a9b93013cc396f48d460b4c1f232a888e3",
    "stage12649_tests_bytes": "79b0796b0e012642f4431eb8c2d43ed09fb57c062a49535e70371ff591c02e73",
    "stage12647_admitted_rows_bytes": "7872bcff8627577be0a8270bdda1760ecae8a2c1f197d0a6a0317958277e3d65",
    "stage12643_rows_bytes": "c627f00695a725359ed88e9a1c1977cc8f25e416953ab902dbe82bdf751e7d42",
    "stage12645_repaired_rows_bytes": "2a2d0ff20ceffae0fb44ec90a09d98200a03f49d1f52703b2c0193d0acf548ae",
    "stage12645_quarantine_rows_bytes": "c90048df65d7174189340e7c79d6f9d2ac0d5cd0df86f5bd10f597d9a21d413e",
}
EXPECTED_STAGE12649_ARTIFACTS = [
    "contract.json",
    "digest_pointer.json",
    "private/repo_code_training_examples.jsonl",
    "private/repo_code_training_pack_materialization_packet.json",
    "summary.json",
]
EXPECTED_COUNTS = {"repo_code_ce": 200, "source_backed_symbol_binding": 80}
EXPECTED_OBJECTIVES = {"repo_code_capability_ce": 200, "source_backed_symbol_binding_ce": 80}
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


class Stage12650ReviewError(RuntimeError):
    pass


def stable_hash(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(data).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12650ReviewError("json_object_required:" + path.name)
    return value


def read_jsonl_bytes(data: bytes) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(data.decode("utf-8").splitlines(), start=1):
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise Stage12650ReviewError(f"jsonl_object_required:{line_number}")
        rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n"
    with path.open("wb") as stream:
        stream.write(data)
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
            raise Stage12650ReviewError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise Stage12650ReviewError(f"{label}_public_leak:{needle}")
    if '"model_input":' in encoded or '"target_text":' in encoded:
        raise Stage12650ReviewError(f"{label}_public_training_text_leak")


def assert_text_sanitized(text: str, label: str) -> None:
    if not isinstance(text, str) or not text.strip():
        raise Stage12650ReviewError(f"{label}_empty_text")
    for needle in TRAINING_TEXT_FORBIDDEN:
        if needle in text:
            raise Stage12650ReviewError(f"{label}_unsafe_text:{needle}")


def split_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(collections.Counter(str(row.get("split")) for row in rows).items()))


def component_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(collections.Counter(str(row.get("admission_family")) for row in rows).items()))


def objective_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(collections.Counter(str(row.get("training_objective")) for row in rows).items()))


def load_stage12649() -> dict[str, Any]:
    emitted = sorted(path.relative_to(S12649).as_posix() for path in S12649.rglob("*") if path.is_file())
    if emitted != EXPECTED_STAGE12649_ARTIFACTS:
        raise Stage12650ReviewError("stage12649_artifact_manifest_drift")
    summary = read_json(S12649 / "summary.json")
    external = read_json(S12649_SUMMARY)
    contract = read_json(S12649 / "contract.json")
    pointer = read_json(S12649 / "digest_pointer.json")
    private = read_json(S12649 / "private/repo_code_training_pack_materialization_packet.json")
    examples_bytes = (S12649 / "private/repo_code_training_examples.jsonl").read_bytes()
    admitted_bytes = S12647_ADMITTED.read_bytes()
    ce_bytes = S12643_ROWS.read_bytes()
    repaired_bytes = S12645_REPAIRED.read_bytes()
    quarantine_bytes = S12645_QUARANTINE.read_bytes()
    examples = read_jsonl_bytes(examples_bytes)
    admitted = read_jsonl_bytes(admitted_bytes)
    ce_rows = read_jsonl_bytes(ce_bytes)
    repaired_rows = read_jsonl_bytes(repaired_bytes)
    quarantine_rows = read_jsonl_bytes(quarantine_bytes)
    if summary != external:
        raise Stage12650ReviewError("stage12649_external_summary_mismatch")
    for label, value in (
        ("stage12649_summary", summary),
        ("stage12649_contract", contract),
        ("stage12649_pointer", pointer),
        ("stage12649_private_packet", private),
    ):
        if stable_hash(value) != EXPECTED_HASHES[label]:
            raise Stage12650ReviewError("pin_drift:" + label)
    for label, data in (
        ("stage12649_examples_bytes", examples_bytes),
        ("stage12649_script_bytes", S12649_SCRIPT.read_bytes()),
        ("stage12649_tests_bytes", S12649_TESTS.read_bytes()),
        ("stage12647_admitted_rows_bytes", admitted_bytes),
        ("stage12643_rows_bytes", ce_bytes),
        ("stage12645_repaired_rows_bytes", repaired_bytes),
        ("stage12645_quarantine_rows_bytes", quarantine_bytes),
    ):
        if sha256_bytes(data) != EXPECTED_HASHES[label]:
            raise Stage12650ReviewError("pin_drift:" + label)
    if stable_hash(examples) != EXPECTED_HASHES["stage12649_examples_semantic"]:
        raise Stage12650ReviewError("pin_drift:stage12649_examples_semantic")
    if pointer.get("contract_sha256") != stable_hash(contract):
        raise Stage12650ReviewError("stage12649_pointer_contract_hash_drift")
    if pointer.get("private_packet_sha256") != stable_hash(private):
        raise Stage12650ReviewError("stage12649_pointer_private_hash_drift")
    if pointer.get("training_examples_sha256") != stable_hash(examples):
        raise Stage12650ReviewError("stage12649_pointer_examples_hash_drift")
    if summary.get("decision") != "TRAINING_PACK_MATERIALIZED_REVIEW_REQUIRED_NO_TRAINING":
        raise Stage12650ReviewError("stage12649_not_at_review_blocker")
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer)):
        check_false(record, "stage12649_" + label)
        assert_public_sanitized(record, "stage12649_" + label)
    check_false(private, "stage12649_private")
    return {
        "summary": summary,
        "contract": contract,
        "pointer": pointer,
        "private": private,
        "examples": examples,
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


def expected_repo_code_text(source: Mapping[str, Any]) -> tuple[str, str]:
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
    return model_input, target_text


def file_features(graph: Mapping[str, Any]) -> dict[str, Any]:
    for node in graph.get("nodes") or []:
        if node.get("node_type") == "file":
            features = node.get("features") or {}
            return dict(sorted(features.items()))
    return {}


def expected_symbol_text(source: Mapping[str, Any]) -> tuple[str, str]:
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
    return model_input, target_text

def review_training_pack(stage12649: Mapping[str, Any]) -> dict[str, Any]:
    summary = stage12649["summary"]
    examples = list(stage12649["examples"])
    admitted = list(stage12649["admitted"])
    ce_by_hash = {stable_hash(row): row for row in stage12649["ce_rows"]}
    repaired_by_hash = {stable_hash(row): row for row in stage12649["repaired_rows"]}
    admitted_by_hash = {str(row.get("source_row_sha256")): row for row in admitted}
    quarantine_hashes = {str(row.get("row_sha256")) for row in stage12649["quarantine_rows"]}
    if len(examples) != 280:
        raise Stage12650ReviewError("training_example_count_drift")
    if len(admitted_by_hash) != 280:
        raise Stage12650ReviewError("admitted_source_hash_collision")
    if len(ce_by_hash) != 200 or len(repaired_by_hash) != 80:
        raise Stage12650ReviewError("review_source_hash_collision")
    if set(repaired_by_hash) & quarantine_hashes:
        raise Stage12650ReviewError("quarantined_rows_in_repaired_source")
    if component_counts(examples) != EXPECTED_COUNTS:
        raise Stage12650ReviewError("training_example_component_drift")
    if objective_counts(examples) != EXPECTED_OBJECTIVES:
        raise Stage12650ReviewError("training_objective_drift")
    if split_counts(examples) != EXPECTED_SPLITS:
        raise Stage12650ReviewError("training_split_drift")
    if summary.get("model_ready_training_rows") != 280:
        raise Stage12650ReviewError("stage12649_model_ready_count_drift")
    source_hashes: set[str] = set()
    model_input_hashes: set[str] = set()
    target_hashes: set[str] = set()
    for index, row in enumerate(examples):
        if row.get("record_type") != "stage12649_private_repo_code_training_example_v1":
            raise Stage12650ReviewError(f"training_example_record_type_drift:{index}")
        if row.get("optimizer_ready") is not True or row.get("repo_code_training_pack_materialized") is not True:
            raise Stage12650ReviewError(f"training_example_materialization_marker_drift:{index}")
        if row.get("training_allowed") is not False:
            raise Stage12650ReviewError(f"training_example_gate_drift:{index}")
        if row.get("admission_family") == "repo_code_ce":
            expected_loss = {"repo_code_ce": True, "symbol_binding_ce": False}
            source = ce_by_hash.get(row.get("source_row_sha256"))
            if source is None:
                raise Stage12650ReviewError(f"missing_repo_code_source_join:{index}")
            expected_model_input, expected_target_text = expected_repo_code_text(source)
        elif row.get("admission_family") == "source_backed_symbol_binding":
            expected_loss = {"repo_code_ce": False, "symbol_binding_ce": True}
            source = repaired_by_hash.get(row.get("source_row_sha256"))
            if source is None:
                raise Stage12650ReviewError(f"missing_symbol_source_join:{index}")
            expected_model_input, expected_target_text = expected_symbol_text(source)
        else:
            raise Stage12650ReviewError(f"unknown_training_example_family:{index}")
        admitted_row = admitted_by_hash.get(str(row.get("source_row_sha256")))
        if admitted_row is None:
            raise Stage12650ReviewError(f"missing_admitted_row_join:{index}")
        for field in ("admission_family", "source_stage", "split"):
            if row.get(field) != admitted_row.get(field):
                raise Stage12650ReviewError(f"admitted_row_binding_drift:{index}:{field}")
        if row.get("source_row_sha256") in quarantine_hashes:
            raise Stage12650ReviewError(f"quarantined_training_source_selected:{index}")
        if row.get("loss_mask") != expected_loss:
            raise Stage12650ReviewError(f"loss_mask_drift:{index}")
        assert_text_sanitized(row.get("model_input", ""), f"model_input:{index}")
        assert_text_sanitized(row.get("target_text", ""), f"target_text:{index}")
        if row.get("model_input") != expected_model_input or row.get("target_text") != expected_target_text:
            raise Stage12650ReviewError(f"training_text_render_drift:{index}")
        encoded = json.dumps(row, sort_keys=True, ensure_ascii=True)
        if "/data/" in encoded or "/arxiv/" in encoded or "source_lineage" in encoded or "source_row_id" in encoded or "source_ref" in encoded:
            raise Stage12650ReviewError(f"training_example_private_leak:{index}")
        source_hashes.add(str(row.get("source_row_sha256")))
        model_input_hashes.add(stable_hash(row["model_input"]))
        target_hashes.add(stable_hash(row["target_text"]))
    if len(source_hashes) != 280:
        raise Stage12650ReviewError("duplicate_source_hashes")
    if len(model_input_hashes) < 120:
        raise Stage12650ReviewError("model_input_diversity_too_low")
    if len(target_hashes) < 50:
        raise Stage12650ReviewError("target_diversity_too_low")
    return {
        "training_pack_reviewed": True,
        "training_pack_review_passed": True,
        "training_examples_materialized": True,
        "training_pack_materialized": True,
        "model_ready_training_rows": 280,
        "repo_code_ce_training_examples": 200,
        "symbol_binding_training_examples": 80,
        "training_split_counts": EXPECTED_SPLITS,
        "training_objective_counts": EXPECTED_OBJECTIVES,
        "optimizer_ready_rows": 280,
        "placeholder_training_rows": 0,
        "raw_path_training_rows": 0,
        "private_lineage_training_rows": 0,
        "quarantined_rows_in_training_pack": 0,
        "admitted_row_joins_verified": 280,
        "reviewed_source_joins_verified": 280,
        "training_text_renders_verified": 280,
        "unique_source_row_hashes": len(source_hashes),
        "unique_model_input_hashes": len(model_input_hashes),
        "unique_target_text_hashes": len(target_hashes),
        "review_blocker_count": 0,
        "review_blockers": [],
    }


def build_packet(stage12649: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    audit = review_training_pack(stage12649)
    true_fields = {
        "repo_code_knowledge_stage_complete": True,
        "dataset_rows_admitted": True,
        "repo_code_rows_admitted": True,
        "repo_code_training_pack_materialized": True,
        "training_pack_materialized": True,
        "training_examples_materialized": True,
        "training_pack_reviewed": True,
        "training_pack_review_passed": True,
        "separate_training_admission_required": True,
    }
    private = {
        "record_type": "stage12650_private_repo_code_training_pack_independent_review_v1",
        **false_fields(),
        **true_fields,
        "reviewed_input_hashes": EXPECTED_HASHES,
        "training_pack_review_audit": audit,
        "claim_boundary": {
            "training_pack": "independently_reviewed_and_passed",
            "training": "not_authorized_separate_training_admission_required",
            "strict_eval": "not_admitted",
            "sealed_eval": "not_admitted",
            "level_3": "not_materialized",
        },
    }
    contract = {
        "record_type": "stage12650_public_repo_code_training_pack_independent_review_contract_v1",
        **false_fields(),
        **true_fields,
        **audit,
        "private_packet_sha256": stable_hash(private),
        "training_allowed": False,
        "training_run_allowed": False,
        "optimizer_step_authorized": False,
        "next_required_action": "stage12651_separate_training_admission_preflight_only",
    }
    summary = {
        "record_type": "stage12650_public_repo_code_training_pack_independent_review_summary_v1",
        **false_fields(),
        **true_fields,
        **audit,
        "stage": STAGE,
        "decision": "TRAINING_PACK_REVIEW_PASSED_SEPARATE_TRAINING_ADMISSION_REQUIRED",
        "training_allowed": False,
        "training_run_allowed": False,
        "optimizer_step_authorized": False,
        "private_packet_sha256": stable_hash(private),
        "contract_sha256": stable_hash(contract),
        "next_required_action": "stage12651_separate_training_admission_preflight_only",
    }
    pointer = {
        "record_type": "stage12650_public_repo_code_training_pack_independent_review_pointer_v1",
        **false_fields(),
        **true_fields,
        "contract_sha256": stable_hash(contract),
        "private_packet_sha256": stable_hash(private),
        "reviewed_training_examples_sha256": EXPECTED_HASHES["stage12649_examples_semantic"],
    }
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer)):
        check_false(record, label)
        assert_public_sanitized(record, label)
    check_false(private, "private")
    return summary, contract, private, pointer


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    summary, contract, private, pointer = build_packet(load_stage12649())
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/repo_code_training_pack_independent_review_packet.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    fsync_dir(out / "private")
    fsync_dir(out)
    fsync_dir(summary_path.parent)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
