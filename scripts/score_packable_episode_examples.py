from __future__ import annotations

import argparse
from pathlib import Path

from episode_example_quality import score_examples_file
from long_context_common import write_json, write_jsonl


def main() -> None:
    parser = argparse.ArgumentParser(description='Score packable long-context episode examples and fail on weak supervision.')
    parser.add_argument('--examples', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--summary-output', type=Path)
    parser.add_argument('--min-quality-score', type=float, default=0.75)
    args = parser.parse_args()
    reports, summary = score_examples_file(examples_path=args.examples, min_quality_score=args.min_quality_score)
    write_jsonl(args.output, reports)
    write_json(args.summary_output or args.output.with_name('packable_episode_quality_summary.json'), summary)
    if summary['failing_example_count'] > 0:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
