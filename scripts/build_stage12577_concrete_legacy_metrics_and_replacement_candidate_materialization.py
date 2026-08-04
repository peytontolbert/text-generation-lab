#!/usr/bin/env python3
"""Materialize pinned legacy metrics and provenance-only replacement candidates."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12577_concrete_legacy_metrics_and_replacement_candidate_materialization"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

SOURCES = {
    "stage12574": ROOT / "runs/local/artifacts/stage12574_guarded_eight_root_historical_lineage_acquisition_preflight/historical_lineage_acquisition_preflight.json",
    "stage12575": ROOT / "runs/local/artifacts/stage12575_provenance_only_protected_root_quarantine_proposal/provenance_only_protected_root_quarantine_proposal.json",
    "stage12564": ROOT / "runs/local/artifacts/stage12564_authoritative_protected_lineage_preflight/authoritative_protected_lineage_preflight.json",
    "stage12568": ROOT / "runs/local/artifacts/stage12568_open_swe_source_lineage_adapter/source_lineage_reference_adapter.json",
    "stage12568_rows": ROOT / "runs/local/artifacts/stage12568_open_swe_source_lineage_adapter/trajectory_source_bindings.jsonl",
    "stage12576": ROOT / "runs/local/artifacts/stage12576_legacy_metrics_and_sealed_replacement_readiness_atlas/legacy_metrics_and_sealed_replacement_readiness_atlas.json",
    "manifest": ROOT / "runs/local/artifacts/stage11897_transition_record_projection_rows/transition_projection_rows.jsonl",
    "gemma_summary": ROOT / "runs/local/artifacts/stage11926_transition_listwise_same_manifest_comparison/transition_listwise_same_manifest_comparison.json",
    "gemma_rows": ROOT / "runs/local/artifacts/stage11926_transition_listwise_same_manifest_comparison/transition_listwise_same_manifest_rows.jsonl",
    "route_summary": ROOT / "runs/summaries/stage12099_task_routed_candidate_selection_composite_audit.json",
    "historical_package": ROOT / "runs/local/artifacts/stage10706_rewritten_plus_reviewed_multilingual_training_package_honest_strict/rewritten_plus_reviewed_multilingual_training_package_honest_strict.json",
    "protected_rows": ROOT / "runs/local/artifacts/stage12105_sealed_transition_candidate_atlas/sealed_transition_candidate_rows.jsonl",
    "rust_inventory": ROOT / "runs/local/artifacts/stage10125_true_source_backed_rust_root_discovery_manifest/true_source_backed_rust_root_candidates.jsonl",
    "reserved12107": ROOT / "runs/local/artifacts/stage12107_fresh_sealed_transition_root_materializer/fresh_sealed_transition_materialization_work_items.jsonl",
    "reserved12118": ROOT / "runs/local/artifacts/stage12118_maintainer_400_pilot_checkout_probe_request/pilot_checkout_probe_targets.jsonl",
}

PINS = {
    "stage12574": "bc8b2e3d9cfb1b7563e46a3ab7020c2b9104d85a9a221132cf0609a11b59f25d",
    "stage12575": "da7d5618703822b75207a4759550e79e69b0c0ec27ed5dffbb09986130da931e",
    "stage12564": "c9e95cbab0eac344e8be5e595067114ef380730fb17baa627c1868451d99aede",
    "stage12568": "a83a025e54283e82018c3762554c14d5ed5c74767201f0d8f3a84a59f70b519b",
    "stage12568_rows": "dab856c947426dcc128acd7bb0c1731f98a6bd9d6ab5cd6eb7be8d8271150b0a",
    "stage12576": "031352edbaf018c8b249c8920e453bcb705ffe452d562d57adb0f9855e1c053a",
    "manifest": "7ce8c030d429d948d3805e836d9e6522bcd0320252cfcb27b59475d8c1cb64bc",
    "gemma_summary": "ca9db1db82450e3a4ae410c54223c39d54ec7602f03f3df6e1fe7bc1e804ded9",
    "gemma_rows": "f10d7042b09fd23267700265b9a41e270734d6920d6ea7ab6b195b52bc293e39",
    "route_summary": "bbc82111e2c55399aa7ed20638c6712d31f4cc94b1e915850788853edb499759",
    "historical_package": "ed98291c3e2a2a6919274004b16e5998f2eef23f4526ee5c8281b136683a7762",
    "protected_rows": "dbaf3800b987bb8607c8cd2ddb0ddcbf2011e6be9b2f4c0a41847013b86dddd2",
    "rust_inventory": "c3352662f562db6745af084485a4f0ba279fb3ffa90430e6f6d3c83f114daf6e",
    "reserved12107": "e2e900ad050f4f083a612afea29ebc88890f0fda4c3d59277ebcea05242abe02",
    "reserved12118": "2de3486ef058a8f27ca602a18b852d46ace194135db4aa4eef630f16363a9f45",
}

CANONICAL_ROOT_SET_SHA256 = "e85fc0827bfcd9e5819fbc862f060afe35617d00b2c67b77a7effbc811541deb"
PROMPT_SURFACE_SHA256 = "6c2f84152b355c8eeaa7b3552327de0199ad55b925a3ee080420db9bf33a00a2"
QUARANTINED_STRATA = {"rust": 4, "web_js_ts_html": 4}
TASK_STRATA = (
    "transition_candidate_selection", "transition_continue_or_stop",
    "transition_next_action", "transition_verifier_transition",
)
CANDIDATE_REPOS = {
    "LLaMA-Adapter": ROOT.parent / "repositories/LLaMA-Adapter",
    "candle": ROOT.parent / "repositories/candle",
    "perftree": ROOT.parent / "repositories/perftree",
    "tokenizers": ROOT.parent / "repositories/tokenizers",
}
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
DENY_FIELDS = (
    "authorization_allowed", "admission_allowed", "training_allowed",
    "evaluation_allowed", "replay_allowed", "gpu_allowed",
    "execution_authorized", "strict_eval_eligible", "root_credit",
    "repair_credit", "level3_credit", "protected_clearance", "use_clearance",
)
ZERO = {field: False for field in DENY_FIELDS}


def stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode()).hexdigest()


def file_sha256(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"expected object rows: {path}")
    return rows


def normalize_family(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower().replace("localgitsnapshot", ""))


def _git(repo: Path, *args: str, binary: bool = False) -> str | bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True,
    ).stdout
    return result if binary else result.decode().strip()


def observe_git(repo: Path, source_path: str) -> dict[str, str]:
    canonical_repo = str(_git(repo, "remote", "get-url", "origin"))
    commit_oid = str(_git(repo, "rev-parse", "HEAD^{commit}"))
    tree_oid = str(_git(repo, "rev-parse", "HEAD^{tree}"))
    listing = _git(repo, "ls-tree", "-z", commit_oid, "--", source_path, binary=True)
    if not listing:
        raise ValueError("source_path_missing_from_commit")
    entries = bytes(listing).rstrip(b"\0").split(b"\0")
    if len(entries) != 1:
        raise ValueError("source_path_ambiguous_in_commit")
    prefix, listed_path = entries[0].split(b"\t", 1)
    _mode, kind, blob_oid = prefix.decode().split()
    if kind != "blob" or listed_path.decode() != source_path:
        raise ValueError("source_path_not_blob")
    content = bytes(_git(repo, "cat-file", "blob", blob_oid, binary=True))
    return {
        "canonical_repo": canonical_repo,
        "commit_oid": commit_oid,
        "tree_oid": tree_oid,
        "source_path": source_path,
        "blob_oid": blob_oid,
        "blob_sha256": hashlib.sha256(content).hexdigest(),
    }


def _validate_compatibility(records: Mapping[str, Mapping[str, Any]], blockers: list[str]) -> None:
    expectations = {
        "stage12574": ("verified_deny_only", "eee5a6c09bff3a387281499a754cd033ecfcbfb25c7a88b13b955fcdc1a5db9c"),
        "stage12575": ("proposal_verified_deny_only", "e152e1999271afd56e4b1e0e0ad32f633043d5763812bb8b82e2e1f62c77426c"),
        "stage12576": ("blocked_readiness_atlas", "f051d8676b6a7e9749ae71ea109837090cc317e5ed8083b0691ca74ffc23b761"),
    }
    for name, (decision, summary_hash) in expectations.items():
        record = records.get(name, {})
        if record.get("decision") != decision:
            blockers.append(f"{name}_decision_mismatch")
        if record.get("summary_record_sha256") != summary_hash:
            blockers.append(f"{name}_summary_identity_mismatch")
        if any(record.get(field) is not False for field in DENY_FIELDS if field in record):
            blockers.append(f"{name}_deny_boundary_violated")
    if records.get("stage12576", {}).get("prospective_replacement_candidate_count") != 0:
        blockers.append("stage12576_empty_atlas_compatibility_mismatch")


def materialize_legacy_metrics(
    manifest_rows: Sequence[Mapping[str, Any]], comparison_rows: Sequence[Mapping[str, Any]],
    gemma_summary: Mapping[str, Any], route_summary: Mapping[str, Any],
    blockers: list[str],
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    manifest_ids = [row.get("row_id") for row in manifest_rows]
    comparison_ids = [row.get("row_id") for row in comparison_rows]
    roots = sorted({str(row.get("root_id")) for row in manifest_rows})
    manifest_root_identity_set_sha256 = stable_hash(roots)
    canonical_25_root_binding = (
        len(roots) == 25
        and manifest_root_identity_set_sha256 == CANONICAL_ROOT_SET_SHA256
    )
    if len(manifest_rows) != 640 or len(set(manifest_ids)) != 640:
        blockers.append("legacy_manifest_not_exactly_640_unique_rows")
    if sorted(comparison_ids) != sorted(manifest_ids):
        blockers.append("same_manifest_row_identity_set_mismatch")
    if len(roots) != 25:
        blockers.append(f"canonical_25_root_metric_manifest_mismatch:observed_{len(roots)}_roots")
    elif manifest_root_identity_set_sha256 != CANONICAL_ROOT_SET_SHA256:
        blockers.append("canonical_25_root_identity_set_mismatch")
    gemma_parent = gemma_summary.get("gemma12b")
    selected_parent = gemma_summary.get("hundred_m")
    gemma = gemma_parent.get("overall") if isinstance(gemma_parent, Mapping) else None
    selected = selected_parent.get("overall") if isinstance(selected_parent, Mapping) else None
    routed = route_summary.get("routed_transition_score")
    gemma = gemma if isinstance(gemma, Mapping) else {}
    selected = selected if isinstance(selected, Mapping) else {}
    routed = routed if isinstance(routed, Mapping) else {}
    observed_metrics = {
        "selected_transition": {key: selected.get(key) for key in ("correct", "rows", "accuracy")},
        "routed_transition": {key: routed.get(key) for key in ("correct", "rows", "accuracy")},
        "gemma3_12b_same_manifest": {key: gemma.get(key) for key in ("correct", "rows", "accuracy")},
    }
    expected_reference_metrics = {
        "selected_transition": {"correct": 364, "rows": 640, "accuracy": 0.56875},
        "routed_transition": {"correct": 375, "rows": 640, "accuracy": 0.5859375},
        "gemma3_12b_same_manifest": {"correct": 386, "rows": 640, "accuracy": 0.603125},
    }
    if gemma_summary.get("prompt_surface_hash") != PROMPT_SURFACE_SHA256:
        blockers.append("legacy_prompt_surface_identity_mismatch")
    recomputed_selected = sum(row.get("hundred_m_correct") is True for row in comparison_rows)
    recomputed_gemma = sum(row.get("gemma12b_correct") is True for row in comparison_rows)
    if recomputed_selected != 364 or recomputed_gemma != 386:
        blockers.append("row_level_correctness_recomputation_mismatch")
    if any(type(row.get("hundred_m_correct")) is not bool or type(row.get("gemma12b_correct")) is not bool for row in comparison_rows):
        blockers.append("row_level_correctness_semantic_fields_missing")
    if (gemma.get("correct"), gemma.get("rows"), gemma.get("accuracy")) != (386, 640, 0.603125):
        blockers.append("same_manifest_gemma_metrics_mismatch")
    if (selected.get("correct"), selected.get("rows"), selected.get("accuracy")) != (364, 640, 0.56875):
        blockers.append("selected_transition_metrics_mismatch")
    if (routed.get("correct"), routed.get("rows"), routed.get("accuracy")) != (375, 640, 0.5859375):
        blockers.append("routed_transition_metrics_mismatch")
    canary_fields = (
        "protected_filtered_strict_preserved_for_candidate_runtime",
        "protected_old_canary_strict_preserved_for_candidate_runtime",
        "protected_residual_preserved_for_candidate_runtime",
        "protected_smoke_preserved_for_candidate_runtime",
    )
    if "gates" not in route_summary:
        blockers.append("historical_canary_gates_missing")
        gates: Mapping[str, Any] = {}
    elif not isinstance(route_summary.get("gates"), Mapping):
        blockers.append("historical_canary_gates_malformed_non_object")
        gates = {}
    else:
        gates = route_summary["gates"]
    observed_canary_values = {field: gates.get(field) for field in canary_fields}
    for field, value in observed_canary_values.items():
        if value is False:
            blockers.append(f"historical_canary_gate_false:{field}")
        elif value is None:
            blockers.append(f"historical_canary_gate_missing:{field}")
        elif value is not True:
            blockers.append(f"historical_canary_gate_not_boolean:{field}")
    if any(value is not True for value in observed_canary_values.values()):
        blockers.append("historical_canary_gate_metrics_mismatch")
    finding_body = {
        "record_type": "stage12577_historical_metric_artifact_finding_v1",
        "canonical_25_root_binding": canonical_25_root_binding,
        "observed_manifest_root_count": len(roots),
        "required_canonical_root_count": 25,
        "required_canonical_root_set_sha256": CANONICAL_ROOT_SET_SHA256,
        "manifest_reference": str(SOURCES["manifest"].relative_to(ROOT)),
        "manifest_file_sha256": PINS["manifest"],
        "manifest_row_count": len(manifest_rows),
        "manifest_row_identity_set_sha256": stable_hash(sorted(manifest_ids)),
        "manifest_root_identity_set_sha256": manifest_root_identity_set_sha256,
        "prompt_surface_sha256": gemma_summary.get("prompt_surface_hash"),
        "comparison_reference": str(SOURCES["gemma_summary"].relative_to(ROOT)),
        "comparison_file_sha256": PINS["gemma_summary"],
        "comparison_rows_file_sha256": PINS["gemma_rows"],
        "route_reference": str(SOURCES["route_summary"].relative_to(ROOT)),
        "route_file_sha256": PINS["route_summary"],
        "selected_transition": observed_metrics["selected_transition"],
        "routed_transition": observed_metrics["routed_transition"],
        "gemma3_12b_same_manifest": observed_metrics["gemma3_12b_same_manifest"],
        "expected_reference_metric_values": expected_reference_metrics,
        "canary_gates": None,
        "observed_canary_gate_summary_values": observed_canary_values,
        "row_level_correctness_recomputed": {"selected_transition": recomputed_selected, "gemma3_12b": recomputed_gemma},
        "routed_row_level_correctness_available": False,
        "semantic_binding_complete": False,
        "preservation_claim_allowed": False,
        "readiness_claim_allowed": False,
        "metrics_recomputed": False,
        "historical_values_only": True,
    }
    finding = {**finding_body, "finding_record_sha256": stable_hash(finding_body)}
    if len(roots) != 25:
        blockers.append("observed_40_root_values_are_noncanonical_summary_only")
    blockers.append("routed_metric_row_level_semantic_binding_unavailable")
    return None, finding
    body = {
        **finding_body,
        "record_type": "stage12577_exact_legacy_25_root_metrics_v1",
        "canonical_root_count": 25,
        "canonical_root_set_sha256": CANONICAL_ROOT_SET_SHA256,
    }
    return {**body, "legacy_metrics_record_sha256": stable_hash(body)}, finding


def _exclusion_sets(
    protected_rows: Sequence[Mapping[str, Any]], manifest_rows: Sequence[Mapping[str, Any]],
    reserved12107: Sequence[Mapping[str, Any]], reserved12118: Sequence[Mapping[str, Any]],
    historical_package: Mapping[str, Any],
) -> tuple[set[str], set[str]]:
    families: set[str] = set()
    roots: set[str] = set()
    for row in [*protected_rows, *manifest_rows]:
        families.add(normalize_family(row.get("repo_family") or row.get("repo_id")))
        roots.update(normalize_family(row.get(key)) for key in ("root_id", "root_lineage_key", "stage12105_root_key"))
    for row in [*reserved12107, *reserved12118]:
        families.add(normalize_family(row.get("repo_family")))
        roots.update(normalize_family(row.get(key)) for key in ("root_id", "root_lineage_key", "work_item_id"))
    splits = historical_package.get("splits", {})
    if isinstance(splits, Mapping):
        for split in splits.values():
            if isinstance(split, Mapping) and isinstance(split.get("repo_family_counts"), Mapping):
                families.update(normalize_family(repo) for repo in split["repo_family_counts"])
    return {value for value in families if value}, {value for value in roots if value}


def materialize_candidates(
    inventory: Sequence[Mapping[str, Any]], excluded_families: set[str], excluded_roots: set[str],
    observer: Callable[[Path, str], Mapping[str, str]], blockers: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_repo: dict[str, list[Mapping[str, Any]]] = {}
    for row in inventory:
        repo_id = row.get("repo_id")
        root_id = row.get("candidate_root_id")
        paths = row.get("candidate_paths_preview")
        if isinstance(repo_id, str) and isinstance(root_id, str) and isinstance(paths, list) and paths:
            by_repo.setdefault(repo_id, []).append(row)
    candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for repo_id in sorted(CANDIDATE_REPOS):
        choices = sorted(by_repo.get(repo_id, []), key=lambda row: str(row["candidate_root_id"]))
        reasons: list[str] = []
        if not choices:
            reasons.append("source_native_inventory_record_missing")
            rejected.append({"repo_id_sha256": stable_hash(repo_id), "reason_codes": reasons})
            continue
        source = choices[0]
        root_id = str(source["candidate_root_id"])
        if normalize_family(repo_id) in excluded_families:
            reasons.append("repo_family_in_protected_train_or_reserved_set")
        if normalize_family(root_id) in excluded_roots:
            reasons.append("root_family_in_protected_train_or_reserved_set")
        try:
            observation = dict(observer(CANDIDATE_REPOS[repo_id], str(source["candidate_paths_preview"][0])))
        except (OSError, subprocess.CalledProcessError, ValueError) as exc:
            reasons.append(f"immutable_git_observation_failed:{type(exc).__name__}")
            observation = {}
        required = ("canonical_repo", "commit_oid", "tree_oid", "source_path", "blob_oid", "blob_sha256")
        if any(not observation.get(key) for key in required):
            reasons.append("repo_revision_tree_blob_evidence_incomplete")
        reasons.extend([
            "injected_observer_claims_diagnostic_only_not_promotion_authority",
            "pre_execution_seal_source_artifact_missing",
            "pre_outcome_stratum_binding_source_artifact_missing",
            "outcome_blindness_not_source_artifact_proven",
        ])
        overlap_rejected = any(reason in reasons for reason in (
            "repo_family_in_protected_train_or_reserved_set",
            "root_family_in_protected_train_or_reserved_set",
        ))
        diagnostic = {
            "candidate_identity_sha256": stable_hash([repo_id, root_id]),
            "diagnostic_only": not overlap_rejected,
            "source_inventory_record_sha256": stable_hash(dict(source)),
            "source_native_git_observation_recomputed": bool(observation),
            "required_source_bound_evidence_fields": [
                "pre_execution_seal_artifact_reference",
                "pre_execution_seal_artifact_file_sha256",
                "pre_outcome_stratum_binding_artifact_reference",
                "pre_outcome_stratum_binding_artifact_file_sha256",
                "full_universe_overlap_evidence_sha256",
            ],
            "reason_codes": sorted(set(reasons)),
        }
        if observation:
            diagnostic["observed_git_evidence_sha256"] = stable_hash(observation)
        rejected.append(diagnostic)
        continue
        lineage = {
            "source_inventory_file_sha256": PINS["rust_inventory"],
            "source_inventory_record_sha256": stable_hash({
                "repo_id": repo_id, "candidate_root_id": root_id,
                "package_root": source.get("package_root"),
                "candidate_paths_preview": source.get("candidate_paths_preview"),
                "sample_span_ids": source.get("sample_span_ids"),
            }),
            "canonical_repo_sha256": stable_hash(observation["canonical_repo"]),
            "immutable_revision_sha256": stable_hash([observation["canonical_repo"], observation["commit_oid"]]),
            "tree_sha256": stable_hash([observation["commit_oid"], observation["tree_oid"]]),
            "path_sha256": stable_hash(observation["source_path"]),
            "blob_sha256": observation["blob_sha256"],
            "git_blob_oid_sha256": stable_hash(observation["blob_oid"]),
        }
        identity = stable_hash([repo_id, root_id, lineage])
        seal_body = {
            "candidate_identity_sha256": identity,
            "split": "prospective_replacement_eval",
            "language_stratum": "rust",
            "task_strata": list(TASK_STRATA),
            "lineage": lineage,
            "excluded_repo_family_set_sha256": stable_hash(sorted(excluded_families)),
            "excluded_root_family_set_sha256": stable_hash(sorted(excluded_roots)),
            "selection_basis": "source_native_provenance_and_quarantined_stratum_only",
            "outcome_or_model_score_fields_read": False,
        }
        seal = stable_hash(seal_body)
        body = {
            "record_type": "stage12577_prospective_replacement_candidate_v1",
            **seal_body,
            "pre_execution_seal_sha256": seal,
            "pre_execution_seal_ready": True,
            "repo_family_disjoint": True,
            "root_family_disjoint": True,
            "prospective_only": True,
            **ZERO,
        }
        candidates.append({**body, "candidate_record_sha256": stable_hash(body)})
    if candidates:
        blockers.append("internal_error_unsealed_candidate_emitted")
        candidates = []
    blockers.append("diagnostic_rust_candidates_not_sealed:missing_pre_outcome_strata_and_seal_evidence")
    if len(candidates) < QUARANTINED_STRATA["rust"]:
        blockers.append(f"rust_replacement_shortfall:{QUARANTINED_STRATA['rust'] - len(candidates)}")
    blockers.append("web_js_ts_html_replacement_shortfall:4:no_provenance_complete_nonexcluded_source_native_roots")
    return candidates[:8], rejected


def build_materialization(
    records: Mapping[str, Mapping[str, Any]], rows: Mapping[str, Sequence[Mapping[str, Any]]],
    *, file_digests: Mapping[str, str | None],
    observer: Callable[[Path, str], Mapping[str, str]] = observe_git,
) -> dict[str, Any]:
    fatal: list[str] = []
    for name, expected in PINS.items():
        if file_digests.get(name) != expected:
            fatal.append(f"source_file_pin_mismatch:{name}")
    _validate_compatibility(records, fatal)
    metrics_blockers: list[str] = []
    metrics, metric_finding = materialize_legacy_metrics(
        rows["manifest"], rows["gemma_rows"], records["gemma_summary"],
        records["route_summary"], metrics_blockers,
    )
    candidate_blockers: list[str] = []
    excluded_families, excluded_roots = _exclusion_sets(
        rows["protected_rows"], rows["manifest"], rows["reserved12107"], rows["reserved12118"],
        records["historical_package"],
    )
    for row in rows.get("stage12568_rows", []):
        evidence = row.get("evidence") if isinstance(row.get("evidence"), Mapping) else {}
        key = evidence.get("namespaced_trajectory_key")
        if isinstance(key, list) and key:
            excluded_families.add(normalize_family(key[0]))
        excluded_roots.add(normalize_family(row.get("candidate_id")))
        excluded_roots.update(normalize_family(value) for value in row.get("source_ids", []) if value)
    excluded_families.discard("")
    excluded_roots.discard("")
    candidates, rejected = materialize_candidates(
        rows["rust_inventory"], excluded_families, excluded_roots, observer, candidate_blockers,
    )
    if fatal:
        metrics = None
        candidates = []
    predecessor_blockers = sorted(set(
        list(records["stage12564"].get("blocking_reasons") or [])
        + list(records["stage12568"].get("blocking_reasons") or [])
        + list(records["stage12568"].get("clearance_blocking_reasons") or [])
    ))
    blockers = sorted(set([*fatal, *metrics_blockers, *candidate_blockers, *[f"predecessor_unresolved:{reason}" for reason in predecessor_blockers]]))
    metric_findings = [metric_finding]
    body = {
        "stage": STAGE,
        "record_type": "stage12577_concrete_legacy_metrics_and_replacement_materialization_v1",
        "decision": "partial_materialization_deny_only" if metrics and candidates else "blocked_materialization_deny_only",
        "source_file_sha256": {name: file_digests.get(name) for name in sorted(PINS)},
        "stage12574_12576_compatible": not fatal,
        "legacy_metrics_materialized": metrics is not None,
        "legacy_metrics": metrics,
        "historical_metric_artifact_findings": metric_findings,
        "legacy_metric_findings": metric_findings,
        "replacement_target_count": 8,
        "quarantined_language_stratum_target": dict(QUARANTINED_STRATA),
        "sealed_candidate_count": 0,
        "replacement_candidate_count": len(candidates),
        "replacement_candidates": candidates,
        "replacement_candidate_set_sha256": stable_hash(sorted(row["candidate_record_sha256"] for row in candidates)) if candidates else None,
        "replacement_materialized_by_language": {
            language: sum(row["language_stratum"] == language for row in candidates)
            for language in sorted(QUARANTINED_STRATA)
        },
        "diagnostic_candidate_count": sum(row.get("diagnostic_only") is True for row in rejected),
        "reviewed_rejected_candidate_count": len(rejected),
        "reviewed_rejected_candidates": rejected,
        "excluded_repo_family_set_sha256": stable_hash(sorted(excluded_families)),
        "excluded_root_family_set_sha256": stable_hash(sorted(excluded_roots)),
        "selection_basis": "source_native_provenance_and_quarantined_stratum_only",
        "selection_outcome_or_model_score_conditioned": None,
        "outcome_blindness_verified": False,
        "outcome_blindness_source_artifact_reference": None,
        "replacement_admission_performed": False,
        "evaluation_performed": False,
        "training_performed": False,
        "clearance_granted": False,
        "blocking_reasons": blockers,
        **ZERO,
    }
    return {**body, "summary_record_sha256": stable_hash(body)}


def build() -> dict[str, Any]:
    records = {name: read_json(SOURCES[name]) for name in (
        "stage12564", "stage12568", "stage12574", "stage12575", "stage12576", "gemma_summary", "route_summary", "historical_package",
    )}
    rows = {name: read_jsonl(SOURCES[name]) for name in (
        "stage12568_rows", "manifest", "gemma_rows", "protected_rows", "rust_inventory", "reserved12107", "reserved12118",
    )}
    return build_materialization(
        records, rows, file_digests={name: file_sha256(path) for name, path in SOURCES.items()}
    )


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    result = build()
    write_json(OUT / "concrete_legacy_metrics_and_replacement_candidate_materialization.json", result)
    write_json(OUT / "historical_metric_artifact_findings.json", {
        "record_type": "stage12577_historical_metric_artifact_findings_v1",
        "findings": result["historical_metric_artifact_findings"],
    })
    write_json(OUT / "sealed_replacement_candidates.json", {
        "record_type": "stage12577_sealed_replacement_candidates_v1",
        "candidate_count": result["replacement_candidate_count"],
        "candidates": result["replacement_candidates"],
        "candidate_set_sha256": result["replacement_candidate_set_sha256"],
        "admission_performed": False,
    })
    write_json(OUT / "exact_blockers.json", {
        "record_type": "stage12577_exact_blockers_v1",
        "blocking_reasons": result["blocking_reasons"],
        "reviewed_rejected_candidates": result["reviewed_rejected_candidates"],
    })
    write_json(OUT / "summary.json", result)
    write_json(SUMMARY, result)
    print(json.dumps({key: result[key] for key in (
        "decision", "legacy_metrics_materialized", "replacement_candidate_count",
        "blocking_reasons", "training_allowed", "evaluation_allowed",
    )}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
