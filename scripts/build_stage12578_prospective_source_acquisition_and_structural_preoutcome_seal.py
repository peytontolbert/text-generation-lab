#!/usr/bin/env python3
"""Build the fail-closed Stage12578 replacement-source readiness ledger."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12578_prospective_source_acquisition_and_structural_preoutcome_seal"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

UNIVERSE_SOURCES = {
    "active_protected": ROOT / "runs/local/artifacts/stage12554_authority_inventory_and_overlap_gate/protected_swe_bench_verified_manifest.json",
    "legacy_protected": ROOT / "runs/local/artifacts/stage12560_protected_namespace_deny_sidecars/hashed_namespace_sidecars.json",
    "sealed_transition": ROOT / "runs/local/artifacts/stage12105_sealed_transition_candidate_atlas/sealed_transition_candidate_rows.jsonl",
    "locked_benchmark": ROOT / "runs/local/artifacts/stage8672_locked_benchmark_pack_manifest/locked_benchmark_packs.jsonl",
    "locked_acceptance": ROOT / "runs/local/artifacts/stage9718_locked_multilingual_acceptance_evidence_ledger/locked_multilingual_acceptance_evidence_ledger.json",
    "scratchpad_exclusions": ROOT / "runs/local/artifacts/stage12037_scratchpad_contamination_exclusion_audit/scratchpad_excluded_keys.jsonl",
    "training_exclusions": ROOT / "runs/local/artifacts/stage12040_training_data_scratchpad_contamination_gate/training_scratchpad_excluded_keys.jsonl",
    "train_families": ROOT / "runs/local/artifacts/stage10706_rewritten_plus_reviewed_multilingual_training_package_honest_strict/rewritten_plus_reviewed_multilingual_training_package_honest_strict.json",
    "transition_train": ROOT / "runs/local/artifacts/stage11897_transition_record_projection_rows/transition_projection_rows.jsonl",
    "open_swe_protected": ROOT / "runs/local/artifacts/stage12568_open_swe_source_lineage_adapter/trajectory_source_bindings.jsonl",
    "reserved12107": ROOT / "runs/local/artifacts/stage12107_fresh_sealed_transition_root_materializer/fresh_sealed_transition_materialization_work_items.jsonl",
    "reserved12118": ROOT / "runs/local/artifacts/stage12118_maintainer_400_pilot_checkout_probe_request/pilot_checkout_probe_targets.jsonl",
}
UNIVERSE_PINS = {
    "active_protected": "50e52154348d471c0d6407e466b3bffce4a197fbe81cce6db122ef22c4bcb5c5",
    "legacy_protected": "f1448cfe374558be29015572f81b07be82ce044756db603072bbb3230fb4b89c",
    "sealed_transition": "dbaf3800b987bb8607c8cd2ddb0ddcbf2011e6be9b2f4c0a41847013b86dddd2",
    "locked_benchmark": "a6cce0dabed78c240037a0ef7d06fb739e7dd9b835ca57686d49d66bff84a570",
    "locked_acceptance": "e19c6b80eb3881d1ceef55dfbc414f12d9a4a1e3b7e7e1e62ab11dc27d2c470f",
    "scratchpad_exclusions": "633d36b0c7c6eabd03ea188cbd75251c2453b4950c745fcf1ce65fcb9c36aab3",
    "training_exclusions": "c48652ada5ca6f23eae8da456d7af16eae4913cf106ddea033359a6ff46261ff",
    "train_families": "ed98291c3e2a2a6919274004b16e5998f2eef23f4526ee5c8281b136683a7762",
    "transition_train": "7ce8c030d429d948d3805e836d9e6522bcd0320252cfcb27b59475d8c1cb64bc",
    "open_swe_protected": "dab856c947426dcc128acd7bb0c1731f98a6bd9d6ab5cd6eb7be8d8271150b0a",
    "reserved12107": "e2e900ad050f4f083a612afea29ebc88890f0fda4c3d59277ebcea05242abe02",
    "reserved12118": "2de3486ef058a8f27ca602a18b852d46ace194135db4aa4eef630f16363a9f45",
}
SUPPORT_SOURCES = {
    "stage12576": ROOT / "runs/local/artifacts/stage12576_legacy_metrics_and_sealed_replacement_readiness_atlas/legacy_metrics_and_sealed_replacement_readiness_atlas.json",
    "stage12577": ROOT / "runs/local/artifacts/stage12577_concrete_legacy_metrics_and_replacement_candidate_materialization/concrete_legacy_metrics_and_replacement_candidate_materialization.json",
}
SUPPORT_PINS = {
    "stage12576": "031352edbaf018c8b249c8920e453bcb705ffe452d562d57adb0f9855e1c053a",
    "stage12577": "0bb6c09af7f583db92061451d8c53c5b5a485cf2d2f9c13784c8989d2643cda1",
}
PINS = {**UNIVERSE_PINS, **SUPPORT_PINS}
SOURCES = {**UNIVERSE_SOURCES, **SUPPORT_SOURCES}

TASK_STRATA = (
    "transition_candidate_selection", "transition_continue_or_stop",
    "transition_next_action", "transition_verifier_transition",
)
DENY_FIELDS = (
    "training_allowed", "evaluation_allowed", "admission_allowed", "clearance_granted",
    "root_credit", "repair_credit", "level3_credit", "protected_clearance",
    "use_clearance", "execution_authorized", "gpu_allowed", "replay_allowed",
    "strict_eval_eligible",
)
ZERO = {key: False for key in DENY_FIELDS}
FORBIDDEN_KEYS = {
    "accuracy", "correct", "correctness", "gold", "gold_label", "loss", "metric",
    "metrics", "model_score", "outcome", "prediction", "reward", "score", "scores",
    "target_label", "verifier_outcome", "verifier_result",
}
HEX40 = re.compile(r"^[0-9a-f]{40}$")

WEB_PROSPECTS = (
    ("bddy_website", "https://github.com/peytontolbert/bddy_website", Path("/data/bddy/bddy_website"), "src/main.js"),
    ("bddy_app", "https://github.com/peytontolbert/bddyio", Path("/data/bddy/bddy_app"), "apps/desktop/src/_pages/SubscribedApp.tsx"),
    ("bddy_desktop", "https://github.com/bddyio/bddy", Path("/data/bddy/bddy"), "electron/main.ts"),
    ("bddy_api", "https://github.com/bddyio/bddy-api", Path("/data/bddy/bddy-api"), "src/app.module.ts"),
)
RUST_TARGETS = (
    ("serde", "https://github.com/serde-rs/serde", Path("/data/repositories/serde"), "serde-*"),
    ("clap", "https://github.com/clap-rs/clap", Path("/data/repositories/clap"), "clap-*"),
    ("petgraph", "https://github.com/petgraph/petgraph", Path("/data/repositories/petgraph"), "petgraph-*"),
    ("indexmap", "https://github.com/indexmap-rs/indexmap", Path("/data/repositories/indexmap"), "indexmap-*"),
)
# Hash-bound identity projection only. Stage10706 itself is never parsed for metrics.
KNOWN_FAMILY_ALIASES = (
    "bddy_website", "bddy_app", "bddy_desktop", "bddy_api", "bddyio", "bddy-api", "bddy",
    "repository_library", "tokenizers", "agentkernel", "candle",
    "transformers", "sphinx", "django", "onnxruntime", "parametergolf",
)


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def file_sha256(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def normalize_remote(value: Any) -> str:
    raw = str(value or "").strip()
    if raw.startswith("git@") and ":" in raw:
        raw = "https://" + raw[4:].replace(":", "/", 1)
    if raw.startswith("ssh://git@"):
        raw = "https://" + raw[len("ssh://git@"):]
    parsed = urlparse(raw)
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if (parsed.hostname or "").lower() != "github.com" or len(parts) != 2:
        raise ValueError("placeholder_or_noncanonical_remote")
    owner, repo = parts
    repo = repo[:-4] if repo.lower().endswith(".git") else repo
    if not owner or not repo:
        raise ValueError("placeholder_or_noncanonical_remote")
    return f"https://github.com/{owner.lower()}/{repo.lower()}"


def normalize_alias(value: Any) -> str:
    raw = str(value or "").strip()
    try:
        raw = normalize_remote(raw).removeprefix("https://github.com/")
    except ValueError:
        pass
    return re.sub(r"[^a-z0-9]", "", raw.lower().replace("localgitsnapshot", ""))


def normalize_source_path(value: Any) -> str:
    raw = PurePosixPath(str(value or "").replace("\\", "/")).as_posix().lower().lstrip("./")
    return re.sub(r"[^a-z0-9/]", "", raw)


def forbidden_paths(value: Any, prefix: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            path = f"{prefix}.{key}"
            if str(key).lower() in FORBIDDEN_KEYS:
                found.append(path)
            found.extend(forbidden_paths(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(forbidden_paths(child, f"{prefix}[{index}]"))
    return found


def _git(repo: Path, *args: str, binary: bool = False) -> str | bytes:
    result = subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
    return result.stdout if binary else result.stdout.decode().strip()


def inspect_git(repo: Path, expected_remote: str, source_path: str) -> dict[str, Any]:
    if not repo.is_dir() or not (repo / ".git").exists():
        raise ValueError("source_native_git_checkout_absent")
    remote = normalize_remote(_git(repo, "remote", "get-url", "origin"))
    if remote != normalize_remote(expected_remote):
        raise ValueError("canonical_remote_mismatch")
    commit = str(_git(repo, "rev-parse", "HEAD^{commit}"))
    tree = str(_git(repo, "rev-parse", "HEAD^{tree}"))
    path = PurePosixPath(source_path).as_posix()
    listing = bytes(_git(repo, "ls-tree", "-z", commit, "--", path, binary=True))
    entries = listing.rstrip(b"\0").split(b"\0") if listing else []
    if len(entries) != 1 or not HEX40.fullmatch(commit) or not HEX40.fullmatch(tree):
        raise ValueError("missing_path_or_malformed_git_identity")
    prefix, listed = entries[0].split(b"\t", 1)
    mode, kind, blob = prefix.decode().split()
    if listed.decode() != path or kind != "blob" or mode not in {"100644", "100755"} or not HEX40.fullmatch(blob):
        raise ValueError("source_path_not_regular_git_blob")
    content = bytes(_git(repo, "cat-file", "blob", blob, binary=True))
    dirty = str(_git(repo, "status", "--porcelain=v1"))
    worktree_matches = (repo / path).is_file() and (repo / path).read_bytes() == content
    raw = {"canonical_remote": remote, "commit_oid": commit, "tree_oid": tree, "source_path": path, "git_blob_oid": blob, "content_sha256": hashlib.sha256(content).hexdigest()}
    return {
        **raw,
        "canonical_identity_hashes": {
            "remote_sha256": stable_hash(remote), "commit_sha256": stable_hash(commit),
            "tree_sha256": stable_hash(tree), "path_sha256": stable_hash(path),
            "blob_oid_sha256": stable_hash(blob), "content_sha256": raw["content_sha256"],
        },
        "worktree_clean": dirty == "", "worktree_matches_committed_blob": worktree_matches,
        "dirty_status_sha256": hashlib.sha256(dirty.encode()).hexdigest(),
        "lineage_sha256": stable_hash(raw),
    }


def revalidate_git_observation(observation: Mapping[str, Any], checkout: Path) -> tuple[bool, list[str]]:
    try:
        current = inspect_git(checkout, str(observation.get("canonical_remote")), str(observation.get("source_path")))
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        return False, [f"source_reobservation_failed:{exc}"]
    fields = ("commit_oid", "tree_oid", "git_blob_oid", "content_sha256", "lineage_sha256", "worktree_clean", "worktree_matches_committed_blob")
    reasons = [f"source_changed:{field}" for field in fields if current.get(field) != observation.get(field)]
    return not reasons, reasons


def validate_universes(universes: Any) -> list[str]:
    blockers: list[str] = []
    seen: set[str] = set()
    if not isinstance(universes, (list, tuple)):
        return ["malformed_universe_collection"]
    if len(universes) != 12:
        blockers.append("authority_universe_not_exactly_12_artifacts")
    for index, row in enumerate(universes):
        if not isinstance(row, Mapping):
            blockers.append(f"malformed_universe:{index}")
            continue
        if forbidden_paths(row):
            blockers.append(f"outcome_field_in_universe:{index}")
        if set(row) != {"universe_id", "role", "complete", "entries"}:
            blockers.append(f"malformed_universe:{index}")
            continue
        uid = row.get("universe_id")
        entries = row.get("entries")
        if not isinstance(uid, str) or not uid or uid in seen:
            blockers.append(f"duplicate_or_placeholder_universe:{index}")
        else:
            seen.add(uid)
        valid_entries = isinstance(entries, list) and bool(entries) and all(
            isinstance(entry, str) and bool(entry.strip()) for entry in entries
        )
        if row.get("role") not in {"protected", "train", "reserved"} or not valid_entries:
            blockers.append(f"malformed_universe:{uid}")
        elif len(entries) != len(set(entries)):
            blockers.append(f"duplicate_universe_entries:{uid}")
        if row.get("complete") is not True:
            blockers.append(f"authority_closure_incomplete:{uid}")
    return sorted(set(blockers))


def normalized_universe_aliases(universes: Any) -> set[str]:
    aliases: set[str] = set()
    if not isinstance(universes, (list, tuple)):
        return aliases
    for row in universes:
        if not isinstance(row, Mapping):
            continue
        entries = row.get("entries")
        if not isinstance(entries, list):
            continue
        aliases.update(
            normalize_alias(entry) for entry in entries
            if isinstance(entry, str) and entry.strip()
        )
    return aliases


def build_universe_ledger() -> list[dict[str, Any]]:
    aliases = sorted({normalize_alias(value) for value in KNOWN_FAMILY_ALIASES})
    # Several sources are deliberately represented by their pinned identity only:
    # their payloads contain outcomes or lack canonical lineage authority.
    return [
        {"universe_id": "active_protected", "role": "protected", "complete": True, "entries": [UNIVERSE_PINS["active_protected"]]},
        {"universe_id": "legacy_protected", "role": "protected", "complete": False, "entries": [UNIVERSE_PINS["legacy_protected"]]},
        {"universe_id": "sealed_transition", "role": "protected", "complete": False, "entries": [UNIVERSE_PINS["sealed_transition"]]},
        {"universe_id": "locked_benchmark", "role": "protected", "complete": False, "entries": [UNIVERSE_PINS["locked_benchmark"]]},
        {"universe_id": "locked_acceptance", "role": "protected", "complete": False, "entries": [UNIVERSE_PINS["locked_acceptance"]]},
        {"universe_id": "scratchpad_exclusions", "role": "protected", "complete": True, "entries": [UNIVERSE_PINS["scratchpad_exclusions"]]},
        {"universe_id": "training_exclusions", "role": "train", "complete": True, "entries": [UNIVERSE_PINS["training_exclusions"]]},
        {"universe_id": "train_families", "role": "train", "complete": True, "entries": aliases},
        {"universe_id": "transition_train", "role": "train", "complete": True, "entries": [UNIVERSE_PINS["transition_train"]]},
        {"universe_id": "open_swe_protected", "role": "protected", "complete": False, "entries": [UNIVERSE_PINS["open_swe_protected"]]},
        {"universe_id": "reserved12107", "role": "reserved", "complete": True, "entries": [UNIVERSE_PINS["reserved12107"]]},
        {"universe_id": "reserved12118", "role": "reserved", "complete": True, "entries": [UNIVERSE_PINS["reserved12118"]]},
    ]


def canonical_universe_digest(universes: Any) -> str | None:
    if not isinstance(universes, (list, tuple)):
        return None
    canonical_rows: list[dict[str, Any]] = []
    for row in universes:
        if not isinstance(row, Mapping) or set(row) != {"universe_id", "role", "complete", "entries"}:
            return None
        entries = row.get("entries")
        if not isinstance(entries, list) or any(not isinstance(entry, str) for entry in entries):
            return None
        canonical_rows.append({
            "universe_id": row.get("universe_id"),
            "role": row.get("role"),
            "complete": row.get("complete"),
            "entries": sorted(normalize_alias(entry) for entry in entries),
        })
    return stable_hash(sorted(canonical_rows, key=lambda row: str(row["universe_id"])))


def validate_caller_candidate(record: Mapping[str, Any]) -> list[str]:
    allowed = {"name", "language", "canonical_remote", "checkout", "source_path"}
    reasons = []
    if set(record) - allowed:
        reasons.append("caller_precomputed_or_unknown_candidate_fields")
    if forbidden_paths(record):
        reasons.append("caller_outcome_fields_rejected")
    return reasons


def duplicate_root_blockers(records: Sequence[Mapping[str, Any]]) -> list[str]:
    roots = [
        (normalize_alias(row.get("canonical_remote")), normalize_source_path(row.get("source_path")))
        for row in records if isinstance(row, Mapping)
    ]
    return ["duplicate_root_or_source_dominance"] if len(roots) != len(set(roots)) else []


def build_stage(*, file_digests: Mapping[str, str | None] | None = None, universes: Any = None) -> dict[str, Any]:
    digests = dict(file_digests or {name: file_sha256(path) for name, path in SOURCES.items()})
    pin_blockers = [
        f"source_file_pin_mismatch:{name}"
        for name, expected in PINS.items()
        if digests.get(name) != expected
    ]
    blockers = list(pin_blockers)
    all_source_pins_valid = not pin_blockers

    canonical_universes = build_universe_ledger()
    canonical_digest = canonical_universe_digest(canonical_universes)
    caller_override = universes is not None
    universe_rows = universes if caller_override else canonical_universes
    universe_blockers = validate_universes(universe_rows)
    effective_digest = canonical_universe_digest(universe_rows)
    exact_canonical_universe_binding = effective_digest is not None and effective_digest == canonical_digest
    if caller_override and not exact_canonical_universe_binding:
        universe_blockers.append("caller_universe_override_non_authoritative")
    universe_blockers = sorted(set(universe_blockers))
    blockers.extend(universe_blockers)
    universe_aliases = normalized_universe_aliases(universe_rows)
    authority_closure_complete = (
        exact_canonical_universe_binding
        and all_source_pins_valid
        and not universe_blockers
    )

    source_native: list[dict[str, Any]] = []
    diagnostic: list[dict[str, Any]] = []
    for name, remote, checkout, source_path in WEB_PROSPECTS:
        try:
            observation = inspect_git(checkout, remote, source_path)
        except (OSError, ValueError, subprocess.CalledProcessError) as exc:
            diagnostic.append({
                "name": name,
                "reason_codes": [f"git_observation_failed:{exc}"],
                "source_native_candidate": False,
            })
            blockers.append(f"web_prospect_git_observation_failed:{name}")
            continue

        revalidation_ok, revalidation_reasons = revalidate_git_observation(observation, checkout)
        identity = stable_hash([
            observation["canonical_remote"], observation["commit_oid"],
            observation["source_path"], observation["content_sha256"],
        ])
        reasons = [
            "source_native_task_diff_evidence_missing",
            "preoutcome_stratum_binding_artifact_missing",
        ]
        if not exact_canonical_universe_binding:
            reasons.append("canonical_universe_binding_not_exact")
        if not all_source_pins_valid:
            reasons.append("source_input_pins_not_all_valid")
        if not authority_closure_complete:
            reasons.append("authority_closure_incomplete")

        candidate_aliases = {normalize_alias(name), normalize_alias(remote)}
        overlap = bool(candidate_aliases & universe_aliases)
        if overlap:
            reasons.append("normalized_protected_train_or_reserved_overlap")
            blockers.append(f"web_prospect_overlap:{name}")
        checkout_clean = bool(observation.get("worktree_clean"))
        committed_blob_matches = bool(observation.get("worktree_matches_committed_blob"))
        if not checkout_clean or not committed_blob_matches:
            reasons.append("dirty_checkout_not_candidate_eligible")
            blockers.append(f"dirty_web_checkout:{name}")
        if not revalidation_ok:
            reasons.extend(revalidation_reasons or ["source_revalidation_failed"])
            blockers.append(f"web_prospect_revalidation_failed:{name}")

        row = {
            "opaque_prospect_id": "prospect_" + identity[:20],
            "language_stratum": "web_js_ts_html",
            "lineage": observation,
            "task_diff_evidence_verified": False,
            "preoutcome_stratum_binding_verified": False,
            "transition_strata": [],
            "reason_codes": sorted(set(reasons)),
            "sealed_credit": False,
        }
        candidate_prerequisites_hold = (
            exact_canonical_universe_binding
            and all_source_pins_valid
            and authority_closure_complete
            and not overlap
            and checkout_clean
            and committed_blob_matches
            and revalidation_ok
            and row["task_diff_evidence_verified"] is True
            and row["preoutcome_stratum_binding_verified"] is True
            and tuple(row["transition_strata"]) == TASK_STRATA
        )
        if candidate_prerequisites_hold:
            source_native.append({**row, "source_native_candidate": True})
        else:
            diagnostic.append({**row, "source_native_candidate": False})

    requests: list[dict[str, Any]] = []
    registry_root = Path.home() / ".cargo/registry/src"
    for name, remote, checkout, pattern in RUST_TARGETS:
        registry_paths = sorted(
            str(path)
            for index in registry_root.glob("*")
            for path in index.glob(pattern)
            if path.is_dir()
        )
        git_present = checkout.is_dir() and (checkout / ".git").exists()
        if not git_present:
            blockers.append(f"rust_source_native_git_checkout_absent:{name}")
        requests.append({
            "request_id": "acq_" + stable_hash(["rust", remote])[:20],
            "crate": name,
            "canonical_remote": normalize_remote(remote),
            "required_git_checkout": str(checkout),
            "source_native_git_checkout_present": git_present,
            "cargo_registry_source_present": bool(registry_paths),
            "cargo_registry_source_set_sha256": stable_hash(registry_paths),
            "registry_sources_are_diagnostic_only": True,
            "network_clone_performed": False,
            "sealed_credit": False,
            "reason": "registry_source_is_not_source_native_git_checkout",
        })

    blockers.extend([
        "authority_closure_unresolved",
        "source_native_task_diff_evidence_missing",
        "preoutcome_stratum_binding_artifact_missing",
        "rust_sealed_credit_zero",
    ])
    blockers.extend(duplicate_root_blockers([
        {"canonical_remote": row[1], "source_path": row[3]}
        for row in WEB_PROSPECTS
    ]))
    body = {
        "stage": STAGE,
        "record_type": "stage12578_prospective_source_acquisition_readiness_ledger_v1",
        "decision": "blocked_acquisition_readiness_deny_only",
        "universe_artifact_count": len(UNIVERSE_SOURCES),
        "canonical_universe_digest": canonical_digest,
        "effective_universe_digest": effective_digest,
        "exact_canonical_universe_binding": exact_canonical_universe_binding,
        "caller_universe_override_used": caller_override,
        "universe_source_file_sha256": {name: digests.get(name) for name in UNIVERSE_SOURCES},
        "support_source_file_sha256": {name: digests.get(name) for name in SUPPORT_SOURCES},
        "all_input_artifacts_pinned": all_source_pins_valid,
        "authority_closure_complete": authority_closure_complete,
        "input_policy": "provenance_identity_only_no_outcome_payload_selection",
        "forbidden_model_score_verifier_outcome_correctness_fields_read": [],
        "post_outcome_selection_performed": False,
        "required_transition_strata": list(TASK_STRATA),
        "source_native_candidate_count": len(source_native),
        "source_native_candidates": source_native,
        "diagnostic_prospect_count": len(diagnostic),
        "diagnostic_prospects": diagnostic,
        "registry_acquisition_target_count": len(requests),
        "registry_acquisition_targets": requests,
        "acquisition_request_count": len(requests),
        "network_clone_performed": False,
        "sealed_candidate_count": 0,
        "sealed_by_language": {"rust": 0, "web_js_ts_html": 0},
        "structural_preoutcome_seals": [],
        "training_performed": False,
        "evaluation_performed": False,
        "admission_performed": False,
        "blocking_reasons": sorted(set(blockers)),
        **ZERO,
    }
    return {**body, "summary_record_sha256": stable_hash(body)}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    result = build_stage()
    write_json(OUT / "prospective_source_acquisition_readiness_ledger.json", result)
    write_json(OUT / "source_native_candidates.json", {"candidate_count": result["source_native_candidate_count"], "candidates": result["source_native_candidates"], "sealed_credit": False})
    write_json(OUT / "diagnostic_prospects.json", {"prospect_count": result["diagnostic_prospect_count"], "prospects": result["diagnostic_prospects"], "sealed_credit": False})
    write_json(OUT / "acquisition_requests.json", {"request_count": result["acquisition_request_count"], "requests": result["registry_acquisition_targets"], "network_clone_performed": False})
    write_json(OUT / "preoutcome_candidate_seals.json", {"seal_count": 0, "seals": [], "admission_performed": False})
    write_json(OUT / "exact_blockers.json", {"blocking_reasons": result["blocking_reasons"]})
    write_json(OUT / "summary.json", result)
    write_json(SUMMARY, result)
    print(json.dumps({key: result[key] for key in ("decision", "universe_artifact_count", "source_native_candidate_count", "diagnostic_prospect_count", "acquisition_request_count", "sealed_candidate_count", "blocking_reasons")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
