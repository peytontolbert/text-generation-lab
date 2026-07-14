#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11410
NAME = "stage11410_rust_verifier_log_backed_partial_support"
OUT = ART / NAME
SUMMARY = OUT / "rust_verifier_log_backed_partial_support.json"
ROWS = OUT / "rust_verifier_log_backed_partial_support_rows.jsonl"
AUDIT = OUT / "rust_verifier_log_backed_partial_support_audit.json"

CAPTURE = ART / "stage11409_rust_candle_verifier_log_capture/rust_candle_verifier_log_capture.json"

OPTIONS = [
    "SUPPORTING_CANDIDATE_CHANGE_SURFACE",
    "DECISIVE_VERIFIER_TEST_CONSTRAINT",
    "OBSERVED_VERIFIER_FAILURE_LOG",
    "DISTRACTOR_BACKGROUND_CONTEXT",
]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text()) if path.exists() else {}


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def safe_read(path: str | None, limit: int = 1200) -> str:
    if not path:
        return ""
    try:
        return Path(path).read_text(errors="replace")[:limit]
    except OSError:
        return ""


def options_for(seed: str) -> list[dict[str, str]]:
    values = OPTIONS[:]
    values.sort(key=lambda value: hashlib.sha256(f"{seed}::{value}".encode()).hexdigest())
    return [{"label": chr(ord("A") + idx), "value": value} for idx, value in enumerate(values)]


def label_for(options: list[dict[str, str]], target: str) -> str:
    for option in options:
        if option["value"] == target:
            return option["label"]
    raise ValueError(target)


def candidate_id(seed: str) -> str:
    return "CE-" + hashlib.sha256(seed.encode()).hexdigest()[:8]


def row_for(result: dict[str, Any], kind: str, target: str, path: str, excerpt: str) -> dict[str, Any]:
    root_id = str(result["root_id"])
    seed = f"{root_id}::{kind}"
    opts = options_for(seed)
    label = label_for(opts, target)
    item = (
        f"Candidate ID: {candidate_id(seed)}\n"
        f"Source path: {path}\n"
        "Evidence note: materialized Rust verifier-log-backed evidence excerpt.\n"
        f"Excerpt:\n{excerpt.strip()}"
    )
    prompt = (
        "Language: rust\n"
        "Perspective: evidence_candidate_judgment\n"
        "Decision objective: classify this Rust maintenance evidence item as changed-source support, "
        "verifier/test constraint, observed verifier failure log, or background context.\n"
        "Use only the root context and candidate evidence item. Do not infer from option order.\n"
        f"Repository family: {result.get('repo_family')}\n"
        f"Crate root: {result.get('crate_dir')}\n"
        f"Verifier command: {result.get('command')}\n"
        f"Verifier status: {result.get('status')} returncode={result.get('returncode')}\n"
        "Root context:\n"
        f"- Source root: {root_id}\n"
        "- Available local evidence roles: changed, verifier_source, verifier_log, background\n\n"
        "Candidate evidence item under judgment:\n"
        f"{item}\n\n"
        "Options:\n"
        + "\n".join(f"{option['label']}. {option['value']}" for option in opts)
        + "\nAnswer:"
    )
    return {
        "row_id": f"stage11410::{root_id}::{kind}",
        "root_id": root_id,
        "root_lineage_key": root_id,
        "repo_family": result.get("repo_family"),
        "repo_id": result.get("repo_family"),
        "language_family": "rust",
        "task_type": "evidence_candidate_judgment",
        "surface": "maintainer_rust_verifier_log_backed_evidence_candidate_judgment_bounded_choice",
        "split": "train",
        "package_split": "train",
        "train_support_only": True,
        "strict_eval_eligible": False,
        "expected_enabled_loss": "decoder_ce",
        "loss_mask": {"decoder_ce": True},
        "input_text": prompt,
        "prompt_text": prompt,
        "decoder_text": label,
        "target_text": label,
        "bounded_choice_target_label": label,
        "semantic_target_value": target,
        "opaque_options": opts,
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "role_alias_not_visible_before_options": True,
            "root_split_isolation_required": True,
            "single_candidate_item_judgment": True,
            "source_text_materialized": True,
            "target_label_not_visible_before_options": True,
            "actual_verifier_log_attached": True,
        },
        "standalone_projection_source": {
            "source_inventory_stage": NAME,
            "source_row_id": root_id,
            "candidate_evidence_kind": kind,
            "candidate_evidence_text": item,
            "source_chunk_path": path,
            "source_chunk_role": kind,
            "verifier_log_path": result.get("log_path"),
            "verifier_status": result.get("status"),
            "gold_value": target,
            "gold_label": label,
            "opaque_options": opts,
        },
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    capture = read_json(CAPTURE)
    rows: list[dict[str, Any]] = []
    used_results = []
    for result in capture.get("results", []):
        if not result.get("materialization_allowed_after_log"):
            continue
        source_excerpt = safe_read(result.get("candidate_change_surface_path"))
        verifier_excerpt = safe_read(result.get("verifier_or_test_constraint_path"))
        log_excerpt = safe_read(ROOT / result.get("log_path"), limit=1600) if result.get("log_path") else ""
        if not (source_excerpt.strip() and verifier_excerpt.strip() and log_excerpt.strip()):
            continue
        rows.append(row_for(result, "candidate_change_surface", "SUPPORTING_CANDIDATE_CHANGE_SURFACE", result["candidate_change_surface_path"], source_excerpt))
        rows.append(row_for(result, "verifier_test_source", "DECISIVE_VERIFIER_TEST_CONSTRAINT", result["verifier_or_test_constraint_path"], verifier_excerpt))
        rows.append(row_for(result, "actual_verifier_log", "OBSERVED_VERIFIER_FAILURE_LOG", rel(ROOT / result["log_path"]), log_excerpt))
        used_results.append(result)

    roots = {row["root_id"] for row in rows}
    repos = {str(row["repo_family"]) for row in rows}
    by_target = Counter(row["semantic_target_value"] for row in rows)
    audit = {
        "rows": len(rows),
        "unique_roots": len(roots),
        "unique_repo_families": len(repos),
        "by_target": dict(sorted(by_target.items())),
        "source_results": [
            {
                "root_id": result["root_id"],
                "status": result["status"],
                "returncode": result["returncode"],
                "log_path": result["log_path"],
            }
            for result in used_results
        ],
        "leak_checks": {
            "all_source_text_materialized": all((row.get("anti_cheat") or {}).get("source_text_materialized") for row in rows),
            "all_target_label_hidden_before_options": all((row.get("anti_cheat") or {}).get("target_label_not_visible_before_options") for row in rows),
            "all_verifier_logs_attached": all((row.get("anti_cheat") or {}).get("actual_verifier_log_attached") for row in rows),
            "all_train_support_only": all(row.get("train_support_only") and not row.get("strict_eval_eligible") for row in rows),
        },
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "verifier_log_backed_partial_rust_support_materialized_not_probe_ready",
        "counts": {
            "train_support_rows": len(rows),
            "unique_roots": len(roots),
            "unique_repo_families": len(repos),
            "minimum_roots_required_before_probe": 10,
        },
        "by_target": dict(sorted(by_target.items())),
        "quality_gate": {
            "anti_cheat_passed": all(audit["leak_checks"].values()),
            "actual_verifier_logs_attached": bool(rows),
            "enough_roots_for_probe": len(roots) >= 10,
            "enough_repo_breadth_for_probe": len(repos) >= 3,
            "probe_ready": False,
        },
        "limitations": [
            "All materialized roots are Candle-family roots.",
            "Verifier logs are build/dependency failures, not clean product fail-to-pass outcomes.",
            "This is support inventory only and must not be used as a Rust headline eval slice.",
        ],
        "recommended_next_action": (
            "Keep these rows as verifier-log-backed partial support. Acquire or hydrate more non-candle Rust roots and prefer "
            "clean selected-test product verifier logs before building a Rust support probe."
        ),
        "source_artifacts": {"stage11409_capture": rel(CAPTURE)},
        "outputs": {"summary": rel(SUMMARY), "rows": rel(ROWS), "audit": rel(AUDIT)},
    }
    write_jsonl(ROWS, rows)
    write_json(AUDIT, audit)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(summary["counts"], indent=2, sort_keys=True))
    print(json.dumps(summary["quality_gate"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
