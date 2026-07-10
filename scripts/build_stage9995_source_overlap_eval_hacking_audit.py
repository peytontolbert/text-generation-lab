#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9995
NAME = "stage9995_source_overlap_eval_hacking_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
ROWS = OUT_DIR / "source_overlap_eval_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SOURCE_OVERLAP_EVAL_HACKING_AUDIT_STAGE9995.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9986_filtered_positive_replay_successor_request/edit_localization_manifest.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "next_best_step": summary["next_best_step"],
        }
    )
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_audit() -> dict[str, Any]:
    rows = load_jsonl(MANIFEST)
    train_sources = {str(row.get("source_row_id") or "") for row in rows if row.get("split") == "train"}
    train_semantics = {str(row.get("semantic_key") or "") for row in rows if row.get("split") == "train"}
    grouped_sources: dict[str, list[dict[str, Any]]] = defaultdict(list)
    grouped_semantics: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped_sources[str(row.get("source_row_id") or "")].append(row)
        grouped_semantics[str(row.get("semantic_key") or "")].append(row)

    overlap_rows: list[dict[str, Any]] = []
    for row in rows:
        split = str(row.get("split") or "")
        if split not in {"eval", "strict_eval"}:
            continue
        source_row_id = str(row.get("source_row_id") or "")
        semantic_key = str(row.get("semantic_key") or "")
        source_overlap = source_row_id in train_sources
        semantic_overlap = semantic_key in train_semantics
        if not source_overlap and not semantic_overlap:
            continue
        overlap_rows.append(
            {
                "row_id": row.get("row_id"),
                "split": split,
                "language_family": row.get("language_family"),
                "counterfactual_role": row.get("counterfactual_role"),
                "source_row_id": source_row_id,
                "semantic_key": semantic_key,
                "source_overlap_with_train": source_overlap,
                "semantic_overlap_with_train": semantic_overlap,
                "matching_train_source_rows": [r.get("row_id") for r in grouped_sources.get(source_row_id, []) if r.get("split") == "train"],
                "matching_train_semantic_rows": [r.get("row_id") for r in grouped_semantics.get(semantic_key, []) if r.get("split") == "train"],
                "task_observation": (row.get("input_state") or {}).get("task_observation"),
                "visible_locality_evidence": (row.get("input_state") or {}).get("visible_locality_evidence"),
            }
        )

    write_jsonl(ROWS, overlap_rows)
    source_only = [row for row in overlap_rows if row["source_overlap_with_train"]]
    semantic_only = [row for row in overlap_rows if row["semantic_overlap_with_train"]]
    heldout = [row for row in rows if row.get("split") in {"eval", "strict_eval"} and str(row.get("source_row_id") or "") not in train_sources]
    metrics = {
        "manifest_rows": len(rows),
        "train_rows": sum(1 for row in rows if row.get("split") == "train"),
        "eval_rows": sum(1 for row in rows if row.get("split") == "eval"),
        "strict_eval_rows": sum(1 for row in rows if row.get("split") == "strict_eval"),
        "source_overlap_eval_rows": len(source_only),
        "source_overlap_eval_by_language": dict(sorted(Counter(str(row["language_family"] or "") for row in source_only).items())),
        "source_overlap_eval_by_role": dict(sorted(Counter(str(row["counterfactual_role"] or "") for row in source_only).items())),
        "semantic_overlap_eval_rows": len(semantic_only),
        "semantic_overlap_eval_by_language": dict(sorted(Counter(str(row["language_family"] or "") for row in semantic_only).items())),
        "heldout_eval_rows_after_source_filter": len(heldout),
        "heldout_eval_by_language": dict(sorted(Counter(str(row.get("language_family") or "") for row in heldout).items())),
    }
    failures: list[str] = []
    if metrics["source_overlap_eval_rows"] <= 0:
        failures.append("expected_source_overlap_rows")
    if metrics["heldout_eval_rows_after_source_filter"] >= metrics["eval_rows"] + metrics["strict_eval_rows"]:
        failures.append("expected_source_filter_to_remove_some_eval_rows")
    return {"passed": not failures, "failures": failures, "metrics": metrics}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_audit()
    next_step = "Use the source-heldout subset, not the raw filtered frontier, for any honest 100M-versus-Gemma comparison and rebuild future eval manifests to avoid train-overlapping roots."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": built["metrics"],
        "failures": built["failures"],
        "artifacts": {"rows": display(ROWS), "doc": display(DOC)},
        "decision": "Audited the filtered frontier for eval hacking risk by checking train-versus-eval overlap on source roots and semantic keys.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9995 Source Overlap Eval Hacking Audit",
                "",
                f"Passed: `{summary['passed']}`",
                f"Source-overlap eval rows: `{built['metrics']['source_overlap_eval_rows']}`",
                f"Semantic-overlap eval rows: `{built['metrics']['semantic_overlap_eval_rows']}`",
                "",
                summary["decision"],
                "",
                f"Next: {next_step}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
