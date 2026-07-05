from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

STAGE_RE = re.compile(r"stage(\d+)")
AUTH_KEYS = [
    "model_execution_authorized_next",
    "decoder_ce_training_authorized_next",
    "denoise_ce_training_authorized_next",
    "runtime_authorized",
    "source_emission_authorized",
    "body_emission_authorized",
    "gemma_execution_authorized_next",
    "harness_execution_authorized_next",
    "scoring_authorized_next",
    "controller_complete_merge_authorized_next",
    "promotion_ready",
]


def parse_stage(path: Path, payload: dict[str, Any]) -> int | None:
    value = payload.get("stage")
    if isinstance(value, int):
        return value
    m = STAGE_RE.search(path.name)
    return int(m.group(1)) if m else None


def decision_payload(payload: dict[str, Any]) -> dict[str, Any]:
    decision = payload.get("decision")
    if isinstance(decision, dict):
        return decision
    authority = payload.get("authority")
    if isinstance(authority, dict):
        return authority
    return payload


def load_summary(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    stage = parse_stage(path, payload)
    if stage is None:
        return None
    decision = decision_payload(payload)
    name = str(payload.get("stage_name") or payload.get("name") or path.stem)
    return {
        "stage": stage,
        "stage_name": name,
        "path": str(path),
        "passed": bool(payload.get("passed", False)),
        "next_best_step": str(payload.get("next_best_step") or decision.get("next_best_step") or ""),
        "authority": {key: bool(decision.get(key, False)) for key in AUTH_KEYS},
    }


def build_registry(repo_root: Path) -> dict[str, Any]:
    summaries_dir = repo_root / "runs" / "summaries"
    rows = []
    for path in sorted(summaries_dir.rglob("*.json")):
        row = load_summary(path)
        if row is not None:
            rows.append(row)
    rows.sort(key=lambda row: (row["stage"], row["stage_name"]))
    latest = rows[-1] if rows else None
    authority_counts = {key: sum(1 for row in rows if row["authority"].get(key)) for key in AUTH_KEYS}
    return {
        "passed": bool(rows),
        "metrics": {
            "registry_rows": len(rows),
            "min_stage": rows[0]["stage"] if rows else None,
            "max_stage": latest["stage"] if latest else None,
            "latest_stage": latest["stage"] if latest else None,
            "latest_stage_name": latest["stage_name"] if latest else "",
            "latest_stage_next_best_step": latest["next_best_step"] if latest else "",
            "authority_counts": authority_counts,
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a non-destructive reconstructed v2.7 stage registry from runs/summaries/*.json")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("runs/local/artifacts/reconstructed_stage_registry.json"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo = args.repo_root.resolve()
    registry = build_registry(repo)
    out = args.output if args.output.is_absolute() else repo / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    public = {"passed": registry["passed"], "metrics": registry["metrics"], "output": str(out)}
    print(json.dumps(public, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
