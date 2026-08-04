#!/usr/bin/env python3
# Harden repo/code symbol-binding curriculum rows against compact-signature shortcuts without authorizing training.
from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12656_repo_code_symbol_binding_shortcut_resilience_preflight_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

S12645_REPAIRED = ROOT / "runs/local/artifacts/stage12645_stage8675_symbol_binding_shortcut_quarantine_reselect/private/repaired_source_backed_symbol_binding_candidate_manifest.jsonl"
S12649_EXAMPLES = ROOT / "runs/local/artifacts/stage12649_repo_code_training_pack_materialization_preflight_only/private/repo_code_training_examples.jsonl"
S12651_MANIFEST = ROOT / "runs/local/artifacts/stage12651_repo_code_curriculum_ingestion_contract_preflight_only/private/repo_code_curriculum_ingest_manifest.jsonl"
S12655_SUMMARY = ROOT / "runs/summaries/stage12655_repo_code_optimizer_context_trainer_binding_preflight_only.json"

EXPECTED_HASHES = {
    "stage12645_repaired_rows_bytes": "2a2d0ff20ceffae0fb44ec90a09d98200a03f49d1f52703b2c0193d0acf548ae",
    "stage12649_examples_bytes": "21ec4c4edd027a844042e0d04a4fa7e73611aea503302ecfa37e13dbe170261d",
    "stage12651_manifest_bytes": "d19e8b0139d1dd179ca369b7db8c4252b8ac4e711855208fd273ec9419a46cb1",
    "stage12655_summary_bytes": "032eacc114cd7cea72723d58fc040d4176b36788ed545a5a51e95d0aa860f230",
}
EXPECTED_COUNTS = {"repo_code_capability_ce": 200, "source_backed_symbol_binding_ce": 80}
EXPECTED_SPLITS = {"eval": 64, "strict_eval": 63, "train": 153}
EXPECTED_LANES = {
    "repo_code_knowledge.repo_capability_profile": 200,
    "repo_code_knowledge.symbol_reference_prediction": 80,
}
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
FORBIDDEN_SUBSTRINGS = (
    "/data/",
    "/arxiv/",
    "\x00",
    "Answer:",
    "PLACEHOLDER",
    "placeholder",
    "TODO",
    "TBD",
    "<fill",
    "source_lineage",
    "source_row_id",
    "source_ref",
    "old_source_ref_path",
    "semantic_key",
    "query_node_id",
    "graph_id",
)
PUBLIC_FORBIDDEN_SUBSTRINGS = FORBIDDEN_SUBSTRINGS + ("model_input", "target_text", "jsonl")


class Stage12656ShortcutResilienceError(RuntimeError):
    pass


def stable_hash(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(data).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12656ShortcutResilienceError("json_object_required:" + path.name)
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise Stage12656ShortcutResilienceError(f"jsonl_object_required:{line_number}")
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
            raise Stage12656ShortcutResilienceError(f"{label}_gate_drift:{field}")


def assert_sanitized(value: Any, label: str, needles: tuple[str, ...] = FORBIDDEN_SUBSTRINGS) -> None:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True) if not isinstance(value, str) else value
    for needle in needles:
        if needle in encoded:
            raise Stage12656ShortcutResilienceError(f"{label}_leak:{needle}")


def counts(rows: Iterable[Mapping[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(collections.Counter(str(row.get(field)) for row in rows).items()))


def counter_text(values: Iterable[Any]) -> str:
    counted = collections.Counter(str(value) for value in values)
    return ",".join(f"{key}={value}" for key, value in sorted(counted.items())) if counted else "none"


def flat_pairs(prefix: str, value: Any) -> list[tuple[str, Any]]:
    if isinstance(value, dict):
        out: list[tuple[str, Any]] = []
        for key in sorted(value):
            child = f"{prefix}.{key}" if prefix else str(key)
            out.extend(flat_pairs(child, value[key]))
        return out
    return [(prefix, value)]


def recall_bucket(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "none"
    if value >= 0.99:
        return "gte_0.99"
    if value >= 0.95:
        return "gte_0.95"
    if value >= 0.90:
        return "gte_0.90"
    return "lt_0.90"


def file_features(graph_input: Mapping[str, Any]) -> dict[str, Any]:
    for node in graph_input.get("nodes", []):
        if isinstance(node, dict) and node.get("node_type") == "file":
            features = node.get("features", {})
            if isinstance(features, dict):
                return dict(features)
    return {}


def source_hash(row: Mapping[str, Any]) -> str:
    return stable_hash(row)


def enriched_symbol_input(source_row: Mapping[str, Any]) -> str:
    graph_input = source_row.get("graph_input", {})
    query = source_row.get("query", {})
    retrieval = source_row.get("retrieval_control", {})
    if not isinstance(graph_input, dict) or not isinstance(query, dict) or not isinstance(retrieval, dict):
        raise Stage12656ShortcutResilienceError("symbol_source_shape_drift")
    nodes = [node for node in graph_input.get("nodes", []) if isinstance(node, dict)]
    edges = [edge for edge in graph_input.get("edges", []) if isinstance(edge, dict)]
    file_feature_text = ",".join(f"{key}={value}" for key, value in sorted(file_features(graph_input).items())) or "none"
    query_features = query.get("features", {})
    if not isinstance(query_features, dict):
        raise Stage12656ShortcutResilienceError("query_features_shape_drift")
    query_feature_text = ",".join(f"{key}={value}" for key, value in flat_pairs("", query_features)) or "none"
    lines = [
        "objective=source_backed_symbol_binding_ce",
        f"query_kind={query.get('query_kind')}",
        f"graph_query_kind={graph_input.get('query_kind')}",
        f"source_file_is_test={query_features.get('source_file_is_test')}",
        f"node_count={len(nodes)}",
        f"edge_count={len(edges)}",
        "graph_node_types=" + counter_text(node.get("node_type") for node in nodes),
        "graph_edge_types=" + counter_text(edge.get("edge_type") for edge in edges),
        "repo_languages=" + counter_text(
            node.get("features", {}).get("language_family")
            for node in nodes
            if node.get("node_type") == "repo" and isinstance(node.get("features"), dict)
        ),
        "file_features=" + file_feature_text,
        "query_features=" + query_feature_text,
        f"retrieval_required={retrieval.get('retrieval_required')}",
        f"evidence_removed_disallowed={retrieval.get('evidence_removed_disallowed')}",
        f"metadata_only_disallowed={retrieval.get('metadata_only_disallowed')}",
        f"bm25_recall_bucket={recall_bucket(retrieval.get('bm25_top5_recall'))}",
        f"dense_recall_bucket={recall_bucket(retrieval.get('dense_top5_recall'))}",
        f"hybrid_rrf_recall_bucket={recall_bucket(retrieval.get('hybrid_rrf_top5_recall'))}",
        "predict=binding_action_and_target_presence",
    ]
    text = "\n".join(lines)
    assert_sanitized(text, "enriched_symbol_input")
    return text


def load_inputs() -> dict[str, Any]:
    for label, path in (
        ("stage12645_repaired_rows_bytes", S12645_REPAIRED),
        ("stage12649_examples_bytes", S12649_EXAMPLES),
        ("stage12651_manifest_bytes", S12651_MANIFEST),
        ("stage12655_summary_bytes", S12655_SUMMARY),
    ):
        if sha256_bytes(path.read_bytes()) != EXPECTED_HASHES[label]:
            raise Stage12656ShortcutResilienceError("pin_drift:" + label)
    repaired_rows = read_jsonl(S12645_REPAIRED)
    examples = read_jsonl(S12649_EXAMPLES)
    manifest = read_jsonl(S12651_MANIFEST)
    summary = read_json(S12655_SUMMARY)
    if summary.get("repo_code_curriculum_layer_complete") is not True:
        raise Stage12656ShortcutResilienceError("repo_code_curriculum_not_complete")
    check_false(summary, "stage12655_summary")
    if counts(examples, "training_objective") != EXPECTED_COUNTS:
        raise Stage12656ShortcutResilienceError("stage12649_objective_count_drift")
    if counts(examples, "split") != EXPECTED_SPLITS:
        raise Stage12656ShortcutResilienceError("stage12649_split_count_drift")
    if counts(manifest, "curriculum_lane") != EXPECTED_LANES:
        raise Stage12656ShortcutResilienceError("stage12651_lane_count_drift")
    return {"repaired_rows": repaired_rows, "examples": examples, "manifest": manifest, "summary": summary}


def cross_split_duplicate_hashes(examples: list[Mapping[str, Any]]) -> tuple[set[str], dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = collections.defaultdict(list)
    for example in examples:
        if example.get("training_objective") != "source_backed_symbol_binding_ce":
            continue
        grouped[stable_hash(example["model_input"])].append(example)
    duplicate_groups = [rows for rows in grouped.values() if len({row.get("split") for row in rows}) > 1]
    duplicate_hashes = {str(row["source_row_sha256"]) for rows in duplicate_groups for row in rows}
    return duplicate_hashes, {
        "cross_split_duplicate_signature_groups": len(duplicate_groups),
        "cross_split_duplicate_signature_rows": len(duplicate_hashes),
    }


def materialize_overlay(inputs: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    source_by_hash = {source_hash(row): row for row in inputs["repaired_rows"]}
    manifest_by_example = {row["source_example_id"]: row for row in inputs["manifest"]}
    hardened_examples: list[dict[str, Any]] = []
    for example in inputs["examples"]:
        row = dict(example)
        row["record_type"] = "stage12656_private_shortcut_resilient_training_example_v1"
        row["example_id"] = row["example_id"].replace("stage12649_training_", "stage12656_hardened_")
        row["shortcut_resilience_overlay_materialized"] = True
        if row.get("training_objective") == "source_backed_symbol_binding_ce":
            source = source_by_hash.get(row.get("source_row_sha256"))
            if source is None:
                raise Stage12656ShortcutResilienceError("symbol_source_join_missing")
            row["model_input"] = enriched_symbol_input(source)
            row["symbol_input_enriched_with_nonleaky_structure"] = True
        else:
            row["symbol_input_enriched_with_nonleaky_structure"] = False
        assert_sanitized(row["model_input"], "overlay_model_input")
        assert_sanitized(row["target_text"], "overlay_target_text")
        hardened_examples.append(row)

    duplicate_hashes, duplicate_audit = cross_split_duplicate_hashes(hardened_examples)
    hardened_manifest: list[dict[str, Any]] = []
    example_by_old_id = {row["example_id"].replace("stage12656_hardened_", "stage12649_training_"): row for row in hardened_examples}
    for original in inputs["manifest"]:
        example = example_by_old_id.get(original["source_example_id"])
        if example is None:
            raise Stage12656ShortcutResilienceError("manifest_source_example_join_missing")
        row = dict(original)
        row["record_type"] = "stage12656_private_shortcut_resilient_curriculum_ingest_row_v1"
        row["ingest_row_id"] = row["ingest_row_id"].replace("stage12651_ingest_", "stage12656_shortcut_resilient_ingest_")
        row["source_example_id"] = example["example_id"]
        row["source_example_sha256"] = stable_hash(example)
        row["shortcut_resilience_overlay_materialized"] = True
        row["symbol_input_enriched_with_nonleaky_structure"] = example["symbol_input_enriched_with_nonleaky_structure"]
        row["shortcut_signature_cross_split_duplicate"] = row["source_row_sha256"] in duplicate_hashes
        if row["shortcut_signature_cross_split_duplicate"]:
            row["trainer_consumable"] = False
            row["loss_weight"] = 0.0
            row["quarantine_reason"] = "stage12656_enriched_symbol_signature_still_cross_split_duplicate"
        elif row.get("training_objective") == "source_backed_symbol_binding_ce":
            row["trainer_consumable"] = True
            row["loss_weight"] = 0.75
            row["quarantine_reason"] = None
        else:
            row["trainer_consumable"] = True
            row["loss_weight"] = 1.0
            row["quarantine_reason"] = None
        row["training_allowed"] = False
        row["optimizer_step_authorized"] = False
        assert_sanitized(row, "overlay_manifest")
        hardened_manifest.append(row)

    audit = {
        **duplicate_audit,
        "shortcut_quarantined_rows": sum(1 for row in hardened_manifest if row["shortcut_signature_cross_split_duplicate"]),
        "shortcut_quarantined_symbol_rows": sum(
            1
            for row in hardened_manifest
            if row["shortcut_signature_cross_split_duplicate"] and row["training_objective"] == "source_backed_symbol_binding_ce"
        ),
        "symbol_rows_enriched": sum(1 for row in hardened_examples if row["symbol_input_enriched_with_nonleaky_structure"]),
        "trainer_consumable_rows_after_hardening": sum(1 for row in hardened_manifest if row["trainer_consumable"]),
        "zero_weight_rows_after_hardening": sum(1 for row in hardened_manifest if row["loss_weight"] == 0.0),
        "objective_counts": counts(hardened_manifest, "training_objective"),
        "split_counts": counts(hardened_manifest, "split"),
        "lane_counts": counts(hardened_manifest, "curriculum_lane"),
        "trainer_consumable_split_counts": dict(
            sorted(collections.Counter(row["split"] for row in hardened_manifest if row["trainer_consumable"]).items())
        ),
    }
    if audit["shortcut_quarantined_rows"] != audit["cross_split_duplicate_signature_rows"]:
        raise Stage12656ShortcutResilienceError("shortcut_quarantine_count_mismatch")
    if audit["symbol_rows_enriched"] != 80:
        raise Stage12656ShortcutResilienceError("symbol_enrichment_count_drift")
    if audit["objective_counts"] != EXPECTED_COUNTS or audit["split_counts"] != EXPECTED_SPLITS or audit["lane_counts"] != EXPECTED_LANES:
        raise Stage12656ShortcutResilienceError("overlay_count_drift")
    return hardened_examples, hardened_manifest, audit


def build_packet() -> dict[str, Any]:
    inputs = load_inputs()
    hardened_examples, hardened_manifest, audit = materialize_overlay(inputs)
    packet = {
        "record_type": "stage12656_private_symbol_binding_shortcut_resilience_packet_v1",
        "stage": STAGE,
        "source_stage": "stage12655_repo_code_optimizer_context_trainer_binding_preflight_only",
        "review_scope": "repo_code_symbol_binding_shortcut_resilience_only",
        "nonleaky_enrichment_fields": [
            "graph/query kind",
            "node/edge counts",
            "node/edge type counts",
            "repo language family",
            "file feature buckets",
            "query shape feature values",
            "retrieval control booleans",
            "retrieval recall buckets",
        ],
        "avoided_fields": [
            "source_lineage",
            "source_row_id",
            "source_ref",
            "old_source_ref_path",
            "semantic_key",
            "row_id",
            "graph_id",
            "query_node_id",
            "target clean_state in input",
        ],
        "hardened_training_examples_sha256": sha256_bytes(
            b"".join(
                json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii") + b"\n"
                for row in hardened_examples
            )
        ),
        "hardened_ingest_manifest_sha256": sha256_bytes(
            b"".join(
                json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii") + b"\n"
                for row in hardened_manifest
            )
        ),
        **audit,
        **false_fields(),
        "training_pack_authorization_reviewed": False,
        "shortcut_resilience_overlay_materialized": True,
        "repo_code_curriculum_layer_complete": True,
        "repo_code_knowledge_stage_complete": True,
        "decision": "SYMBOL_BINDING_SHORTCUT_RESILIENCE_OVERLAY_MATERIALIZED_NO_TRAINING",
        "next_required_action": "stage12657_repo_code_shortcut_resilience_overlay_independent_review_only",
    }
    check_false(packet, "packet")
    return {"packet": packet, "examples": hardened_examples, "manifest": hardened_manifest}


def build() -> dict[str, Any]:
    built = build_packet()
    packet = built["packet"]
    private = OUT / "private"
    write_jsonl(private / "shortcut_resilient_repo_code_training_examples.jsonl", built["examples"])
    write_jsonl(private / "shortcut_resilient_repo_code_curriculum_ingest_manifest.jsonl", built["manifest"])
    write_json(private / "symbol_binding_shortcut_resilience_packet.json", packet)
    public_summary = {
        key: value
        for key, value in packet.items()
        if key
        not in {
            "hardened_training_examples_sha256",
            "hardened_ingest_manifest_sha256",
            "nonleaky_enrichment_fields",
            "avoided_fields",
        }
    }
    assert_sanitized(public_summary, "public_summary", PUBLIC_FORBIDDEN_SUBSTRINGS)
    contract = {
        "record_type": "stage12656_public_symbol_binding_shortcut_resilience_contract_v1",
        "stage": STAGE,
        "requires_nonleaky_symbol_input_enrichment": True,
        "requires_cross_split_duplicate_signature_quarantine": True,
        "requires_training_closed": True,
        "private_packet_sha256": stable_hash(packet),
        **false_fields(),
    }
    pointer = {
        "record_type": "stage12656_public_symbol_binding_shortcut_resilience_digest_pointer_v1",
        "stage": STAGE,
        "summary_sha256": stable_hash(public_summary),
        "contract_sha256": stable_hash(contract),
        "private_packet_sha256": stable_hash(packet),
        **false_fields(),
    }
    for label, record in (("contract", contract), ("pointer", pointer)):
        check_false(record, label)
        assert_sanitized(record, label, PUBLIC_FORBIDDEN_SUBSTRINGS)
    write_json(OUT / "contract.json", contract)
    write_json(OUT / "digest_pointer.json", pointer)
    write_json(OUT / "summary.json", public_summary)
    write_json(SUMMARY, public_summary)
    fsync_dir(private)
    fsync_dir(OUT)
    fsync_dir(SUMMARY.parent)
    return public_summary


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True))
