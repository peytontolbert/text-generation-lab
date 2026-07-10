from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from long_context_common import write_json
from materialize_trainer_setup import read_jsonl

TOKEN_RE = re.compile(r"[A-Za-z0-9_./:-]+")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_training_rows_from_shard_manifest(
    *,
    strict_shard_manifest_path: Path,
    include_audit_only_direct: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    manifest = _load_json(strict_shard_manifest_path)
    selected = [dict(row) for row in manifest.get("selected_shards") or [] if isinstance(row, dict)]

    loaded_rows: list[dict[str, Any]] = []
    included_shards: list[str] = []
    excluded_shards: list[dict[str, str]] = []
    duplicate_pack_ids = 0
    seen_pack_ids: set[str] = set()

    for shard in selected:
        acceptance_mode = str(shard.get("acceptance_mode") or "")
        if acceptance_mode == "audit_only_direct" and not include_audit_only_direct:
            excluded_shards.append({"name": str(shard.get("name") or ""), "reason": "audit_only_direct_excluded"})
            continue
        if not bool(shard.get("ready_for_training")):
            excluded_shards.append({"name": str(shard.get("name") or ""), "reason": "not_ready_for_training"})
            continue
        training_rows_path = Path(str(((shard.get("artifacts") or {}).get("training_rows_jsonl") or "")).strip())
        if not training_rows_path.exists():
            raise ValueError(f"missing_training_rows_jsonl:{training_rows_path}")
        shard_rows = read_jsonl(training_rows_path)
        included_shards.append(str(shard.get("name") or ""))
        for row in shard_rows:
            pack_id = str(row.get("pack_id") or "")
            if not pack_id:
                raise ValueError(f"missing_pack_id:{training_rows_path}")
            if pack_id in seen_pack_ids:
                duplicate_pack_ids += 1
                continue
            seen_pack_ids.add(pack_id)
            loaded_rows.append(row)

    if not loaded_rows:
        raise ValueError("no_training_rows_loaded_from_strict_shard_manifest")

    source_summary = {
        "source_mode": "strict_shard_manifest",
        "strict_shard_manifest_path": str(strict_shard_manifest_path),
        "include_audit_only_direct": bool(include_audit_only_direct),
        "included_shards": included_shards,
        "excluded_shards": excluded_shards,
        "loaded_pack_count": len(loaded_rows),
        "duplicate_pack_ids_dropped": duplicate_pack_ids,
    }
    return loaded_rows, source_summary


def _load_trainer_rows(
    *,
    trainer_rows_path: Path | None,
    strict_shard_manifest_path: Path | None,
    include_audit_only_direct: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if trainer_rows_path is not None and strict_shard_manifest_path is not None:
        raise ValueError("trainer_rows_path_and_strict_shard_manifest_path_are_mutually_exclusive")
    if trainer_rows_path is None and strict_shard_manifest_path is None:
        raise ValueError("trainer_rows_path_or_strict_shard_manifest_path_required")
    if trainer_rows_path is not None:
        return read_jsonl(trainer_rows_path), {
            "source_mode": "trainer_rows_jsonl",
            "trainer_rows_path": str(trainer_rows_path),
            "include_audit_only_direct": bool(include_audit_only_direct),
        }
    assert strict_shard_manifest_path is not None
    return _load_training_rows_from_shard_manifest(
        strict_shard_manifest_path=strict_shard_manifest_path,
        include_audit_only_direct=include_audit_only_direct,
    )


def _parse_json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return dict(parsed)
    return {}


def _clean_scalar_text(value: Any) -> str:
    return str(value or "").strip()


def _clean_string_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    cleaned: list[str] = []
    for value in values:
        text = _clean_scalar_text(value)
        if text:
            cleaned.append(text)
    return cleaned


def _compact_list(values: Any, *, limit: int = 8) -> list[str]:
    items = _clean_string_list(values)
    if len(items) <= limit:
        return items
    return items[:limit]


def _infer_state_variable(final_state: dict[str, Any]) -> str:
    preferred_keys = [
        "verification_targets",
        "expected_changed_files",
        "key_symbols",
        "commit_subject",
        "commit_sha",
        "execution_route",
        "test_selection_route",
    ]
    for key in preferred_keys:
        if key in final_state and final_state.get(key) not in ({}, [], "", None):
            return key
    for key, value in final_state.items():
        if value not in ({}, [], "", None):
            return str(key)
    return "structured_final_state"


def _normalize_target_row(target_row: dict[str, Any]) -> dict[str, Any]:
    final_state = _parse_json_dict(target_row.get("final_state"))
    if not final_state:
        final_state = _parse_json_dict(target_row.get("final_state_json"))
    query_text = _clean_scalar_text(target_row.get("query_text"))
    program_id = _clean_scalar_text(target_row.get("program_id"))
    state_variable = _clean_scalar_text(target_row.get("state_variable")) or _infer_state_variable(final_state)
    canonical_name = _clean_scalar_text(target_row.get("canonical_name")) or program_id or state_variable
    seed_paths = _clean_string_list(target_row.get("seed_paths"))
    selected_tests = _clean_string_list(target_row.get("selected_tests"))
    seed_symbols = _clean_string_list(target_row.get("seed_symbols"))
    execution_route = _clean_scalar_text(target_row.get("execution_route") or final_state.get("execution_route"))
    test_selection_route = _clean_scalar_text(target_row.get("test_selection_route") or final_state.get("test_selection_route"))

    if not final_state:
        raise ValueError(f"blank_final_state:{target_row.get('example_id') or target_row.get('query_index')}")
    if not canonical_name:
        raise ValueError(f"blank_canonical_name:{target_row.get('example_id') or target_row.get('query_index')}")
    if not state_variable:
        raise ValueError(f"blank_state_variable:{target_row.get('example_id') or target_row.get('query_index')}")

    return {
        **target_row,
        "query_text": query_text,
        "program_id": program_id,
        "final_state": final_state,
        "state_variable": state_variable,
        "canonical_name": canonical_name,
        "seed_paths": seed_paths,
        "selected_tests": selected_tests,
        "seed_symbols": seed_symbols,
        "execution_route": execution_route,
        "test_selection_route": test_selection_route,
    }


def _full_context_target_text(target_rows: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for row in target_rows:
        normalized = _normalize_target_row(row)
        lines.append(
            json.dumps(
                {
                    "canonical_name": normalized["canonical_name"],
                    "state_variable": normalized["state_variable"],
                    "final_state": normalized["final_state"],
                },
                sort_keys=True,
            )
        )
    return "\n".join(lines)


def _query_text(target_row: dict[str, Any]) -> str:
    normalized = _normalize_target_row(target_row)
    final_state = dict(normalized.get("final_state") or {})
    query_text = _clean_scalar_text(normalized.get("query_text"))
    query_index = int(normalized.get("query_index") or 0)
    state_variable = str(normalized.get("state_variable") or "structured_final_state")
    changed_files = _compact_list(final_state.get("expected_changed_files") or normalized.get("seed_paths"))
    verification_targets = _compact_list(final_state.get("verification_targets") or normalized.get("selected_tests"))
    key_symbols = _compact_list(final_state.get("key_symbols") or normalized.get("seed_symbols"))

    lines = [
        f"Repository: {normalized.get('canonical_name') or normalized.get('program_id') or 'unknown'}",
        f"Query index: {query_index}",
        f"Transition target: {state_variable}",
    ]
    if normalized.get("execution_route"):
        lines.append(f"Execution route: {normalized['execution_route']}")
    if normalized.get("test_selection_route"):
        lines.append(f"Verifier route: {normalized['test_selection_route']}")
    if changed_files:
        lines.append(f"Changed files: {', '.join(changed_files)}")
    if verification_targets:
        lines.append(f"Verification targets: {', '.join(verification_targets)}")
    if key_symbols:
        lines.append(f"Key symbols: {', '.join(key_symbols)}")
    if query_text:
        lines.append(f"Task: {' '.join(query_text.split())}")
    else:
        lines.append("Task: Reconstruct the transition outcome using the provided long-context evidence.")
    return "\n".join(lines)


def _support_terms(target_row: dict[str, Any]) -> tuple[list[str], list[str]]:
    normalized = _normalize_target_row(target_row)
    final_state = dict(normalized.get("final_state") or {})
    exact_paths: list[str] = []
    lexical_terms: list[str] = []

    def add_path_terms(values: Any) -> None:
        for value in values or []:
            text = _clean_scalar_text(value)
            if not text:
                continue
            exact_paths.append(text.lower())
            lexical_terms.extend(token.lower() for token in TOKEN_RE.findall(text) if len(token) >= 3)

    def add_scalar_terms(values: Any) -> None:
        for value in values or []:
            text = _clean_scalar_text(value)
            if not text:
                continue
            lexical_terms.extend(token.lower() for token in TOKEN_RE.findall(text) if len(token) >= 3)

    add_path_terms(final_state.get("expected_changed_files"))
    add_path_terms(final_state.get("verification_targets"))
    add_path_terms(normalized.get("seed_paths"))
    add_path_terms(normalized.get("selected_tests"))
    add_scalar_terms(final_state.get("key_symbols"))
    add_scalar_terms(normalized.get("seed_symbols"))
    add_scalar_terms(final_state.keys())
    add_scalar_terms(final_state.values())
    add_scalar_terms(
        [
            normalized.get("canonical_name"),
            normalized.get("state_variable"),
            normalized.get("program_id"),
            normalized.get("execution_route"),
            normalized.get("test_selection_route"),
            normalized.get("query_text"),
            final_state.get("commit_subject"),
            final_state.get("commit_sha"),
        ]
    )
    if not exact_paths and not lexical_terms:
        raise ValueError(f"no_support_terms_derived:{target_row.get('example_id') or target_row.get('query_index')}")
    return list(dict.fromkeys(exact_paths)), list(dict.fromkeys(term for term in lexical_terms if term))


def _prepare_context_rows(context_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for ordinal, row in enumerate(context_rows):
        path_text = _clean_scalar_text(row.get("path")).lower()
        text = _clean_scalar_text(row.get("text")).lower()
        tokens = {token.lower() for token in TOKEN_RE.findall(f"{path_text} {text}") if len(token) >= 3}
        prepared.append(
            {
                "ordinal": ordinal,
                "chunk_id": _clean_scalar_text(row.get("chunk_id")),
                "path": _clean_scalar_text(row.get("path")),
                "path_text": path_text,
                "haystack": f"{path_text} {text}",
                "token_set": tokens,
                "role": str(row.get("role") or ""),
                "source_type": str(row.get("source_type") or ""),
                "source_id": str(row.get("source_id") or ""),
            }
        )
    return prepared


def _support_reasons(*, path_hits: int, lexical_hits: int, role_bonus: int, prepared: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if path_hits > 0:
        reasons.append("path_hit")
    if lexical_hits > 0:
        reasons.append("lexical_hit")
    if prepared.get("role") == "verification_constraint":
        reasons.append("verifier_target_hit")
    elif prepared.get("role") in {"seed_change", "repo_graph_neighbor"}:
        reasons.append("changed_file_hit")
    if role_bonus > 0:
        reasons.append("role_bonus")
    if any(part in prepared.get("path_text", "") for part in ("tests/", "test_")):
        reasons.append("test_path_hint")
    return reasons


def _role_bonus(role: str) -> int:
    if role == "verification_constraint":
        return 4
    if role == "seed_change":
        return 2
    if role in {"test_neighbor", "repo_graph_neighbor"}:
        return 1
    return 0


def _scored_support_rows(target_row: dict[str, Any], prepared_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    exact_paths, lexical_terms = _support_terms(target_row)
    lexical_term_set = {term for term in lexical_terms if term}
    scored_rows: list[dict[str, Any]] = []
    for prepared in prepared_rows:
        chunk_id = prepared["chunk_id"]
        if not chunk_id:
            continue
        path_text = prepared["path_text"]
        haystack = prepared["haystack"]
        token_set = prepared["token_set"]
        path_hits = sum(1 for path in exact_paths if path and (path_text.endswith(path) or path in haystack))
        lexical_hits = len(token_set & lexical_term_set)
        role_bonus = _role_bonus(prepared["role"])
        score = path_hits * 10 + lexical_hits + role_bonus
        if score <= 0:
            continue
        scored_rows.append(
            {
                "chunk_id": chunk_id,
                "score": score,
                "path_hits": path_hits,
                "lexical_hits": lexical_hits,
                "role_bonus": role_bonus,
                "source_type": prepared.get("source_type") or "",
                "source_id": prepared.get("source_id") or "",
                "role": prepared.get("role") or "",
                "path": prepared.get("path") or "",
                "ordinal": int(prepared.get("ordinal") or 0),
                "support_reasons": _support_reasons(path_hits=path_hits, lexical_hits=lexical_hits, role_bonus=role_bonus, prepared=prepared),
            }
        )
    scored_rows.sort(key=lambda item: (item["score"], item["path_hits"], -item["ordinal"], item["chunk_id"]), reverse=True)
    if not scored_rows:
        raise ValueError(f"no_positive_chunks_derived:{target_row.get('example_id') or target_row.get('query_index')}")
    return scored_rows


def _join_type(scored_rows: list[dict[str, Any]]) -> str:
    if not scored_rows:
        return "single_source"
    source_types = {str(row.get("source_type") or "") for row in scored_rows if str(row.get("source_type") or "")}
    source_ids = {str(row.get("source_id") or "") for row in scored_rows if str(row.get("source_id") or "")}
    paths = [str(row.get("path") or "").lower() for row in scored_rows]
    has_repo = bool(source_types & {"repo", "local_repo"})
    has_paper = "paper" in source_types
    has_dataset = "dataset" in source_types
    has_session = any(source in {"session", "trace", "transcript"} for source in source_types)
    has_test = any("tests/" in path or "/test_" in path or path.startswith("tests/") or "test_" in Path(path).name for path in paths)
    if len(source_ids) >= 2 and has_repo:
        return "multi_repo"
    if has_repo and has_paper:
        return "repo+paper"
    if has_repo and has_session:
        return "repo+session"
    if has_repo and has_dataset:
        return "repo+dataset"
    if has_repo and has_test:
        return "repo+test"
    if len(source_types) >= 2:
        return "multi_source"
    return "single_source"


def _retrieval_supervision_payload(target_row: dict[str, Any], prepared_rows: list[dict[str, Any]], *, max_positive_chunks: int) -> dict[str, Any]:
    scored_rows = _scored_support_rows(target_row, prepared_rows)
    positives = scored_rows[:max_positive_chunks]
    positive_ids = [row["chunk_id"] for row in positives]
    hard_negatives: list[dict[str, Any]] = []
    positive_id_set = set(positive_ids)
    for row in scored_rows[max_positive_chunks:]:
        if row["chunk_id"] in positive_id_set:
            continue
        if row["path_hits"] > 0:
            continue
        if row["lexical_hits"] <= 0:
            continue
        hard_negatives.append(row)
        if len(hard_negatives) >= max_positive_chunks:
            break
    support_scores = []
    for row in positives + hard_negatives:
        support_scores.append(
            {
                "chunk_id": row["chunk_id"],
                "score": row["score"],
                "path_hits": row["path_hits"],
                "lexical_hits": row["lexical_hits"],
                "role_bonus": row["role_bonus"],
                "source_type": row["source_type"],
                "role": row["role"],
                "support_reasons": row["support_reasons"],
            }
        )
    return {
        "positive_chunk_ids": positive_ids,
        "hard_negative_chunk_ids": [row["chunk_id"] for row in hard_negatives],
        "support_scores": support_scores,
        "join_type": _join_type(positives),
    }


def _memory_target(row: dict[str, Any], target_rows: list[dict[str, Any]], context_rows: list[dict[str, Any]]) -> dict[str, Any]:
    normalized_targets = [_normalize_target_row(item) for item in target_rows]
    state_variables = [str(item.get("state_variable") or "") for item in normalized_targets]
    canonical_names = [str(item.get("canonical_name") or "") for item in normalized_targets]
    if any(not value for value in state_variables):
        raise ValueError(f"blank_memory_state_variable:{row.get('pack_id')}")
    if any(not value for value in canonical_names):
        raise ValueError(f"blank_memory_canonical_name:{row.get('pack_id')}")
    return {
        "pack_id": str(row.get("pack_id") or ""),
        "trainer_policy_mode": str(row.get("trainer_policy_mode") or ""),
        "overlap_family_id": str(row.get("overlap_family_id") or ""),
        "candidate_count": int(row.get("candidate_count") or 0),
        "chunk_count": int(row.get("chunk_count") or 0),
        "state_variables": state_variables,
        "canonical_names": canonical_names,
        "source_types": sorted({str(item.get("source_type") or "") for item in context_rows if str(item.get("source_type") or "")}),
    }


def compile_long_context_pack_trainer_rows(
    *,
    trainer_rows_path: Path | None = None,
    strict_shard_manifest_path: Path | None = None,
    include_audit_only_direct: bool = False,
    max_positive_chunks: int = 8,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    trainer_rows, source_summary = _load_trainer_rows(
        trainer_rows_path=trainer_rows_path,
        strict_shard_manifest_path=strict_shard_manifest_path,
        include_audit_only_direct=include_audit_only_direct,
    )

    full_context_rows: list[dict[str, Any]] = []
    retrieval_rows: list[dict[str, Any]] = []
    memory_rows: list[dict[str, Any]] = []
    split_counts: Counter[str] = Counter()
    mode_counts: Counter[str] = Counter()

    for row in trainer_rows:
        pack_id = str(row.get("pack_id") or "")
        if not pack_id:
            raise ValueError("missing_pack_id")
        effective_split = str(row.get("effective_split") or "train")
        trainer_policy_mode = str(row.get("trainer_policy_mode") or "")
        prompt_text = str(row.get("prompt_text") or "")
        context_rows = row.get("context_rows") or []
        target_rows = [_normalize_target_row(item) for item in (row.get("target_rows") or [])]
        prepared_context_rows = _prepare_context_rows(context_rows)
        if not target_rows:
            raise ValueError(f"missing_target_rows:{pack_id}")
        if not context_rows:
            raise ValueError(f"missing_context_rows:{pack_id}")

        split_counts[effective_split] += 1
        mode_counts[trainer_policy_mode] += 1

        full_context_rows.append(
            {
                "row_id": f"full::{pack_id}",
                "pack_id": pack_id,
                "task_type": "full_context_state_reconstruction",
                "effective_split": effective_split,
                "trainer_policy_mode": trainer_policy_mode,
                "overlap_family_id": str(row.get("overlap_family_id") or ""),
                "prompt_text": prompt_text,
                "context_rows": context_rows,
                "target_text": _full_context_target_text(target_rows),
                "metadata": {
                    "candidate_count": int(row.get("candidate_count") or 0),
                    "chunk_count": int(row.get("chunk_count") or 0),
                    "pack_token_count": int(row.get("pack_token_count") or 0),
                },
            }
        )

        for target_row in target_rows:
            retrieval_payload = _retrieval_supervision_payload(target_row, prepared_context_rows, max_positive_chunks=max_positive_chunks)
            retrieval_rows.append(
                {
                    "row_id": f"retrieval::{pack_id}::{int(target_row.get('query_index') or 0)}",
                    "pack_id": pack_id,
                    "task_type": "retrieval_supervision",
                    "effective_split": effective_split,
                    "trainer_policy_mode": trainer_policy_mode,
                    "overlap_family_id": str(row.get("overlap_family_id") or ""),
                    "query_text": _query_text(target_row),
                    "positive_chunk_ids": retrieval_payload["positive_chunk_ids"],
                    "hard_negative_chunk_ids": retrieval_payload["hard_negative_chunk_ids"],
                    "support_scores": retrieval_payload["support_scores"],
                    "join_type": retrieval_payload["join_type"],
                    "target_text": json.dumps(
                        {
                            "canonical_name": target_row.get("canonical_name") or "",
                            "state_variable": target_row.get("state_variable") or "structured_final_state",
                            "final_state": target_row.get("final_state") or {},
                        },
                        sort_keys=True,
                    ),
                    "metadata": {
                        "canonical_name": str(target_row.get("canonical_name") or ""),
                        "query_index": int(target_row.get("query_index") or 0),
                    },
                }
            )

        memory_rows.append(
            {
                "row_id": f"memory::{pack_id}",
                "pack_id": pack_id,
                "task_type": "state_summary_compression",
                "effective_split": effective_split,
                "trainer_policy_mode": trainer_policy_mode,
                "overlap_family_id": str(row.get("overlap_family_id") or ""),
                "input_text": f"Summarize the persistent working memory for pack {pack_id}.",
                "target_text": json.dumps(_memory_target(row, target_rows, context_rows), sort_keys=True),
                "metadata": {
                    "candidate_count": int(row.get("candidate_count") or 0),
                    "chunk_count": int(row.get("chunk_count") or 0),
                },
            }
        )

    buckets = {
        "full_context_rows": full_context_rows,
        "retrieval_rows": retrieval_rows,
        "memory_rows": memory_rows,
    }
    summary = {
        "trainer_rows": len(trainer_rows),
        "full_context_rows": len(full_context_rows),
        "retrieval_rows": len(retrieval_rows),
        "memory_rows": len(memory_rows),
        "effective_split_counts": dict(sorted(split_counts.items())),
        "trainer_policy_mode_counts": dict(sorted(mode_counts.items())),
        "max_positive_chunks": int(max_positive_chunks),
        "full_context_format": "structured_prompt_plus_context_rows",
        "source_summary": source_summary,
    }
    return buckets, summary


def stream_compile_long_context_pack_trainer_rows(
    *,
    output_dir: Path,
    trainer_rows_path: Path | None = None,
    strict_shard_manifest_path: Path | None = None,
    include_audit_only_direct: bool = False,
    max_positive_chunks: int = 8,
) -> dict[str, Any]:
    buckets, summary = compile_long_context_pack_trainer_rows(
        trainer_rows_path=trainer_rows_path,
        strict_shard_manifest_path=strict_shard_manifest_path,
        include_audit_only_direct=include_audit_only_direct,
        max_positive_chunks=max_positive_chunks,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    output_map = {
        "full_context_rows": output_dir / "full_context_rows.jsonl",
        "retrieval_rows": output_dir / "retrieval_rows.jsonl",
        "memory_rows": output_dir / "memory_rows.jsonl",
    }
    for bucket_name, output_path in output_map.items():
        with output_path.open("w", encoding="utf-8") as handle:
            for row in buckets[bucket_name]:
                handle.write(json.dumps(row, sort_keys=True) + "\n")
    write_json(output_dir / "compile_card.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile long-context pack trainer rows into model-consumable training shards.")
    parser.add_argument("--trainer-rows", type=Path)
    parser.add_argument("--strict-shard-manifest", type=Path)
    parser.add_argument("--include-audit-only-direct", action="store_true")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-positive-chunks", type=int, default=8)
    args = parser.parse_args()
    stream_compile_long_context_pack_trainer_rows(
        trainer_rows_path=args.trainer_rows,
        strict_shard_manifest_path=args.strict_shard_manifest,
        include_audit_only_direct=args.include_audit_only_direct,
        output_dir=args.output_dir,
        max_positive_chunks=args.max_positive_chunks,
    )


if __name__ == "__main__":
    main()
