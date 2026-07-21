#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12240_external_repair_acquisition_request_v2"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    exhausted_pools = [
        "stage12201/stage12217 patch-trace queue",
        "stage12219/stage12220/stage12221/stage12223/stage12224/stage12225 patch-trace replay/QC",
        "stage12228/stage12229 external patch-trace projections",
        "stage12209",
        "stage11977",
        "stage11999",
        "stage12003",
        "stage12123",
        "stage12143",
        "controlled fixture pools stage11978/stage11980/stage12025/stage12053/stage12055/stage12231/stage12232",
    ]
    payload: dict[str, Any] = {
        "stage": STAGE,
        "decision": "external_repair_acquisition_required_existing_local_pools_exhausted",
        "accepted_existing_candidates": 0,
        "training_allowed": False,
        "acquisition_goal": {
            "minimum_before_training": {
                "external_comparable_patch_trace_rows": 25,
                "external_fail_to_pass_rows": 15,
                "non_python_external_rows": 10,
                "max_repo_family_fraction": 0.2,
            },
            "preferred_batch": {
                "external_comparable_patch_trace_rows": 60,
                "external_fail_to_pass_rows": 30,
                "languages": {
                    "python": 15,
                    "c_cpp": 15,
                    "rust": 15,
                    "web_js_ts_html": 15,
                },
            },
        },
        "required_record_contract": {
            "phase_tuple": [
                "before: selected verifier exists and fails for behavior, not missing test/env",
                "before_plus_patch: same verifier passes after applying patch",
                "after: authoritative target state/verifier remains passing when available",
            ],
            "required_evidence": [
                "repo_family, commit_before, commit_after or patch source",
                "same-source unified diff and apply evidence",
                "selected verifier command text, cwd, exit code, stdout/stderr excerpt and hashes for every phase",
                "visible source/test context proving verifier relevance",
                "candidate action set with inspect/run/patch/abstain hard negatives",
                "state_before, ordered_events, state_after/state_update, stop_continue decision",
                "lineage and repo-family cap metadata",
            ],
        },
        "hard_rejects": [
            "missing test file or no-tests-collected counted as failure",
            "ENV/dependency/network/install/GPU failure unless task is explicitly environment repair",
            "syntax-only or forced compile-error mutation counted as maintainer repair",
            "commit metadata inferred pass/fail without command output",
            "selected test added only by the patch",
            "weak/unrelated verifier that does not exercise changed path",
            "cross-source joins where diff, command, and verifier evidence come from different lineage",
            "controlled fixture counted as external repair or source-heldout proof",
            "PASS_TO_PASS safe refactor counted as FAIL_TO_PASS",
        ],
        "exhausted_local_pools": exhausted_pools,
        "known_near_misses": [
            {
                "source": "mem0",
                "reason": "before failure was missing tests/test_telemetry.py / no tests ran; downgraded to TEST_ADDED_NOT_COMPARABLE",
            },
            {
                "source": "agent-governance-toolkit",
                "reason": "PASS_TO_PASS with weak/unrelated verifier; useful patch-apply/safe-refactor support only",
            },
            {
                "source": "unsloth",
                "reason": "PASS_TO_PASS only; useful no-regression support, not repair proof",
            },
            {
                "source": "stage11999/stage12003",
                "reason": "syntax/compile-error mutations excluded from semantic repair floor",
            },
        ],
        "subagent_packet": {
            "role": "strict external repair scout/materializer",
            "objective": "Find and materialize new locally hydratable real repo commits with comparable same-verifier behavior FAIL_TO_PASS patch traces.",
            "instructions": [
                "Do not mine exhausted pools unless you are proving a missed command-output field.",
                "Prefer repos with no-install or already-cached tests.",
                "For non-Python, require build/test hydration before row drafting.",
                "Return candidates as admission records, not training rows.",
                "Every candidate must include why each hard reject does not apply.",
            ],
        },
        "claim_boundary": "Acquisition request only. No training or frontier claim.",
    }

    brief = f"""# {STAGE}

Decision: {payload['decision']}

The existing local pools are exhausted for strict external comparable repair. New agents should not re-mine them unless they have a specific missing command-output lead.

Minimum before any repair training:
- external comparable patch trace rows >= 25
- external FAIL_TO_PASS rows >= 15
- non-Python external rows >= 10
- no repo family > 20%

Hard rejects:
{chr(10).join('- ' + item for item in payload['hard_rejects'])}

Required phase tuple:
{chr(10).join('- ' + item for item in payload['required_record_contract']['phase_tuple'])}

Exhausted pools:
{chr(10).join('- ' + item for item in exhausted_pools)}
"""

    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / "external_repair_acquisition_request_v2.json", payload)
    write_text(OUT / "EXTERNAL_REPAIR_ACQUISITION_REQUEST_STAGE12240.md", brief)
    write_json(SUMMARY, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
