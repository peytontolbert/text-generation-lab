#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11616
NAME = "stage11616_web_fail_to_pass_support_decision"
OUT = ART / NAME
SUMMARY = OUT / "web_fail_to_pass_support_decision.json"
AUDIT = SUMMARIES / "stage11615_web_mutation_rows_anticheat_audit.json"
SELECTED_RUNTIME = ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    audit = load_json(AUDIT)
    selected = load_json(SELECTED_RUNTIME)
    enough_for_probe = audit.get("admitted_rows", 0) >= 36 and audit.get("complete_six_task_roots", 0) >= 6 and audit.get("rejected_rows", 1) == 0
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "build_guarded_training_request_with_controlled_web_fail_to_pass_support" if enough_for_probe else "scale_more_controlled_web_fail_to_pass_roots_before_training",
        "selected_frontier": {
            "runtime": rel(SELECTED_RUNTIME),
            "scorer": "encoder_option_retrieval_evidence_judgment_head",
            "weights_sha256": selected.get("weights_sha256"),
        },
        "support_status": {
            "admitted_rows": audit.get("admitted_rows"),
            "complete_six_task_roots": audit.get("complete_six_task_roots"),
            "admitted_by_task": audit.get("admitted_by_task"),
            "admitted_by_target_role": audit.get("admitted_by_target_role"),
            "strict_eval_eligible": 0,
            "source_kind": "controlled_bug_injection_fail_to_pass",
        },
        "training_policy": [
            "Use these rows only as train-support, never as strict eval or headline web heldout.",
            "Initialize from Stage11507 and preserve canary/residual gates.",
            "Evaluate against existing Web heldout and no-abstain successor; promotion requires web heldout improvement plus preservation.",
            "If training improves successor but not heldout, treat as overfit and continue materializing more diverse roots.",
        ],
        "recommended_probe_shape": {
            "init_runtime": rel(SELECTED_RUNTIME),
            "train_support_rows": "runs/local/artifacts/stage11615_web_mutation_rows_anticheat_audit/web_mutation_rows_admitted_train_support.jsonl",
            "sampler": "web_task_family_balanced",
            "scorer": "encoder_option_retrieval_evidence_judgment_head or web_task_candidate_head_ablation",
            "preservation_kl_weight": "high enough to keep residual >=7/10",
            "promotion_gates": {
                "filtered_strict": "22/22",
                "old_canary_strict": "23/23",
                "filtered_validation": ">=20/22",
                "old_canary_validation": ">=21/23",
                "residual_bank": ">=7/10",
                "web_heldout": ">35/66 first, then >42/66",
                "web_successor_or_controlled_mutation_probe": "improves without becoming headline eval",
            },
        },
        "claim_boundary": [
            "This stage authorizes a guarded probe, not promotion.",
            "Controlled mutation rows are useful for training verifier-transition behavior but cannot by themselves prove organic maintainer superiority.",
        ],
        "source_artifacts": {"audit": rel(AUDIT), "selected_runtime": rel(SELECTED_RUNTIME)},
        "outputs": {"summary": rel(SUMMARY)},
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({
        "decision": summary["decision"],
        "support_status": summary["support_status"],
        "recommended_probe_shape": summary["recommended_probe_shape"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
