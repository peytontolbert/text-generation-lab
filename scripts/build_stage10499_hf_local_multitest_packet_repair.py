#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10499
NAME = "stage10499_hf_local_multitest_packet_repair"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKET_JSON = OUT_DIR / "hf_local_multitest_repaired_packet.json"
PREVIEW_ROWS_JSONL = OUT_DIR / "hf_local_multitest_repaired_preview_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

SOURCE_PACKET_JSON = ROOT / "runs/local/artifacts/stage10497_hf_local_multitest_verifier_packet_builder/hf_local_multitest_verifier_packet.json"
SOURCE_PREVIEW_ROWS_JSONL = ROOT / "runs/local/artifacts/stage10497_hf_local_multitest_verifier_packet_builder/hf_local_multitest_verifier_preview_rows.jsonl"
AUDIT_JSON = ROOT / "runs/local/artifacts/stage10498_hf_local_multitest_verifier_packet_audit/hf_local_multitest_verifier_packet_audit.json"

REPO_ROOT = Path("/data/code_assist")
HF_LOCAL = REPO_ROOT / "src/code_assist/agents/hf_local.py"
CONFIG = REPO_ROOT / "src/code_assist/orchestrator/config.py"
ORCHESTRATOR = REPO_ROOT / "src/code_assist/orchestrator/orchestrator.py"
CLI = REPO_ROOT / "src/code_assist/cli.py"
TEST_PARAMS = REPO_ROOT / "tests/unit/test_hf_local_params.py"
TEST_PLANNER = REPO_ROOT / "tests/unit/test_hf_local_planner_cpu_fallback.py"
TEST_CLI = REPO_ROOT / "tests/integration/test_cli_public_interface.py"

BUNDLE_ID = "stage10499::localsess_code_assist_hf_local_multitest_repaired::python"
SOURCE_EPISODE_ID = (
    "localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_26t23_27_57_019bfca2_aa35_7502_b929_649a_"
    "src_code_assist_agents_hf_local_py_src_code_assist_agents_hf_local_planner_py_sr_3fb1ce61a2_aug_1500000_8b46e7f662"
)

CANDIDATE_PATHS = [
    "src/code_assist/agents/hf_local.py",
    "src/code_assist/orchestrator/config.py",
    "src/code_assist/orchestrator/orchestrator.py",
    "src/code_assist/cli.py",
]
CANDIDATE_IDS = {
    "A": "src/code_assist/agents/hf_local.py",
    "B": "src/code_assist/orchestrator/config.py",
    "C": "src/code_assist/orchestrator/orchestrator.py",
    "D": "src/code_assist/cli.py",
}
VERIFIER_IDS = {
    "V1": "tests/unit/test_hf_local_params.py",
    "V2": "tests/unit/test_hf_local_planner_cpu_fallback.py",
    "V3": "tests/integration/test_cli_public_interface.py",
}
VISIBLE_EVIDENCE_KEYS = [
    "candidate_change_surface",
    "nearby_definition_or_usage_context",
    "symptom_or_call_path_analogue",
    "verifier_and_test_constraint",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


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


def snippet(text: str, *, limit: int = 900) -> str:
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
    return "\n".join(lines[start:end])


def scrub_names(text: str) -> str:
    replacements = [
        ("HFLocalAgent", "WorkAgent"),
        ("HFLocalConfig", "WorkAgentConfig"),
        ("HFLocalSettings", "WorkAgentSettings"),
        ("HFLocalPlannerAgent", "PlannerNeighborAgent"),
        ("HFLocalPlannerConfig", "PlannerNeighborConfig"),
        ("hf_local_planner", "planner_neighbor"),
        ("hf_local", "work_agent"),
        ("code_assist.agents.hf_local", "package.agents.work_agent"),
        ("code_assist.agents.hf_local_planner", "package.agents.planner_neighbor"),
        ("code_assist", "package"),
    ]
    for src, dst in replacements:
        text = text.replace(src, dst)
    return text


def scrub_paths(text: str) -> str:
    path_map = {
        "tests/unit/test_hf_local_params.py": "VERIFIER_SLOT_V1",
        "tests/unit/test_hf_local_planner_cpu_fallback.py": "VERIFIER_SLOT_V2",
        "tests/integration/test_cli_public_interface.py": "VERIFIER_SLOT_V3",
        "src/code_assist/agents/hf_local.py": "CANDIDATE_SLOT_A",
        "src/code_assist/orchestrator/config.py": "CANDIDATE_SLOT_B",
        "src/code_assist/orchestrator/orchestrator.py": "CANDIDATE_SLOT_C",
        "src/code_assist/cli.py": "CANDIDATE_SLOT_D",
    }
    for src, dst in path_map.items():
        text = text.replace(src, dst)
    return text


def scrub_test_identifiers(text: str) -> str:
    test_names = {
        "test_hf_local_prefers_hf_temperature_over_generic_temperature": "test_visible_verifier_slot_v1_case_a",
        "test_hf_local_allows_zero_temperature_config": "test_visible_verifier_slot_v1_case_b",
        "test_hf_local_parses_require_cuda_flag": "test_visible_verifier_slot_v1_case_c",
        "test_hf_local_planner_retries_on_cpu_after_cuda_oom": "test_visible_verifier_slot_v2_case_a",
        "test_cli_planner_list_includes_hf_local_planner": "test_visible_verifier_slot_v3_case_a",
    }
    for src, dst in test_names.items():
        text = text.replace(src, dst)
    return text


def scrub_text(text: str) -> str:
    text = scrub_names(text)
    text = scrub_paths(text)
    text = scrub_test_identifiers(text)
    text = re.sub(r'"model_id"\s*:\s*"[^"]+"', '"model_id": "<hidden>"', text)
    return snippet(text)


def make_evidence() -> dict[str, list[dict[str, Any]]]:
    return {
        "candidate_change_surface": [
            {
                "evidence_id": "E1",
                "surface_role": "candidate_slot_A_behavior_owner",
                "why_included": "The owning implementation surface contains parameter parsing defaults, temperature precedence, and CUDA requirement handling.",
                "source_kind": "source_backed_summary",
                "text": scrub_text(excerpt(HF_LOCAL, anchor="def from_params(cls, params: dict[str, str])", radius=28)),
            },
            {
                "evidence_id": "E2",
                "surface_role": "candidate_slot_A_temperature_and_cuda_logic",
                "why_included": "A second implementation excerpt isolates the branch where specialized parameter fields override generic defaults.",
                "source_kind": "source_backed_summary",
                "text": scrub_text(excerpt(HF_LOCAL, anchor='temperature = float(params.get("hf_temperature") or params.get("temperature") or 0.2)', radius=12)),
            },
        ],
        "nearby_definition_or_usage_context": [
            {
                "evidence_id": "E3",
                "surface_role": "candidate_slot_C_param_forwarding_neighbor",
                "why_included": "A nearby orchestrator surface forwards several specialized fields into the work-agent params map but does not parse them itself.",
                "source_kind": "source_backed_summary",
                "text": scrub_text(excerpt(ORCHESTRATOR, anchor='params["hf_temperature"] = str(cfg.hf_local.temperature)', radius=12)),
            },
            {
                "evidence_id": "E4",
                "surface_role": "candidate_slot_B_settings_schema_neighbor",
                "why_included": "A nearby schema surface defines defaults and types for the same fields but is not the runtime parser that converts params into agent config.",
                "source_kind": "source_backed_summary",
                "text": scrub_text(excerpt(CONFIG, anchor="class HFLocalSettings(BaseModel):", radius=18)),
            },
            {
                "evidence_id": "E5",
                "surface_role": "candidate_slot_D_cli_neighbor",
                "why_included": "A nearby CLI surface references planner selection and environment setup, making it plausible but weaker than the implementation owner.",
                "source_kind": "source_backed_summary",
                "text": scrub_text(excerpt(CLI, anchor='planner: str = typer.Option("hf_local_planner"', radius=14)),
            },
        ],
        "symptom_or_call_path_analogue": [
            {
                "evidence_id": "E6",
                "surface_role": "verifier_slot_V1_direct_behavior_checks",
                "why_included": "This verifier family checks direct parsing semantics for temperature precedence, zero temperature, and CUDA-flag handling.",
                "source_kind": "source_backed_summary",
                "text": scrub_text(excerpt(TEST_PARAMS, anchor="def test_hf_local_prefers_hf_temperature_over_generic_temperature()", radius=24)),
            },
            {
                "evidence_id": "E7",
                "surface_role": "verifier_slot_V2_planner_neighbor_checks",
                "why_included": "This verifier family checks a related planner-side fallback path after CUDA OOM rather than direct work-agent parameter parsing.",
                "source_kind": "source_backed_summary",
                "text": scrub_text(excerpt(TEST_PLANNER, anchor="def test_hf_local_planner_retries_on_cpu_after_cuda_oom", radius=28)),
            },
            {
                "evidence_id": "E8",
                "surface_role": "verifier_slot_V3_cli_registry_neighbor",
                "why_included": "This verifier family checks CLI planner listing and help text, which is nearby product surface area but not parameter parsing semantics.",
                "source_kind": "source_backed_summary",
                "text": scrub_text(excerpt(TEST_CLI, anchor="def test_cli_planner_list_includes_hf_local_planner", radius=16)),
            },
        ],
        "verifier_and_test_constraint": [
            {
                "evidence_id": "E9",
                "surface_role": "verifier_slot_V1_gold_candidate",
                "why_included": "The strongest visible verifier target directly asserts the parameter-conversion behavior implicated by the implementation excerpts.",
                "source_kind": "source_backed_summary",
                "text": scrub_text(excerpt(TEST_PARAMS, anchor="def test_hf_local_parses_require_cuda_flag()", radius=20)),
            },
            {
                "evidence_id": "E10",
                "surface_role": "verifier_slot_V2_tempting_wrong_candidate",
                "why_included": "A tempting wrong verifier target exercises a related planner fallback but depends on different runtime behavior and config flow.",
                "source_kind": "source_backed_summary",
                "text": scrub_text(excerpt(TEST_PLANNER, anchor='raise RuntimeError("CUDA out of memory. Tried to allocate ...")', radius=18)),
            },
            {
                "evidence_id": "E11",
                "surface_role": "verifier_slot_V3_medium_strength_neighbor",
                "why_included": "A weaker neighbor target touches planner exposure at the CLI surface and remains plausible only as a secondary distractor.",
                "source_kind": "source_backed_summary",
                "text": scrub_text(excerpt(TEST_CLI, anchor='assert "hf_local_planner" in names', radius=12)),
            },
        ],
        "external_analogue_reference": [],
        "algorithmic_background_reference": [],
    }


def preview_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    base_contract = {
        "candidate_options": [{"id": key, "path": value} for key, value in CANDIDATE_IDS.items()],
        "verifier_options": [
            {
                "id": key,
                "role_summary": (
                    "direct parameter parsing checks"
                    if key == "V1"
                    else "planner-side CUDA fallback checks"
                    if key == "V2"
                    else "CLI planner registration checks"
                ),
            }
            for key in ["V1", "V2", "V3"]
        ],
        "visible_evidence_keys": VISIBLE_EVIDENCE_KEYS,
    }
    rows.append(
        {
            "bundle_id": BUNDLE_ID,
            "source_episode_id": SOURCE_EPISODE_ID,
            "language_family": "python",
            "task_type": "symptom_localization",
            "prompt_contract": {
                **base_contract,
                "task": "Choose the most likely edit target from the visible parameter-handling and verifier evidence.",
                "abstention_option_required": False,
            },
            "preview_answer_kind": "candidate_id",
            "preview_gold_value": "A",
            "preview_options": ["A", "B", "C", "D"],
            "status": "repaired_preview_needs_review",
        }
    )
    rows.append(
        {
            "bundle_id": BUNDLE_ID,
            "source_episode_id": SOURCE_EPISODE_ID,
            "language_family": "python",
            "task_type": "evidence_citation",
            "prompt_contract": {
                **base_contract,
                "task": "Choose the visible evidence bucket that best supports the chosen edit target over nearby planner, config, and CLI surfaces.",
                "abstention_option_required": False,
            },
            "preview_answer_kind": "visible_evidence_key",
            "preview_gold_value": "candidate_change_surface",
            "preview_options": list(VISIBLE_EVIDENCE_KEYS),
            "status": "repaired_preview_needs_review",
        }
    )
    rows.append(
        {
            "bundle_id": BUNDLE_ID,
            "source_episode_id": SOURCE_EPISODE_ID,
            "language_family": "python",
            "task_type": "patch_impact",
            "prompt_contract": {
                **base_contract,
                "task": "Choose the edit target with the strongest expected behavior change on the direct parameter-handling bug and the smallest nearby blast radius.",
                "abstention_option_required": False,
            },
            "preview_answer_kind": "candidate_id",
            "preview_gold_value": "A",
            "preview_options": ["A", "B", "C", "D"],
            "status": "repaired_preview_needs_review",
        }
    )
    rows.append(
        {
            "bundle_id": BUNDLE_ID,
            "source_episode_id": SOURCE_EPISODE_ID,
            "language_family": "python",
            "task_type": "verifier_outcome",
            "prompt_contract": {
                **base_contract,
                "task": "Choose the most relevant visible verification target for the proposed fix from multiple plausible neighboring verifier families.",
                "abstention_option_required": False,
            },
            "preview_answer_kind": "verifier_id",
            "preview_gold_value": "V1",
            "preview_options": ["V1", "V2", "V3"],
            "status": "repaired_preview_needs_review",
        }
    )
    rows.append(
        {
            "bundle_id": BUNDLE_ID,
            "source_episode_id": SOURCE_EPISODE_ID,
            "language_family": "python",
            "task_type": "abstention_insufficient_evidence",
            "prompt_contract": {
                **base_contract,
                "task": "Decide whether the visible evidence supports a singleton answer or whether abstention is more honest.",
                "abstention_option_required": True,
            },
            "preview_answer_kind": "abstain",
            "preview_gold_value": "ABSTAIN_INSUFFICIENT_EVIDENCE",
            "preview_options": ["ABSTAIN_INSUFFICIENT_EVIDENCE", "A", "B", "C", "D"],
            "status": "repaired_preview_needs_review",
        }
    )
    return rows


def main() -> None:
    source_packet = load_json(SOURCE_PACKET_JSON)
    source_rows = load_jsonl(SOURCE_PREVIEW_ROWS_JSONL)
    audit = load_json(AUDIT_JSON)
    repaired_evidence = make_evidence()
    rows = preview_rows()

    packet = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "hf_local_multitest_packet_repaired",
        "claim_scope": [
            "Repair the Stage10497 hf_local packet so maintainer-visible evidence is still source-backed but no longer exposes concrete target paths or raw symbol-name shortcuts.",
            "Prepare an execution-quality preview with opaque candidate IDs and verifier IDs for later bounded materialization.",
        ],
        "source_artifacts": {
            "source_packet": display(SOURCE_PACKET_JSON),
            "source_preview_rows": display(SOURCE_PREVIEW_ROWS_JSONL),
            "stage10498_audit": display(AUDIT_JSON),
        },
        "bundle": {
            "bundle_id": BUNDLE_ID,
            "repo_id": "code_assist",
            "language_family": "python",
            "candidate_id_map": CANDIDATE_IDS,
            "verifier_id_map": VERIFIER_IDS,
            "selected_tests_count": 3,
            "maintainer_visible_evidence": repaired_evidence,
            "preview_rows_count": len(rows),
        },
        "repair_actions": [
            "Removed concrete file paths from visible evidence entries and replaced them with opaque candidate or verifier slot roles.",
            "Scrubbed direct HFLocalAgent and hf_local naming from snippets to reduce symbol-name solving.",
            "Converted verifier options from raw test paths to opaque verifier IDs with role summaries.",
            "Kept the CLI verifier sibling but downgraded it explicitly to medium-strength neighbor status instead of pretending it is equal semantic competition.",
        ],
        "known_limits": [
            "The V3 CLI neighbor remains weaker than V2 and V1 because the repo does not expose a richer third hf_local-adjacent verifier family.",
            "This repair improves anti-cheat quality but still requires a fresh audit before bounded execution materialization.",
        ],
        "comparison_to_stage10497": {
            "source_preview_rows_count": len(source_rows),
            "repaired_preview_rows_count": len(rows),
            "source_candidate_paths_count": len(source_packet["bundle"]["candidate_paths"]),
            "repaired_candidate_paths_count": len(CANDIDATE_IDS),
        },
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
