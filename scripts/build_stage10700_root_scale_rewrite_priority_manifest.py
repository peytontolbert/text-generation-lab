#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10700
NAME = "stage10700_root_scale_rewrite_priority_manifest"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST_JSON = OUT_DIR / "root_scale_rewrite_priority_manifest.json"
PRIORITY_ROWS_JSONL = OUT_DIR / "rewrite_priority_rows.jsonl"
RUN_SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

SCALE_PACKAGE = ROOT / "runs/local/artifacts/stage10699_multilingual_root_scale_package_v1/multilingual_root_scale_package_v1.json"
QUARANTINE_BACKLOG = ROOT / "runs/local/artifacts/stage10699_multilingual_root_scale_package_v1/quarantine_rewrite_backlog.jsonl"

LANGUAGES = ["python", "rust", "c_cpp", "web_js_ts_html"]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def action_for_language(language: str) -> str:
    return {
        "python": "rewrite_prompt_target_leaks_and_add_repo_caps",
        "rust": "rewrite_leaks_and_mine_fresh_non_tokenizers_verifier_roots",
        "c_cpp": "rewrite_prompt_target_leaks_and_expand_verifier_anchors",
        "web_js_ts_html": "rewrite_leaks_and_mine_pure_web_verifier_roots",
    }.get(language, "rewrite_prompt_target_leaks")


def main() -> None:
    scale_package = load_json(SCALE_PACKAGE)
    backlog_rows = load_jsonl(QUARANTINE_BACKLOG)

    by_language: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in backlog_rows:
        by_language[str(row.get("language_family") or "unknown")].append(row)

    priority_rows: list[dict[str, Any]] = []
    language_actions: list[dict[str, Any]] = []
    for language in LANGUAGES:
        rows = by_language.get(language, [])
        families = Counter(str(row.get("repo_family") or "unknown") for row in rows)
        for repo_family, count in families.most_common(8):
            family_rows = [row for row in rows if str(row.get("repo_family") or "") == repo_family]
            priority_rows.append(
                {
                    "language_family": language,
                    "repo_family": repo_family,
                    "roots": count,
                    "example_root_ids": [str(row.get("root_id") or "") for row in family_rows[:5]],
                    "priority_action": action_for_language(language),
                    "rewrite_priority": "high" if language in {"rust", "web_js_ts_html"} else "medium",
                    "source_kinds": dict(sorted(Counter(str(row.get("source_kind") or "unknown") for row in family_rows).items())),
                    "prompt_target_leak_rows_total": sum(int(row.get("prompt_target_leak_rows") or 0) for row in family_rows),
                }
            )
        card = next(
            (item for item in (scale_package.get("language_cards") or []) if str(item.get("language_family") or "") == language),
            {},
        )
        language_actions.append(
            {
                "language_family": language,
                "phase_1_gap": ((card.get("gaps") or {}).get("phase_1")),
                "phase_2_gap": ((card.get("gaps") or {}).get("phase_2")),
                "long_term_gap": ((card.get("gaps") or {}).get("long_term")),
                "ready_train_roots_now": ((scale_package.get("global_counts") or {}).get("ready_for_large_scale_train_by_language") or {}).get(language),
                "top_quarantine_repo_families": [
                    {"repo_family": repo_family, "roots": count}
                    for repo_family, count in families.most_common(5)
                ],
                "recommended_action": action_for_language(language),
            }
        )

    priority_rows.sort(
        key=lambda row: (
            {"high": 0, "medium": 1, "low": 2}.get(str(row.get("rewrite_priority") or "low"), 3),
            -int(row.get("roots") or 0),
            str(row.get("language_family") or ""),
            str(row.get("repo_family") or ""),
        )
    )
    write_jsonl(PRIORITY_ROWS_JSONL, priority_rows)

    manifest = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "root_scale_rewrite_priority_manifest_ready",
        "claim_scope": [
            "Turn the multilingual quarantine backlog into a concrete rewrite and source-mining priority list.",
            "Focus the next dataset work on the highest-yield repo families and the languages with the weakest phase-1 readiness.",
            "This is a root-rewrite planning artifact, not a new training or evaluation result.",
        ],
        "source_artifacts": {
            "scale_package": display(SCALE_PACKAGE),
            "quarantine_backlog": display(QUARANTINE_BACKLOG),
        },
        "headline_findings": [
            "Rust and web should be treated as highest-priority rewrite/mining lanes because their honest ready pools are tiny even though the global quarantine backlog is dominated by Python.",
            "Python and c_cpp need leak rewrites too, but their next problem is also repo-family concentration, not only raw count.",
            "The rewrite backlog is now explicit enough to drive a true v2.8 scale program instead of another same-surface compact probe.",
        ],
        "language_actions": language_actions,
        "priority_rows_count": len(priority_rows),
        "outputs": {
            "priority_rows": display(PRIORITY_ROWS_JSONL),
            "manifest_json": display(MANIFEST_JSON),
        },
    }
    write_json(MANIFEST_JSON, manifest)
    write_json(
        RUN_SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": manifest["decision"],
            "manifest_json": display(MANIFEST_JSON),
        },
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
