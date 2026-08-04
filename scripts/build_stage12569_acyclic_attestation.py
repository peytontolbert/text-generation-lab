#!/usr/bin/env python3
"""Emit an acyclic, deny-only successor to the frozen Stage12562/64 artifacts."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from collections import deque
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12569_acyclic_attestation"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
SOURCES = {
    "sealed": ROOT / "runs/local/artifacts/stage12105_sealed_transition_candidate_atlas/sealed_transition_candidate_rows.jsonl",
    "locked": ROOT / "runs/local/artifacts/stage8672_locked_benchmark_pack_manifest/locked_benchmark_packs.jsonl",
    "protected": ROOT / "runs/local/artifacts/stage12554_authority_inventory_and_overlap_gate/protected_swe_bench_verified_manifest.json",
    "tasks": ROOT / "runs/local/artifacts/stage12555_swe_rebench_identity_adapter/exact_task_authority_bindings.jsonl",
    "ready": ROOT / "runs/local/artifacts/stage12556_local_checkout_readiness_census/checkout_object_ready.jsonl",
    "scope": ROOT / "runs/summaries/stage12561_active_protected_scope_gate.json",
    "commitment": ROOT / "runs/local/artifacts/stage12565_paired_pre_outcome_candidate_commitment_v2/paired_candidate_commitment_v2.json",
    "mapping": ROOT / "runs/local/artifacts/stage12568_open_swe_source_lineage_adapter/source_lineage_reference_adapter.json",
}
PINNED_BYTE_SHA256 = {
    "sealed": "dbaf3800b987bb8607c8cd2ddb0ddcbf2011e6be9b2f4c0a41847013b86dddd2",
    "locked": "a6cce0dabed78c240037a0ef7d06fb739e7dd9b835ca57686d49d66bff84a570",
    "protected": "50e52154348d471c0d6407e466b3bffce4a197fbe81cce6db122ef22c4bcb5c5",
    "tasks": "b423a417dc2f0a65c808a4edd2b3e4b7cdd8f90c0f3af8de8a92e8a5575bbeae",
    "ready": "ad7f205b0b757437c073ca88e014bdd0140083bbbeb5b93b6e088e1f55b91511",
    "scope": "b959eba3b87e32fc79731b7b9f0508ad0e189ba8db03bb9040b21cc3e03c73b5",
    "commitment": "f90d9a972f4e2029c97344f8ed17fa9d2f1ce8f143651901f7d21a4d3bd53e1a",
}
PINNED_MAPPING_SEMANTIC_SHA256 = "6f8562ddecfe20b50c7226d7fe96088b18f2a788c84d820fe68497d86a8adfae"
CANONICAL_SOURCE_ID = "src_53e6cea43bf6fbb6"
BASE_REGISTRY_SHA256 = "98b50df0083fea7be08ccf513b361e78669a2d1be03db7948a2f0a3a90bab807"
STAGE12554_SHA256 = "98a7f396868d2c7672129c71b7a0c7d62337ee389bdde8e0e37de153ef76dcbd"
SHARD_SHA256 = "5befb7356a4bce7c13bc5a8313fdd42df0488c567eeaf42a668dcf307642320e"
OPEN_SWE_REVISION = "f6689f56f1af2e2082861738071d4c4278b1922a"
AUTH_FIELDS = (
    "admission_allowed", "training_allowed", "replay_allowed", "gpu_allowed",
    "execution_authorized", "root_credit", "repair_credit", "level3_credit",
    "strict_eval_eligible",
)
ZERO = {name: False for name in AUTH_FIELDS}
JSONL_NAMES = {"sealed", "locked", "tasks", "ready"}

_SPEC = importlib.util.spec_from_file_location(
    "stage12565_for_stage12569",
    ROOT / "scripts/build_stage12565_paired_pre_outcome_candidate_commitment_v2.py",
)
if not _SPEC or not _SPEC.loader:
    raise ImportError("Stage12565 commitment verifier unavailable")
STAGE12565 = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(STAGE12565)


def stable_hash(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(data).hexdigest()


def _read_bound_inputs(paths: Mapping[str, Path]) -> tuple[dict[str, Any], dict[str, str], list[str]]:
    values: dict[str, Any] = {}
    hashes: dict[str, str] = {}
    blockers: list[str] = []
    if set(paths) != set(SOURCES):
        return values, hashes, ["declared_source_nodes_changed"]
    for name, path in paths.items():
        try:
            raw = path.read_bytes()
            hashes[name] = hashlib.sha256(raw).hexdigest()
            text = raw.decode("utf-8")
            if name in JSONL_NAMES:
                value = [json.loads(line) for line in text.splitlines() if line.strip()]
                if not all(isinstance(row, dict) for row in value):
                    raise ValueError("non-object JSONL row")
            else:
                value = json.loads(text)
                if not isinstance(value, dict):
                    raise ValueError("non-object JSON")
            values[name] = value
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
            blockers.append(f"{name}_source_missing_or_invalid")
    return values, hashes, blockers


def _authority_hashes(byte_hashes: Mapping[str, str]) -> dict[str, str | None]:
    return {
        "stage12554_resolved_trajectory_bindings": STAGE12554_SHA256,
        "stage12555_exact_authority_bindings": byte_hashes.get("tasks"),
        "stage12556_ready_rows": byte_hashes.get("ready"),
        "stage12565_paired_commitment": byte_hashes.get("commitment"),
    }


def mapping_projection(mapping: dict[str, Any]) -> dict[str, Any]:
    bindings = mapping.get("bindings") if isinstance(mapping.get("bindings"), list) else []
    projected = []
    for row in bindings:
        if not isinstance(row, dict):
            projected.append({"invalid_binding": True})
            continue
        projected.append({
            "candidate_id": row.get("candidate_id"),
            "source_ids": row.get("source_ids"),
            "source_known": row.get("source_known"),
            "evidence": row.get("evidence"),
            "provenance_refs": row.get("provenance_refs"),
            "authority_hashes": row.get("authority_hashes"),
            **{name: row.get(name) for name in AUTH_FIELDS},
        })
    projected.sort(key=lambda row: str(row.get("candidate_id") or ""))
    return {
        "mapping_schema": mapping.get("record_type"),
        "canonical_source_id": mapping.get("canonical_source_id"),
        "base_registry_sha256": mapping.get("base_registry_sha256"),
        "authority_hashes": mapping.get("authority_hashes"),
        "bindings": projected,
    }


def _mapping_blockers(
    mapping: dict[str, Any],
    candidate_ids: set[str],
    byte_hashes: Mapping[str, str],
) -> tuple[dict[str, Any], list[str]]:
    projection = mapping_projection(mapping)
    blockers: list[str] = []
    expected_authority = _authority_hashes(byte_hashes)
    expected_refs = [
        f"{name}:sha256:{digest}" for name, digest in sorted(expected_authority.items())
    ]
    if stable_hash(projection) != PINNED_MAPPING_SEMANTIC_SHA256:
        blockers.append("stage12568_mapping_projection_hash_mismatch")
    if (
        projection["mapping_schema"] != "stage12568_source_lineage_reference_adapter_v1"
        or projection["canonical_source_id"] != CANONICAL_SOURCE_ID
        or projection["base_registry_sha256"] != BASE_REGISTRY_SHA256
        or projection["authority_hashes"] != expected_authority
    ):
        blockers.append("stage12568_mapping_projection_header_invalid")
    bindings = projection["bindings"]
    ids = [str(row.get("candidate_id") or "") for row in bindings]
    if len(ids) != 8 or len(set(ids)) != 8 or set(ids) != candidate_ids:
        blockers.append("stage12568_mapping_candidate_set_changed")
    for row in bindings:
        evidence = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
        key = evidence.get("namespaced_trajectory_key")
        evidence_valid = (
            set(evidence) == {
                "namespaced_trajectory_key", "stage12554_row_sha256",
                "trajectory_shard_path", "trajectory_shard_sha256",
            }
            and isinstance(key, list) and len(key) == 7
            and key[0] == "nvidia/Open-SWE-Traces"
            and key[1] == OPEN_SWE_REVISION
            and key[2] == "openhands"
            and key[3] == "minimax_m25"
            and key[4] == "train-00000-of-00020.parquet"
            and isinstance(key[5], int) and not isinstance(key[5], bool) and key[5] >= 0
            and isinstance(key[6], str) and bool(key[6])
            and evidence.get("trajectory_shard_path") == "/arxiv/datasets/nvidia--Open-SWE-Traces/data/minimax_m25_openhands_trajectories/train-00000-of-00020.parquet"
            and evidence.get("trajectory_shard_sha256") == SHARD_SHA256
            and isinstance(evidence.get("stage12554_row_sha256"), str)
            and len(evidence["stage12554_row_sha256"]) == 64
        )
        if not (
            row.get("source_ids") == [CANONICAL_SOURCE_ID]
            and row.get("source_known") is True
            and row.get("authority_hashes") == expected_authority
            and row.get("provenance_refs") == expected_refs
            and evidence_valid
            and all(row.get(name) is False for name in AUTH_FIELDS)
        ):
            blockers.append("stage12568_mapping_binding_invalid")
    return projection, sorted(set(blockers))


def _candidate_projection(
    ready: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    commitment: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    blockers = [f"stage12565_{reason}" for reason in STAGE12565.verify_envelope(commitment)]
    atomic = commitment.get("atomic_records") if isinstance(commitment.get("atomic_records"), list) else []
    task_ids = [str(row.get("candidate_id") or "") for row in tasks]
    ready_ids = [str(row.get("candidate_id") or "") for row in ready]
    atomic_ids = [str(row.get("candidate_id") or "") for row in atomic if isinstance(row, dict)]
    by_task = {str(row.get("candidate_id") or ""): row for row in tasks}
    by_atomic = {str(row.get("candidate_id") or ""): row for row in atomic if isinstance(row, dict)}
    if (
        len(ready_ids) != 8 or len(set(ready_ids)) != 8
        or len(atomic_ids) != 8 or len(set(atomic_ids)) != 8
        or set(ready_ids) != set(atomic_ids)
        or len(task_ids) != len(set(task_ids))
        or not set(ready_ids).issubset(task_ids)
    ):
        blockers.append("candidate_sets_changed_or_mismatched")
    projection = []
    for ready_row in ready:
        candidate_id = str(ready_row.get("candidate_id") or "")
        task = by_task.get(candidate_id)
        committed = by_atomic.get(candidate_id)
        if task is None or committed is None:
            blockers.append("candidate_atomic_pair_missing")
            continue
        identity = task.get("task_identity") if isinstance(task.get("task_identity"), dict) else {}
        item = {
            "candidate_id": candidate_id,
            "task_key": ready_row.get("task_key"),
            "canonical_repo": identity.get("canonical_repo"),
            "base_commit": identity.get("base_commit"),
            "instance_id": identity.get("instance_id"),
            "ready_row_sha256": STAGE12565.stable_hash(STAGE12565.ready_row_projection(ready_row)),
            "task_row_sha256": STAGE12565.stable_hash(STAGE12565.authority_row_projection(task)),
        }
        expected_rows = {
            "stage12555_exact_authority_binding": item["task_row_sha256"],
            "stage12556_ready_row": item["ready_row_sha256"],
        }
        if not (
            ready_row.get("task_key") == task.get("task_key") == committed.get("task_key")
            and task.get("policy_split") == committed.get("policy_split") == "train"
            and task.get("protected_from_training") is False
            and committed.get("canonical_repo") == item["canonical_repo"]
            and committed.get("base_commit") == item["base_commit"]
            and committed.get("instance_id") == item["instance_id"]
            and committed.get("source_row_sha256") == expected_rows
        ):
            blockers.append("candidate_atomic_pair_binding_changed")
        projection.append(item)
    return sorted(projection, key=lambda row: row["candidate_id"]), sorted(set(blockers))


def analyze_graph(
    nodes: Sequence[dict[str, str]],
    edges: Sequence[Sequence[str]],
) -> dict[str, Any]:
    names = [str(node.get("id") or "") for node in nodes]
    invalid = any(not name for name in names) or len(names) != len(set(names))
    adjacency = {name: [] for name in names}
    indegree = {name: 0 for name in names}
    for edge in edges:
        if len(edge) != 2 or edge[0] not in adjacency or edge[1] not in adjacency:
            invalid = True
            continue
        adjacency[edge[0]].append(edge[1])
        indegree[edge[1]] += 1
    queue = deque(sorted(name for name, degree in indegree.items() if degree == 0))
    order: list[str] = []
    while queue:
        current = queue.popleft()
        order.append(current)
        for child in sorted(adjacency[current]):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    cycle_nodes = sorted(name for name, degree in indegree.items() if degree > 0)
    stage12557_dependencies = sorted({
        str(node.get("path") or node.get("id") or "")
        for node in nodes
        if str(node.get("id") or "").lower().startswith("stage12557")
        or any(part.lower().startswith("stage12557") for part in Path(str(node.get("path") or "")).parts)
    })
    return {
        "valid": not invalid,
        "acyclic": not invalid and len(order) == len(names),
        "topological_order": order if not invalid and len(order) == len(names) else [],
        "cycle_nodes": cycle_nodes,
        "stage12557_dependencies": stage12557_dependencies,
        "stage12557_dependency_count": len(stage12557_dependencies),
    }


def _declared_graph(paths: Mapping[str, Path]) -> tuple[list[dict[str, str]], list[list[str]]]:
    nodes = [
        {"id": name, "kind": "source", "path": str(path)}
        for name, path in sorted(paths.items())
    ] + [
        {"id": "mapping_projection", "kind": "derived", "path": ""},
        {"id": "protected_candidate_precondition", "kind": "sink", "path": ""},
    ]
    edges = [
        ["mapping", "mapping_projection"],
        ["mapping_projection", "protected_candidate_precondition"],
    ]
    edges.extend([
        [name, "protected_candidate_precondition"]
        for name in sorted(paths)
        if name != "mapping"
    ])
    return nodes, edges


def _sealed_roots(rows: list[dict[str, Any]]) -> list[str]:
    return sorted({
        str(row.get("stage12105_root_key") or row.get("root_lineage_key") or row.get("root_id") or "")
        for row in rows
    } - {""})


def build(
    paths: Mapping[str, Path] = SOURCES,
    *,
    graph_nodes: Sequence[dict[str, str]] | None = None,
    graph_edges: Sequence[Sequence[str]] | None = None,
) -> dict[str, Any]:
    values, byte_hashes, blockers = _read_bound_inputs(paths)
    for name, expected in PINNED_BYTE_SHA256.items():
        if byte_hashes.get(name) != expected:
            blockers.append(f"{name}_byte_hash_stale")
    candidates, candidate_blockers = _candidate_projection(
        values.get("ready", []), values.get("tasks", []), values.get("commitment", {})
    )
    blockers.extend(candidate_blockers)
    mapping, mapping_blockers = _mapping_blockers(
        values.get("mapping", {}), {row["candidate_id"] for row in candidates}, byte_hashes
    )
    blockers.extend(mapping_blockers)

    nodes, edges = _declared_graph(paths)
    if graph_nodes is not None:
        nodes = list(graph_nodes)
    if graph_edges is not None:
        edges = [list(edge) for edge in graph_edges]
    graph = analyze_graph(nodes, edges)
    if not graph["valid"]:
        blockers.append("dependency_graph_invalid")
    if not graph["acyclic"]:
        blockers.append("dependency_cycle_detected")
    if graph["stage12557_dependency_count"]:
        blockers.append("stage12557_output_present_in_dependencies")

    roots = _sealed_roots(values.get("sealed", []))
    unresolved = [{
        "protected_root_key_sha256": stable_hash(["stage12105", root]),
        "resolution_status": "unresolved",
        "reason": "authoritative_repo_and_commit_provenance_missing",
    } for root in roots]
    if len(roots) != 25:
        blockers.append("protected_root_set_changed")
    if unresolved:
        blockers.append("protected_legacy_lineage_unresolved")
    scope = values.get("scope", {})
    scope_disjoint = (
        scope.get("diagnostic_active_scope_disjoint") is True
        and all(scope.get(name) == 0 for name in (
            "exact_task_overlap_count", "canonical_repo_overlap_count",
            "malformed_protected_identity_count", "invalid_ready_count",
            "duplicate_binding_id_count",
        ))
    )
    if not scope_disjoint:
        blockers.append("active_protected_disjointness_not_proven")
    blockers = sorted(set(blockers))

    contract_body = {
        "record_type": "stage12569_acyclic_phase_contract_v2",
        "frozen_deny_predecessors": ["stage12562", "stage12564"],
        "declared_nodes": nodes,
        "declared_edges": edges,
        "graph_analysis": graph,
        "single_use_grant_implemented": False,
        **ZERO,
    }
    contract = {**contract_body, "contract_sha256": stable_hash(contract_body)}
    precondition_body = {
        "record_type": "stage12569_protected_candidate_precondition_v2",
        "contract_sha256": contract["contract_sha256"],
        "source_byte_sha256": dict(sorted((name, digest) for name, digest in byte_hashes.items() if name != "mapping")),
        "mapping_projection": mapping,
        "mapping_projection_sha256": stable_hash(mapping),
        "candidate_count": len(candidates),
        "candidate_set_sha256": stable_hash(candidates),
        "candidate_projection": candidates,
        "protected_root_count": len(roots),
        "unresolved_protected_root_count": len(unresolved),
        "unresolved_protected_roots": unresolved,
        "scope_disjointness_diagnostic": scope_disjoint,
        "preconditions_clear": False,
        "deny_only": True,
        "blocking_reasons": blockers,
        **ZERO,
    }
    precondition = {
        **precondition_body,
        "precondition_sha256": stable_hash(precondition_body),
    }
    future = {
        "record_type": "stage12569_future_hook_and_authority_requirements_v2",
        "non_authorizing_unattested_requirements_only": True,
        "observed_code_or_test_hashes": {},
        "required": [
            "resolve_all_25_roots_with_authoritative_repo_commit_provenance",
            "future_external_stage12557_hook_code_and_test_attestation",
            "future_subsequent_execution_consumption_only",
        ],
        **ZERO,
    }
    summary_body = {
        "stage": STAGE,
        "record_type": "stage12569_acyclic_attestation_summary_v2",
        "phase_contract": contract,
        "successor_precondition": precondition,
        "future_requirements": future,
        "unresolved_protected_root_count": len(unresolved),
        "stage12557_dependency_count": graph["stage12557_dependency_count"],
        "preconditions_clear": False,
        "blocking_reasons": blockers,
        **ZERO,
    }
    return {**summary_body, "summary_sha256": stable_hash(summary_body)}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    result = build()
    for name, key in (
        ("acyclic_phase_contract.json", "phase_contract"),
        ("protected_candidate_precondition.json", "successor_precondition"),
        ("future_hook_and_authority_requirements.json", "future_requirements"),
        ("summary.json", None),
    ):
        write_json(OUT / name, result if key is None else result[key])
    write_json(SUMMARY, result)
    print(json.dumps({
        "blocking_reasons": result["blocking_reasons"],
        "execution_authorized": result["execution_authorized"],
        "preconditions_clear": result["preconditions_clear"],
        "stage12557_dependency_count": result["stage12557_dependency_count"],
        "unresolved_protected_root_count": result["unresolved_protected_root_count"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
