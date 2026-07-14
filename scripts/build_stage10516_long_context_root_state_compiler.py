from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10516
NAME = "stage10516_long_context_root_state_compiler"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME

PLAN_JSON = ROOT / "runs/local/artifacts/stage10515_root_based_seq2seq_curriculum_plan/root_based_seq2seq_curriculum_plan.json"
ROOT_SCHEMA_JSON = ROOT / "runs/local/artifacts/stage10515_root_based_seq2seq_curriculum_plan/canonical_maintainer_root_schema.json"
STATE_SCHEMA_JSON = ROOT / "runs/local/artifacts/stage10515_root_based_seq2seq_curriculum_plan/causal_state_projection_schema.json"

RAW_PACK_ROWS = ROOT / "runs/local/artifacts/merged_packable_examples/strict_commit_plus_strict_session_strict_packs_5m_familyfiltered_tuned_groupcap12_hardened_v2/strict_long_context_pack_training_rows.jsonl"
RAW_PACK_SUMMARY = ROOT / "runs/local/artifacts/merged_packable_examples/strict_commit_plus_strict_session_strict_packs_5m_familyfiltered_tuned_groupcap12_hardened_v2/strict_long_context_packs_summary.json"
AUDITED_RETRIEVAL_ROWS = ROOT / "runs/local/artifacts/strict_long_context_train_ready_plus_audit_v1/retrieval_rows.jsonl"
AUDITED_FULL_ROWS = ROOT / "runs/local/artifacts/strict_long_context_train_ready_plus_audit_v1/full_context_rows.jsonl"
AUDITED_CARD = ROOT / "runs/local/artifacts/strict_long_context_train_ready_plus_audit_v1/strict_long_context_training_dataset_card.json"

ROOTS_JSONL = OUT_DIR / "compiled_root_records.jsonl"
EPISODES_JSONL = OUT_DIR / "compiled_episode_records.jsonl"
EVENTS_JSONL = OUT_DIR / "compiled_typed_events.jsonl"
STATES_JSONL = OUT_DIR / "compiled_causal_states.jsonl"
ROWS_JSONL = OUT_DIR / "compiled_multitarget_rows.jsonl"
SUMMARY_JSON = OUT_DIR / "long_context_root_state_compiler.json"
RUN_SUMMARY_JSON = ROOT / "runs/summaries" / f"{NAME}.json"

QUERY_RE = re.compile(r"^\[(\d+)\]\s", re.MULTILINE)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def split_pack_queries(prompt_text: str) -> dict[int, str]:
    matches = list(QUERY_RE.finditer(prompt_text))
    if not matches:
        return {}
    sections: dict[int, str] = {}
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(prompt_text)
        query_index = int(match.group(1))
        sections[query_index] = prompt_text[start:end].strip()
    return sections


def parse_state_json(raw: str) -> dict[str, Any]:
    raw = (raw or "").strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def is_prompt_target_leak(metadata: dict[str, Any]) -> bool:
    risk = str(metadata.get("label_leakage_risk", "")).strip().lower()
    return risk in {"medium", "high", "critical", "true", "yes", "1"}


def normalize_repo_id(value: str) -> str:
    value = value.strip()
    if value == "peytontolbert-parameter-golf":
        return "parametergolf"
    return value


def infer_language_from_paths(paths: list[str]) -> str:
    counts = Counter()
    for path in paths:
        lowered = path.lower()
        if lowered.endswith((".py", ".pyi")):
            counts["python"] += 1
        elif lowered.endswith((".rs",)):
            counts["rust"] += 1
        elif lowered.endswith((".c", ".cc", ".cpp", ".cu", ".cuh", ".h", ".hpp")):
            counts["c_cpp"] += 1
        elif lowered.endswith((".js", ".jsx", ".ts", ".tsx", ".html", ".css")):
            counts["web_js_ts_html"] += 1
    if counts:
        return counts.most_common(1)[0][0]
    return "unknown"


def infer_language_from_query_text(query_text: str) -> str:
    candidates: list[str] = []
    prefixes = ('Changed files:', 'Verification targets:')
    for line in query_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith(prefixes):
            continue
        _, _, remainder = stripped.partition(':')
        parts = [part.strip() for part in remainder.split(',') if part.strip()]
        candidates.extend(parts)
    return infer_language_from_paths(candidates)


def language_from_repo(repo_id: str, changed_paths: list[str] | None = None, query_text: str | None = None) -> str:
    mapping = {
        "agentkernel": "python",
        "parametergolf": "c_cpp",
        "repository_library": "python",
    }
    direct = mapping.get(repo_id)
    if direct is not None:
        return direct
    if changed_paths:
        inferred = infer_language_from_paths(changed_paths)
        if inferred != "unknown":
            return inferred
    if query_text:
        inferred = infer_language_from_query_text(query_text)
        if inferred != "unknown":
            return inferred
    return "unknown"


def route_to_action(route: str) -> str:
    mapping = {
        "PATCH_PLUS_EXEC": "APPLY_PATCH_AND_VERIFY",
        "COMMIT_PLUS_VERIFY": "INSPECT_AND_VERIFY_COMMIT_STATE",
    }
    return mapping.get(route, "INSPECT_AND_DECIDE")


def infer_events_for_raw_root(
    *,
    root_id: str,
    episode_id: str,
    query_text: str,
    final_state: dict[str, Any],
    final_answer: str,
) -> list[dict[str, Any]]:
    changed_files = final_state.get("expected_changed_files", [])
    verification_targets = final_state.get("verification_targets", [])
    events: list[dict[str, Any]] = [
        {
            "event_id": f"{episode_id}::ev001",
            "root_id": root_id,
            "episode_id": episode_id,
            "event_index": 1,
            "event_type": "USER_TASK",
            "actor": "trace_compiler_inferred",
            "timestamp_utc": None,
            "content": query_text,
            "artifact_refs": [],
        }
    ]
    if changed_files:
        events.append(
            {
                "event_id": f"{episode_id}::ev002",
                "root_id": root_id,
                "episode_id": episode_id,
                "event_index": 2,
                "event_type": "PATCH",
                "actor": "trace_compiler_inferred",
                "timestamp_utc": None,
                "content": json.dumps({"expected_changed_files": changed_files}, sort_keys=True),
                "artifact_refs": changed_files,
            }
        )
    if verification_targets:
        events.append(
            {
                "event_id": f"{episode_id}::ev003",
                "root_id": root_id,
                "episode_id": episode_id,
                "event_index": 3,
                "event_type": "TEST_RESULT",
                "actor": "trace_compiler_inferred",
                "timestamp_utc": None,
                "content": json.dumps(
                    {
                        "test_selection_route": final_state.get("test_selection_route"),
                        "verification_targets": verification_targets,
                    },
                    sort_keys=True,
                ),
                "artifact_refs": verification_targets,
            }
        )
    events.append(
        {
            "event_id": f"{episode_id}::ev999",
            "root_id": root_id,
            "episode_id": episode_id,
            "event_index": len(events) + 1,
            "event_type": "FINAL_RESPONSE",
            "actor": "trace_compiler_inferred",
            "timestamp_utc": None,
            "content": final_answer,
            "artifact_refs": [],
        }
    )
    return events


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RUN_SUMMARY_JSON.parent.mkdir(parents=True, exist_ok=True)

    plan = load_json(PLAN_JSON)
    root_schema = load_json(ROOT_SCHEMA_JSON)
    state_schema = load_json(STATE_SCHEMA_JSON)
    raw_pack_row = load_jsonl(RAW_PACK_ROWS)[0]
    raw_pack_summary = load_json(RAW_PACK_SUMMARY)
    retrieval_rows = load_jsonl(AUDITED_RETRIEVAL_ROWS)
    full_rows = load_jsonl(AUDITED_FULL_ROWS)
    audited_card = load_json(AUDITED_CARD)

    query_sections = split_pack_queries(raw_pack_row["prompt_text"])

    root_records: list[dict[str, Any]] = []
    episode_records: list[dict[str, Any]] = []
    event_records: list[dict[str, Any]] = []
    state_records: list[dict[str, Any]] = []
    multitarget_rows: list[dict[str, Any]] = []

    # Raw pack query roots: compile bootstrap root/episode/state rows from the merged hardened 5M pack.
    for target in raw_pack_row["target_rows"]:
        query_index = int(target["query_index"])
        repo_id = normalize_repo_id(target["program_id"])
        root_id = f"rawpack::{raw_pack_row['pack_id']}::q{query_index}"
        episode_id = f"{root_id}::episode0"
        state_id = f"{episode_id}::state_final_query_projection"
        final_state = parse_state_json(target.get("final_state_json", ""))
        query_text = query_sections.get(query_index, f"[{query_index}] query_not_recovered")
        language_family = language_from_repo(repo_id, final_state.get("expected_changed_files", []), query_text)

        root_records.append(
            {
                "root_id": root_id,
                "repo_id": repo_id,
                "repo_family": repo_id,
                "language_family": language_family,
                "task_family": "software_maintenance_query",
                "snapshot_id": raw_pack_row["pack_id"],
                "environment_id": "long_context_pack_inferred",
                "verifier_id": final_state.get("test_selection_route", "UNKNOWN"),
                "provenance": {
                    "source_family_id": "merged_packable_examples_hardened_v2",
                    "pack_id": raw_pack_row["pack_id"],
                    "example_id": target["example_id"],
                    "query_index": query_index,
                },
                "split_component": "train_bootstrap_long_context",
            }
        )
        episode_records.append(
            {
                "episode_id": episode_id,
                "root_id": root_id,
                "episode_kind": "long_context_query_projection",
                "agent_family": "trace_compiler_inferred",
                "start_state_id": state_id,
                "terminal_state_id": state_id,
                "outcome_grade": final_state.get("execution_route", "UNKNOWN"),
            }
        )
        event_records.extend(
            infer_events_for_raw_root(
                root_id=root_id,
                episode_id=episode_id,
                query_text=query_text,
                final_state=final_state,
                final_answer=target["final_answer"],
            )
        )
        state_records.append(
            {
                "state_id": state_id,
                "episode_id": episode_id,
                "root_id": root_id,
                "event_span": [f"{episode_id}::ev001", f"{episode_id}::ev999"],
                "state_kind": "query_terminal_supervision",
                "visible_evidence_ids": [],
                "candidate_set_ids": [],
                "hypothesis_status": "teacher_supplied_terminal_state",
                "input_view_id": "context_pack_state",
                "query_text": query_text,
                "final_state": final_state,
            }
        )
        multitarget_rows.extend(
            [
                {
                    "row_id": f"{state_id}::next_action",
                    "root_id": root_id,
                    "episode_id": episode_id,
                    "state_id": state_id,
                    "split_component": "train_bootstrap_long_context",
                    "target_family": "short_structured_text",
                    "target_subtype": "next_action",
                    "input_text": query_text,
                    "target_text": json.dumps(
                        {
                            "action": route_to_action(final_state.get("execution_route", "UNKNOWN")),
                            "repo_id": repo_id,
                            "expected_information": final_state.get("test_selection_route", "UNKNOWN"),
                        },
                        sort_keys=True,
                    ),
                    "anti_cheat": {
                        "same_root_train_eval_forbidden": True,
                        "prompt_target_leak": False,
                    },
                },
                {
                    "row_id": f"{state_id}::verifier_outcome",
                    "root_id": root_id,
                    "episode_id": episode_id,
                    "state_id": state_id,
                    "split_component": "train_bootstrap_long_context",
                    "target_family": "bounded_decision",
                    "target_subtype": "verifier_outcome",
                    "input_text": query_text,
                    "target_text": final_state.get("test_selection_route", "UNKNOWN"),
                    "anti_cheat": {
                        "same_root_train_eval_forbidden": True,
                        "prompt_target_leak": False,
                    },
                },
                {
                    "row_id": f"{state_id}::repair_intent",
                    "root_id": root_id,
                    "episode_id": episode_id,
                    "state_id": state_id,
                    "split_component": "train_bootstrap_long_context",
                    "target_family": "short_structured_text",
                    "target_subtype": "repair_intent",
                    "input_text": query_text,
                    "target_text": target["final_answer"],
                    "anti_cheat": {
                        "same_root_train_eval_forbidden": True,
                        "prompt_target_leak": False,
                    },
                },
                {
                    "row_id": f"{state_id}::patch_sketch",
                    "root_id": root_id,
                    "episode_id": episode_id,
                    "state_id": state_id,
                    "split_component": "train_bootstrap_long_context",
                    "target_family": "constrained_generation",
                    "target_subtype": "patch_sketch",
                    "input_text": query_text,
                    "target_text": json.dumps(
                        {
                            "execution_route": final_state.get("execution_route"),
                            "expected_changed_files": final_state.get("expected_changed_files", []),
                            "verification_targets": final_state.get("verification_targets", []),
                        },
                        sort_keys=True,
                    ),
                    "anti_cheat": {
                        "same_root_train_eval_forbidden": True,
                        "prompt_target_leak": False,
                    },
                },
            ]
        )

    # Audited retrieval teacher states: compile evaluation-safe causal evidence states.
    for row in retrieval_rows:
        target = parse_state_json(row["target_text"])
        final_state = target.get("final_state", {})
        query_index = int(row["metadata"]["query_index"])
        root_id = f"audited::{row['pack_id']}::q{query_index}"
        episode_id = f"{root_id}::episode0"
        state_id = f"{episode_id}::retrieval_support_state"
        repo_id = normalize_repo_id(target.get("canonical_name", "unknown"))
        language_family = language_from_repo(repo_id, final_state.get("expected_changed_files", []), query_text)
        positive_refs = [score.get("chunk_id") for score in row.get("support_scores", []) if score.get("chunk_id")]

        root_records.append(
            {
                "root_id": root_id,
                "repo_id": repo_id,
                "repo_family": repo_id,
                "language_family": language_family,
                "task_family": "retrieval_supervision",
                "snapshot_id": row["pack_id"],
                "environment_id": "strict_long_context_train_ready_plus_audit_v1",
                "verifier_id": final_state.get("test_selection_route", "UNKNOWN"),
                "provenance": {
                    "source_family_id": "strict_long_context_train_ready_plus_audit_v1",
                    "pack_id": row["pack_id"],
                    "query_index": query_index,
                    "row_id": row["row_id"],
                },
                "split_component": f"audited_{row['effective_split']}",
            }
        )
        episode_records.append(
            {
                "episode_id": episode_id,
                "root_id": root_id,
                "episode_kind": "audited_retrieval_teacher_state",
                "agent_family": "strict_long_context_teacher",
                "start_state_id": state_id,
                "terminal_state_id": state_id,
                "outcome_grade": final_state.get("execution_route", "UNKNOWN"),
            }
        )
        event_records.extend(
            [
                {
                    "event_id": f"{episode_id}::ev001",
                    "root_id": root_id,
                    "episode_id": episode_id,
                    "event_index": 1,
                    "event_type": "USER_TASK",
                    "actor": "strict_long_context_teacher",
                    "timestamp_utc": None,
                    "content": row["query_text"],
                    "artifact_refs": [],
                },
                {
                    "event_id": f"{episode_id}::ev002",
                    "root_id": root_id,
                    "episode_id": episode_id,
                    "event_index": 2,
                    "event_type": "SEARCH_RESULT",
                    "actor": "strict_long_context_teacher",
                    "timestamp_utc": None,
                    "content": json.dumps(row.get("support_scores", [])[:8], sort_keys=True),
                    "artifact_refs": positive_refs[:8],
                },
                {
                    "event_id": f"{episode_id}::ev003",
                    "root_id": root_id,
                    "episode_id": episode_id,
                    "event_index": 3,
                    "event_type": "TEST_RESULT",
                    "actor": "strict_long_context_teacher",
                    "timestamp_utc": None,
                    "content": json.dumps(
                        {
                            "test_selection_route": final_state.get("test_selection_route"),
                            "verification_targets": final_state.get("verification_targets", []),
                        },
                        sort_keys=True,
                    ),
                    "artifact_refs": final_state.get("verification_targets", []),
                },
            ]
        )
        state_records.append(
            {
                "state_id": state_id,
                "episode_id": episode_id,
                "root_id": root_id,
                "event_span": [f"{episode_id}::ev001", f"{episode_id}::ev003"],
                "state_kind": "retrieval_teacher_state",
                "visible_evidence_ids": positive_refs[:8],
                "candidate_set_ids": row.get("hard_negative_chunk_ids", []),
                "hypothesis_status": "teacher_supported",
                "input_view_id": "trajectory_prefix",
                "query_text": row["query_text"],
                "final_state": final_state,
            }
        )
        multitarget_rows.extend(
            [
                {
                    "row_id": f"{state_id}::decisive_evidence",
                    "root_id": root_id,
                    "episode_id": episode_id,
                    "state_id": state_id,
                    "split_component": f"audited_{row['effective_split']}",
                    "target_family": "bounded_decision",
                    "target_subtype": "decisive_evidence",
                    "input_text": row["query_text"],
                    "target_text": json.dumps(row.get("positive_chunk_ids", []), sort_keys=True),
                    "anti_cheat": {
                        "same_root_train_eval_forbidden": True,
                        "prompt_target_leak": is_prompt_target_leak(row["metadata"]),
                    },
                },
                {
                    "row_id": f"{state_id}::verifier_outcome",
                    "root_id": root_id,
                    "episode_id": episode_id,
                    "state_id": state_id,
                    "split_component": f"audited_{row['effective_split']}",
                    "target_family": "bounded_decision",
                    "target_subtype": "verifier_outcome",
                    "input_text": row["query_text"],
                    "target_text": final_state.get("test_selection_route", "UNKNOWN"),
                    "anti_cheat": {
                        "same_root_train_eval_forbidden": True,
                        "prompt_target_leak": is_prompt_target_leak(row["metadata"]),
                    },
                },
                {
                    "row_id": f"{state_id}::retrieve_answer_abstain",
                    "root_id": root_id,
                    "episode_id": episode_id,
                    "state_id": state_id,
                    "split_component": f"audited_{row['effective_split']}",
                    "target_family": "bounded_decision",
                    "target_subtype": "retrieve_answer_abstain",
                    "input_text": row["query_text"],
                    "target_text": "ANSWER_WITH_RETRIEVED_EVIDENCE",
                    "anti_cheat": {
                        "same_root_train_eval_forbidden": True,
                        "prompt_target_leak": is_prompt_target_leak(row["metadata"]),
                    },
                },
            ]
        )

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": True,
        "inputs": {
            "curriculum_plan": str(PLAN_JSON.relative_to(ROOT)),
            "root_schema": str(ROOT_SCHEMA_JSON.relative_to(ROOT)),
            "state_schema": str(STATE_SCHEMA_JSON.relative_to(ROOT)),
            "raw_pack_rows": str(RAW_PACK_ROWS.relative_to(ROOT)),
            "raw_pack_summary": str(RAW_PACK_SUMMARY.relative_to(ROOT)),
            "audited_retrieval_rows": str(AUDITED_RETRIEVAL_ROWS.relative_to(ROOT)),
            "audited_full_rows": str(AUDITED_FULL_ROWS.relative_to(ROOT)),
            "audited_dataset_card": str(AUDITED_CARD.relative_to(ROOT)),
        },
        "claim_boundary": [
            "This compiler emits root, episode, event, and state records from long-context supervision sources.",
            "Raw merged 5M pack roots are bootstrap train-only lineage and are not heldout evaluation claims.",
            "Audited retrieval rows are teacher states and preserve their original train split semantics.",
            "The inferred event streams are structural reconstructions from stored supervision artifacts, not literal terminal logs.",
            "The repaired 24-row v2.7 frontier remains a separate canary/regression suite and is not part of this compiler output.",
        ],
        "metrics": {
            "raw_pack_query_roots": len(raw_pack_row["target_rows"]),
            "audited_retrieval_roots": len(retrieval_rows),
            "audited_full_context_rows_available": len(full_rows),
            "compiled_root_records": len(root_records),
            "compiled_episode_records": len(episode_records),
            "compiled_event_records": len(event_records),
            "compiled_causal_states": len(state_records),
            "compiled_multitarget_rows": len(multitarget_rows),
            "target_family_counts": dict(sorted(Counter(row["target_family"] for row in multitarget_rows).items())),
            "repo_counts": dict(sorted(Counter(root["repo_id"] for root in root_records).items())),
            "language_counts": dict(sorted(Counter(root["language_family"] for root in root_records).items())),
            "execution_route_counts_raw_pack": dict(
                sorted(
                    Counter(
                        parse_state_json(t.get("final_state_json", "")).get("execution_route", "UNKNOWN")
                        for t in raw_pack_row["target_rows"]
                    ).items()
                )
            ),
            "execution_route_counts_audited_retrieval": dict(
                sorted(
                    Counter(
                        parse_state_json(row["target_text"]).get("final_state", {}).get("execution_route", "UNKNOWN")
                        for row in retrieval_rows
                    ).items()
                )
            ),
        },
        "schema_contracts": {
            "root_schema_name": root_schema["schema_name"],
            "projection_schema_name": state_schema["schema_name"],
        },
        "next_best_step": (
            "Use these compiled root and state records to build split-aware multi-target training manifests, "
            "then add fresh heldout root supply so Python/Rust/C++/Web evaluations move beyond the canary frontier."
        ),
        "outputs": {
            "root_records": str(ROOTS_JSONL.relative_to(ROOT)),
            "episode_records": str(EPISODES_JSONL.relative_to(ROOT)),
            "typed_events": str(EVENTS_JSONL.relative_to(ROOT)),
            "causal_states": str(STATES_JSONL.relative_to(ROOT)),
            "multitarget_rows": str(ROWS_JSONL.relative_to(ROOT)),
        },
        "source_quality_notes": {
            "raw_pack_summary": raw_pack_summary.get("training_signal_summary", {}),
            "audited_compile_summary": audited_card.get("compile_summary", {}),
        },
    }

    write_jsonl(ROOTS_JSONL, root_records)
    write_jsonl(EPISODES_JSONL, episode_records)
    write_jsonl(EVENTS_JSONL, event_records)
    write_jsonl(STATES_JSONL, state_records)
    write_jsonl(ROWS_JSONL, multitarget_rows)
    write_json(SUMMARY_JSON, summary)
    write_json(RUN_SUMMARY_JSON, summary)


if __name__ == "__main__":
    main()
