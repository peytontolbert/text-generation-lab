#!/usr/bin/env python3
"""Mine replacement source-heldout smoke candidates excluding train/support roots.

Stage11715 rejected Stage11713 seeds because every selected root overlapped
train/support. This stage builds a train/support root blacklist from existing
JSONL artifacts, then filters the near-repairable pool for candidate roots not
seen in that blacklist.
"""

from __future__ import annotations

import json
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
NEAR = ROOT / "runs/local/artifacts/stage11519_source_heldout_smoke_candidate_miner/near_repairable_smoke_candidates.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts/stage11716_train_excluded_source_heldout_smoke_miner"
SUMMARY = ROOT / "runs/summaries/stage11716_train_excluded_source_heldout_smoke_miner.json"

TARGET_LANGS = ("python", "c_cpp", "rust")
TRAIN_PATH_MARKERS = ("train", "support", "training", "probe_request", "finetune")
IGNORE_DIR_MARKERS = (
    "stage11713_source_heldout_smoke_materialization_request",
    "stage11714_source_heldout_smoke_admission_preflight",
    "stage11715_source_heldout_lineage_attestation_audit",
    "stage11716_train_excluded_source_heldout_smoke_miner",
)
TRAIN_FIELD_VALUES = {"train", "train_support", "support", "train_support_only"}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def root_id(row: dict[str, Any]) -> str | None:
    for key in ("root_lineage_key", "source_root_id", "root_id"):
        val = row.get(key)
        if isinstance(val, str) and val:
            return val
    rid = row.get("row_id")
    if isinstance(rid, str) and "::" in rid:
        # Keep the broad stage/root prefix only when no stronger root field exists.
        parts = rid.split("::")
        if len(parts) >= 2:
            return "::".join(parts[:2])
    return None


def trainish_file(path: Path) -> bool:
    s = str(path).lower()
    return any(marker in s for marker in TRAIN_PATH_MARKERS) and not any(marker in s for marker in IGNORE_DIR_MARKERS)


def row_is_trainish(row: dict[str, Any]) -> bool:
    vals = {
        str(row.get("split", "")).lower(),
        str(row.get("split_role", "")).lower(),
        str(row.get("admit_role", "")).lower(),
    }
    return row.get("train_support_only") is True or bool(vals & TRAIN_FIELD_VALUES)


def build_train_blacklist() -> tuple[set[str], dict[str, Any]]:
    files = [p for p in sorted(ROOT.glob("runs/local/artifacts/**/*.jsonl")) if trainish_file(p)]
    roots: set[str] = set()
    rows_scanned = 0
    files_scanned = 0
    source_counts = Counter()
    for path in files:
        try:
            fh = path.open("r", encoding="utf-8")
        except OSError:
            continue
        files_scanned += 1
        with fh:
            for line in fh:
                rows_scanned += 1
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                # Path-level train/support files count unless row explicitly says eval/validation.
                split = str(row.get("split", "")).lower()
                split_role = str(row.get("split_role", "")).lower()
                explicit_eval = split in {"strict_eval", "validation", "eval", "heldout"} or split_role in {"strict_eval", "validation", "eval", "heldout"}
                if explicit_eval and not row_is_trainish(row):
                    continue
                rid = root_id(row)
                if rid:
                    roots.add(rid)
                    source_counts[str(path.relative_to(ROOT))] += 1
    return roots, {
        "trainish_files_scanned": files_scanned,
        "trainish_rows_scanned": rows_scanned,
        "blacklisted_roots": len(roots),
        "top_blacklist_sources": dict(source_counts.most_common(20)),
    }


def near_root(row: dict[str, Any]) -> str | None:
    return row.get("source_root_id") or row.get("root_id") or root_id(row)


def candidate_ok(row: dict[str, Any]) -> bool:
    if row.get("language_family") not in TARGET_LANGS:
        return False
    source_file = str(row.get("source_file") or "").lower()
    if any(marker in source_file for marker in TRAIN_PATH_MARKERS):
        return False
    if not near_root(row) or not row.get("repo_family"):
        return False
    if row.get("opaque_labels") is not True:
        return False
    if int(row.get("option_count") or 0) < 2:
        return False
    if row.get("prompt_target_value_leak") is not False:
        return False
    blockers = set(row.get("blockers") or [])
    if "singleton_or_missing_options" in blockers or "prompt_target_value_leak" in blockers:
        return False
    return True


def score(row: dict[str, Any]) -> tuple[int, int, int, int, int]:
    blockers = set(row.get("blockers") or [])
    task = row.get("task_type")
    return (
        5 if row.get("selected_test_anchor") or row.get("verifier_anchor") else 0,
        4 if "missing_verifier_or_selected_test_anchor" not in blockers else 0,
        3 if "source_heldout_not_attested" in blockers else 0,
        2 if task in {"verifier_outcome_semantic_transition", "evidence_citation", "patch_impact", "abstention_insufficient_evidence"} else 0,
        int(row.get("option_count") or 0),
    )


def overlaps_train(root: str, blacklist: set[str]) -> bool:
    if root in blacklist:
        return True
    # Catch row IDs that share a long root prefix with a blacklisted root.
    for b in blacklist:
        if len(root) > 32 and (root.startswith(b) or b.startswith(root)):
            return True
    return False


def mine_candidates(rows: list[dict[str, Any]], blacklist: set[str], max_roots_per_lang: int = 12) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    rejected = Counter()
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if row.get("language_family") not in TARGET_LANGS:
            continue
        if not candidate_ok(row):
            rejected["basic_quality"] += 1
            continue
        root = near_root(row)
        assert root is not None
        if overlaps_train(root, blacklist):
            rejected["train_overlap"] += 1
            continue
        grouped[row["language_family"]][root].append(row)

    selected: dict[str, list[dict[str, Any]]] = {lang: [] for lang in TARGET_LANGS}
    for lang in TARGET_LANGS:
        root_cards = []
        for root, root_rows in grouped[lang].items():
            root_rows = sorted(root_rows, key=lambda r: (score(r), r.get("row_id", "")), reverse=True)
            best = root_rows[0]
            root_cards.append({
                "root_id": root,
                "language_family": lang,
                "repo_family": best.get("repo_family"),
                "seed_rows": root_rows[: min(6, len(root_rows))],
                "best_score": score(best),
                "blockers": sorted({b for r in root_rows for b in (r.get("blockers") or [])}),
                "task_types": sorted({r.get("task_type") for r in root_rows if r.get("task_type")}),
            })
        root_cards.sort(key=lambda c: (c["best_score"], c["repo_family"], c["root_id"]), reverse=True)
        used_repos = set()
        for card in root_cards:
            if len(selected[lang]) >= max_roots_per_lang:
                break
            if card["repo_family"] in used_repos:
                continue
            selected[lang].append(card)
            used_repos.add(card["repo_family"])
        for card in root_cards:
            if len(selected[lang]) >= max_roots_per_lang:
                break
            if card not in selected[lang]:
                selected[lang].append(card)
    return selected, {
        "rejected": dict(rejected),
        "candidate_roots_after_exclusion": {lang: len(grouped[lang]) for lang in TARGET_LANGS},
    }


def request_from_card(card: dict[str, Any]) -> dict[str, Any]:
    rows = card["seed_rows"]
    return {
        "request_type": "fresh_train_excluded_source_heldout_smoke_candidate",
        "language_family": card["language_family"],
        "repo_family": card["repo_family"],
        "root_id": card["root_id"],
        "seed_row_ids": sorted({r.get("row_id") for r in rows if r.get("row_id")}),
        "seed_source_files": sorted({r.get("source_file") for r in rows if r.get("source_file")}),
        "task_types": card["task_types"],
        "current_blockers": card["blockers"],
        "train_overlap_status": "no_train_overlap_found_by_blacklist_scan",
        "required_repairs": [
            "attach explicit source_heldout_admissible=true or source-heldout attestation",
            "persist root_lineage_key and no-train/no-support split proof",
            "set deterministic_option_shuffle=true only after persisted option permutation is verified",
            "attach explicit has_verifier_row_or_transition=true payload",
            "preserve opaque labels, option_count>=2, and no target leak",
        ],
        "full_product_extension_required_repairs": [
            "attach patch_or_abstain signal",
            "emit harness_run_id",
            "emit same_task_pack_as_gemma12b=true",
            "emit tool_trace_spans",
            "emit verifier_results",
            "emit patch_minimality_or_abstain_scores",
        ],
    }


def main() -> None:
    if not NEAR.exists():
        raise FileNotFoundError(NEAR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    blacklist, blacklist_summary = build_train_blacklist()
    rows = read_jsonl(NEAR)
    selected, mine_summary = mine_candidates(rows, blacklist)
    requests = [request_from_card(card) for lang in TARGET_LANGS for card in selected[lang]]
    ready = all(len(selected[lang]) > 0 for lang in TARGET_LANGS)

    artifact = {
        "stage": 11716,
        "stage_name": "train_excluded_source_heldout_smoke_miner",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision": "train_excluded_source_heldout_candidates_ready" if ready else "train_excluded_source_heldout_candidates_insufficient",
        "passed": ready,
        "blacklist_summary": blacklist_summary,
        "mine_summary": mine_summary,
        "selected_root_counts": {lang: len(selected[lang]) for lang in TARGET_LANGS},
        "selected_roots_by_language": {
            lang: [
                {
                    "root_id": card["root_id"],
                    "repo_family": card["repo_family"],
                    "seed_rows": len(card["seed_rows"]),
                    "task_types": card["task_types"],
                    "blockers": card["blockers"],
                }
                for card in selected[lang]
            ]
            for lang in TARGET_LANGS
        },
        "request_count": len(requests),
        "claim_boundary": [
            "This stage mines candidates that do not hit the current train/support root blacklist; it does not admit them.",
            "No-train blacklist absence is weaker than explicit source-heldout attestation and must be followed by admission preflight.",
            "Selected roots still need verifier-transition payloads, deterministic option shuffle repair, and full-product patch/abstain extensions before broad claims.",
        ],
        "next_stage_acceptance": [
            "run Stage11714-style preflight on these replacement roots",
            "admit at least one python, c_cpp, and rust source-heldout smoke root",
            "attach same-manifest 100M and Gemma scoring only after admission",
        ],
        "source_artifacts": {
            "near_repairable": str(NEAR.relative_to(ROOT)),
        },
        "outputs": {
            "artifact": "runs/local/artifacts/stage11716_train_excluded_source_heldout_smoke_miner/train_excluded_source_heldout_smoke_miner.json",
            "requests_jsonl": "runs/local/artifacts/stage11716_train_excluded_source_heldout_smoke_miner/train_excluded_source_heldout_smoke_requests.jsonl",
            "summary": "runs/summaries/stage11716_train_excluded_source_heldout_smoke_miner.json",
        },
    }
    artifact_path = OUT_DIR / "train_excluded_source_heldout_smoke_miner.json"
    requests_path = OUT_DIR / "train_excluded_source_heldout_smoke_requests.jsonl"
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with requests_path.open("w", encoding="utf-8") as fh:
        for req in requests:
            fh.write(json.dumps(req, sort_keys=True) + "\n")
    shutil.copyfile(artifact_path, SUMMARY)
    print(json.dumps({"artifact": str(artifact_path), "summary": str(SUMMARY), "passed": ready, "selected_root_counts": artifact["selected_root_counts"], "request_count": len(requests)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
