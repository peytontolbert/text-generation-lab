#!/usr/bin/env python3
"""Build layered research ledgers from stage summaries.

This is intentionally conservative: raw summaries remain the source of truth,
and ledger records keep source paths so every inference is auditable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SUMMARY_DIR = ROOT / "runs" / "summaries"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / "stage12198_layered_research_ledgers"
SUMMARY_OUT = ROOT / "runs" / "summaries" / "stage12198_layered_research_ledgers.json"
GRAPH_IN = (
    ROOT
    / "runs"
    / "local"
    / "artifacts"
    / "stage12195_central_graph_integration"
    / "central_research_graph_with_stage12197_evidence_layers.json"
)
GRAPH_OUT = (
    ROOT
    / "runs"
    / "local"
    / "artifacts"
    / "stage12195_central_graph_integration"
    / "central_research_graph_with_stage12198_ledgers.json"
)


FAILURE_KEYWORDS = {
    "schema_renderer_option_collapse": [
        "schema",
        "renderer",
        "option",
        "selected_test",
        "selected-test",
        "visible_gold",
        "singleton",
        "target leak",
    ],
    "shared_head_interference": [
        "shared head",
        "interference",
        "regress",
        "negative transfer",
        "candidate_selection",
        "next_action",
    ],
    "data_scale_quality_gap": [
        "root",
        "source",
        "heldout",
        "scale",
        "admitted",
        "blocked",
        "lineage",
    ],
    "decoder_generation_mismatch": [
        "decoder",
        "generation",
        "short",
        "junk",
        "repetition",
        "exact_match",
    ],
    "episode_supply_gap": [
        "episode",
        "trajectory",
        "level_3",
        "patch_trace",
        "closed_loop",
        "closed-loop",
    ],
    "tokenizer_distraction": ["tokenizer", "vocab", "bpe", "1506", "4096"],
}

FRONTIER_TERMS = [
    "frontier",
    "promote",
    "promotion",
    "selected",
    "gemma",
    "runtime",
    "strict",
    "validation",
    "residual",
    "candidate",
    "decision",
]

DATASET_TERMS = [
    "rows",
    "roots",
    "repo",
    "language",
    "source",
    "heldout",
    "split",
    "lineage",
    "verifier",
    "selected_test",
    "episode",
    "patch_trace",
    "admission",
]

TRAINER_TERMS = [
    "trainer",
    "training",
    "runtime",
    "preflight",
    "differentiability",
    "loss",
    "head",
    "tokenizer",
    "cuda",
    "contract",
    "probe",
]


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(errors="ignore"))
    except Exception as exc:  # pragma: no cover - audit script
        return {"_read_error": str(exc)}
    return value if isinstance(value, dict) else {"value": value}


def stage_id(path: Path) -> int | None:
    match = re.match(r"stage(\d+)", path.name)
    return int(match.group(1)) if match else None


def short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def text_blob(stage_name: str, data: dict[str, Any]) -> str:
    return (stage_name + " " + json.dumps(data, sort_keys=True, default=str)).lower()


def find_paths(value: Any) -> list[str]:
    paths: list[str] = []
    if isinstance(value, str):
        if value.startswith("runs/") or value.startswith("docs/") or value.startswith("/data/"):
            paths.append(value)
    elif isinstance(value, list):
        for item in value:
            paths.extend(find_paths(item))
    elif isinstance(value, dict):
        for item in value.values():
            paths.extend(find_paths(item))
    return sorted(set(paths))


def decision_text(data: dict[str, Any]) -> str | None:
    for key in ("decision", "classification", "status", "result", "current_blocker"):
        value = data.get(key)
        if isinstance(value, str):
            return value
    return None


def extract_scores(data: dict[str, Any]) -> dict[str, Any]:
    scores: dict[str, Any] = {}
    for key, value in data.items():
        lk = key.lower()
        if any(term in lk for term in ("score", "accuracy", "strict", "validation", "residual", "gemma", "correct")):
            if isinstance(value, (str, int, float, bool, dict, list)):
                scores[key] = value
    return scores


def mechanism_tags(blob: str) -> list[str]:
    tags = []
    for mechanism, words in FAILURE_KEYWORDS.items():
        if any(word in blob for word in words):
            tags.append(mechanism)
    return tags


def has_any(blob: str, terms: list[str]) -> bool:
    return any(term in blob for term in terms)


def raw_record(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    sid = stage_id(path)
    name = path.stem
    blob = text_blob(name, data)
    tags = []
    for tag, terms in {
        "frontier": FRONTIER_TERMS,
        "dataset": DATASET_TERMS,
        "trainer": TRAINER_TERMS,
        "failure": sum(FAILURE_KEYWORDS.values(), []),
    }.items():
        if has_any(blob, terms):
            tags.append(tag)
    return {
        "record_id": f"stage_index:{sid}",
        "stage": sid,
        "stage_name": name,
        "summary_path": str(path.relative_to(ROOT)),
        "decision": decision_text(data),
        "passed": data.get("passed"),
        "training_executed": data.get("training_executed"),
        "source_code_modified": data.get("source_code_modified"),
        "tags": tags,
        "artifact_paths": find_paths(data)[:50],
    }


def frontier_record(path: Path, data: dict[str, Any]) -> dict[str, Any] | None:
    sid = stage_id(path)
    name = path.stem
    blob = text_blob(name, data)
    if not has_any(blob, FRONTIER_TERMS):
        return None
    decision = decision_text(data) or ""
    status = "diagnostic"
    if "reject" in decision.lower() or "rejected" in blob or "regress" in blob:
        status = "rejected"
    elif "promote" in decision.lower() or "selected" in decision.lower():
        status = "selected_or_promoted"
    elif "blocked" in blob:
        status = "blocked"
    return {
        "record_id": f"frontier:{sid}:{short_hash(name)}",
        "stage": sid,
        "stage_name": name,
        "record_type": "frontier_decision",
        "candidate_status": status,
        "decision": decision or None,
        "scores": extract_scores(data),
        "runtime_paths": [p for p in find_paths(data) if "runtime_model" in p][:20],
        "source_paths": [str(path.relative_to(ROOT))],
        "claim_boundary": data.get("claim_boundary") or data.get("remaining_caveats") or data.get("blocked_actions"),
    }


def failure_records(path: Path, data: dict[str, Any]) -> list[dict[str, Any]]:
    sid = stage_id(path)
    name = path.stem
    blob = text_blob(name, data)
    tags = mechanism_tags(blob)
    if not tags:
        return []
    explicit = []
    for key in ("lesson", "lessons", "why_training_blocked", "why_rejected", "blockers", "top_blockers", "useful_progress"):
        if key in data:
            explicit.append({key: data[key]})
    return [
        {
            "record_id": f"failure:{tag}:{sid}:{short_hash(name + tag)}",
            "stage": sid,
            "stage_name": name,
            "mechanism": tag,
            "severity": "blocks_or_guides_training",
            "decision": decision_text(data),
            "explicit_fields": explicit[:8],
            "recommended_guard": guard_for_mechanism(tag),
            "source_paths": [str(path.relative_to(ROOT))],
        }
        for tag in tags
    ]


def guard_for_mechanism(tag: str) -> str:
    return {
        "schema_renderer_option_collapse": "require task-specific target semantics, deterministic shuffle, no singleton/visible-gold rows",
        "shared_head_interference": "use task-routed or isolated heads and per-task preservation gates",
        "data_scale_quality_gap": "scale root-disjoint verifier-backed mechanisms, not same-root variants",
        "decoder_generation_mismatch": "separate bounded scorer quality from freeform generation claims",
        "episode_supply_gap": "block closed-loop training until level_3+ and patch-trace floors pass",
        "tokenizer_distraction": "keep tokenizer work diagnostic unless retrained/evaluated under matched manifests",
    }.get(tag, "require explicit gate before training")


def dataset_record(path: Path, data: dict[str, Any]) -> dict[str, Any] | None:
    sid = stage_id(path)
    name = path.stem
    blob = text_blob(name, data)
    if not has_any(blob, DATASET_TERMS):
        return None
    counts: dict[str, Any] = {}
    for key, value in data.items():
        lk = key.lower()
        if any(term in lk for term in ("count", "rows", "roots", "language", "split", "admitted", "blocked")):
            if isinstance(value, (str, int, float, bool, dict, list)):
                counts[key] = value
    status = "unknown"
    if "blocked" in blob or "quarantine" in blob:
        status = "blocked_or_quarantine"
    elif "train_support" in blob or "support-only" in blob or "support_only" in blob:
        status = "support_only"
    elif "strict" in blob or "heldout" in blob:
        status = "eval_or_heldout_related"
    return {
        "record_id": f"dataset_source:{sid}:{short_hash(name)}",
        "stage": sid,
        "stage_name": name,
        "record_type": "dataset_source_status",
        "status": status,
        "counts": counts,
        "train_authority": infer_train_authority(blob),
        "source_paths": [str(path.relative_to(ROOT))],
        "artifact_paths": find_paths(data)[:30],
    }


def infer_train_authority(blob: str) -> str:
    if "training_allowed\": false" in blob or "training blocked" in blob or "do not train" in blob:
        return "not_trainable"
    if "strict_eval_eligible\": false" in blob or "train_support_only" in blob:
        return "support_only"
    if "strict_eval" in blob or "heldout" in blob:
        return "eval_related_check_lineage"
    return "review_required"


def trainer_record(path: Path, data: dict[str, Any]) -> dict[str, Any] | None:
    sid = stage_id(path)
    name = path.stem
    blob = text_blob(name, data)
    if not has_any(blob, TRAINER_TERMS):
        return None
    status = "review_required"
    if "contract-only" in blob or "contract_only" in blob or "preflight" in blob:
        status = "contract_or_preflight"
    if "training_executed\": true" in blob or data.get("training_executed") is True:
        status = "training_executed"
    if "blocked" in blob or "do not train" in blob:
        status = "blocked"
    return {
        "record_id": f"trainer_capability:{sid}:{short_hash(name)}",
        "stage": sid,
        "stage_name": name,
        "record_type": "trainer_capability_status",
        "status": status,
        "decision": decision_text(data),
        "missing_or_blocked": data.get("blocked_actions") or data.get("why_training_blocked") or data.get("top_blockers"),
        "source_paths": [str(path.relative_to(ROOT))],
        "artifact_paths": find_paths(data)[:30],
    }


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def update_graph(summary: dict[str, Any]) -> dict[str, Any]:
    if not GRAPH_IN.exists():
        return {"skipped": "graph input missing", "path": str(GRAPH_IN.relative_to(ROOT))}
    graph = json.loads(GRAPH_IN.read_text())
    nodes = graph.setdefault("nodes", [])
    edges = graph.setdefault("edges", [])
    node_ids = {node.get("id") for node in nodes}
    edge_keys = {(edge.get("source"), edge.get("relation"), edge.get("target"), edge.get("evidence_source")) for edge in edges}

    ledger_nodes = [
        ("ledger:frontier", "Frontier ledger", "frontier_ledger_jsonl"),
        ("ledger:failure_mechanism", "Failure mechanism ledger", "failure_mechanism_ledger_jsonl"),
        ("ledger:dataset_source", "Dataset/source ledger", "dataset_source_ledger_jsonl"),
        ("ledger:trainer_capability", "Trainer capability ledger", "trainer_capability_ledger_jsonl"),
        ("ledger:raw_stage_index", "Raw stage index", "raw_stage_index_jsonl"),
    ]
    added_nodes = 0
    added_edges = 0
    for node_id, name, key in ledger_nodes:
        if node_id not in node_ids:
            nodes.append(
                {
                    "id": node_id,
                    "kind": "research_ledger",
                    "name": name,
                    "status": "generated_stage12198",
                    "evidence_source": summary["outputs"][key],
                    "record_count": summary["record_counts"][key.replace("_jsonl", "")],
                }
            )
            node_ids.add(node_id)
            added_nodes += 1
        for target in ("lane:unbounded_software_task_completion_training", "frontier:compact_bounded_stage11507"):
            edge = {
                "source": node_id,
                "relation": "informs_training_decisions_for",
                "target": target,
                "evidence_source": summary["outputs"][key],
            }
            edge_key = (edge["source"], edge["relation"], edge["target"], edge["evidence_source"])
            if edge_key not in edge_keys:
                edges.append(edge)
                edge_keys.add(edge_key)
                added_edges += 1

    graph["stage12198_layered_research_ledgers"] = {
        "added_nodes": added_nodes,
        "added_edges": added_edges,
        "new_node_count": len(nodes),
        "new_edge_count": len(edges),
    }
    GRAPH_OUT.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n")
    return graph["stage12198_layered_research_ledgers"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary-dir", type=Path, default=SUMMARY_DIR)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    raw: list[dict[str, Any]] = []
    frontier: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    datasets: list[dict[str, Any]] = []
    trainers: list[dict[str, Any]] = []
    tag_counts: Counter[str] = Counter()

    for path in sorted(args.summary_dir.glob("stage*.json")):
        sid = stage_id(path)
        if sid is None:
            continue
        data = read_json(path)
        raw_rec = raw_record(path, data)
        raw.append(raw_rec)
        tag_counts.update(raw_rec["tags"])
        f_rec = frontier_record(path, data)
        if f_rec:
            frontier.append(f_rec)
        failures.extend(failure_records(path, data))
        d_rec = dataset_record(path, data)
        if d_rec:
            datasets.append(d_rec)
        t_rec = trainer_record(path, data)
        if t_rec:
            trainers.append(t_rec)

    outputs = {
        "raw_stage_index_jsonl": args.out_dir / "raw_stage_index.jsonl",
        "frontier_ledger_jsonl": args.out_dir / "frontier_ledger.jsonl",
        "failure_mechanism_ledger_jsonl": args.out_dir / "failure_mechanism_ledger.jsonl",
        "dataset_source_ledger_jsonl": args.out_dir / "dataset_source_ledger.jsonl",
        "trainer_capability_ledger_jsonl": args.out_dir / "trainer_capability_ledger.jsonl",
    }
    write_jsonl(outputs["raw_stage_index_jsonl"], raw)
    write_jsonl(outputs["frontier_ledger_jsonl"], frontier)
    write_jsonl(outputs["failure_mechanism_ledger_jsonl"], failures)
    write_jsonl(outputs["dataset_source_ledger_jsonl"], datasets)
    write_jsonl(outputs["trainer_capability_ledger_jsonl"], trainers)

    summary: dict[str, Any] = {
        "stage": "stage12198_layered_research_ledgers",
        "decision": "append_only_research_ledgers_generated",
        "training_executed": False,
        "source_code_modified": True,
        "record_counts": {
            "raw_stage_index": len(raw),
            "frontier_ledger": len(frontier),
            "failure_mechanism_ledger": len(failures),
            "dataset_source_ledger": len(datasets),
            "trainer_capability_ledger": len(trainers),
        },
        "tag_counts": dict(sorted(tag_counts.items())),
        "outputs": {key: str(path.relative_to(ROOT)) for key, path in outputs.items()},
        "inputs": {"summary_dir": str(args.summary_dir.relative_to(ROOT))},
        "graph_output": str(GRAPH_OUT.relative_to(ROOT)),
    }
    summary["graph_delta"] = update_graph(summary)
    for key, rel in summary["outputs"].items():
        path = ROOT / rel
        summary.setdefault("sha256", {})[key] = hashlib.sha256(path.read_bytes()).hexdigest()
    if GRAPH_OUT.exists():
        summary["sha256"]["graph_output"] = hashlib.sha256(GRAPH_OUT.read_bytes()).hexdigest()

    (args.out_dir / "layered_research_ledgers_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    SUMMARY_OUT.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
