#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer

STAGE = 10535
NAME = "stage10535_bootstrap_package_balance_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
AUDIT_JSON = OUT_DIR / "bootstrap_package_balance_audit.json"

TRAIN_ROWS = ROOT / "runs/local/artifacts/stage10530_leak_clean_root_based_multitarget_probe_request/leak_clean_root_based_multitarget_probe_manifest.jsonl"
STRICT_ROWS = ROOT / "runs/local/artifacts/stage10528_cleaned_heldout_anticheat_successor/strict_eval_rows.jsonl"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


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


def count_by(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    counter = Counter(str(row.get(field) or "unknown") for row in rows)
    return dict(sorted(counter.items()))


def roots_by_language(rows: list[dict[str, Any]]) -> dict[str, int]:
    buckets: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        buckets[str(row.get("language_family") or "unknown")].add(str(row.get("root_id") or ""))
    return {key: len(value) for key, value in sorted(buckets.items())}


def repos_by_language(rows: list[dict[str, Any]]) -> dict[str, int]:
    buckets: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        buckets[str(row.get("language_family") or "unknown")].add(str(row.get("repo_id") or ""))
    return {key: len(value) for key, value in sorted(buckets.items())}


def cross_counts(rows: list[dict[str, Any]], a: str, b: str) -> dict[str, dict[str, int]]:
    buckets: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        buckets[str(row.get(a) or "unknown")][str(row.get(b) or "unknown")] += 1
    return {key: dict(sorted(counter.items())) for key, counter in sorted(buckets.items())}


def anti_cheat_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "prompt_target_leak_true": sum(1 for row in rows if bool((row.get("anti_cheat") or {}).get("prompt_target_leak"))),
        "source_heldout_admissible_true": sum(1 for row in rows if bool((row.get("anti_cheat") or {}).get("source_heldout_admissible"))),
        "same_root_train_eval_forbidden_true": sum(1 for row in rows if bool((row.get("anti_cheat") or {}).get("same_root_train_eval_forbidden"))),
    }


def token_len(text: str, tokenizer: AgentKernelBPETokenizer) -> int:
    return len(tokenizer.encode(text, max_length=4096))


def cap_pressure(rows: list[dict[str, Any]], tokenizer: AgentKernelBPETokenizer, cap: int) -> dict[str, Any]:
    buckets: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get("target_subtype") or "unknown")].append(token_len(str(row.get("target_text") or ""), tokenizer))
    out: dict[str, Any] = {}
    for subtype, lengths in sorted(buckets.items()):
        lengths.sort()
        rows_over = sum(1 for length in lengths if length > cap)
        out[subtype] = {
            "rows": len(lengths),
            "rows_over_cap": rows_over,
            "max": max(lengths),
            "p50": lengths[len(lengths) // 2],
            "p90": lengths[min(len(lengths) - 1, int(len(lengths) * 0.9))],
            "p95": lengths[min(len(lengths) - 1, int(len(lengths) * 0.95))],
        }
    return out


def missing_language_targets(rows: list[dict[str, Any]], languages: list[str], target_subtypes: list[str]) -> dict[str, list[str]]:
    seen = {(str(row.get("language_family") or ""), str(row.get("target_subtype") or "")) for row in rows}
    gaps: dict[str, list[str]] = {}
    for language in languages:
        missing = [subtype for subtype in target_subtypes if (language, subtype) not in seen]
        if missing:
            gaps[language] = missing
    return gaps


def main() -> None:
    train_rows = load_jsonl(TRAIN_ROWS)
    strict_rows = load_jsonl(STRICT_ROWS)
    tokenizer = AgentKernelBPETokenizer(TOKENIZER_JSON, TOKENIZER_CONFIG)

    languages = sorted({str(row.get("language_family") or "unknown") for row in train_rows + strict_rows})
    target_subtypes = sorted({str(row.get("target_subtype") or "unknown") for row in train_rows + strict_rows})

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Package-balance audit for the leak-clean root-based bootstrap manifest and the cleaned strict heldout slice.",
            "Quantifies language, root, repo, and target-subtype coverage plus decoder-cap pressure.",
            "This is a dataset/runtime planning artifact, not a model-quality result.",
        ],
        "source_artifacts": {
            "train_rows": str(TRAIN_ROWS.relative_to(ROOT)),
            "strict_rows": str(STRICT_ROWS.relative_to(ROOT)),
        },
        "languages": languages,
        "target_subtypes": target_subtypes,
        "train": {
            "rows": len(train_rows),
            "unique_roots": len({str(row.get("root_id") or "") for row in train_rows}),
            "unique_repos": len({str(row.get("repo_id") or "") for row in train_rows}),
            "language_counts": count_by(train_rows, "language_family"),
            "target_subtype_counts": count_by(train_rows, "target_subtype"),
            "language_by_target_subtype": cross_counts(train_rows, "language_family", "target_subtype"),
            "roots_by_language": roots_by_language(train_rows),
            "repos_by_language": repos_by_language(train_rows),
            "anti_cheat": anti_cheat_counts(train_rows),
            "decoder_cap_1024": cap_pressure(train_rows, tokenizer, 1024),
        },
        "strict": {
            "rows": len(strict_rows),
            "unique_roots": len({str(row.get("root_id") or "") for row in strict_rows}),
            "unique_repos": len({str(row.get("repo_id") or "") for row in strict_rows}),
            "language_counts": count_by(strict_rows, "language_family"),
            "target_subtype_counts": count_by(strict_rows, "target_subtype"),
            "language_by_target_subtype": cross_counts(strict_rows, "language_family", "target_subtype"),
            "roots_by_language": roots_by_language(strict_rows),
            "repos_by_language": repos_by_language(strict_rows),
            "anti_cheat": anti_cheat_counts(strict_rows),
            "decoder_cap_1024": cap_pressure(strict_rows, tokenizer, 1024),
        },
        "gaps": {
            "strict_missing_language_target_subtypes": missing_language_targets(strict_rows, languages, target_subtypes),
            "train_missing_language_target_subtypes": missing_language_targets(train_rows, languages, target_subtypes),
            "strict_single_repo_languages": sorted(
                language for language, count in repos_by_language(strict_rows).items() if count <= 1
            ),
        },
        "next_best_step": (
            "Expand the heldout slice with repo-diverse Rust/Web/Python/C++ roots and add heldout verifier_outcome "
            "and patch_sketch targets before treating the root-based seq2seq path as a broad multilingual maintainer benchmark."
        ),
    }
    write_json(AUDIT_JSON, payload)
    write_json(SUMMARY, payload)


if __name__ == "__main__":
    main()
