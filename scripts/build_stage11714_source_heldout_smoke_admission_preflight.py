#!/usr/bin/env python3
"""Preflight Stage11713 source-heldout smoke requests against actual seed rows.

This stage attempts no model execution and does not fabricate source-heldout
attestation. It loads the requested seed rows, records which fields already
exist, and emits row-level blockers required before admission.
"""

from __future__ import annotations

import json
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REQUESTS = ROOT / "runs/local/artifacts/stage11713_source_heldout_smoke_materialization_request/source_heldout_smoke_materialization_requests.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts/stage11714_source_heldout_smoke_admission_preflight"
SUMMARY = ROOT / "runs/summaries/stage11714_source_heldout_smoke_admission_preflight.json"

LANGS = ("python", "c_cpp", "rust")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def index_sources(requests: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    wanted = {rid for req in requests for rid in req.get("seed_row_ids", [])}
    sources = sorted({source for req in requests for source in req.get("seed_source_files", [])})
    found: dict[str, dict[str, Any]] = {}
    found_sources: dict[str, list[str]] = defaultdict(list)
    for source in sources:
        path = ROOT / source
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                row_id = row.get("row_id")
                if row_id in wanted:
                    found.setdefault(row_id, row)
                    found_sources[row_id].append(source)
    for row_id, row in found.items():
        row["_found_sources"] = sorted(found_sources[row_id])
    return found


def nested_shuffle(row: dict[str, Any]) -> bool | None:
    anti = row.get("anti_cheat") or {}
    if "deterministic_option_shuffle" in row:
        return row.get("deterministic_option_shuffle")
    if isinstance(anti, dict) and "deterministic_option_shuffle" in anti:
        return anti.get("deterministic_option_shuffle")
    return None


def root_lineage(row: dict[str, Any], req: dict[str, Any]) -> str | None:
    return row.get("root_lineage_key") or row.get("source_root_id") or req.get("root_id")


def row_blockers(row: dict[str, Any] | None, req: dict[str, Any], row_id: str) -> list[str]:
    if row is None:
        return ["seed_row_not_found"]
    blockers: list[str] = []
    anti = row.get("anti_cheat") or {}
    if row.get("source_heldout_admissible") is not True:
        blockers.append("source_heldout_admissible_not_true")
    if not root_lineage(row, req):
        blockers.append("missing_root_lineage_key_or_source_root")
    if row.get("train_support_only") is True:
        blockers.append("train_support_only_true")
    if row.get("split") in {"train", "train_support"} or row.get("split_role") in {"train", "train_support"}:
        blockers.append("train_split_marker_present")
    if not (row.get("selected_test_anchor") is True or row.get("verifier_anchor") is True):
        blockers.append("missing_selected_test_or_verifier_anchor")
    if row.get("has_verifier_row_or_transition") is not True:
        blockers.append("missing_explicit_has_verifier_row_or_transition_true")
    shuffle = nested_shuffle(row)
    if shuffle is not True:
        blockers.append("deterministic_option_shuffle_not_true")
    if not row.get("opaque_options") or len(row.get("opaque_options") or []) < 2:
        blockers.append("missing_or_singleton_opaque_options")
    if row.get("prompt_target_value_leak") is True:
        blockers.append("prompt_target_value_leak_true")
    if isinstance(anti, dict) and anti.get("requires_review_before_training") is True:
        blockers.append("requires_review_before_training")
    if isinstance(anti, dict) and anti.get("heuristic_gold_value") is True:
        blockers.append("heuristic_gold_value_requires_review")
    if row.get("target_text") in (None, "") and row.get("expected_label") in (None, ""):
        blockers.append("missing_target_text_or_expected_label")
    # Needed for the full-product harness path, but not for standalone smoke admission.
    if row.get("has_patch_or_abstain_row") is not True:
        blockers.append("full_product_missing_patch_or_abstain_row")
    return blockers


def row_card(row: dict[str, Any] | None, req: dict[str, Any], row_id: str) -> dict[str, Any]:
    blockers = row_blockers(row, req, row_id)
    if row is None:
        return {
            "row_id": row_id,
            "language_family": req.get("language_family"),
            "repo_family": req.get("repo_family"),
            "root_id": req.get("root_id"),
            "status": "blocked",
            "blockers": blockers,
        }
    standalone_blockers = [b for b in blockers if not b.startswith("full_product_")]
    return {
        "row_id": row_id,
        "language_family": row.get("language_family") or req.get("language_family"),
        "repo_family": row.get("repo_family") or req.get("repo_family"),
        "root_id": row.get("source_root_id") or req.get("root_id"),
        "root_lineage_candidate": root_lineage(row, req),
        "task_type": row.get("task_type"),
        "split": row.get("split"),
        "split_role": row.get("split_role"),
        "seed_sources": row.get("_found_sources", []),
        "status": "admissible" if not standalone_blockers else "blocked",
        "standalone_blockers": standalone_blockers,
        "full_product_blockers": [b for b in blockers if b.startswith("full_product_")],
        "all_blockers": blockers,
        "field_state": {
            "source_heldout_admissible": row.get("source_heldout_admissible"),
            "root_lineage_present": bool(root_lineage(row, req)),
            "train_support_only": row.get("train_support_only"),
            "selected_test_anchor": row.get("selected_test_anchor"),
            "verifier_anchor": row.get("verifier_anchor"),
            "has_verifier_row_or_transition": row.get("has_verifier_row_or_transition"),
            "deterministic_option_shuffle": nested_shuffle(row),
            "opaque_option_count": len(row.get("opaque_options") or []),
            "target_present": bool(row.get("target_text") or row.get("expected_label")),
            "has_patch_or_abstain_row": row.get("has_patch_or_abstain_row"),
        },
        "repair_hint": {
            "can_repair_shuffle_from_existing_options": bool(row.get("opaque_options")) and nested_shuffle(row) is not True,
            "needs_external_attestation": row.get("source_heldout_admissible") is not True,
            "needs_verifier_transition_flag_or_payload": row.get("has_verifier_row_or_transition") is not True,
            "needs_full_product_patch_or_abstain": row.get("has_patch_or_abstain_row") is not True,
        },
    }


def main() -> None:
    if not REQUESTS.exists():
        raise FileNotFoundError(REQUESTS)
    requests = read_jsonl(REQUESTS)
    found = index_sources(requests)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)

    cards: list[dict[str, Any]] = []
    for req in requests:
        for row_id in req.get("seed_row_ids", []):
            cards.append(row_card(found.get(row_id), req, row_id))

    status_counts = Counter(card["status"] for card in cards)
    blockers = Counter(b for card in cards for b in card.get("all_blockers", card.get("blockers", [])))
    blockers_by_lang: dict[str, Counter[str]] = defaultdict(Counter)
    for card in cards:
        lang = card.get("language_family", "unknown")
        for blocker in card.get("all_blockers", card.get("blockers", [])):
            blockers_by_lang[lang][blocker] += 1

    admitted_by_lang = Counter(card.get("language_family") for card in cards if card["status"] == "admissible")
    minimal_ready = all(admitted_by_lang.get(lang, 0) > 0 for lang in LANGS)

    artifact = {
        "stage": 11714,
        "stage_name": "source_heldout_smoke_admission_preflight",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision": "no_source_heldout_smoke_rows_admitted" if not minimal_ready else "source_heldout_smoke_rows_preflight_admitted",
        "passed": True,
        "minimal_multilingual_smoke_ready": minimal_ready,
        "request_count": len(requests),
        "seed_row_count": len(cards),
        "seed_rows_found": len(found),
        "status_counts": dict(status_counts),
        "admissible_by_language": {lang: admitted_by_lang.get(lang, 0) for lang in LANGS},
        "blockers": dict(blockers.most_common()),
        "blockers_by_language": {lang: dict(counter.most_common()) for lang, counter in sorted(blockers_by_lang.items())},
        "next_repairs": [
            "Provide explicit source-heldout/no-train attestation for selected roots or reject them.",
            "Promote root_lineage_key/source_root_id into every candidate row.",
            "Set deterministic_option_shuffle=true only after persisted option permutation is verified.",
            "Attach explicit has_verifier_row_or_transition=true payload, not just selected_test_anchor/verifier_anchor booleans.",
            "For full-product harness claims, attach patch_or_abstain rows plus harness writeback fields.",
        ],
        "claim_boundary": [
            "This is an admission preflight, not a model run and not an admission stage.",
            "No source-heldout smoke row is admitted unless standalone_blockers is empty.",
            "Full-product harness readiness additionally requires patch/abstain and writeback fields.",
        ],
        "source_artifacts": {
            "requests": str(REQUESTS.relative_to(ROOT)),
        },
        "outputs": {
            "artifact": "runs/local/artifacts/stage11714_source_heldout_smoke_admission_preflight/source_heldout_smoke_admission_preflight.json",
            "row_cards": "runs/local/artifacts/stage11714_source_heldout_smoke_admission_preflight/source_heldout_smoke_preflight_row_cards.jsonl",
            "summary": "runs/summaries/stage11714_source_heldout_smoke_admission_preflight.json",
        },
    }

    artifact_path = OUT_DIR / "source_heldout_smoke_admission_preflight.json"
    cards_path = OUT_DIR / "source_heldout_smoke_preflight_row_cards.jsonl"
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with cards_path.open("w", encoding="utf-8") as fh:
        for card in cards:
            fh.write(json.dumps(card, sort_keys=True) + "\n")
    shutil.copyfile(artifact_path, SUMMARY)
    print(json.dumps({"artifact": str(artifact_path), "summary": str(SUMMARY), "minimal_ready": minimal_ready, "status_counts": dict(status_counts)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
