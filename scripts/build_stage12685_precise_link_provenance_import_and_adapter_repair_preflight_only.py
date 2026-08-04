#!/usr/bin/env python3
"""Materialize private precise-link provenance and a non-leaky pair adapter."""
from __future__ import annotations

import ast
import collections
import functools
import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12685_precise_link_provenance_import_and_adapter_repair_preflight_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S83_SCRIPT = ROOT / "scripts/build_stage12683_precise_link_semantic_repair_preflight_only.py"
S83_ROWS = ROOT / "runs/local/artifacts/stage12683_precise_link_semantic_repair_preflight_only/private/precise_link_semantic_repair_rows.jsonl"
S84_SUMMARY = ROOT / "runs/summaries/stage12684_precise_link_semantic_repair_independent_review_only.json"
S84_AUDIT = ROOT / "runs/local/artifacts/stage12684_precise_link_semantic_repair_independent_review_only/precise_link_semantic_repair_independent_review_audit.json"
S84_CONTRACT = ROOT / "runs/local/artifacts/stage12684_precise_link_semantic_repair_independent_review_only/contract.json"
S84_SCRIPT = ROOT / "scripts/build_stage12684_precise_link_semantic_repair_independent_review_only.py"

PINS = {
    S83_SCRIPT: "0e63bba99d5d5c66b7f4420da1fbd0efade62eb4dabfb37aa338766b2329c2ce",
    S83_ROWS: "3253d8af1543b1242eab6f223ee08fe35da88294663e859c1921bc8c446c9b8d",
    S84_SUMMARY: "2dda51f3ecf1e06ecf236741d51acb41886769ab461b526f132552e3ca8e2690",
    S84_AUDIT: "1220faf761fbf7dbb93fd75fe51173ac1531c024676397a92e6452afd6f6a45d",
    S84_CONTRACT: "2cf306f553e7860b05f596c91b2d9d8a04bc93f82f5ecc9a0ed018d3d80d4a9b",
    S84_SCRIPT: "b00fbf8005658a1b81d0aff0e83a3b7d6b97c779102308b6c30e1ec2a9745a31",
}
FALSE_FIELDS = (
    "implementation_ready", "stage12686_allowed", "training_allowed", "training_run_allowed",
    "training_admitted", "gpu_allocation_requested", "cuda2_training_allowed", "vm_runner_execution_allowed",
    "runtime_authorized", "replay_trustworthy", "level_3_materialized", "model_execution_authorized_next",
    "optimizer_step_authorized", "source_emission_authorized", "body_emission_authorized",
    "sealed_eval_admitted", "sealed_eval_eligible", "strict_eval_admitted", "strict_eval_eligible",
    "strict_eval_authorized", "sealed_eval_authorized", "loss_authorized", "gemma_execution_authorized_next",
)
FORBIDDEN = ("/data/", "/arxiv/", "PLACEHOLDER", "placeholder", "TODO", "TBD", "Answer:", "<fill", "\x00")

SPEC = importlib.util.spec_from_file_location("stage12683", S83_SCRIPT)
assert SPEC and SPEC.loader
s83 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(s83)


class Stage12685Error(RuntimeError):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable(value: Any) -> str:
    return sha(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii"))


def false_fields() -> dict[str, bool]:
    return {key: False for key in FALSE_FIELDS}


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12685Error("object_required:" + path.name)
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n"
    with path.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii") + b"\n")
        handle.flush()
        os.fsync(handle.fileno())


def assert_clean(value: Any, label: str) -> None:
    text = json.dumps(value, sort_keys=True, ensure_ascii=True)
    for marker in FORBIDDEN:
        if marker.lower() in text.lower():
            raise Stage12685Error(f"{label}_forbidden:{marker}")


def contains_forbidden(value: Any) -> bool:
    text = json.dumps(value, sort_keys=True, ensure_ascii=True)
    return any(marker.lower() in text.lower() for marker in FORBIDDEN)


def contains_key(value: Any, forbidden: set[str]) -> bool:
    if isinstance(value, Mapping):
        return bool(set(value) & forbidden) or any(contains_key(item, forbidden) for item in value.values())
    if isinstance(value, list):
        return any(contains_key(item, forbidden) for item in value)
    return False


def load_inputs() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    for path, expected in PINS.items():
        if sha(path.read_bytes()) != expected:
            raise Stage12685Error("pin_drift:" + path.name)
    summary84, audit84, contract84 = read_json(S84_SUMMARY), read_json(S84_AUDIT), read_json(S84_CONTRACT)
    for record in (summary84, audit84, contract84):
        if any(record.get(key) is not False for key in s83.FALSE_FIELDS if key in record):
            raise Stage12685Error("stage12684_authority_drift")
    if summary84.get("recommended_next_stage") != STAGE or audit84.get("next_required_action") != STAGE:
        raise Stage12685Error("stage12684_next_stage_drift")
    _summary82, _audit82, repos = s83.load_inputs()
    rows = read_jsonl(S83_ROWS)
    if len(rows) != 117892:
        raise Stage12685Error("stage12683_row_count_drift")
    return repos, rows


def occurrence_span(repo_root: Path, file: Mapping[str, Any], symbol: str, line: int, method: str) -> dict[str, Any] | None:
    path = repo_root / str(file["rel"])
    data = path.read_bytes()
    if sha(data) != file["digest"]:
        raise Stage12685Error("source_digest_race")
    text = data.decode("utf-8", errors="ignore")
    if method == "python_ast_definition":
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return None
        matches = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == symbol and node.lineno == line]
        if len(matches) != 1:
            return None
        node = matches[0]
        end_line = int(getattr(node, "end_lineno", node.lineno))
        end_col = int(getattr(node, "end_col_offset", node.col_offset + len(symbol)))
        segment = ast.get_source_segment(text, node) or ""
        return {"line": line, "column": int(node.col_offset), "end_line": end_line, "end_column": end_col, "snippet_sha256": sha(segment.encode("utf-8"))}
    pattern = re.compile(r"(?<![A-Za-z0-9_$])" + re.escape(symbol) + r"(?![A-Za-z0-9_$])")
    matches = list(pattern.finditer(text))
    if not matches:
        return None
    match = next((item for item in matches if text.count("\n", 0, item.start()) + 1 == line), matches[0])
    start_line = text.count("\n", 0, match.start()) + 1
    line_start = text.rfind("\n", 0, match.start()) + 1
    return {"line": start_line, "column": match.start() - line_start, "end_line": start_line, "end_column": match.end() - line_start, "occurrence_count": len(matches), "snippet_sha256": sha(match.group().encode("utf-8"))}


def structural_context(file: Mapping[str, Any], query: str, repo_root: Path) -> dict[str, Any]:
    others = [item for item in file["definitions"] if item["name"] != query]
    kinds = collections.Counter(str(item["kind"]) for item in others)
    line_count = (repo_root / str(file["rel"])).read_bytes().count(b"\n") + 1
    return {
        "role": file["role"],
        "language_family": file["language_family"],
        "suffix_token": file["suffix_token"],
        "path_depth_bucket": file["path_depth_bucket"],
        "line_count_bucket": s83.stage12678.count_bucket(line_count),
        "non_query_definition_count_bucket": s83.stage12678.count_bucket(len(others)),
        "non_query_definition_kind_counts": dict(sorted(kinds.items())),
        "neighbor_symbol_names": sorted({str(item["name"]) for item in others if not contains_forbidden(str(item["name"]))})[:12],
    }


def content_components(scanned: Mapping[str, Any], splits: Mapping[str, str]) -> dict[str, dict[str, Any]]:
    digest_repos: dict[str, list[str]] = collections.defaultdict(list)
    for repo_id, packet in scanned.items():
        for file in packet["files"]:
            digest_repos[file["digest"]].append(repo_id)
    union = s83.UnionFind(scanned)
    for repo_ids in digest_repos.values():
        for repo_id in repo_ids[1:]:
            union.union(repo_ids[0], repo_id)
    members: dict[str, list[str]] = collections.defaultdict(list)
    for repo_id in scanned:
        members[union.find(repo_id)].append(repo_id)
    result: dict[str, dict[str, Any]] = {}
    for repo_ids in members.values():
        component_digest = stable(sorted(repo_ids))
        for repo_id in repo_ids:
            result[repo_id] = {"component_digest": component_digest, "component_size": len(repo_ids), "split": splits[repo_id]}
    return result


@functools.lru_cache(maxsize=1)
def materialize() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    repos, upstream_rows = load_inputs()
    scanned, splits, scan_stats = s83.scan_repositories(repos)
    components = content_components(scanned, splits)
    repo_roots = {str(item["repo_id"]): Path(str(item["path"])) for item in repos}
    repo_contexts = {s83.stage12678.opaque("repo_context", repo_id): repo_id for repo_id in scanned}
    indexes: dict[str, dict[str, Any]] = {}
    for repo_id, packet in scanned.items():
        definitions: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = collections.defaultdict(list)
        contexts: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
        for file in packet["files"]:
            contexts[stable(s83.file_context(file))].append(file)
            for symbol in file["definitions"]:
                definitions[str(symbol["name"])].append((file, symbol))
        indexes[repo_id] = {"definitions": definitions, "contexts": contexts}
    pairs: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in upstream_rows:
        pairs[row["evidence"]["contrast_pair_digest"]].append(row)
    drafts: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    quarantines = collections.Counter()
    for pair_digest, pair in sorted(pairs.items()):
        objective = pair[0]["objective_family"]
        if objective == "python_absolute_import_symbol_resolution":
            quarantines["unproven_absolute_import_pairs"] += 1
            continue
        if len(pair) != 2:
            quarantines["malformed_pairs"] += 1
            continue
        repo_id = repo_contexts.get(str(pair[0]["input_state"].get("repository_context_id")))
        if not repo_id:
            quarantines["unmapped_repository_pairs"] += 1
            continue
        packet, root = scanned[repo_id], repo_roots[repo_id]
        symbol_name = str(pair[0]["input_state"]["symbol_name"])
        definitions = indexes[repo_id]["definitions"].get(symbol_name, [])
        source_files = {file["rel"] for file, _symbol in definitions}
        if len(source_files) != 1 or not definitions:
            quarantines["ambiguous_source_pairs"] += 1
            continue
        source_file, symbol = definitions[0]
        candidates: list[dict[str, Any]] = []
        failed = False
        for row in pair:
            context = row["input_state"]["candidate_file"]
            matches = [file for file in indexes[repo_id]["contexts"].get(stable(context), []) if stable([repo_id, symbol_name, file["rel"], row["expected_output"]["relationship"], symbol.get("line", 0)]) == row["evidence"]["occurrence_proof_digest"]]
            if len(matches) != 1:
                failed = True
                break
            candidates.append(matches[0])
        if failed or len({file["rel"] for file in candidates}) != 2:
            quarantines["ambiguous_candidate_pairs"] += 1
            continue
        if any(contains_forbidden(str(file["rel"])) for file in [source_file, *candidates]):
            quarantines["forbidden_private_path_pairs"] += 1
            continue
        method = str(pair[0]["evidence"]["extraction_method"])
        occurrence_file, occurrence_method, occurrence_line = source_file, str(symbol["method"]), int(symbol["line"])
        if objective == "doc_build_literal_symbol_association":
            ref_context = pair[0]["input_state"].get("reference_file")
            refs = [file for file in indexes[repo_id]["contexts"].get(stable(ref_context), []) if symbol_name in file["tokens"]]
            if len(refs) != 1:
                quarantines["ambiguous_reference_pairs"] += 1
                continue
            occurrence_file, occurrence_method, occurrence_line = refs[0], "literal_token_intersection", 0
            if contains_forbidden(str(occurrence_file["rel"])):
                quarantines["forbidden_private_path_pairs"] += 1
                continue
        span = occurrence_span(root, occurrence_file, symbol_name, occurrence_line, occurrence_method)
        if span is None:
            quarantines["unresolved_occurrence_pairs"] += 1
            continue
        ordering = sorted(range(2), key=lambda index: stable([repo_id, candidates[index]["rel"], candidates[index]["digest"]]))
        ordered_rows, ordered_files = [pair[i] for i in ordering], [candidates[i] for i in ordering]
        base = {key: value for key, value in ordered_rows[0]["input_state"].items() if key not in {"candidate_file", "repository_context_id"}}
        trainer = {
            "objective_family": objective,
            "training_stage": pair[0]["training_stage"],
            "split": pair[0]["split"],
            "input_state": {**base, "candidate_a": structural_context(ordered_files[0], symbol_name, root), "candidate_b": structural_context(ordered_files[1], symbol_name, root)},
            "expected_output": {"selected_candidate": "candidate_a" if ordered_files[0]["rel"] == source_file["rel"] else "candidate_b"},
        }
        if contains_forbidden(trainer):
            quarantines["forbidden_trainer_marker_pairs"] += 1
            continue
        provenance = {
            "trainer_row_sha256": stable(trainer),
            "repository_context_id": pair[0]["input_state"]["repository_context_id"],
            "split_evidence": components[repo_id],
            "source_occurrence": {"repository_relative_path": occurrence_file["rel"], "source_file_digest": occurrence_file["digest"], "extraction_method": occurrence_method, **span},
            "definition_occurrence": {"repository_relative_path": source_file["rel"], "source_file_digest": source_file["digest"], "line": int(symbol["line"]), "extraction_method": symbol["method"]},
            "candidate_endpoints": [{"slot": slot, "repository_relative_path": file["rel"], "candidate_file_digest": file["digest"]} for slot, file in zip(("candidate_a", "candidate_b"), ordered_files)],
            "upstream_contrast_pair_digest": pair_digest,
            "target_independent_ordering": True,
        }
        candidate_a = trainer["input_state"]["candidate_a"]
        candidate_b = trainer["input_state"]["candidate_b"]
        bucket_rank = {"zero": 0, "one": 1, "few": 2, "some": 3, "many": 4, "large": 5, "very_large": 6}
        definition_delta = bucket_rank[candidate_a["non_query_definition_count_bucket"]] - bucket_rank[candidate_b["non_query_definition_count_bucket"]]
        line_delta = bucket_rank[candidate_a["line_count_bucket"]] - bucket_rank[candidate_b["line_count_bucket"]]
        neighbor_delta = len(candidate_a["neighbor_symbol_names"]) - len(candidate_b["neighbor_symbol_names"])
        shortcut = stable({
            "objective": objective,
            "split": trainer["split"],
            "definition_relation": (definition_delta > 0) - (definition_delta < 0),
            "line_relation": (line_delta > 0) - (line_delta < 0),
            "neighbor_relation": (neighbor_delta > 0) - (neighbor_delta < 0),
            "same_depth": candidate_a["path_depth_bucket"] == candidate_b["path_depth_bucket"],
            "same_language": candidate_a["language_family"] == candidate_b["language_family"],
        })
        drafts.append((trainer, provenance, shortcut))

    semantic: dict[str, tuple[dict[str, Any], dict[str, Any], str]] = {}
    input_targets: dict[str, set[str]] = collections.defaultdict(set)
    for item in drafts:
        trainer = item[0]
        semantic.setdefault(stable(trainer), item)
        input_key = stable({key: trainer[key] for key in ("objective_family", "split", "input_state")})
        input_targets[input_key].add(stable(trainer["expected_output"]))
    conflicts = {key for key, targets in input_targets.items() if len(targets) > 1}
    deduplicated = []
    for item in semantic.values():
        trainer = item[0]
        input_key = stable({key: trainer[key] for key in ("objective_family", "split", "input_state")})
        if input_key not in conflicts:
            deduplicated.append(item)
    quarantines["semantic_duplicate_pairs"] = len(drafts) - len(semantic)
    quarantines["conflicting_input_groups"] = len(conflicts)
    drafts = deduplicated

    buckets: dict[str, dict[str, list[tuple[dict[str, Any], dict[str, Any], str]]]] = collections.defaultdict(lambda: collections.defaultdict(list))
    for item in drafts:
        buckets[item[2]][item[0]["expected_output"]["selected_candidate"]].append(item)
    kept: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    for labels in buckets.values():
        count = min(len(labels.get("candidate_a", [])), len(labels.get("candidate_b", [])))
        for label in ("candidate_a", "candidate_b"):
            kept.extend(sorted(labels[label], key=lambda item: item[1]["trainer_row_sha256"])[:count])
    kept.sort(key=lambda item: item[1]["trainer_row_sha256"])
    rows, provenance = [item[0] for item in kept], [item[1] for item in kept]
    quarantines["shortcut_balance_pairs"] = len(drafts) - len(kept)
    labels = collections.Counter(row["expected_output"]["selected_candidate"] for row in rows)
    shortcut_targets: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
    for trainer, _private, shortcut in kept:
        shortcut_targets[shortcut][trainer["expected_output"]["selected_candidate"]] += 1
    shortcut_accuracy = sum(max(counts.values()) for counts in shortcut_targets.values()) / len(kept) if kept else 1.0
    duplicates = len(rows) - len({stable(row) for row in rows})
    stats = {
        **scan_stats,
        "upstream_pairs": len(pairs),
        "eligible_pairs_before_shortcut_balance": len(drafts),
        "trainer_pairs_materialized": len(rows),
        "private_provenance_records": len(provenance),
        "label_counts": dict(sorted(labels.items())),
        "label_majority_accuracy": max(labels.values()) / len(rows) if rows else 1.0,
        "coarse_shortcut_majority_accuracy": shortcut_accuracy,
        "duplicate_trainer_rows": duplicates,
        "quarantines": dict(sorted(quarantines.items())),
    }
    return rows, provenance, stats


def build_packet() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    rows, provenance, stats = materialize()
    if len(rows) < 20_000 or len(rows) != len(provenance):
        raise Stage12685Error("insufficient_or_unbound_rows")
    if contains_key(rows, {"row_id", "occurrence_proof_digest"}) or stats["duplicate_trainer_rows"]:
        raise Stage12685Error(f"trainer_surface_hygiene_failure:duplicates={stats['duplicate_trainer_rows']}")
    if stats["label_majority_accuracy"] != 0.5 or stats["coarse_shortcut_majority_accuracy"] != 0.5:
        raise Stage12685Error("shortcut_balance_failure")
    decision = "PRECISE_LINK_PROVENANCE_AND_PAIR_ADAPTER_MATERIALIZED_INDEPENDENT_REVIEW_REQUIRED"
    next_stage = "stage12686_precise_link_provenance_and_adapter_independent_review_only"
    summary = {
        "record_type": "stage12685_public_summary_v1", "stage": STAGE, "decision": decision,
        "trainer_pairs_materialized": len(rows), "private_provenance_records": len(provenance),
        "unproven_absolute_import_pairs_quarantined": stats["quarantines"].get("unproven_absolute_import_pairs", 0),
        "label_majority_accuracy": stats["label_majority_accuracy"],
        "coarse_shortcut_majority_accuracy": stats["coarse_shortcut_majority_accuracy"],
        "training_source_rows_admitted": 0, "recommended_next_stage": next_stage, **false_fields(),
    }
    audit = {"record_type": "stage12685_private_audit_v1", "stage": STAGE, "decision": decision, "input_hashes": {path.name: digest for path, digest in PINS.items()}, "stats": stats, "trainer_rows_sha256": stable(rows), "provenance_sha256": stable(provenance), "next_required_action": next_stage, "training_source_rows_admitted": 0, **false_fields()}
    checks = [
        {"check_id": "upstream_physical_pins", "status": "passed", "count": len(PINS)},
        {"check_id": "private_exact_provenance", "status": "passed", "count": len(provenance)},
        {"check_id": "target_derived_metadata_removed", "status": "passed", "count": len(rows)},
        {"check_id": "target_independent_pair_ordering", "status": "passed", "count": len(rows)},
        {"check_id": "unproven_absolute_import_quarantine", "status": "passed", "count": summary["unproven_absolute_import_pairs_quarantined"]},
        {"check_id": "coarse_shortcut_balance", "status": "passed", "count": len(rows)},
        {"check_id": "independent_review", "status": "blocked", "count": 0},
        {"check_id": "training_authority", "status": "blocked", "count": 0},
    ]
    for label, value in (("rows", rows), ("provenance", provenance), ("summary", summary), ("audit", audit), ("checks", checks)):
        assert_clean(value, label)
    return summary, audit, checks, rows, provenance


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    summary, audit, checks, rows, provenance = build_packet()
    private = {"record_type": "stage12685_private_packet_v1", "stage": STAGE, "trainer_rows_sha256": stable(rows), "provenance_sha256": stable(provenance), "audit_sha256": stable(audit), **false_fields()}
    contract = {"record_type": "stage12685_contract_v1", "stage": STAGE, "decision": summary["decision"], "trainer_rows_sha256": stable(rows), "private_packet_sha256": stable(private), "recommended_next_stage": summary["recommended_next_stage"], **false_fields()}
    pointer = {"record_type": "stage12685_pointer_v1", "stage": STAGE, "summary_sha256": stable(summary), "contract_sha256": stable(contract), "private_packet_sha256": stable(private), **false_fields()}
    write_jsonl(out / "private/trainer_pairs.jsonl", rows)
    write_jsonl(out / "private/provenance_ledger.jsonl", provenance)
    write_jsonl(out / "private/checks.jsonl", checks)
    write_json(out / "audit.json", audit)
    write_json(out / "private/packet.json", private)
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True, ensure_ascii=True))
