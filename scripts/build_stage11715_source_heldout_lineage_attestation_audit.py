#!/usr/bin/env python3
"""Audit Stage11714 seed roots for train/support overlap evidence.

This stage does not create source-heldout admissions. It scans existing JSONL
artifacts for exact seed row/root occurrences and separates train/support hits
from eval/validation/reference hits. A root with no train/support hit still needs
explicit source-heldout attestation before admission.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "runs/local/artifacts/stage11714_source_heldout_smoke_admission_preflight/source_heldout_smoke_preflight_row_cards.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts/stage11715_source_heldout_lineage_attestation_audit"
SUMMARY = ROOT / "runs/summaries/stage11715_source_heldout_lineage_attestation_audit.json"

TRAIN_PATH_MARKERS = (
    "train",
    "support",
    "probe_request",
    "training",
    "finetune",
)
NONTRAIN_PATH_MARKERS = (
    "strict_eval",
    "validation",
    "eval",
    "heldout",
    "harness",
    "audit",
    "comparison",
)
IGNORE_PATH_MARKERS = (
    "stage11713_source_heldout_smoke_materialization_request",
    "stage11714_source_heldout_smoke_admission_preflight",
    "stage11715_source_heldout_lineage_attestation_audit",
)
TRAIN_FIELD_VALUES = {"train", "train_support", "support", "train_support_only"}
NONTRAIN_FIELD_VALUES = {"strict_eval", "validation", "eval", "heldout", "strict_eval_candidate"}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def jsonl_files(needles: set[str]) -> list[Path]:
    # Use ripgrep fixed-string search to avoid a full Python crawl over the artifact tree.
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pattern_path = OUT_DIR / "lineage_scan_patterns.txt"
    pattern_path.write_text("\n".join(sorted(needles)) + "\n", encoding="utf-8")
    cmd = [
        "rg",
        "-l",
        "-F",
        "-f",
        str(pattern_path),
        "runs/local/artifacts",
        "-g",
        "*.jsonl",
    ]
    proc = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode not in (0, 1):
        raise RuntimeError(f"ripgrep failed: {proc.stderr}")
    files = [ROOT / line.strip() for line in proc.stdout.splitlines() if line.strip()]
    return [p for p in sorted(set(files)) if not any(marker in str(p) for marker in IGNORE_PATH_MARKERS)]


def classify_hit(path: Path, row: dict[str, Any]) -> str:
    path_s = str(path).lower()
    split_vals = {
        str(row.get("split", "")).lower(),
        str(row.get("split_role", "")).lower(),
        str(row.get("admit_role", "")).lower(),
    }
    train_support_only = row.get("train_support_only") is True
    if train_support_only or split_vals & TRAIN_FIELD_VALUES:
        return "train_like"
    if split_vals & NONTRAIN_FIELD_VALUES:
        return "nontrain_like"
    if any(marker in path_s for marker in TRAIN_PATH_MARKERS):
        return "train_like_path"
    if any(marker in path_s for marker in NONTRAIN_PATH_MARKERS):
        return "nontrain_like_path"
    return "unknown_context"


def row_strings(row: dict[str, Any]) -> set[str]:
    vals = set()
    for key in ("row_id", "root_id", "source_root_id", "root_lineage_key"):
        value = row.get(key)
        if isinstance(value, str) and value:
            vals.add(value)
    return vals


def main() -> None:
    if not CARDS.exists():
        raise FileNotFoundError(CARDS)
    cards = read_jsonl(CARDS)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)

    roots: dict[str, dict[str, Any]] = {}
    row_to_root: dict[str, str] = {}
    needles: set[str] = set()
    for card in cards:
        root = card.get("root_id") or card.get("root_lineage_candidate") or card.get("row_id")
        roots.setdefault(
            root,
            {
                "root_id": root,
                "language_family": card.get("language_family"),
                "repo_family": card.get("repo_family"),
                "seed_row_ids": [],
                "seed_tasks": set(),
            },
        )
        roots[root]["seed_row_ids"].append(card.get("row_id"))
        roots[root]["seed_tasks"].add(card.get("task_type"))
        row_to_root[card.get("row_id")] = root
        needles.add(root)
        needles.add(card.get("row_id"))
    needles = {n for n in needles if isinstance(n, str) and n}

    hits_by_root: dict[str, list[dict[str, Any]]] = defaultdict(list)
    files_scanned = 0
    rows_scanned = 0
    candidate_files = jsonl_files(needles)
    for path in candidate_files:
        try:
            fh = path.open("r", encoding="utf-8")
        except OSError:
            continue
        files_scanned += 1
        with fh:
            for line_no, line in enumerate(fh, start=1):
                rows_scanned += 1
                if not any(needle in line for needle in needles):
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                values = row_strings(row)
                matched = [needle for needle in needles if needle in values or needle in line]
                if not matched:
                    continue
                matched_roots = set()
                for needle in matched:
                    if needle in row_to_root:
                        matched_roots.add(row_to_root[needle])
                    elif needle in roots:
                        matched_roots.add(needle)
                    else:
                        for root in roots:
                            if needle and needle in root:
                                matched_roots.add(root)
                hit_kind = classify_hit(path, row)
                for root in matched_roots:
                    hits_by_root[root].append(
                        {
                            "path": str(path.relative_to(ROOT)),
                            "line_no": line_no,
                            "hit_kind": hit_kind,
                            "row_id": row.get("row_id"),
                            "root_id": row.get("root_id"),
                            "source_root_id": row.get("source_root_id"),
                            "split": row.get("split"),
                            "split_role": row.get("split_role"),
                            "train_support_only": row.get("train_support_only"),
                        }
                    )

    root_cards = []
    status_counts = Counter()
    for root, info in sorted(roots.items(), key=lambda kv: (kv[1]["language_family"], kv[1]["repo_family"], kv[0])):
        hits = hits_by_root.get(root, [])
        train_hits = [h for h in hits if h["hit_kind"].startswith("train_like")]
        nontrain_hits = [h for h in hits if h["hit_kind"].startswith("nontrain_like")]
        unknown_hits = [h for h in hits if h["hit_kind"] == "unknown_context"]
        if train_hits:
            status = "reject_train_or_support_overlap_found"
        elif hits:
            status = "no_train_overlap_found_in_scan_but_source_heldout_attestation_still_missing"
        else:
            status = "insufficient_evidence_no_hits_found"
        status_counts[status] += 1
        root_cards.append(
            {
                "root_id": root,
                "language_family": info["language_family"],
                "repo_family": info["repo_family"],
                "seed_row_ids": sorted(set(info["seed_row_ids"])),
                "seed_tasks": sorted(t for t in info["seed_tasks"] if t),
                "status": status,
                "hit_counts": {
                    "all": len(hits),
                    "train_like": len(train_hits),
                    "nontrain_like": len(nontrain_hits),
                    "unknown_context": len(unknown_hits),
                },
                "train_like_hits_sample": train_hits[:10],
                "nontrain_like_hits_sample": nontrain_hits[:10],
                "unknown_hits_sample": unknown_hits[:10],
                "attestation_requirement": [
                    "explicit source_heldout_admissible=true or equivalent source-heldout attestation",
                    "root_lineage_key stored on final rows",
                    "no train/support split hit in lineage audit",
                    "same-root sibling rows not used for training if final row is strict smoke eval",
                ],
            }
        )

    by_lang = defaultdict(Counter)
    for card in root_cards:
        by_lang[card["language_family"]][card["status"]] += 1

    attestable_roots = [
        c for c in root_cards if c["status"] == "no_train_overlap_found_in_scan_but_source_heldout_attestation_still_missing"
    ]
    minimal_attestation_candidates_by_lang = Counter(c["language_family"] for c in attestable_roots)

    artifact = {
        "stage": 11715,
        "stage_name": "source_heldout_lineage_attestation_audit",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision": "lineage_scan_complete_attestation_still_required",
        "passed": True,
        "candidate_files_from_rg": len(candidate_files),
        "files_scanned": files_scanned,
        "rows_scanned": rows_scanned,
        "root_count": len(root_cards),
        "status_counts": dict(status_counts),
        "status_by_language": {lang: dict(counter) for lang, counter in sorted(by_lang.items())},
        "attestation_candidate_counts_by_language": {
            lang: minimal_attestation_candidates_by_lang.get(lang, 0) for lang in ("python", "c_cpp", "rust")
        },
        "minimal_multilingual_attestation_candidate_ready": all(
            minimal_attestation_candidates_by_lang.get(lang, 0) > 0 for lang in ("python", "c_cpp", "rust")
        ),
        "claim_boundary": [
            "A no-train-overlap scan is not itself source-heldout admission.",
            "Roots with train/support hits should be rejected for strict smoke admission unless the hit is manually proven unrelated.",
            "Roots without train/support hits still require explicit source-heldout attestation and verifier-transition payloads before admission.",
        ],
        "next_repairs": [
            "For roots marked no_train_overlap_found, attach source-heldout attestation and root_lineage_key.",
            "For roots marked reject_train_or_support_overlap_found, replace with fresh roots or manually adjudicate false-positive hits.",
            "After attestation, rerun Stage11714-style row preflight for verifier-transition and option-shuffle blockers.",
        ],
        "source_artifacts": {
            "cards": str(CARDS.relative_to(ROOT)),
        },
        "outputs": {
            "artifact": "runs/local/artifacts/stage11715_source_heldout_lineage_attestation_audit/source_heldout_lineage_attestation_audit.json",
            "root_cards": "runs/local/artifacts/stage11715_source_heldout_lineage_attestation_audit/source_heldout_lineage_root_cards.jsonl",
            "summary": "runs/summaries/stage11715_source_heldout_lineage_attestation_audit.json",
        },
    }

    artifact_path = OUT_DIR / "source_heldout_lineage_attestation_audit.json"
    cards_path = OUT_DIR / "source_heldout_lineage_root_cards.jsonl"
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with cards_path.open("w", encoding="utf-8") as fh:
        for card in root_cards:
            # Convert sets left in info already normalized above.
            fh.write(json.dumps(card, sort_keys=True) + "\n")
    shutil.copyfile(artifact_path, SUMMARY)
    print(json.dumps({"artifact": str(artifact_path), "summary": str(SUMMARY), "status_counts": dict(status_counts)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
