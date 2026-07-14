#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10880
NAME = "stage10880_evidence_alias_anticheat_audit"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "evidence_alias_anticheat_audit.json"

BASE_DIR = ARTIFACTS / "stage10864_residual_family_support_package_plus_second_python_materialized"
SPLITS = {
    "train": BASE_DIR / "agentkernel_lite_encdec_train.jsonl",
    "validation": BASE_DIR / "agentkernel_lite_encdec_validation.jsonl",
    "strict_eval": BASE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def extract_duplicate_groups(prompt_text: str) -> list[dict[str, Any]]:
    if "Evidence:\n" not in prompt_text or "\nOptions:\n" not in prompt_text:
        return []
    evidence_block = prompt_text.split("Evidence:\n", 1)[1].split("\nOptions:\n", 1)[0]
    groups: dict[tuple[str, str], list[str]] = {}
    for line in evidence_block.splitlines():
        if " [" not in line or "]: " not in line:
            continue
        key = line.split(" [", 1)[0].strip()
        remainder = line.split(" [", 1)[1]
        path, text = remainder.split("]: ", 1)
        sig = (path.strip(), text.strip())
        groups.setdefault(sig, []).append(key)
    duplicate_groups = []
    for (path, text), keys in groups.items():
        if len(keys) > 1:
            duplicate_groups.append(
                {
                    "path": path,
                    "keys": keys,
                    "text_sha1": hashlib.sha1(text.encode("utf-8")).hexdigest()[:12],
                }
            )
    return duplicate_groups


def main() -> None:
    blocked_rows = []
    counts = Counter()
    by_split = Counter()
    by_language = Counter()

    for split, path in SPLITS.items():
        for row in load_jsonl(path):
            if row.get("task_type") != "evidence_citation":
                continue
            duplicate_groups = extract_duplicate_groups(str(row.get("prompt_text") or ""))
            if not duplicate_groups:
                continue
            counts["blocked_rows"] += 1
            by_split[split] += 1
            by_language[str(row.get("language_family") or "unknown")] += 1
            blocked_rows.append(
                {
                    "split": split,
                    "row_id": str(row["row_id"]),
                    "language_family": str(row.get("language_family") or "unknown"),
                    "gold_value": str(((row.get("standalone_projection_source") or {}).get("gold_value")) or ""),
                    "duplicate_visible_evidence_groups": duplicate_groups,
                }
            )

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "evidence_alias_anticheat_audited",
        "claim_scope": [
            "Audit reviewed v2.7 evidence_citation rows for duplicated visible evidence material assigned to different semantic labels.",
            "Flag rows where the visible prompt does not support a unique evidence-role distinction because multiple options reuse the same path/text payload.",
        ],
        "metrics": {
            "blocked_rows": counts["blocked_rows"],
            "blocked_by_split": dict(sorted(by_split.items())),
            "blocked_by_language": dict(sorted(by_language.items())),
        },
        "blocked_rows": blocked_rows,
        "diagnosis": [
            "The current strict Rust tokenizers evidence row is not a clean semantic distinction because candidate_change_surface and symptom_or_call_path_analogue share the same visible file/text span.",
            "A similar aliasing pattern exists in the validation Rust candle-core evidence row.",
            "Training rows with the same aliasing pattern should be quarantined from promotable evidence-role claims and ideally removed from support packages that aim to teach those distinctions.",
        ],
        "next_best_step": "Build a duplicate-evidence quarantine successor package that removes aliased evidence rows from train/validation/strict, then replenish Rust evidence evaluation with a fresh reviewed root whose visible evidence keys are actually distinguishable.",
    }

    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
