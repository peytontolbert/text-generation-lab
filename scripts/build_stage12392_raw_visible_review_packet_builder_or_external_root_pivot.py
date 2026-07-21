#!/usr/bin/env python3
"""Stage12392 fail-closed external-root pivot after Stage12391.

This stage consumes Stage12391 reviewed/blocked packet metadata plus selected
central-spine summaries. It emits no training rows and does not copy raw packet
paths, commands, outputs, source text, or patch bodies into its artifacts.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12392_raw_visible_review_packet_builder_or_external_root_pivot"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12391_ARTIFACT = ROOT / "runs/local/artifacts/stage12391_manual_review_packet_admission_audit"
STAGE12391_REVIEWED = STAGE12391_ARTIFACT / "reviewed_manual_policy_candidate_packets.jsonl"
STAGE12391_BLOCKED = STAGE12391_ARTIFACT / "blocked_manual_policy_candidate_packets.jsonl"
STAGE12391_ADMITTED = STAGE12391_ARTIFACT / "admitted_manual_policy_candidate_packets_should_be_empty.jsonl"
STAGE12391_SUMMARY = ROOT / "runs/summaries/stage12391_manual_review_packet_admission_audit.json"

CENTRAL_SPINE_SUMMARIES = [
    "stage12313_spine_aligned_training_progress_analysis",
    "stage12327_external_adapter_preflight",
    "stage12328_external_adapter_qc_materialization_request",
    "stage12233_external_acquisition_blocker_decision",
    "stage12240_external_repair_acquisition_request_v2",
    "stage12268_external_candidate_semantic_review_shortlist",
    "stage12269_external_semantic_review_result_ingest",
    "stage12280_external_normalized_verifier_identity_selector",
    "stage12281_semantic_review_packet_normalized_exact_verifiers",
    "stage12284_external_repair_commit_pair_preflight",
    "stage12285_external_repair_replay_executor_request",
    "stage12286_external_repair_replay_smoke_executor",
    "stage12287_external_repair_replay_second_smoke_request",
    "stage12288_external_repair_replay_second_smoke_executor",
    "stage12387_transition_local_materializer_upgrade_worklist",
]

SELF_REPO_FAMILIES = {"agentkernel-seq2seq-text-lab"}
FORBIDDEN_TEXT_PATTERNS = [
    re.compile(r"/(?:data|home|tmp|var|mnt|workspace|arxiv)/"),
    re.compile(r"\b(?:pytest|python3?|cargo|npm|pnpm|yarn|make|cmake|ctest|node)\s+\S+"),
    re.compile(r"(?m)^\s*(?:diff --git|@@ |\+\+\+ |--- )"),
]
RAWISH_KEY_RE = re.compile(
    r"(raw|command|output|patch_body|diff|source_text|failureDetails|sample_files|root|path)$",
    re.IGNORECASE,
)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def count_jsonl(path: Path) -> int:
    return len(read_jsonl(path))


def sanitized_leaf(value: Any) -> Any:
    if isinstance(value, str):
        if any(pattern.search(value) for pattern in FORBIDDEN_TEXT_PATTERNS):
            return "redacted_raw_or_absolute_reference"
        return value
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return None


def sanitize_summary_fragment(value: Any, key_hint: str = "") -> Any:
    if RAWISH_KEY_RE.search(key_hint):
        if isinstance(value, (int, float, bool)) or value is None:
            return value
        if isinstance(value, str):
            return sanitized_leaf(value)
        if isinstance(value, list):
            return f"redacted_{len(value)}_items"
        if isinstance(value, dict):
            return "redacted_rawish_mapping"
    if isinstance(value, dict):
        return {str(k): sanitize_summary_fragment(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_summary_fragment(item, key_hint) for item in value]
    return sanitized_leaf(value)


def flatten_strings(value: Any) -> list[str]:
    if isinstance(value, dict):
        out: list[str] = []
        for item in value.values():
            out.extend(flatten_strings(item))
        return out
    if isinstance(value, list):
        out = []
        for item in value:
            out.extend(flatten_strings(item))
        return out
    if isinstance(value, str):
        return [value]
    return []


def packet_counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    blocker_counts: Counter[str] = Counter()
    repo_counts: Counter[str] = Counter()
    verifier_counts: Counter[str] = Counter()
    patch_status_counts: Counter[str] = Counter()
    source_hashes: set[str] = set()
    raw_visibility_true: Counter[str] = Counter()

    for row in rows:
        blocker_counts.update(str(item) for item in row.get("remaining_blockers", []) if item)
        repo_counts[str(row.get("repo_family") or "missing")] += 1
        verifier = row.get("selected_verifier_identity_candidate")
        if isinstance(verifier, dict):
            verifier_counts[str(verifier.get("command_head_class") or "missing")] += 1
        else:
            verifier_counts["missing"] += 1
        patch_status_counts[str(row.get("patch_apply_status") or "missing")] += 1
        source_ids = row.get("source_ids")
        if isinstance(source_ids, dict) and source_ids.get("source_file_hash_compat"):
            source_hashes.add(str(source_ids["source_file_hash_compat"]))
        raw_visibility = row.get("raw_visibility")
        if isinstance(raw_visibility, dict):
            for key, value in raw_visibility.items():
                if value is True:
                    raw_visibility_true[str(key)] += 1

    return {
        "remaining_blocker_counts": dict(sorted(blocker_counts.items())),
        "repo_family_counts": dict(sorted(repo_counts.items())),
        "selected_verifier_command_class_counts": dict(sorted(verifier_counts.items())),
        "patch_apply_status_counts": dict(sorted(patch_status_counts.items())),
        "unique_repo_families": len(repo_counts),
        "unique_source_hashes": len(source_hashes),
        "raw_visibility_true_counts": dict(sorted(raw_visibility_true.items())),
    }


def why_stage12391_cannot_train(stage12391_summary: dict[str, Any], counts: dict[str, Any]) -> dict[str, Any]:
    blockers = counts["remaining_blocker_counts"]
    self_repo_rows = sum(
        count
        for repo, count in counts["repo_family_counts"].items()
        if repo in SELF_REPO_FAMILIES
    )
    reviewed = int(stage12391_summary.get("manual_packets_reviewed") or 0)
    return {
        "decision": "stage12391_self_repo_packets_cannot_be_training_rows",
        "reviewed_packets": reviewed,
        "blocked_packets": int(stage12391_summary.get("blocked_rows") or 0),
        "admitted_packets": int(stage12391_summary.get("admitted_rows") or 0),
        "self_repo_packet_count": self_repo_rows,
        "unique_repo_families": counts["unique_repo_families"],
        "top_blocker_categories": [
            {
                "blocker": blocker,
                "count": blockers.get(blocker, 0),
                "effect": effect,
            }
            for blocker, effect in [
                ("policy_label_not_selected", "observed action is not an admitted policy label"),
                (
                    "selected_verifier_relevance_not_semantically_proven",
                    "selected verifier is not proven to be the relevant causal check",
                ),
                (
                    "state_delta_semantics_not_proven_from_packet",
                    "patch/state transition semantics are not proven from safe packet fields",
                ),
                (
                    "self_repo_dominated_scale_claim_blocked",
                    "single self-repo family cannot support external/source-heldout scale claims",
                ),
                (
                    "strict_or_source_heldout_admission_requires_separate_full_proof",
                    "higher-trust admissions need a separate proof gate",
                ),
            ]
            if blockers.get(blocker, 0)
        ],
        "fail_closed_reason": (
            "Stage12391 packets are manual review candidates from the self repository. They preserve useful "
            "counts and blocker categories, but they lack admitted policy labels, proven verifier relevance, "
            "proven state-delta semantics, source diversity, and a separate Level-3/patch-trace/strict/source-heldout proof."
        ),
        "co_presence_not_causality_boundary": {
            "stage12390_verifier_selection_is_review_heuristic": True,
            "unique_patch_verifier_binding_proven": False,
            "safe_manual_packet_fields_include_verifier_event_count": False,
            "hard_blocker": (
                "A verifier-like event after a patch is not causal proof. Stage12392 successors must recover a "
                "unique patch-to-verifier binding from private raw-visible records before any Level-3, patch-trace, "
                "strict/source-heldout, or training admission."
            ),
            "required_private_review_fields": [
                "patch_attempt_boundary",
                "selected_verifier_event_ref",
                "verifier_in_after_patch_pre_next_patch_interval",
                "same_source_root_and_checkout",
                "verifier_semantically_tests_changed_behavior",
                "pre_status_class",
                "post_status_class",
            ],
        },
    }


def load_spine_summaries() -> dict[str, dict[str, Any]]:
    loaded: dict[str, dict[str, Any]] = {}
    for stage in CENTRAL_SPINE_SUMMARIES:
        loaded[stage] = read_json(ROOT / "runs/summaries" / f"{stage}.json")
    return loaded


def build_adapter_worklist(spine: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    stage12327 = spine.get("stage12327_external_adapter_preflight", {})
    stage12328 = spine.get("stage12328_external_adapter_qc_materialization_request", {})
    stage12280 = spine.get("stage12280_external_normalized_verifier_identity_selector", {})
    stage12387 = spine.get("stage12387_transition_local_materializer_upgrade_worklist", {})

    open_swe = stage12327.get("open_swe_import_artifact", {})
    open_swe_contract = stage12328.get("open_swe_qc_materialization_contract", {})
    bears = stage12327.get("bears_inventory", {})
    bears_contract = stage12328.get("bears_qc_materialization_contract", {})

    worklist = [
        {
            "priority": 1,
            "candidate_source_adapter": "open_swe_trace_safe_transition_adapter",
            "source_family": "Open-SWE-Traces",
            "candidate_count": open_swe.get("priority_capped_candidates")
            or open_swe.get("sampled_preflight_candidates"),
            "summary_source_stages": [
                "stage12327_external_adapter_preflight",
                "stage12328_external_adapter_qc_materialization_request",
            ],
            "private_raw_visible_review_packet_scope": (
                "convert capped raw-visible traces into private reviewer packets with only safe semantic "
                "fields promoted to any model-facing artifact"
            ),
            "schema_requirements": open_swe_contract.get("required_safe_fields", []),
            "hard_rejects": open_swe_contract.get("hard_rejects", []),
            "admission_boundary": "trace_support_only_until_causality_and_anti_leak_qc_pass",
        },
        {
            "priority": 2,
            "candidate_source_adapter": "bears_failing_passing_repair_adapter",
            "source_family": "Bears/RepairThemAll",
            "candidate_count": bears.get("failing_passing_candidates")
            or bears_contract.get("candidate_count"),
            "summary_source_stages": [
                "stage12327_external_adapter_preflight",
                "stage12328_external_adapter_qc_materialization_request",
            ],
            "private_raw_visible_review_packet_scope": (
                "hydrate failing_passing candidates for private review; passing_passing rows remain blocked"
            ),
            "schema_requirements": bears_contract.get("admission_requires", []),
            "hard_rejects": bears_contract.get("hard_rejects", []),
            "admission_boundary": "external_repair_candidate_only_until_checkout_verifier_causality_pass",
        },
        {
            "priority": 3,
            "candidate_source_adapter": "normalized_exact_verifier_identity_adapter",
            "source_family": "external_normalized_verifier_candidates",
            "candidate_count": stage12280.get("candidate_count"),
            "summary_source_stages": [
                "stage12280_external_normalized_verifier_identity_selector",
                "stage12281_semantic_review_packet_normalized_exact_verifiers",
            ],
            "private_raw_visible_review_packet_scope": (
                "continue semantic review of normalized exact verifier identities before any train-support use"
            ),
            "schema_requirements": [
                "root_id",
                "repo_family",
                "verifier_identity_class",
                "pre_post_status_class",
                "semantic_relevance_decision",
                "anti_leak_rendering_pass",
            ],
            "hard_rejects": [
                "raw command text in model-facing fields",
                "verifier identity without semantic relevance decision",
            ],
            "admission_boundary": "review_packet_only_no_training_admission",
        },
        {
            "priority": 4,
            "candidate_source_adapter": "transition_local_materializer_external_root_upgrade",
            "source_family": "transition_local_recovery_worklist",
            "candidate_count": stage12387.get("worklist_count"),
            "summary_source_stages": ["stage12387_transition_local_materializer_upgrade_worklist"],
            "private_raw_visible_review_packet_scope": (
                "recover missing transition-local fields into safe schema, then pivot non-self roots first"
            ),
            "schema_requirements": (
                stage12387.get("stage12206_control_contract", {}).get("required_level3_control_fields", [])
            ),
            "hard_rejects": [
                "observation support row promoted to causal transition without new review",
                "observed action promoted to policy gold without manual label review",
            ],
            "admission_boundary": "worklist_only_until_non_self_identity_and_full_control_contract_pass",
        },
    ]
    return [sanitize_summary_fragment(row) for row in worklist]


def summarize_spine(spine: dict[str, dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for stage, summary in spine.items():
        if not summary:
            out[stage] = {"exists": False}
            continue
        fragment = {
            "exists": True,
            "decision": summary.get("decision"),
            "training_allowed": summary.get("training_allowed"),
            "admitted_rows": summary.get("admitted_rows"),
            "claim_boundary": summary.get("claim_boundary"),
        }
        strings = flatten_strings(summary)
        adapter_mentions = sorted(
            {
                text
                for text in strings
                if any(token in text.lower() for token in ["open-swe", "bears", "external", "source_heldout"])
                and not any(pattern.search(text) for pattern in FORBIDDEN_TEXT_PATTERNS)
            }
        )
        if adapter_mentions:
            fragment["sanitized_adapter_or_pivot_mentions"] = adapter_mentions[:10]
        out[stage] = sanitize_summary_fragment(fragment)
    return out


def write_markdown(summary: dict[str, Any]) -> None:
    why = summary["stage12391_training_rejection"]
    worklist = summary["external_root_pivot_worklist"]
    lines = [
        "# Stage12392 Raw-Visible Review Packet Builder Or External Root Pivot",
        "",
        "Fail-closed non-training stage. It does not emit model-facing raw paths, commands, outputs, or patch bodies.",
        "",
        f"Stage12391 reviewed packets: `{why['reviewed_packets']}`",
        f"Stage12391 blocked packets: `{why['blocked_packets']}`",
        f"Training allowed: `{summary['training_allowed']}`",
        f"Level-3 admitted: `{summary['level3_admitted']}`",
        f"Patch-trace admitted: `{summary['patch_trace_admitted']}`",
        f"Strict-eval eligible: `{summary['strict_eval_eligible']}`",
        f"Source-heldout admissible: `{summary['source_heldout_admissible']}`",
        "",
        "## Pivot Worklist",
    ]
    for item in worklist:
        lines.append(
            f"- P{item['priority']} `{item['candidate_source_adapter']}`: "
            f"{item.get('candidate_count')} candidates; boundary `{item['admission_boundary']}`"
        )
    lines.extend(
        [
            "",
            "No Stage12391 self-repo packet is admitted as a training row. The next useful move is private "
            "raw-visible review packet construction for external/non-self sources followed by a separate admission gate.",
        ]
    )
    (OUT / "RAW_VISIBLE_REVIEW_PACKET_EXTERNAL_ROOT_PIVOT_STAGE12392.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def assert_no_forbidden_artifact_text(paths: list[Path]) -> None:
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_TEXT_PATTERNS:
            if pattern.search(text):
                raise RuntimeError(f"forbidden raw-like text emitted in {path.relative_to(ROOT)}")


def main() -> None:
    reviewed_rows = read_jsonl(STAGE12391_REVIEWED)
    blocked_rows = read_jsonl(STAGE12391_BLOCKED)
    stage12391_summary = read_json(STAGE12391_SUMMARY)
    counts = packet_counts(reviewed_rows)
    spine = load_spine_summaries()
    worklist = build_adapter_worklist(spine)

    summary = {
        "stage": STAGE,
        "decision": "fail_closed_self_repo_packets_blocked_external_raw_visible_pivot_ready",
        "claim_boundary": (
            "Non-training pivot artifact only. Stage12391 self-repo packets are summarized for counts and "
            "blocker categories; no model-facing raw paths, commands, outputs, source text, or patch bodies are emitted."
        ),
        "input_stage_counts": {
            "stage12391_reviewed_packets": len(reviewed_rows),
            "stage12391_blocked_packets": len(blocked_rows),
            "stage12391_admitted_packets": count_jsonl(STAGE12391_ADMITTED),
            "central_spine_summaries_loaded": sum(1 for item in spine.values() if item),
            "central_spine_summaries_requested": len(CENTRAL_SPINE_SUMMARIES),
        },
        "training_allowed": False,
        "new_training_rows_emitted": 0,
        "level3_admitted": 0,
        "patch_trace_admitted": 0,
        "strict_eval_eligible": 0,
        "source_heldout_admissible": 0,
        "raw_visibility_boundary": {
            "model_facing_raw_paths_emitted": False,
            "model_facing_raw_commands_emitted": False,
            "model_facing_raw_outputs_emitted": False,
            "model_facing_patch_bodies_emitted": False,
            "private_reviewer_raw_visibility_may_be_built_in_next_stage": True,
        },
        "stage12391_training_rejection": why_stage12391_cannot_train(stage12391_summary, counts),
        "stage12391_sanitized_counts": counts,
        "central_spine_sanitized_summary": summarize_spine(spine),
        "external_root_pivot_worklist_count": len(worklist),
        "external_root_pivot_worklist": worklist,
        "next_stage_contract": {
            "required_action": "build_private_reviewer_packets_from_external_or_non_self_raw_visible_sources",
            "must_remain_fail_closed_until": [
                "non_self_repo_identity_proven",
                "safe semantic extraction completed",
                "selected verifier relevance semantically proven",
                "state delta semantics proven",
                "anti_leak rendering check passes",
                "separate training_admission_gate passes",
            ],
            "minimum_schema_for_private_review_packet": [
                "root_id",
                "repo_family",
                "language_family",
                "source_adapter_name",
                "private_raw_record_ref",
                "safe_state_before_codes",
                "candidate_action_set_opaque",
                "chosen_action_semantic_type_for_review_only",
                "verifier_identity_class",
                "observation_status_class",
                "state_delta_codes",
                "semantic_review_questions",
                "anti_leak_rendering_status",
                "training_allowed_false",
            ],
        },
    }

    OUT.mkdir(parents=True, exist_ok=True)
    worklist_path = OUT / "external_root_private_review_packet_pivot_worklist.jsonl"
    summary_path = OUT / "summary.json"
    write_jsonl(worklist_path, worklist)
    write_json(summary_path, summary)
    write_json(SUMMARY, summary)
    write_markdown(summary)
    assert_no_forbidden_artifact_text(
        [
            worklist_path,
            summary_path,
            SUMMARY,
            OUT / "RAW_VISIBLE_REVIEW_PACKET_EXTERNAL_ROOT_PIVOT_STAGE12392.md",
        ]
    )


if __name__ == "__main__":
    main()
