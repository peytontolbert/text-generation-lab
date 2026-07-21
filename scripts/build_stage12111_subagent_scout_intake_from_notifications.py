#!/usr/bin/env python3
"""Materialize bounded subagent scout outputs into the Stage12111 intake file."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 12111
NAME = "stage12111_subagent_scout_intake_from_notifications"
OUT = ROOT / "runs/local/artifacts/stage12111_subagent_scout_intake_audit"
SUMMARY = OUT / "subagent_scout_intake_from_notifications.json"
INTAKE = OUT / "subagent_scout_candidates.jsonl"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def anti(build_only: bool = True) -> dict[str, bool]:
    return {
        "must_use_opaque_shuffled_options": True,
        "no_singleton_options": True,
        "target_not_visible_before_options": True,
        "build_only_not_selected_test": build_only,
    }


def main() -> None:
    rows: list[dict[str, Any]] = [
        {
            "repo_family": "unilm",
            "source_path": "/data/repositories/unilm/decoding/GAD",
            "language": "mixed_build_config_dependency",
            "verifier_type": "static_compile_anchor",
            "available_evidence": [
                "setup.py",
                "pyproject.toml",
                "C++ extension sources: fairseq/data/token_block_utils_fast.cpp, fairseq/data/data_utils_fast.cpp",
                "test/data fixture present",
            ],
            "missing_evidence": ["no captured build/test execution log", "no selected unit test anchor identified yet"],
            "candidate_task_family": "transition_verifier_transition",
            "why_valid": "Local mixed Python/C++ extension root with explicit build config and C++ source files.",
            "reserved_family_conflict": False,
            "conflict_reason": "",
            "suggested_commands": [["python", "setup.py", "build_ext", "--inplace"], ["python", "-m", "pytest", "-q", "-k", "stage12104_nonexistent_filter"]],
            "anti_cheat_notes": anti(build_only=True),
            "split_status": "sealed_candidate",
        },
        {
            "repo_family": "unilm",
            "source_path": "/data/repositories/unilm/kosmos-2/open_clip",
            "language": "mixed_build_config_dependency",
            "verifier_type": "build_config_anchor",
            "available_evidence": ["Makefile", "setup.py", "requirements-test.txt"],
            "missing_evidence": ["no captured build/test execution log", "no selected test anchor identified"],
            "candidate_task_family": "transition_next_action",
            "why_valid": "Build/config dependency root suitable for build-probe versus run-test-if-available decisions.",
            "reserved_family_conflict": False,
            "conflict_reason": "",
            "suggested_commands": [["make", "-n"], ["python", "setup.py", "--help"], ["python", "-m", "pytest", "-q", "-k", "stage12104_nonexistent_filter"]],
            "anti_cheat_notes": anti(build_only=True),
            "split_status": "sealed_candidate",
        },
        {
            "repo_family": "method_comparison",
            "source_path": "/data/repositories/method_comparison/MetaMathQA",
            "language": "mixed_build_config_dependency",
            "verifier_type": "build_config_anchor",
            "available_evidence": ["Makefile"],
            "missing_evidence": ["no C/C++ source found in shallow check", "no test marker found", "no captured build log"],
            "candidate_task_family": "transition_next_action",
            "why_valid": "Fresh local build-config root that can support insufficient-evidence/build-probe transition candidates.",
            "reserved_family_conflict": False,
            "conflict_reason": "",
            "suggested_commands": [["make", "-n"], ["make", "-n", "stage12104_nonexistent_target"]],
            "anti_cheat_notes": anti(build_only=True),
            "split_status": "sealed_candidate",
        },
        {
            "repo_family": "v8",
            "source_path": "/data/repositories/v8/tools/gcmole",
            "language": "c_cpp",
            "verifier_type": "selected_test_anchor",
            "available_evidence": ["Makefile", "gcmole.cc", "gcmole-test.cc", "gcmole_test.py", "test-expectations.txt"],
            "missing_evidence": ["no captured fresh build/test log"],
            "candidate_task_family": "transition_candidate_selection",
            "why_valid": "Strong C++ root with implementation, test file, harness, and Makefile, but family overlaps Stage12107.",
            "reserved_family_conflict": True,
            "conflict_reason": "repo_family v8 appears in Stage12107 work items via turbolizer.",
            "suggested_commands": [["make", "-n"], ["python", "gcmole_test.py"]],
            "anti_cheat_notes": anti(build_only=False),
            "split_status": "dev_only",
        },
        {
            "repo_family": "git",
            "source_path": "/data/repositories/git/t/unit-tests/clar",
            "language": "c_cpp",
            "verifier_type": "static_compile_anchor",
            "available_evidence": ["CMakeLists.txt", "clar.c", "clar.h", "test/CMakeLists.txt", "test/selftest.c", "example/example.c"],
            "missing_evidence": ["no captured cmake/ctest log"],
            "candidate_task_family": "transition_verifier_transition",
            "why_valid": "Self-contained C unit-test framework subtree, but git is a prior transition family.",
            "reserved_family_conflict": True,
            "conflict_reason": "repo_family git appears in prior transition/support artifacts.",
            "suggested_commands": [["cmake", "-S", ".", "-B", "/data/tmp/stage12104_git_clar_build"], ["ctest", "--test-dir", "/data/tmp/stage12104_git_clar_build", "--output-on-failure"]],
            "anti_cheat_notes": anti(build_only=True),
            "split_status": "dev_only",
        },
    ]

    rust_dev = [
        ("LLaMA-Adapter", "/data/repositories/LLaMA-Adapter/gorilla/gorilla-main/eval/eval-scripts/codebleu/parser/tree-sitter-python", "selected_test_anchor"),
        ("tokenizers", "/data/repositories/tokenizers/tokenizers", "selected_test_anchor"),
        ("tokenizers", "/data/repositories/tokenizers/bindings/python", "dependency_resolution_anchor"),
        ("candle/candle-core", "/data/repositories/candle/candle-core", "selected_test_anchor"),
        ("candle/candle-nn", "/data/repositories/candle/candle-nn", "selected_test_anchor"),
        ("perftree", "/data/repositories/perftree/perftree", "build_config_anchor"),
        ("git", "/data/repositories/git/contrib/libgit-rs", "build_config_anchor"),
    ]
    for repo, path, verifier_type in rust_dev:
        rows.append({
            "repo_family": repo,
            "source_path": path,
            "language": "rust",
            "verifier_type": verifier_type,
            "available_evidence": ["Cargo.toml", "local Rust source/build surface"],
            "missing_evidence": ["sealed root-lineage disjointness"],
            "candidate_task_family": "transition_verifier_transition",
            "why_valid": "Technically usable Rust surface, but not sealed-valid because scout found prior transition-family conflict.",
            "reserved_family_conflict": True,
            "conflict_reason": "Rust scout found local Rust candidates overlap Stage120xx or reserved transition families.",
            "suggested_commands": [["cargo", "check", "--locked"], ["cargo", "test", "--locked", "--no-fail-fast"]],
            "anti_cheat_notes": anti(build_only=verifier_type != "selected_test_anchor"),
            "split_status": "dev_only",
        })

    web_dev = [
        ("modelcontextprotocol__typescript-sdk", "/data/repositories/modelcontextprotocol__typescript-sdk/packages/middleware/express", "selected_test_anchor"),
        ("langchain-ai__langgraph", "/data/repositories/langchain-ai__langgraph/libs/cli/js-examples", "selected_test_anchor"),
        ("camel-ai__camel", "/data/repositories/camel-ai__camel/camel/toolkits/hybrid_browser_toolkit/ts", "static_compile_anchor"),
        ("v8", "/data/repositories/v8/tools/clusterfuzz/js_fuzzer", "selected_test_anchor"),
        ("v8", "/data/repositories/v8/tools/turbolizer", "selected_test_anchor"),
        ("aitown", "/data/repositories/ai-town", "build_config_anchor"),
        ("lettaailettacode", "/data/repositories/letta-ai__letta-code", "build_config_anchor"),
        ("openagents", "/data/repositories/OpenAgents/frontend", "build_config_anchor"),
        ("transformerdebugger", "/data/repositories/transformer-debugger/neuron_viewer", "build_config_anchor"),
        ("dspy", "/data/repositories/dspy/inspect-app/react-app", "build_config_anchor"),
        ("cpython", "/data/repositories/cpython/Tools/wasm/emscripten/browser_test", "build_config_anchor"),
        ("microsoftautogen", "/data/repositories/microsoft__autogen/python/packages/autogen-studio/frontend", "build_config_anchor"),
    ]
    for repo, path, verifier_type in web_dev:
        rows.append({
            "repo_family": repo,
            "source_path": path,
            "language": "web_js_ts_html",
            "verifier_type": verifier_type,
            "available_evidence": ["package.json", "local JS/TS build or test surface"],
            "missing_evidence": ["fresh sealed verifier run", "sealed root-lineage disjointness"],
            "candidate_task_family": "transition_verifier_transition",
            "why_valid": "Technically scoutable Web root, but not sealed-valid because scout found exact or family overlap.",
            "reserved_family_conflict": True,
            "conflict_reason": "Web scout found root or repo family overlaps excluded transition families.",
            "suggested_commands": [["npm", "test"], ["npm", "run", "build", "--if-present"]],
            "anti_cheat_notes": anti(build_only=verifier_type != "selected_test_anchor"),
            "split_status": "dev_only",
        })

    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(INTAKE, rows)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "subagent_notifications_materialized_for_deterministic_audit",
        "rows": len(rows),
        "sealed_candidate_rows_claimed_by_scouts": sum(1 for row in rows if row["split_status"] == "sealed_candidate"),
        "dev_only_rows": sum(1 for row in rows if row["split_status"] == "dev_only"),
        "outputs": {"intake": str(INTAKE.relative_to(ROOT)), "summary": str(SUMMARY.relative_to(ROOT))},
    }
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
