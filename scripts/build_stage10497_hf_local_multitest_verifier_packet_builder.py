#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10497
NAME = "stage10497_hf_local_multitest_verifier_packet_builder"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKET_JSON = OUT_DIR / "hf_local_multitest_verifier_packet.json"
PREVIEW_ROWS_JSONL = OUT_DIR / "hf_local_multitest_verifier_preview_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

REQUEST_JSON = ROOT / "runs/local/artifacts/stage10496_hf_local_verifier_geometry_rebuild_request/hf_local_verifier_geometry_rebuild_request.json"

REPO_ROOT = Path("/data/code_assist")
HF_LOCAL = REPO_ROOT / "src/code_assist/agents/hf_local.py"
CONFIG = REPO_ROOT / "src/code_assist/orchestrator/config.py"
ORCHESTRATOR = REPO_ROOT / "src/code_assist/orchestrator/orchestrator.py"
CLI = REPO_ROOT / "src/code_assist/cli.py"
TEST_PARAMS = REPO_ROOT / "tests/unit/test_hf_local_params.py"
TEST_PLANNER = REPO_ROOT / "tests/unit/test_hf_local_planner_cpu_fallback.py"
TEST_CLI = REPO_ROOT / "tests/integration/test_cli_public_interface.py"

BUNDLE_ID = (
    "stage10497::localsess_code_assist_hf_local_multitest_verifier::python"
)
SOURCE_EPISODE_ID = (
    "localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_26t23_27_57_019bfca2_aa35_7502_b929_649a_"
    "src_code_assist_agents_hf_local_py_src_code_assist_agents_hf_local_planner_py_sr_3fb1ce61a2_aug_1500000_8b46e7f662"
)
SEED_PATHS = [
    "src/code_assist/agents/hf_local.py",
    "src/code_assist/orchestrator/config.py",
    "src/code_assist/orchestrator/orchestrator.py",
]
CANDIDATE_PATHS = [
    "src/code_assist/agents/hf_local.py",
    "src/code_assist/orchestrator/config.py",
    "src/code_assist/orchestrator/orchestrator.py",
    "src/code_assist/cli.py",
]
SELECTED_TESTS = [
    "tests/unit/test_hf_local_params.py",
    "tests/unit/test_hf_local_planner_cpu_fallback.py",
    "tests/integration/test_cli_public_interface.py",
]
PERSPECTIVES = [
    "symptom_localization",
    "evidence_citation",
    "patch_impact",
    "verifier_outcome",
    "abstention_insufficient_evidence",
]


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


def snippet(text: str, *, limit: int = 1200) -> str:
    compact = str(text).strip()
    return compact if len(compact) <= limit else compact[: limit - 3].rstrip() + "..."


def excerpt(path: Path, *, anchor: str, radius: int = 18) -> str:
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    idx = 0
    for i, line in enumerate(lines):
        if anchor in line:
            idx = i
            break
    start = max(0, idx - radius)
    end = min(len(lines), idx + radius)
    return snippet("\n".join(lines[start:end]))


def evidence() -> dict[str, list[dict[str, Any]]]:
    return {
        "candidate_change_surface": [
            {
                "path": "src/code_assist/agents/hf_local.py",
                "source_type": "local_repo",
                "retrieval_reason": "behavior_owner",
                "distance_from_seed": 0,
                "text": excerpt(HF_LOCAL, anchor="def from_params(cls, params: dict[str, str])", radius=28),
            },
            {
                "path": "src/code_assist/agents/hf_local.py",
                "source_type": "local_repo",
                "retrieval_reason": "temperature_and_cuda_logic",
                "distance_from_seed": 0,
                "text": excerpt(HF_LOCAL, anchor='temperature = float(params.get("hf_temperature") or params.get("temperature") or 0.2)', radius=12),
            },
        ],
        "nearby_definition_or_usage_context": [
            {
                "path": "src/code_assist/orchestrator/orchestrator.py",
                "source_type": "local_repo",
                "retrieval_reason": "param_forwarding",
                "distance_from_seed": 1,
                "text": excerpt(ORCHESTRATOR, anchor='params["hf_temperature"] = str(cfg.hf_local.temperature)', radius=12),
            },
            {
                "path": "src/code_assist/orchestrator/config.py",
                "source_type": "local_repo",
                "retrieval_reason": "hf_local_settings_schema",
                "distance_from_seed": 1,
                "text": excerpt(CONFIG, anchor="class HFLocalSettings(BaseModel):", radius=18),
            },
            {
                "path": "src/code_assist/cli.py",
                "source_type": "local_repo",
                "retrieval_reason": "planner_registry_surface",
                "distance_from_seed": 1,
                "text": excerpt(CLI, anchor='planner: str = typer.Option("hf_local_planner"', radius=14),
            },
        ],
        "symptom_or_call_path_analogue": [
            {
                "path": "tests/unit/test_hf_local_params.py",
                "source_type": "local_repo",
                "retrieval_reason": "direct_behavior_check",
                "distance_from_seed": 1,
                "text": excerpt(TEST_PARAMS, anchor="def test_hf_local_prefers_hf_temperature_over_generic_temperature()", radius=24),
            },
            {
                "path": "tests/unit/test_hf_local_planner_cpu_fallback.py",
                "source_type": "local_repo",
                "retrieval_reason": "planner_neighbor_behavior",
                "distance_from_seed": 1,
                "text": excerpt(TEST_PLANNER, anchor="def test_hf_local_planner_retries_on_cpu_after_cuda_oom", radius=28),
            },
            {
                "path": "tests/integration/test_cli_public_interface.py",
                "source_type": "local_repo",
                "retrieval_reason": "cli_listing_neighbor",
                "distance_from_seed": 1,
                "text": excerpt(TEST_CLI, anchor="def test_cli_planner_list_includes_hf_local_planner", radius=16),
            },
        ],
        "verifier_and_test_constraint": [
            {
                "path": "tests/unit/test_hf_local_params.py",
                "source_type": "local_repo",
                "retrieval_reason": "gold_verifier_candidate",
                "distance_from_seed": 1,
                "text": excerpt(TEST_PARAMS, anchor="def test_hf_local_parses_require_cuda_flag()", radius=20),
            },
            {
                "path": "tests/unit/test_hf_local_planner_cpu_fallback.py",
                "source_type": "local_repo",
                "retrieval_reason": "tempting_wrong_planner_test",
                "distance_from_seed": 1,
                "text": excerpt(TEST_PLANNER, anchor='raise RuntimeError("CUDA out of memory. Tried to allocate ...")', radius=18),
            },
            {
                "path": "tests/integration/test_cli_public_interface.py",
                "source_type": "local_repo",
                "retrieval_reason": "tempting_wrong_cli_test",
                "distance_from_seed": 1,
                "text": excerpt(TEST_CLI, anchor='assert "hf_local_planner" in names', radius=12),
            },
        ],
        "external_analogue_reference": [],
        "algorithmic_background_reference": [],
    }


def perspective_task(perspective: str) -> str:
    tasks = {
        "symptom_localization": "Choose the most likely edit target from the visible hf_local parameter-handling and verifier evidence.",
        "evidence_citation": "Name the visible fact that best supports the chosen edit target instead of a nearby planner or CLI surface.",
        "patch_impact": "Compare candidate edits by likely behavior change and blast radius.",
        "verifier_outcome": "Choose the most relevant visible verification target for the proposed fix from multiple plausible hf_local-adjacent tests.",
        "abstention_insufficient_evidence": "Decide whether the visible evidence supports a singleton answer or whether abstention is more honest.",
    }
    return tasks[perspective]


def preview_rows(bundle_evidence: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    visible_keys = sorted(key for key, value in bundle_evidence.items() if value)
    rows: list[dict[str, Any]] = []
    for perspective in PERSPECTIVES:
        if perspective == "verifier_outcome":
            options = [
                "tests/unit/test_hf_local_params.py",
                "tests/unit/test_hf_local_planner_cpu_fallback.py",
                "tests/integration/test_cli_public_interface.py",
            ]
            gold_value = "tests/unit/test_hf_local_params.py"
            answer_kind = "selected_test"
        elif perspective == "abstention_insufficient_evidence":
            options = ["ABSTAIN_INSUFFICIENT_EVIDENCE"] + CANDIDATE_PATHS
            gold_value = "ABSTAIN_INSUFFICIENT_EVIDENCE"
            answer_kind = "abstain"
        else:
            options = list(CANDIDATE_PATHS)
            gold_value = "src/code_assist/agents/hf_local.py"
            answer_kind = "candidate_path" if perspective != "evidence_citation" else "visible_evidence_key"
        rows.append(
            {
                "bundle_id": BUNDLE_ID,
                "source_episode_id": SOURCE_EPISODE_ID,
                "language_family": "python",
                "task_type": perspective,
                "prompt_contract": {
                    "task": perspective_task(perspective),
                    "candidate_paths": list(CANDIDATE_PATHS),
                    "selected_tests": list(SELECTED_TESTS),
                    "visible_evidence_keys": visible_keys,
                    "abstention_option_required": perspective == "abstention_insufficient_evidence",
                },
                "preview_answer_kind": answer_kind,
                "preview_gold_value": gold_value,
                "preview_options": options,
                "status": "needs_review_and_materialization",
            }
        )
    return rows


def main() -> None:
    request = load_json(REQUEST_JSON)
    bundle_evidence = evidence()
    rows = preview_rows(bundle_evidence)
    packet = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "hf_local_multitest_verifier_packet_preview_built",
        "claim_scope": [
            "Materialize a real source-backed hf_local verifier packet preview with multiple plausible verifier targets.",
            "Provide the concrete packet needed to replace the singleton verifier geometry flagged in stage10496.",
        ],
        "source_route": "CODE_ASSIST_HF_LOCAL_MULTITEST_REBUILD_PREVIEW",
        "source_bundle_lineage": {
            "rebuild_request_stage": request["stage"],
            "rebuild_request_path": display(REQUEST_JSON),
            "source_episode_id": SOURCE_EPISODE_ID,
            "repo_id": "code_assist",
        },
        "bundle": {
            "bundle_id": BUNDLE_ID,
            "repo_id": "code_assist",
            "language_family": "python",
            "seed_paths": SEED_PATHS,
            "candidate_paths": CANDIDATE_PATHS,
            "selected_tests": SELECTED_TESTS,
            "selected_tests_count": len(SELECTED_TESTS),
            "maintainer_visible_evidence": bundle_evidence,
            "preview_rows_count": len(rows),
        },
        "verifier_geometry": {
            "minimum_visible_verifier_targets_required": request["rebuild_requirements"]["minimum_visible_verifier_targets"],
            "visible_verifier_targets_present": len(SELECTED_TESTS),
            "gold_verifier_candidate": "tests/unit/test_hf_local_params.py",
            "tempting_wrong_siblings": [
                "tests/unit/test_hf_local_planner_cpu_fallback.py",
                "tests/integration/test_cli_public_interface.py",
            ],
            "why_gold_should_win": "The visible evidence centers HFLocalAgent.from_params parsing semantics, while the sibling tests cover planner CPU fallback and planner-list CLI registration rather than the direct parameter parsing behavior.",
        },
        "anti_cheat_preview": {
            "known_shortcut_risks": request["anti_cheat_gates"]["existing_review_flags"],
            "must_pass_before_execution": request["anti_cheat_gates"]["new_required_checks"],
            "open_risks": [
                "The verifier evidence still contains explicit HFLocalAgent naming in the direct test snippet.",
                "The planner-list sibling may be too weak unless the final packet shows why it remains plausible but wrong.",
            ],
        },
        "next_review_actions": [
            "Adjudicate whether the two sibling tests are strong enough verifier distractors or whether one must be replaced by another hf_local-adjacent test.",
            "Run prompt-target leak audit on the preview rows before bounded execution materialization.",
            "Compile the reviewed packet into bounded executable rows only after anti-cheat pass.",
        ],
        "outputs": {
            "packet_json": display(PACKET_JSON),
            "preview_rows_jsonl": display(PREVIEW_ROWS_JSONL),
        },
    }

    write_json(PACKET_JSON, packet)
    write_jsonl(PREVIEW_ROWS_JSONL, rows)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": packet["decision"],
            "packet": display(PACKET_JSON),
        },
    )
    print(json.dumps(packet, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
