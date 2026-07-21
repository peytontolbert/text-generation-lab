#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12236_stage11977_candidate_audit"
SRC = ROOT / "runs/local/artifacts/stage11977_fail_to_pass_mutation_from_pass_roots/fail_to_pass_mutation_from_pass_roots.json"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    src = json.loads(SRC.read_text()) if SRC.exists() else {}
    cards = src.get("probe_cards") or []
    blocked = []
    admitted = []
    for card in cards:
        blockers = []
        if not card.get("admitted"):
            blockers.append("stage11977_card_not_admitted")
        for phase in ["baseline", "mutant", "restored"]:
            result = card.get(phase) or {}
            if result.get("timed_out") or result.get("returncode") == 124:
                blockers.append(f"{phase}_timed_out")
        if not card.get("mutation_applied"):
            blockers.append("mutation_not_applied")
        if blockers:
            blocked.append({"mutation": card.get("mutation"), "blockers": sorted(set(blockers)), "card": card})
        else:
            admitted.append(card)
    payload = {
        "stage": STAGE,
        "source_stage": "stage11977_fail_to_pass_mutation_from_pass_roots",
        "decision": "stage11977_blocked_no_external_repair_candidate" if not admitted else "stage11977_has_admitted_candidates",
        "admitted_count": len(admitted),
        "blocked_count": len(blocked),
        "blocked_reasons": sorted({b for row in blocked for b in row["blockers"]}),
        "training_allowed": False,
        "claim_boundary": "Audit only. Stage11977 does not overcome Stage12233 because its only candidate timed out in baseline/mutant/restored and admitted zero records.",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / "stage11977_candidate_audit.json", payload)
    write_json(OUT / "stage11977_blocked_cards.json", blocked)
    write_json(SUMMARY, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
