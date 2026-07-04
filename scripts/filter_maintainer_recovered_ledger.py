#!/usr/bin/env python3
"""Filter recovered session variable ledger to maintainer-relevant variables."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


KEEP_TERMS = [
    "ACTION",
    "EVIDENCE",
    "SAFE",
    "UNSAFE",
    "RETRIEVE",
    "HOLD",
    "REPAIR",
    "BUILD",
    "IMPORT",
    "PATCH",
    "VERIFY",
    "VERIFIER",
    "SYMBOL",
    "TARGET",
    "SOURCE",
    "DECODER",
    "RUNTIME",
    "GEMMA",
    "AUTH",
    "BODY",
    "MATERIAL",
    "CANDIDATE",
    "ACCEPT",
    "REJECT",
    "ROUTE",
    "POLICY",
    "INTENT",
    "GRAPH",
    "STATE",
    "LOSS",
]

DROP_TERMS = [
    "RTM",
    "URL",
    "MOBILE",
    "BROWSER",
    "HF_HOME",
    "LD_LIBRARY",
    "CACHE",
    "NATIVE_APP",
    "GL_",
    "SKILL",
    "CSS",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def keep_label(label: str) -> bool:
    if any(term in label for term in DROP_TERMS):
        return False
    return any(term in label for term in KEEP_TERMS)


def filter_pairs(pairs: list[list[Any]], limit: int = 160) -> list[dict[str, Any]]:
    out = []
    for label, count in pairs:
        if isinstance(label, str) and keep_label(label):
            out.append({"label": label, "count": count})
        if len(out) >= limit:
            break
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", default="runs/local/artifacts/stage8615_recovered_variable_ledger/recovered_variable_ledger.json")
    parser.add_argument("--output", default="runs/local/artifacts/stage8615_recovered_variable_ledger/maintainer_filtered_ledger.json")
    args = parser.parse_args()
    ledger = load_json(Path(args.ledger))
    filtered = {
        "bucket_counts": ledger.get("bucket_counts", {}),
        "maintainer_labels": filter_pairs(ledger.get("top_all_caps_labels", []), 220),
        "stage_ids": ledger.get("top_stage_ids", [])[:160],
        "script_names": ledger.get("top_script_names", [])[:160],
        "summary_names": ledger.get("top_summary_names", [])[:160],
        "json_keys": [
            {"key": key, "count": count}
            for key, count in ledger.get("top_json_keys", [])
            if any(term.lower() in key.lower() for term in ["action", "evidence", "route", "loss", "label", "verifier", "decoder", "authority", "surface", "intent", "target", "source", "split", "metric"])
        ][:220],
    }
    write_json(Path(args.output), filtered)
    print(json.dumps({
        "maintainer_labels": filtered["maintainer_labels"][:40],
        "json_keys": filtered["json_keys"][:40],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
