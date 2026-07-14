#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11106
NAME = "stage11106_fresh_family_evidence_role_leak_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "fresh_family_evidence_role_leak_audit.json"

EVIDENCE_ROWS = ARTIFACTS / "stage11097_fresh_family_materialized_rows" / "evidence_candidate_rows.jsonl"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def main() -> None:
    rows = load_jsonl(EVIDENCE_ROWS)
    leakage_rows = []
    role_string_hits = Counter()

    for row in rows:
        prompt = str(row.get("prompt_text") or row.get("input_text") or "")
        prompt_prefix = prompt.split("Options:", 1)[0]
        option_values = [str(opt.get("value") or "") for opt in list(row.get("opaque_options") or [])]
        leaked_values = [value for value in option_values if value and value in prompt_prefix]
        if leaked_values:
            leakage_rows.append(
                {
                    "row_id": row.get("row_id"),
                    "repo_family": row.get("repo_family"),
                    "language_family": row.get("language_family"),
                    "target_text": row.get("target_text"),
                    "gold_value": (row.get("standalone_projection_source") or {}).get("gold_value"),
                    "leaked_option_values": leaked_values,
                }
            )
            for value in leaked_values:
                role_string_hits[value] += 1

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": False if leakage_rows else True,
        "claim_scope": [
            "Audit whether the stage11097 fresh-family evidence candidate rows leak semantic role names directly in the prompt before the option list.",
        ],
        "source_artifacts": {
            "evidence_rows": rel(EVIDENCE_ROWS),
        },
        "metrics": {
            "row_count": len(rows),
            "role_name_leak_rows": len(leakage_rows),
            "role_name_leak_fraction": (len(leakage_rows) / len(rows)) if rows else None,
            "role_string_hit_counts": dict(sorted(role_string_hits.items())),
            "by_language": dict(sorted(Counter(str(row.get("language_family") or "") for row in leakage_rows).items())),
            "by_repo_family": dict(sorted(Counter(str(row.get("repo_family") or "") for row in leakage_rows).items())),
        },
        "findings": [
            "Any evidence row that names the same semantic role strings in the visible ledger and the option list is shortcut-prone.",
            "These rows should not be admitted to train or heldout scoring until the visible evidence ledger is rewritten to remove role-name leakage.",
        ],
        "blocking_rows": leakage_rows,
        "next_best_step": "Rewrite the evidence candidate rows so the visible ledger uses opaque evidence IDs and natural descriptions rather than the semantic option values themselves.",
    }

    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
