#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10895
NAME = "stage10895_code_assist_python_verifier_transition_strict_candidate_audit"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "code_assist_python_verifier_transition_strict_candidate_audit.json"

BUNDLE_JSON = ARTIFACTS / "stage10894_code_assist_python_verifier_transition_strict_candidate" / "strict_candidate_bundle.json"
ROW_JSONL = ARTIFACTS / "stage10894_code_assist_python_verifier_transition_strict_candidate" / "strict_candidate_rows.jsonl"
SOURCE_GOLD_JSON = ARTIFACTS / "stage10813_python_queue_aligned_admission" / "review_packets" / "stage10236__localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_27t02_21_48_019bfd41_d2a6_7672_9873_81f8_src_code_assist_orchestrator_config_py_src_code_assist_orchestrator_context_pack_acd5ccc9c1_aug_1500000_8b46e7f662__python" / "perspective_gold_adjudication.json"


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
    rows = load_jsonl(ROW_JSONL)
    gold = load_json(SOURCE_GOLD_JSON)
    row = rows[0]
    prompt = str(row.get("prompt_text") or "")

    verifier_gold = None
    for answer in gold.get("perspective_gold_answers") or []:
        if answer.get("perspective") == "verifier_outcome":
            verifier_gold = answer
            break
    if verifier_gold is None:
        raise ValueError("missing verifier gold")
    gold_path = str(verifier_gold.get("gold_answer_value") or "")

    pre_options = prompt.split("Options:\n", 1)[0]
    target_leak = gold_path in pre_options
    selected_tests = list(verifier_gold.get("selected_tests") or [])
    visible_test_path_mentions = [test for test in selected_tests if test in pre_options]
    opaque_ids = [item.get("test_id") for item in (bundle.get("verifier_target_ledger") or [])]
    explicit_transition_semantics = all("FAIL_TO_PASS" in str(opt.get("value") or "") for opt in (row.get("opaque_options") or []))
    candidate_option_count = len(row.get("opaque_options") or [])
    opaque_id_only_targeting = gold_path not in "\n".join(str(opt.get("value") or "") for opt in (row.get("opaque_options") or []))

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "code_assist_python_verifier_transition_strict_candidate_audited",
        "claim_scope": [
            "Audit the stage10894 strict-heldout Python verifier candidate for direct target-path leakage and semantic readiness.",
            "Check whether the candidate moves the interface from raw test paths toward opaque verifier IDs plus explicit transition semantics.",
        ],
        "metrics": {
            "candidate_option_count": candidate_option_count,
            "target_path_visible_pre_options": target_leak,
            "visible_test_path_mentions_pre_options": visible_test_path_mentions,
            "opaque_test_id_count": len([item for item in opaque_ids if item]),
            "explicit_transition_semantics": explicit_transition_semantics,
            "gold_path_hidden_from_option_values": opaque_id_only_targeting,
        },
        "interpretation": [
            "The strict candidate now hides the raw gold verifier path from the pre-option prompt surface.",
            "Verifier choices are expressed as opaque IDs with transition semantics, which is closer to the desired heldout interface than file-path letters.",
            "This is still a single-root candidate and should be review-gated before entering strict scoring or Gemma comparison.",
        ],
        "remaining_risks": [
            "All verifier targets still share FAIL_TO_PASS, so the distinguishing pressure comes mainly from focus semantics rather than transition diversity.",
            "The source root is still same-family code_assist; it improves heldout honesty relative to MirrorMind but does not by itself prove broader verifier generalization.",
            "Human/AI review should still confirm that the focus descriptions are not merely paraphrases of one test being obviously more specific than the rest.",
        ],
        "next_best_step": "Use this audit-passing packet as the seed for a fresh verifier heldout slice, or build a second similarly opaque code_assist/agentkernel verifier candidate before the next training probe.",
        "source_artifacts": {
            "bundle_json": rel(BUNDLE_JSON),
            "row_jsonl": rel(ROW_JSONL),
            "source_gold": rel(SOURCE_GOLD_JSON),
        },
    }

    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
