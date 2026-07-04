#!/usr/bin/env python3
"""Attach targeted /arxiv recovery sources to the central research graph.

This stage records durable storage sources needed for rebuilding the 100M
software-maintainer program. It also prepares a longevity-doc bundle that can be
mirrored to /arxiv with an explicit non-destructive write.
"""

from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CENTRAL_GRAPH_PATH = ROOT / "runs" / "local" / "artifacts" / "stage8622_central_research_graph" / "central_research_graph.json"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / "stage8624_arxiv_recovery_graph_attachment"
SUMMARY_PATH = ROOT / "runs" / "summaries" / "stage8624_reconstructed_arxiv_recovery_graph_attachment.json"
DOC_PATH = ROOT / "docs" / "ARXIV_RECOVERY_GRAPH_ATTACHMENT_STAGE8624.md"

ARXIV_MIRROR_DIR = Path("/arxiv/agentkernel_recovery/stage8624_central_graph_recovery")

AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}

LONGEVITY_DOCS = [
    "docs/CENTRAL_RESEARCH_GRAPH_STAGE8622.md",
    "docs/ARXIV_LONGTERM_STORAGE_RECOVERY_STAGE8623.md",
    "docs/CURRENT_RESEARCH_SPINE_RECONSTRUCTED.md",
    "docs/RECOVERED_VARIABLE_LEDGER_STAGE8615.md",
    "docs/RECOVERED_TRAINING_MINING_GAP_MATRIX_STAGE8616.md",
    "docs/SPINE_LEDGER_SESSION_SCRAPE_STAGE8620.md",
    "docs/MODEL_FAMILY_SCHEMA_RECOVERY_STAGE8621.md",
    "docs/SYMBOL_BINDING_RECOVERY_STATUS.md",
    "docs/MINING_AND_TRAINING_RECOVERY_GAP_STATUS.md",
    "docs/TRAINER_REBUILD_CONTRACT.md",
    "docs/TRAINING_TINY_DETAILS_CONTRACT.md",
    "configs/software_maintainer/action_feature_registry.json",
    "configs/software_maintainer/mining_contract_v1.json",
    "configs/software_maintainer/model_family_stack_registry.json",
    "runs/local/artifacts/stage8622_central_research_graph/central_research_graph.json",
    "runs/local/artifacts/stage8622_central_research_graph/central_research_nodes.jsonl",
    "runs/local/artifacts/stage8622_central_research_graph/central_research_edges.jsonl",
]

LIKELY_DATASET_KEYWORDS = [
    "code",
    "swe",
    "codex",
    "coding",
    "software",
    "trace",
    "instruct",
    "refinement",
    "completion",
    "defect",
    "clone",
    "method",
    "open-swe",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True))


def make_node_id(kind: str, name: str) -> str:
    return f"{kind}:{str(name).replace('/', '_').replace(' ', '_')}"


def add_node(nodes: dict[str, dict[str, Any]], kind: str, name: str, **attrs: Any) -> str:
    nid = make_node_id(kind, name)
    nodes[nid] = {"id": nid, "kind": kind, "name": name, **nodes.get(nid, {}), **attrs}
    return nid


def add_edge(edges: list[dict[str, Any]], source: str, relation: str, target: str, **attrs: Any) -> None:
    edge = {"source": source, "relation": relation, "target": target, **attrs}
    key = (source, relation, target)
    if not any((e["source"], e["relation"], e["target"]) == key for e in edges):
        edges.append(edge)


def session_inventory() -> dict[str, Any]:
    root = Path("/arxiv/code/sessions")
    manifests = sorted(root.glob("_backup_manifest_*.json"))
    session_files = sorted(root.glob("**/*.jsonl"))
    latest_manifest: dict[str, Any] = {}
    if manifests:
        latest_manifest = load_json(manifests[-1])
    total_bytes = 0
    samples = []
    largest = []
    for path in session_files:
        try:
            size = path.stat().st_size
        except OSError:
            continue
        total_bytes += size
        rel = str(path.relative_to(root))
        if len(samples) < 40:
            samples.append(rel)
        largest.append((size, rel))
    largest.sort(reverse=True)
    return {
        "root": str(root),
        "manifest_count": len(manifests),
        "latest_manifest": latest_manifest,
        "session_jsonl_count": len(session_files),
        "session_jsonl_bytes": total_bytes,
        "sample_session_paths": samples,
        "largest_session_paths": [{"bytes": size, "path": rel} for size, rel in largest[:20]],
    }


def preserved_seq2seq_inventory() -> dict[str, Any]:
    root = Path("/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab")
    files = sorted(root.glob("**/*")) if root.exists() else []
    records = []
    for path in files:
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix not in {".json", ".jsonl", ".safetensors", ".pt"}:
            continue
        rel = str(path.relative_to(root))
        try:
            size = path.stat().st_size
        except OSError:
            size = None
        records.append({"path": str(path), "relative_path": rel, "suffix": suffix, "size_bytes": size})
    by_suffix = Counter(record["suffix"] for record in records)
    return {
        "root": str(root),
        "exists": root.exists(),
        "records": records,
        "counts_by_suffix": dict(sorted(by_suffix.items())),
        "manifest_paths": [r for r in records if "manifest" in r["relative_path"].lower()],
        "checkpoint_reference_paths": [r for r in records if r["suffix"] in {".safetensors", ".pt"}],
    }


def dataset_inventory() -> dict[str, Any]:
    root = Path("/arxiv/datasets")
    dirs = sorted([p for p in root.iterdir() if p.is_dir()]) if root.exists() else []
    selected = []
    for path in dirs:
        lower = path.name.lower()
        if any(keyword in lower for keyword in LIKELY_DATASET_KEYWORDS):
            selected.append({"path": str(path), "name": path.name})
    return {
        "root": str(root),
        "exists": root.exists(),
        "top_level_dataset_count": len(dirs),
        "likely_software_dataset_count": len(selected),
        "likely_software_datasets": selected,
    }


def build_longevity_bundle(attachments: dict[str, Any]) -> Path:
    bundle = OUT_DIR / "longevity_docs_bundle"
    bundle.mkdir(parents=True, exist_ok=True)
    copied = []
    for rel in LONGEVITY_DOCS:
        src = ROOT / rel
        if not src.exists():
            continue
        dst = bundle / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(rel)
    write_json(bundle / "stage8624_arxiv_recovery_attachments.json", attachments)
    (bundle / "README.md").write_text(
        "\n".join(
            [
                "# Stage8624 Longevity Bundle",
                "",
                "This bundle contains the central recovered research graph, core registries, and recovery docs needed to resume the 100M software-maintainer rebuild. It is a documentation bundle only and carries no training/runtime authority.",
                "",
                "Authority remains closed for model execution, decoder CE, runtime, source/body emission, Gemma, harness, scoring, controller merge, and promotion.",
                "",
                "Included files:",
                "",
                *[f"- `{rel}`" for rel in copied],
                "- `stage8624_arxiv_recovery_attachments.json`",
                "",
            ]
        )
    )
    return bundle


def mirror_bundle_to_arxiv(bundle: Path) -> str:
    if ARXIV_MIRROR_DIR.exists():
        raise FileExistsError(f"Refusing to overwrite existing /arxiv mirror: {ARXIV_MIRROR_DIR}")
    ARXIV_MIRROR_DIR.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(bundle, ARXIV_MIRROR_DIR)
    return str(ARXIV_MIRROR_DIR)


def attach_to_graph(attachments: dict[str, Any]) -> dict[str, Any]:
    graph = load_json(CENTRAL_GRAPH_PATH)
    nodes = {node["id"]: node for node in graph.get("nodes", [])}
    edges = list(graph.get("edges", []))
    final = add_node(nodes, "final_objective", "100M software maintainer")
    stage = add_node(nodes, "stage", "8624", stage_name="stage8624_reconstructed_arxiv_recovery_graph_attachment", passed=True)
    add_edge(edges, final, "has_recovery_stage", stage, evidence_source="stage8624")

    session_node = add_node(nodes, "recovery_source", "/arxiv/code/sessions", **{
        "session_jsonl_count": attachments["sessions"]["session_jsonl_count"],
        "session_jsonl_bytes": attachments["sessions"]["session_jsonl_bytes"],
        "backup_manifest_count": attachments["sessions"]["manifest_count"],
    })
    add_edge(edges, stage, "attaches_recovery_source", session_node, evidence_source="stage8624")

    ckpt_node = add_node(nodes, "recovery_source", "/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab", **{
        "exists": attachments["preserved_seq2seq"]["exists"],
        "file_records": len(attachments["preserved_seq2seq"]["records"]),
    })
    add_edge(edges, stage, "attaches_recovery_source", ckpt_node, evidence_source="stage8624")

    datasets_node = add_node(nodes, "recovery_source", "/arxiv/datasets", **{
        "top_level_dataset_count": attachments["datasets"]["top_level_dataset_count"],
        "likely_software_dataset_count": attachments["datasets"]["likely_software_dataset_count"],
    })
    add_edge(edges, stage, "attaches_recovery_source", datasets_node, evidence_source="stage8624")

    for item in attachments["datasets"]["likely_software_datasets"]:
        dataset_node = add_node(nodes, "dataset_source", item["name"], path=item["path"])
        add_edge(edges, datasets_node, "contains_likely_software_dataset", dataset_node, evidence_source="stage8624")

    graph["nodes"] = sorted(nodes.values(), key=lambda n: n["id"])
    graph["edges"] = sorted(edges, key=lambda e: (e["source"], e["relation"], e["target"]))
    graph["version"] = "stage8624_reconstructed_central_research_graph_with_arxiv_sources"
    return graph


def write_doc(attachments: dict[str, Any], metrics: dict[str, Any], mirror_path: str | None) -> None:
    datasets = attachments["datasets"]["likely_software_datasets"]
    DOC_PATH.write_text(
        "\n".join(
            [
                "# Stage8624 `/arxiv` Recovery Graph Attachment",
                "",
                "This stage attaches durable `/arxiv` recovery sources to the central research graph and prepares a longevity documentation bundle. It does not run models, load checkpoints, delete files, or authorize training.",
                "",
                "## Session Archive",
                "",
                f"- root: `{attachments['sessions']['root']}`",
                f"- backup manifests: {attachments['sessions']['manifest_count']}",
                f"- session JSONL files: {attachments['sessions']['session_jsonl_count']}",
                f"- session JSONL bytes: {attachments['sessions']['session_jsonl_bytes']}",
                f"- latest backup manifest reports missing_count: {attachments['sessions']['latest_manifest'].get('missing_count')}",
                f"- latest backup manifest reports destination_file_count: {attachments['sessions']['latest_manifest'].get('destination_file_count')}",
                "",
                "## Preserved Seq2Seq Storage",
                "",
                f"- root: `{attachments['preserved_seq2seq']['root']}`",
                f"- exists: {attachments['preserved_seq2seq']['exists']}",
                f"- records: {len(attachments['preserved_seq2seq']['records'])}",
                f"- manifests: {len(attachments['preserved_seq2seq']['manifest_paths'])}",
                f"- checkpoint references: {len(attachments['preserved_seq2seq']['checkpoint_reference_paths'])}",
                "",
                "## Likely Software Dataset Roots",
                "",
                *[f"- `{item['path']}`" for item in datasets],
                "",
                "## Longevity Bundle",
                "",
                f"- local bundle: `{OUT_DIR / 'longevity_docs_bundle'}`",
                f"- `/arxiv` mirror: `{mirror_path}`" if mirror_path else "- `/arxiv` mirror: not written in this run",
                "",
                "## Metrics",
                "",
                "```json",
                json.dumps(metrics, indent=2, sort_keys=True),
                "```",
                "",
                "## Recovery Use",
                "",
                "Use these sources to recover exact old session passages, preserved 100M config/checkpoint metadata, and dataset roots. Checkpoints remain references only until explicit future execution/training gates pass.",
                "",
            ]
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mirror-to-arxiv", action="store_true", help="Copy the longevity bundle to a new /arxiv/agentkernel_recovery stage directory.")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOC_PATH.parent.mkdir(parents=True, exist_ok=True)

    attachments = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "authority": AUTHORITY_CLOSED,
        "sessions": session_inventory(),
        "preserved_seq2seq": preserved_seq2seq_inventory(),
        "datasets": dataset_inventory(),
    }
    write_json(OUT_DIR / "arxiv_recovery_attachments.json", attachments)

    attached_graph = attach_to_graph(attachments)
    write_json(OUT_DIR / "central_research_graph_with_arxiv_sources.json", attached_graph)
    with (OUT_DIR / "central_research_graph_with_arxiv_sources_nodes.jsonl").open("w") as f:
        for node in attached_graph["nodes"]:
            f.write(json.dumps(node, sort_keys=True) + "\n")
    with (OUT_DIR / "central_research_graph_with_arxiv_sources_edges.jsonl").open("w") as f:
        for edge in attached_graph["edges"]:
            f.write(json.dumps(edge, sort_keys=True) + "\n")

    bundle = build_longevity_bundle(attachments)
    mirror_path = mirror_bundle_to_arxiv(bundle) if args.mirror_to_arxiv else None

    metrics = {
        "session_jsonl_count": attachments["sessions"]["session_jsonl_count"],
        "session_jsonl_bytes": attachments["sessions"]["session_jsonl_bytes"],
        "session_backup_manifest_count": attachments["sessions"]["manifest_count"],
        "latest_session_manifest_missing_count": attachments["sessions"]["latest_manifest"].get("missing_count"),
        "preserved_seq2seq_records": len(attachments["preserved_seq2seq"]["records"]),
        "preserved_seq2seq_manifest_paths": len(attachments["preserved_seq2seq"]["manifest_paths"]),
        "preserved_seq2seq_checkpoint_references": len(attachments["preserved_seq2seq"]["checkpoint_reference_paths"]),
        "top_level_arxiv_dataset_count": attachments["datasets"]["top_level_dataset_count"],
        "likely_software_dataset_count": attachments["datasets"]["likely_software_dataset_count"],
        "attached_graph_nodes": len(attached_graph["nodes"]),
        "attached_graph_edges": len(attached_graph["edges"]),
        "arxiv_mirror_written": mirror_path is not None,
    }
    write_doc(attachments, metrics, mirror_path)

    summary = {
        "stage": 8624,
        "stage_name": "stage8624_reconstructed_arxiv_recovery_graph_attachment",
        "passed": True,
        "reconstructed": True,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "gates": {
            "arxiv_session_archive_attached": attachments["sessions"]["session_jsonl_count"] > 0,
            "preserved_seq2seq_storage_attached": attachments["preserved_seq2seq"]["exists"],
            "longevity_bundle_created": bundle.exists(),
            "no_checkpoint_loaded": True,
            "no_model_execution": True,
            "authority_closed": True,
        },
        "artifacts": {
            "attachments": str((OUT_DIR / "arxiv_recovery_attachments.json").relative_to(ROOT)),
            "attached_graph": str((OUT_DIR / "central_research_graph_with_arxiv_sources.json").relative_to(ROOT)),
            "longevity_bundle": str(bundle.relative_to(ROOT)),
            "doc": str(DOC_PATH.relative_to(ROOT)),
            "arxiv_mirror": mirror_path,
        },
        "next_best_step": "Use the attached graph to drive targeted recovery of remaining objective builders: intent/build, edit localization, patch operator, verifier repair, bounded decoder args, and denoise repair.",
        "notes": "Stage8624 links durable /arxiv storage into the central recovery graph and prepares long-lived docs. It is non-executing.",
    }
    write_json(SUMMARY_PATH, summary)
    print(json.dumps({"passed": True, "metrics": metrics, "summary": str(SUMMARY_PATH)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
