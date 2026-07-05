#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from commit_inventory_dry_run_design_builder import AUTHORITY_CLOSED, build_card, build_inventory_design_rows  # noqa: E402

STAGE = 8883
NAME = "stage8883_metadata_only_commit_inventory_preflight_design"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "METADATA_ONLY_COMMIT_INVENTORY_PREFLIGHT_DESIGN_STAGE8883.md"


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = build_inventory_design_rows()
    for row in rows:
        row["source_stage"] = NAME
        row["objective_family"] = "metadata_only_commit_inventory_preflight_design"
        row["route"] = "PREFLIGHT_DESIGN_ONLY_NO_REPO_WALK"
        row["preflight_scope"] = {
            "reads_repository_paths_now": False,
            "walks_arxiv_repositories_now": False,
            "reads_git_commits_now": False,
            "reads_diff_bodies_now": False,
            "emits_training_rows_now": False,
            "future_max_repositories_requires_explicit_authorization": True,
        }
    design_path = OUT_DIR / "metadata_only_commit_inventory_preflight_design.jsonl"
    write_jsonl(design_path, rows)
    metrics = build_card(rows)
    # build_card expects the original route, so compute explicit preflight validation here too.
    route_ok = all(row.get("route") == "PREFLIGHT_DESIGN_ONLY_NO_REPO_WALK" for row in rows)
    no_open = all(not any((row.get("authority") or {}).values()) and not any((row.get("loss_mask") or {}).values()) for row in rows)
    no_walk = all(not any((row.get("preflight_scope") or {}).get(key) for key in ["reads_repository_paths_now", "walks_arxiv_repositories_now", "reads_git_commits_now", "reads_diff_bodies_now", "emits_training_rows_now"]) for row in rows)
    failures = []
    if not rows:
        failures.append("no_rows")
    if not route_ok:
        failures.append("bad_route")
    if not no_open:
        failures.append("authority_or_loss_open")
    if not no_walk:
        failures.append("walk_or_read_enabled")
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "rows": len(rows),
            "failures": failures,
            "repository_walks_now": 0,
            "commit_reads_now": 0,
            "diff_body_reads_now": 0,
            "training_rows_now": 0,
            "metadata_only_schema_fields": len(metrics.get("commit_metadata_fields", [])),
            "future_inventory_requires_explicit_authorization": True,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
        },
        "artifacts": {"design_manifest": str(design_path.relative_to(ROOT)), "builder": "scripts/commit_inventory_dry_run_design_builder.py"},
        "decision": "Metadata-only commit inventory preflight design recorded. It performs no repository walking, commit reads, diff body reads, mining, or training.",
        "next_best_step": "Only if explicitly authorized later, build a bounded metadata inventory ticket with repository caps and no patch bodies. Otherwise leave inventory closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "metadata_only_commit_inventory_preflight_design_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8883 Metadata-Only Commit Inventory Preflight Design",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "Current counts:",
        "",
        "- repository walks now: `0`",
        "- commit reads now: `0`",
        "- diff body reads now: `0`",
        "- training rows now: `0`",
        "",
        "This is design-only. `/arxiv` is not walked and no data is mined.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
