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
STAGE = 11295
NAME = "stage11295_fact_rich_verifier_materialization"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "fact_rich_verifier_materialization.json"
TRAIN_JSONL = OUT_DIR / "fact_rich_verifier_train_rows.jsonl"
VALIDATION_JSONL = OUT_DIR / "fact_rich_verifier_validation_rows.jsonl"
STRICT_JSONL = OUT_DIR / "fact_rich_verifier_strict_rows.jsonl"
BLOCKED_JSONL = OUT_DIR / "fact_rich_verifier_blocked_roots.jsonl"

SOURCE_DIR = ARTIFACTS / "strict_long_context_train_ready_plus_audit_v1"
RETRIEVAL_ROWS = SOURCE_DIR / "retrieval_rows.jsonl"
FULL_CONTEXT_ROWS = SOURCE_DIR / "full_context_rows.jsonl"

CODE_EXTS = (".py", ".rs", ".cpp", ".cc", ".cxx", ".c", ".h", ".hpp", ".cu", ".cuh", ".js", ".ts", ".tsx", ".jsx", ".html", ".css")
TEST_HINTS = ("test", "tests/", "_test.", "spec.", ".spec", "assert", "expect(", "pytest", "unittest", "should_panic", "assert_eq!", "ASSERT_", "EXPECT_")
ASSERT_PAT = re.compile(r"\b(assert|pytest\.raises|unittest|expect\(|assert_eq!|assert_ne!|should_panic|ASSERT_[A-Z_]+|EXPECT_[A-Z_]+|REQUIRE\()", re.I)
LOW_SIGNAL_CHANGE = ("readme", "docs/", "doc/", "test", "tests/", "benchmark", "bench", "example", "examples/")
OPTION_VALUES = ["candidate_change_surface", "verifier_and_test_constraint", "symptom_or_call_path_analogue", "background_context"]


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def stable_hash(text: str, n: int = 12) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:n]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def full_context_chunks() -> dict[str, dict[str, Any]]:
    chunks: dict[str, dict[str, Any]] = {}
    for row in load_jsonl(FULL_CONTEXT_ROWS):
        for chunk in row.get("context_rows") or []:
            cid = str(chunk.get("chunk_id") or "")
            if cid and cid not in chunks:
                chunks[cid] = chunk
    return chunks


def infer_language(text: str) -> str:
    low = text.lower()
    if any(x in low for x in [".rs", "cargo", " rust", "assert_eq!"]):
        return "rust"
    if any(x in low for x in [".cpp", ".cc", ".cxx", ".hpp", ".cu", ".cuh", " c++", "cmake", "assert_"]):
        return "c_cpp"
    if any(x in low for x in [".js", ".ts", ".tsx", ".jsx", ".html", "javascript", "typescript", "expect("]):
        return "web_js_ts_html"
    if ".py" in low or "python" in low or "pytest" in low or "unittest" in low:
        return "python"
    return "unknown"


def repo_id(row: dict[str, Any]) -> str:
    metadata = row.get("metadata") or {}
    value = str(metadata.get("canonical_name") or "unknown")
    return value.replace("/", "_")


def query_index(row: dict[str, Any]) -> str:
    metadata = row.get("metadata") or {}
    return str(metadata.get("query_index") or row.get("row_id") or stable_hash(json.dumps(row, sort_keys=True)))


def norm_path(path: str) -> str:
    return str(path or "").replace("\\", "/")


def rich_verifier_score(chunk: dict[str, Any]) -> int:
    path = norm_path(str(chunk.get("path") or chunk.get("doc_id") or ""))
    text = str(chunk.get("text") or "")
    score = 0
    if any(h.lower() in path.lower() for h in TEST_HINTS):
        score += 2
    if ASSERT_PAT.search(text):
        score += 4
    if any(marker in text for marker in ["def test_", "class Test", "TEST(", "TEST_F(", "it(", "describe("]):
        score += 2
    if len(text) >= 300:
        score += 1
    return score


def changed_score(chunk: dict[str, Any]) -> int:
    path = norm_path(str(chunk.get("path") or chunk.get("doc_id") or "")).lower()
    text = str(chunk.get("text") or "")
    score = 0
    if path.endswith(CODE_EXTS):
        score += 3
    if not any(part in path for part in LOW_SIGNAL_CHANGE):
        score += 2
    if re.search(r"def |class |function |=>|::|#include|impl |pub fn|export ", text):
        score += 1
    return score


def excerpt_around_fact(text: str, max_chars: int = 900) -> str:
    text = str(text or "").strip()
    if len(text) <= max_chars:
        return text
    match = ASSERT_PAT.search(text)
    if not match:
        positions = [text.find(marker) for marker in ["def test_", "class Test", "TEST(", "TEST_F(", "it(", "describe("]]
        positions = [pos for pos in positions if pos >= 0]
        if positions:
            class _Match:
                def __init__(self, pos: int) -> None:
                    self._pos = pos
                def start(self) -> int:
                    return self._pos
            match = _Match(min(positions))
    if not match:
        return text[:max_chars].rstrip()
    start = max(0, match.start() - max_chars // 3)
    end = min(len(text), start + max_chars)
    return text[start:end].strip()


def options_for(seed: str) -> list[dict[str, str]]:
    values = sorted(OPTION_VALUES, key=lambda value: stable_hash(f"{seed}::{value}"))
    return [{"label": "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[i], "value": value} for i, value in enumerate(values)]


def make_prompt(language: str, evidence_text: str, options: list[dict[str, str]]) -> str:
    return "\n".join([
        f"Language: {language}",
        "Perspective: evidence_citation",
        "Decision objective: choose the semantic role of the candidate evidence item.",
        "The verifier/test option is correct only when the candidate includes concrete test, assertion, command-result, or expected-outcome evidence.",
        "The candidate-change option is correct only when the candidate is the implementation/config/code surface being changed.",
        "",
        "Candidate evidence item:",
        evidence_text,
        "",
        "Options:",
        *[f"{opt['label']}. {opt['value']}" for opt in options],
        "Answer:",
    ])


def evidence_text(kind: str, chunk: dict[str, Any]) -> str:
    path = norm_path(str(chunk.get("path") or chunk.get("doc_id") or "unknown"))
    excerpt = excerpt_around_fact(str(chunk.get("text") or ""))
    return "\n".join([
        f"Source path: {path}",
        "Evidence note: fact-rich source excerpt.",
        "Excerpt:",
        excerpt,
    ])


def select_chunks(row: dict[str, Any], chunks: dict[str, dict[str, Any]]) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[str]]:
    reasons: list[str] = []
    verifier: list[dict[str, Any]] = []
    changed: list[dict[str, Any]] = []
    for score in row.get("support_scores") or []:
        cid = str(score.get("chunk_id") or "")
        chunk = chunks.get(cid)
        if not chunk:
            continue
        if str(score.get("source_type") or chunk.get("source_type") or "") != "local_repo":
            continue
        role = str(score.get("role") or "")
        merged = {**chunk, "support_score": score}
        if role == "verification_constraint":
            verifier.append(merged)
        elif role == "seed_change":
            changed.append(merged)
    verifier = [c for c in verifier if rich_verifier_score(c) >= 5]
    changed = [c for c in changed if changed_score(c) >= 5]
    if not verifier:
        reasons.append("missing_fact_rich_verifier_chunk")
    if not changed:
        reasons.append("missing_implementation_changed_chunk")
    verifier.sort(key=lambda c: (-rich_verifier_score(c), norm_path(str(c.get("path") or ""))))
    changed.sort(key=lambda c: (-changed_score(c), norm_path(str(c.get("path") or ""))))
    return (verifier[0] if verifier else None), (changed[0] if changed else None), reasons


def split_items(items: list[dict[str, Any]]) -> dict[str, str]:
    by_lang: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        by_lang[item["language_family"]].append(item)
    out: dict[str, str] = {}
    for _lang, vals in by_lang.items():
        vals = sorted(vals, key=lambda x: (x["repo_family"], x["root_id"]))
        n = len(vals)
        val_n = max(1, round(n * 0.12)) if n >= 6 else (1 if n >= 3 else 0)
        strict_n = max(1, round(n * 0.12)) if n >= 6 else (1 if n >= 4 else 0)
        for idx, item in enumerate(vals):
            if idx < strict_n:
                split = "strict_eval"
            elif idx < strict_n + val_n:
                split = "validation"
            else:
                split = "train"
            out[item["root_id"]] = split
    return out


def build_row(item: dict[str, Any], kind: str, split: str) -> dict[str, Any]:
    chunk = item[kind]
    target = "verifier_and_test_constraint" if kind == "verifier" else "candidate_change_surface"
    options = options_for(f"{item['root_id']}::{kind}::stage11295")
    target_label = next(opt["label"] for opt in options if opt["value"] == target)
    text = evidence_text(kind, chunk)
    prompt = make_prompt(item["language_family"], text, options)
    return {
        "row_id": f"stage11295::{item['root_id']}::{kind}",
        "root_id": item["root_id"],
        "source_root_id": item["source_row_id"],
        "root_lineage_key": item["root_lineage_key"],
        "source_row_id": item["source_row_id"],
        "source_family_id": "strict_long_context_train_ready_plus_audit_v1",
        "repo_family": item["repo_family"],
        "repo_id": item["repo_id"],
        "language_family": item["language_family"],
        "task_type": "evidence_citation",
        "surface": "maintainer_fact_rich_verifier_vs_changed_evidence_citation",
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
        "preservation_exempt": split == "train",
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "root_split_isolation_required": True,
            "fact_rich_verifier_required": kind == "verifier",
            "implementation_changed_required": kind == "changed",
            "target_label_not_visible_before_options": True,
        },
        "standalone_projection_source": {
            "gold_label": target_label,
            "gold_value": target,
            "opaque_options": options,
            "candidate_evidence_kind": kind,
            "candidate_evidence_text": text,
            "source_chunk_id": chunk.get("chunk_id"),
            "source_chunk_path": norm_path(str(chunk.get("path") or chunk.get("doc_id") or "")),
            "source_chunk_role": (chunk.get("support_score") or {}).get("role"),
            "source_chunk_support_reasons": (chunk.get("support_score") or {}).get("support_reasons") or [],
            "fact_rich_verifier_score": rich_verifier_score(chunk) if kind == "verifier" else None,
            "implementation_changed_score": changed_score(chunk) if kind == "changed" else None,
            "contrast_family": "candidate_change_surface_vs_verifier_and_test_constraint",
            "source_inventory_stage": "stage11295_fact_rich_verifier_materialization",
        },
    }


def audit(rows_by_split: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    all_rows = [row for rows in rows_by_split.values() for row in rows]
    leaks = Counter()
    for row in all_rows:
        before = str(row.get("input_text") or "").split("Options:", 1)[0]
        if str(row.get("semantic_target_value") or "") in before:
            leaks["semantic_target_before_options"] += 1
        label = str(row.get("bounded_choice_target_label") or "")
        if f"\n{label}." in before or f" {label}. " in before:
            leaks["target_label_before_options"] += 1
    root_sets = {split: {str(row.get("root_id")) for row in rows} for split, rows in rows_by_split.items()}
    root_balance = {}
    for split, rows in rows_by_split.items():
        by_root: dict[str, Counter[str]] = defaultdict(Counter)
        for row in rows:
            by_root[str(row.get("root_id"))][str((row.get("standalone_projection_source") or {}).get("candidate_evidence_kind"))] += 1
        root_balance[split] = {
            "roots": len(by_root),
            "unpaired_roots": sorted(root for root, counts in by_root.items() if counts.get("changed") != 1 or counts.get("verifier") != 1),
        }
    return {
        "duplicate_row_ids": len(all_rows) - len({str(row.get("row_id")) for row in all_rows}),
        "leaks": dict(leaks),
        "root_overlap": {
            "train_validation": sorted(root_sets["train"] & root_sets["validation"]),
            "train_strict": sorted(root_sets["train"] & root_sets["strict_eval"]),
            "validation_strict": sorted(root_sets["validation"] & root_sets["strict_eval"]),
        },
        "root_balance": root_balance,
    }


def counts(rows_by_split: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    out = {}
    for split, rows in rows_by_split.items():
        out[split] = {
            "rows": len(rows),
            "roots": len({str(row.get("root_id")) for row in rows}),
            "by_language": dict(Counter(str(row.get("language_family")) for row in rows)),
            "by_target": dict(Counter(str(row.get("semantic_target_value")) for row in rows)),
            "by_repo_top20": Counter(str(row.get("repo_family")) for row in rows).most_common(20),
        }
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    chunks = full_context_chunks()
    items: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    seen_roots: set[str] = set()
    for row in load_jsonl(RETRIEVAL_ROWS):
        verifier, changed, reasons = select_chunks(row, chunks)
        rid = str(row.get("row_id") or "")
        repo = repo_id(row)
        root_id = f"stage11295::{repo}::{query_index(row)}::{stable_hash(rid, 8)}"
        if root_id in seen_roots:
            continue
        seen_roots.add(root_id)
        lang = infer_language((row.get("query_text") or "") + " " + json.dumps(row.get("target_text") or {}))
        if not verifier or not changed or lang == "unknown":
            blocked.append({
                "source_row_id": rid,
                "repo_family": repo,
                "language_family": lang,
                "blockers": reasons + (["unknown_language"] if lang == "unknown" else []),
            })
            continue
        items.append({
            "root_id": root_id,
            "source_row_id": rid,
            "root_lineage_key": f"{repo}::{query_index(row)}",
            "repo_family": repo,
            "repo_id": repo,
            "language_family": lang,
            "verifier": verifier,
            "changed": changed,
        })
    splits = split_items(items)
    rows_by_split = {"train": [], "validation": [], "strict_eval": []}
    for item in items:
        split = splits[item["root_id"]]
        rows_by_split[split].append(build_row(item, "changed", split))
        rows_by_split[split].append(build_row(item, "verifier", split))
    audit_card = audit(rows_by_split)
    count_card = counts(rows_by_split)
    passed = (
        audit_card["duplicate_row_ids"] == 0
        and not audit_card["leaks"]
        and not any(audit_card["root_overlap"].values())
        and all(not v["unpaired_roots"] for v in audit_card["root_balance"].values())
        and count_card["train"]["roots"] >= 30
        and count_card["validation"]["roots"] >= 4
        and count_card["strict_eval"]["roots"] >= 4
    )
    write_jsonl(TRAIN_JSONL, rows_by_split["train"])
    write_jsonl(VALIDATION_JSONL, rows_by_split["validation"])
    write_jsonl(STRICT_JSONL, rows_by_split["strict_eval"])
    write_jsonl(BLOCKED_JSONL, blocked)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": passed,
        "decision": "fact_rich_verifier_materialization_ready" if passed else "fact_rich_verifier_materialization_blocked",
        "counts": count_card,
        "audit": audit_card,
        "blocked_count": len(blocked),
        "blocked_by_reason": dict(Counter(reason for row in blocked for reason in row["blockers"])),
        "rationale": "Join retrieval rows to full-context source chunks and admit only verifier evidence with concrete assertion/test facts plus implementation-like changed-source negatives from the same root.",
        "outputs": {
            "train_jsonl": rel(TRAIN_JSONL),
            "validation_jsonl": rel(VALIDATION_JSONL),
            "strict_jsonl": rel(STRICT_JSONL),
            "blocked_jsonl": rel(BLOCKED_JSONL),
            "summary_json": rel(SUMMARY_JSON),
        },
        "source_artifacts": {
            "retrieval_rows": rel(RETRIEVAL_ROWS),
            "full_context_rows": rel(FULL_CONTEXT_ROWS),
            "stage11294_decision": "runs/local/artifacts/stage11294_paired_candidate_item_contrast_decision/paired_candidate_item_contrast_decision.json",
        },
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
