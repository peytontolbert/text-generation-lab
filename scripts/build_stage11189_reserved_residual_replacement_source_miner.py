#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11189
NAME = "stage11189_reserved_residual_replacement_source_miner"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "reserved_residual_replacement_source_miner.json"
WORK_ITEMS_JSONL = OUT_DIR / "replacement_materialization_work_items.jsonl"
CANDIDATES_JSONL = OUT_DIR / "replacement_source_candidates.jsonl"
GAPS_JSONL = OUT_DIR / "replacement_source_gaps.jsonl"

REPLACEMENT_REQUIREMENTS = ARTIFACTS / "stage11188_reserved_residual_validity_reconciliation/reserved_residual_replacement_requirements.jsonl"
RETRIEVAL_ROWS = ARTIFACTS / "strict_long_context_train_ready_plus_audit_v1/retrieval_rows.jsonl"
CONSUMED_TRAIN_ROWS = ARTIFACTS / "stage11178_contract_aware_evidence_rows/contract_aware_evidence_rows.jsonl"
CURRENT_STRICT_ROWS = ARTIFACTS / "stage11146_singleton_strict_quarantine_successor/agentkernel_lite_encdec_strict_eval.jsonl"
CURRENT_VALIDATION_ROWS = ARTIFACTS / "stage11146_singleton_strict_quarantine_successor/agentkernel_lite_encdec_validation.jsonl"
CURRENT_RESERVED_ROWS = ARTIFACTS / "stage11051_successor_residual_support_plus_priority_evidence/reserved_residual_candidates.jsonl"

OLD_EVAL_REPO_FAMILIES = {
    "agentkernel",
    "bddy_website",
    "candle",
    "code_assist",
    "parametergolf",
    "repository_library",
    "tokenizers",
}
ROLE_TARGETS = {
    "candidate_change_surface",
    "symptom_or_call_path_analogue",
    "verifier_and_test_constraint",
}
EXT_LANGUAGE = {
    ".py": "python",
    ".pyi": "python",
    ".rs": "rust",
    ".c": "c_cpp",
    ".cc": "c_cpp",
    ".cpp": "c_cpp",
    ".cxx": "c_cpp",
    ".h": "c_cpp",
    ".hh": "c_cpp",
    ".hpp": "c_cpp",
    ".cu": "c_cpp",
    ".cuh": "c_cpp",
    ".js": "web_js_ts_html",
    ".jsx": "web_js_ts_html",
    ".ts": "web_js_ts_html",
    ".tsx": "web_js_ts_html",
    ".html": "web_js_ts_html",
    ".css": "web_js_ts_html",
    ".scss": "web_js_ts_html",
    ".vue": "web_js_ts_html",
    ".svelte": "web_js_ts_html",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def normalize_repo(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "unknown"


def extract_query_paths(query: str, label: str) -> list[str]:
    pattern = rf"^{re.escape(label)}:\s*(.*)$"
    for line in query.splitlines():
        m = re.match(pattern, line.strip(), flags=re.I)
        if not m:
            continue
        text = m.group(1).strip()
        if not text:
            return []
        return [part.strip() for part in text.split(",") if part.strip()]
    return []


def path_language(path: str) -> str | None:
    lower = path.lower().split("?")[0].split("#")[0]
    for ext, lang in sorted(EXT_LANGUAGE.items(), key=lambda item: len(item[0]), reverse=True):
        if lower.endswith(ext):
            return lang
    return None


def infer_language(row: dict[str, Any]) -> str | None:
    query = str(row.get("query_text") or "")
    paths = extract_query_paths(query, "Changed files")
    paths += [str(score.get("path") or "") for score in row.get("support_scores") or []]
    counts = Counter(lang for path in paths if (lang := path_language(path)))
    if not counts:
        return None
    # Prefer changed-file majority; tie order keeps systems-oriented files from being misclassified by docs/tests.
    priority = {"python": 4, "rust": 3, "c_cpp": 2, "web_js_ts_html": 1}
    return max(counts, key=lambda lang: (counts[lang], priority.get(lang, 0)))


def evidence_paths_by_role(row: dict[str, Any]) -> dict[str, list[str]]:
    roles = {"candidate_change_surface": [], "verifier_and_test_constraint": [], "symptom_or_call_path_analogue": []}
    query = str(row.get("query_text") or "")
    changed = extract_query_paths(query, "Changed files")
    verifiers = extract_query_paths(query, "Verification targets")
    roles["candidate_change_surface"].extend(changed)
    roles["verifier_and_test_constraint"].extend(verifiers)
    for score in row.get("support_scores") or []:
        path = str(score.get("path") or "").strip()
        if not path:
            continue
        role = str(score.get("role") or "")
        reasons = " ".join(str(x) for x in (score.get("support_reasons") or []))
        if role == "seed_change" or "change_path" in reasons:
            roles["candidate_change_surface"].append(path)
        elif role == "verification_constraint" or "verifier" in reasons:
            roles["verifier_and_test_constraint"].append(path)
        elif score.get("source_type") == "local_repo":
            roles["symptom_or_call_path_analogue"].append(path)
        else:
            roles["symptom_or_call_path_analogue"].append(path)
    return {k: sorted(dict.fromkeys(v)) for k, v in roles.items()}


def role_separated(roles: dict[str, list[str]], gold_role: str) -> tuple[bool, list[str]]:
    blockers: list[str] = []
    if gold_role not in ROLE_TARGETS:
        blockers.append("unsupported_gold_role")
    for role in ROLE_TARGETS:
        if not roles.get(role):
            blockers.append(f"missing_{role}")
    candidate = set(roles.get("candidate_change_surface") or [])
    verifier = set(roles.get("verifier_and_test_constraint") or [])
    symptom = set(roles.get("symptom_or_call_path_analogue") or [])
    if candidate & verifier:
        blockers.append("candidate_verifier_path_overlap")
    if gold_role == "symptom_or_call_path_analogue" and symptom & candidate:
        blockers.append("gold_symptom_duplicates_candidate")
    if gold_role == "verifier_and_test_constraint" and not verifier:
        blockers.append("gold_verifier_missing_anchor")
    if gold_role == "candidate_change_surface" and not candidate:
        blockers.append("gold_candidate_missing_anchor")
    return (not blockers, blockers)


def consumed_ids() -> dict[str, set[str]]:
    retrieval_rows = load_jsonl(CONSUMED_TRAIN_ROWS)
    current_rows: list[dict[str, Any]] = []
    for path in [CURRENT_STRICT_ROWS, CURRENT_VALIDATION_ROWS, CURRENT_RESERVED_ROWS]:
        current_rows.extend(load_jsonl(path))
    source_retrieval_ids = {str(row.get("source_retrieval_row_id")) for row in retrieval_rows if row.get("source_retrieval_row_id")}
    source_roots = {str(row.get("root_id")) for row in retrieval_rows if row.get("root_id")}
    root_lineages = {str(row.get("root_lineage_key")) for row in retrieval_rows if row.get("root_lineage_key")}
    repos = {str(row.get("repo_family")) for row in retrieval_rows if row.get("repo_family")}
    for row in current_rows:
        if row.get("source_root_id"):
            source_roots.add(str(row.get("source_root_id")))
        if row.get("root_id"):
            source_roots.add(str(row.get("root_id")))
        if row.get("root_lineage_key"):
            root_lineages.add(str(row.get("root_lineage_key")))
        if row.get("repo_family"):
            repos.add(str(row.get("repo_family")))
    repos |= OLD_EVAL_REPO_FAMILIES
    return {"source_retrieval_ids": source_retrieval_ids, "source_roots": source_roots, "root_lineages": root_lineages, "repos": repos}


def retrieval_root_id(row: dict[str, Any]) -> str:
    meta = row.get("metadata") or {}
    return f"retrieval::{row.get('pack_id')}::{meta.get('query_index')}"


def root_lineage(row: dict[str, Any]) -> str:
    meta = row.get("metadata") or {}
    return f"{normalize_repo(str(meta.get('canonical_name') or 'unknown'))}::{row.get('pack_id')}"


def candidate_from_row(row: dict[str, Any], gold_role: str) -> dict[str, Any]:
    meta = row.get("metadata") or {}
    repo = normalize_repo(str(meta.get("canonical_name") or "unknown"))
    roles = evidence_paths_by_role(row)
    lang = infer_language(row)
    ok, blockers = role_separated(roles, gold_role)
    query_index = meta.get("query_index")
    source_root = retrieval_root_id(row)
    return {
        "source_row_id": row.get("row_id"),
        "source_root_id": source_root,
        "root_lineage_key": root_lineage(row),
        "repo_family": repo,
        "repo_id": meta.get("canonical_name") or repo,
        "pack_id": row.get("pack_id"),
        "query_index": query_index,
        "language_family": lang,
        "target_task_type": "evidence_citation",
        "target_gold_value": gold_role,
        "role_paths": roles,
        "role_path_counts": {k: len(v) for k, v in roles.items()},
        "selected_test_anchor": bool(extract_query_paths(str(row.get("query_text") or ""), "Verification targets")),
        "verifier_anchor": bool(roles.get("verifier_and_test_constraint")),
        "quality_score": float(row.get("span_ratio") or 0.0) + (0.2 if row.get("long_join_positive") else 0.0),
        "admission_ready": ok and lang is not None,
        "blockers": blockers + ([] if lang else ["language_not_inferred"]),
        "source_family_id": "strict_long_context_train_ready_plus_audit_v1",
    }


def make_work_item(candidate: dict[str, Any], requirement: dict[str, Any], slot_index: int) -> dict[str, Any]:
    role = candidate["target_gold_value"]
    role_requirements = {
        "candidate_change_surface": [
            "Candidate surface evidence must be the unique strongest support; verifier text must not independently argue that candidate surface is correct.",
            "Include plausible verifier/test and symptom/call-path distractors that are visibly less specific than the candidate surface evidence.",
        ],
        "symptom_or_call_path_analogue": [
            "Expose symptom/call-path/trace evidence as a distinct visible fact, not the same path/span as candidate_change_surface.",
            "If source material cannot separate symptom/call-path from candidate surface, block the row instead of forcing gold.",
        ],
        "verifier_and_test_constraint": [
            "Expose selected test, verifier route, assertion, command, or transition as independent evidence.",
            "Candidate surface must remain a plausible but wrong distractor, not a duplicate of verifier evidence.",
        ],
    }[role]
    return {
        "work_item_id": f"stage11189::{candidate['source_root_id']}::replacement_slot_{slot_index}::{role}",
        "stage": STAGE,
        "admit_role": "reserved_residual_replacement_candidate",
        "replacement_for_blocked_row_id": requirement.get("blocked_row_id"),
        "source_row_id": candidate["source_row_id"],
        "source_root_id": candidate["source_root_id"],
        "root_lineage_key": candidate["root_lineage_key"],
        "repo_family": candidate["repo_family"],
        "repo_id": candidate["repo_id"],
        "language_family": candidate["language_family"],
        "pack_id": candidate["pack_id"],
        "query_index": candidate["query_index"],
        "source_family_id": candidate["source_family_id"],
        "target_task_type": "evidence_citation",
        "target_gold_value": role,
        "selected_test_anchor": candidate["selected_test_anchor"],
        "verifier_anchor": candidate["verifier_anchor"],
        "quality_score": candidate["quality_score"],
        "role_paths": candidate["role_paths"],
        "required_outputs": [
            "One bounded evidence_citation strict-candidate row with opaque labels and deterministic/recorded option shuffle.",
            "Visible evidence ledger with separate candidate, verifier/test, symptom/call-path, and nearby context entries.",
            "Machine-readable option mapping, semantic target value, target label, root_id, source_row_id, and anti-cheat card.",
            "No target label, target role, or target path leakage before options.",
        ],
        "role_specific_requirements": role_requirements,
        "replacement_contract": requirement.get("replacement_contract"),
        "quarantine_reasons_replaced": requirement.get("quarantine_reasons"),
        "train_eval_policy": "strict_candidate_only_until materialized row passes review and is kept out of training support",
    }


def main() -> None:
    requirements = load_jsonl(REPLACEMENT_REQUIREMENTS)
    retrieval_rows = load_jsonl(RETRIEVAL_ROWS)
    consumed = consumed_ids()

    needed = Counter((r.get("language_family"), r.get("target_gold_value")) for r in requirements)
    candidates: list[dict[str, Any]] = []
    blocked_candidates: list[dict[str, Any]] = []
    for req in requirements:
        role = str(req.get("target_gold_value") or "")
        for row in retrieval_rows:
            cand = candidate_from_row(row, role)
            if cand["source_row_id"] in consumed["source_retrieval_ids"]:
                cand["blockers"].append("source_retrieval_row_already_used_in_train_support")
            if cand["source_root_id"] in consumed["source_roots"] or cand["root_lineage_key"] in consumed["root_lineages"]:
                cand["blockers"].append("root_or_lineage_already_consumed")
            if cand["repo_family"] in consumed["repos"]:
                cand["blockers"].append("repo_family_already_consumed_or_quarantined")
            cand["matches_requirement_language"] = cand.get("language_family") == req.get("language_family")
            cand["matches_requirement_role"] = cand.get("target_gold_value") == req.get("target_gold_value")
            if cand["matches_requirement_language"] and cand["matches_requirement_role"]:
                if cand["admission_ready"] and not cand["blockers"]:
                    candidates.append(cand)
                else:
                    blocked_candidates.append(cand)

    by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for cand in candidates:
        by_key[(str(cand["language_family"]), str(cand["target_gold_value"]))].append(cand)
    for values in by_key.values():
        values.sort(key=lambda c: (c["quality_score"], c["selected_test_anchor"], c["verifier_anchor"], c["repo_family"]), reverse=True)

    selected: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    used_roots: set[str] = set()
    used_repos: set[str] = set()
    slot = 0
    for req in requirements:
        key = (str(req.get("language_family")), str(req.get("target_gold_value")))
        chosen = None
        for cand in by_key.get(key, []):
            if cand["source_root_id"] in used_roots or cand["repo_family"] in used_repos:
                continue
            chosen = cand
            break
        if chosen is None:
            for cand in by_key.get(key, []):
                if cand["source_root_id"] not in used_roots:
                    chosen = cand
                    break
        if chosen is None:
            gaps.append({
                "blocked_row_id": req.get("blocked_row_id"),
                "language_family": req.get("language_family"),
                "target_gold_value": req.get("target_gold_value"),
                "repo_family": req.get("repo_family"),
                "reason": "no_root_disjoint_role_separated_source_candidate_available",
                "blocked_candidate_reason_counts": dict(Counter(reason for c in blocked_candidates if c.get("language_family") == req.get("language_family") and c.get("target_gold_value") == req.get("target_gold_value") for reason in c.get("blockers", []))),
            })
            continue
        slot += 1
        selected.append(make_work_item(chosen, req, slot))
        used_roots.add(chosen["source_root_id"])
        used_repos.add(chosen["repo_family"])

    selected_counts = Counter((w["language_family"], w["target_gold_value"]) for w in selected)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": len(gaps) == 0,
        "decision": "replacement_materialization_queue_ready" if not gaps else "replacement_source_supply_gap_remains",
        "source_artifacts": {
            "replacement_requirements": rel(REPLACEMENT_REQUIREMENTS),
            "retrieval_rows": rel(RETRIEVAL_ROWS),
            "consumed_train_rows": rel(CONSUMED_TRAIN_ROWS),
            "current_strict_rows": rel(CURRENT_STRICT_ROWS),
            "current_validation_rows": rel(CURRENT_VALIDATION_ROWS),
            "current_reserved_rows": rel(CURRENT_RESERVED_ROWS),
        },
        "counts": {
            "requirements": len(requirements),
            "selected_work_items": len(selected),
            "gaps": len(gaps),
            "retrieval_rows_scanned": len(retrieval_rows),
            "eligible_candidate_instances": len(candidates),
            "blocked_candidate_instances": len(blocked_candidates),
            "needed_by_language_role": {f"{k[0]}::{k[1]}": v for k, v in sorted(needed.items())},
            "selected_by_language_role": {f"{k[0]}::{k[1]}": v for k, v in sorted(selected_counts.items())},
            "selected_by_repo": dict(sorted(Counter(w["repo_family"] for w in selected).items())),
        },
        "anti_cheat_policy": {
            "exclude_consumed_source_retrieval_rows": True,
            "exclude_consumed_roots_and_root_lineages": True,
            "exclude_current_quarantined_or_eval_repo_families": sorted(OLD_EVAL_REPO_FAMILIES),
            "require_role_separated_candidate_verifier_symptom_paths": True,
            "selected_items_are_not_train_rows": True,
        },
        "next_best_step": "Materialize selected work items into strict-candidate evidence rows and run a stage11175-style anti-cheat/admission audit before any training or comparison.",
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "work_items_jsonl": rel(WORK_ITEMS_JSONL),
            "candidates_jsonl": rel(CANDIDATES_JSONL),
            "gaps_jsonl": rel(GAPS_JSONL),
        },
    }
    write_json(SUMMARY_JSON, summary)
    write_jsonl(WORK_ITEMS_JSONL, selected)
    write_jsonl(CANDIDATES_JSONL, candidates[:5000])
    write_jsonl(GAPS_JSONL, gaps)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
