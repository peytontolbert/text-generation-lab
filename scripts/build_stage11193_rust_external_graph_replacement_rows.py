#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11193
NAME = "stage11193_rust_external_graph_replacement_rows"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "rust_external_graph_replacement_rows.json"
ROWS_JSONL = OUT_DIR / "rust_replacement_strict_candidate_rows.jsonl"

WORK_ITEMS = ARTIFACTS / "stage11192_rust_external_graph_replacement_queue/rust_external_graph_replacement_work_items.jsonl"
REPO_ROOTS = {
    "rust-analyzer": Path("/arxiv/repositories/rust-analyzer"),
    "prusti-dev": Path("/arxiv/repositories/prusti-dev"),
    "rust": Path("/arxiv/repositories/rust"),
}
OPTION_VALUES = [
    "candidate_change_surface",
    "verifier_and_test_constraint",
    "symptom_or_call_path_analogue",
    "nearby_definition_or_usage_context",
]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def stable_shuffle(values: list[str], seed: str) -> list[str]:
    return sorted(values, key=lambda value: hashlib.sha256(f"{seed}\0{value}".encode()).hexdigest())


def git_head(repo_root: Path) -> str | None:
    try:
        return subprocess.check_output(["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return None


def snippet(path: Path, max_chars: int = 520) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    # Preserve imports/module comments and first function/test context without making snippets too long.
    preview = "\n".join(lines[: min(len(lines), 28)])
    if len(preview) > max_chars:
        preview = preview[:max_chars].rsplit("\n", 1)[0]
    return {
        "path": str(path),
        "sha256": hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest(),
        "line_start": 1,
        "line_end": min(len(lines), len(preview.splitlines())),
        "text": preview.strip(),
    }


def fact_lines(repo: str, role_paths: dict[str, str], snippets: dict[str, dict[str, Any]], gold_value: str) -> dict[str, str]:
    c = snippets["candidate_change_surface"]
    v = snippets["verifier_and_test_constraint"]
    s = snippets["symptom_or_call_path_analogue"]
    # Deliberately avoid answer role names in the visible facts. The role names only appear in options.
    return {
        "candidate_change_surface": (
            f"E01. Modified implementation surface in `{Path(c['path']).name}` from repo `{repo}`. "
            f"Snippet lines {c['line_start']}-{c['line_end']}: {c['text'][:420]}"
        ),
        "verifier_and_test_constraint": (
            f"E02. Concrete Rust test/verification file `{Path(v['path']).name}` is available for checking behavior. "
            f"Snippet lines {v['line_start']}-{v['line_end']}: {v['text'][:420]}"
        ),
        "symptom_or_call_path_analogue": (
            f"E03. Related runtime/API path `{Path(s['path']).name}` gives independent behavior context distinct from the modified surface. "
            f"Snippet lines {s['line_start']}-{s['line_end']}: {s['text'][:420]}"
        ),
        "nearby_definition_or_usage_context": (
            "E04. General neighboring repository context exists, but no separate snippet is stronger than E01-E03 for this row."
        ),
    }


def build_row(item: dict[str, Any]) -> dict[str, Any]:
    repo = str(item["repo_family"])
    repo_root = REPO_ROOTS[repo]
    seed_paths = item.get("seed_role_paths") or {}
    snippets = {}
    for role, rel_path in seed_paths.items():
        path = repo_root / rel_path
        snippets[role] = snippet(path)
        snippets[role]["repo_relative_path"] = rel_path
    row_id = item["work_item_id"].replace("stage11192::", "stage11193::")
    values = stable_shuffle(OPTION_VALUES, row_id)
    labels = [chr(ord("A") + idx) for idx in range(len(values))]
    options = [{"label": label, "value": value} for label, value in zip(labels, values)]
    gold_value = str(item["target_gold_value"])
    gold_label = next(opt["label"] for opt in options if opt["value"] == gold_value)
    facts = fact_lines(repo, seed_paths, snippets, gold_value)
    pre_options_lines = [
        "Language: rust",
        "Perspective: evidence_citation",
        "Task: choose the evidence role best supported by the visible Rust maintainer evidence. Use evidence content, not option order.",
        f"Repository family: {repo}",
        f"Source commit: {git_head(repo_root) or 'unknown'}",
        "",
        "Visible evidence ledger:",
        facts["candidate_change_surface"],
        facts["verifier_and_test_constraint"],
        facts["symptom_or_call_path_analogue"],
        facts["nearby_definition_or_usage_context"],
        "",
    ]
    pre_options = "\n".join(pre_options_lines)
    prompt = pre_options + "Options:\n" + "\n".join(f"{opt['label']}. {opt['value']}" for opt in options) + "\nAnswer:"
    return {
        "row_id": row_id,
        "root_id": item.get("work_item_id"),
        "root_lineage_key": f"stage11192::{repo}::{git_head(repo_root) or 'unknown'}",
        "repo_family": repo,
        "repo_id": repo,
        "language_family": "rust",
        "task_type": "evidence_citation",
        "split": "strict_candidate",
        "strict_eval_eligible": False,
        "strict_replacement_candidate": True,
        "train_support_only": False,
        "source_family_id": item.get("source_family_id"),
        "replacement_for_blocked_row_id": item.get("replacement_for_blocked_row_id"),
        "input_text": prompt,
        "prompt_text": prompt,
        "target_text": gold_label,
        "decoder_text": gold_label,
        "bounded_choice_target_label": gold_label,
        "opaque_options": options,
        "loss_mask": {"decoder_ce": True},
        "expected_enabled_loss": "decoder_ce",
        "standalone_projection_source": {
            "gold_value": gold_value,
            "gold_label": gold_label,
            "opaque_options": options,
            "evidence_facts": facts,
            "source_work_item_id": item.get("work_item_id"),
            "source_commit": git_head(repo_root),
            "repo_root": str(repo_root),
            "seed_role_paths": seed_paths,
            "snippets": snippets,
        },
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "gold_label_not_in_prompt_before_options": gold_label not in pre_options.splitlines(),
            "target_role_not_named_as_answer_before_options": gold_value not in pre_options,
            "visible_role_facts_are_distinct": len({snippets[r]["repo_relative_path"] for r in ["candidate_change_surface", "verifier_and_test_constraint", "symptom_or_call_path_analogue"]}) == 3,
            "source_snippets_materialized": True,
            "source_commit_recorded": git_head(repo_root) is not None,
            "not_train_support": True,
            "replacement_for_quarantined_reserved_row": True,
        },
    }


def main() -> None:
    items = load_jsonl(WORK_ITEMS)
    rows: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for item in items:
        try:
            rows.append(build_row(item))
        except Exception as exc:
            blocked.append({"work_item_id": item.get("work_item_id"), "reason": type(exc).__name__, "detail": str(exc)})
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "decision": "rust_replacement_rows_materialized" if rows and not blocked else "rust_replacement_rows_partial_or_blocked",
        "promotion_eligible": False,
        "reason_not_promotion_eligible": "Rows require admission audit before strict replacement use.",
        "source_artifacts": {"work_items": rel(WORK_ITEMS)},
        "counts": {
            "input_work_items": len(items),
            "materialized_rows": len(rows),
            "blocked_items": len(blocked),
            "by_gold_value": {value: sum(1 for row in rows if (row.get("standalone_projection_source") or {}).get("gold_value") == value) for value in sorted({(row.get("standalone_projection_source") or {}).get("gold_value") for row in rows})},
            "by_repo": {repo: sum(1 for row in rows if row.get("repo_family") == repo) for repo in sorted({row.get("repo_family") for row in rows})},
        },
        "blocked": blocked,
        "outputs": {"summary_json": rel(SUMMARY_JSON), "rows_jsonl": rel(ROWS_JSONL)},
    }
    write_jsonl(ROWS_JSONL, rows)
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
