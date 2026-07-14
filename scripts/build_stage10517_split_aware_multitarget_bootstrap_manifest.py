from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10517
NAME = "stage10517_split_aware_multitarget_bootstrap_manifest"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME

BOOTSTRAP_BOUNDED_ROWS = ROOT / "runs/local/artifacts/stage10514_multilingual_maintainer_frontier_v1_package/multilingual_maintainer_frontier_v1_rows.jsonl"
LONG_CONTEXT_ROOTS = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_root_records.jsonl"
LONG_CONTEXT_ROWS = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_multitarget_rows.jsonl"

MANIFEST_JSON = OUT_DIR / "split_aware_multitarget_bootstrap_manifest.json"
ALL_ROWS_JSONL = OUT_DIR / "multitarget_bootstrap_rows.jsonl"
TRAIN_ROWS_JSONL = OUT_DIR / "multitarget_bootstrap_train_rows.jsonl"
VALIDATION_ROWS_JSONL = OUT_DIR / "multitarget_bootstrap_validation_rows.jsonl"
REFERENCE_ROWS_JSONL = OUT_DIR / "multitarget_bootstrap_reference_rows.jsonl"
DIAGNOSTIC_ROWS_JSONL = OUT_DIR / "multitarget_bootstrap_diagnostic_rows.jsonl"
RUN_SUMMARY_JSON = ROOT / "runs/summaries" / f"{NAME}.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def map_bounded_split_component(row: dict[str, Any]) -> str:
    role = row.get("package_role", "")
    mapping = {
        "bootstrap_train_support": "train_bootstrap_bounded",
        "bootstrap_train_support_geometry_rebuild": "train_bootstrap_geometry",
        "bootstrap_validation_seed_abstention_heavy": "validation_bootstrap_bounded",
        "diagnostic_support_only": "diagnostic_bounded",
        "legacy_reviewed_eval_reference": "reference_bounded_eval",
    }
    return mapping.get(role, "reference_bounded_eval")


def normalize_bounded_row(row: dict[str, Any]) -> dict[str, Any]:
    root_id = (
        row.get("root_lineage_key")
        or row.get("source_root_id")
        or row.get("episode_id")
        or row.get("row_id")
    )
    split_component = map_bounded_split_component(row)
    return {
        "row_id": row["row_id"],
        "root_id": root_id,
        "episode_id": row.get("episode_id", root_id),
        "state_id": row.get("state_id", row["row_id"]),
        "split_component": split_component,
        "language_family": row.get("language_family", "unknown"),
        "repo_id": row.get("repo_id", "unknown"),
        "repo_family": row.get("repo_family", row.get("repo_id", "unknown")),
        "target_family": row.get("target_family") or ("bounded_decision" if row.get("objective_family") == "bounded_decoder_ce" else "unknown"),
        "target_subtype": row.get("target_subtype", row.get("task_type", "unknown")),
        "input_text": row.get("input_text") or row.get("prompt_text", ""),
        "target_text": row.get("target_text", ""),
        "anti_cheat": row.get("anti_cheat", {}),
        "source_family_id": row.get("bootstrap_family", "stage10514_multilingual_bootstrap"),
        "source_stage": 10514,
        "lineage_role": row.get("package_role", "unknown"),
    }


def normalize_long_context_row(row: dict[str, Any], root_lookup: dict[str, dict[str, Any]]) -> dict[str, Any]:
    root = root_lookup.get(row["root_id"], {})
    split_component = row.get("split_component", "unknown")
    if split_component == "audited_train":
        split_component = "train_teacher_long_context"
    return {
        "row_id": row["row_id"],
        "root_id": row["root_id"],
        "episode_id": row["episode_id"],
        "state_id": row["state_id"],
        "split_component": split_component,
        "language_family": root.get("language_family", "unknown"),
        "repo_id": root.get("repo_id", "unknown"),
        "repo_family": root.get("repo_family", root.get("repo_id", "unknown")),
        "target_family": row.get("target_family", "unknown"),
        "target_subtype": row.get("target_subtype", "unknown"),
        "input_text": row.get("input_text", ""),
        "target_text": row.get("target_text", ""),
        "anti_cheat": row.get("anti_cheat", {}),
        "source_family_id": root.get("provenance", {}).get("source_family_id", "stage10516_long_context_compiler"),
        "source_stage": 10516,
        "lineage_role": "long_context_teacher_state" if split_component == "train_teacher_long_context" else "long_context_bootstrap",
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RUN_SUMMARY_JSON.parent.mkdir(parents=True, exist_ok=True)

    bounded_rows = load_jsonl(BOOTSTRAP_BOUNDED_ROWS)
    long_context_roots = load_jsonl(LONG_CONTEXT_ROOTS)
    long_context_rows = load_jsonl(LONG_CONTEXT_ROWS)
    root_lookup = {row["root_id"]: row for row in long_context_roots}

    normalized_bounded = [normalize_bounded_row(row) for row in bounded_rows]
    normalized_long_context = [normalize_long_context_row(row, root_lookup) for row in long_context_rows]
    all_rows = normalized_bounded + normalized_long_context

    rows_by_root: dict[str, set[str]] = defaultdict(set)
    for row in all_rows:
        rows_by_root[row["root_id"]].add(row["split_component"])

    split_overlap_roots = {
        root_id: sorted(components)
        for root_id, components in rows_by_root.items()
        if len(components) > 1 and not all(comp.startswith("reference_") or comp.startswith("diagnostic_") for comp in components)
    }

    train_rows = [
        row for row in all_rows
        if row["split_component"] in {
            "train_bootstrap_bounded",
            "train_bootstrap_geometry",
            "train_bootstrap_long_context",
            "train_teacher_long_context",
        }
    ]
    validation_rows = [row for row in all_rows if row["split_component"].startswith("validation_")]
    reference_rows = [row for row in all_rows if row["split_component"].startswith("reference_")]
    diagnostic_rows = [row for row in all_rows if row["split_component"].startswith("diagnostic_")]

    manifest = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": len(split_overlap_roots) == 0,
        "claim_boundary": [
            "This is a training/bootstrap manifest, not a promotable evaluation artifact.",
            "The repaired v2.7 bounded frontier remains a canary and reference slice, not a direct training target.",
            "Legacy reviewed eval references are carried as reference-only rows and must not silently enter train.",
            "Long-context raw pack roots are bootstrap-only; audited retrieval teacher states remain train teacher supervision, not heldout claims.",
        ],
        "inputs": {
            "stage10514_bootstrap_rows": str(BOOTSTRAP_BOUNDED_ROWS.relative_to(ROOT)),
            "stage10516_compiled_roots": str(LONG_CONTEXT_ROOTS.relative_to(ROOT)),
            "stage10516_compiled_rows": str(LONG_CONTEXT_ROWS.relative_to(ROOT)),
        },
        "metrics": {
            "all_rows": len(all_rows),
            "train_rows": len(train_rows),
            "validation_rows": len(validation_rows),
            "reference_rows": len(reference_rows),
            "diagnostic_rows": len(diagnostic_rows),
            "rows_by_split_component": dict(sorted(Counter(row["split_component"] for row in all_rows).items())),
            "rows_by_language": dict(sorted(Counter(row["language_family"] for row in all_rows).items())),
            "rows_by_target_family": dict(sorted(Counter(row["target_family"] for row in all_rows).items())),
            "rows_by_source_stage": dict(sorted(Counter(str(row["source_stage"]) for row in all_rows).items())),
            "train_rows_by_language": dict(sorted(Counter(row["language_family"] for row in train_rows).items())),
            "train_rows_by_target_family": dict(sorted(Counter(row["target_family"] for row in train_rows).items())),
            "unique_train_roots": len({row["root_id"] for row in train_rows}),
        },
        "root_split_audit": {
            "violations": split_overlap_roots,
            "violation_count": len(split_overlap_roots),
            "rule": "same root_id must not appear across train/validation/eval claim paths",
        },
        "next_best_step": (
            "Use the train and validation slices here to launch the first root-based seq2seq curriculum run, "
            "while keeping reference and diagnostic slices out of promotion claims. "
            "Then add fresh Rust and web heldout roots so multilingual training supply matches the target headline languages."
        ),
        "outputs": {
            "all_rows": str(ALL_ROWS_JSONL.relative_to(ROOT)),
            "train_rows": str(TRAIN_ROWS_JSONL.relative_to(ROOT)),
            "validation_rows": str(VALIDATION_ROWS_JSONL.relative_to(ROOT)),
            "reference_rows": str(REFERENCE_ROWS_JSONL.relative_to(ROOT)),
            "diagnostic_rows": str(DIAGNOSTIC_ROWS_JSONL.relative_to(ROOT)),
        },
    }

    write_jsonl(ALL_ROWS_JSONL, all_rows)
    write_jsonl(TRAIN_ROWS_JSONL, train_rows)
    write_jsonl(VALIDATION_ROWS_JSONL, validation_rows)
    write_jsonl(REFERENCE_ROWS_JSONL, reference_rows)
    write_jsonl(DIAGNOSTIC_ROWS_JSONL, diagnostic_rows)
    write_json(MANIFEST_JSON, manifest)
    write_json(RUN_SUMMARY_JSON, manifest)


if __name__ == "__main__":
    main()
