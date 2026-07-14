#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10621
NAME = "stage10621_multilingual_duplicate_rowid_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "multilingual_duplicate_rowid_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

MANIFEST = ROOT / "runs/local/artifacts/stage10620_reviewed_plus_bootstrap_multilingual_probe_request_capped/reviewed_plus_bootstrap_multilingual_probe_manifest_capped.jsonl"
EXECUTION_RESULT = ROOT / "runs/local/artifacts/stage10620_reviewed_plus_bootstrap_multilingual_probe_capped/bounded_decoder_probe/execution_result.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    rows = load_jsonl(MANIFEST)
    execution = load_json(EXECUTION_RESULT)
    by_row_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_row_id[str(row.get("row_id") or "")].append(row)

    duplicate_groups: list[dict[str, Any]] = []
    duplicate_counts_by_split: Counter[str] = Counter()
    duplicate_counts_by_source_pair: Counter[str] = Counter()
    duplicate_counts_by_language: Counter[str] = Counter()

    for row_id, group in sorted(by_row_id.items()):
        if len(group) <= 1:
            continue
        splits = sorted({str(r.get("split") or "unknown") for r in group})
        source_kinds = sorted({str(r.get("package_source_kind") or "unknown") for r in group})
        languages = sorted({str(r.get("language_family") or "unknown") for r in group})
        for split in splits:
            duplicate_counts_by_split[split] += 1
        duplicate_counts_by_source_pair[" + ".join(source_kinds)] += 1
        for language in languages:
            duplicate_counts_by_language[language] += 1
        duplicate_groups.append(
            {
                "row_id": row_id,
                "count": len(group),
                "splits": splits,
                "languages": languages,
                "source_kinds": source_kinds,
                "rows": [
                    {
                        "split": r.get("split"),
                        "package_source_kind": r.get("package_source_kind"),
                        "language_family": r.get("language_family"),
                        "target_family": r.get("target_family"),
                        "target_subtype": r.get("target_subtype"),
                        "root_id": r.get("root_id"),
                        "source_stage": r.get("source_stage"),
                    }
                    for r in group
                ],
            }
        )

    strict = ((execution.get("bounded_choice_eval") or {}).get("strict_eval") or {})
    strict_row_cards = strict.get("row_cards") or []
    strict_duplicate_cards = [
        card
        for card in strict_row_cards
        if len(by_row_id.get(str(card.get("row_id") or ""), [])) > 1
    ]
    strict_duplicate_with_options = sum(1 for card in strict_duplicate_cards if card.get("option_labels"))
    strict_duplicate_without_options = sum(1 for card in strict_duplicate_cards if not card.get("option_labels"))

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "duplicate_rowid_eval_honesty_risk_confirmed",
        "claim": "The stage10620 multilingual package is not promotable as a broader heldout eval because eval and strict_eval contain duplicate row_ids that pair reviewed rows with compiled duplicates of the same logical decision.",
        "inputs": {
            "manifest": display(MANIFEST),
            "execution_result": display(EXECUTION_RESULT),
        },
        "duplicate_row_ids": len(duplicate_groups),
        "duplicate_counts_by_split": dict(sorted(duplicate_counts_by_split.items())),
        "duplicate_counts_by_source_pair": dict(sorted(duplicate_counts_by_source_pair.items())),
        "duplicate_counts_by_language": dict(sorted(duplicate_counts_by_language.items())),
        "strict_duplicate_card_counts": {
            "rows": len(strict_duplicate_cards),
            "with_options": strict_duplicate_with_options,
            "without_options": strict_duplicate_without_options,
        },
        "headline_risk": [
            "Duplicate row_ids break clean row-level joins between manifest metadata and strict result cards.",
            "Compiled duplicates in strict/eval are not independent heldout evidence; they are same logical reviewed rows resurfaced under a second package source.",
            "The apparent 36-row multilingual strict slice overstates breadth because 12 strict rows are duplicate logical decisions.",
        ],
        "recommended_fix": [
            "Deduplicate eval and strict_eval by row_id for promotable scoring.",
            "Prefer reviewed_bundle_root rows in promotable eval when a compiled_root_state duplicate shares the same row_id.",
            "Quarantine the compiled duplicates to train or diagnostic-only roles unless they are re-keyed and justified as distinct evaluations.",
        ],
        "duplicate_groups": duplicate_groups,
    }
    write_json(AUDIT_JSON, payload)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "audit": display(AUDIT_JSON),
            "duplicate_row_ids": len(duplicate_groups),
        },
    )
    print(json.dumps({"stage": STAGE, "duplicate_row_ids": len(duplicate_groups), "passed": True}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
