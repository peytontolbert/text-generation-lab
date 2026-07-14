#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11366
NAME = "stage11366_summary_registry_backfill"
OUT = ART / NAME
SUMMARY = OUT / "summary_registry_backfill.json"

STAGE_RE = re.compile(r"^stage(\d+)_(.+)$")


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def latest_summary_stage() -> int:
    latest = 0
    for path in SUMMARIES.glob("stage*.json"):
        match = re.match(r"stage(\d+)_", path.name)
        if match:
            latest = max(latest, int(match.group(1)))
    return latest


def stage_dirs_after(stage_floor: int) -> list[tuple[int, Path]]:
    out = []
    for path in ART.iterdir():
        if not path.is_dir():
            continue
        match = STAGE_RE.match(path.name)
        if not match:
            continue
        stage_num = int(match.group(1))
        if stage_num > stage_floor and stage_num != STAGE:
            out.append((stage_num, path))
    return sorted(out)


def score_summary_candidate(path: Path, stage_num: int) -> tuple[int, str]:
    name = path.name
    score = 0
    if name.startswith("bounded_choice_eval_audit_"):
        score -= 50
    if name.endswith("_rows.json") or name.endswith("_rows.jsonl"):
        score -= 20
    if "summary" in name:
        score += 20
    if "decision" in name:
        score += 10
    if "audit" in name:
        score += 8
    if "comparison" in name:
        score += 8
    if "package" in name:
        score += 4
    if f"stage{stage_num}" in name:
        score += 5
    try:
        obj = read_json(path)
        if isinstance(obj, dict):
            if obj.get("stage") == stage_num:
                score += 25
            if "stage_name" in obj:
                score += 10
            if "decision" in obj:
                score += 10
            if "counts" in obj or "metrics" in obj or "product_metrics" in obj:
                score += 5
    except Exception:
        score -= 100
    return score, name


def choose_primary_json(stage_dir: Path, stage_num: int) -> Path | None:
    candidates = [p for p in stage_dir.glob("*.json") if p.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda p: score_summary_candidate(p, stage_num))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    floor = latest_summary_stage()
    mirrored = []
    skipped = []
    for stage_num, stage_dir in stage_dirs_after(floor):
        target = SUMMARIES / f"{stage_dir.name}.json"
        if target.exists():
            skipped.append({"stage": stage_num, "artifact": rel(stage_dir), "reason": "summary_already_exists"})
            continue
        primary = choose_primary_json(stage_dir, stage_num)
        if primary is None:
            skipped.append({"stage": stage_num, "artifact": rel(stage_dir), "reason": "no_primary_json_found"})
            continue
        shutil.copyfile(primary, target)
        mirrored.append({"stage": stage_num, "artifact": rel(stage_dir), "source": rel(primary), "summary": rel(target)})

    latest_after = latest_summary_stage()
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": latest_after >= max([m["stage"] for m in mirrored], default=floor),
        "decision": "summary_registry_backfill_complete",
        "counts": {
            "latest_summary_stage_before": floor,
            "latest_summary_stage_after": latest_after,
            "mirrored": len(mirrored),
            "skipped": len(skipped),
        },
        "mirrored": mirrored,
        "skipped": skipped[:200],
        "outputs": {"summary": rel(SUMMARY)},
        "recommended_next_action": "Keep future stage builders writing both local artifact summaries and runs/summaries mirrors, then continue scoring Stage11364 support against the sealed Stage11361 heldout.",
    }
    write_json(SUMMARY, summary)
    # Mirror this stage too, so the registry no longer immediately falls behind.
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
