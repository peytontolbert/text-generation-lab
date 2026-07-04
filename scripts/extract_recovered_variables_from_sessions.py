#!/usr/bin/env python3
"""Extract recovered variables, labels, stages, and artifact names from sessions."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


KEYWORDS = [
    "software",
    "maintainer",
    "repo",
    "repair",
    "verifier",
    "decoder",
    "semantic",
    "intent",
    "mine",
    "mining",
    "curriculum",
    "counterfactual",
    "symbol",
    "edit",
    "patch",
    "operator",
    "telemetry",
    "loss",
    "route",
    "evidence",
    "authority",
    "dataset judge",
    "junk ranker",
    "bounded",
]

PATTERNS = {
    "stage_ids": re.compile(r"\bstage(\d{3,5})(?:_[A-Za-z0-9_]+)?"),
    "all_caps_labels": re.compile(r"\b[A-Z][A-Z0-9]+(?:_[A-Z0-9]+){1,8}\b"),
    "script_names": re.compile(r"\b(?:scripts|legacy_src/scripts)/[A-Za-z0-9_./-]+\.py\b"),
    "summary_names": re.compile(r"\bruns/summaries/[A-Za-z0-9_./-]+\.json\b"),
    "artifact_paths": re.compile(r"\bruns/(?:local|summaries)/[A-Za-z0-9_./-]+\b"),
    "json_keys": re.compile(r"\"([A-Za-z_][A-Za-z0-9_]{2,80})\"\s*:"),
}

RECOVERY_BUCKET_TERMS = {
    "semantic_presentation": ["SAFE", "UNSAFE", "RETRIEVE", "semantic", "surface", "target_shape", "maintainer_answer"],
    "intent_build": ["USE_WHITELIST_IMPORT", "BUILD_ON_TOP", "BUILD_FROM_SCRATCH", "allowed_import", "blocked_import", "file_plan"],
    "routing_authority": ["authority", "authorized", "runtime_authorized", "body_emission", "promotion_ready", "controller"],
    "mining_judge": ["mine", "mining", "dataset judge", "junk ranker", "shortcut", "baseline", "duplicate"],
    "counterfactual": ["counterfactual", "sibling", "mixed replay", "evidence removed", "hard negative"],
    "software_graph": ["repo_state", "symbol binding", "edit localization", "patch operator", "call graph", "test graph"],
    "verifier_loop": ["verifier", "failure log", "pytest", "baseline", "repair"],
    "training_telemetry": ["logit", "loss", "gradient", "confusion_matrix", "eval_loss", "module_delta"],
    "decoder": ["decoder", "bounded", "short", "junk", "repetition", "internal token", "EOS"],
}


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def relevant(line: str) -> bool:
    lower = line.lower()
    return any(term in lower for term in KEYWORDS)


def scan_file(path: Path, max_bytes: int) -> tuple[dict[str, Counter[str]], Counter[str], list[dict[str, Any]]]:
    counters = {name: Counter() for name in PATTERNS}
    buckets: Counter[str] = Counter()
    snippets: list[dict[str, Any]] = []
    try:
        raw = path.read_bytes()[:max_bytes]
    except OSError:
        return counters, buckets, snippets
    lines = raw.decode("utf-8", errors="ignore").splitlines()
    per_bucket_snips: Counter[str] = Counter()
    for line_no, line in enumerate(lines, start=1):
        if not relevant(line):
            continue
        for name, pattern in PATTERNS.items():
            for match in pattern.findall(line):
                value = match if isinstance(match, str) else match[0]
                counters[name][value] += 1
        lower = line.lower()
        for bucket, terms in RECOVERY_BUCKET_TERMS.items():
            if any(term.lower() in lower for term in terms):
                buckets[bucket] += 1
                if per_bucket_snips[bucket] < 8:
                    per_bucket_snips[bucket] += 1
                    snippets.append(
                        {
                            "bucket": bucket,
                            "session_file": str(path),
                            "line": line_no,
                            "snippet": re.sub(r"\s+", " ", line).strip()[:1400],
                        }
                    )
    return counters, buckets, snippets


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions-root", default="/home/peyton/.codex/sessions")
    parser.add_argument("--output-dir", default="runs/local/artifacts/stage8615_recovered_variable_ledger")
    parser.add_argument("--max-files", type=int, default=260)
    parser.add_argument("--max-bytes-per-file", type=int, default=2500000)
    args = parser.parse_args()

    root = Path(args.sessions_root)
    files = sorted(root.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)[: args.max_files]
    aggregate = {name: Counter() for name in PATTERNS}
    bucket_counts: Counter[str] = Counter()
    snippets: list[dict[str, Any]] = []
    files_with_hits = 0
    for path in files:
        counters, buckets, file_snippets = scan_file(path, args.max_bytes_per_file)
        if any(counters[name] for name in counters) or buckets:
            files_with_hits += 1
        for name, counter in counters.items():
            aggregate[name].update(counter)
        bucket_counts.update(buckets)
        snippets.extend(file_snippets)

    ledger = {
        "sessions_root": str(root),
        "files_scanned": len(files),
        "files_with_hits": files_with_hits,
        "bucket_counts": dict(bucket_counts),
        "top_stage_ids": aggregate["stage_ids"].most_common(250),
        "top_all_caps_labels": aggregate["all_caps_labels"].most_common(300),
        "top_script_names": aggregate["script_names"].most_common(250),
        "top_summary_names": aggregate["summary_names"].most_common(250),
        "top_artifact_paths": aggregate["artifact_paths"].most_common(250),
        "top_json_keys": aggregate["json_keys"].most_common(300),
    }
    out = Path(args.output_dir)
    write_json(out / "recovered_variable_ledger.json", ledger)
    write_jsonl(out / "recovered_variable_snippets.jsonl", snippets[:500])
    print(json.dumps({
        "files_scanned": len(files),
        "files_with_hits": files_with_hits,
        "bucket_counts": dict(bucket_counts),
        "top_labels": aggregate["all_caps_labels"].most_common(20),
        "top_stages": aggregate["stage_ids"].most_common(20),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
