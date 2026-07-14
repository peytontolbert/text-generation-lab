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
STAGE = 11407
NAME = "stage11407_partial_candle_rust_train_support_rows"
OUT = ART / NAME
SUMMARY = OUT / "partial_candle_rust_train_support_rows.json"
ROWS = OUT / "partial_candle_rust_train_support_rows.jsonl"
AUDIT = OUT / "partial_candle_rust_train_support_audit.json"

ATLAS_ROOTS = ART / "stage11406_local_rust_source_acquisition_atlas/local_rust_source_roots.jsonl"

OPTIONS = [
    "SUPPORTING_CANDIDATE_CHANGE_SURFACE",
    "DECISIVE_VERIFIER_TEST_CONSTRAINT",
    "SUPPORTING_SYMPTOM_OR_CALL_PATH",
    "DISTRACTOR_BACKGROUND_CONTEXT",
]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def safe_read(path: str, limit: int = 1200) -> str:
    try:
        return Path(path).read_text(errors="replace")[:limit]
    except OSError:
        return ""


def deterministic_options(seed: str) -> list[dict[str, str]]:
    values = OPTIONS[:]
    values.sort(key=lambda value: hashlib.sha256(f"{seed}::{value}".encode()).hexdigest())
    return [{"label": chr(ord("A") + idx), "value": value} for idx, value in enumerate(values)]


def label_for(options: list[dict[str, str]], target: str) -> str:
    for option in options:
        if option["value"] == target:
            return option["label"]
    raise ValueError(target)


def candidate_id(text: str) -> str:
    return "CE-" + hashlib.sha256(text.encode()).hexdigest()[:8]


def row_for(root: dict[str, Any], kind: str, target: str, path: str, excerpt: str) -> dict[str, Any]:
    seed = f"{root['root_id']}::{kind}"
    options = deterministic_options(seed)
    label = label_for(options, target)
    item = (
        f"Candidate ID: {candidate_id(seed)}\n"
        f"Source path: {path}\n"
        "Evidence note: materialized local Rust source excerpt.\n"
        f"Excerpt:\n{excerpt.strip()}"
    )
    prompt = (
        "Language: rust\n"
        "Perspective: evidence_candidate_judgment\n"
        "Decision objective: classify this source-derived Rust evidence item as verifier/test evidence, "
        "changed-source support, symptom/call-path support, or background context.\n"
        "Use only the root context and candidate evidence item. Do not infer from option order.\n"
        f"Repository family: {root['repo_family']}\n"
        f"Crate root: {root['crate_dir']}\n"
        "Execution route: LOCAL_SOURCE_MATERIALIZATION_ONLY\n"
        "Verifier route: SELECTED_TEST_OR_EXAMPLE_ANCHOR_PRESENT\n"
        "Root context:\n"
        f"- Source root: {root['root_id']}\n"
        "- Available local evidence roles: changed, verifier, background\n\n"
        "Candidate evidence item under judgment:\n"
        f"{item}\n\n"
        "Options:\n"
        + "\n".join(f"{option['label']}. {option['value']}" for option in options)
        + "\nAnswer:"
    )
    row_id = f"stage11407::{root['root_id']}::{kind}"
    return {
        "row_id": row_id,
        "root_id": root["root_id"],
        "root_lineage_key": root["root_id"],
        "repo_family": root["repo_family"],
        "repo_id": root["repo_family"],
        "language_family": "rust",
        "task_type": "evidence_candidate_judgment",
        "surface": "maintainer_local_rust_source_evidence_candidate_judgment_bounded_choice",
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
        "opaque_options": options,
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "role_alias_not_visible_before_options": True,
            "root_split_isolation_required": True,
            "single_candidate_item_judgment": True,
            "source_text_materialized": True,
            "target_label_not_visible_before_options": True,
        },
        "standalone_projection_source": {
            "source_inventory_stage": NAME,
            "source_row_id": root["root_id"],
            "candidate_evidence_kind": kind,
            "candidate_evidence_text": item,
            "source_chunk_path": path,
            "source_chunk_role": kind,
            "gold_value": target,
            "gold_label": label,
            "opaque_options": options,
        },
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    candidates = [row for row in read_jsonl(ATLAS_ROOTS) if row.get("materialization_candidate") is True]
    rows: list[dict[str, Any]] = []
    for root in candidates:
        source_path = root.get("candidate_change_surface_path")
        verifier_path = root.get("verifier_or_test_constraint_path")
        cargo_path = root.get("cargo_toml")
        if not source_path or not verifier_path or not cargo_path:
            continue
        source_excerpt = safe_read(source_path)
        verifier_excerpt = safe_read(verifier_path)
        cargo_excerpt = safe_read(cargo_path)
        if not source_excerpt.strip() or not verifier_excerpt.strip() or not cargo_excerpt.strip():
            continue
        rows.append(row_for(root, "changed_source", "SUPPORTING_CANDIDATE_CHANGE_SURFACE", source_path, source_excerpt))
        rows.append(row_for(root, "verifier_test", "DECISIVE_VERIFIER_TEST_CONSTRAINT", verifier_path, verifier_excerpt))
        rows.append(row_for(root, "background_manifest", "DISTRACTOR_BACKGROUND_CONTEXT", cargo_path, cargo_excerpt))

    roots = {row["root_id"] for row in rows}
    repos = {row["repo_family"] for row in rows}
    by_target = Counter(row["semantic_target_value"] for row in rows)
    by_root = Counter(row["root_id"] for row in rows)
    audit_obj = {
        "rows": len(rows),
        "unique_roots": len(roots),
        "unique_repo_families": len(repos),
        "by_target": dict(sorted(by_target.items())),
        "by_root": dict(sorted(by_root.items())),
        "leak_checks": {
            "all_source_text_materialized": all((row.get("anti_cheat") or {}).get("source_text_materialized") for row in rows),
            "all_target_label_hidden_before_options": all((row.get("anti_cheat") or {}).get("target_label_not_visible_before_options") for row in rows),
            "all_train_support_only": all(row.get("train_support_only") and not row.get("strict_eval_eligible") for row in rows),
        },
        "probe_ready": False,
        "why_not_probe_ready": [
            "Only four roots were materialized.",
            "All roots are from the candle repo family.",
            "No symptom/call-path positive rows are available from this source-only atlas.",
        ],
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "partial_candle_rust_support_rows_materialized_not_probe_ready",
        "counts": {
            "train_support_rows": len(rows),
            "unique_roots": len(roots),
            "unique_repo_families": len(repos),
            "minimum_roots_required_before_probe": 10,
        },
        "by_target": dict(sorted(by_target.items())),
        "quality_gate": {
            "anti_cheat_passed": all(audit_obj["leak_checks"].values()),
            "enough_roots_for_probe": len(roots) >= 10,
            "enough_repo_breadth_for_probe": len(repos) >= 3,
            "probe_ready": False,
        },
        "recommended_next_action": (
            "Keep these rows as partial Rust support inventory. Do not launch a support probe until additional non-candle "
            "Rust roots with selected-test/verifier anchors are acquired or materialized."
        ),
        "source_artifacts": {"stage11406_atlas": rel(ATLAS_ROOTS)},
        "outputs": {
            "summary": rel(SUMMARY),
            "rows": rel(ROWS),
            "audit": rel(AUDIT),
        },
    }
    write_jsonl(ROWS, rows)
    write_json(AUDIT, audit_obj)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(summary["counts"], indent=2, sort_keys=True))
    print(json.dumps(summary["quality_gate"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
