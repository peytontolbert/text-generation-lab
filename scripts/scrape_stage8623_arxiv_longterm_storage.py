#!/usr/bin/env python3
"""Targeted scrape of /arxiv long-term recovery sources.

This script intentionally avoids broad corpus reads. It inventories likely
durable project storage locations and records paths/metadata only. It does not
copy checkpoints, run models, delete files, or authorize training.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / "stage8623_arxiv_longterm_storage_scrape"
SUMMARY_PATH = ROOT / "runs" / "summaries" / "stage8623_reconstructed_arxiv_longterm_storage_scrape.json"
DOC_PATH = ROOT / "docs" / "ARXIV_LONGTERM_STORAGE_RECOVERY_STAGE8623.md"

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

TARGET_ROOTS = [
    Path("/arxiv/code/sessions"),
    Path("/arxiv/preserved_checkpoints_20260609"),
    Path("/arxiv/TOLBERT_BRAIN"),
    Path("/arxiv/repositories/TOLBERT"),
    Path("/arxiv/repositories/tolbert-brain"),
]

IMPORTANT_NAME_FRAGMENTS = [
    "spine",
    "ledger",
    "registry",
    "summary",
    "curriculum",
    "compiler",
    "judge",
    "ranker",
    "manifest",
    "loss_mask",
    "telemetry",
    "trainer",
    "agentkernel",
    "pocketpal",
    "seq2seq",
    "encdec",
    "decoder",
    "checkpoint",
    "latest",
    "config",
    "README",
]

IMPORTANT_SUFFIXES = {
    ".json",
    ".jsonl",
    ".md",
    ".py",
    ".yaml",
    ".yml",
    ".toml",
    ".txt",
}

CHECKPOINT_SUFFIXES = {
    ".safetensors",
    ".pt",
    ".pth",
    ".bin",
    ".ckpt",
}

MAX_RECORDS_PER_ROOT = 5000
MAX_SAMPLE_BYTES = 64 * 1024


def stable_id(path: Path) -> str:
    return hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:16]


def classify_path(path: Path) -> str:
    name = path.name.lower()
    full = str(path).lower()
    if path.suffix.lower() in CHECKPOINT_SUFFIXES:
        return "checkpoint_or_weight"
    if "runs/summaries" in full or "summary" in name:
        return "stage_summary_or_summary_doc"
    if "ledger" in name or "/ledgers/" in full:
        return "ledger"
    if "manifest" in name:
        return "manifest"
    if "registry" in name:
        return "registry"
    if "trainer" in name or "train_" in name:
        return "trainer_script_or_config"
    if "curriculum" in name or "compiler" in name:
        return "curriculum_compiler"
    if "judge" in name or "ranker" in name:
        return "dataset_judge_or_ranker"
    if "spine" in name or "research" in name:
        return "research_spine_or_note"
    if "checkpoint" in full:
        return "checkpoint_metadata"
    if "session" in full:
        return "session_archive"
    return "candidate_recovery_file"


def should_record(path: Path) -> bool:
    name = path.name.lower()
    suffix = path.suffix.lower()
    if suffix in CHECKPOINT_SUFFIXES:
        return True
    if suffix in IMPORTANT_SUFFIXES and any(fragment in name for fragment in IMPORTANT_NAME_FRAGMENTS):
        return True
    full = str(path).lower()
    if "runs/ledgers" in full or "runs/summaries" in full:
        return True
    if "legacy_src/scripts/train_agentkernel_lite_encdec.py" in full:
        return True
    if "agentkernel_lite_encdec_manifest" in full:
        return True
    if "latest.json" in name:
        return True
    return False


def safe_stat(path: Path) -> dict[str, Any]:
    try:
        stat = path.stat()
    except OSError as exc:
        return {"stat_error": str(exc)}
    return {
        "size_bytes": stat.st_size,
        "mtime_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
    }


def sample_keywords(path: Path) -> dict[str, int]:
    if path.suffix.lower() not in IMPORTANT_SUFFIXES:
        return {}
    try:
        with path.open("rb") as f:
            raw = f.read(MAX_SAMPLE_BYTES)
    except OSError:
        return {}
    text = raw.decode("utf-8", errors="ignore").lower()
    keywords = [
        "agentkernel",
        "pocketpal",
        "100m",
        "seq2seq",
        "encdec",
        "decoder",
        "curriculum",
        "judge",
        "loss_mask",
        "authority",
        "gemma",
        "runtime",
        "stage",
        "manifest",
        "checkpoint",
    ]
    return {kw: text.count(kw) for kw in keywords if text.count(kw)}


def inventory_root(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records: list[dict[str, Any]] = []
    stats = {
        "root": str(root),
        "exists": root.exists(),
        "files_seen": 0,
        "records_kept": 0,
        "truncated": False,
        "errors": [],
    }
    if not root.exists():
        return records, stats

    try:
        walker = os.walk(root)
        for dirpath, dirnames, filenames in walker:
            dirnames[:] = [
                d
                for d in dirnames
                if d not in {".git", "node_modules", "__pycache__", ".venv", "venv"}
            ]
            for filename in filenames:
                path = Path(dirpath) / filename
                stats["files_seen"] += 1
                if not should_record(path):
                    continue
                record = {
                    "id": stable_id(path),
                    "path": str(path),
                    "root": str(root),
                    "class": classify_path(path),
                    "suffix": path.suffix.lower(),
                    **safe_stat(path),
                    "keyword_hits": sample_keywords(path),
                }
                records.append(record)
                stats["records_kept"] += 1
                if len(records) >= MAX_RECORDS_PER_ROOT:
                    stats["truncated"] = True
                    return records, stats
    except OSError as exc:
        stats["errors"].append(str(exc))
    return records, stats


def write_doc(records: list[dict[str, Any]], root_stats: list[dict[str, Any]], metrics: dict[str, Any]) -> None:
    by_class = Counter(record["class"] for record in records)
    by_root = Counter(record["root"] for record in records)
    important = [
        record
        for record in records
        if record["class"] in {
            "ledger",
            "manifest",
            "registry",
            "trainer_script_or_config",
            "curriculum_compiler",
            "dataset_judge_or_ranker",
            "research_spine_or_note",
            "checkpoint_or_weight",
        }
    ][:80]

    DOC_PATH.write_text(
        "\n".join(
            [
                "# Stage8623 `/arxiv` Long-Term Storage Recovery",
                "",
                "This is a targeted inventory of durable `/arxiv` locations that may contain old sessions, ledgers, manifests, trainer configs, checkpoint metadata, and research-spine material. It records paths and metadata only. It does not copy checkpoints, run models, or authorize training.",
                "",
                "## Target Roots",
                "",
                *[f"- `{stats['root']}`: exists={stats['exists']}, files_seen={stats['files_seen']}, records_kept={stats['records_kept']}, truncated={stats['truncated']}" for stats in root_stats],
                "",
                "## Counts By Class",
                "",
                *[f"- `{klass}`: {count}" for klass, count in sorted(by_class.items())],
                "",
                "## Counts By Root",
                "",
                *[f"- `{root}`: {count}" for root, count in sorted(by_root.items())],
                "",
                "## High-Value Recovered Paths",
                "",
                *[f"- `{record['class']}` `{record['path']}`" for record in important],
                "",
                "## Metrics",
                "",
                "```json",
                json.dumps(metrics, indent=2, sort_keys=True),
                "```",
                "",
                "## Next Step",
                "",
                "Attach selected high-value paths to the central research graph as recovery-source nodes and use them to rebuild missing manifest builders or trainer contracts. Keep checkpoint paths as references only until an explicit execution/training gate is passed.",
                "",
            ]
        )
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOC_PATH.parent.mkdir(parents=True, exist_ok=True)

    all_records: list[dict[str, Any]] = []
    root_stats: list[dict[str, Any]] = []
    for root in TARGET_ROOTS:
        records, stats = inventory_root(root)
        all_records.extend(records)
        root_stats.append(stats)

    all_records.sort(key=lambda r: (r["class"], r["path"]))
    (OUT_DIR / "arxiv_longterm_sources.json").write_text(json.dumps(all_records, indent=2, sort_keys=True))
    with (OUT_DIR / "arxiv_longterm_sources.jsonl").open("w") as f:
        for record in all_records:
            f.write(json.dumps(record, sort_keys=True) + "\n")
    (OUT_DIR / "arxiv_root_stats.json").write_text(json.dumps(root_stats, indent=2, sort_keys=True))

    by_class = Counter(record["class"] for record in all_records)
    by_root = Counter(record["root"] for record in all_records)
    keyword_totals: Counter[str] = Counter()
    for record in all_records:
        keyword_totals.update(record.get("keyword_hits", {}))

    metrics = {
        "target_roots": len(TARGET_ROOTS),
        "existing_roots": sum(1 for stats in root_stats if stats["exists"]),
        "files_seen": sum(int(stats["files_seen"]) for stats in root_stats),
        "records_kept": len(all_records),
        "classes": dict(sorted(by_class.items())),
        "records_by_root": dict(sorted(by_root.items())),
        "keyword_totals": dict(sorted(keyword_totals.items())),
        "checkpoint_or_weight_paths": by_class.get("checkpoint_or_weight", 0),
        "ledger_paths": by_class.get("ledger", 0),
        "manifest_paths": by_class.get("manifest", 0),
        "trainer_script_or_config_paths": by_class.get("trainer_script_or_config", 0),
    }
    write_doc(all_records, root_stats, metrics)

    summary = {
        "stage": 8623,
        "stage_name": "stage8623_reconstructed_arxiv_longterm_storage_scrape",
        "passed": True,
        "reconstructed": True,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "gates": {
            "targeted_arxiv_inventory_written": True,
            "no_model_execution": True,
            "no_checkpoint_copy": True,
            "authority_closed": True,
        },
        "artifacts": {
            "sources_json": str((OUT_DIR / "arxiv_longterm_sources.json").relative_to(ROOT)),
            "sources_jsonl": str((OUT_DIR / "arxiv_longterm_sources.jsonl").relative_to(ROOT)),
            "root_stats": str((OUT_DIR / "arxiv_root_stats.json").relative_to(ROOT)),
            "doc": str(DOC_PATH.relative_to(ROOT)),
        },
        "next_best_step": "Mirror longevity docs under /arxiv in a non-destructive stage directory, then attach selected recovery sources to the central graph.",
        "notes": "Targeted /arxiv scrape records durable paths only. Checkpoints are referenced, not copied or loaded.",
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, sort_keys=True))
    print(json.dumps({"passed": True, "metrics": metrics, "summary": str(SUMMARY_PATH)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
