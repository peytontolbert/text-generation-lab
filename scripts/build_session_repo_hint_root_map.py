from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from long_context_common import write_json


DEFAULT_HINT_MAP = {
    "agentkernel": "/data/agentkernel",
    "agentkernel-seq2seq-text-lab": "/data/agentkernel-seq2seq-text-lab",
    "parametergolf": "/data/parametergolf",
    "bddy": "/data/bddy",
    "bddy_website": "/data/bddy/bddy_website",
    "repository_library": "/data/repository_library",
    "code_assist": "/data/code_assist",
    "bddy_model": "/data/bddy/bddy_model",
    "models": "/data/repository_library/models",
}


def build_session_repo_hint_root_map(*, hints_path: Path | None = None) -> dict[str, Any]:
    hints = []
    if hints_path and hints_path.exists():
        hints = [json.loads(line) for line in hints_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    observed = sorted({str(row.get("repo_hint") or "") for row in hints if str(row.get("repo_hint") or "")})
    rows = []
    for hint in sorted(set(observed) | set(DEFAULT_HINT_MAP)):
        root = DEFAULT_HINT_MAP.get(hint, "")
        exists = Path(root).exists() if root else False
        rows.append(
            {
                "repo_hint": hint,
                "local_repo_root": root,
                "root_exists": exists,
            }
        )
    return {
        "rows": rows,
        "mapped_count": sum(int(bool(row["local_repo_root"])) for row in rows),
        "existing_count": sum(int(bool(row["root_exists"])) for row in rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an explicit repo-hint to local-root map for session-derived seeds.")
    parser.add_argument("--session-seeds", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = build_session_repo_hint_root_map(hints_path=args.session_seeds)
    write_json(args.output, payload)


if __name__ == "__main__":
    main()
