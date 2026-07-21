#!/usr/bin/env python3
"""Stage12402 private Open-SWE event digest extractor.

Consumes Stage12401 preflight rows, Stage12400 worklist rows, and Stage12327
Open-SWE private refs. Privately joins to raw parquet rows where possible, then
emits only safe event digests: ordinals, classes, hashes, aggregate counts, and
non-causal ordered relation classes. No raw commands, outputs, paths, URLs,
source text, issue bodies, patch bodies/diffs, or line contents are emitted.
All admission and training flags remain false/zero.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12402_open_swe_private_event_digest_extractor"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12401_ROWS = (
    ROOT
    / "runs/local/artifacts/stage12401_open_swe_raw_private_hydration_preflight/"
    / "open_swe_raw_private_hydration_preflight.jsonl"
)
STAGE12401_SUMMARY = (
    ROOT
    / "runs/local/artifacts/stage12401_open_swe_raw_private_hydration_preflight/"
    / "open_swe_raw_private_hydration_preflight_summary.json"
)
STAGE12400_WORKLIST = (
    ROOT
    / "runs/local/artifacts/stage12400_open_swe_replay_hydration_worklist/"
    / "open_swe_replay_hydration_worklist.jsonl"
)
STAGE12327_OPEN_SWE = (
    ROOT
    / "runs/local/artifacts/stage12327_external_adapter_preflight/"
    / "open_swe_trace_support_candidates.jsonl"
)

ROWS_NAME = "open_swe_private_event_digests.jsonl"
LOCAL_SUMMARY_NAME = "open_swe_private_event_digest_summary.json"
GUARDRAIL_NAME = "guardrail_scan.json"
EXPECTED_ITEM_COUNT = 15

ZERO_ADMISSION: dict[str, int | bool] = {
    "admission": False,
    "training_allowed": False,
    "training_row_count": 0,
    "level3_admitted": 0,
    "patch_trace_admitted": 0,
    "strict_eval_eligible": 0,
    "source_heldout_admissible": 0,
    "repair_claim_admitted": 0,
}
RAW_CONTENT_POLICY: dict[str, bool] = {
    "raw_trajectory_text_emitted": False,
    "raw_commands_emitted": False,
    "raw_outputs_emitted": False,
    "raw_patches_emitted": False,
    "source_text_emitted": False,
    "absolute_paths_emitted": False,
    "urls_emitted": False,
    "issue_bodies_emitted": False,
    "line_contents_emitted": False,
    "patch_diffs_emitted": False,
}
CLAIM_BOUNDARY: dict[str, bool] = {
    "state_before_claim_emitted": False,
    "state_after_claim_emitted": False,
    "patch_application_claim_emitted": False,
    "verifier_relevance_claim_emitted": False,
    "causal_linkage_claim_emitted": False,
    "correct_next_action_policy_claim_emitted": False,
    "training_admission_claim_emitted": False,
}
SAFE_MARKERS = {
    "PASSED": "verifier_pass_marker",
    "FAILED": "verifier_fail_marker",
    "ERROR": "verifier_error_marker",
    "Traceback": "traceback_marker",
    "AssertionError": "assertion_marker",
    "pytest": "pytest_marker",
    "mvn test": "maven_test_marker",
    "cargo test": "cargo_test_marker",
    "npm test": "npm_test_marker",
}

ABS_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+")
URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
MULTILINE_RE = re.compile(r"[\r\n]")
HEX_RE = re.compile(r"^[0-9a-f]{12,64}$")
RAW_KEY_RE = re.compile(
    r"(?:^|_)(trajectory|command|output|patch|diff|source_text|issue_body|line_content|stdout|stderr|url|path)(?:$|_)",
    re.IGNORECASE,
)
SAFE_KEY_CONTEXT_RE = re.compile(
    r"(?:status|code|codes|proof|gate|hash|hashes|class|classes|signal|policy|count|counts|bucket|ref|refs|emitted|allowed|stage|scan|claim)",
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


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:n]


def text_hash(value: str, n: int = 24) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:n]


def stage_file_hash(path: Path) -> str:
    if not path.exists():
        return "missing"
    return hashlib.sha256(path.read_bytes()).hexdigest()[:24]


def index_stage12400(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {stable_hash(row.get("worklist_item_id") or "missing", 24): row for row in rows}


def index_private_refs(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    refs: dict[str, dict[str, Any]] = {}
    for row in rows:
        ref = row.get("source_record_ref") if isinstance(row.get("source_record_ref"), dict) else {}
        if ref:
            refs[stable_hash(ref, 24)] = ref
    return refs


def role_class(role: Any) -> str:
    role_name = str(role or "unknown").lower()
    if role_name in {"system", "user", "assistant", "tool"}:
        return f"role_{role_name}"
    return "role_other"


def classify_tool_name(name: str) -> str:
    lowered = name.lower()
    if any(token in lowered for token in ("bash", "shell", "terminal", "exec")):
        return "shell_tool_call"
    if any(token in lowered for token in ("edit", "patch", "write", "replace")):
        return "file_mutation_tool_call"
    if any(token in lowered for token in ("read", "open", "view", "grep", "search")):
        return "file_inspection_tool_call"
    return "other_tool_call"


def action_class(turn: dict[str, Any]) -> str:
    calls = turn.get("tool_calls") if isinstance(turn.get("tool_calls"), list) else []
    classes: list[str] = []
    for call in calls:
        fn = call.get("function") if isinstance(call, dict) else {}
        classes.append(classify_tool_name(str((fn or {}).get("name") or "")))
    if not classes:
        if str(turn.get("role") or "").lower() == "tool":
            return "tool_observation"
        return "no_tool_call_action"
    unique = sorted(set(classes))
    if len(unique) == 1:
        return unique[0]
    return "mixed_tool_call_action"


def marker_classes_for_text(text: str) -> list[str]:
    return sorted({klass for marker, klass in SAFE_MARKERS.items() if marker in text})


def status_class(turn: dict[str, Any], marker_classes: list[str]) -> str:
    if str(turn.get("role") or "").lower() != "tool":
        return "status_not_observation"
    present = set(marker_classes)
    if {"verifier_pass_marker", "verifier_fail_marker"} <= present:
        return "mixed_pass_fail_observation_marker"
    if "verifier_pass_marker" in present and "verifier_error_marker" in present:
        return "mixed_pass_error_observation_marker"
    if "verifier_pass_marker" in present:
        return "pass_observation_marker_not_correctness"
    if "verifier_fail_marker" in present:
        return "fail_observation_marker_not_correctness"
    if "verifier_error_marker" in present:
        return "error_observation_marker_not_correctness"
    if present:
        return "nonverifier_observation_marker"
    return "observation_marker_absent"


def patch_signal_class(turn: dict[str, Any], content: str) -> str:
    calls = turn.get("tool_calls") if isinstance(turn.get("tool_calls"), list) else []
    for call in calls:
        fn = call.get("function") if isinstance(call, dict) else {}
        if classify_tool_name(str((fn or {}).get("name") or "")) == "file_mutation_tool_call":
            return "patch_tool_call_class_present_not_apply_proof"
    lowered = content.lower()
    if "diff --git" in lowered or "*** begin patch" in lowered:
        return "patch_body_marker_present_not_apply_proof"
    return "patch_signal_absent"


def verifier_signal_class(marker_classes: list[str]) -> str:
    present = set(marker_classes)
    if {"verifier_pass_marker", "verifier_fail_marker"} <= present:
        return "mixed_pass_fail_marker_not_causality"
    if "verifier_pass_marker" in present:
        return "pass_marker_not_correctness_proof"
    if "verifier_fail_marker" in present:
        return "fail_marker_not_correctness_proof"
    if "verifier_error_marker" in present:
        return "error_marker_not_correctness_proof"
    if present:
        return "nonverifier_marker_present"
    return "verifier_signal_absent"


def read_private_row(ref: dict[str, Any]) -> tuple[dict[str, Any], str]:
    dataset_file = ref.get("dataset_file")
    if not dataset_file:
        return {}, "private_ref_missing_dataset_file"
    parquet_path = Path(str(dataset_file))
    if not parquet_path.exists():
        return {}, "private_ref_not_accessible"
    try:
        import pyarrow.parquet as pq  # type: ignore
    except Exception:
        return {}, "pyarrow_unavailable"
    wanted_instance = ref.get("instance_id")
    wanted_trajectory = ref.get("trajectory_id")
    try:
        table = pq.read_table(
            parquet_path,
            columns=["instance_id", "trajectory_id", "trajectory", "model_patch", "resolved", "metadata"],
            filters=[
                ("instance_id", "=", wanted_instance),
                ("trajectory_id", "=", wanted_trajectory),
            ],
        )
    except Exception:
        return {}, "private_parquet_read_failed"
    for record in table.to_pylist():
        if record.get("instance_id") == wanted_instance and record.get("trajectory_id") == wanted_trajectory:
            return record, "private_parquet_row_joined"
    return {}, "private_parquet_row_not_found"


def bucket_bool(value: bool) -> str:
    return "present" if value else "absent"


def proof_status_slots() -> dict[str, dict[str, str]]:
    return {
        "authoritative_state_before": {"status_code": "blocked_missing_authoritative_state_before"},
        "authoritative_state_after": {"status_code": "blocked_missing_authoritative_state_after"},
        "patch_application": {"status_code": "blocked_missing_patch_application_proof"},
        "verifier_relevance": {"status_code": "blocked_missing_verifier_relevance_proof"},
        "causal_verifier_linkage": {"status_code": "blocked_missing_causal_verifier_linkage"},
        "stop_continue": {"status_code": "blocked_missing_stop_continue_proof"},
        "next_action_policy": {"status_code": "blocked_correct_next_action_not_authoritatively_proven"},
    }


def build_event_digests(trajectory: Any) -> list[dict[str, Any]]:
    if not isinstance(trajectory, list):
        return []
    digests: list[dict[str, Any]] = []
    for ordinal, turn in enumerate(trajectory):
        if not isinstance(turn, dict):
            continue
        content = str(turn.get("content") or "")
        marker_classes = marker_classes_for_text(content)
        role = role_class(turn.get("role"))
        action = action_class(turn)
        status = status_class(turn, marker_classes)
        patch_signal = patch_signal_class(turn, content)
        verifier_signal = verifier_signal_class(marker_classes)
        calls = turn.get("tool_calls") if isinstance(turn.get("tool_calls"), list) else []
        observation_ref_hash = "missing"
        if str(turn.get("role") or "").lower() == "tool" and content:
            observation_ref_hash = text_hash(content, 24)
        event_ref_hash = stable_hash(turn, 24)
        digests.append(
            {
                "event_index": ordinal,
                "ordinal": ordinal,
                "role_class": role,
                "action_class": action,
                "has_tool_call_bucket": bucket_bool(bool(calls)),
                "has_tool_result_bucket": bucket_bool(str(turn.get("role") or "").lower() == "tool"),
                "observation_status_class": status,
                "observation_marker_classes": marker_classes,
                "safe_order_evidence": "relative_order_only",
                "event_ref_hash": event_ref_hash,
                "observation_ref_hash": observation_ref_hash,
                "patch_signal_class": patch_signal,
                "verifier_signal_class": verifier_signal,
                "status_class": status,
            }
        )
    return digests


def ordered_relation_classes(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    relations: list[dict[str, Any]] = []
    for previous, current in zip(events, events[1:]):
        relation_bits = [
            str(previous.get("role_class") or "role_other"),
            "to",
            str(current.get("role_class") or "role_other"),
        ]
        if current.get("patch_signal_class") != "patch_signal_absent":
            relation_bits.append("then_patch_signal")
        if current.get("verifier_signal_class") != "verifier_signal_absent":
            relation_bits.append("then_verifier_signal")
        relations.append(
            {
                "from_ordinal": int(previous.get("ordinal") or 0),
                "to_ordinal": int(current.get("ordinal") or 0),
                "relation_class": "_".join(relation_bits),
            }
        )
    return relations


def aggregate_counts(events: list[dict[str, Any]], relations: list[dict[str, Any]]) -> dict[str, Any]:
    count_fields = [
        "role_class",
        "action_class",
        "status_class",
        "patch_signal_class",
        "verifier_signal_class",
    ]
    counts: dict[str, Any] = {"event_count": len(events), "relation_count": len(relations)}
    for field in count_fields:
        counts[f"{field}_counts"] = dict(sorted(Counter(str(event.get(field) or "missing") for event in events).items()))
    counts["ordered_relation_class_counts"] = dict(
        sorted(Counter(str(relation.get("relation_class") or "missing") for relation in relations).items())
    )
    counts["observation_ref_hash_count"] = sum(1 for event in events if event.get("observation_ref_hash") != "missing")
    return counts


def build_item(
    preflight_row: dict[str, Any],
    worklist_by_hash: dict[str, dict[str, Any]],
    private_refs_by_hash: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    source_refs = preflight_row.get("source_stage_ref_hashes") if isinstance(preflight_row.get("source_stage_ref_hashes"), dict) else {}
    worklist_hash = str(preflight_row.get("source_worklist_item_hash") or source_refs.get("stage12400_item_hash") or "missing")
    private_ref_hash = str(source_refs.get("stage12327_private_ref_hash") or "missing")
    worklist_row = worklist_by_hash.get(worklist_hash, {})
    private_ref = private_refs_by_hash.get(private_ref_hash, {})
    raw_record, join_status = read_private_row(private_ref) if private_ref else ({}, "private_ref_hash_not_joined")
    events = build_event_digests(raw_record.get("trajectory"))
    relations = ordered_relation_classes(events)
    counts = aggregate_counts(events, relations)
    model_patch_hash = "missing"
    if isinstance(raw_record.get("model_patch"), str) and raw_record.get("model_patch"):
        model_patch_hash = text_hash(str(raw_record.get("model_patch")), 24)
    metadata = raw_record.get("metadata") if isinstance(raw_record.get("metadata"), dict) else {}
    unresolved = sorted(
        set(str(blocker) for blocker in preflight_row.get("unresolved_blockers", []))
        | set(str(blocker) for blocker in worklist_row.get("blockers", []))
        | {
            "digest_only_not_training_row",
            "event_hashes_are_not_state_before_after",
            "no_patch_application_claim",
            "no_verifier_relevance_claim",
            "no_causal_linkage_claim",
            "no_correct_next_action_policy_claim",
            "event_digest_is_not_transition_proof",
            "event_digest_is_not_training_row",
            "blocked_fail_closed_raw_private_event_digest",
            "blocked_correct_next_action_not_authoritatively_proven",
        }
    )
    return {
        "stage": STAGE,
        "record_type": "blocked_open_swe_private_event_digest",
        "digest_item_id": f"{STAGE}::{stable_hash({'preflight': preflight_row.get('preflight_item_id'), 'rank': preflight_row.get('selection_rank')}, 20)}",
        "selection_rank": int(preflight_row.get("selection_rank") or 0),
        "language_family": str(preflight_row.get("language_family") or worklist_row.get("language_family") or "unknown"),
        "repo_family_hash": str(preflight_row.get("repo_family_hash") or worklist_row.get("repo_family_hash") or "missing"),
        "source_stage_ref_hashes": {
            "stage12401_preflight_item_hash": stable_hash(preflight_row.get("preflight_item_id") or "missing", 24),
            "stage12400_item_hash": worklist_hash,
            "stage12327_private_ref_hash": private_ref_hash,
            "candidate_transition_window_ref_hash": str(source_refs.get("candidate_transition_window_ref_hash") or "missing"),
        },
        "private_join_status": {
            "stage12400_join_status": "stage12400_worklist_joined" if worklist_row else "stage12400_worklist_not_joined",
            "stage12327_private_ref_join_status": "private_ref_hash_joined" if private_ref else "private_ref_hash_not_joined",
            "private_parquet_join_status": join_status,
        },
        "event_digest_available": bool(events),
        "event_count": len(events),
        "event_count_bucket": "gte_200" if len(events) >= 200 else "150_199" if len(events) >= 150 else "100_149" if len(events) >= 100 else "50_99" if len(events) >= 50 else "lt_50",
        "event_digest_hash": stable_hash(events, 24),
        "event_order_digest": events,
        "safe_trajectory_event_digests": events,
        "proof_status_slots": proof_status_slots(),
        "next_action_policy_class": "blocked_correct_next_action_not_authoritatively_proven",
        "aggregate_counts": {
            **counts,
            "raw_resolved_flag_present_count": int("resolved" in raw_record),
            "model_patch_ref_hash_present_count": int(model_patch_hash != "missing"),
            "metadata_category_class_present_count": int(bool(metadata.get("category"))),
        },
        "ordered_relation_classes": relations,
        "raw_row_ref_hashes": {
            "source_record_ref_hash": stable_hash(private_ref, 24) if private_ref else "missing",
            "instance_ref_hash": stable_hash(private_ref.get("instance_id") or "missing", 16) if private_ref else "missing",
            "trajectory_ref_hash": stable_hash(private_ref.get("trajectory_id") or "missing", 16) if private_ref else "missing",
            "model_patch_ref_hash": model_patch_hash,
        },
        "unresolved_blockers": unresolved,
        "claim_boundary": CLAIM_BOUNDARY,
        "raw_content_policy": RAW_CONTENT_POLICY,
        **ZERO_ADMISSION,
    }


def validate_item(row: dict[str, Any], row_index: int) -> list[str]:
    issues: list[str] = []
    required = [
        "digest_item_id",
        "source_stage_ref_hashes",
        "private_join_status",
        "event_digest_available",
        "event_count",
        "event_count_bucket",
        "event_digest_hash",
        "event_order_digest",
        "safe_trajectory_event_digests",
        "proof_status_slots",
        "next_action_policy_class",
        "aggregate_counts",
        "ordered_relation_classes",
        "raw_row_ref_hashes",
        "unresolved_blockers",
        "claim_boundary",
        "raw_content_policy",
    ]
    for key in required:
        if key not in row:
            issues.append(f"row_{row_index}_missing_{key}")
    for key, expected in ZERO_ADMISSION.items():
        if row.get(key) != expected:
            issues.append(f"row_{row_index}_{key}_not_zero_or_false")
    for claim, expected in CLAIM_BOUNDARY.items():
        if row.get("claim_boundary", {}).get(claim) != expected:
            issues.append(f"row_{row_index}_{claim}_not_false")
    events = row.get("safe_trajectory_event_digests")
    if not isinstance(events, list):
        issues.append(f"row_{row_index}_events_not_list")
        events = []
    if row.get("aggregate_counts", {}).get("event_count") != len(events) or row.get("event_count") != len(events):
        issues.append(f"row_{row_index}_event_count_mismatch")
    if row.get("event_order_digest") != events:
        issues.append(f"row_{row_index}_event_order_digest_alias_mismatch")
    proof_slots = row.get("proof_status_slots") if isinstance(row.get("proof_status_slots"), dict) else {}
    for slot_key in [
        "authoritative_state_before",
        "authoritative_state_after",
        "patch_application",
        "verifier_relevance",
        "causal_verifier_linkage",
        "stop_continue",
        "next_action_policy",
    ]:
        if slot_key not in proof_slots:
            issues.append(f"row_{row_index}_missing_proof_status_slot_{slot_key}")
    if row.get("next_action_policy_class") != "blocked_correct_next_action_not_authoritatively_proven":
        issues.append(f"row_{row_index}_next_action_policy_not_blocked")
    for ordinal, event in enumerate(events):
        if event.get("ordinal") != ordinal:
            issues.append(f"row_{row_index}_event_{ordinal}_ordinal_mismatch")
        for field in [
            "event_index",
            "role_class",
            "action_class",
            "has_tool_call_bucket",
            "has_tool_result_bucket",
            "observation_status_class",
            "observation_marker_classes",
            "safe_order_evidence",
            "status_class",
            "event_ref_hash",
            "observation_ref_hash",
            "patch_signal_class",
            "verifier_signal_class",
        ]:
            if field not in event:
                issues.append(f"row_{row_index}_event_{ordinal}_missing_{field}")
    relations = row.get("ordered_relation_classes")
    if not isinstance(relations, list):
        issues.append(f"row_{row_index}_relations_not_list")
        relations = []
    if row.get("aggregate_counts", {}).get("relation_count") != len(relations):
        issues.append(f"row_{row_index}_relation_count_mismatch")
    if row.get("private_join_status", {}).get("private_parquet_join_status") == "private_parquet_row_joined" and not events:
        issues.append(f"row_{row_index}_joined_private_row_but_no_events")
    return issues


def scan_value(value: Any, artifact: str, issues: list[dict[str, Any]], key_path: str = "") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{key_path}.{key}" if key_path else str(key)
            if (
                RAW_KEY_RE.search(str(key))
                and not SAFE_KEY_CONTEXT_RE.search(str(key))
                and isinstance(child, str)
                and child
                and not HEX_RE.match(child)
            ):
                issues.append({"artifact": artifact, "issue": "raw_like_key_with_string_value", "key": child_path})
            scan_value(child, artifact, issues, child_path)
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            scan_value(child, artifact, issues, f"{key_path}[{index}]")
        return
    if not isinstance(value, str):
        return
    if ABS_PATH_RE.search(value):
        issues.append({"artifact": artifact, "issue": "absolute_path_string", "key": key_path})
    if URL_RE.search(value):
        issues.append({"artifact": artifact, "issue": "url_string", "key": key_path})
    if MULTILINE_RE.search(value):
        issues.append({"artifact": artifact, "issue": "multiline_string", "key": key_path})
    if key_path.endswith("_hash") and not HEX_RE.match(value) and value != "missing":
        issues.append({"artifact": artifact, "issue": "non_hash_value_in_hash_field", "key": key_path})


def guardrail_scan(paths: list[Path]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    parsed_json_values = 0
    scanned_jsonl_rows = 0
    for path in paths:
        text = path.read_text(encoding="utf-8")
        if ABS_PATH_RE.search(text):
            issues.append({"artifact": path.name, "issue": "absolute_path_pattern"})
        if URL_RE.search(text):
            issues.append({"artifact": path.name, "issue": "url_pattern"})
        if path.suffix == ".jsonl":
            for line_number, line in enumerate(text.splitlines(), 1):
                if not line.strip():
                    continue
                scanned_jsonl_rows += 1
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    issues.append({"artifact": path.name, "issue": "invalid_jsonl", "line": line_number})
                    continue
                scan_value(value, path.name, issues, f"line[{line_number}]")
        else:
            try:
                value = json.loads(text)
            except json.JSONDecodeError:
                issues.append({"artifact": path.name, "issue": "invalid_json"})
                continue
            parsed_json_values += 1
            scan_value(value, path.name, issues)
    return {
        "scan_passed": not issues,
        "issues": issues,
        "scanned_artifact_count": len(paths),
        "parsed_json_values": parsed_json_values,
        "scanned_jsonl_rows": scanned_jsonl_rows,
    }


def merge_counter_dict(target: defaultdict[str, Counter[str]], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if key.endswith("_counts") and isinstance(value, dict):
            target[key].update({str(inner_key): int(count) for inner_key, count in value.items()})


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    preflight_rows = sorted(read_jsonl(STAGE12401_ROWS), key=lambda row: int(row.get("selection_rank") or 0))
    stage12401_summary = read_json(STAGE12401_SUMMARY)
    stage12400_rows = read_jsonl(STAGE12400_WORKLIST)
    stage12327_rows = read_jsonl(STAGE12327_OPEN_SWE)
    worklist_by_hash = index_stage12400(stage12400_rows)
    private_refs_by_hash = index_private_refs(stage12327_rows)

    rows = [build_item(row, worklist_by_hash, private_refs_by_hash) for row in preflight_rows]

    row_path = OUT / ROWS_NAME
    local_summary_path = OUT / LOCAL_SUMMARY_NAME
    guardrail_path = OUT / GUARDRAIL_NAME
    write_jsonl(row_path, rows)

    schema_issues = [issue for index, row in enumerate(rows, 1) for issue in validate_item(row, index)]
    language_counts = Counter(str(row.get("language_family") or "unknown") for row in rows)
    parquet_status_counts = Counter(
        str(row.get("private_join_status", {}).get("private_parquet_join_status") or "missing") for row in rows
    )
    global_counts: defaultdict[str, Counter[str]] = defaultdict(Counter)
    total_event_count = 0
    total_relation_count = 0
    observation_ref_hash_count = 0
    blocker_counts = Counter()
    for row in rows:
        counts = row.get("aggregate_counts") if isinstance(row.get("aggregate_counts"), dict) else {}
        total_event_count += int(counts.get("event_count") or 0)
        total_relation_count += int(counts.get("relation_count") or 0)
        observation_ref_hash_count += int(counts.get("observation_ref_hash_count") or 0)
        merge_counter_dict(global_counts, counts)
        blocker_counts.update(str(blocker) for blocker in row.get("unresolved_blockers", []))

    upstream_zero_ok = all(
        stage12401_summary.get(key) == expected
        for key, expected in {
            "training_allowed": False,
            "level3_admitted": 0,
            "patch_trace_admitted": 0,
            "strict_eval_eligible": 0,
            "source_heldout_admissible": 0,
        }.items()
    )
    summary: dict[str, Any] = {
        "stage": STAGE,
        "decision": "private_event_digest_extraction_complete_zero_admission",
        "source_stages": [
            "stage12401_open_swe_raw_private_hydration_preflight",
            "stage12400_open_swe_replay_hydration_worklist",
            "stage12327_external_adapter_preflight",
        ],
        "source_stage_artifact_hashes": {
            "stage12401_rows_hash": stage_file_hash(STAGE12401_ROWS),
            "stage12400_worklist_hash": stage_file_hash(STAGE12400_WORKLIST),
            "stage12327_open_swe_candidates_hash": stage_file_hash(STAGE12327_OPEN_SWE),
        },
        "input_counts": {
            "stage12401_preflight_row_count": len(preflight_rows),
            "stage12400_worklist_row_count": len(stage12400_rows),
            "stage12327_open_swe_candidate_count": len(stage12327_rows),
        },
        "expected_item_count": EXPECTED_ITEM_COUNT,
        "input_preflight_item_count": len(preflight_rows),
        "digest_item_count": len(rows),
        "output_digest_item_count": len(rows),
        "private_rows_joined": parquet_status_counts.get("private_parquet_row_joined", 0),
        "language_family_counts": dict(sorted(language_counts.items())),
        "private_parquet_join_status_counts": dict(sorted(parquet_status_counts.items())),
        "event_digest_count": total_event_count,
        "total_event_digest_count": total_event_count,
        "ordered_relation_count": total_relation_count,
        "total_ordered_relation_count": total_relation_count,
        "observation_ref_hash_count": observation_ref_hash_count,
        "aggregate_class_counts": {key: dict(sorted(counter.items())) for key, counter in sorted(global_counts.items())},
        "unresolved_blocker_counts": dict(sorted(blocker_counts.items())),
        "zero_admission_flags": {
            **ZERO_ADMISSION,
            "admitted_digest_item_count": 0,
            "upstream_stage12401_zero_admission_confirmed": upstream_zero_ok,
        },
        "claim_boundary": {
            **CLAIM_BOUNDARY,
            "event_hashes_are_private_refs_not_raw_content": True,
            "ordered_relations_are_noncausal_classes_only": True,
        },
        "raw_content_policy": RAW_CONTENT_POLICY,
        "raw_leak_scan": None,
        "raw_leak_findings": [],
        "schema_issue_count": len(schema_issues),
        "schema_issues": schema_issues,
        "generated_artifacts": [ROWS_NAME, LOCAL_SUMMARY_NAME, GUARDRAIL_NAME],
        **ZERO_ADMISSION,
    }
    write_json(local_summary_path, summary)
    write_json(SUMMARY, summary)

    guardrail = guardrail_scan([row_path, local_summary_path, SUMMARY])
    write_json(guardrail_path, guardrail)
    summary["raw_leak_scan"] = guardrail
    summary["raw_leak_findings"] = guardrail["issues"]
    summary["guardrail_issue_count"] = len(guardrail["issues"])
    write_json(local_summary_path, summary)
    write_json(SUMMARY, summary)

    if schema_issues or guardrail["issues"] or len(rows) != EXPECTED_ITEM_COUNT:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
