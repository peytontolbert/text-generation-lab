from __future__ import annotations

from pathlib import Path
import argparse
import json
import re

from stage_summary_schema import make_summary, write_summary


def infer_stage_name(stage: int, snippet: str) -> str:
    m = re.search(r"stage%d[_a-zA-Z0-9-]*" % stage, snippet)
    if m:
        return m.group(0)
    return f"stage{stage}_reconstructed_from_session_index"


def infer_passed(snippet: str) -> bool:
    lower = snippet.lower()
    if "passed: false" in lower or '"passed": false' in lower or "failed" in lower:
        return False
    if "passed: true" in lower or '"passed": true' in lower or " passed" in lower:
        return True
    return False


def build_reconstructed_summary(record: dict, *, force_closed_authority: bool = True) -> dict:
    stage = int(record["stage"])
    snippet = str(record.get("snippet", ""))
    name = infer_stage_name(stage, snippet)
    passed = infer_passed(snippet)
    next_best_step = "reconstructed from session index; rerun original audit before using for authorization"
    if stage == 8586:
        next_best_step = "pre-incident stage authorized one tiny retry, but reconstructed summary keeps current authority closed after incident"
    if stage == 8587:
        next_best_step = "rebuild safe cleanup utilities and tests before any trainer or model execution"
    return make_summary(
        stage=stage,
        stage_name=name,
        passed=passed,
        next_best_step=next_best_step,
        metrics={
            "source_session": record.get("session", ""),
            "source_line": record.get("line", 0),
            "source_kind": record.get("kind", ""),
            "snippet_chars": len(snippet),
        },
        gates={"reconstructed_from_session_index": True, "current_authority_forced_closed": force_closed_authority},
        authority={},
        reconstructed=True,
        notes=snippet[:2000],
    )


def choose_records(index_rows: list[dict]) -> dict[int, dict]:
    chosen: dict[int, tuple[int, dict]] = {}
    for rec in index_rows:
        stage = int(rec["stage"])
        snippet = str(rec.get("snippet", ""))
        score = 0
        if '"passed"' in snippet or 'passed:' in snippet.lower():
            score += 3
        if "latest_stage" in snippet:
            score += 2
        if rec.get("kind") in {"function_call_output", "message", "agent_message"}:
            score += 1
        if len(snippet) > 400:
            score += 1
        if stage not in chosen or score > chosen[stage][0]:
            chosen[stage] = (score, rec)
    return {stage: rec for stage, (_score, rec) in chosen.items()}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reconstruct closed-authority stage summary stubs from session recovery index.")
    parser.add_argument("--index", type=Path, default=Path("runs/local/artifacts/session_recovery/stage8530_8589_session_hit_index.jsonl"))
    parser.add_argument("--output-dir", type=Path, default=Path("runs/summaries/reconstructed_from_sessions"))
    parser.add_argument("--stage-min", type=int, default=8530)
    parser.add_argument("--stage-max", type=int, default=8586)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = [json.loads(line) for line in args.index.read_text(encoding="utf-8").splitlines() if line.strip()]
    chosen = choose_records(rows)
    written = []
    for stage in range(args.stage_min, args.stage_max + 1):
        rec = chosen.get(stage)
        if rec is None:
            continue
        summary = build_reconstructed_summary(rec)
        path = args.output_dir / f"stage{stage}_reconstructed_from_session_index.json"
        write_summary(path, summary, require_closed=True)
        written.append(str(path))
    print(json.dumps({"written_count": len(written), "written": written}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
