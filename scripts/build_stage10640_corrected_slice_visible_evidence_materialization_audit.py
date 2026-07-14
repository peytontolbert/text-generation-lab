#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
STAGE = 10640
NAME = "stage10640_corrected_slice_visible_evidence_materialization_audit"
STRICT_ROWS_PATH = (
    ROOT
    / "runs/local/artifacts/stage10635_repaired_long_context_successor_package_permuted"
    / "repaired_long_context_successor_package_permuted_strict_rows.jsonl"
)
SPANS_PATH = Path("/arxiv/TOLBERT_BRAIN/data/repos/spans_repos.jsonl")
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "corrected_slice_visible_evidence_materialization_audit.json"
PREVIEW_ROWS_JSONL = OUT_DIR / "corrected_slice_visible_evidence_materialized_preview_rows.jsonl"

HANDLE_RE = re.compile(r"^(?P<kind>repo|localchunk|paper|dataset|localrepochunk)_(?P<body>.+)_(?P<slot>\d+)_(?P<hash>[0-9a-f]{10})$")
MAX_TEXT = 700


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def normalize(text: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", str(text).lower())).strip("_")


def short_text(text: str, limit: int = MAX_TEXT) -> str:
    clean = str(text or "").strip()
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."


def build_workspace_index() -> dict[str, str]:
    idx: dict[str, str] = {}
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT).as_posix()
        idx[normalize(rel)] = rel
    return idx


def parse_handle(value: str, repo_id: str) -> dict[str, Any]:
    m = HANDLE_RE.match(str(value))
    repo_norm = normalize(repo_id)
    if not m:
        return {
            "handle": value,
            "kind": "unknown",
            "repo_norm": repo_norm,
            "body_norm": normalize(value),
            "slot": None,
            "match_norms": [],
        }
    kind = m.group("kind")
    body = m.group("body")
    body_norm = normalize(body)
    match_norms: list[str] = []
    if kind == "repo":
        match_norms.append(body_norm)
        if body_norm.startswith(repo_norm + "_"):
            one = body_norm[len(repo_norm) + 1 :]
            match_norms.append(one)
            if one.startswith(repo_norm + "_"):
                match_norms.append(one[len(repo_norm) + 1 :])
    elif kind in {"localchunk", "localrepochunk"}:
        match_norms.append(body_norm)
        prefixes = [
            "agentkernel_seq2seq_text_lab_",
            "agentkernel_",
            "parametergolf_",
            "peytontolbert_parameter_golf_",
            repo_norm + "_",
        ]
        for prefix in prefixes:
            if body_norm.startswith(prefix):
                match_norms.append(body_norm[len(prefix) :])
    else:
        match_norms.append(body_norm)
    match_norms = [item for item in dict.fromkeys(match_norms) if item]
    return {
        "handle": value,
        "kind": kind,
        "repo_norm": repo_norm,
        "body_norm": body_norm,
        "slot": int(m.group("slot")),
        "match_norms": match_norms,
    }


def looks_like_match(path_norm: str, handle_norms: list[str]) -> tuple[int, str] | None:
    best: tuple[int, str] | None = None
    for cand in handle_norms:
        score = -1
        if path_norm == cand:
            score = 3000 + len(cand)
        elif path_norm.endswith(cand):
            score = 2000 + len(cand)
        elif cand.endswith(path_norm):
            score = 1500 + len(path_norm)
        elif all(part in path_norm for part in cand.split("_")[-3:]):
            score = 500 + len(cand)
        if best is None or score > best[0]:
            if score >= 0:
                best = (score, cand)
    return best


def resolve_repo_handles(repo_handles: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    resolved: dict[str, dict[str, Any]] = {}
    if not SPANS_PATH.exists():
        return resolved
    with SPANS_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            obj = json.loads(line)
            span_id = str(obj.get("span_id") or "")
            if ":" not in span_id:
                continue
            corpus, path_text = span_id.split(":", 1)
            corpus_norm = normalize(corpus)
            if corpus_norm not in repo_handles:
                continue
            path_norm = normalize(path_text)
            meta = obj.get("meta") if isinstance(obj.get("meta"), dict) else {}
            for item in repo_handles[corpus_norm]:
                key = item["handle"]
                if key in resolved:
                    continue
                match = looks_like_match(path_norm, item["match_norms"])
                if not match:
                    continue
                resolved[key] = {
                    "resolution_kind": "repo_span_text",
                    "span_id": span_id,
                    "source_id": str(obj.get("source_id") or ""),
                    "path": path_text,
                    "corpus": corpus,
                    "meta": meta,
                    "matched_norm": match[1],
                    "text": short_text(obj.get("text") or ""),
                }
    return resolved


def resolve_local_handle(info: dict[str, Any], workspace_index: dict[str, str]) -> dict[str, Any] | None:
    best_path: str | None = None
    best_score = -1
    for cand in info["match_norms"]:
        for path_norm, rel in workspace_index.items():
            score = -1
            if path_norm == cand:
                score = 3000 + len(cand)
            elif path_norm.endswith(cand):
                score = 2000 + len(cand)
            elif cand.endswith(path_norm):
                score = 1500 + len(path_norm)
            if score > best_score:
                best_score = score
                best_path = rel
    if not best_path:
        return None
    text = short_text((ROOT / best_path).read_text(encoding="utf-8", errors="ignore"))
    return {
        "resolution_kind": "workspace_file_text",
        "path": best_path,
        "matched_norm": normalize(best_path),
        "text": text,
    }


def fallback_summary(info: dict[str, Any]) -> dict[str, Any]:
    kind = info["kind"]
    body = info["body_norm"]
    return {
        "resolution_kind": f"{kind}_summary_only",
        "summary": body,
        "text": "",
    }


def visible_card(label: str, handle: str, resolved: dict[str, Any]) -> dict[str, Any]:
    card = {
        "label": label,
        "handle": handle,
        "resolution_kind": resolved.get("resolution_kind"),
    }
    for key in ["path", "corpus", "span_id", "source_id", "matched_norm", "summary", "text", "meta"]:
        if key in resolved:
            card[key] = resolved[key]
    return card


def prompt_from_row(row: dict[str, Any], cards: list[dict[str, Any]]) -> str:
    lines = [
        f"Repository: {row.get('repo_id')}",
        f"Query index: {str(row.get('root_id') or '').split('::q')[-1].split('::')[0]}",
        f"Changed files: {str(row.get('input_text') or '').split('Changed files: ', 1)[1].splitlines()[0] if 'Changed files: ' in str(row.get('input_text') or '') else ''}",
        f"Verification targets: {str(row.get('input_text') or '').split('Verification targets: ', 1)[1].splitlines()[0] if 'Verification targets: ' in str(row.get('input_text') or '') else ''}",
        f"Key symbols: {str(row.get('input_text') or '').split('Key symbols: ', 1)[1].splitlines()[0] if 'Key symbols: ' in str(row.get('input_text') or '') else ''}",
        "Task: Choose the decisive visible evidence card that best justifies the maintenance decision.",
        "",
        "Visible evidence cards:",
    ]
    for card in cards:
        head = f"{card['label']}: "
        if card["resolution_kind"] == "repo_span_text":
            lines.append(head + f"[repo_span {card.get('corpus')}::{card.get('path')}]")
            if card.get("text"):
                lines.append(short_text(card["text"], 260))
        elif card["resolution_kind"] == "workspace_file_text":
            lines.append(head + f"[workspace::{card.get('path')}]")
            if card.get("text"):
                lines.append(short_text(card["text"], 260))
        else:
            lines.append(head + f"[{card['resolution_kind']}] {card.get('summary') or card.get('handle')}")
        lines.append("")
    lines.append("Return only the option label.")
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    strict_rows = load_jsonl(STRICT_ROWS_PATH)
    workspace_index = build_workspace_index()

    repo_handle_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    parsed_by_handle: dict[str, dict[str, Any]] = {}
    for row in strict_rows:
        repo_id = str(row.get("repo_id") or "")
        for option in row.get("candidate_options") or []:
            handle = str(option.get("value") or "")
            info = parse_handle(handle, repo_id)
            parsed_by_handle[handle] = info
            if info["kind"] == "repo":
                repo_handle_groups[info["repo_norm"]].append(info)

    resolved_repo = resolve_repo_handles(repo_handle_groups)

    preview_rows: list[dict[str, Any]] = []
    metrics = Counter()
    lang_metrics: dict[str, Counter[str]] = defaultdict(Counter)

    for row in strict_rows:
        cards: list[dict[str, Any]] = []
        gold_label = str(row.get("target_text") or "")
        gold_handle = ""
        gold_resolved_real = False
        all_repo_candidates_resolved = True
        any_real_text = False

        for option in row.get("candidate_options") or []:
            label = str(option.get("label") or "")
            handle = str(option.get("value") or "")
            if label == gold_label:
                gold_handle = handle
            info = parsed_by_handle[handle]
            resolved = resolved_repo.get(handle)
            if resolved is None and info["kind"] in {"localchunk", "localrepochunk"}:
                resolved = resolve_local_handle(info, workspace_index)
            if resolved is None:
                resolved = fallback_summary(info)
            if resolved["resolution_kind"] in {"repo_span_text", "workspace_file_text"} and resolved.get("text"):
                any_real_text = True
            if info["kind"] == "repo" and resolved["resolution_kind"] != "repo_span_text":
                all_repo_candidates_resolved = False
            if label == gold_label and resolved["resolution_kind"] == "repo_span_text":
                gold_resolved_real = True
            cards.append(visible_card(label, handle, resolved))

        lang = str(row.get("language_family") or "unknown")
        metrics["rows"] += 1
        lang_metrics[lang]["rows"] += 1
        if gold_resolved_real:
            metrics["rows_with_gold_repo_span_text"] += 1
            lang_metrics[lang]["rows_with_gold_repo_span_text"] += 1
        if all_repo_candidates_resolved:
            metrics["rows_with_all_repo_candidates_resolved"] += 1
            lang_metrics[lang]["rows_with_all_repo_candidates_resolved"] += 1
        if any_real_text:
            metrics["rows_with_any_real_text_card"] += 1
            lang_metrics[lang]["rows_with_any_real_text_card"] += 1

        preview_rows.append(
            {
                "row_id": row["row_id"],
                "repo_id": row.get("repo_id"),
                "language_family": lang,
                "target_text": gold_label,
                "gold_handle": gold_handle,
                "gold_resolution_kind": next((card["resolution_kind"] for card in cards if card["label"] == gold_label), None),
                "cards": cards,
                "visible_prompt_text": prompt_from_row(row, cards),
                "materialization_summary": {
                    "gold_resolved_real_repo_span": gold_resolved_real,
                    "all_repo_candidates_resolved": all_repo_candidates_resolved,
                    "any_real_text_card": any_real_text,
                },
            }
        )

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "partial_real_visible_evidence_recovery_available",
        "inputs": {
            "strict_rows": str(STRICT_ROWS_PATH),
            "spans_repos": str(SPANS_PATH),
        },
        "metrics": {
            **metrics,
            "by_language": {lang: dict(sorted(counter.items())) for lang, counter in sorted(lang_metrics.items())},
        },
        "claim_boundary": [
            "This stage does not score models and does not upgrade any benchmark claim.",
            "It tests whether the corrected strict slice can be partially upgraded from opaque handles to visible evidence cards using local repo span recovery.",
            "Recovered repo-span text is stronger than opaque handles, but the resulting rows still need expert review before any maintainer-grade promotion.",
        ],
        "interpretation": [
            "If gold repo candidates resolve to real span text, the strict slice can be rebuilt into a more honest evidence-selection task without inventing new shells.",
            "If many distractors remain summary-only, the slice is still transitional rather than fully maintainer-grade.",
            "This bridge is most useful for repo-backed evidence candidates; paper/dataset/localchunk distractors remain lower-fidelity until separately materialized or replaced.",
        ],
        "next_best_step": [
            "Review the preview rows and keep only those where the gold evidence and the strongest distractors both have real visible text or clear visible summaries.",
            "Build a filtered maintainer-visible strict successor from the recovered rows, and exclude rows whose candidate competition still depends too heavily on summary-only distractors.",
            "Compare 100M and Gemma only after that filtered visible-evidence successor is frozen.",
        ],
    }

    write_json(AUDIT_JSON, payload)
    write_jsonl(PREVIEW_ROWS_JSONL, preview_rows)
    print(json.dumps({"ok": True, "audit": str(AUDIT_JSON), "preview_rows": str(PREVIEW_ROWS_JSONL), "metrics": payload["metrics"]}, indent=2))


if __name__ == "__main__":
    main()
