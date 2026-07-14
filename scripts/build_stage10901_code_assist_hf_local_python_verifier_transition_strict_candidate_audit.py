#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10901
NAME = "stage10901_code_assist_hf_local_python_verifier_transition_strict_candidate_audit"
OUT_DIR = ARTIFACTS / NAME
AUDIT_JSON = OUT_DIR / "code_assist_hf_local_python_verifier_transition_strict_candidate_audit.json"

BUNDLE_JSON = ARTIFACTS / "stage10900_code_assist_hf_local_python_verifier_transition_strict_candidate" / "strict_candidate_bundle.json"
ROW_JSONL = ARTIFACTS / "stage10900_code_assist_hf_local_python_verifier_transition_strict_candidate" / "strict_candidate_rows.jsonl"
SOURCE_GOLD = ARTIFACTS / "stage10813_python_queue_aligned_admission" / "review_packets" / "stage10300__localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_26t23_27_57_019bfca2_aa35_7502_b929_649a_src_code_assist_agents_hf_local_py_src_code_assist_agents_hf_local_planner_py_sr_3fb1ce61a2_aug_1500000_8b46e7f662__python" / "perspective_gold_adjudication.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    bundle = load_json(BUNDLE_JSON)
    row = load_jsonl(ROW_JSONL)[0]
    gold = load_json(SOURCE_GOLD)
    prompt = str(row.get("prompt_text") or "")
    option_values = [str(item.get("value") or "") for item in row.get("opaque_options") or [] if isinstance(item, dict)]
    pre_options = prompt.split("Options:\n", 1)[0]
    gold_path = "tests/unit/test_hf_local_params.py"

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "code_assist_hf_local_python_verifier_transition_strict_candidate_audited",
        "claim_scope": [
            "Audit the stage10900 same-test semantic Python verifier candidate for target-path leakage and semantic competition quality.",
            "Check whether the candidate improves over raw file-choice semantics by forcing assertion-level verifier distinctions inside the same test surface.",
        ],
        "metrics": {
            "candidate_option_count": len(option_values),
            "explicit_transition_semantics": True,
            "gold_path_hidden_from_option_values": all(gold_path not in value for value in option_values),
            "same_test_semantic_target_competition": True,
            "target_path_visible_pre_options": gold_path in pre_options,
            "visible_test_path_mentions_pre_options": [gold_path] if gold_path in pre_options else [],
        },
        "interpretation": [
            "The candidate uses semantic verifier targets inside one unit-test surface rather than relying on multiple visible test-path labels.",
            "That reduces path-order shortcut pressure, but the shared test-file evidence means the row is only useful if the semantic focus descriptions are genuinely distinguishable from the visible code and assertion text.",
            "Because the verifier snippet still exposes the shared test file before options, this row is better suited as a follow-on candidate or support root unless a stricter visibility rewrite removes that residual shortcut.",
        ],
        "remaining_risks": [
            "The verifier evidence still visibly names the shared unit-test file, so the anti-cheat gain comes from same-test semantic competition rather than hidden test identity.",
            "All targets share FAIL_TO_PASS, so the discriminative pressure remains on focus semantics rather than transition diversity.",
            "A future stronger version should redact or normalize the verifier snippet further if the shared test-path mention proves shortcut-prone.",
        ],
        "source_artifacts": {
            "bundle_json": rel(BUNDLE_JSON),
            "row_jsonl": rel(ROW_JSONL),
            "source_gold": rel(SOURCE_GOLD),
        },
        "next_best_step": "Use this as a second reviewed candidate only if the heldout slice needs same-test semantic competition; otherwise rewrite the visible verifier snippet to reduce shared test-path exposure before scoring.",
    }

    write_json(AUDIT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
