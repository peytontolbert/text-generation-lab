#!/usr/bin/env python3
"""Extract compact research-spine and ledger hits from Codex session archives."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


PATTERNS = {
    "research_spine": re.compile(r"research spine|central spine|durable spine|spine refresh|current_research_spine", re.I),
    "ledger": re.compile(r"ledger|stage ledger|run ledger|pocketpal_seq2seq_runs", re.I),
    "frontier": re.compile(r"current frontier|latest stage|registry frontier|frontier is", re.I),
    "curriculum_compiler": re.compile(r"curriculum compiler|canonical curriculum|counterfactual|mixed replay|obligation", re.I),
    "dataset_judge": re.compile(r"dataset judge|junk ranker|shortcut baseline|row route|routing ranker", re.I),
    "decoder_branch": re.compile(r"bounded decoder|decoder CE|short/junk|internal token|repetition|EOS", re.I),
    "repo_graph": re.compile(r"repo_state_graph|symbol binding|edit localization|patch operator|verifier repair", re.I),
    "training_telemetry": re.compile(r"row_token_loss|module_delta_norms|field_exact|logits|gradient|telemetry", re.I),
}


def iter_session_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)


def safe_snippet(line: str, max_len: int) -> str:
    line = line.replace("\x00", "")
    line = re.sub(r"\s+", " ", line).strip()
    return line[:max_len]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions-root", default="/home/peyton/.codex/sessions")
    parser.add_argument("--output-dir", default="runs/local/artifacts/stage8620_spine_ledger_session_scrape")
    parser.add_argument("--max-files", type=int, default=220)
    parser.add_argument("--max-bytes-per-file", type=int, default=2_000_000)
    parser.add_argument("--max-snippets-per-bucket", type=int, default=40)
    parser.add_argument("--snippet-len", type=int, default=1400)
    args = parser.parse_args()

    root = Path(args.sessions_root)
    files = iter_session_files(root)[: args.max_files]
    bucket_counts: Counter[str] = Counter()
    stage_counts: Counter[str] = Counter()
    session_counts: Counter[str] = Counter()
    snippets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    stage_re = re.compile(r"stage\s*[-_ ]?(\d{3,5})", re.I)

    files_with_hits = 0
    for path in files:
        file_hit = False
        try:
            text = path.read_bytes()[: args.max_bytes_per_file].decode("utf-8", errors="ignore")
        except Exception:
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            matched = [name for name, pattern in PATTERNS.items() if pattern.search(line)]
            if not matched:
                continue
            file_hit = True
            for stage in stage_re.findall(line):
                stage_counts[stage] += 1
            for name in matched:
                bucket_counts[name] += 1
                session_counts[str(path)] += 1
                if len(snippets[name]) < args.max_snippets_per_bucket:
                    snippets[name].append(
                        {
                            "session_file": str(path),
                            "line": line_no,
                            "snippet": safe_snippet(line, args.snippet_len),
                        }
                    )
        if file_hit:
            files_with_hits += 1

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    summary = {
        "sessions_root": str(root),
        "files_scanned": len(files),
        "files_with_hits": files_with_hits,
        "bucket_counts": dict(bucket_counts),
        "top_stage_ids": stage_counts.most_common(80),
        "top_session_files": session_counts.most_common(40),
        "patterns": {name: pattern.pattern for name, pattern in PATTERNS.items()},
    }
    (out / "spine_ledger_session_scrape_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    with (out / "spine_ledger_session_snippets.jsonl").open("w", encoding="utf-8") as f:
        for bucket, rows in sorted(snippets.items()):
            for row in rows:
                f.write(json.dumps({"bucket": bucket, **row}, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
