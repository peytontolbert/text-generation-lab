#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import build_stage11269_source_specific_evidence_item_materialization as s11269

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11275
NAME = "stage11275_direct_retrieval_multilingual_evidence_materialization"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "direct_retrieval_multilingual_evidence_materialization.json"
TRAIN_JSONL = OUT_DIR / "direct_retrieval_multilingual_evidence_train_rows.jsonl"
VALIDATION_JSONL = OUT_DIR / "direct_retrieval_multilingual_evidence_validation_rows.jsonl"
STRICT_JSONL = OUT_DIR / "direct_retrieval_multilingual_evidence_strict_rows.jsonl"
BLOCKED_JSONL = OUT_DIR / "direct_retrieval_multilingual_evidence_blocked_roots.jsonl"
ROOT_SPLITS_JSONL = OUT_DIR / "direct_retrieval_multilingual_evidence_root_splits.jsonl"

RETRIEVAL_ROWS = ARTIFACTS / "strict_long_context_train_ready_plus_audit_v1/retrieval_rows.jsonl"
FULL_CONTEXT_ROWS = ARTIFACTS / "strict_long_context_train_ready_plus_audit_v1/full_context_rows.jsonl"

ROLE_TARGETS = {
    "verifier": "DECISIVE_VERIFIER_TEST_CONSTRAINT",
    "changed": "SUPPORTING_CANDIDATE_CHANGE_SURFACE",
    "symptom": "SUPPORTING_SYMPTOM_OR_CALL_PATH",
    "distractor": "DISTRACTOR_BACKGROUND_CONTEXT",
}
ROLE_MAP = {
    "verification_constraint": "verifier",
    "seed_change": "changed",
    "trace_analogue": "symptom",
    "algorithm_grounding": "distractor",
    "cross_repo_analogue": "distractor",
    "repo_graph_neighbor": "distractor",
    "test_neighbor": "distractor",
}


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def infer_language(row: dict[str, Any]) -> str:
    text = ((row.get("query_text") or "") + " " + json.dumps(row.get("target_text") or {})).lower()
    if any(token in text for token in [".rs", "cargo", " rust"]):
        return "rust"
    if any(token in text for token in [".cpp", ".cc", ".cxx", ".hpp", ".cu", ".cuh", " c++", "cmake"]):
        return "c_cpp"
    if any(token in text for token in [".js", ".ts", ".tsx", ".jsx", ".html", "javascript", "typescript"]):
        return "web_js_ts_html"
    if ".py" in text or "python" in text:
        return "python"
    return "unknown"


def repo_id(row: dict[str, Any]) -> str:
    metadata = row.get("metadata") or {}
    if metadata.get("canonical_name"):
        return str(metadata["canonical_name"])
    match = re.search(r"^Repository:\s*(.+)$", str(row.get("query_text") or ""), flags=re.MULTILINE)
    return (match.group(1).strip() if match else "unknown").replace("-", "_").replace("/", "_").lower()


def target_state(row: dict[str, Any]) -> dict[str, Any]:
    target = row.get("target_text") or {}
    if isinstance(target, str):
        try:
            target = json.loads(target)
        except json.JSONDecodeError:
            target = {}
    if not isinstance(target, dict):
        return {}
    final_state = target.get("final_state") or {}
    return final_state if isinstance(final_state, dict) else {}


def split_roots(items: list[dict[str, Any]]) -> dict[str, str]:
    by_lang: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        by_lang[item["language_family"]].append(item)
    out: dict[str, str] = {}
    for _lang, rows in sorted(by_lang.items()):
        rows = sorted(rows, key=lambda x: (x["repo_family"], x["source_row_id"]))
        n = len(rows)
        if n <= 2:
            strict_n, val_n = (1 if n == 2 else 0), 0
        elif n < 8:
            strict_n, val_n = 1, 1
        else:
            strict_n, val_n = max(1, round(n * 0.15)), max(1, round(n * 0.15))
        for idx, item in enumerate(rows):
            if idx < strict_n:
                split = "strict_eval"
            elif idx < strict_n + val_n:
                split = "validation"
            else:
                split = "train"
            out[item["root_id"]] = split
    return out


def selected_supports(row: dict[str, Any], chunks: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for score in row.get("support_scores") or []:
        cid = str(score.get("chunk_id") or "")
        chunk = chunks.get(cid)
        if not chunk:
            continue
        if str(score.get("source_type") or chunk.get("source_type") or "") != "local_repo":
            continue
        role = ROLE_MAP.get(str(score.get("role") or ""))
        if not role:
            continue
        path = s11269.norm_path(score.get("path") or chunk.get("path") or "")
        text = chunk.get("text") or ""
        if not s11269.excerpt(text):
            continue
        buckets[role].append({**score, "path": path, "text": text, "doc_id": chunk.get("doc_id") or path})
    selected: dict[str, dict[str, Any]] = {}
    used: set[str] = set()
    for role in ["verifier", "changed", "symptom", "distractor"]:
        for score in sorted(buckets[role], key=lambda x: (-float(x.get("score") or 0), str(x.get("chunk_id") or ""))):
            cid = str(score.get("chunk_id") or "")
            if cid not in used:
                selected[role] = score
                used.add(cid)
                break
    return selected


def make_prompt(item: dict[str, Any], evidence_text: str, options: list[dict[str, str]]) -> str:
    return "\n".join([
        f"Language: {item['language_family']}",
        "Perspective: evidence_candidate_judgment",
        "Decision objective: classify this source-derived evidence item as verifier/test evidence, changed-source support, symptom/call-path support, or background context.",
        "Use only the root context and candidate evidence item. Do not infer from option order.",
        f"Repository family: {item['repo_family']}",
        f"Execution route: {item.get('execution_route') or 'UNKNOWN'}",
        f"Verifier route: {item.get('test_selection_route') or 'UNKNOWN'}",
        "Root context:",
        f"- Source row: {item['source_row_id']}",
        f"- Available local evidence roles: {', '.join(sorted(item['available_roles']))}",
        "",
        "Candidate evidence item under judgment:",
        f"Candidate ID: CE-{s11269.stable_hash(item['root_id'] + evidence_text, 8)}",
        evidence_text,
        "",
        "Options:",
        *[f"{opt['label']}. {opt['value']}" for opt in options],
        "Answer:",
    ])


def build_rows(item: dict[str, Any], split: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for role, score in item["selected"].items():
        target = ROLE_TARGETS[role]
        evidence_text = s11269.candidate_text(role, score)
        options = s11269.deterministic_options(f"{item['root_id']}::{role}::direct_retrieval")
        target_label = next(opt["label"] for opt in options if opt["value"] == target)
        prompt = make_prompt(item, evidence_text, options)
        rows.append({
            "row_id": f"stage11275::{item['source_row_id']}::direct_retrieval_evidence_candidate_judgment::{role}",
            "root_id": item["root_id"],
            "source_root_id": item["source_row_id"],
            "root_lineage_key": item["root_lineage_key"],
            "source_row_id": item["source_row_id"],
            "source_family_id": "strict_long_context_train_ready_plus_audit_v1",
            "repo_family": item["repo_family"],
            "repo_id": item["repo_id"],
            "language_family": item["language_family"],
            "task_type": "evidence_candidate_judgment",
            "surface": "maintainer_direct_retrieval_source_evidence_candidate_judgment_bounded_choice",
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
                "source_text_materialized": True,
                "target_label_not_visible_before_options": True,
                "role_alias_not_visible_before_options": True,
            },
            "standalone_projection_source": {
                "gold_label": target_label,
                "gold_value": target,
                "opaque_options": options,
                "candidate_evidence_kind": role,
                "candidate_evidence_text": evidence_text,
                "source_chunk_id": score.get("chunk_id"),
                "source_chunk_path": score.get("path"),
                "source_chunk_role": score.get("role"),
                "source_chunk_support_reasons": score.get("support_reasons") or [],
                "source_row_id": item["source_row_id"],
                "source_inventory_stage": "stage11275_direct_retrieval",
            },
        })
    return rows


def audit_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    duplicate_ids = len(rows) - len({row["row_id"] for row in rows})
    leaks = Counter()
    roots_by_split: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        before_options = str(row.get("prompt_text") or "").split("Options:", 1)[0]
        label = str(row.get("bounded_choice_target_label") or "").lower()
        lower = before_options.lower()
        if f"target label: {label}" in lower or f"answer: {label}" in lower:
            leaks["target_label"] += 1
        for token in s11269.ROLE_ALIAS_TOKENS:
            if token in before_options:
                leaks["role_alias"] += 1
                break
        if "Evidence note: grounded_" in before_options or (("Evidence note: " in before_options) and "_path_match" in before_options):
            leaks["internal_reason"] += 1
        roots_by_split[str(row.get("split"))].add(str(row.get("root_id")))
    overlaps = {
        "train_validation": sorted(roots_by_split["train"] & roots_by_split["validation"]),
        "train_strict": sorted(roots_by_split["train"] & roots_by_split["strict_eval"]),
        "validation_strict": sorted(roots_by_split["validation"] & roots_by_split["strict_eval"]),
    }
    return {
        "duplicate_row_ids": duplicate_ids,
        "target_label_leak_rows": leaks["target_label"],
        "role_alias_leak_rows": leaks["role_alias"],
        "internal_support_reason_leak_rows": leaks["internal_reason"],
        "root_overlap": overlaps,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    chunks = s11269.index_chunk_text()
    source_rows = load_jsonl(RETRIEVAL_ROWS)
    candidates: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for row in source_rows:
        lang = infer_language(row)
        if lang not in {"python", "rust", "c_cpp", "web_js_ts_html"}:
            blocked.append({"source_row_id": row.get("row_id"), "language_family": lang, "blockers": ["unsupported_or_unknown_language"]})
            continue
        selected = selected_supports(row, chunks)
        if not {"verifier", "changed"}.issubset(selected):
            blocked.append({"source_row_id": row.get("row_id"), "language_family": lang, "blockers": ["missing_local_repo_verifier_or_changed_pair"], "available_roles": sorted(selected)})
            continue
        repo = repo_id(row)
        final_state = target_state(row)
        candidates.append({
            "root_id": f"stage11275::{row['row_id']}",
            "source_row_id": row["row_id"],
            "root_lineage_key": f"{repo}::{row.get('pack_id') or row['row_id']}",
            "repo_family": repo,
            "repo_id": repo,
            "language_family": lang,
            "execution_route": final_state.get("execution_route"),
            "test_selection_route": final_state.get("test_selection_route"),
            "selected": selected,
            "available_roles": sorted(selected),
        })
    root_splits = split_roots(candidates)
    rows: list[dict[str, Any]] = []
    split_rows: list[dict[str, Any]] = []
    for item in candidates:
        split = root_splits[item["root_id"]]
        split_rows.append({k: item[k] for k in ["root_id", "source_row_id", "root_lineage_key", "repo_family", "language_family"]} | {"split": split, "available_roles": item["available_roles"]})
        rows.extend(build_rows(item, split))
    by_split: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_split[row["split"]].append(row)
    train, validation, strict = by_split["train"], by_split["validation"], by_split["strict_eval"]
    write_jsonl(TRAIN_JSONL, train)
    write_jsonl(VALIDATION_JSONL, validation)
    write_jsonl(STRICT_JSONL, strict)
    write_jsonl(BLOCKED_JSONL, blocked)
    write_jsonl(ROOT_SPLITS_JSONL, split_rows)
    audit = audit_rows(rows)
    counts = {
        "source_retrieval_rows": len(source_rows),
        "materialized_roots": len(candidates),
        "blocked_roots": len(blocked),
        "train_rows": len(train),
        "validation_rows": len(validation),
        "strict_rows": len(strict),
        "by_split_language": {name: dict(Counter(r["language_family"] for r in data)) for name, data in [("train", train), ("validation", validation), ("strict_eval", strict)]},
        "by_split_target": {name: dict(Counter(r["semantic_target_value"] for r in data)) for name, data in [("train", train), ("validation", validation), ("strict_eval", strict)]},
        "by_split_candidate_kind": {name: dict(Counter((r.get("standalone_projection_source") or {}).get("candidate_evidence_kind") for r in data)) for name, data in [("train", train), ("validation", validation), ("strict_eval", strict)]},
        "materialized_roots_by_language": dict(Counter(item["language_family"] for item in candidates)),
        "materialized_roots_by_repo_top20": Counter(item["repo_family"] for item in candidates).most_common(20),
    }
    passed = bool(rows) and not audit["duplicate_row_ids"] and not audit["target_label_leak_rows"] and not audit["role_alias_leak_rows"] and not audit["internal_support_reason_leak_rows"] and not any(audit["root_overlap"].values())
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": passed,
        "decision": "direct_retrieval_multilingual_evidence_materialization_ready" if passed else "direct_retrieval_multilingual_evidence_materialization_blocked",
        "counts": counts,
        "audit": audit,
        "quality_gates": {
            "uses_materialized_chunk_text": all((row.get("anti_cheat") or {}).get("source_text_materialized") for row in rows),
            "root_split_disjoint": not any(audit["root_overlap"].values()),
            "unique_row_ids": audit["duplicate_row_ids"] == 0,
            "target_label_not_visible_before_options": audit["target_label_leak_rows"] == 0,
            "role_alias_not_visible_before_options": audit["role_alias_leak_rows"] == 0,
            "internal_support_reasons_not_visible": audit["internal_support_reason_leak_rows"] == 0,
            "has_c_cpp_rust_web_supply": all(counts["materialized_roots_by_language"].get(lang, 0) > 0 for lang in ["c_cpp", "rust", "web_js_ts_html"]),
        },
        "interpretation": {
            "why_this_differs_from_stage11237": "This mines retrieval rows directly for local-repo verifier/change support instead of requiring Stage11237's stricter candidate inventory fields.",
            "claim_limit": "Diagnostic source-supply package; it provides verifier-vs-changed evidence rows, not full maintainer-bundle perspective coverage.",
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
            "retrieval_rows": rel(RETRIEVAL_ROWS),
            "full_context_rows": rel(FULL_CONTEXT_ROWS),
        },
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
