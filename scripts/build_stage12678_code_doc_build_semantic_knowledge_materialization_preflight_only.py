#!/usr/bin/env python3
"""Materialize deeper source-derived repo/code knowledge without raw body emission."""
from __future__ import annotations

import ast
import collections
import hashlib
import json
import os
import re
import warnings
from pathlib import Path
from typing import Any, Iterable, Mapping

warnings.filterwarnings("ignore", category=SyntaxWarning)

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12678_code_doc_build_semantic_knowledge_materialization_preflight_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

S12676_SUMMARY = ROOT / "runs/summaries/stage12676_repo_knowledge_trainer_adapter_and_shortcut_baseline_preflight_only.json"
REPO_SUMMARIES = ROOT / "runs/local/artifacts/stage8600_arxiv_corpus_index/repository_summaries.jsonl"

EXPECTED_HASHES = {
    "stage12676_summary": "302935471616849c1a26ef22fa637b4d16e299f51a4e0dcea6efe45b98397d59",
    "repository_summaries": "4905c47a9e3feca39b0ed3abf51d07ee334e002c81292617ca90c4bad13a3489",
}

FALSE_FIELDS = (
    "implementation_ready", "stage12679_allowed", "training_allowed", "training_run_allowed",
    "training_admitted", "gpu_allocation_requested", "cuda2_training_allowed", "vm_runner_execution_allowed",
    "runtime_authorized", "replay_trustworthy", "level_3_materialized", "model_execution_authorized_next",
    "optimizer_step_authorized", "source_emission_authorized", "body_emission_authorized",
    "sealed_eval_admitted", "sealed_eval_eligible", "strict_eval_admitted", "strict_eval_eligible",
    "strict_eval_authorized", "sealed_eval_authorized", "loss_authorized", "compiler_execution_authorized",
)
UPSTREAM_FALSE_FIELDS = tuple(field for field in FALSE_FIELDS if field != "stage12679_allowed") + ("stage12677_allowed",)
FORBIDDEN_SUBSTRINGS = ("/data/", "/arxiv/", "PLACEHOLDER", "placeholder", "TODO", "TBD", "Answer:", "<fill", "\x00")

CODE_SUFFIXES = {".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".kt", ".scala", ".c", ".cc", ".cpp", ".h", ".hpp"}
DOC_SUFFIXES = {".md", ".rst", ".txt"}
CONFIG_SUFFIXES = {".toml", ".yaml", ".yml", ".json", ".ini", ".cfg", ".xml"}
SELECT_SUFFIXES = CODE_SUFFIXES | DOC_SUFFIXES | CONFIG_SUFFIXES
BUILD_NAMES = {"pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "package.json", "Cargo.toml", "go.mod", "pom.xml", "build.gradle", "Makefile", "CMakeLists.txt"}
MAINTENANCE_TERMS = ("bug", "fix", "test", "error", "config", "install", "api", "issue", "build", "release", "debug", "dependency")
TEST_FRAMEWORK_TERMS = ("pytest", "unittest", "jest", "mocha", "vitest", "cargo test", "go test", "junit")
MAX_FILES_PER_REPO = 120
MAX_BYTES_PER_FILE = 200_000
MAX_ROWS = 120_000


class Stage12678DeepKnowledgeError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def stable_int(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:12], 16)


def opaque(prefix: str, *parts: object) -> str:
    return f"{prefix}_{hashlib.sha256(':'.join(str(part) for part in parts).encode('utf-8')).hexdigest()[:16]}"


def split_for_id(repo_id: str) -> str:
    bucket = stable_int(repo_id) % 10
    if bucket < 6:
        return "train"
    if bucket < 8:
        return "eval"
    return "strict_eval"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12678DeepKnowledgeError("json_object_required:" + path.name)
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise Stage12678DeepKnowledgeError(f"jsonl_object_required:{line_number}")
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


def check_false(record: Mapping[str, Any], label: str, fields: tuple[str, ...]) -> None:
    for field in fields:
        if record.get(field) is not False:
            raise Stage12678DeepKnowledgeError(f"{label}_gate_drift:{field}")


def assert_no_forbidden(value: Any, label: str) -> None:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True) if not isinstance(value, str) else value
    for needle in FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise Stage12678DeepKnowledgeError(f"{label}_forbidden_substring:{needle}")


def count_bucket(value: int) -> str:
    if value <= 0:
        return "zero"
    if value == 1:
        return "one"
    if value <= 4:
        return "few"
    if value <= 19:
        return "some"
    if value <= 99:
        return "many"
    if value <= 999:
        return "large"
    return "very_large"


def language_for_suffix(suffix: str) -> str:
    return {
        ".py": "python", ".pyi": "python", ".js": "javascript", ".jsx": "javascript", ".ts": "typescript", ".tsx": "typescript",
        ".go": "go", ".rs": "rust", ".java": "java", ".kt": "kotlin", ".scala": "scala", ".c": "c_family",
        ".cc": "c_family", ".cpp": "c_family", ".h": "c_family", ".hpp": "c_family", ".md": "docs", ".rst": "docs", ".txt": "docs",
    }.get(suffix, "config" if suffix in CONFIG_SUFFIXES else "unknown")


def file_role(rel_path: str, name: str, suffix: str) -> str:
    lower = rel_path.lower()
    if name in BUILD_NAMES:
        return "build_config"
    if re.search(r"(^|/)(tests?|spec|__tests__)(/|$)|(^|/)(test_|.*_test\.|.*\.spec\.)", lower):
        return "test"
    if suffix in DOC_SUFFIXES or "readme" in lower or "/docs/" in lower or "/examples/" in lower:
        return "doc"
    if suffix in CONFIG_SUFFIXES:
        return "config"
    return "code"


def safe_read(path: Path) -> bytes:
    try:
        size = path.stat().st_size
        if size > MAX_BYTES_PER_FILE:
            return b""
        return path.read_bytes()
    except OSError:
        return b""


def selected_files(repo_root: Path) -> list[Path]:
    candidates: list[tuple[int, str, Path]] = []
    for root, dirs, files in os.walk(repo_root, followlinks=False):
        dirs[:] = [d for d in dirs if d not in {".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__", "target", "dist", "build"}]
        for name in files:
            path = Path(root) / name
            suffix = path.suffix.lower()
            if suffix not in SELECT_SUFFIXES and name not in BUILD_NAMES:
                continue
            try:
                rel = path.relative_to(repo_root).as_posix()
                size = path.stat().st_size
            except OSError:
                continue
            if size > MAX_BYTES_PER_FILE:
                continue
            role = file_role(rel, name, suffix)
            priority = {"test": 0, "build_config": 1, "code": 2, "doc": 3, "config": 4}.get(role, 5)
            candidates.append((priority, rel, path))
            if len(candidates) > MAX_FILES_PER_REPO * 4:
                break
        if len(candidates) > MAX_FILES_PER_REPO * 4:
            break
    return [item[2] for item in sorted(candidates, key=lambda item: (item[0], item[1]))[:MAX_FILES_PER_REPO]]


def python_facts(text: str) -> tuple[list[str], list[tuple[str, str]], dict[str, int]]:
    imports: set[str] = set()
    symbols: list[tuple[str, str]] = []
    metrics = {"functions": 0, "classes": 0, "async_functions": 0, "asserts": 0}
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return [], [], metrics
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.FunctionDef):
            metrics["functions"] += 1
            symbols.append(("function", node.name))
        elif isinstance(node, ast.AsyncFunctionDef):
            metrics["async_functions"] += 1
            symbols.append(("async_function", node.name))
        elif isinstance(node, ast.ClassDef):
            metrics["classes"] += 1
            symbols.append(("class", node.name))
        elif isinstance(node, ast.Assert):
            metrics["asserts"] += 1
    return sorted(imports)[:30], symbols[:40], metrics


def regex_symbols(text: str, suffix: str) -> list[tuple[str, str]]:
    patterns = []
    if suffix in {".js", ".jsx", ".ts", ".tsx"}:
        patterns = [("function", r"\bfunction\s+([A-Za-z_$][\w$]*)"), ("class", r"\bclass\s+([A-Za-z_$][\w$]*)"), ("const", r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)")]
    elif suffix == ".go":
        patterns = [("function", r"\bfunc\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)")]
    elif suffix == ".rs":
        patterns = [("function", r"\bfn\s+([A-Za-z_]\w*)"), ("struct", r"\bstruct\s+([A-Za-z_]\w*)"), ("enum", r"\benum\s+([A-Za-z_]\w*)")]
    elif suffix in {".java", ".kt", ".scala"}:
        patterns = [("class", r"\bclass\s+([A-Za-z_]\w*)"), ("interface", r"\binterface\s+([A-Za-z_]\w*)")]
    out = []
    for kind, pattern in patterns:
        for match in re.finditer(pattern, text):
            out.append((kind, match.group(1)))
            if len(out) >= 40:
                return out
    return out


def maintenance_counts(text: str) -> dict[str, int]:
    lower = text.lower()
    return {term: len(re.findall(r"\b" + re.escape(term) + r"\b", lower)) for term in MAINTENANCE_TERMS}


def framework_hits(text: str) -> list[str]:
    lower = text.lower()
    return [term.replace(" ", "_") for term in TEST_FRAMEWORK_TERMS if term in lower]


def load_inputs() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    for label, path in (("stage12676_summary", S12676_SUMMARY), ("repository_summaries", REPO_SUMMARIES)):
        if sha256_bytes(path.read_bytes()) != EXPECTED_HASHES[label]:
            raise Stage12678DeepKnowledgeError("pin_drift:" + label)
    summary76 = read_json(S12676_SUMMARY)
    check_false(summary76, "stage12676_summary", UPSTREAM_FALSE_FIELDS)
    repos = read_jsonl(REPO_SUMMARIES)
    if len(repos) != 500:
        raise Stage12678DeepKnowledgeError("repo_count_drift")
    return summary76, repos


def make_row(rows: list[dict[str, Any]], repo: Mapping[str, Any], objective: str, input_state: Mapping[str, Any], target: Mapping[str, Any], source_digest: str) -> None:
    if len(rows) >= MAX_ROWS:
        return
    repo_id = str(repo["repo_id"])
    row = {
        "row_id": f"stage12678_deep_repo_code_knowledge_{len(rows):06d}",
        "split": split_for_id(repo_id),
        "objective_family": objective,
        "training_stage": "repo_and_code_knowledge.deep_semantic",
        "input_state": dict(input_state),
        "expected_output": dict(target),
        "evidence": {
            "source_stage": STAGE,
            "repo_digest": opaque("repo", repo_id),
            "source_file_digest": source_digest,
            "raw_source_body_included": False,
            "absolute_path_included": False,
        },
        "authority": {
            "training_allowed": False,
            "training_run_allowed": False,
            "optimizer_step_authorized": False,
            "runtime_authorized": False,
            "source_emission_authorized": False,
            "body_emission_authorized": False,
            "loss_authorized": False,
        },
        "quality": {"source_body_read_for_extraction_only": True, "requires_independent_review_before_training": True},
    }
    assert_no_forbidden(row, "deep_knowledge_row")
    rows.append(row)


def materialize_rows(repos: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    scanned_files = 0
    empty_files = 0
    per_repo_files: dict[str, int] = {}
    for repo in sorted(repos, key=lambda item: (-int(item.get("maintainer_usefulness_score", 0)), str(item["repo_id"]))):
        repo_root = Path(str(repo.get("path", "")))
        if not repo_root.exists() or not repo_root.is_dir():
            continue
        files = selected_files(repo_root)
        per_repo_files[str(repo["repo_id"])] = len(files)
        code_file_ids: list[str] = []
        test_file_ids: list[str] = []
        doc_file_ids: list[str] = []
        build_file_ids: list[str] = []
        for path in files:
            rel = path.relative_to(repo_root).as_posix()
            data = safe_read(path)
            if not data:
                empty_files += 1
                continue
            scanned_files += 1
            digest = sha256_bytes(data)
            text = data.decode("utf-8", errors="ignore")
            suffix = path.suffix.lower()
            name = path.name
            role = file_role(rel, name, suffix)
            file_id = opaque("file", repo["repo_id"], rel)
            language = language_for_suffix(suffix)
            base_input = {"opaque_repo_id": opaque("repo", repo["repo_id"]), "opaque_file_id": file_id, "file_role": role, "language_family": language, "suffix_token": suffix or "<none>", "size_bucket": count_bucket(len(data))}
            make_row(rows, repo, "deep_file_role_language_fact", base_input, {"file_role": role, "language_family": language, "is_test": role == "test", "is_doc": role == "doc", "is_build_config": role == "build_config"}, digest)
            if role == "code":
                code_file_ids.append(file_id)
            elif role == "test":
                test_file_ids.append(file_id)
            elif role == "doc":
                doc_file_ids.append(file_id)
            elif role == "build_config":
                build_file_ids.append(file_id)
            if suffix in {".py", ".pyi"}:
                imports, symbols, metrics = python_facts(text)
                make_row(rows, repo, "python_syntax_summary_fact", base_input, {"function_count_bucket": count_bucket(metrics["functions"]), "class_count_bucket": count_bucket(metrics["classes"]), "async_function_count_bucket": count_bucket(metrics["async_functions"]), "assert_count_bucket": count_bucket(metrics["asserts"])}, digest)
                for ordinal, module in enumerate(imports):
                    make_row(rows, repo, "python_import_api_fact", {**base_input, "import_ordinal_bucket": count_bucket(ordinal + 1)}, {"import_module": module, "import_module_digest": opaque("module", module)}, digest)
                for ordinal, (kind, symbol) in enumerate(symbols):
                    make_row(rows, repo, "python_symbol_definition_fact", {**base_input, "symbol_ordinal_bucket": count_bucket(ordinal + 1)}, {"symbol_kind": kind, "symbol_name_digest": opaque("symbol", symbol), "name_length_bucket": count_bucket(len(symbol))}, digest)
            elif suffix in CODE_SUFFIXES:
                symbols = regex_symbols(text, suffix)
                make_row(rows, repo, "nonpython_syntax_summary_fact", base_input, {"symbol_count_bucket": count_bucket(len(symbols)), "language_family": language}, digest)
                for ordinal, (kind, symbol) in enumerate(symbols[:25]):
                    make_row(rows, repo, "nonpython_symbol_definition_fact", {**base_input, "symbol_ordinal_bucket": count_bucket(ordinal + 1)}, {"symbol_kind": kind, "symbol_name_digest": opaque("symbol", symbol), "name_length_bucket": count_bucket(len(symbol))}, digest)
            if role == "test":
                hits = framework_hits(text)
                make_row(rows, repo, "test_framework_signal_fact", base_input, {"frameworks_detected": sorted(hits), "framework_count_bucket": count_bucket(len(hits)), "assert_term_bucket": count_bucket(text.lower().count("assert"))}, digest)
            if role in {"doc", "build_config", "test"}:
                counts = maintenance_counts(text)
                for term, value in counts.items():
                    if value:
                        make_row(rows, repo, "maintenance_vocabulary_fact", {**base_input, "maintenance_term": term}, {"term_count_bucket": count_bucket(value), "term_present": True}, digest)
        for ordinal, test_id in enumerate(test_file_ids[:20]):
            make_row(rows, repo, "test_file_association_fact", {"opaque_repo_id": opaque("repo", repo["repo_id"]), "opaque_test_file_id": test_id, "candidate_code_file_count_bucket": count_bucket(len(code_file_ids))}, {"association_type": "repo_level_test_to_code_surface", "test_ordinal_bucket": count_bucket(ordinal + 1)}, opaque("assoc", repo["repo_id"], test_id))
        for ordinal, doc_id in enumerate(doc_file_ids[:20]):
            make_row(rows, repo, "doc_code_association_fact", {"opaque_repo_id": opaque("repo", repo["repo_id"]), "opaque_doc_file_id": doc_id, "candidate_code_file_count_bucket": count_bucket(len(code_file_ids))}, {"association_type": "repo_level_doc_to_code_surface", "doc_ordinal_bucket": count_bucket(ordinal + 1)}, opaque("assoc", repo["repo_id"], doc_id))
        for ordinal, build_id in enumerate(build_file_ids[:20]):
            make_row(rows, repo, "build_code_association_fact", {"opaque_repo_id": opaque("repo", repo["repo_id"]), "opaque_build_file_id": build_id, "candidate_code_file_count_bucket": count_bucket(len(code_file_ids))}, {"association_type": "repo_level_build_to_code_surface", "build_ordinal_bucket": count_bucket(ordinal + 1)}, opaque("assoc", repo["repo_id"], build_id))
    stats = {"repositories_seen": len(repos), "repositories_with_selected_files": len(per_repo_files), "source_files_scanned": scanned_files, "empty_or_skipped_files": empty_files, "max_files_per_repo": MAX_FILES_PER_REPO}
    if len(rows) < 50000:
        raise Stage12678DeepKnowledgeError("deep_knowledge_rows_below_expected_scale")
    return rows, stats


def build_packet() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    _summary76, repos = load_inputs()
    rows, stats = materialize_rows(repos)
    objective_counts = dict(sorted(collections.Counter(row["objective_family"] for row in rows).items()))
    split_counts = dict(sorted(collections.Counter(row["split"] for row in rows).items()))
    audit = {
        "record_type": "stage12678_deep_repo_code_knowledge_materialization_audit_v1",
        "stage": STAGE,
        "decision": "DEEP_REPO_CODE_KNOWLEDGE_MATERIALIZED_REVIEW_REQUIRED",
        "materialized_rows": len(rows),
        "objective_counts": objective_counts,
        "split_counts": split_counts,
        "source_scan_stats": stats,
        "raw_source_body_rows": 0,
        "absolute_path_rows": 0,
        "training_source_rows_admitted": 0,
        "next_required_action": "stage12679_deep_repo_code_knowledge_independent_review_only",
        **false_fields(),
    }
    summary = {
        "record_type": "stage12678_public_deep_repo_code_knowledge_materialization_summary_v1",
        "stage": STAGE,
        "decision": audit["decision"],
        "materialized_rows": len(rows),
        "objective_family_count": len(objective_counts),
        "source_files_scanned": stats["source_files_scanned"],
        "split_counts": split_counts,
        "training_source_rows_admitted": 0,
        "recommended_next_stage": audit["next_required_action"],
        **false_fields(),
    }
    checks = [
        {"check_id": "stage12676_and_repo_pins", "status": "pass"},
        {"check_id": "source_body_read_no_body_emit", "status": "pass"},
        {"check_id": "deep_row_scale", "status": "pass"},
        {"check_id": "raw_path_absence", "status": "pass"},
        {"check_id": "training_authority", "status": "blocked"},
        {"check_id": "independent_review", "status": "blocked"},
    ]
    for label, record in (("summary", summary), ("audit", audit), ("checks", checks)):
        assert_no_forbidden(record, label)
    return summary, audit, checks, rows


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    summary, audit, checks, rows = build_packet()
    private = {"record_type": "stage12678_private_deep_repo_code_knowledge_packet_v1", "stage": STAGE, "input_hashes": EXPECTED_HASHES, "rows_sha256": stable_hash(rows), "audit_sha256": stable_hash(audit), "checks_sha256": stable_hash(checks), **false_fields()}
    contract = {"record_type": "stage12678_deep_repo_code_knowledge_contract_v1", "stage": STAGE, "decision": summary["decision"], "materialized_rows": summary["materialized_rows"], "rows_sha256": stable_hash(rows), "private_packet_sha256": stable_hash(private), "audit_sha256": stable_hash(audit), "recommended_next_stage": summary["recommended_next_stage"], **false_fields()}
    pointer = {"record_type": "stage12678_digest_pointer_v1", "stage": STAGE, "summary_sha256": stable_hash(summary), "contract_sha256": stable_hash(contract), "private_packet_sha256": stable_hash(private), "audit_sha256": stable_hash(audit), "rows_sha256": stable_hash(rows), **false_fields()}
    for label, record in (("private", private), ("contract", contract), ("pointer", pointer)):
        assert_no_forbidden(record, label)
    write_jsonl(out / "private/deep_repo_code_knowledge_rows.jsonl", rows)
    write_json(out / "summary.json", summary)
    write_json(out / "deep_repo_code_knowledge_materialization_audit.json", audit)
    write_jsonl(out / "private/deep_repo_code_knowledge_checks.jsonl", checks)
    write_json(out / "private/deep_repo_code_knowledge_packet.json", private)
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(summary_path, summary)
    fsync_dir(out)
    fsync_dir(out / "private")
    fsync_dir(summary_path.parent)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True, ensure_ascii=True))
