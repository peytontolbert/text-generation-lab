#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10520
NAME = "stage10520_multilingual_eval_safe_heldout_slice"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SLICE_JSON = OUT_DIR / "multilingual_eval_safe_heldout_slice.json"
ROOTS_JSONL = OUT_DIR / "heldout_root_reservations.jsonl"
ROWS_JSONL = OUT_DIR / "heldout_eval_safe_rows.jsonl"
SUMMARY_JSON = ROOT / "runs/summaries" / f"{NAME}.json"

COMPILED_ROOTS = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_root_records.jsonl"
COMPILED_ROWS = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_multitarget_rows.jsonl"

TARGET_LANGS = ("python", "rust", "c_cpp", "web_js_ts_html")
TARGET_ROWS = {"decisive_evidence", "retrieve_answer_abstain"}
TARGET_ROOTS_PER_LANG = {"python": 6, "rust": 4, "c_cpp": 4, "web_js_ts_html": 4}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def main() -> None:
    roots = load_jsonl(COMPILED_ROOTS)
    rows = load_jsonl(COMPILED_ROWS)
    root_lookup = {row["root_id"]: row for row in roots}

    eval_safe_rows = [
        row for row in rows
        if row["root_id"].startswith("audited::")
        and row.get("target_subtype") in TARGET_ROWS
        and not row.get("anti_cheat", {}).get("prompt_target_leak", False)
    ]

    rows_by_root: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in eval_safe_rows:
        rows_by_root[row["root_id"]].append(row)

    candidate_roots: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for root_id, root in root_lookup.items():
        if not root_id.startswith("audited::"):
            continue
        lang = root.get("language_family", "unknown")
        if lang not in TARGET_LANGS:
            continue
        repo_id = root.get("repo_id", "unknown")
        root_rows = rows_by_root.get(root_id, [])
        if len(root_rows) < 2:
            continue
        candidate_roots[lang].append(
            {
                "root_id": root_id,
                "language_family": lang,
                "repo_id": repo_id,
                "verifier_id": root.get("verifier_id"),
                "task_family": root.get("task_family"),
                "row_ids": sorted(row["row_id"] for row in root_rows),
                "target_subtypes": sorted({row["target_subtype"] for row in root_rows}),
            }
        )

    selected_roots: list[dict[str, Any]] = []
    selected_root_ids: set[str] = set()
    for lang in TARGET_LANGS:
        per_repo = defaultdict(list)
        for root in candidate_roots.get(lang, []):
            per_repo[root["repo_id"]].append(root)
        for repo_id in per_repo:
            per_repo[repo_id].sort(key=lambda row: row["root_id"])
        repo_ids = sorted(per_repo)
        while repo_ids and len([r for r in selected_roots if r["language_family"] == lang]) < TARGET_ROOTS_PER_LANG[lang]:
            for repo_id in list(repo_ids):
                if not per_repo[repo_id]:
                    repo_ids.remove(repo_id)
                    continue
                root = per_repo[repo_id].pop(0)
                if root["root_id"] in selected_root_ids:
                    continue
                selected_roots.append(root)
                selected_root_ids.add(root["root_id"])
                if len([r for r in selected_roots if r["language_family"] == lang]) >= TARGET_ROOTS_PER_LANG[lang]:
                    break

    selected_rows = [row for row in eval_safe_rows if row["root_id"] in selected_root_ids]
    per_lang_selected = Counter(root["language_family"] for root in selected_roots)
    per_lang_repos = {lang: sorted({root["repo_id"] for root in selected_roots if root["language_family"] == lang}) for lang in TARGET_LANGS}

    audit_failures = []
    for lang in TARGET_LANGS:
        if per_lang_selected.get(lang, 0) == 0:
            audit_failures.append(f"missing_lang:{lang}")

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": len(audit_failures) == 0,
        "failures": audit_failures,
        "claim_boundary": [
            "This slice reserves audited long-context roots for evaluation-safe use by excluding train-only target subtypes.",
            "Only decisive_evidence and retrieve_answer_abstain projections are included because verifier_outcome is verbatim-leaky in the current audited prompts.",
            "These roots must be removed from training manifests before any multilingual benchmark claim uses them.",
        ],
        "metrics": {
            "candidate_roots_by_language": dict(sorted((lang, len(items)) for lang, items in candidate_roots.items())),
            "selected_roots_by_language": dict(sorted(per_lang_selected.items())),
            "selected_rows": len(selected_rows),
            "selected_rows_by_language": dict(sorted(Counter(root_lookup[row["root_id"]]["language_family"] for row in selected_rows).items())),
            "selected_rows_by_target_subtype": dict(sorted(Counter(row["target_subtype"] for row in selected_rows).items())),
            "selected_repo_ids_by_language": per_lang_repos,
        },
        "next_best_step": (
            "Rebuild the bootstrap manifest with these roots removed from train and reclassified as heldout evaluation rows, "
            "then rerun the honesty audit to confirm multilingual heldout coverage."
        ),
        "outputs": {
            "heldout_root_reservations": str(ROOTS_JSONL.relative_to(ROOT)),
            "heldout_eval_safe_rows": str(ROWS_JSONL.relative_to(ROOT)),
        },
    }

    write_jsonl(ROOTS_JSONL, selected_roots)
    write_jsonl(ROWS_JSONL, selected_rows)
    write_json(SLICE_JSON, payload)
    write_json(SUMMARY_JSON, payload)


if __name__ == "__main__":
    main()
