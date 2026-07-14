#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUM = ROOT / "runs/summaries"
NAME = "stage11518_minimal_source_heldout_smoke_materialization_request"
OUT_DIR = ART / NAME
OUT_JSON = SUM / f"{NAME}.json"

WORKLIST = SUM / "stage11517_source_heldout_harness_hardening_worklist.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    worklist = load_json(WORKLIST)
    nearest = worklist.get("nearest_repair_rows_by_language") or {}
    source_candidate_counts = (worklist.get("repair_queue_summary") or {}).get("source_heldout_candidate_rows_by_language") or {}

    requests: list[dict[str, Any]] = []
    for language in ("python", "c_cpp", "web_js_ts_html"):
        template_rows = nearest.get(language) or []
        requests.append(
            {
                "language_family": language,
                "request_type": "fresh_source_heldout_root_required",
                "reason": "Stage11517 found zero source-heldout candidate rows for this language.",
                "template_rows_for_geometry_only": template_rows[:3],
                "minimum_rows": 1,
                "minimum_roots": 1,
                "required_properties": [
                    "source_heldout_admissible=true",
                    "deterministic_option_shuffle=true",
                    "opaque_labels=true",
                    "option_count>=2",
                    "prompt_target_value_leak=false",
                    "selected_test_anchor=true or verifier_anchor=true",
                    "has_verifier_row_or_transition=true",
                    "has_patch_or_abstain_row=true for full-product harness claim",
                    "train_eligible=false for strict smoke rows",
                ],
                "preferred_task_types": [
                    "verifier_outcome_semantic_transition",
                    "evidence_citation",
                    "patch_impact",
                    "abstention_insufficient_evidence",
                ],
            }
        )

    rust_templates = nearest.get("rust") or []
    requests.append(
        {
            "language_family": "rust",
            "request_type": "repair_existing_source_heldout_or_materialize_fresh",
            "reason": f"Stage11517 found {source_candidate_counts.get('rust', 0)} Rust source-heldout candidates but none are admitted.",
            "template_rows_for_geometry_only": rust_templates[:5],
            "minimum_rows": 1,
            "minimum_roots": 1,
            "required_properties": [
                "source_heldout_admissible=true",
                "deterministic_option_shuffle=true",
                "opaque_labels=true",
                "option_count>=2",
                "prompt_target_value_leak=false",
                "selected_test_anchor=true or verifier_anchor=true",
                "has_verifier_row_or_transition=true",
                "has_patch_or_abstain_row=true for full-product harness claim",
                "avoid singleton verifier rows",
            ],
            "preferred_task_types": [
                "evidence_citation",
                "symptom_localization",
                "verifier_outcome_semantic_transition",
            ],
        }
    )

    output_manifest = OUT_DIR / "minimal_source_heldout_smoke_requests.jsonl"
    write_jsonl(output_manifest, requests)

    payload = {
        "stage": 11518,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "minimal_source_heldout_smoke_materialization_requested",
        "why": [
            "Stage11516 proves the compact same-task harness survives removal of the most obvious shortcut-risk rows.",
            "Stage11517 proves the broader source-heldout/full-product successor is not ready: Python, C/C++, and Web have zero source-heldout candidate rows; Rust has candidates but no admitted row.",
            "This stage converts that into the minimal next materialization request: one hardened source-heldout row per language, then same-manifest 100M/Gemma comparison.",
        ],
        "requests": requests,
        "successor_acceptance_gate": {
            "rows": ">=4 total, exactly >=1 per python/rust/c_cpp/web_js_ts_html",
            "root_split": "all rows strict/smoke only; no train eligibility; no train root overlap",
            "anti_cheat": [
                "zero prompt_target_value_leak",
                "zero singleton_or_missing_options",
                "deterministic_option_shuffle=true",
                "opaque_labels=true",
            ],
            "evidence": [
                "source_heldout_admissible=true",
                "selected_test_anchor=true or verifier_anchor=true",
                "has_verifier_row_or_transition=true",
                "patch_or_abstain evidence present or explicit claim marked standalone-only",
            ],
            "comparison": [
                "run Stage11507 selected runtime with CUDA_VISIBLE_DEVICES=2",
                "run Gemma same-manifest only if Ollama can be pinned away from GPUs 0/1 or run from existing/pinned backend",
                "100M must beat Gemma overall and not lose any language cell for smoke promotion",
            ],
        },
        "recommended_next_command_template": [
            "materialize rows into runs/local/artifacts/stage11519_minimal_source_heldout_smoke_package/",
            "run selected Stage11507 100M on the package with: CUDA_VISIBLE_DEVICES=2 conda run -n trellis ...",
            "run or attach same-manifest Gemma outputs under an explicit GPU placement policy",
            "audit with Stage11515-equivalent anti-cheat before any claim upgrade",
        ],
        "outputs": {
            "request_manifest": rel(output_manifest),
        },
        "source_artifacts": {
            "worklist": rel(WORKLIST),
        },
        "next_best_step": "Materialize Stage11519 minimal source-heldout smoke package from fresh roots rather than reusing non-heldout compact canary roots.",
    }
    write_json(OUT_DIR / f"{NAME}.json", payload)
    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
