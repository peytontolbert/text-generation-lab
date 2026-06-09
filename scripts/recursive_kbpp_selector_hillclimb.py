#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "runs/local/tmp/pocketpal_stage602_entity_field_balanced_replay_seed461/agentkernel_lite_encdec_dataset_manifest.json"
DEFAULT_BUNDLE = ROOT / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage602_stage601_entity_field_balanced_replay_lr3e6_steps200"
DEFAULT_OUTPUT = ROOT / "runs/local/tmp/recursive_kbpp_selector_hillclimb"
DEFAULT_ARTIFACT = ROOT / "runs/local/artifacts/recursive_kbpp_selector_hillclimb.json"
PYTHON = "/home/peyton/miniconda3/envs/ai/bin/python"
EVAL = ROOT / "legacy_src/scripts/evaluate_agentkernel_lite_retrieval_embeddings.py"
KEY_VALUE_RE = re.compile(r"([A-Za-z][A-Za-z0-9_]*?)=([^\s;]+)")
TEXT_FIELDS = {
    "decoder_text",
    "encoder_text",
    "json_decoder_text",
    "negative_decoder_text",
    "retrieval_doc_text",
    "retrieval_query_text",
    "state_text",
}
DEFAULT_TEMPLATES = [
    "{entity}|{field}",
    "{field}|{entity}",
    "{domain}|{entity}|{field}",
    "sp={entity}|{field}",
    "selector_pair={entity}|{field}",
]


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def key_values(text: str) -> dict[str, str]:
    return {str(key): str(value) for key, value in KEY_VALUE_RE.findall(str(text or ""))}


def safe_name(text: str) -> str:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    clean = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").lower()[:42]
    return f"{clean or 'template'}_{digest}"


def marker_from_template(template: str, keys: dict[str, str]) -> str | None:
    try:
        marker = template.format_map({key: keys.get(key, "") for key in keys})
    except KeyError:
        return None
    if "{" in marker or "}" in marker:
        return None
    parts = re.findall(r"\{([A-Za-z][A-Za-z0-9_]*)\}", template)
    if any(not keys.get(part) for part in parts):
        return None
    marker = marker.strip()
    return marker or None


def inject_after_operation(text: str, op: str, marker: str) -> str:
    if not text or marker in text:
        return text
    op_token = f"<AK_OP_{op.upper()}>"
    op_match = re.search(rf"({re.escape(op_token)}|op={re.escape(op)})", text)
    if op_match:
        return text[: op_match.end()] + f" {marker}" + text[op_match.end() :]
    return f"{marker} {text}"


def rewrite_row(row: dict[str, Any], target_ops: set[str], template: str) -> tuple[dict[str, Any], bool, str | None]:
    op = str(row.get("operation", "") or "")
    if op not in target_ops:
        return dict(row), False, None
    query_keys = key_values(str(row.get("retrieval_query_text", "") or ""))
    doc_keys = key_values(str(row.get("retrieval_doc_text", "") or ""))
    keys = dict(doc_keys)
    keys.update(query_keys)
    marker = marker_from_template(template, keys)
    if marker is None:
        return dict(row), False, None
    rewritten: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, str) and key in TEXT_FIELDS:
            rewritten[key] = inject_after_operation(value, op, marker)
        else:
            rewritten[key] = value
    rewritten["recursive_kbpp_selector_marker"] = marker
    rewritten["recursive_kbpp_selector_template"] = template
    rewritten["source_type"] = f"{row.get('source_type', 'retrieval')}_recursive_selector"
    return rewritten, True, marker


def build_candidate(
    *,
    source_manifest: dict[str, Any],
    source_manifest_path: Path,
    output_root: Path,
    target_ops: set[str],
    template: str,
) -> dict[str, Any]:
    name = safe_name(template)
    out_dir = output_root / name
    out_dir.mkdir(parents=True, exist_ok=True)
    split_paths: dict[str, Path] = {}
    changed_counts: dict[str, int] = {}
    marker_counts: dict[str, int] = {}
    operation_counts: dict[str, dict[str, int]] = {}
    for split in ("train", "eval"):
        rows = list(iter_jsonl(Path(source_manifest[f"{split}_dataset_path"])))
        rewritten_rows = []
        changed = 0
        markers: Counter[str] = Counter()
        for row in rows:
            new_row, did_change, marker = rewrite_row(row, target_ops, template)
            changed += int(did_change)
            if marker:
                markers[marker] += 1
            rewritten_rows.append(new_row)
        split_path = out_dir / f"agentkernel_lite_encdec_{split}.jsonl"
        write_jsonl(split_path, rewritten_rows)
        split_paths[split] = split_path
        changed_counts[split] = changed
        marker_counts[split] = len(markers)
        operation_counts[split] = dict(Counter(str(row.get("operation", "") or "") for row in rewritten_rows))

    manifest = dict(source_manifest)
    manifest.update(
        {
            "artifact_kind": "agentkernel_lite_encdec_recursive_kbpp_selector_candidate",
            "source_manifest_path": str(source_manifest_path),
            "manifest_path": str(out_dir / "agentkernel_lite_encdec_dataset_manifest.json"),
            "train_dataset_path": str(split_paths["train"]),
            "eval_dataset_path": str(split_paths["eval"]),
            "train_examples": sum(1 for _ in iter_jsonl(split_paths["train"])),
            "eval_examples": sum(1 for _ in iter_jsonl(split_paths["eval"])),
            "recursive_kbpp_selector_template": template,
            "recursive_kbpp_target_ops": sorted(target_ops),
            "recursive_kbpp_changed_train_examples": changed_counts["train"],
            "recursive_kbpp_changed_eval_examples": changed_counts["eval"],
        }
    )
    manifest_path = out_dir / "agentkernel_lite_encdec_dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "name": name,
        "template": template,
        "manifest_path": str(manifest_path),
        "changed_counts": changed_counts,
        "distinct_marker_counts": marker_counts,
        "operation_counts": operation_counts,
    }


def run_eval(bundle_dir: Path, manifest_path: Path, output_dir: Path, density_steps: int) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    no_filter = output_dir / "retrieval_eval_full_corpus_operation_gated.json"
    hard_filter = output_dir / "retrieval_eval_full_corpus_operation_gated_structured_hard_filter.json"
    common = [
        PYTHON,
        str(EVAL),
        "--bundle-dir",
        str(bundle_dir),
        "--dataset-manifest",
        str(manifest_path),
        "--dataset-split",
        "eval",
        "--device",
        "cuda",
        "--limit",
        "0",
        "--batch-size",
        "512",
        "--max-query-tokens",
        "128",
        "--max-doc-tokens",
        "128",
        "--operation-gated",
        "1",
        "--full-corpus",
        "1",
        "--density-train-batch-size",
        "64",
        "--density-total-train-steps",
        str(density_steps),
    ]
    subprocess.run(common + ["--output-json", str(no_filter)], check=True)
    subprocess.run(
        common
        + [
            "--structured-key-rerank",
            "1",
            "--structured-key-hard-filter",
            "1",
            "--output-json",
            str(hard_filter),
        ],
        check=True,
    )
    no = json.loads(no_filter.read_text(encoding="utf-8"))
    hard = json.loads(hard_filter.read_text(encoding="utf-8"))
    density = no["verified_density"]
    stats = hard["structured_key_hard_filter_stats"]
    return {
        "eval_json": str(no_filter),
        "hard_filter_eval_json": str(hard_filter),
        "exact_top1": no["top1_accuracy"],
        "answer_top1": no["answer_top1_accuracy"],
        "mrr": no["mean_reciprocal_rank"],
        "exact_bits_per_param": density["exact_verified_bits"] / density["parameter_count"],
        "answer_bits_per_param": density["answer_verified_bits"] / density["parameter_count"],
        "avg_train_retrieval_tokens_per_pair": density["token_stats"]["avg_train_retrieval_tokens_per_pair"],
        "hard_filter_exact_top1": hard["top1_accuracy"],
        "hard_filter_answer_top1": hard["answer_top1_accuracy"],
        "hard_filter_corrections": stats["top1_corrected_by_hard_filter"],
    }


def score(metrics: dict[str, Any], token_penalty: float) -> float:
    return float(metrics["answer_bits_per_param"]) - token_penalty * float(metrics["avg_train_retrieval_tokens_per_pair"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Recursively hill-climb compact selector schemas for KBPP.")
    parser.add_argument("--source-manifest", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--bundle-dir", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--artifact-json", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--target-ops", default="entity_context")
    parser.add_argument("--templates", nargs="*", default=DEFAULT_TEMPLATES)
    parser.add_argument("--run-eval", type=int, default=0)
    parser.add_argument("--density-total-train-steps", type=int, default=3800)
    parser.add_argument("--token-penalty", type=float, default=0.0)
    parser.add_argument("--max-candidates", type=int, default=0)
    args = parser.parse_args()

    source_manifest = json.loads(args.source_manifest.read_text(encoding="utf-8"))
    target_ops = {op.strip() for op in args.target_ops.split(",") if op.strip()}
    templates = list(dict.fromkeys(args.templates))
    if args.max_candidates > 0:
        templates = templates[: args.max_candidates]

    candidates = []
    for template in templates:
        candidate = build_candidate(
            source_manifest=source_manifest,
            source_manifest_path=args.source_manifest,
            output_root=args.output_root,
            target_ops=target_ops,
            template=template,
        )
        if args.run_eval:
            eval_dir = args.output_root / candidate["name"] / "eval"
            metrics = run_eval(args.bundle_dir, Path(candidate["manifest_path"]), eval_dir, args.density_total_train_steps)
            candidate["metrics"] = metrics
            candidate["score"] = score(metrics, args.token_penalty)
        candidates.append(candidate)

    ranked = sorted(candidates, key=lambda item: item.get("score", float("-inf")), reverse=True)
    summary = {
        "artifact_kind": "recursive_kbpp_selector_hillclimb",
        "source_manifest": str(args.source_manifest),
        "bundle_dir": str(args.bundle_dir),
        "target_ops": sorted(target_ops),
        "run_eval": bool(args.run_eval),
        "token_penalty": args.token_penalty,
        "candidate_count": len(candidates),
        "best_candidate": ranked[0] if ranked else None,
        "candidates": ranked,
        "finding": (
            "Use this script to recursively test compact selector markers and rank them by answer bits/param, optionally "
            "with a retrieval-token penalty. It automates the Stage610-615 hill-climb pattern."
        ),
    }
    args.artifact_json.parent.mkdir(parents=True, exist_ok=True)
    args.artifact_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
