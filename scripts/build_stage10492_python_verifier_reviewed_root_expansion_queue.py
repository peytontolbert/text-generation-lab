#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10492
NAME = "stage10492_python_verifier_reviewed_root_expansion_queue"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
QUEUE_JSON = OUT_DIR / "python_verifier_reviewed_root_expansion_queue.json"
TARGETS_JSONL = OUT_DIR / "python_verifier_reviewed_root_expansion_targets.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

REPLENISHMENT_JSON = ROOT / "runs/local/artifacts/stage10235_fresh_maintainer_bundle_replenishment_request/fresh_maintainer_bundle_replenishment_request.json"
SUPPLY_JSON = ROOT / "runs/local/artifacts/stage10463_python_verifier_fresh_root_inventory/python_verifier_fresh_root_inventory.json"
DELEAK_AUDIT = ROOT / "runs/local/artifacts/stage10491_deleaked_python_promotable_probe_audit/deleaked_python_promotable_probe_audit.json"
RESIDUAL_QUEUE = ROOT / "runs/local/artifacts/stage10444_repaired_v27_disjoint_residual_queue/repaired_v27_disjoint_residual_queue.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    replenishment = load_json(REPLENISHMENT_JSON)
    supply = load_json(SUPPLY_JSON)
    deleak = load_json(DELEAK_AUDIT)
    residual_queue = load_json(RESIDUAL_QUEUE)

    python_targets = list(((replenishment.get("fresh_builder_targets") or {}).get("python") or {}).get("recommended_episode_targets") or [])
    residual = next(target for target in residual_queue["targets"] if target["language_family"] == "python")

    ranked_targets: list[dict[str, Any]] = []
    for order, row in enumerate(python_targets, start=1):
        repo_id = str(row.get("repo_id") or "")
        ranked_targets.append(
            {
                "priority_order": order,
                "episode_id": row["episode_id"],
                "repo_id": repo_id,
                "selected_tests_count": int(row.get("selected_tests_count") or 0),
                "selected_tests": list(row.get("selected_tests") or []),
                "change_paths_for_language": list(row.get("change_paths_for_language") or []),
                "candidate_geometry_tags": list(row.get("candidate_geometry_tags") or []),
                "supports_shortcut_safe_successor": bool(row.get("supports_shortcut_safe_successor")),
                "builder_use": "fresh_python_verifier_bundle_review",
                "motivation": (
                    "new repo-family episode with broad sibling-test competition"
                    if repo_id == "agentkernel"
                    else "code_assist episode with richer selected-test competition than the exhausted compact support rows"
                ),
                "required_bundle_shape": [
                    "verifier_outcome rows with 3 or more plausible test targets",
                    "selected-test anchor present but not exposed verbatim before options",
                    "candidate path and verifier target competition preserved under anti-cheat review",
                    "root remains disjoint from current MirrorMind strict family",
                ],
            }
        )

    queue = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(ranked_targets),
        "decision": "python_verifier_reviewed_root_expansion_queue_ready",
        "claim_scope": [
            "Promote the next Python residual work from exhausted compact support rows to fresh reviewed root construction.",
            "Use the clean negative result from stage10491 to justify a new reviewed-root queue rather than more training on the same support rows.",
        ],
        "source_artifacts": {
            "fresh_replenishment_request": display(REPLENISHMENT_JSON),
            "fresh_root_supply_inventory": display(SUPPLY_JSON),
            "deleaked_promotable_probe_audit": display(DELEAK_AUDIT),
            "residual_queue": display(RESIDUAL_QUEUE),
        },
        "current_python_residual": residual,
        "negative_control_summary": {
            "stage10491_delta": (deleak.get("accuracy") or {}).get("delta"),
            "stage10491_python_residual_fixed": ((deleak.get("headline") or {}).get("python_residual_fixed")),
            "stage10491_zero_regressions": ((deleak.get("headline") or {}).get("zero_regressions")),
            "interpretation": "honest de-leaked compact support did not move the frontier; next progress requires new reviewed roots, not more support tuning",
        },
        "builder_requirements": supply["builder_requirements"],
        "queue_targets": ranked_targets,
        "required_honesty_gates": [
            "Do not reuse the de-leaked stage10487 support rows as the main Python curriculum again.",
            "Every new root must pass prompt-target-leak audit before execution.",
            "At least one next bundle should come from a repo family beyond code_assist to reduce support-family saturation risk.",
            "Any promotion candidate still must beat 22/24 with zero regressions on the repaired strict overlay.",
        ],
        "recommended_next_stage": "stage10493_python_verifier_fresh_review_packet_builder",
        "remaining_multilingual_note": {
            "rust": "still blocked on fresh non-tokenizers E-vs-F citation roots",
            "c_cpp": "needs new source mining rather than more packet repair",
            "web": "same-manifest win exists, but broader web claim still wants a cleaner pure-web verifier bundle",
        },
    }

    write_jsonl(TARGETS_JSONL, ranked_targets)
    write_json(QUEUE_JSON, queue)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": queue["passed"],
            "decision": queue["decision"],
            "queue": display(QUEUE_JSON),
        },
    )
    print(json.dumps(queue, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
