#!/usr/bin/env python3
"""Build Stage12441 fail-closed embedding-backed expansion gate.

This stage supersedes Stage12440 for priority/routing only. It builds
public-safe candidate hash records, embeds only normalized enum/hash tokens,
and uses vector similarity only to order future private review work.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12441_embedding_transition_candidate_expansion_gate"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12440_SUMMARY = ROOT / "runs/summaries/stage12440_diverse_transition_candidate_expansion_gate.json"
STAGE12439_SUMMARY = ROOT / "runs/summaries/stage12439_session_like_raw_private_semantic_review_packet_request.json"
STAGE12438_SUMMARY = ROOT / "runs/summaries/stage12438_session_like_materializer_upgrade_postrun.json"

STAGE12387_RECORDS = (
    ROOT
    / "runs/local/artifacts/stage12387_transition_local_materializer_upgrade_worklist/"
    "transition_local_materializer_upgrade_worklist.jsonl"
)
STAGE12388_RECORDS = (
    ROOT
    / "runs/local/artifacts/stage12388_transition_local_candidate_recovery/"
    "transition_local_candidate_recovery_records.jsonl"
)
STAGE12389_RECORDS = (
    ROOT
    / "runs/local/artifacts/stage12389_transition_candidate_semantic_review/"
    "transition_candidate_semantic_review_records.jsonl"
)

ZERO_COUNTERS: dict[str, bool | int] = {
    "training_allowed": False,
    "admission_allowed": False,
    "execution_allowed": False,
    "admitted_rows": 0,
    "emitted_training_rows": 0,
    "countable_new_rows": 0,
    "level3_candidate_count": 0,
    "patch_trace_candidate_count": 0,
}

SIMILARITY_USE_POLICY = {
    "used_for_priority_only": True,
    "used_for_admission": False,
    "used_for_labeling": False,
    "used_for_eval_selection": False,
}

EMBEDDING_USE_POLICY = {
    "used_for_review_priority_ordering": True,
    "used_for_admission": False,
    "used_for_labeling": False,
    "used_for_eval_selection": False,
    "used_for_training": False,
    "used_as_proof": False,
}

EMBEDDING_INPUT_FIELD_NAMES = [
    "source_adapter_enum",
    "language_family_enum",
    "task_family_role_enum",
    "priority_bucket_enum",
    "recovery_status_enum",
    "review_status_enum",
    "verifier_status_enum",
    "patch_status_enum",
    "blocker_code_enums",
    "rule_id_hash_indicators",
    "repo_family_hash_indicator",
    "safe_next_action_count_bucket",
]

RAW_CONTENT_POLICY = {
    "raw_private_trace_text_inspected": False,
    "raw_private_trace_text_emitted": False,
    "raw_command_values_emitted": False,
    "raw_output_values_emitted": False,
    "raw_diff_values_emitted": False,
    "raw_patch_values_emitted": False,
    "raw_source_values_emitted": False,
    "raw_url_values_emitted": False,
    "raw_path_values_emitted": False,
    "private_locator_values_emitted": False,
    "raw_row_values_emitted": False,
}

FORBIDDEN_SOURCE_KEYS = {
    "source_path",
    "path",
    "url",
    "uri",
    "command",
    "command_text",
    "output",
    "stdout",
    "stderr",
    "diff",
    "patch",
    "source",
    "source_text",
    "private_locator",
    "raw_text",
    "trace_text",
}

RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:Traceback \(most recent call last\)|stdout:|stderr:|stack trace|"
    r"terminal output:|command output:|git clone\s+\S|git apply\s+\S|"
    r"curl\s+\S|bash -|sh -|python -c)\b",
    re.IGNORECASE | re.MULTILINE,
)

OVERCLAIM_RE = re.compile(
    r"\b(?:admission|admitted|training|trainable|accepted|acceptance|proof|"
    r"execution succeeded|review executed|verified repair|closed loop|"
    r"level3 complete|level-3|patch-trace|patch applied|tests passed)\b",
    re.IGNORECASE,
)

ALLOWED_OVERCLAIM_CONTEXT_RE = re.compile(
    r"(false|zero|none|\bno\b|not_|blocked|fail_closed|fail-closed|no_|never|disallowed|"
    r"priority.only|priority only|not.admission|guardrail|counter|risk|unavailable|"
    r"requested|future|required|policy|claim_boundary|similarity|embedding|routing)",
    re.IGNORECASE,
)

NEAR_DUPLICATE_THRESHOLD = 0.86
REVIEW_DIVERSITY_THRESHOLD = 0.72

ALLOWED_LANGUAGE_FAMILIES = {
    "python",
    "rust",
    "c_cpp",
    "web_js_ts_html",
    "mixed",
    "unknown",
    "unknown_from_metadata",
    "missing_language_family",
}

ALLOWED_TASK_FAMILIES = {
    "transition_local_audit",
    "verifier_observation_support",
    "transition_next_action",
    "transition_candidate_selection",
    "transition_verifier_transition",
    "transition_continue_or_stop",
    "candidate_selection",
    "next_action",
    "verifier_transition",
    "continue_or_stop",
    "transition_candidate_review",
}

ALLOWED_SOURCE_ADAPTERS = {
    "session_like_transition_local",
}

ALLOWED_STATUS_FIELDS = {
    "missing_review",
    "not_structurally_recovered",
    "structurally_recovered",
    "missing_verifier_status",
    "missing_patch_status",
    "needs_manual_review",
    "semantic_review_only_blocked",
    "blocked_private_packet_or_policy_label_missing",
}

ALLOWED_PRIORITY_BUCKETS = set(priority for priority in (
    "manual_semantic_review_priority_if_private_packet_exists",
    "blocked_private_packet_or_policy_label_missing",
    "semantic_review_only_blocked",
    "verifier_nonpass_low_priority",
    "hard_rule_rejected_low_priority",
    "structural_recovery_required_before_private_review",
))


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


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def dig(row: dict[str, Any] | None, *path: str) -> Any:
    value: Any = row or {}
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def index_by(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row[key]): row for row in rows if row.get(key)}


def normalized_enum(value: Any, fallback: str) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return fallback
    if any(marker in text for marker in ("/", "\\", "://", "www.")):
        return fallback
    text = re.sub(r"[^a-z0-9_.:-]+", "_", text).strip("_")
    if not text or len(text) > 96:
        return fallback
    return text


def normalized_enum_list(values: Any) -> list[str]:
    normalized = [normalized_enum(value, "") for value in safe_list(values)]
    return sorted({value for value in normalized if value})


def bounded_enum(value: Any, allowed: set[str], fallback: str, namespace: str) -> str:
    normalized = normalized_enum(value, fallback)
    if normalized in allowed:
        return normalized
    if normalized == fallback:
        return fallback
    return f"other_{namespace}_hash_{stable_hash(normalized, 12)}"


def bounded_enum_list(values: Any, allowed: set[str], namespace: str) -> list[str]:
    bounded = [bounded_enum(value, allowed, "", namespace) for value in safe_list(values)]
    return sorted({value for value in bounded if value})


def source_guardrail_status(payload: dict[str, Any]) -> str:
    if not payload:
        return "missing_fail_closed"
    if payload.get("guardrail_scan_passed") is True:
        return "passed"
    guardrail = payload.get("guardrail_scan")
    if isinstance(guardrail, dict) and guardrail.get("scan_passed") is True:
        return "passed"
    if "guardrail_scan_passed" in payload or isinstance(guardrail, dict):
        return "failed_fail_closed"
    return "legacy_no_scan_fail_closed"


def input_status(items: list[tuple[str, Path, dict[str, Any]]]) -> dict[str, Any]:
    return {
        label: {
            "present": bool(payload),
            "stage": normalized_enum(payload.get("stage"), "unknown"),
            "decision_hash": stable_hash(payload.get("decision")),
            "guardrail_status": source_guardrail_status(payload),
            "summary_sha256_24": file_hash(path),
        }
        for label, path, payload in items
    }


def task_family_for(worklist: dict[str, Any], review: dict[str, Any] | None) -> str:
    expected = normalized_enum(worklist.get("expected_role"), "")
    classification = normalized_enum(worklist.get("classification"), "")
    recommendation = normalized_enum((review or {}).get("recommendation"), "")
    if expected:
        return expected
    if classification:
        return classification
    if recommendation:
        return f"semantic_review_{recommendation}"
    return "transition_candidate_review"


def priority_bucket(
    worklist: dict[str, Any],
    recovery: dict[str, Any] | None,
    review: dict[str, Any] | None,
) -> str:
    if not recovery:
        return "structural_recovery_required_before_private_review"
    recommendation = normalized_enum((review or {}).get("recommendation"), "")
    blockers = set(normalized_enum_list((review or {}).get("remaining_blockers")))
    if recommendation == "needs_manual_review":
        return "manual_semantic_review_priority_if_private_packet_exists"
    if "mixed_patch_status_repair_transition_rejected" in blockers or "patch_failed_repair_transition_rejected" in blockers:
        return "hard_rule_rejected_low_priority"
    if "verifier_nonpass_repair_transition_rejected" in blockers:
        return "verifier_nonpass_low_priority"
    if safe_dict(worklist.get("recovery_safety")).get("semantic_review_only") is True:
        return "semantic_review_only_blocked"
    return "blocked_private_packet_or_policy_label_missing"


def safe_candidate_hash_records(
    worklist_rows: list[dict[str, Any]],
    recovery_rows: list[dict[str, Any]],
    review_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    recovery_by_worklist = index_by(recovery_rows, "source_worklist_id")
    review_by_recovery = index_by(review_rows, "source_recovery_record_id")

    records: list[dict[str, Any]] = []
    for worklist in worklist_rows:
        worklist_id = str(worklist.get("worklist_id") or "")
        recovery = recovery_by_worklist.get(worklist_id)
        review = review_by_recovery.get(str((recovery or {}).get("recovery_record_id") or ""))

        source_adapter = bounded_enum("session_like_transition_local", ALLOWED_SOURCE_ADAPTERS, "unknown_source_adapter", "source_adapter")
        repo_family_token = normalized_enum(
            (review or {}).get("repo_family") or dig(recovery, "identity_recovery", "repo_family_candidate"),
            "missing_repo_family",
        )
        language_family = bounded_enum(
            dig(recovery, "identity_recovery", "language_candidate") or worklist.get("language_family"),
            ALLOWED_LANGUAGE_FAMILIES,
            "missing_language_family",
            "language_family",
        )
        task_family = bounded_enum(task_family_for(worklist, review), ALLOWED_TASK_FAMILIES, "transition_candidate_review", "task_family")
        rule_ids = [f"rule_hash_{stable_hash(value, 12)}" for value in normalized_enum_list((review or {}).get("rule_ids"))]
        blocker_codes = sorted(
            set(f"blocker_hash_{stable_hash(value, 12)}" for value in normalized_enum_list(worklist.get("blocker_classes")))
            | set(f"blocker_hash_{stable_hash(value, 12)}" for value in normalized_enum_list((recovery or {}).get("blocked_reasons")))
            | set(f"blocker_hash_{stable_hash(value, 12)}" for value in normalized_enum_list((review or {}).get("remaining_blockers")))
        ) or ["not_structurally_recovered"]
        next_action_count = len(safe_list((review or {}).get("next_materialization_actions")))
        recovery_status = "structurally_recovered" if recovery else "not_structurally_recovered"
        review_status = bounded_enum(
            (review or {}).get("review_status_class") or (review or {}).get("review_status"),
            ALLOWED_STATUS_FIELDS,
            "missing_review",
            "review_status",
        )
        verifier_status = bounded_enum(
            dig(recovery, "transition_recovery", "verifier_transition_candidate", "verifier_status_class"),
            ALLOWED_STATUS_FIELDS,
            "missing_verifier_status",
            "verifier_status",
        )
        patch_status = bounded_enum(
            dig(recovery, "transition_recovery", "verifier_transition_candidate", "patch_apply_status"),
            ALLOWED_STATUS_FIELDS,
            "missing_patch_status",
            "patch_status",
        )
        source_cluster_hash = stable_hash(
            {
                "source_adapter": source_adapter,
                "repo_family": repo_family_token,
                "language_family": language_family,
                "task_family": task_family,
            }
        )
        semantic_key_hash = stable_hash(
            {
                "rule_ids": rule_ids,
                "task_family": task_family,
                "blocked_reason_codes": blocker_codes,
            }
        )
        candidate_profile_hash = stable_hash(
            {
                "source_adapter": source_adapter,
                "repo_family_hash": stable_hash(repo_family_token),
                "language_family": language_family,
                "task_family": task_family,
                "rule_ids_hash": stable_hash(rule_ids),
                "blocker_codes": blocker_codes,
                "recovery_status": recovery_status,
                "review_status": review_status,
                "verifier_status": verifier_status,
                "patch_status": patch_status,
                "priority_bucket": priority_bucket(worklist, recovery, review),
                "next_action_count_bucket": min(next_action_count, 9),
            }
        )
        root_lineage_hash = stable_hash(
            {
                "source_adapter": source_adapter,
                "repo_family_hash": stable_hash(repo_family_token),
                "language_family": language_family,
                "task_family": task_family,
                "task_window_present": bool((review or {}).get("task_window_id") or (recovery or {}).get("task_window_id")),
            }
        )
        duplicate_cluster_hash = stable_hash(
            {
                "source_cluster_key_hash": source_cluster_hash,
                "semantic_key_hash": semantic_key_hash,
                "blocked_reason_codes": blocker_codes,
            }
        )
        feature_tokens = (
            [f"src:{source_adapter}", f"lang:{language_family}", f"task:{task_family}"]
            + [f"repo_hash:{stable_hash(repo_family_token)}"]
            + [f"rule:{stable_hash(rule)}" for rule in rule_ids]
            + [f"blocker:{code}" for code in blocker_codes]
            + [
                f"recovery:{recovery_status}",
                f"review:{review_status}",
                f"verifier:{verifier_status}",
                f"patch:{patch_status}",
                f"priority:{priority_bucket(worklist, recovery, review)}",
                f"action_count:{min(next_action_count, 9)}",
            ]
        )
        feature_tokens = sorted(set(feature_tokens))
        records.append(
            {
                "candidate_id_hash": stable_hash(
                    {
                        "candidate_ordinal": len(records),
                        "candidate_profile_hash": candidate_profile_hash,
                    }
                ),
                "root_lineage_key_hash": root_lineage_hash,
                "split_group_id_hash": stable_hash({"root_lineage_key_hash": root_lineage_hash, "gate": "blocked"}),
                "source_adapter": source_adapter,
                "repo_family_hash": stable_hash(repo_family_token),
                "language_family": language_family,
                "task_family": task_family,
                "transition_function_key_hash": stable_hash(
                    {
                        "task_family": task_family,
                        "verifier_status": verifier_status,
                        "patch_status": patch_status,
                        "blocker_codes": blocker_codes,
                    }
                ),
                "semantic_rule_id_hash": stable_hash({"rule_ids": rule_ids}) if rule_ids else "unavailable_hash",
                "candidate_action_set_hash": stable_hash({"next_action_count": next_action_count}),
                "semantic_key_hash": semantic_key_hash,
                "source_cluster_key_hash": source_cluster_hash,
                "deterministic_duplicate_cluster_id_hash": duplicate_cluster_hash,
                "priority_bucket": priority_bucket(worklist, recovery, review),
                "blocked_reason_codes": blocker_codes,
                "safe_embedding_feature_hash": stable_hash(feature_tokens),
                "safe_embedding_token_count": len(feature_tokens),
                "safe_embedding_tokens": feature_tokens,
            }
        )
    return records


def embedding_documents(records: list[dict[str, Any]]) -> list[str]:
    return [" ".join(str(token) for token in row["safe_embedding_tokens"]) for row in records]


def l2_normalize(matrix: Any) -> Any:
    import numpy as np

    arr = np.asarray(matrix, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    return arr / norms


def sklearn_embedding(records: list[dict[str, Any]]) -> tuple[Any, str, str, int]:
    import numpy as np
    from sklearn.decomposition import TruncatedSVD
    from sklearn.feature_extraction.text import TfidfVectorizer

    docs = embedding_documents(records)
    vectorizer = TfidfVectorizer(
        analyzer="word",
        token_pattern=r"(?u)\b[^\s]+\b",
        lowercase=False,
        norm="l2",
    )
    tfidf = vectorizer.fit_transform(docs)
    max_dim = min(64, max(1, tfidf.shape[0] - 1), max(1, tfidf.shape[1] - 1))
    if max_dim >= 2:
        vectors = TruncatedSVD(n_components=max_dim, random_state=12441).fit_transform(tfidf)
        return l2_normalize(vectors), "sklearn_tfidf_truncated_svd_cpu", "available_default_cpu", int(vectors.shape[1])
    vectors = tfidf.toarray()
    return l2_normalize(vectors), "sklearn_tfidf_cpu", "available_cpu_no_svd_needed", int(np.asarray(vectors).shape[1])


def hashing_vectorizer_embedding(records: list[dict[str, Any]], dimension: int = 64) -> tuple[Any, str, str, int]:
    from sklearn.feature_extraction.text import HashingVectorizer

    docs = embedding_documents(records)
    vectorizer = HashingVectorizer(
        analyzer="word",
        token_pattern=r"(?u)\b[^\s]+\b",
        lowercase=False,
        alternate_sign=True,
        norm="l2",
        n_features=dimension,
    )
    vectors = vectorizer.transform(docs).toarray()
    return l2_normalize(vectors), "sklearn_hashing_vectorizer_cpu", "fallback_available_cpu", dimension


def fallback_embedding(records: list[dict[str, Any]], dimension: int = 64) -> tuple[list[list[float]], str, str, int]:
    vectors: list[list[float]] = []
    for row in records:
        vector = [0.0] * dimension
        for token in row["safe_embedding_tokens"]:
            digest = hashlib.sha256(str(token).encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        vectors.append([value / norm for value in vector])
    return vectors, "deterministic_lexical_hashed_bag_of_features_cpu", "fallback_available_no_sklearn", dimension


def compute_embeddings(records: list[dict[str, Any]]) -> tuple[Any, str, str, int]:
    if not records:
        return [], "empty_no_embedding_backend_needed", "empty_corpus", 0
    try:
        return sklearn_embedding(records)
    except Exception:
        try:
            return hashing_vectorizer_embedding(records)
        except Exception:
            return fallback_embedding(records)


def cosine_matrix(vectors: Any) -> list[list[float]]:
    import numpy as np

    arr = l2_normalize(vectors)
    return np.clip(arr @ arr.T, -1.0, 1.0).tolist()


def near_duplicate_components(similarities: list[list[float]], threshold: float) -> list[list[int]]:
    graph: dict[int, list[int]] = defaultdict(list)
    n = len(similarities)
    for i in range(n):
        for j in range(i + 1, n):
            if similarities[i][j] >= threshold:
                graph[i].append(j)
                graph[j].append(i)

    seen: set[int] = set()
    components: list[list[int]] = []
    for start in range(n):
        if start in seen:
            continue
        queue: deque[int] = deque([start])
        seen.add(start)
        component: list[int] = []
        while queue:
            node = queue.popleft()
            component.append(node)
            for child in graph[node]:
                if child not in seen:
                    seen.add(child)
                    queue.append(child)
        components.append(sorted(component))
    return components


def novelty_bucket(score: float) -> str:
    if score >= 0.65:
        return "high_vector_novelty"
    if score >= 0.35:
        return "medium_vector_novelty"
    return "low_vector_novelty_near_duplicate_risk"


def priority_bucket_rank(bucket: str) -> int:
    ranks = {
        "manual_semantic_review_priority_if_private_packet_exists": 0,
        "blocked_private_packet_or_policy_label_missing": 1,
        "semantic_review_only_blocked": 2,
        "verifier_nonpass_low_priority": 3,
        "hard_rule_rejected_low_priority": 4,
        "structural_recovery_required_before_private_review": 5,
    }
    return ranks.get(bucket, 9)


def build_similarity_outputs(
    records: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    vectors, backend, backend_status, dimension = compute_embeddings(records)
    similarities = cosine_matrix(vectors) if records else []
    candidate_count = len(records)
    comparison_count = candidate_count * (candidate_count - 1) // 2
    near_pairs: list[tuple[int, int, float]] = []
    max_similarity_by_index = [0.0] * candidate_count
    for i in range(candidate_count):
        for j in range(i + 1, candidate_count):
            score = float(similarities[i][j])
            max_similarity_by_index[i] = max(max_similarity_by_index[i], score)
            max_similarity_by_index[j] = max(max_similarity_by_index[j], score)
            if score >= NEAR_DUPLICATE_THRESHOLD:
                near_pairs.append((i, j, score))

    components = near_duplicate_components(similarities, NEAR_DUPLICATE_THRESHOLD)
    cluster_id_by_index: dict[int, str] = {}
    cluster_rows: list[dict[str, Any]] = []
    for index, component in enumerate(components):
        members = [records[item]["candidate_id_hash"] for item in component]
        cluster_id = stable_hash({"near_duplicate_cluster_index": index, "members": sorted(members)})
        for item in component:
            cluster_id_by_index[item] = cluster_id
        max_internal = 1.0 if len(component) == 1 else max(
            float(similarities[i][j]) for offset, i in enumerate(component) for j in component[offset + 1 :]
        )
        cluster_rows.append(
            {
                "embedding_cluster_id_hash": cluster_id,
                "cluster_size": len(component),
                "cluster_type": "near_duplicate" if len(component) > 1 else "singleton",
                "max_internal_similarity_bucket": similarity_score_bucket(max_internal),
                "representative_candidate_id_hash": min(members),
                "member_candidate_id_hashes": sorted(members),
            }
        )

    priority_records: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        max_similarity = max_similarity_by_index[index]
        novelty = round(1.0 - max_similarity, 6)
        priority_records.append(
            {
                "candidate_id_hash": record["candidate_id_hash"],
                "root_lineage_key_hash": record["root_lineage_key_hash"],
                "split_group_id_hash": record["split_group_id_hash"],
                "source_adapter": record["source_adapter"],
                "repo_family_hash": record["repo_family_hash"],
                "language_family": record["language_family"],
                "task_family": record["task_family"],
                "transition_function_key_hash": record["transition_function_key_hash"],
                "semantic_rule_id_hash": record["semantic_rule_id_hash"],
                "candidate_action_set_hash": record["candidate_action_set_hash"],
                "semantic_key_hash": record["semantic_key_hash"],
                "source_cluster_key_hash": record["source_cluster_key_hash"],
                "deterministic_duplicate_cluster_id_hash": record["deterministic_duplicate_cluster_id_hash"],
                "embedding_feature_set_hash": record["safe_embedding_feature_hash"],
                "embedding_cluster_id_hash": cluster_id_by_index[index],
                "priority_bucket": record["priority_bucket"],
                "novelty_bucket": novelty_bucket(novelty),
                "max_similarity_bucket": similarity_score_bucket(max_similarity),
                "embedding_priority_score": round(
                    (priority_bucket_rank(record["priority_bucket"]) * 10.0)
                    - novelty
                    + (0.25 if max_similarity >= NEAR_DUPLICATE_THRESHOLD else 0.0),
                    6,
                ),
                "novelty_score": novelty,
                "blocked_reason_code_hashes": [stable_hash(code) for code in record["blocked_reason_codes"]],
            }
        )
    priority_records.sort(
        key=lambda row: (
            float(row["embedding_priority_score"]),
            str(row["embedding_cluster_id_hash"]),
            str(row["candidate_id_hash"]),
        )
    )
    for rank, row in enumerate(priority_records, start=1):
        row["embedding_priority_rank"] = rank

    near_duplicate_clusters = [row for row in cluster_rows if row["cluster_type"] == "near_duplicate"]
    singleton_clusters = [row for row in cluster_rows if row["cluster_type"] == "singleton"]
    denominator = candidate_count or 1
    novelty_counts = Counter(str(row["novelty_bucket"]) for row in priority_records)
    priority_bucket_counts = Counter(str(row["priority_bucket"]) for row in priority_records)
    max_similarity_bucket_counts = Counter(str(row["max_similarity_bucket"]) for row in priority_records)
    cluster_size_counts = Counter(str(row["cluster_size"]) for row in cluster_rows)
    records_by_cluster: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in priority_records:
        records_by_cluster[str(row["embedding_cluster_id_hash"])].append(row)

    representative_records: list[dict[str, Any]] = []
    for cluster_id, rows in records_by_cluster.items():
        best = sorted(
            rows,
            key=lambda row: (
                float(row["embedding_priority_score"]),
                str(row["candidate_id_hash"]),
            ),
        )[0]
        representative = {
            key: value
            for key, value in best.items()
            if key not in {"embedding_priority_rank"}
        }
        representative["represented_candidate_count"] = len(rows)
        representative["representative_selection_policy"] = (
            "lowest_embedding_priority_score_within_near_duplicate_cluster_public_safe"
        )
        representative_records.append(representative)
    representative_records.sort(
        key=lambda row: (
            float(row["embedding_priority_score"]),
            -int(row["represented_candidate_count"]),
            str(row["candidate_id_hash"]),
        )
    )
    for rank, row in enumerate(representative_records, start=1):
        row["representative_priority_rank"] = rank

    embedding_cluster_accounting = {
        "embedding_cluster_count": len(cluster_rows),
        "singleton_cluster_count": len(singleton_clusters),
        "near_duplicate_cluster_count": len(near_duplicate_clusters),
        "largest_cluster_size": max((int(row["cluster_size"]) for row in cluster_rows), default=0),
        "largest_cluster_share": round(max((int(row["cluster_size"]) for row in cluster_rows), default=0) / denominator, 6),
        "near_duplicate_cluster_max_share": round(
            max((row["cluster_size"] for row in near_duplicate_clusters), default=0) / denominator,
            6,
        ),
        "representative_priority_queue_count": len(representative_records),
        "candidate_vector_count": candidate_count,
        "candidate_to_representative_compression_ratio": round(
            candidate_count / max(1, len(representative_records)),
            6,
        ),
        "cluster_accounting_policy": (
            "cluster representatives are review-priority candidates only; they are not admission, labels, proof, or eval rows"
        ),
    }
    similarity_thresholds = {
        "near_duplicate_cosine_threshold": NEAR_DUPLICATE_THRESHOLD,
        "review_diversity_cosine_threshold": REVIEW_DIVERSITY_THRESHOLD,
    }
    similarity_histograms = {
        "novelty_bucket_counts": dict(sorted(novelty_counts.items())),
        "priority_bucket_counts": dict(sorted(priority_bucket_counts.items())),
        "max_similarity_bucket_counts": dict(sorted(max_similarity_bucket_counts.items())),
        "cluster_size_counts_top20": top_counts(cluster_size_counts),
    }
    summary = {
        "embedding_backend": backend,
        "embedding_backend_used": backend,
        "embedding_backend_status": backend_status,
        "embedding_backend_hash": stable_hash(backend),
        "embedding_vector_dim": dimension,
        "embedding_dimension": dimension,
        "embedding_input_field_names": EMBEDDING_INPUT_FIELD_NAMES,
        "embedding_input_profile_hash": stable_hash(
            [row["safe_embedding_feature_hash"] for row in records]
        ),
        "embedding_corpus_scope": "stage12387_12388_12389_public_safe_surrogate_candidate_metadata",
        "embedding_training_performed": False,
        "embedding_network_used": False,
        "embedding_gpu_used": False,
        "raw_vector_values_emitted": False,
        "candidate_vector_count": candidate_count,
        "near_duplicate_similarity_pair_count": len(near_pairs),
        "total_similarity_pair_count": comparison_count,
        "similarity_pair_count": len(near_pairs),
        "similarity_pair_count_semantics": "thresholded_near_duplicate_pairs_kept_for_backward_compatibility",
        "similarity_pair_comparison_count": comparison_count,
        "near_duplicate_threshold": NEAR_DUPLICATE_THRESHOLD,
        "review_diversity_threshold": REVIEW_DIVERSITY_THRESHOLD,
        "similarity_thresholds": similarity_thresholds,
        "near_duplicate_cluster_count": len(near_duplicate_clusters),
        "near_duplicate_cluster_max_share": round(max((row["cluster_size"] for row in near_duplicate_clusters), default=0) / denominator, 6),
        "novelty_bucket_counts": dict(sorted(novelty_counts.items())),
        "priority_bucket_counts": dict(sorted(priority_bucket_counts.items())),
        "max_similarity_bucket_counts": dict(sorted(max_similarity_bucket_counts.items())),
        "embedding_cluster_accounting": embedding_cluster_accounting,
        "similarity_histograms": similarity_histograms,
        "full_candidate_priority_queue_count": len(priority_records),
        "collapsed_representative_queue_count": len(representative_records),
        "collapsed_duplicate_candidate_count": max(0, len(priority_records) - len(representative_records)),
        "expansion_priority_queue_count": len(representative_records),
        "representative_priority_queue_count": len(representative_records),
    }
    cluster_summary = {
        **summary,
        "cluster_size_counts_top20": top_counts(Counter(str(row["cluster_size"]) for row in cluster_rows)),
        "near_duplicate_cluster_size_counts_top20": top_counts(
            Counter(str(row["cluster_size"]) for row in near_duplicate_clusters)
        ),
        "top_embedding_clusters": sorted(
            cluster_rows,
            key=lambda row: (-int(row["cluster_size"]), str(row["embedding_cluster_id_hash"])),
        )[:20],
    }
    return summary, priority_records, representative_records, cluster_summary


def similarity_score_bucket(score: float) -> str:
    if score >= 0.95:
        return "cosine_ge_0_95"
    if score >= NEAR_DUPLICATE_THRESHOLD:
        return "cosine_ge_0_86"
    if score >= REVIEW_DIVERSITY_THRESHOLD:
        return "cosine_ge_0_72"
    if score >= 0.50:
        return "cosine_ge_0_50"
    return "cosine_lt_0_50"


def top_counts(counter: Counter[str], limit: int = 20) -> dict[str, int]:
    return dict(sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit])


def public_artifact_manifest() -> list[dict[str, Any]]:
    names = [
        f"{STAGE}.json",
        "summary.json",
        "embedding_gate_card.json",
        "candidate_embedding_priority_records.jsonl",
        "candidate_embedding_representative_priority_records.jsonl",
        "similarity_cluster_summary.json",
        "guardrail_scan.json",
    ]
    return [
        {
            "artifact_file": name,
            "public_safe": True,
            "contains_raw_values": False,
            "raw_leak_count": 0,
            "overclaim_count": 0,
        }
        for name in names
    ]


def iter_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        strings: list[str] = []
        for key, child in value.items():
            lowered = str(key).lower()
            if lowered in FORBIDDEN_SOURCE_KEYS:
                strings.append(f"forbidden_source_key_present:{stable_hash(lowered)}")
            strings.extend(iter_strings(child))
        return strings
    if isinstance(value, list):
        strings = []
        for child in value:
            strings.extend(iter_strings(child))
        return strings
    return []


def scan_payload(label: str, payload: Any) -> list[str]:
    issues: list[str] = []
    for text in iter_strings(payload):
        if text.startswith("forbidden_source_key_present:"):
            issues.append(f"{label}:{text}")
            continue
        if RAW_LEAK_RE.search(text):
            issues.append(f"{label}:raw_leak_pattern:{stable_hash(text)}")
        for match in OVERCLAIM_RE.finditer(text):
            start = max(0, match.start() - 80)
            end = min(len(text), match.end() + 80)
            context = text[start:end]
            if not ALLOWED_OVERCLAIM_CONTEXT_RE.search(context):
                issues.append(f"{label}:overclaim_pattern:{stable_hash(context)}")
    return issues


def scan_artifact_set(artifact_set: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    main = safe_dict(artifact_set.get("main"))
    for key, expected in ZERO_COUNTERS.items():
        if main.get(key) != expected:
            issues.append(f"zero_counter_mismatch:{key}")
    if main.get("similarity_use_policy") != SIMILARITY_USE_POLICY:
        issues.append("similarity_use_policy_mismatch")
    if main.get("embedding_use_policy") != EMBEDDING_USE_POLICY:
        issues.append("embedding_use_policy_mismatch")
    similarity_policy = safe_dict(main.get("similarity_use_policy"))
    if similarity_policy.get("used_for_admission") is not False:
        issues.append("similarity_admission_policy_mismatch")
    if similarity_policy.get("used_for_labeling") is not False:
        issues.append("similarity_labeling_policy_mismatch")
    if similarity_policy.get("used_for_eval_selection") is not False:
        issues.append("similarity_eval_selection_policy_mismatch")
    embedding_policy = safe_dict(main.get("embedding_use_policy"))
    if embedding_policy.get("used_for_admission") is not False:
        issues.append("embedding_admission_policy_mismatch")
    if embedding_policy.get("used_for_labeling") is not False:
        issues.append("embedding_labeling_policy_mismatch")
    if embedding_policy.get("used_for_eval_selection") is not False:
        issues.append("embedding_eval_selection_policy_mismatch")
    if main.get("embedding_training_performed") is not False:
        issues.append("embedding_training_performed_mismatch")
    if main.get("embedding_network_used") is not False:
        issues.append("embedding_network_used_mismatch")
    if main.get("embedding_gpu_used") is not False:
        issues.append("embedding_gpu_used_mismatch")
    if main.get("raw_vector_values_emitted") is not False:
        issues.append("raw_vector_values_emitted_mismatch")
    candidate_vector_count = int(main.get("candidate_vector_count") or 0)
    representative_count = int(main.get("representative_priority_queue_count") or 0)
    collapsed_representative_count = int(main.get("collapsed_representative_queue_count") or 0)
    full_priority_count = int(main.get("full_candidate_priority_queue_count") or 0)
    collapsed_duplicate_count = int(main.get("collapsed_duplicate_candidate_count") or 0)
    if main.get("expansion_priority_queue_count") != representative_count:
        issues.append("expansion_queue_must_use_representative_count")
    if collapsed_representative_count != representative_count:
        issues.append("collapsed_representative_queue_count_mismatch")
    if full_priority_count != candidate_vector_count:
        issues.append("full_priority_queue_count_mismatch")
    if collapsed_duplicate_count != max(0, candidate_vector_count - representative_count):
        issues.append("collapsed_duplicate_candidate_count_mismatch")
    accounting = safe_dict(main.get("embedding_cluster_accounting"))
    if int(accounting.get("representative_priority_queue_count") or -1) != representative_count:
        issues.append("cluster_accounting_representative_count_mismatch")
    if int(accounting.get("candidate_vector_count") or -1) != candidate_vector_count:
        issues.append("cluster_accounting_candidate_vector_count_mismatch")
    if main.get("near_duplicate_similarity_pair_count") != main.get("similarity_pair_count"):
        issues.append("near_duplicate_similarity_pair_alias_mismatch")
    if main.get("total_similarity_pair_count") != main.get("similarity_pair_comparison_count"):
        issues.append("total_similarity_pair_alias_mismatch")
    for key, expected in RAW_CONTENT_POLICY.items():
        if safe_dict(main.get("raw_content_policy")).get(key) != expected:
            issues.append(f"raw_content_policy_mismatch:{key}")
    expected_blockers = [
        "policy_label_valid_zero",
        "private_review_packet_ready_zero",
        "level3_admission_blocked",
        "similarity_not_admission_authority",
    ]
    if main.get("hard_gate_blockers") != expected_blockers:
        issues.append("hard_gate_blockers_mismatch")
    for label, payload in artifact_set.items():
        if label != "guardrail_scan":
            issues.extend(scan_payload(label, payload))
    raw_leaks = [issue for issue in issues if ":raw_leak_pattern:" in issue or ":forbidden_source_key_present:" in issue]
    overclaims = [issue for issue in issues if ":overclaim_pattern:" in issue]
    return {
        "scan_passed": not issues,
        "issue_count": len(set(issues)),
        "issues": sorted(set(issues)),
        "raw_leak_count": len(set(raw_leaks)),
        "overclaim_count": len(set(overclaims)),
        "scan_scope": "stage12441_public_safe_embedding_hash_and_aggregate_artifacts",
        "raw_leak_policy": {
            "raw_urls_fail": True,
            "raw_paths_fail": True,
            "raw_diffs_or_patches_fail": True,
            "raw_commands_fail": True,
            "raw_outputs_fail": True,
            "private_locator_values_fail": True,
            "forbidden_raw_source_keys_fail": True,
        },
        "overclaim_policy": {
            "unqualified_admission_claim_fails": True,
            "unqualified_training_claim_fails": True,
            "unqualified_proof_claim_fails": True,
        },
    }


def build_artifact() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    stage12440 = read_json(STAGE12440_SUMMARY)
    stage12439 = read_json(STAGE12439_SUMMARY)
    stage12438 = read_json(STAGE12438_SUMMARY)
    worklist_rows = read_jsonl(STAGE12387_RECORDS)
    recovery_rows = read_jsonl(STAGE12388_RECORDS)
    review_rows = read_jsonl(STAGE12389_RECORDS)

    candidate_records = safe_candidate_hash_records(worklist_rows, recovery_rows, review_rows)
    embedding_summary, priority_records, representative_records, cluster_summary = build_similarity_outputs(candidate_records)
    carried_flow = safe_dict(stage12440.get("candidate_denominator_flow"))
    if not carried_flow:
        carried_flow = {
            "raw_or_worklist_candidates": len(worklist_rows),
            "structurally_recovered": len(recovery_rows),
            "private_review_packet_ready": 0,
            "policy_label_valid": 0,
            "level3_candidate": 0,
        }
    hard_gate_blockers = [
        "policy_label_valid_zero",
        "private_review_packet_ready_zero",
        "level3_admission_blocked",
        "similarity_not_admission_authority",
    ]
    deterministic_hard_gates_preserved = [
        "training_allowed_false",
        "admission_allowed_false",
        "execution_allowed_false",
        "admitted_rows_zero",
        "emitted_training_rows_zero",
        "countable_new_rows_zero",
        "level3_candidate_count_zero_until_policy_and_proof_gates_pass",
        "patch_trace_candidate_count_zero",
        "strict_no_eval_root_overlap_authority",
        "deterministic_exact_gate_blocked",
        "deterministic_lineage_gate_blocked",
        "deterministic_split_gate_blocked",
        "deterministic_proof_gate_blocked",
        "raw_private_value_leakage_blocked",
        "similarity_used_for_priority_only_not_labeling_or_admission",
    ]
    card = {
        "stage": STAGE,
        "record_type": "embedding_transition_candidate_expansion_gate_card_public_safe_v1",
        "supersedes_or_augments": "stage12440_diverse_transition_candidate_expansion_gate",
        "embedding_backend": embedding_summary["embedding_backend"],
        "embedding_backend_used": embedding_summary["embedding_backend_used"],
        "embedding_backend_status": embedding_summary["embedding_backend_status"],
        "embedding_backend_hash": embedding_summary["embedding_backend_hash"],
        "embedding_vector_dim": embedding_summary["embedding_vector_dim"],
        "embedding_dimension": embedding_summary["embedding_dimension"],
        "embedding_input_field_names": embedding_summary["embedding_input_field_names"],
        "embedding_input_profile_hash": embedding_summary["embedding_input_profile_hash"],
        "embedding_corpus_scope": embedding_summary["embedding_corpus_scope"],
        "embedding_training_performed": False,
        "embedding_network_used": False,
        "embedding_gpu_used": False,
        "raw_vector_values_emitted": False,
        "candidate_vector_count": embedding_summary["candidate_vector_count"],
        "similarity_pair_count": embedding_summary["similarity_pair_count"],
        "similarity_use_policy": SIMILARITY_USE_POLICY,
        "embedding_use_policy": EMBEDDING_USE_POLICY,
        "candidate_feature_contract": {
            "uses_raw_private_trace_text": False,
            "uses_raw_commands_outputs_diffs_source_urls": False,
            "uses_raw_option_prompt_path_url_command_output_diff_patch_source_locator_issue_rowid_private_note_values": False,
            "uses_target_labels_eval_gold_fields_or_model_outputs": False,
            "feature_material": "allowlisted_enum_role_status_blocker_fields_and_stage_salted_hash_indicators_only",
            "candidate_records_emit_raw_values": False,
        },
        "thresholds": {
            "near_duplicate_cosine_threshold": NEAR_DUPLICATE_THRESHOLD,
            "review_diversity_cosine_threshold": REVIEW_DIVERSITY_THRESHOLD,
        },
        "hard_gate_blockers": hard_gate_blockers,
        "deterministic_hard_gates_preserved": deterministic_hard_gates_preserved,
    }
    artifact: dict[str, Any] = {
        "stage": STAGE,
        "record_type": "embedding_transition_candidate_expansion_gate_public_safe_v1",
        "decision": "fail_closed_embedding_transition_candidate_expansion_gate_ready",
        "supersedes_or_augments": "stage12440_diverse_transition_candidate_expansion_gate",
        **ZERO_COUNTERS,
        **embedding_summary,
        "similarity_use_policy": SIMILARITY_USE_POLICY,
        "embedding_use_policy": EMBEDDING_USE_POLICY,
        "embedding_input_contract": {
            "embedding_input_field_names": EMBEDDING_INPUT_FIELD_NAMES,
            "allowlisted_or_stage_salted_hash_bucket_inputs_only": True,
            "allowlisted_inputs_only": False,
            "allowed_input_classes": [
                "enum_fields",
                "role_fields",
                "status_fields",
                "blocker_code_fields",
                "stage_salted_hash_indicators",
                "safe_count_buckets",
            ],
            "forbidden_raw_input_classes": [
                "raw_option_values",
                "prompt_or_input_text",
                "paths",
                "urls",
                "commands",
                "outputs",
                "diffs",
                "patches",
                "source_snippets",
                "locators",
                "issue_bodies",
                "row_ids",
                "private_notes",
                "target_labels",
                "eval_or_gold_fields",
                "model_outputs",
            ],
            "embedding_input_profile_hash": embedding_summary["embedding_input_profile_hash"],
            "raw_vector_values_emitted": False,
        },
        "candidate_embedding_records_path": "runs/local/artifacts/stage12441_embedding_transition_candidate_expansion_gate/candidate_embedding_priority_records.jsonl",
        "representative_priority_records_path": "runs/local/artifacts/stage12441_embedding_transition_candidate_expansion_gate/candidate_embedding_representative_priority_records.jsonl",
        "deterministic_hard_gates_preserved": deterministic_hard_gates_preserved,
        "candidate_denominator_flow": carried_flow,
        "hard_gate_blockers": hard_gate_blockers,
        "raw_content_policy": RAW_CONTENT_POLICY,
        "candidate_hash_record_contract": {
            "candidate_records_public_safe": True,
            "raw_values_emitted": False,
            "raw_or_private_fields_forbidden": sorted(FORBIDDEN_SOURCE_KEYS),
            "safe_record_fields": sorted(priority_records[0].keys()) if priority_records else [],
        },
        "input_status": input_status(
            [
                ("stage12440", STAGE12440_SUMMARY, stage12440),
                ("stage12439", STAGE12439_SUMMARY, stage12439),
                ("stage12438", STAGE12438_SUMMARY, stage12438),
            ]
        ),
        "source_record_counts": {
            "stage12387_public_safe_worklist_rows": len(worklist_rows),
            "stage12388_public_safe_recovery_rows": len(recovery_rows),
            "stage12389_public_safe_review_rows": len(review_rows),
        },
        "claim_boundary": (
            "public-safe fail-closed embedding expansion gate; vector similarity orders a future review queue only; "
            "no row admission, no labels, no eval selection, no execution, and no training emission"
        ),
        "embedding_gate_card_hash": stable_hash(card),
        "similarity_cluster_summary_hash": stable_hash(cluster_summary),
        "public_artifact_manifest": public_artifact_manifest(),
        "summary_hash": "pending",
    }

    artifact_set = {
        "main": artifact,
        "embedding_gate_card": card,
        "candidate_embedding_priority_records": priority_records,
        "candidate_embedding_representative_priority_records": representative_records,
        "similarity_cluster_summary": cluster_summary,
        "public_artifact_manifest": artifact["public_artifact_manifest"],
    }
    guardrail = scan_artifact_set(artifact_set)
    artifact["guardrail_scan"] = guardrail
    artifact["guardrail_scan_passed"] = guardrail["scan_passed"]
    artifact["raw_leak_count"] = guardrail["raw_leak_count"]
    artifact["overclaim_count"] = guardrail["overclaim_count"]
    artifact["summary_hash"] = stable_hash({key: value for key, value in artifact.items() if key != "summary_hash"})

    artifact_set["main"] = artifact
    guardrail = scan_artifact_set(artifact_set)
    artifact["guardrail_scan"] = guardrail
    artifact["guardrail_scan_passed"] = guardrail["scan_passed"]
    artifact["raw_leak_count"] = guardrail["raw_leak_count"]
    artifact["overclaim_count"] = guardrail["overclaim_count"]
    artifact["summary_hash"] = stable_hash({key: value for key, value in artifact.items() if key != "summary_hash"})
    return artifact, card, priority_records, representative_records, cluster_summary


def main() -> None:
    artifact, card, priority_records, representative_records, cluster_summary = build_artifact()
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / f"{STAGE}.json", artifact)
    write_json(OUT / "summary.json", artifact)
    write_json(SUMMARY, artifact)
    write_json(OUT / "embedding_gate_card.json", card)
    write_jsonl(OUT / "candidate_embedding_priority_records.jsonl", priority_records)
    write_jsonl(OUT / "candidate_embedding_representative_priority_records.jsonl", representative_records)
    write_json(OUT / "similarity_cluster_summary.json", cluster_summary)
    write_json(OUT / "guardrail_scan.json", artifact["guardrail_scan"])
    print(
        json.dumps(
            {
                "stage": artifact["stage"],
                "decision": artifact["decision"],
                "embedding_backend": artifact["embedding_backend"],
                "embedding_backend_used": artifact["embedding_backend_used"],
                "embedding_backend_status": artifact["embedding_backend_status"],
                "embedding_backend_hash": artifact["embedding_backend_hash"],
                "embedding_vector_dim": artifact["embedding_vector_dim"],
                "embedding_dimension": artifact["embedding_dimension"],
                "candidate_vector_count": artifact["candidate_vector_count"],
                "near_duplicate_similarity_pair_count": artifact["near_duplicate_similarity_pair_count"],
                "total_similarity_pair_count": artifact["total_similarity_pair_count"],
                "similarity_pair_count": artifact["similarity_pair_count"],
                "near_duplicate_cluster_count": artifact["near_duplicate_cluster_count"],
                "near_duplicate_cluster_max_share": artifact["near_duplicate_cluster_max_share"],
                "novelty_bucket_counts": artifact["novelty_bucket_counts"],
                "full_candidate_priority_queue_count": artifact["full_candidate_priority_queue_count"],
                "collapsed_representative_queue_count": artifact["collapsed_representative_queue_count"],
                "collapsed_duplicate_candidate_count": artifact["collapsed_duplicate_candidate_count"],
                "expansion_priority_queue_count": artifact["expansion_priority_queue_count"],
                "guardrail_scan_passed": artifact["guardrail_scan_passed"],
                "raw_leak_count": artifact["raw_leak_count"],
                "overclaim_count": artifact["overclaim_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
