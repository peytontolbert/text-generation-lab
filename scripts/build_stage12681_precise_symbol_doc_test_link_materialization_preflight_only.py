#!/usr/bin/env python3
"""Materialize precise symbol/doc/test/build link rows without raw source emission."""
from __future__ import annotations

import collections
import hashlib
import importlib.util
import json
import os
import re
import warnings
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12681_precise_symbol_doc_test_link_materialization_preflight_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

S12680_SUMMARY = ROOT / "runs/summaries/stage12680_deep_repo_code_knowledge_adapter_and_shortcut_preflight_only.json"
S12680_AUDIT = ROOT / "runs/local/artifacts/stage12680_deep_repo_code_knowledge_adapter_and_shortcut_preflight_only/deep_repo_code_knowledge_adapter_audit.json"
S12680_ADAPTER = ROOT / "runs/local/artifacts/stage12680_deep_repo_code_knowledge_adapter_and_shortcut_preflight_only/private/deep_repo_code_knowledge_adapter_candidates.jsonl"
REPO_SUMMARIES = ROOT / "runs/local/artifacts/stage8600_arxiv_corpus_index/repository_summaries.jsonl"
STAGE12678_SCRIPT = ROOT / "scripts/build_stage12678_code_doc_build_semantic_knowledge_materialization_preflight_only.py"

EXPECTED_HASHES = {
    "stage12680_summary": "600c7d6f859fd03b000a31a2ce6441dbbecae6c5dec185590bda20b93d51c784",
    "stage12680_audit": "e26179117b7e28fe4b7d491df89c9d4a77e48bcedfd13138d0a284900b9fe89f",
    "stage12680_adapter": "7808edc1286fa46fa4cdb709b4c4e779ba8b91fec705ea62c5b0331f49d9798c",
    "repository_summaries": "4905c47a9e3feca39b0ed3abf51d07ee334e002c81292617ca90c4bad13a3489",
}

FALSE_FIELDS = (
    "implementation_ready", "stage12682_allowed", "training_allowed", "training_run_allowed",
    "training_admitted", "gpu_allocation_requested", "cuda2_training_allowed", "vm_runner_execution_allowed",
    "runtime_authorized", "replay_trustworthy", "level_3_materialized", "model_execution_authorized_next",
    "optimizer_step_authorized", "source_emission_authorized", "body_emission_authorized",
    "sealed_eval_admitted", "sealed_eval_eligible", "strict_eval_admitted", "strict_eval_eligible",
    "strict_eval_authorized", "sealed_eval_authorized", "loss_authorized", "compiler_execution_authorized",
)
UPSTREAM_FALSE_FIELDS = tuple(field for field in FALSE_FIELDS if field != "stage12682_allowed") + ("stage12681_allowed",)
ROW_AUTHORITY_FALSE_FIELDS = (
    "training_allowed", "training_run_allowed", "optimizer_step_authorized", "runtime_authorized",
    "source_emission_authorized", "body_emission_authorized", "model_execution_authorized", "loss_authorized",
)
FORBIDDEN_SUBSTRINGS = ("/data/", "/arxiv/", "PLACEHOLDER", "placeholder", "TODO", "TBD", "Answer:", "<fill", "\x00")
MAX_ROWS = 80_000
MAX_SYMBOLS_PER_REPO = 500
MAX_LINK_ROWS_PER_FILE = 40
TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")

warnings.filterwarnings("ignore", category=SyntaxWarning)

SPEC = importlib.util.spec_from_file_location("stage12678_helpers", STAGE12678_SCRIPT)
assert SPEC and SPEC.loader
stage12678 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage12678)


class Stage12681LinkError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12681LinkError("json_object_required:" + path.name)
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise Stage12681LinkError(f"jsonl_object_required:{line_number}")
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
            stream.write(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii") + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def fsync_dir(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def false_fields() -> dict[str, bool]:
    return {field: False for field in FALSE_FIELDS}


def row_authority() -> dict[str, bool]:
    return {field: False for field in ROW_AUTHORITY_FALSE_FIELDS}


def check_false(record: Mapping[str, Any], label: str, fields: tuple[str, ...]) -> None:
    for field in fields:
        if record.get(field) is not False:
            raise Stage12681LinkError(f"{label}_gate_drift:{field}")


def assert_no_forbidden(value: Any, label: str) -> None:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True) if not isinstance(value, str) else value
    for needle in FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise Stage12681LinkError(f"{label}_forbidden_substring:{needle}")


def load_inputs() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    pins = {
        "stage12680_summary": S12680_SUMMARY,
        "stage12680_audit": S12680_AUDIT,
        "stage12680_adapter": S12680_ADAPTER,
        "repository_summaries": REPO_SUMMARIES,
    }
    for label, path in pins.items():
        if sha256_bytes(path.read_bytes()) != EXPECTED_HASHES[label]:
            raise Stage12681LinkError("pin_drift:" + label)
    summary80 = read_json(S12680_SUMMARY)
    audit80 = read_json(S12680_AUDIT)
    check_false(summary80, "stage12680_summary", UPSTREAM_FALSE_FIELDS)
    check_false(audit80, "stage12680_audit", UPSTREAM_FALSE_FIELDS)
    if summary80.get("next_required_action") != STAGE:
        raise Stage12681LinkError("stage12680_next_action_drift")
    repos = read_jsonl(REPO_SUMMARIES)
    if len(repos) != 500:
        raise Stage12681LinkError("repo_count_drift")
    return summary80, audit80, repos


def count_bucket(value: int) -> str:
    return stage12678.count_bucket(value)


def split_for_id(repo_id: str) -> str:
    return stage12678.split_for_id(repo_id)


def opaque(prefix: str, *parts: object) -> str:
    return stage12678.opaque(prefix, *parts)


def tokens(text: str) -> set[str]:
    return set(TOKEN_RE.findall(text))


def make_row(rows: list[dict[str, Any]], repo: Mapping[str, Any], objective: str, input_state: Mapping[str, Any], target: Mapping[str, Any], evidence: Mapping[str, Any]) -> None:
    if len(rows) >= MAX_ROWS:
        return
    row = {
        "row_id": f"stage12681_precise_symbol_doc_test_link_{len(rows):06d}",
        "split": split_for_id(str(repo["repo_id"])),
        "objective_family": objective,
        "training_stage": "repo_and_code_knowledge.precise_symbol_doc_test_links",
        "input_state": dict(input_state),
        "expected_output": dict(target),
        "evidence": {
            **dict(evidence),
            "source_stage": STAGE,
            "repo_digest": opaque("repo", repo["repo_id"]),
            "raw_source_body_included": False,
            "absolute_path_included": False,
        },
        "authority": row_authority(),
        "quality": {
            "source_body_read_for_extraction_only": True,
            "requires_independent_review_before_training": True,
            "precise_link_derived_from_literal_symbol_reference": True,
        },
    }
    assert_no_forbidden(row, "stage12681_row")
    rows.append(row)


def materialize_rows(repos: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    scanned_files = 0
    repos_with_symbols = 0
    linkable_files = 0
    for repo in sorted(repos, key=lambda item: (-int(item.get("maintainer_usefulness_score", 0)), str(item["repo_id"]))):
        repo_root = Path(str(repo.get("path", "")))
        if not repo_root.exists() or not repo_root.is_dir():
            continue
        symbols: list[dict[str, Any]] = []
        reference_files: list[dict[str, Any]] = []
        for path in stage12678.selected_files(repo_root):
            rel = path.relative_to(repo_root).as_posix()
            data = stage12678.safe_read(path)
            if not data:
                continue
            scanned_files += 1
            text = data.decode("utf-8", errors="ignore")
            suffix = path.suffix.lower()
            role = stage12678.file_role(rel, path.name, suffix)
            file_id = opaque("file", repo["repo_id"], rel)
            file_digest = sha256_bytes(data)
            language = stage12678.language_for_suffix(suffix)
            if role == "code" and suffix in stage12678.CODE_SUFFIXES:
                extracted = stage12678.python_facts(text)[1] if suffix in {".py", ".pyi"} else stage12678.regex_symbols(text, suffix)
                for kind, name in extracted:
                    if len(name) < 4 or len(symbols) >= MAX_SYMBOLS_PER_REPO:
                        continue
                    symbols.append({
                        "name": name,
                        "symbol_digest": opaque("symbol", name),
                        "kind": kind,
                        "file_id": file_id,
                        "file_digest": file_digest,
                        "language_family": language,
                        "suffix_token": suffix or "<none>",
                    })
            elif role in {"test", "doc", "build_config"}:
                reference_files.append({
                    "role": role,
                    "file_id": file_id,
                    "file_digest": file_digest,
                    "language_family": language,
                    "suffix_token": suffix or "<none>",
                    "tokens": tokens(text),
                })
        if not symbols:
            continue
        repos_with_symbols += 1
        symbol_by_name: dict[str, dict[str, Any]] = {}
        for symbol in symbols:
            symbol_by_name.setdefault(symbol["name"], symbol)
        for ordinal, symbol in enumerate(symbols[:200]):
            make_row(
                rows,
                repo,
                "precise_symbol_definition_file_link",
                {
                    "opaque_repo_id": opaque("repo", repo["repo_id"]),
                    "symbol_name_digest": symbol["symbol_digest"],
                    "symbol_kind": symbol["kind"],
                    "language_family": symbol["language_family"],
                    "symbol_ordinal_bucket": count_bucket(ordinal + 1),
                },
                {
                    "defining_file_id": symbol["file_id"],
                    "defining_file_digest": symbol["file_digest"],
                    "definition_link_type": "symbol_to_defining_source_file",
                },
                {"defining_file_digest": symbol["file_digest"]},
            )
        for ref in reference_files:
            matched = sorted(name for name in ref["tokens"].intersection(symbol_by_name))[:MAX_LINK_ROWS_PER_FILE]
            if not matched:
                continue
            linkable_files += 1
            objective = {
                "test": "precise_test_symbol_reference_link",
                "doc": "precise_doc_symbol_reference_link",
                "build_config": "precise_build_symbol_reference_link",
            }[ref["role"]]
            for name in matched:
                symbol = symbol_by_name[name]
                make_row(
                    rows,
                    repo,
                    objective,
                    {
                        "opaque_repo_id": opaque("repo", repo["repo_id"]),
                        "reference_file_id": ref["file_id"],
                        "reference_file_role": ref["role"],
                        "reference_language_family": ref["language_family"],
                        "symbol_name_digest": symbol["symbol_digest"],
                        "symbol_kind": symbol["kind"],
                        "candidate_symbol_count_bucket": count_bucket(len(symbols)),
                    },
                    {
                        "linked_code_file_id": symbol["file_id"],
                        "linked_code_file_digest": symbol["file_digest"],
                        "reference_link_type": f"{ref['role']}_literal_symbol_reference_to_code_file",
                    },
                    {"reference_file_digest": ref["file_digest"], "linked_code_file_digest": symbol["file_digest"]},
                )
    stats = {
        "repositories_seen": len(repos),
        "repositories_with_symbols": repos_with_symbols,
        "source_files_scanned": scanned_files,
        "linkable_reference_files": linkable_files,
        "max_rows": MAX_ROWS,
        "max_symbols_per_repo": MAX_SYMBOLS_PER_REPO,
        "max_link_rows_per_file": MAX_LINK_ROWS_PER_FILE,
    }
    if len(rows) < 40_000:
        raise Stage12681LinkError("precise_link_rows_below_expected_scale")
    return rows, stats


def build_packet() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    summary80, _audit80, repos = load_inputs()
    rows, stats = materialize_rows(repos)
    objective_counts = dict(sorted(collections.Counter(row["objective_family"] for row in rows).items()))
    split_counts = dict(sorted(collections.Counter(row["split"] for row in rows).items()))
    audit = {
        "record_type": "stage12681_precise_symbol_doc_test_link_materialization_audit_v1",
        "stage": STAGE,
        "decision": "PRECISE_SYMBOL_DOC_TEST_LINKS_MATERIALIZED_REVIEW_REQUIRED",
        "materialized_rows": len(rows),
        "objective_counts": objective_counts,
        "split_counts": split_counts,
        "source_scan_stats": stats,
        "upstream_stage12680_adapter_candidate_rows": summary80["adapter_candidate_rows"],
        "raw_source_body_rows": 0,
        "absolute_path_rows": 0,
        "training_source_rows_admitted": 0,
        "next_required_action": "stage12682_precise_link_independent_review_only",
        **false_fields(),
    }
    summary = {
        "record_type": "stage12681_public_precise_symbol_doc_test_link_summary_v1",
        "stage": STAGE,
        "decision": audit["decision"],
        "materialized_rows": len(rows),
        "objective_family_count": len(objective_counts),
        "split_counts": split_counts,
        "source_files_scanned": stats["source_files_scanned"],
        "linkable_reference_files": stats["linkable_reference_files"],
        "training_source_rows_admitted": 0,
        "recommended_next_stage": audit["next_required_action"],
        **false_fields(),
    }
    checks = [
        {"check_id": "stage12680_and_repo_pins", "status": "passed", "count": len(EXPECTED_HASHES)},
        {"check_id": "literal_symbol_link_materialization", "status": "passed", "count": len(rows)},
        {"check_id": "raw_source_body_absence", "status": "passed", "count": 0},
        {"check_id": "absolute_path_absence", "status": "passed", "count": 0},
        {"check_id": "independent_review", "status": "blocked", "count": 0},
        {"check_id": "training_authority", "status": "blocked", "count": 0},
    ]
    for label, record in (("summary", summary), ("audit", audit), ("checks", checks)):
        assert_no_forbidden(record, label)
    return summary, audit, checks, rows


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    summary, audit, checks, rows = build_packet()
    private = {"record_type": "stage12681_private_precise_symbol_doc_test_link_packet_v1", "stage": STAGE, "input_hashes": EXPECTED_HASHES, "rows_sha256": stable_hash(rows), "audit_sha256": stable_hash(audit), "checks_sha256": stable_hash(checks), **false_fields()}
    contract = {"record_type": "stage12681_precise_symbol_doc_test_link_contract_v1", "stage": STAGE, "decision": summary["decision"], "materialized_rows": summary["materialized_rows"], "rows_sha256": stable_hash(rows), "private_packet_sha256": stable_hash(private), "audit_sha256": stable_hash(audit), "recommended_next_stage": summary["recommended_next_stage"], **false_fields()}
    pointer = {"record_type": "stage12681_digest_pointer_v1", "stage": STAGE, "summary_sha256": stable_hash(summary), "contract_sha256": stable_hash(contract), "private_packet_sha256": stable_hash(private), "audit_sha256": stable_hash(audit), "rows_sha256": stable_hash(rows), **false_fields()}
    for label, record in (("private", private), ("contract", contract), ("pointer", pointer)):
        assert_no_forbidden(record, label)
    write_jsonl(out / "private/precise_symbol_doc_test_link_rows.jsonl", rows)
    write_json(out / "summary.json", summary)
    write_json(out / "precise_symbol_doc_test_link_materialization_audit.json", audit)
    write_jsonl(out / "private/precise_symbol_doc_test_link_checks.jsonl", checks)
    write_json(out / "private/precise_symbol_doc_test_link_packet.json", private)
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(summary_path, summary)
    fsync_dir(out)
    fsync_dir(out / "private")
    fsync_dir(summary_path.parent)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True, ensure_ascii=True))
