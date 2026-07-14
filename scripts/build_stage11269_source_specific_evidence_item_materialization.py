#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11269
NAME = "stage11269_source_specific_evidence_item_materialization"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "source_specific_evidence_item_materialization.json"
TRAIN_JSONL = OUT_DIR / "source_specific_evidence_item_train_rows.jsonl"
VALIDATION_JSONL = OUT_DIR / "source_specific_evidence_item_validation_rows.jsonl"
STRICT_JSONL = OUT_DIR / "source_specific_evidence_item_strict_rows.jsonl"
BLOCKED_JSONL = OUT_DIR / "source_specific_evidence_item_blocked_roots.jsonl"
ROOT_SPLITS_JSONL = OUT_DIR / "source_specific_evidence_item_root_splits.jsonl"

SOURCE_CANDIDATES = ARTIFACTS / "stage11237_multilingual_verifier_constraint_source_inventory/verifier_constraint_source_candidates.jsonl"
RETRIEVAL_ROWS = ARTIFACTS / "strict_long_context_train_ready_plus_audit_v1/retrieval_rows.jsonl"
FULL_CONTEXT_ROWS = ARTIFACTS / "strict_long_context_train_ready_plus_audit_v1/full_context_rows.jsonl"

LABELS = list("ABCDEFGHIJ")
JUDGMENT_VALUES = [
    "DECISIVE_VERIFIER_TEST_CONSTRAINT",
    "SUPPORTING_CANDIDATE_CHANGE_SURFACE",
    "SUPPORTING_SYMPTOM_OR_CALL_PATH",
    "DISTRACTOR_BACKGROUND_CONTEXT",
]
ROLE_ALIAS_TOKENS = {
    "verifier_and_test_constraint",
    "candidate_change_surface",
    "symptom_or_call_path_analogue",
    "DECISIVE_VERIFIER_TEST_CONSTRAINT",
    "SUPPORTING_CANDIDATE_CHANGE_SURFACE",
    "SUPPORTING_SYMPTOM_OR_CALL_PATH",
    "DISTRACTOR_BACKGROUND_CONTEXT",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def stable_hash(text: str, n: int = 10) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:n]


def norm_path(path: str) -> str:
    path = str(path or "").strip().replace("\\", "/")
    parts = [p for p in path.split("/") if p and p != "."]
    return "/".join(parts)


def path_matches(candidate_path: str, chunk_path: str) -> bool:
    cand = norm_path(candidate_path)
    chunk = norm_path(chunk_path)
    return bool(cand and chunk and (cand == chunk or cand.endswith("/" + chunk) or chunk.endswith("/" + cand)))


def scrub_role_aliases(text: str) -> str:
    out = text
    replacements = {
        "verification_constraint": "test-linked evidence",
        "seed_change": "changed-source evidence",
        "trace_analogue": "runtime-path evidence",
        "algorithm_grounding": "background grounding",
        "cross_repo_analogue": "cross-repository analogue",
        "repo_graph_neighbor": "nearby repository context",
        "test_neighbor": "nearby test context",
    }
    for key, value in replacements.items():
        out = re.sub(re.escape(key), value, out, flags=re.IGNORECASE)
    return out


def excerpt(text: str, *, limit: int = 720) -> str:
    text = str(text or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.rstrip() for ln in text.splitlines()]
    interesting: list[str] = []
    patterns = (
        "assert ",
        "def ",
        "class ",
        "fn ",
        "test",
        "pytest",
        "expect(",
        "describe(",
        "it(",
        "return ",
        "raise ",
        "panic!",
        "Result<",
        "#include",
    )
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if any(p in stripped for p in patterns):
            start = max(0, idx - 1)
            end = min(len(lines), idx + 4)
            interesting.extend(lines[start:end])
            break
    if not interesting:
        interesting = [ln for ln in lines if ln.strip()][:8]
    compact = "\n".join(interesting).strip()
    compact = re.sub(r"\n{3,}", "\n\n", compact)
    if len(compact) > limit:
        compact = compact[: limit - 3].rstrip() + "..."
    return compact


def deterministic_options(seed: str) -> list[dict[str, str]]:
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    keyed = sorted((digest[idx % len(digest)], value) for idx, value in enumerate(JUDGMENT_VALUES))
    return [{"label": LABELS[idx], "value": value} for idx, (_, value) in enumerate(keyed)]


def index_retrieval_rows() -> dict[str, dict[str, Any]]:
    return {row["row_id"]: row for row in load_jsonl(RETRIEVAL_ROWS)}


def index_chunk_text() -> dict[str, dict[str, Any]]:
    chunks: dict[str, dict[str, Any]] = {}
    for row in load_jsonl(FULL_CONTEXT_ROWS):
        for chunk in row.get("context_rows") or []:
            if chunk.get("chunk_id") and chunk.get("text"):
                chunks[str(chunk["chunk_id"])] = chunk
    return chunks


def split_roots(candidates: list[dict[str, Any]]) -> dict[str, str]:
    by_lang: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in candidates:
        by_lang[str(item.get("language_family") or "unknown")].append(item)
    root_to_split: dict[str, str] = {}
    for _lang, items in sorted(by_lang.items()):
        items = sorted(items, key=lambda item: (-float(item.get("quality_score") or 0.0), str(item.get("root_id") or "")))
        n = len(items)
        if n <= 1:
            val_n, strict_n = 0, 0
        elif n == 2:
            val_n, strict_n = 0, 1
        elif n < 8:
            val_n, strict_n = 1, 1
        else:
            val_n = max(1, int(round(n * 0.10)))
            strict_n = max(1, int(round(n * 0.10)))
        for idx, item in enumerate(items):
            root = str(item.get("root_id") or item.get("source_root_id"))
            if idx < strict_n:
                split = "strict_eval"
            elif idx < strict_n + val_n:
                split = "validation"
            else:
                split = "train"
            root_to_split[root] = split
    return root_to_split


def choose_support(
    item: dict[str, Any],
    retrieval: dict[str, Any],
    chunks: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    blockers: list[str] = []
    support_scores = retrieval.get("support_scores") or []
    candidates: dict[str, list[dict[str, Any]]] = {
        "verifier": [],
        "changed": [],
        "symptom": [],
        "distractor": [],
    }
    changed_paths = [norm_path(x) for x in item.get("candidate_change_surface_paths") or []]
    verifier_paths = [norm_path(x) for x in item.get("verifier_and_test_constraint_paths") or []]
    symptom_paths = [norm_path(x) for x in item.get("symptom_or_call_path_analogue_paths") or []]

    for score in support_scores:
        cid = str(score.get("chunk_id") or "")
        chunk = chunks.get(cid)
        if not chunk:
            continue
        path = norm_path(score.get("path") or chunk.get("path") or "")
        enriched = {**score, "text": chunk.get("text") or "", "doc_id": chunk.get("doc_id") or path, "path": path}
        role = str(score.get("role") or "")
        if any(path_matches(p, path) for p in verifier_paths) or role == "verification_constraint":
            candidates["verifier"].append(enriched)
        if any(path_matches(p, path) for p in changed_paths) or role == "seed_change":
            candidates["changed"].append(enriched)
        if any(path_matches(p, path) for p in symptom_paths) or role == "trace_analogue":
            candidates["symptom"].append(enriched)
        if role in {"algorithm_grounding", "cross_repo_analogue", "repo_graph_neighbor", "test_neighbor"}:
            candidates["distractor"].append(enriched)

    used: set[str] = set()
    selected: dict[str, dict[str, Any]] = {}
    for key in ["verifier", "changed", "symptom", "distractor"]:
        ordered = sorted(
            candidates[key],
            key=lambda score: (-float(score.get("score") or 0), str(score.get("chunk_id") or "")),
        )
        for score in ordered:
            cid = str(score.get("chunk_id") or "")
            if cid not in used and excerpt(score.get("text") or ""):
                selected[key] = score
                used.add(cid)
                break
        if key not in selected:
            blockers.append(f"missing_distinct_{key}_text_chunk")
    return selected, blockers


def candidate_text(kind: str, score: dict[str, Any]) -> str:
    path = norm_path(score.get("path") or score.get("doc_id") or "")
    body = excerpt(str(score.get("text") or ""))
    return scrub_role_aliases(f"Source path: {path}\nEvidence note: materialized source excerpt from the root evidence ledger.\nExcerpt:\n{body}")


def prompt_for(item: dict[str, Any], evidence_text: str, options: list[dict[str, str]]) -> str:
    lines = [
        f"Language: {item.get('language_family')}",
        "Perspective: evidence_candidate_judgment",
        "Decision objective: classify the single source-derived evidence item as decisive verifier/test evidence, changed-source support, symptom/call-path support, or background context.",
        "Use only the visible root context and candidate evidence item. Do not infer from option order.",
        f"Repository family: {item.get('repo_family')}",
        f"Execution route: {item.get('execution_route') or 'UNKNOWN'}",
        f"Test-selection route: {item.get('test_selection_route') or 'UNKNOWN'}",
        "Root context:",
        f"- Changed-surface count: {len(item.get('candidate_change_surface_paths') or [])}",
        f"- Verifier/test target count: {len(item.get('verifier_and_test_constraint_paths') or [])}",
        f"- Key-symbol count: {len(item.get('key_symbols') or [])}",
        "",
        "Candidate evidence item under judgment:",
        f"Candidate ID: CE-{stable_hash(str(item.get('root_id')) + evidence_text, 8)}",
        evidence_text,
        "",
        "Options:",
    ]
    lines.extend(f"{opt['label']}. {opt['value']}" for opt in options)
    lines.append("Answer:")
    return "\n".join(lines)


def build_rows_for_root(
    item: dict[str, Any],
    split: str,
    retrieval_by_id: dict[str, dict[str, Any]],
    chunks: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    blockers: list[str] = []
    if item.get("language_family") not in {"python", "rust", "c_cpp", "web_js_ts_html"}:
        blockers.append("unsupported_language")
    if not item.get("candidate_change_surface_paths"):
        blockers.append("missing_candidate_paths")
    if not item.get("verifier_and_test_constraint_paths"):
        blockers.append("missing_verifier_paths")
    if set(item.get("candidate_change_surface_paths") or []) & set(item.get("verifier_and_test_constraint_paths") or []):
        blockers.append("candidate_verifier_path_overlap")
    retrieval = retrieval_by_id.get(str(item.get("source_row_id") or ""))
    if not retrieval:
        blockers.append("missing_retrieval_source_row")
    selected: dict[str, dict[str, Any]] = {}
    if retrieval:
        selected, chunk_blockers = choose_support(item, retrieval, chunks)
        blockers.extend(chunk_blockers)
    if blockers:
        return [], [{"root_id": item.get("root_id"), "source_row_id": item.get("source_row_id"), "language_family": item.get("language_family"), "blockers": sorted(set(blockers))}]

    projections = [
        ("verifier", "DECISIVE_VERIFIER_TEST_CONSTRAINT"),
        ("changed", "SUPPORTING_CANDIDATE_CHANGE_SURFACE"),
        ("symptom", "SUPPORTING_SYMPTOM_OR_CALL_PATH"),
        ("distractor", "DISTRACTOR_BACKGROUND_CONTEXT"),
    ]
    rows: list[dict[str, Any]] = []
    for kind, target in projections:
        text = candidate_text(kind, selected[kind])
        seed = f"{item.get('root_id')}::{kind}::{target}"
        options = deterministic_options(seed)
        target_label = next(opt["label"] for opt in options if opt["value"] == target)
        prompt = prompt_for(item, text, options)
        row_id = f"stage11269::{item.get('source_root_id')}::source_specific_evidence_candidate_judgment::{kind}"
        row = {
            "row_id": row_id,
            "root_id": item.get("root_id"),
            "source_root_id": item.get("source_root_id"),
            "root_lineage_key": item.get("root_lineage_key"),
            "source_row_id": item.get("source_row_id"),
            "source_family_id": item.get("source_family_id"),
            "repo_family": item.get("repo_family"),
            "repo_id": item.get("repo_id"),
            "language_family": item.get("language_family"),
            "task_type": "evidence_candidate_judgment",
            "surface": "maintainer_source_specific_evidence_candidate_judgment_bounded_choice",
            "split": split,
            "package_split": split,
            "input_text": prompt,
            "prompt_text": prompt,
            "decoder_text": target_label,
            "target_text": target_label,
            "bounded_choice_target_label": target_label,
            "semantic_target_value": target,
            "opaque_options": options,
            "expected_enabled_loss": "decoder_ce",
            "loss_mask": {"decoder_ce": True},
            "strict_eval_eligible": split == "strict_eval",
            "train_support_only": split == "train",
            "anti_cheat": {
                "deterministic_option_shuffle": True,
                "root_split_isolation_required": True,
                "single_candidate_item_judgment": True,
                "target_label_not_visible_before_options": True,
                "role_alias_not_visible_before_options": True,
                "candidate_and_verifier_paths_distinct": True,
                "source_text_materialized": True,
            },
            "standalone_projection_source": {
                "gold_label": target_label,
                "gold_value": target,
                "opaque_options": options,
                "candidate_evidence_kind": kind,
                "candidate_evidence_text": text,
                "source_chunk_id": selected[kind].get("chunk_id"),
                "source_chunk_path": selected[kind].get("path"),
                "source_chunk_role": selected[kind].get("role"),
                "source_chunk_support_reasons": selected[kind].get("support_reasons") or [],
                "candidate_change_surface_paths": item.get("candidate_change_surface_paths") or [],
                "verifier_and_test_constraint_paths": item.get("verifier_and_test_constraint_paths") or [],
                "symptom_or_call_path_analogue_paths": item.get("symptom_or_call_path_analogue_paths") or [],
                "key_symbols": item.get("key_symbols") or [],
                "source_row_id": item.get("source_row_id"),
                "source_inventory_stage": "stage11237",
                "objective": "source_specific_candidate_evidence_decisive_supporting_or_distractor_judgment",
            },
        }
        rows.append(row)
    return rows, []


def audit_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    duplicate_ids = len(rows) - len({row["row_id"] for row in rows})
    label_leaks = 0
    role_alias_leaks = 0
    internal_reason_leaks = 0
    for row in rows:
        before_options = str(row.get("prompt_text") or "").split("Options:", 1)[0]
        if str(row.get("bounded_choice_target_label") or "") and re.search(rf"\b{re.escape(str(row['bounded_choice_target_label']))}\b", before_options):
            label_leaks += 1
        for token in ROLE_ALIAS_TOKENS:
            if token in before_options:
                role_alias_leaks += 1
                break
        if "grounded_" in before_options or "_path_match" in before_options or "role_match" in before_options:
            internal_reason_leaks += 1
    roots_by_split: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        roots_by_split[str(row.get("split"))].add(str(row.get("root_id")))
    overlaps = {
        "train_validation": sorted(roots_by_split["train"] & roots_by_split["validation"]),
        "train_strict": sorted(roots_by_split["train"] & roots_by_split["strict_eval"]),
        "validation_strict": sorted(roots_by_split["validation"] & roots_by_split["strict_eval"]),
    }
    return {
        "duplicate_row_ids": duplicate_ids,
        "target_label_leak_rows": label_leaks,
        "role_alias_leak_rows": role_alias_leaks,
        "internal_support_reason_leak_rows": internal_reason_leaks,
        "root_overlap": overlaps,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source_candidates = [row for row in load_jsonl(SOURCE_CANDIDATES) if row.get("admission_ready")]
    retrieval_by_id = index_retrieval_rows()
    chunks = index_chunk_text()
    root_splits = split_roots(source_candidates)

    rows: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    split_rows: list[dict[str, Any]] = []
    for item in source_candidates:
        split = root_splits.get(str(item.get("root_id")), "train")
        split_rows.append({
            "root_id": item.get("root_id"),
            "source_row_id": item.get("source_row_id"),
            "root_lineage_key": item.get("root_lineage_key"),
            "language_family": item.get("language_family"),
            "repo_family": item.get("repo_family"),
            "split": split,
        })
        built, block = build_rows_for_root(item, split, retrieval_by_id, chunks)
        rows.extend(built)
        blocked.extend(block)

    by_split = defaultdict(list)
    for row in rows:
        by_split[str(row.get("split"))].append(row)
    train = by_split["train"]
    validation = by_split["validation"]
    strict = by_split["strict_eval"]

    write_jsonl(TRAIN_JSONL, train)
    write_jsonl(VALIDATION_JSONL, validation)
    write_jsonl(STRICT_JSONL, strict)
    write_jsonl(BLOCKED_JSONL, blocked)
    write_jsonl(ROOT_SPLITS_JSONL, split_rows)

    audit = audit_rows(rows)
    counts = {
        "source_ready_candidates": len(source_candidates),
        "materialized_roots": len({row["root_id"] for row in rows}),
        "blocked_roots": len(blocked),
        "train_rows": len(train),
        "validation_rows": len(validation),
        "strict_rows": len(strict),
        "by_split_language": {
            split: dict(Counter(str(row.get("language_family")) for row in split_rows_))
            for split, split_rows_ in [("train", train), ("validation", validation), ("strict_eval", strict)]
        },
        "by_split_target": {
            split: dict(Counter(str(row.get("semantic_target_value")) for row in split_rows_))
            for split, split_rows_ in [("train", train), ("validation", validation), ("strict_eval", strict)]
        },
        "source_chunks_indexed": len(chunks),
        "retrieval_rows_indexed": len(retrieval_by_id),
        "c_cpp_gap": {
            "ready_c_cpp_roots": sum(1 for row in source_candidates if row.get("language_family") == "c_cpp"),
            "reason": "stage11237 found no clean C/C++ verifier-constraint source candidates under current filters",
        },
    }
    passed = bool(rows) and not audit["duplicate_row_ids"] and not audit["target_label_leak_rows"] and not audit["role_alias_leak_rows"] and not audit["internal_support_reason_leak_rows"] and not any(audit["root_overlap"].values())
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": passed,
        "decision": "source_specific_evidence_item_materialization_ready" if passed else "source_specific_evidence_item_materialization_blocked",
        "counts": counts,
        "audit": audit,
        "quality_gates": {
            "uses_materialized_chunk_text": all((row.get("anti_cheat") or {}).get("source_text_materialized") for row in rows),
            "root_split_disjoint": not any(audit["root_overlap"].values()),
            "unique_row_ids": audit["duplicate_row_ids"] == 0,
            "target_label_not_visible_before_options": audit["target_label_leak_rows"] == 0,
            "role_alias_not_visible_before_options": audit["role_alias_leak_rows"] == 0,
            "internal_support_reasons_not_visible": audit["internal_support_reason_leak_rows"] == 0,
            "has_validation_and_strict": bool(validation and strict),
        },
        "interpretation": {
            "why_this_differs_from_stage11259": "Rows use actual source chunk excerpts resolved from full_context_rows instead of generic path-list templates.",
            "claim_limit": "Still diagnostic: C/C++ source supply is absent and Rust/Web supply remains small.",
        },
        "outputs": {
            "train_jsonl": rel(TRAIN_JSONL),
            "validation_jsonl": rel(VALIDATION_JSONL),
            "strict_jsonl": rel(STRICT_JSONL),
            "blocked_jsonl": rel(BLOCKED_JSONL),
            "root_splits_jsonl": rel(ROOT_SPLITS_JSONL),
            "summary_json": rel(SUMMARY_JSON),
        },
        "source_artifacts": {
            "stage11237_candidates": rel(SOURCE_CANDIDATES),
            "retrieval_rows": rel(RETRIEVAL_ROWS),
            "full_context_rows": rel(FULL_CONTEXT_ROWS),
        },
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
