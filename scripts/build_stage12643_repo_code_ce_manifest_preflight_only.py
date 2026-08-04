#!/usr/bin/env python3
# Build a private repo/code CE candidate manifest preflight without admitting training rows.
from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12643_repo_code_ce_manifest_preflight_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12642 = ROOT / "runs/summaries/stage12642_repo_code_knowledge_completion_audit_only.json"
S8601_DIR = ROOT / "runs/local/artifacts/stage8601_arxiv_repo_capability_and_graph_seed"
CATALOG = S8601_DIR / "repo_capability_catalog.jsonl"
GRAPH = S8601_DIR / "repo_state_graph_seed.jsonl"
S8601_AUDIT = S8601_DIR / "audit_card.json"
S8601_AUTHORITY = S8601_DIR / "authority_card.json"

FALSE_FIELDS = (
    "repo_code_knowledge_stage_complete",
    "repo_code_ce_manifest_materialized",
    "repo_code_rows_admitted",
    "dataset_rows_admitted",
    "new_rows_admitted",
    "training_admission_allowed",
    "training_allowed",
    "training_run_allowed",
    "training_admitted",
    "strict_eval_admitted",
    "sealed_eval_admitted",
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
)

PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/",
    "/arxiv/",
    "row_id",
    "source_ref",
    "jsonl",
    "raw_stream",
    "stdout.raw",
    "stderr.raw",
    "production_path",
    "patch_path",
    "repository_root",
)

ROW_FORBIDDEN_SUBSTRINGS = (
    "/data/",
    "/arxiv/",
    "\\",
    "\x00",
    "Answer:",
    "PLACEHOLDER",
    "placeholder",
    "TODO",
    "TBD",
    "<fill",
)

REQUIRED_ROW_FIELDS = (
    "row_id",
    "record_type",
    "schema_version",
    "split",
    "objective_family",
    "source_lineage",
    "input",
    "target",
    "loss_mask",
    "authority",
    "anti_cheat",
    "admission",
)

ALLOWED_SPLITS = {"train", "eval", "strict_eval"}
NO_AUTHORITY = {
    "training_authorized": False,
    "decoder_ce_authorized": False,
    "runtime_authorized": False,
    "scoring_authorized": False,
    "harness_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_authorized": False,
}
NO_LOSS = {
    "repo_code_ce_candidate": False,
    "decoder_ce": False,
    "denoise_ce": False,
    "runtime_reward": False,
    "structured_aux": False,
}


class RepoCodeCeManifestPreflightError(RuntimeError):
    pass


def stable_hash(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RepoCodeCeManifestPreflightError("json_object_required:" + path.name)
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise RepoCodeCeManifestPreflightError(f"jsonl_object_required:{path.name}:{line_number}")
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
            data = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
            stream.write(data + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def fsync_dir(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def no_claim_fields() -> dict[str, Any]:
    return {field: False for field in FALSE_FIELDS}


def check_false(record: Mapping[str, Any], label: str) -> None:
    for field in FALSE_FIELDS:
        if field in record and record[field] is not False:
            raise RepoCodeCeManifestPreflightError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise RepoCodeCeManifestPreflightError(f"{label}_public_leak:{needle}")


def assert_row_sanitized(row: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(row, sort_keys=True, ensure_ascii=True)
    for needle in ROW_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise RepoCodeCeManifestPreflightError(f"{label}_row_leak_or_placeholder:{needle}")


def ordered_counts(values: Iterable[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def count_node_types(nodes: list[Mapping[str, Any]]) -> dict[str, int]:
    return ordered_counts(str(node.get("node_type")) for node in nodes)


def count_edge_types(edges: list[Mapping[str, Any]]) -> dict[str, int]:
    return ordered_counts(str(edge.get("edge_type")) for edge in edges)


def iter_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from iter_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_strings(item)


def target_label_values(row: Mapping[str, Any]) -> set[str]:
    target = row.get("target") or {}
    labels: set[str] = set()
    for key in ("repo_capability_profile", "curriculum_uses", "recommended_next_objectives"):
        for item in target.get(key) or []:
            if isinstance(item, str) and len(item) >= 3:
                labels.add(item.lower())
    return labels


def has_target_label_in_value(labels: set[str], value: Any) -> bool:
    if not labels:
        return False
    for text in iter_strings(value):
        lowered = text.lower()
        if any(label in lowered for label in labels):
            return True
    return False


def repo_path_in_input(row: Mapping[str, Any]) -> bool:
    encoded = json.dumps(row.get("input") or {}, sort_keys=True, ensure_ascii=True)
    return any(needle in encoded for needle in ("/arxiv/", "/data/", "repositories/")) or "path" in encoded.lower()


def raw_source_included(row: Mapping[str, Any]) -> bool:
    anti_cheat = row.get("anti_cheat") or {}
    if anti_cheat.get("raw_source_included") is True:
        return True
    encoded = json.dumps(row, sort_keys=True, ensure_ascii=True).lower()
    if any(needle in encoded for needle in ("/arxiv/", "/data/", "source_ref", "source_body", "raw_body")):
        return True
    if "raw_source" in encoded and "raw_source_included" not in encoded:
        return True
    return False


def split_repo_overlap(candidates: list[dict[str, Any]]) -> int:
    seen: dict[str, set[str]] = {}
    for row in candidates:
        repo_id = str((row.get("input") or {}).get("opaque_repo_id") or "")
        split = str(row.get("split"))
        seen.setdefault(repo_id, set()).add(split)
    return sum(1 for splits in seen.values() if len(splits) > 1)


def compute_shortcut_audit(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    target_label_in_id_rows = 0
    repo_path_in_model_input_rows = 0
    raw_source_included_rows = 0
    objective_label_in_graph_id_rows = 0
    opaque_ids_only_rows = 0
    for row in candidates:
        labels = target_label_values(row)
        row_id = str(row.get("row_id") or "")
        if has_target_label_in_value(labels, row_id):
            target_label_in_id_rows += 1
        if repo_path_in_input(row):
            repo_path_in_model_input_rows += 1
        if raw_source_included(row):
            raw_source_included_rows += 1
        graph_shape = ((row.get("input") or {}).get("graph_shape") or {})
        if has_target_label_in_value(labels, graph_shape):
            objective_label_in_graph_id_rows += 1
        opaque_repo_id = str((row.get("input") or {}).get("opaque_repo_id") or "")
        if opaque_repo_id.startswith("repo_") and not repo_path_in_input(row):
            opaque_ids_only_rows += 1
    local_screen_passed = (
        target_label_in_id_rows == 0
        and repo_path_in_model_input_rows == 0
        and raw_source_included_rows == 0
        and objective_label_in_graph_id_rows == 0
        and opaque_ids_only_rows == len(candidates)
    )
    return {
        "target_label_in_id_rows": target_label_in_id_rows,
        "repo_path_in_model_input_rows": repo_path_in_model_input_rows,
        "raw_source_included_rows": raw_source_included_rows,
        "objective_label_in_graph_id_rows": objective_label_in_graph_id_rows,
        "opaque_ids_only_rows": opaque_ids_only_rows,
        "local_manifest_shortcut_screen_passed": local_screen_passed,
        "global_shortcut_preflight_passed": False,
        "stage8675_shortcut_issue_resolved": False,
        "stage8675_shortcut_issue_quarantined": False,
    }


def assert_source_row_safe(catalog: Mapping[str, Any], graph: Mapping[str, Any], index: int) -> None:
    if catalog.get("split") != graph.get("split"):
        raise RepoCodeCeManifestPreflightError(f"split_mismatch:{index}")
    split = catalog.get("split")
    if split not in ALLOWED_SPLITS:
        raise RepoCodeCeManifestPreflightError(f"invalid_split:{index}:{split}")

    catalog_input = catalog.get("model_input")
    graph_input = graph.get("graph_input")
    if not isinstance(catalog_input, dict) or not isinstance(graph_input, dict):
        raise RepoCodeCeManifestPreflightError(f"input_object_required:{index}")
    if catalog_input.get("opaque_repo_id") is None:
        raise RepoCodeCeManifestPreflightError(f"opaque_repo_id_required:{index}")
    graph_repo = None
    for node in graph_input.get("nodes") or []:
        features = node.get("features") or {}
        if node.get("node_type") == "repo":
            graph_repo = features.get("opaque_repo_id")
            break
    if graph_repo != catalog_input.get("opaque_repo_id"):
        raise RepoCodeCeManifestPreflightError(f"opaque_repo_id_mismatch:{index}")

    for source, label in ((catalog, "catalog"), (graph, "graph")):
        authority = source.get("authority") or {}
        for key, expected in NO_AUTHORITY.items():
            if authority.get(key) is not expected:
                raise RepoCodeCeManifestPreflightError(f"{label}_authority_drift:{index}:{key}")
        loss_mask = source.get("loss_mask") or {}
        for key in ("decoder_ce", "denoise_ce", "runtime_reward", "structured_aux"):
            if loss_mask.get(key) is not False:
                raise RepoCodeCeManifestPreflightError(f"{label}_loss_mask_drift:{index}:{key}")

    catalog_anti = catalog.get("anti_cheat") or {}
    graph_anti = graph.get("anti_cheat") or {}
    if catalog_anti.get("raw_source_included") is not False:
        raise RepoCodeCeManifestPreflightError(f"catalog_raw_source_included:{index}")
    if catalog_anti.get("repo_path_in_model_input") is not False:
        raise RepoCodeCeManifestPreflightError(f"catalog_repo_path_in_model_input:{index}")
    if catalog_anti.get("target_label_in_id") is not False:
        raise RepoCodeCeManifestPreflightError(f"catalog_target_label_in_id:{index}")
    if catalog_anti.get("requires_shortcut_audit_before_training") is not True:
        raise RepoCodeCeManifestPreflightError(f"catalog_shortcut_audit_flag_missing:{index}")
    if graph_anti.get("raw_source_included") is not False:
        raise RepoCodeCeManifestPreflightError(f"graph_raw_source_included:{index}")
    if graph_anti.get("opaque_graph_ids") is not True:
        raise RepoCodeCeManifestPreflightError(f"graph_opaque_ids_missing:{index}")
    if graph_anti.get("objective_label_in_graph_id") is not False:
        raise RepoCodeCeManifestPreflightError(f"graph_objective_label_in_graph_id:{index}")
    if graph_anti.get("requires_endpoint_audit") is not True:
        raise RepoCodeCeManifestPreflightError(f"graph_endpoint_audit_flag_missing:{index}")

    assert_row_sanitized({"catalog_input": catalog_input, "graph_input": graph_input}, f"source_input:{index}")


def compact_target_text(catalog_target: Mapping[str, Any], graph_target: Mapping[str, Any], model_input: Mapping[str, Any]) -> str:
    languages = ",".join(model_input.get("language_families") or [])
    build_systems = ",".join(model_input.get("build_system_families") or [])
    profile = ",".join(catalog_target.get("repo_capability_profile") or [])
    next_objectives = ",".join(graph_target.get("recommended_next_objectives") or [])
    curriculum = ",".join(catalog_target.get("curriculum_uses") or [])
    return (
        "repo_code_knowledge "
        f"languages={languages}; "
        f"build_systems={build_systems}; "
        f"tests={model_input.get('test_coverage_bucket')}; "
        f"repo_size={model_input.get('repo_size_bucket')}; "
        f"docs={bool(model_input.get('has_docs'))}; "
        f"profile={profile}; "
        f"curriculum={curriculum}; "
        f"next_objectives={next_objectives}"
    )


def make_candidate(catalog: Mapping[str, Any], graph: Mapping[str, Any], index: int) -> dict[str, Any]:
    assert_source_row_safe(catalog, graph, index)
    model_input = catalog["model_input"]
    graph_input = graph["graph_input"]
    nodes = graph_input.get("nodes") or []
    edges = graph_input.get("edges") or []
    target = {
        "compact_maintenance_text": compact_target_text(catalog.get("target") or {}, graph.get("target") or {}, model_input),
        "repo_capability_profile": sorted(catalog.get("target", {}).get("repo_capability_profile") or []),
        "curriculum_uses": sorted(catalog.get("target", {}).get("curriculum_uses") or []),
        "recommended_next_objectives": sorted(graph.get("target", {}).get("recommended_next_objectives") or []),
    }
    row = {
        "record_type": "stage12643_private_repo_code_ce_candidate_manifest_row_v1",
        "schema_version": 1,
        "row_id": f"stage12643_repo_code_ce_candidate_{index:06d}",
        "split": catalog["split"],
        "objective_family": "repo_code_ce_manifest_preflight",
        "source_lineage": {
            "stage8601_catalog_row_sha256": stable_hash(catalog),
            "stage8601_graph_seed_row_sha256": stable_hash(graph),
            "source_repo_id_sha256": hashlib.sha256(str((catalog.get("source_ref") or {}).get("repo_id", "")).encode("utf-8")).hexdigest(),
        },
        "input": {
            "opaque_repo_id": model_input["opaque_repo_id"],
            "language_families": sorted(model_input.get("language_families") or []),
            "build_system_families": sorted(model_input.get("build_system_families") or []),
            "has_docs": bool(model_input.get("has_docs")),
            "has_tests": bool(model_input.get("has_tests")),
            "repo_size_bucket": model_input.get("repo_size_bucket"),
            "scan_truncated": bool(model_input.get("scan_truncated")),
            "test_coverage_bucket": model_input.get("test_coverage_bucket"),
            "graph_shape": {
                "node_count": len(nodes),
                "edge_count": len(edges),
                "node_type_counts": count_node_types(nodes),
                "edge_type_counts": count_edge_types(edges),
            },
        },
        "target": target,
        "loss_mask": dict(NO_LOSS),
        "authority": dict(NO_AUTHORITY),
        "anti_cheat": {
            "raw_source_included": False,
            "repo_path_in_model_input": False,
            "target_label_in_id": False,
            "objective_label_in_graph_id": False,
            "opaque_ids_only": True,
            "requires_shortcut_audit_before_training": True,
            "requires_independent_review_before_admission": True,
        },
        "admission": {
            "candidate_only": True,
            "schema_preflight_passed": True,
            "heldout_preflight_passed": True,
            "local_manifest_shortcut_screen_passed": True,
            "global_shortcut_preflight_passed": False,
            "admitted": False,
            "training_allowed": False,
            "admission_blockers": [
                "independent_stage12644_review_required",
                "stage8675_symbol_binding_shortcut_issue_unresolved_or_unquarantined",
                "repo_code_metrics_not_run",
                "separate_training_admission_not_performed",
            ],
        },
    }
    assert_row_sanitized(row, f"candidate:{index}")
    return row


def build_candidates(catalog_rows: list[dict[str, Any]], graph_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(catalog_rows) != len(graph_rows):
        raise RepoCodeCeManifestPreflightError("catalog_graph_row_count_mismatch")
    return [make_candidate(catalog, graph, index) for index, (catalog, graph) in enumerate(zip(catalog_rows, graph_rows))]


def audit_candidates(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    if not candidates:
        raise RepoCodeCeManifestPreflightError("no_candidates")
    schema_complete = 0
    no_placeholder = 0
    no_raw_path = 0
    authority_blocked = 0
    split_counts = ordered_counts(str(row.get("split")) for row in candidates)
    for row in candidates:
        if all(field in row for field in REQUIRED_ROW_FIELDS):
            schema_complete += 1
        encoded = json.dumps(row, sort_keys=True, ensure_ascii=True)
        if not any(needle in encoded for needle in ("Answer:", "PLACEHOLDER", "placeholder", "TODO", "TBD", "<fill")):
            no_placeholder += 1
        if "/arxiv/" not in encoded and "/data/" not in encoded:
            no_raw_path += 1
        if row.get("authority") == NO_AUTHORITY and row.get("loss_mask") == NO_LOSS:
            authority_blocked += 1
        if str(row.get("split")) not in ALLOWED_SPLITS:
            raise RepoCodeCeManifestPreflightError("candidate_invalid_split:" + str(row.get("row_id")))
        text = str((row.get("target") or {}).get("compact_maintenance_text") or "")
        if not text:
            raise RepoCodeCeManifestPreflightError("candidate_compact_target_text_missing")
    split_overlap_count = split_repo_overlap(candidates)
    heldout_preserved = (
        split_counts.get("eval", 0) > 0
        and split_counts.get("strict_eval", 0) > 0
        and split_counts.get("train", 0) > 0
        and split_overlap_count == 0
    )
    shortcut_audit = compute_shortcut_audit(candidates)
    return {
        "record_type": "stage12643_repo_code_ce_manifest_preflight_audit_v1",
        "candidate_rows": len(candidates),
        "schema_complete_candidate_rows": schema_complete,
        "no_placeholder_candidate_rows": no_placeholder,
        "no_raw_path_candidate_rows": no_raw_path,
        "authority_blocked_candidate_rows": authority_blocked,
        "split_counts": split_counts,
        "heldout_preserved": heldout_preserved,
        "heldout_splits": ["eval", "strict_eval"],
        "cross_split_duplicate_opaque_repo_ids": split_overlap_count,
        "shortcut_audit": shortcut_audit,
        "model_ready_training_rows": 0,
        "repo_code_ce_training_rows_admitted": 0,
        "training_allowed": False,
        "dataset_rows_admitted": False,
        "independent_review_required_next": True,
    }


def load_inputs() -> dict[str, Any]:
    return {
        "stage12642": read_json(STAGE12642),
        "stage8601_audit": read_json(S8601_AUDIT),
        "stage8601_authority": read_json(S8601_AUTHORITY),
        "catalog_rows": read_jsonl(CATALOG),
        "graph_rows": read_jsonl(GRAPH),
    }


def build_packet(inputs: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    stage12642 = inputs["stage12642"]
    s8601_audit = inputs["stage8601_audit"]
    s8601_authority = inputs["stage8601_authority"]
    catalog_rows = inputs["catalog_rows"]
    graph_rows = inputs["graph_rows"]

    if stage12642.get("repo_code_knowledge_substrate_recovered") is not True:
        raise RepoCodeCeManifestPreflightError("stage12642_substrate_not_recovered")
    if stage12642.get("repo_code_knowledge_stage_complete") is not False:
        raise RepoCodeCeManifestPreflightError("stage12642_completion_drift")
    if stage12642.get("training_allowed") is not False or stage12642.get("dataset_rows_admitted") is not False:
        raise RepoCodeCeManifestPreflightError("stage12642_training_authority_drift")
    if s8601_audit.get("catalog_rows") != 200 or s8601_audit.get("graph_seed_rows") != 200:
        raise RepoCodeCeManifestPreflightError("stage8601_row_count_drift")
    if s8601_authority.get("passed") is not True or s8601_authority.get("decoder_ce_training_authorized_next") is not False:
        raise RepoCodeCeManifestPreflightError("stage8601_authority_drift")

    candidates = build_candidates(catalog_rows, graph_rows)
    audit = audit_candidates(candidates)
    if audit["split_counts"] != dict(sorted((s8601_audit.get("split_counts") or {}).items())):
        raise RepoCodeCeManifestPreflightError("split_counts_not_preserved")
    if audit["candidate_rows"] != s8601_audit.get("catalog_rows"):
        raise RepoCodeCeManifestPreflightError("candidate_count_mismatch")
    if audit["schema_complete_candidate_rows"] != audit["candidate_rows"]:
        raise RepoCodeCeManifestPreflightError("schema_incomplete_candidates")
    if audit["no_placeholder_candidate_rows"] != audit["candidate_rows"]:
        raise RepoCodeCeManifestPreflightError("placeholder_candidates")
    if audit["no_raw_path_candidate_rows"] != audit["candidate_rows"]:
        raise RepoCodeCeManifestPreflightError("raw_path_candidates")
    if audit["authority_blocked_candidate_rows"] != audit["candidate_rows"]:
        raise RepoCodeCeManifestPreflightError("authority_unblocked_candidates")
    if audit["heldout_preserved"] is not True:
        raise RepoCodeCeManifestPreflightError("heldout_not_preserved")
    if audit["cross_split_duplicate_opaque_repo_ids"] != 0:
        raise RepoCodeCeManifestPreflightError("heldout_repo_overlap")
    if audit["shortcut_audit"]["local_manifest_shortcut_screen_passed"] is not True:
        raise RepoCodeCeManifestPreflightError("local_shortcut_screen_failed")
    if audit["shortcut_audit"]["global_shortcut_preflight_passed"] is not False:
        raise RepoCodeCeManifestPreflightError("global_shortcut_gate_drift")

    source_hashes = {
        "stage12642_summary": stable_hash(stage12642),
        "stage8601_audit_card": stable_hash(s8601_audit),
        "stage8601_authority_card": stable_hash(s8601_authority),
        "stage8601_catalog_bytes": file_sha256(CATALOG),
        "stage8601_graph_bytes": file_sha256(GRAPH),
    }
    manifest_sha256 = stable_hash(candidates)
    private = {
        "record_type": "stage12643_private_repo_code_ce_manifest_preflight_packet_v1",
        **no_claim_fields(),
        "repo_code_ce_candidate_manifest_materialized": True,
        "stage12643_repo_code_ce_manifest_preflight_performed": True,
        "repo_code_knowledge_substrate_recovered": True,
        "source_hashes": source_hashes,
        "candidate_manifest_sha256": manifest_sha256,
        "preflight_audit": audit,
        "decision": "REPO_CODE_CE_CANDIDATE_MANIFEST_BUILT_NOT_ADMITTED_NO_TRAINING",
    }
    contract = {
        "record_type": "stage12643_public_repo_code_ce_manifest_preflight_contract_v1",
        **no_claim_fields(),
        "repo_code_ce_candidate_manifest_materialized": True,
        "stage12643_repo_code_ce_manifest_preflight_performed": True,
        "repo_code_knowledge_substrate_recovered": True,
        "source_hashes": source_hashes,
        "candidate_manifest_sha256": manifest_sha256,
        "private_packet_sha256": stable_hash(private),
        "preflight_audit_sha256": stable_hash(audit),
        "candidate_rows": audit["candidate_rows"],
        "schema_complete_candidate_rows": audit["schema_complete_candidate_rows"],
        "heldout_preserved": audit["heldout_preserved"],
        "split_counts": audit["split_counts"],
        "shortcut_audit": audit["shortcut_audit"],
        "claim_boundary": {
            "candidate_manifest": "private_preflight_only",
            "row_admission": "not_performed",
            "training": "not_authorized",
            "decoder_ce": "not_authorized",
            "repo_code_stage": "not_complete",
            "stage8675": "shortcut_issue_still_blocks_admission_until_repaired_or_quarantined",
        },
    }
    summary = {
        "record_type": "stage12643_public_repo_code_ce_manifest_preflight_summary_v1",
        **no_claim_fields(),
        "stage": STAGE,
        "repo_code_ce_candidate_manifest_materialized": True,
        "stage12643_repo_code_ce_manifest_preflight_performed": True,
        "repo_code_knowledge_substrate_recovered": True,
        "decision": "REPO_CODE_CE_CANDIDATE_MANIFEST_BUILT_NOT_ADMITTED_NO_TRAINING",
        "candidate_manifest_sha256": manifest_sha256,
        "private_packet_sha256": stable_hash(private),
        "preflight_audit_sha256": stable_hash(audit),
        "candidate_rows": audit["candidate_rows"],
        "schema_complete_candidate_rows": audit["schema_complete_candidate_rows"],
        "no_placeholder_candidate_rows": audit["no_placeholder_candidate_rows"],
        "no_raw_path_candidate_rows": audit["no_raw_path_candidate_rows"],
        "authority_blocked_candidate_rows": audit["authority_blocked_candidate_rows"],
        "split_counts": audit["split_counts"],
        "heldout_preserved": audit["heldout_preserved"],
        "model_ready_training_rows": 0,
        "repo_code_ce_training_rows_admitted": 0,
        "stage8675_shortcut_issue_resolved": False,
        "stage8675_shortcut_issue_quarantined": False,
        "independent_review_required_next": True,
        "next_required_action": "stage12644_independent_repo_code_ce_manifest_preflight_review_or_stage8675_shortcut_quarantine",
    }
    for label, record in (("summary", summary), ("contract", contract)):
        check_false(record, "stage12643_" + label)
        assert_public_sanitized(record, "stage12643_" + label)
    check_false(private, "stage12643_private")
    return summary, contract, private, candidates


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    inputs = load_inputs()
    summary, contract, private, candidates = build_packet(inputs)
    pointer = {
        "record_type": "stage12643_public_repo_code_ce_manifest_preflight_pointer_v1",
        **no_claim_fields(),
        "repo_code_ce_candidate_manifest_materialized": True,
        "stage12643_repo_code_ce_manifest_preflight_performed": True,
        "repo_code_knowledge_substrate_recovered": True,
        "contract_sha256": stable_hash(contract),
        "private_packet_sha256": stable_hash(private),
        "candidate_manifest_sha256": stable_hash(candidates),
        "preflight_audit_sha256": stable_hash(private["preflight_audit"]),
    }
    check_false(pointer, "stage12643_pointer")
    assert_public_sanitized(pointer, "stage12643_pointer")
    write_jsonl(out / "private/repo_code_ce_candidate_manifest.jsonl", candidates)
    write_json(out / "private/repo_code_ce_manifest_preflight_packet.json", private)
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    fsync_dir(out / "private")
    fsync_dir(out)
    fsync_dir(summary_path.parent)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
