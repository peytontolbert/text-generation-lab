#!/usr/bin/env python3
"""Build a public-safe local-model concept proposal queue.

Stage12490 is a proposal-only bridge after Stage12489. It consumes safe hashed
metadata from prior stages and emits concept proposals for later semantic
review. It does not train, admit rows, hydrate private source, execute proof
work, or claim repair credit.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12490_local_model_concept_proposal_queue"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

INPUT_JSON = {
    "stage12295": ROOT / "runs/summaries/stage12295_transition_function_ledger.json",
    "stage12320": ROOT / "runs/summaries/stage12320_event_local_semantic_review_admission.json",
    "stage12441": ROOT / "runs/summaries/stage12441_embedding_transition_candidate_expansion_gate.json",
    "stage12488": ROOT / "runs/summaries/stage12488_source_to_private_proof_bundle_funnel.json",
    "stage12489": ROOT / "runs/summaries/stage12489_anti_collapse_dataset_generation_contract.json",
}
STAGE12441_REPRESENTATIVES = (
    ROOT
    / "runs/local/artifacts/stage12441_embedding_transition_candidate_expansion_gate"
    / "candidate_embedding_representative_priority_records.jsonl"
)
STAGE12489_GATES = (
    ROOT
    / "runs/local/artifacts/stage12489_anti_collapse_dataset_generation_contract"
    / "anti_collapse_gates.jsonl"
)

FALSE_GUARDS = {
    "training_allowed": False,
    "admission_allowed": False,
    "reviewed_train_support": False,
    "proof_grade_repair": False,
    "external_repair_credit_allowed": False,
    "execution_performed_by_stage": False,
    "hydration_performed_by_stage": False,
    "network_performed_by_stage": False,
}
ZERO_GUARDS = {
    "emitted_training_rows": 0,
    "admitted_rows": 0,
    "reviewed_train_support_rows": 0,
    "proof_grade_repair_rows": 0,
    "external_repair_credit_count": 0,
    "sealed_eval_rows": 0,
}
RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:git clone|git apply|pytest\s|python -c|bash -|sh -|curl\s|"
    r"stdout|stderr|traceback|terminal output|command output)\b|"
    r"\b[0-9a-f]{40}\b",
    re.IGNORECASE | re.MULTILINE,
)
FORBIDDEN_KEYS = {
    "body",
    "cmd",
    "command",
    "commit",
    "content",
    "diff",
    "file_path",
    "patch",
    "path",
    "private_locator",
    "raw",
    "raw_text",
    "repo",
    "repository",
    "sha",
    "source",
    "source_text",
    "stderr",
    "stdout",
    "text",
    "trace_text",
    "uri",
    "url",
}

CONCEPT_VARIANT_FAMILIES = [
    "independent_policy_label_concept",
    "state_delta_code_concept",
    "verifier_status_transition_concept",
    "stop_continue_boundary_concept",
    "hard_negative_family_concept",
    "proof_boundary_noncredit_concept",
]


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:n]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def as_int(value: Any, default: int = 0) -> int:
    return value if isinstance(value, int) else default


def safe_key_hashes(mapping: Any) -> list[str]:
    if not isinstance(mapping, dict):
        return []
    return [stable_hash(key) for key in sorted(str(key) for key in mapping) if key and key != "MISSING"]


def gate_results(row: dict[str, Any], source_share: float, cluster_share: float) -> dict[str, str]:
    local_model_status = row.get("local_model_inference_status")
    return {
        "no_observed_action_imitation": "pass_target_is_concept_proposal_not_observed_action",
        "candidate_role_entropy": "pass_role_varied_by_concept_variant_family",
        "template_similarity_cap": "blocked_for_train_support" if cluster_share > 0.20 else "pass",
        "source_family_cap": "blocked_for_train_support" if source_share > 0.15 else "pass",
        "proof_training_separation": "pass_zero_training_rows_zero_proof_credit",
        "renderer_consistency": "pending_not_rendered_as_training_row",
        "local_model_non_authority": (
            "pass_embedding_priority_only"
            if local_model_status == "safe_embedding_priority_available"
            else "pass_local_model_inference_pending"
        ),
    }


def proposal_from_representative(
    row: dict[str, Any],
    rank: int,
    source_share: float,
    cluster_share: float,
    local_embedding_available: bool,
) -> dict[str, Any]:
    variant = CONCEPT_VARIANT_FAMILIES[(rank - 1) % len(CONCEPT_VARIANT_FAMILIES)]
    local_model_status = (
        "safe_embedding_priority_available"
        if local_embedding_available
        else "generative_local_model_inference_pending_safe_unavailable"
    )
    proposal = {
        "record_type": "stage12490_concept_proposal_queue_item_v1",
        "proposal_id_hash": stable_hash(
            {
                "candidate_id_hash": row.get("candidate_id_hash"),
                "variant": variant,
                "rank": rank,
            }
        ),
        "proposal_rank": rank,
        "proposal_lane": "concept_proposal_only",
        "proposal_review_status": "requires_stage12491_semantic_review_before_train_support",
        "concept_variant_family": variant,
        "source_stage_refs": [
            "stage12441_embedding_transition_candidate_expansion_gate",
            "stage12489_anti_collapse_dataset_generation_contract",
        ],
        "transition_function_key_hash": row.get("transition_function_key_hash"),
        "semantic_rule_candidate_hash": stable_hash(
            {
                "semantic_rule_id_hash": row.get("semantic_rule_id_hash"),
                "variant": variant,
            }
        ),
        "state_code_candidate_hash": stable_hash(
            {
                "transition_function_key_hash": row.get("transition_function_key_hash"),
                "task_family": row.get("task_family"),
                "variant": variant,
            }
        ),
        "hard_negative_family_hash": stable_hash(
            {
                "candidate_action_set_hash": row.get("candidate_action_set_hash"),
                "blocked_reason_hashes": row.get("blocked_reason_code_hashes") or [],
            }
        ),
        "novelty_cluster_id_hash": row.get("embedding_cluster_id_hash"),
        "deterministic_duplicate_cluster_id_hash": row.get("deterministic_duplicate_cluster_id_hash"),
        "root_lineage_key_hash": row.get("root_lineage_key_hash"),
        "split_group_id_hash": row.get("split_group_id_hash"),
        "source_cluster_key_hash": row.get("source_cluster_key_hash"),
        "language_family": row.get("language_family") or "unknown",
        "task_family": row.get("task_family") or "unknown",
        "priority_bucket": row.get("priority_bucket") or "unknown",
        "novelty_bucket": row.get("novelty_bucket") or "unknown",
        "max_similarity_bucket": row.get("max_similarity_bucket") or "unknown",
        "represented_candidate_count": as_int(row.get("represented_candidate_count")),
        "review_priority": {
            "source_rank": rank,
            "embedding_priority_score_bucket": row.get("max_similarity_bucket") or "unknown",
            "priority_basis": "safe_metadata_embedding_rank_and_anti_collapse_risk_only",
        },
        "local_model_inference_status": local_model_status,
        "local_model_output_used": local_embedding_available,
        "generative_local_model_inference_pending": True,
        "claim_boundary": {
            "concept_proposal": True,
            "reviewed_train_support": False,
            "proof_grade_repair": False,
        },
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    proposal["anti_collapse_gate_results"] = gate_results(proposal, source_share, cluster_share)
    blocked = [
        gate_id
        for gate_id, status in proposal["anti_collapse_gate_results"].items()
        if status.startswith("blocked")
    ]
    proposal["anti_collapse_train_support_blockers"] = blocked
    proposal["eligible_for_stage12491_review"] = not blocked
    proposal["eligible_for_training_or_admission"] = False
    return proposal


def aggregate_proposal(
    *,
    rank: int,
    concept_variant_family: str,
    basis_stage: str,
    task_family: str,
    semantic_key_hashes: list[str],
    local_embedding_available: bool,
) -> dict[str, Any]:
    local_model_status = (
        "safe_embedding_context_available"
        if local_embedding_available
        else "generative_local_model_inference_pending_safe_unavailable"
    )
    proposal = {
        "record_type": "stage12490_concept_proposal_queue_item_v1",
        "proposal_id_hash": stable_hash(
            {
                "basis_stage": basis_stage,
                "concept_variant_family": concept_variant_family,
                "task_family": task_family,
                "semantic_key_hashes": semantic_key_hashes,
            }
        ),
        "proposal_rank": rank,
        "proposal_lane": "concept_proposal_only",
        "proposal_review_status": "requires_stage12491_semantic_review_before_train_support",
        "concept_variant_family": concept_variant_family,
        "source_stage_refs": [basis_stage, "stage12489_anti_collapse_dataset_generation_contract"],
        "transition_function_key_hash": stable_hash({"basis_stage": basis_stage, "task_family": task_family}),
        "semantic_rule_candidate_hash": stable_hash(semantic_key_hashes),
        "state_code_candidate_hash": stable_hash({"task_family": task_family, "concept_variant_family": concept_variant_family}),
        "hard_negative_family_hash": stable_hash({"basis_stage": basis_stage, "semantic_key_hashes": semantic_key_hashes}),
        "novelty_cluster_id_hash": stable_hash({"aggregate": basis_stage, "task_family": task_family}),
        "language_family": "mixed_or_unknown_public_metadata",
        "task_family": task_family,
        "priority_bucket": "aggregate_safe_metadata_gap_fill",
        "novelty_bucket": "metadata_aggregate_not_vector_scored",
        "max_similarity_bucket": "metadata_aggregate_not_vector_scored",
        "review_priority": {
            "source_rank": rank,
            "priority_basis": "aggregate_public_safe_summary_gap_fill",
        },
        "local_model_inference_status": local_model_status,
        "local_model_output_used": False,
        "generative_local_model_inference_pending": True,
        "claim_boundary": {
            "concept_proposal": True,
            "reviewed_train_support": False,
            "proof_grade_repair": False,
        },
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    proposal["anti_collapse_gate_results"] = {
        "no_observed_action_imitation": "pass_target_is_concept_proposal_not_observed_action",
        "candidate_role_entropy": "pass_aggregate_variant_counterbalances_embedding_representatives",
        "template_similarity_cap": "pending_stage12491_review",
        "source_family_cap": "pending_stage12491_review",
        "proof_training_separation": "pass_zero_training_rows_zero_proof_credit",
        "renderer_consistency": "pending_not_rendered_as_training_row",
        "local_model_non_authority": "pass_local_model_hint_not_gold",
    }
    proposal["anti_collapse_train_support_blockers"] = [
        "template_similarity_pending_review",
        "source_family_share_pending_review",
    ]
    proposal["eligible_for_stage12491_review"] = True
    proposal["eligible_for_training_or_admission"] = False
    return proposal


def iter_strings(value: Any) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    if isinstance(value, str):
        pairs.append(("", value))
    elif isinstance(value, dict):
        for key, child in value.items():
            pairs.extend((f"{key}.{path}" if path else str(key), text) for path, text in iter_strings(child))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            pairs.extend((f"{index}.{path}" if path else str(index), text) for path, text in iter_strings(child))
    return pairs


def scan_payload(payload: Any) -> dict[str, Any]:
    issues: list[str] = []
    for path, text in iter_strings(payload):
        leaf = path.rsplit(".", 1)[-1].lower()
        if leaf in FORBIDDEN_KEYS:
            issues.append(f"forbidden_key:{stable_hash(path)}")
        if RAW_LEAK_RE.search(text):
            issues.append(f"raw_pattern:{stable_hash(text)}")
    return {
        "scan_passed": not issues,
        "raw_leak_count": len(issues),
        "issues": sorted(set(issues))[:80],
        "scan_scope": "stage12490_public_safe_concept_proposal_artifacts",
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    inputs = {name: read_json(path) for name, path in INPUT_JSON.items()}
    representatives = read_jsonl(STAGE12441_REPRESENTATIVES)
    gates = read_jsonl(STAGE12489_GATES)

    stage12441 = inputs["stage12441"]
    local_embedding_available = bool(
        representatives
        and stage12441.get("guardrail_scan_passed") is True
        and stage12441.get("embedding_backend_status")
    )
    total_vectors = max(1, as_int(stage12441.get("candidate_vector_count"), len(representatives)))
    largest_cluster_share = float(stage12441.get("near_duplicate_cluster_max_share") or 0.0)
    source_counts = Counter(str(row.get("source_adapter") or "unknown") for row in representatives)

    queue: list[dict[str, Any]] = []
    for rank, row in enumerate(representatives, start=1):
        source_share = source_counts[str(row.get("source_adapter") or "unknown")] / max(1, len(representatives))
        queue.append(
            proposal_from_representative(
                row,
                rank,
                source_share,
                largest_cluster_share,
                local_embedding_available,
            )
        )

    next_rank = len(queue) + 1
    stage12295_task_counts = inputs["stage12295"].get("train_task_family_counts") or {}
    for task_family in sorted(stage12295_task_counts)[:6]:
        queue.append(
            aggregate_proposal(
                rank=next_rank,
                concept_variant_family="ledger_task_family_counterbalance_concept",
                basis_stage="stage12295_transition_function_ledger",
                task_family=str(task_family),
                semantic_key_hashes=[stable_hash(task_family)],
                local_embedding_available=local_embedding_available,
            )
        )
        next_rank += 1

    stage12320_rule_counts = inputs["stage12320"].get("semantic_rule_counts") or {}
    for semantic_rule_hash in safe_key_hashes(stage12320_rule_counts)[:6]:
        queue.append(
            aggregate_proposal(
                rank=next_rank,
                concept_variant_family="reviewed_status_rule_counterbalance_concept",
                basis_stage="stage12320_event_local_semantic_review_admission",
                task_family="event_local_transition_observation",
                semantic_key_hashes=[semantic_rule_hash],
                local_embedding_available=local_embedding_available,
            )
        )
        next_rank += 1

    if inputs["stage12488"].get("remaining_external_fail_to_pass_gap"):
        queue.append(
            aggregate_proposal(
                rank=next_rank,
                concept_variant_family="proof_boundary_gap_concept_noncredit",
                basis_stage="stage12488_source_to_private_proof_bundle_funnel",
                task_family="proof_boundary_not_train_support",
                semantic_key_hashes=[stable_hash(inputs["stage12488"].get("remaining_external_fail_to_pass_gap"))],
                local_embedding_available=local_embedding_available,
            )
        )

    task_family_counts = Counter(str(row.get("task_family")) for row in queue)
    language_counts = Counter(str(row.get("language_family")) for row in queue)
    variant_counts = Counter(str(row.get("concept_variant_family")) for row in queue)
    blocked_for_train_support = sum(1 for row in queue if row.get("anti_collapse_train_support_blockers"))
    blocker_counts = Counter(
        blocker
        for row in queue
        for blocker in row.get("anti_collapse_train_support_blockers", [])
    )
    representative_rows = sum(1 for row in queue if "stage12441_embedding_transition_candidate_expansion_gate" in row["source_stage_refs"])
    aggregate_rows = len(queue) - representative_rows
    summary = {
        "stage": STAGE,
        "record_type": "stage12490_local_model_concept_proposal_queue_summary_v1",
        "decision": "concept_proposal_queue_ready_no_training_no_admission_no_proof",
        "claim_boundary": "Proposal queue only. Local embeddings are priority hints, generative local-model inference is pending, and no row becomes reviewed train support or proof-grade repair in this stage.",
        "source_stage_refs": sorted(INPUT_JSON),
        "input_file_hashes": {name: file_hash(path) for name, path in INPUT_JSON.items()},
        "stage12489_gate_ids": [gate.get("gate_id") for gate in gates],
        "stage12489_gate_count": len(gates),
        "proposal_queue_rows": len(queue),
        "stage12441_representative_proposal_rows": representative_rows,
        "aggregate_safe_metadata_proposal_rows": aggregate_rows,
        "blocked_from_train_support_by_anti_collapse_rows": blocked_for_train_support,
        "eligible_for_stage12491_review_rows": sum(1 for row in queue if row.get("eligible_for_stage12491_review")),
        "eligible_for_training_or_admission_rows": 0,
        "local_embedding_outputs_available": local_embedding_available,
        "local_embeddings_available": local_embedding_available,
        "local_embedding_backend_status": stage12441.get("embedding_backend_status") or "unavailable",
        "generative_local_model_inference_status": "pending_safe_unavailable",
        "generative_local_model_inference": "pending_safe_unavailable",
        "near_duplicate_cluster_max_share": largest_cluster_share,
        "template_similarity_cap_enforced": True,
        "source_family_cap_enforced": True,
        "blocked_reason_counts": dict(sorted(blocker_counts.items())),
        "task_family_counts": dict(sorted(task_family_counts.items())),
        "language_family_counts": dict(sorted(language_counts.items())),
        "concept_variant_family_counts": dict(sorted(variant_counts.items())),
        "next_stage": "stage12491_concept_proposal_semantic_review_gate",
        "non_actions": [
            "does_not_train",
            "does_not_admit_rows",
            "does_not_emit_training_rows",
            "does_not_execute_private_proof",
            "does_not_claim_external_repair_credit",
            "does_not_emit_raw_private_values",
        ],
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    guardrail = scan_payload({"summary": summary, "queue": queue})
    summary["guardrail_scan_passed"] = guardrail["scan_passed"]
    summary["raw_leak_count"] = guardrail["raw_leak_count"]
    summary["summary_hash"] = stable_hash(summary)

    artifact = {
        **summary,
        "local_model_use_policy": {
            "safe_embedding_outputs_allowed_as_priority_hints": True,
            "generative_model_outputs_allowed_as_gold": False,
            "generative_model_outputs_status": "pending_safe_unavailable",
            "local_model_outputs_used_for_training": False,
            "local_model_outputs_used_for_admission": False,
            "local_model_outputs_used_as_proof": False,
        },
        "artifact_manifest": [
            {
                "artifact_name": "local_model_concept_proposal_queue.jsonl",
                "public_safe": True,
                "contains_raw_values": False,
                "proposal_only": True,
            },
            {
                "artifact_name": "summary.json",
                "public_safe": True,
                "contains_raw_values": False,
                "proposal_only": True,
            },
        ],
    }

    write_jsonl(OUT / "local_model_concept_proposal_queue.jsonl", queue)
    write_json(OUT / "local_model_concept_proposal_queue_summary.json", artifact)
    write_json(OUT / "guardrail_scan.json", guardrail)
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY, summary)


if __name__ == "__main__":
    main()
