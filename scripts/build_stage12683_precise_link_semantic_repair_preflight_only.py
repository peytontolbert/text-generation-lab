#!/usr/bin/env python3
"""Repair Stage12681 links into grounded, non-leaky relation examples."""
from __future__ import annotations

import ast
import collections
import hashlib
import importlib.util
import json
import os
import re
import warnings
from pathlib import Path
from typing import Any, Iterable, Mapping

warnings.filterwarnings("ignore", category=SyntaxWarning)

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12683_precise_link_semantic_repair_preflight_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

S12682_SUMMARY = ROOT / "runs/summaries/stage12682_precise_link_independent_review_only.json"
S12682_AUDIT = ROOT / "runs/local/artifacts/stage12682_precise_link_independent_review_only/precise_link_independent_review_audit.json"
S12682_CONTRACT = ROOT / "runs/local/artifacts/stage12682_precise_link_independent_review_only/contract.json"
REPO_SUMMARIES = ROOT / "runs/local/artifacts/stage8600_arxiv_corpus_index/repository_summaries.jsonl"
STAGE12678_SCRIPT = ROOT / "scripts/build_stage12678_code_doc_build_semantic_knowledge_materialization_preflight_only.py"

EXPECTED_HASHES = {
    "stage12682_summary": "be6b6c61496b870e57160134bf78b22551e33854dbf5b71f59025555e39c4cf0",
    "stage12682_audit": "90ec75ae4e32aca519a643fad920afe820da2557d10b5d3f77e0351922082761",
    "stage12682_contract": "a0ad5454c0791dcee509f5cf44926184d9f5098a84e120a26cebfceeb2fe1eb5",
    "repository_summaries": "4905c47a9e3feca39b0ed3abf51d07ee334e002c81292617ca90c4bad13a3489",
}

FALSE_FIELDS = (
    "implementation_ready", "stage12684_allowed", "training_allowed", "training_run_allowed",
    "training_admitted", "gpu_allocation_requested", "cuda2_training_allowed", "vm_runner_execution_allowed",
    "runtime_authorized", "replay_trustworthy", "level_3_materialized", "model_execution_authorized_next",
    "optimizer_step_authorized", "source_emission_authorized", "body_emission_authorized",
    "sealed_eval_admitted", "sealed_eval_eligible", "strict_eval_admitted", "strict_eval_eligible",
    "strict_eval_authorized", "sealed_eval_authorized", "loss_authorized", "compiler_execution_authorized",
    "gemma_execution_authorized_next",
)
UPSTREAM_FALSE_FIELDS = tuple(field for field in FALSE_FIELDS if field not in {"stage12684_allowed", "gemma_execution_authorized_next"}) + ("stage12683_allowed",)
ROW_AUTHORITY_FALSE_FIELDS = (
    "training_allowed", "training_run_allowed", "optimizer_step_authorized", "runtime_authorized",
    "source_emission_authorized", "body_emission_authorized", "model_execution_authorized", "loss_authorized",
)
FORBIDDEN_SUBSTRINGS = ("/data/", "/arxiv/", "PLACEHOLDER", "placeholder", "TODO", "TBD", "Answer:", "<fill", "\x00")
TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{3,}")
MAX_SYMBOLS_PER_REPO = 500
MAX_LEXICAL_LINKS_PER_FILE = 20
MAX_ROWS = 120_000
MAX_PAIRS_BY_OBJECTIVE_SPLIT = {
    "python_ast_symbol_definition_relation": {"train": 24_000, "eval": 8_000, "strict_eval": 8_000},
    "language_pattern_symbol_definition_relation": {"train": 12_000, "eval": 4_000, "strict_eval": 4_000},
    "python_absolute_import_symbol_resolution": {"train": 10_000, "eval": 10_000, "strict_eval": 10_000},
    "doc_build_literal_symbol_association": {"train": 10_000, "eval": 10_000, "strict_eval": 10_000},
}

SPEC = importlib.util.spec_from_file_location("stage12678_helpers", STAGE12678_SCRIPT)
assert SPEC and SPEC.loader
stage12678 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage12678)


class Stage12683RepairError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def stable_int(value: str) -> int:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:12], 16)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12683RepairError("json_object_required:" + path.name)
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise Stage12683RepairError(f"jsonl_object_required:{line_number}")
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
            raise Stage12683RepairError(f"{label}_gate_drift:{field}")


def assert_no_forbidden(value: Any, label: str) -> None:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True) if not isinstance(value, str) else value
    for needle in FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise Stage12683RepairError(f"{label}_forbidden_substring:{needle}")


def contains_forbidden(value: Any) -> bool:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True) if not isinstance(value, str) else value
    return any(needle in encoded for needle in FORBIDDEN_SUBSTRINGS)


def scalar_values(value: Any) -> set[str]:
    if isinstance(value, Mapping):
        out: set[str] = set()
        for item in value.values():
            out.update(scalar_values(item))
        return out
    if isinstance(value, list):
        out = set()
        for item in value:
            out.update(scalar_values(item))
        return out
    if isinstance(value, (str, int, float, bool)):
        return {str(value)}
    return set()


def load_inputs() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    paths = {
        "stage12682_summary": S12682_SUMMARY,
        "stage12682_audit": S12682_AUDIT,
        "stage12682_contract": S12682_CONTRACT,
        "repository_summaries": REPO_SUMMARIES,
    }
    for label, path in paths.items():
        if sha256_bytes(path.read_bytes()) != EXPECTED_HASHES[label]:
            raise Stage12683RepairError("pin_drift:" + label)
    summary82, audit82 = read_json(S12682_SUMMARY), read_json(S12682_AUDIT)
    for label, record in (("summary", summary82), ("audit", audit82), ("contract", read_json(S12682_CONTRACT))):
        check_false(record, "stage12682_" + label, UPSTREAM_FALSE_FIELDS)
    if summary82.get("recommended_next_stage") != STAGE or audit82.get("next_required_action") != STAGE:
        raise Stage12683RepairError("stage12682_next_action_drift")
    if summary82.get("decision") != "BLOCKED_PRECISE_LINK_LABEL_LEAKAGE_AMBIGUITY_AND_SPLIT_CONTAMINATION":
        raise Stage12683RepairError("stage12682_decision_drift")
    repos = read_jsonl(REPO_SUMMARIES)
    if len(repos) != 500:
        raise Stage12683RepairError("repo_count_drift")
    return summary82, audit82, repos


def style_token(value: str) -> str:
    if "_" in value:
        return "snake_case"
    if "-" in value:
        return "kebab_case"
    if value[:1].isupper():
        return "upper_camel"
    if any(char.isupper() for char in value[1:]):
        return "lower_camel"
    return "lowercase"


def path_bucket(rel: str) -> str:
    depth = rel.count("/")
    if depth == 0:
        return "root"
    if depth == 1:
        return "shallow"
    if depth <= 3:
        return "nested"
    return "deep"


def file_context(file: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "role": file["role"],
        "language_family": file["language_family"],
        "suffix_token": file["suffix_token"],
        "stem_token": file["stem_token"],
        "stem_style": style_token(str(file["stem_token"])),
        "path_depth_bucket": file["path_depth_bucket"],
        "definition_count_bucket": stage12678.count_bucket(len(file["definitions"])),
    }


def definition_occurrences(text: str, suffix: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if suffix in {".py", ".pyi"}:
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return out
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                kind = "async_function"
            elif isinstance(node, ast.FunctionDef):
                kind = "function"
            elif isinstance(node, ast.ClassDef):
                kind = "class"
            else:
                continue
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                shape = {
                    "positional_parameter_count_bucket": stage12678.count_bucket(len(node.args.posonlyargs) + len(node.args.args)),
                    "keyword_only_parameter_count_bucket": stage12678.count_bucket(len(node.args.kwonlyargs)),
                    "variadic_positional": node.args.vararg is not None,
                    "variadic_keyword": node.args.kwarg is not None,
                    "decorator_count_bucket": stage12678.count_bucket(len(node.decorator_list)),
                }
            else:
                shape = {
                    "base_count_bucket": stage12678.count_bucket(len(node.bases)),
                    "decorator_count_bucket": stage12678.count_bucket(len(node.decorator_list)),
                }
            out.append({"name": node.name, "kind": kind, "line": int(node.lineno), "method": "python_ast_definition", "shape": shape})
        return out[:40]
    for kind, name in stage12678.regex_symbols(text, suffix):
        match = re.search(r"(?<![A-Za-z0-9_$])" + re.escape(name) + r"(?![A-Za-z0-9_$])", text)
        line = text.count("\n", 0, match.start()) + 1 if match else 0
        out.append({
            "name": name,
            "kind": kind,
            "line": line,
            "method": "language_definition_pattern",
            "shape": {"language_suffix": suffix or "none", "pattern_scope": "supported_definition_pattern_only"},
        })
    return out[:40]


def python_imports(text: str) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    rows: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        for alias in node.names:
            if alias.name == "*":
                continue
            rows.append({
                "module": node.module,
                "level": int(node.level),
                "name": alias.name,
                "alias_used": alias.asname is not None,
                "line": int(node.lineno),
            })
    return rows


def module_aliases(rel: str) -> set[str]:
    if not rel.endswith((".py", ".pyi")):
        return set()
    base = rel.rsplit(".", 1)[0]
    if base.endswith("/__init__"):
        base = base[:-9]
    parts = [part for part in base.split("/") if part]
    aliases = {".".join(parts[index:]) for index in range(len(parts))}
    return {alias for alias in aliases if alias}


class UnionFind:
    def __init__(self, values: Iterable[str]):
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: str, right: str) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self.parent[max(left_root, right_root)] = min(left_root, right_root)


def scan_repositories(repos: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, str], dict[str, Any]]:
    scanned: dict[str, dict[str, Any]] = {}
    digest_repos: dict[str, list[str]] = collections.defaultdict(list)
    files_scanned = 0
    for repo in sorted(repos, key=lambda item: (-int(item.get("maintainer_usefulness_score", 0)), str(item["repo_id"]))):
        repo_id = str(repo["repo_id"])
        repo_root = Path(str(repo.get("path", "")))
        if not repo_root.is_dir():
            continue
        files: list[dict[str, Any]] = []
        for path in stage12678.selected_files(repo_root):
            data = stage12678.safe_read(path)
            if not data:
                continue
            rel = path.relative_to(repo_root).as_posix()
            suffix = path.suffix.lower()
            text = data.decode("utf-8", errors="ignore")
            role = stage12678.file_role(rel, path.name, suffix)
            definitions = definition_occurrences(text, suffix) if role == "code" else []
            file = {
                "rel": rel,
                "digest": sha256_bytes(data),
                "role": role,
                "language_family": stage12678.language_for_suffix(suffix),
                "suffix_token": suffix or "<none>",
                "stem_token": path.stem[:80],
                "path_depth_bucket": path_bucket(rel),
                "definitions": definitions,
                "definition_names": {item["name"] for item in definitions},
                "tokens": set(TOKEN_RE.findall(text)) if role in {"doc", "build_config"} else set(),
                "imports": python_imports(text) if role == "test" and suffix in {".py", ".pyi"} else [],
                "module_aliases": module_aliases(rel),
            }
            files.append(file)
            digest_repos[file["digest"]].append(repo_id)
            files_scanned += 1
        scanned[repo_id] = {"repo": repo, "files": files}

    union = UnionFind(scanned)
    for repo_ids in digest_repos.values():
        for repo_id in repo_ids[1:]:
            union.union(repo_ids[0], repo_id)
    members: dict[str, list[str]] = collections.defaultdict(list)
    for repo_id in scanned:
        members[union.find(repo_id)].append(repo_id)
    splits: dict[str, str] = {}
    for repo_ids in members.values():
        component_key = stable_hash(sorted(repo_ids))
        bucket = stable_int(component_key) % 10
        split = "train" if bucket < 6 else "eval" if bucket < 8 else "strict_eval"
        for repo_id in repo_ids:
            splits[repo_id] = split
    stats = {
        "repositories_scanned": len(scanned),
        "source_files_scanned": files_scanned,
        "content_connected_components": len(members),
        "shared_file_digest_groups": sum(1 for repo_ids in digest_repos.values() if len(set(repo_ids)) > 1),
        "cross_split_file_digest_groups": sum(1 for repo_ids in digest_repos.values() if len({splits[item] for item in repo_ids}) > 1),
    }
    return scanned, splits, stats


def draft_row(repo_id: str, split: str, objective: str, input_state: Mapping[str, Any], relation: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "split": split,
        "objective_family": objective,
        "training_stage": "repo_and_code_knowledge.precise_semantic_links",
        "input_state": {"repository_context_id": stage12678.opaque("repo_context", repo_id), **dict(input_state)},
        "expected_output": {"relationship": relation},
        "evidence": {
            "source_stage": STAGE,
            "extraction_method": evidence["extraction_method"],
            "occurrence_proof_digest": evidence["occurrence_proof_digest"],
            "contrast_pair_digest": evidence.get("contrast_pair_digest", stable_hash([repo_id, objective, input_state])),
            "raw_source_body_included": False,
            "absolute_path_included": False,
            "target_file_identity_included": False,
        },
        "authority": row_authority(),
        "quality": {
            "source_body_read_for_extraction_only": True,
            "requires_independent_review_before_training": True,
            "semantic_resolution_claimed": objective == "python_absolute_import_symbol_resolution",
            "lexical_association_only": objective == "doc_build_literal_symbol_association",
        },
    }


def paired_rows(repo_id: str, split: str, objective: str, symbol: Mapping[str, Any], positive: Mapping[str, Any], negative: Mapping[str, Any], context: Mapping[str, Any], positive_relation: str, negative_relation: str, method: str) -> list[dict[str, Any]]:
    base = {
        "symbol_name": symbol["name"],
        "symbol_kind": symbol["kind"],
        "symbol_name_style": style_token(str(symbol["name"])),
        "definition_method": symbol["method"],
        "declaration_line_bucket": stage12678.count_bucket(int(symbol.get("line", 0))),
        "declaration_shape": dict(symbol.get("shape") or {}),
        **dict(context),
    }
    pair_digest = stable_hash([repo_id, objective, symbol["name"], positive["rel"], negative["rel"], context])
    return [
        draft_row(repo_id, split, objective, {**base, "candidate_file": file_context(candidate)}, relation, {
            "extraction_method": method,
            "occurrence_proof_digest": stable_hash([repo_id, symbol["name"], candidate["rel"], relation, symbol.get("line", 0)]),
            "contrast_pair_digest": pair_digest,
        })
        for candidate, relation in ((positive, positive_relation), (negative, negative_relation))
    ]


def choose_negative(code_files: list[dict[str, Any]], positive: Mapping[str, Any], symbol_name: str, salt: str) -> dict[str, Any] | None:
    candidates = [
        file for file in code_files
        if file["rel"] != positive["rel"]
        and file["language_family"] == positive["language_family"]
        and symbol_name not in file["definition_names"]
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: stable_hash([salt, item["rel"]]))[0]


def materialize_drafts(scanned: dict[str, dict[str, Any]], splits: dict[str, str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    drafts: list[dict[str, Any]] = []
    ambiguous_symbol_keys = ambiguous_reference_occurrences = 0
    unresolved_import_occurrences = 0
    for repo_id, packet in sorted(scanned.items()):
        files = packet["files"]
        code_files = [file for file in files if file["role"] == "code" and file["definitions"]]
        definitions: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = collections.defaultdict(list)
        modules: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
        for file in code_files:
            for symbol in file["definitions"][:MAX_SYMBOLS_PER_REPO]:
                definitions[symbol["name"]].append((file, symbol))
            for alias in file["module_aliases"]:
                modules[alias].append(file)
        unique = {name: values[0] for name, values in definitions.items() if len({item[0]["rel"] for item in values}) == 1}
        ambiguous = set(definitions) - set(unique)
        ambiguous_symbol_keys += len(ambiguous)

        for name, (file, symbol) in sorted(unique.items()):
            negative = choose_negative(code_files, file, name, "definition:" + name)
            if negative is None:
                continue
            if symbol["method"] == "python_ast_definition":
                objective = "python_ast_symbol_definition_relation"
                positive_relation = "python_ast_observed_symbol_definition"
                negative_relation = "python_ast_did_not_observe_symbol_definition"
            else:
                objective = "language_pattern_symbol_definition_relation"
                positive_relation = "language_pattern_observed_symbol_definition"
                negative_relation = "language_pattern_did_not_observe_symbol_definition"
            drafts.extend(paired_rows(
                repo_id, splits[repo_id], objective, symbol, file, negative,
                {"candidate_pool_size_bucket": stage12678.count_bucket(len(code_files))},
                positive_relation, negative_relation, symbol["method"],
            ))

        for ref in [file for file in files if file["role"] == "test"]:
            for occurrence in ref["imports"]:
                name = occurrence["name"]
                if occurrence["level"] != 0:
                    unresolved_import_occurrences += 1
                    continue
                if name in ambiguous:
                    ambiguous_reference_occurrences += 1
                    continue
                candidates = modules.get(occurrence["module"], [])
                if len(candidates) != 1 or name not in unique or unique[name][0]["rel"] != candidates[0]["rel"]:
                    unresolved_import_occurrences += 1
                    continue
                positive, symbol = unique[name]
                negative = choose_negative(code_files, positive, name, "import:" + ref["rel"] + ":" + name)
                if negative is None:
                    continue
                drafts.extend(paired_rows(
                    repo_id, splits[repo_id], "python_absolute_import_symbol_resolution", symbol, positive, negative,
                    {
                        "reference_file": file_context(ref),
                        "import_form": "absolute_from_module_import_symbol",
                        "imported_module": occurrence["module"],
                        "import_line_bucket": stage12678.count_bucket(occurrence["line"]),
                        "relative_import_level_bucket": "zero",
                        "alias_used": occurrence["alias_used"],
                    },
                    "absolute_import_resolves_candidate", "absolute_import_does_not_resolve_candidate", "python_ast_absolute_import_unique_module_resolution",
                ))

        for ref in [file for file in files if file["role"] in {"doc", "build_config"}]:
            matched = sorted((ref["tokens"] & set(unique)))[:MAX_LEXICAL_LINKS_PER_FILE]
            for name in matched:
                positive, symbol = unique[name]
                negative = choose_negative(code_files, positive, name, "lexical:" + ref["rel"] + ":" + name)
                if negative is None:
                    continue
                drafts.extend(paired_rows(
                    repo_id, splits[repo_id], "doc_build_literal_symbol_association", symbol, positive, negative,
                    {"reference_file": file_context(ref), "reference_role": ref["role"], "association_scope": "literal_token_only"},
                    "literal_symbol_associates_candidate", "candidate_is_not_unique_definition_file_for_literal", "literal_token_intersection",
                ))

    stats = {
        "draft_rows_before_deduplication": len(drafts),
        "ambiguous_symbol_keys_quarantined": ambiguous_symbol_keys,
        "ambiguous_reference_occurrences_quarantined": ambiguous_reference_occurrences,
        "unresolved_import_occurrences_quarantined": unresolved_import_occurrences,
    }
    return drafts, stats


def finalize_rows(drafts: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    unique_by_semantic: dict[str, dict[str, Any]] = {}
    input_targets: dict[str, set[str]] = collections.defaultdict(set)
    forbidden_lexical_candidates_quarantined = 0
    for row in drafts:
        encoded = json.dumps(row, sort_keys=True, ensure_ascii=True)
        if any(needle in encoded for needle in FORBIDDEN_SUBSTRINGS):
            forbidden_lexical_candidates_quarantined += 1
            continue
        semantic_key = stable_hash({key: row[key] for key in ("split", "objective_family", "input_state", "expected_output", "evidence")})
        unique_by_semantic.setdefault(semantic_key, row)
        input_key = stable_hash({"objective_family": row["objective_family"], "input_state": row["input_state"]})
        input_targets[input_key].add(stable_hash(row["expected_output"]))
    conflicts = {key for key, targets in input_targets.items() if len(targets) > 1}
    eligible = []
    target_leak_rows = 0
    for row in unique_by_semantic.values():
        input_key = stable_hash({"objective_family": row["objective_family"], "input_state": row["input_state"]})
        if input_key in conflicts:
            continue
        target_values = scalar_values(row["expected_output"])
        target_leak_rows += int(bool(target_values & (scalar_values(row["input_state"]) | scalar_values(row["evidence"]))))
        eligible.append(row)
    pair_rows: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in eligible:
        pair_rows[row["evidence"]["contrast_pair_digest"]].append(row)
    complete_pairs = {
        key: values for key, values in pair_rows.items()
        if len(values) == 2
        and len({row["expected_output"]["relationship"] for row in values}) == 2
        and len({row["objective_family"] for row in values}) == 1
        and len({row["split"] for row in values}) == 1
    }
    selected_pairs: list[list[dict[str, Any]]] = []
    pair_buckets: dict[tuple[str, str], list[tuple[str, list[dict[str, Any]]]]] = collections.defaultdict(list)
    for key, values in complete_pairs.items():
        pair_buckets[(values[0]["objective_family"], values[0]["split"])].append((key, values))
    selected_pair_counts: dict[str, dict[str, int]] = collections.defaultdict(dict)
    for (objective, split), values in sorted(pair_buckets.items()):
        limit = MAX_PAIRS_BY_OBJECTIVE_SPLIT[objective][split]
        chosen = sorted(values, key=lambda item: item[0])[:limit]
        selected_pairs.extend(pair for _key, pair in chosen)
        selected_pair_counts[objective][split] = len(chosen)
    kept = [row for pair in selected_pairs for row in pair]
    kept.sort(key=lambda row: (row["evidence"]["contrast_pair_digest"], row["expected_output"]["relationship"]))
    for index, row in enumerate(kept):
        row["row_id"] = f"stage12683_precise_link_semantic_repair_{index:06d}"
        assert_no_forbidden(row, "stage12683_row")
    stats = {
        "semantic_duplicate_excess_rows_removed": len(drafts) - forbidden_lexical_candidates_quarantined - len(unique_by_semantic),
        "conflicting_input_groups_quarantined": len(conflicts),
        "target_leak_rows": target_leak_rows,
        "forbidden_lexical_candidates_quarantined": forbidden_lexical_candidates_quarantined,
        "incomplete_contrast_pairs_quarantined": len(pair_rows) - len(complete_pairs),
        "complete_contrast_pairs_before_quota": len(complete_pairs),
        "contrast_pairs_materialized": len(selected_pairs),
        "materialized_pair_counts_by_objective_split": {key: dict(sorted(value.items())) for key, value in sorted(selected_pair_counts.items())},
    }
    return kept, stats


def build_packet() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    summary82, _audit82, repos = load_inputs()
    scanned, splits, scan_stats = scan_repositories(repos)
    drafts, generation_stats = materialize_drafts(scanned, splits)
    rows, repair_stats = finalize_rows(drafts)
    if len(rows) < 20_000:
        raise Stage12683RepairError("repaired_rows_below_minimum_scale")
    if repair_stats["target_leak_rows"]:
        raise Stage12683RepairError("target_leakage_detected")
    if scan_stats["cross_split_file_digest_groups"]:
        raise Stage12683RepairError("content_connected_split_failure")
    objective_counts = dict(sorted(collections.Counter(row["objective_family"] for row in rows).items()))
    relation_counts = dict(sorted(collections.Counter(row["expected_output"]["relationship"] for row in rows).items()))
    split_counts = dict(sorted(collections.Counter(row["split"] for row in rows).items()))
    stats = {**scan_stats, **generation_stats, **repair_stats}
    decision = "PRECISE_LINK_SEMANTIC_REPAIR_MATERIALIZED_INDEPENDENT_REVIEW_REQUIRED"
    audit = {
        "record_type": "stage12683_precise_link_semantic_repair_audit_v1",
        "stage": STAGE,
        "decision": decision,
        "input_hashes": EXPECTED_HASHES,
        "upstream_blocked_rows": summary82["precise_link_rows_reviewed"],
        "materialized_rows": len(rows),
        "objective_counts": objective_counts,
        "relation_counts": relation_counts,
        "split_counts": split_counts,
        "repair_stats": stats,
        "semantic_claim_policy": {
            "python_ast_definition_relations": "ast_observed_definition_or_ast_non_observation_in_same_language_candidate",
            "language_pattern_definition_relations": "supported_pattern_observation_or_non_observation_only_no_universal_absence_claim",
            "python_import_relations": "absolute_import_unique_repository_module_alias_and_symbol_resolution_from_python_ast",
            "doc_build_relations": "literal_association_only_no_semantic_resolution_claim",
        },
        "training_source_rows_admitted": 0,
        "gemma_execution_used": False,
        "gemma_role": "quarantined_review_metadata_only",
        "next_required_action": "stage12684_precise_link_semantic_repair_independent_review_only",
        **false_fields(),
    }
    summary = {
        "record_type": "stage12683_public_precise_link_semantic_repair_summary_v1",
        "stage": STAGE,
        "decision": decision,
        "materialized_rows": len(rows),
        "objective_counts": objective_counts,
        "relation_counts": relation_counts,
        "split_counts": split_counts,
        "ambiguous_symbol_keys_quarantined": stats["ambiguous_symbol_keys_quarantined"],
        "unresolved_import_occurrences_quarantined": stats["unresolved_import_occurrences_quarantined"],
        "cross_split_file_digest_groups": stats["cross_split_file_digest_groups"],
        "semantic_duplicate_excess_rows": 0,
        "identical_input_multiple_target_groups": 0,
        "target_leak_rows": stats["target_leak_rows"],
        "contrast_pairs_materialized": stats["contrast_pairs_materialized"],
        "incomplete_contrast_pairs_quarantined": stats["incomplete_contrast_pairs_quarantined"],
        "gemma_execution_used": False,
        "gemma_role": "quarantined_review_metadata_only",
        "training_source_rows_admitted": 0,
        "recommended_next_stage": audit["next_required_action"],
        **false_fields(),
    }
    checks = [
        {"check_id": "stage12682_and_repository_hash_pins", "status": "passed", "count": len(EXPECTED_HASHES)},
        {"check_id": "ambiguous_symbols_quarantined", "status": "passed", "count": stats["ambiguous_symbol_keys_quarantined"]},
        {"check_id": "content_connected_split_isolation", "status": "passed", "count": stats["cross_split_file_digest_groups"]},
        {"check_id": "target_leakage_absence", "status": "passed", "count": stats["target_leak_rows"]},
        {"check_id": "semantic_duplicate_absence", "status": "passed", "count": 0},
        {"check_id": "complete_contrast_pair_preservation", "status": "passed", "count": stats["contrast_pairs_materialized"]},
        {"check_id": "independent_review", "status": "blocked", "count": 0},
        {"check_id": "training_authority", "status": "blocked", "count": 0},
    ]
    for label, value in (("summary", summary), ("audit", audit), ("checks", checks)):
        assert_no_forbidden(value, label)
    return summary, audit, checks, rows


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    summary, audit, checks, rows = build_packet()
    private = {
        "record_type": "stage12683_private_precise_link_semantic_repair_packet_v1",
        "stage": STAGE,
        "input_hashes": EXPECTED_HASHES,
        "rows_sha256": stable_hash(rows),
        "audit_sha256": stable_hash(audit),
        "checks_sha256": stable_hash(checks),
        **false_fields(),
    }
    contract = {
        "record_type": "stage12683_precise_link_semantic_repair_contract_v1",
        "stage": STAGE,
        "decision": summary["decision"],
        "materialized_rows": len(rows),
        "rows_sha256": stable_hash(rows),
        "private_packet_sha256": stable_hash(private),
        "audit_sha256": stable_hash(audit),
        "recommended_next_stage": summary["recommended_next_stage"],
        **false_fields(),
    }
    pointer = {
        "record_type": "stage12683_digest_pointer_v1",
        "stage": STAGE,
        "summary_sha256": stable_hash(summary),
        "contract_sha256": stable_hash(contract),
        "private_packet_sha256": stable_hash(private),
        "audit_sha256": stable_hash(audit),
        "rows_sha256": stable_hash(rows),
        **false_fields(),
    }
    for label, value in (("private", private), ("contract", contract), ("pointer", pointer)):
        assert_no_forbidden(value, label)
    write_jsonl(out / "private/precise_link_semantic_repair_rows.jsonl", rows)
    write_json(out / "summary.json", summary)
    write_json(out / "precise_link_semantic_repair_audit.json", audit)
    write_jsonl(out / "private/precise_link_semantic_repair_checks.jsonl", checks)
    write_json(out / "private/precise_link_semantic_repair_packet.json", private)
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(summary_path, summary)
    fsync_dir(out / "private")
    fsync_dir(out)
    fsync_dir(summary_path.parent)
    return summary


def main() -> int:
    print(json.dumps(build(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
