#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-manifest",
        default="runs/local/tmp/stage662_atomic_binding_overfit_1k/agentkernel_lite_encdec_dataset_manifest.json",
    )
    parser.add_argument("--output-root", default="runs/local/tmp/stage664_atomic_binding_overfit_sweep")
    parser.add_argument("--artifact-json", default="runs/local/artifacts/stage664_atomic_binding_overfit_sweep.json")
    parser.add_argument("--sizes", default="64,128,256,512,1024")
    args = parser.parse_args()

    source_manifest_path = (ROOT / args.source_manifest).resolve()
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    source_train = Path(source_manifest["train_dataset_path"])
    rows = [
        row
        for row in iter_jsonl(source_train)
        if row.get("operation") == "atomic_fact"
        and row.get("retrieval_query_text")
        and row.get("retrieval_doc_text")
    ]
    if not rows:
        raise RuntimeError(f"no atomic_fact retrieval rows found in {source_train}")

    sizes = [int(part) for part in str(args.sizes).split(",") if part.strip()]
    output_root = (ROOT / args.output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    manifests: dict[str, str] = {}
    summaries: dict[str, dict[str, Any]] = {}
    for size in sizes:
        if size <= 0 or size > len(rows):
            raise ValueError(f"invalid size {size}; available rows={len(rows)}")
        selected = rows[:size]
        stage_dir = output_root / f"n{size}"
        stage_dir.mkdir(parents=True, exist_ok=True)
        train_path = stage_dir / "agentkernel_lite_encdec_train.jsonl"
        eval_path = stage_dir / "agentkernel_lite_encdec_eval.jsonl"
        write_jsonl(train_path, selected)
        write_jsonl(eval_path, selected)

        manifest = dict(source_manifest)
        manifest.update(
            {
                "artifact_kind": "agentkernel_lite_encdec_stage664_atomic_binding_overfit_subset",
                "manifest_path": str(stage_dir / "agentkernel_lite_encdec_dataset_manifest.json"),
                "train_dataset_path": str(train_path),
                "eval_dataset_path": str(eval_path),
                "train_examples": size,
                "eval_examples": size,
                "stage664_goal": "Find the smallest atomic binding overfit scale that the recursive KBPP doubling primitive can solve.",
                "stage664_subset_size": size,
                "stage664_source_manifest": str(source_manifest_path),
                "stage664_acceptance": "Full-corpus no-filter answer recovery should approach 1.0 before broad generalized KBPP doubling resumes.",
                "timestamp": int(time.time()),
            }
        )
        manifest_path = stage_dir / "agentkernel_lite_encdec_dataset_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        manifests[str(size)] = str(manifest_path)
        summaries[str(size)] = {
            "rows": size,
            "verified_bits": sum(float(row.get("stage653_verified_bits_if_correct", 0.0) or 0.0) for row in selected),
            "distinct_expected_content": len({str(row.get("expected_content", "")) for row in selected}),
            "distinct_selectors": len({str(row.get("stage655_generalized_selector", "")) for row in selected}),
        }

    artifact = {
        "artifact_kind": "stage664_atomic_binding_overfit_sweep",
        "source_manifest": str(source_manifest_path),
        "output_root": str(output_root),
        "manifests": manifests,
        "subsets": summaries,
        "decision_rule": "Use this sweep to separate objective failure from corpus-size/capacity failure before continuing recursive generalized KBPP doubling.",
        "timestamp": int(time.time()),
    }
    artifact_path = (ROOT / args.artifact_json).resolve()
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    latest_manifest = output_root / "agentkernel_lite_encdec_dataset_manifest.json"
    shutil.copyfile(output_root / f"n{sizes[0]}" / "agentkernel_lite_encdec_dataset_manifest.json", latest_manifest)
    print(json.dumps(artifact, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
