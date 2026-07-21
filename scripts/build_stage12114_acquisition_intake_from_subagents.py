#!/usr/bin/env python3
"""Materialize normalized Stage12114 acquisition intake from subagent scouts."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "runs/local/artifacts/stage12114_fresh_repo_acquisition_intake_audit"
SUMMARY = OUT / "subagent_acquisition_intake_materialization.json"
MIRROR = ROOT / "runs/summaries/stage12114_subagent_acquisition_intake_materialization.json"
INTAKE = ROOT / "runs/local/artifacts/stage12113_fresh_repo_acquisition_plan/fresh_repo_acquisition_scout_candidates.jsonl"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def acquisition_row(
    *,
    repo: str,
    language: str,
    verifier_type: str,
    available_evidence: list[str],
    missing_evidence: list[str],
    suggested_commands: list[list[str]],
    why_valid: str,
    scout: str,
) -> dict[str, Any]:
    return {
        "repo_family": repo,
        "source_path_or_acquisition_target": f"https://github.com/{repo}",
        "exists_locally": False,
        "language": language,
        "verifier_type": verifier_type,
        "available_evidence": available_evidence,
        "missing_evidence": missing_evidence,
        "suggested_commands": suggested_commands,
        "reserved_family_conflict": False,
        "conflict_reason": "",
        "split_status": "needs_acquisition",
        "why_valid": why_valid,
        "risk_notes": [
            "needs local checkout before it can become evidence",
            "selected-test claims require actual test discovery and execution after acquisition",
            "build-only scope must remain build_config_anchor/static_compile_anchor if no selected test is found",
            "not a train/eval row until verifier logs and anti-cheat fields are materialized",
        ],
        "anti_cheat_notes": [
            "target semantic value must be hidden before options",
            "opaque shuffled non-singleton options required at row materialization",
            "canonical repo lineage must be rechecked after checkout",
        ],
        "subagent_scout": scout,
        "stage12114_source": "subagent_acquisition_scout_normalized",
    }


def local_row(
    *,
    repo: str,
    path: str,
    language: str,
    verifier_type: str,
    available_evidence: list[str],
    suggested_commands: list[list[str]],
    why_valid: str,
    scout: str,
) -> dict[str, Any]:
    return {
        "repo_family": repo,
        "source_path_or_acquisition_target": path,
        "exists_locally": True,
        "language": language,
        "verifier_type": verifier_type,
        "available_evidence": available_evidence,
        "missing_evidence": ["verifier execution log", "anti-cheat row materialization", "root-lineage confirmation"],
        "suggested_commands": suggested_commands,
        "reserved_family_conflict": False,
        "conflict_reason": "",
        "split_status": "sealed_candidate",
        "why_valid": why_valid,
        "risk_notes": [
            "local candidate still requires deterministic probe before row admission",
            "selected-test scope is not claimed for static/build-only candidates",
            "build-only scope is explicit and must not be used as selected-test evidence",
        ],
        "anti_cheat_notes": [
            "target semantic value must be hidden before options",
            "opaque shuffled non-singleton options required at row materialization",
            "canonical repo lineage must be rechecked against prior transition artifacts",
        ],
        "subagent_scout": scout,
        "stage12114_source": "subagent_local_scout_normalized",
    }


def build_rows() -> list[dict[str, Any]]:
    rust_repos = [
        "BurntSushi/ripgrep",
        "sharkdp/fd",
        "sharkdp/bat",
        "eza-community/eza",
        "starship/starship",
        "alacritty/alacritty",
        "helix-editor/helix",
        "nushell/nushell",
        "rust-lang/rust-analyzer",
        "tokio-rs/tokio",
        "hyperium/hyper",
        "tokio-rs/axum",
        "serde-rs/serde",
        "clap-rs/clap",
        "bevyengine/bevy",
        "swc-project/swc",
        "denoland/deno",
        "tauri-apps/tauri",
        "zellij-org/zellij",
        "nextest-rs/nextest",
    ]
    web_repos = [
        "vitejs/vite",
        "vercel/next.js",
        "sveltejs/svelte",
        "withastro/astro",
        "vuejs/core",
        "solidjs/solid",
        "remix-run/remix",
        "storybookjs/storybook",
        "microsoft/playwright",
        "vitest-dev/vitest",
        "tailwindlabs/tailwindcss",
        "facebook/docusaurus",
    ]
    c_cpp_repos = [
        "fmtlib/fmt",
        "catchorg/Catch2",
        "nlohmann/json",
        "google/googletest",
        "gabime/spdlog",
        "CLIUtils/CLI11",
        "capnproto/capnproto",
    ]

    rows: list[dict[str, Any]] = []
    for repo in rust_repos:
        rows.append(
            acquisition_row(
                repo=repo,
                language="rust",
                verifier_type="selected_test_anchor",
                available_evidence=["expected Cargo.toml workspace marker", "expected Rust source tree", "expected cargo test targets"],
                missing_evidence=["fresh checkout", "selected test discovery", "verifier execution log"],
                suggested_commands=[["cargo", "test", "--locked"], ["cargo", "test", "--workspace", "--locked"]],
                why_valid="Rust acquisition target can supply selected-test transition rows if checkout exposes cargo tests and role-distinct source evidence.",
                scout="rust_acquisition_scout",
            )
        )
    for repo in web_repos:
        rows.append(
            acquisition_row(
                repo=repo,
                language="web_js_ts_html",
                verifier_type="selected_test_anchor",
                available_evidence=["expected package.json", "expected JS/TS source tree", "expected npm/pnpm/yarn test scripts"],
                missing_evidence=["fresh checkout", "test script hydration", "verifier execution log"],
                suggested_commands=[["npm", "test"], ["pnpm", "test"], ["yarn", "test"]],
                why_valid="Web acquisition target can supply verifier-grounded OpenHands/Llama-style transition analogues after local test discovery.",
                scout="web_acquisition_scout",
            )
        )
    for repo in c_cpp_repos:
        rows.append(
            acquisition_row(
                repo=repo,
                language="c_cpp",
                verifier_type="selected_test_anchor",
                available_evidence=["expected CMakeLists.txt or build manifest", "expected C/C++ source tree", "expected ctest or unit-test target"],
                missing_evidence=["fresh checkout", "build hydration", "ctest or selected verifier execution log"],
                suggested_commands=[["cmake", "-S", ".", "-B", "build"], ["cmake", "--build", "build"], ["ctest", "--test-dir", "build", "--output-on-failure"]],
                why_valid="C/C++ acquisition target can supply build/test transition rows if checkout exposes ctest or comparable focused verifier targets.",
                scout="c_cpp_acquisition_scout",
            )
        )

    rows.extend(
        [
            local_row(
                repo="mentals-ai",
                path="/data/repositories/mentals-ai",
                language="c_cpp",
                verifier_type="static_compile_anchor",
                available_evidence=["local repository path", "C/C++ source markers expected by scout"],
                suggested_commands=[["cmake", "-S", ".", "-B", "build"], ["cmake", "--build", "build"]],
                why_valid="Local C/C++ candidate for static compile/build transition probing, not selected-test evidence.",
                scout="c_cpp_acquisition_scout",
            ),
            local_row(
                repo="mentals-ai-liboai",
                path="/data/repositories/mentals-ai/src/liboai",
                language="c_cpp",
                verifier_type="static_compile_anchor",
                available_evidence=["local nested C/C++ source path", "build/source markers expected by scout"],
                suggested_commands=[["cmake", "-S", ".", "-B", "build"], ["cmake", "--build", "build"]],
                why_valid="Nested local C/C++ candidate retained for audit; repo-family cap/nested-root risk must be checked deterministically.",
                scout="c_cpp_acquisition_scout",
            ),
            local_row(
                repo="openwebvoyager-megatron-datasets",
                path="/data/repositories/OpenWebVoyager/training/Pai-Megatron-Patch/Megatron-LM-240424/megatron/core/datasets",
                language="mixed_build_config_dependency",
                verifier_type="build_config_anchor",
                available_evidence=["local mixed build/dependency subtree", "dataset/build configuration source path"],
                suggested_commands=[["python", "-m", "py_compile", "."], ["pytest", "-q"]],
                why_valid="Local mixed build/config dependency candidate; valid only for build/config transition decisions after probe.",
                scout="c_cpp_acquisition_scout",
            ),
        ]
    )
    return rows


def main() -> None:
    rows = build_rows()
    write_jsonl(INTAKE, rows)
    summary = {
        "stage": 12114,
        "stage_name": "stage12114_subagent_acquisition_intake_materialization",
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "subagent_acquisition_intake_materialized",
        "input_source": "second_round_subagent_scout_outputs_normalized_by_main_agent",
        "do_not_train": True,
        "rows_written": len(rows),
        "rows_by_language": {
            "c_cpp": 9,
            "mixed_build_config_dependency": 1,
            "rust": 20,
            "web_js_ts_html": 12,
        },
        "normalizations": [
            "cargo_test_after_acquisition -> selected_test_anchor",
            "selected_test_anchor_candidate -> selected_test_anchor",
            "ctest_anchor -> selected_test_anchor",
            "local build-only candidates retained as static_compile_anchor/build_config_anchor",
        ],
        "claim_boundary": [
            "needs_acquisition targets are leads only, not evidence",
            "local candidates are not train/eval rows until deterministic verifier probes and anti-cheat row admission pass",
            "build/static candidates cannot be used as selected-test rows unless a real selected verifier is discovered later",
        ],
        "outputs": {
            "intake_jsonl": rel(INTAKE),
            "summary": rel(SUMMARY),
            "summary_mirror": rel(MIRROR),
        },
    }
    write_json(SUMMARY, summary)
    write_json(MIRROR, summary)
    print(json.dumps({"decision": summary["decision"], "rows_written": len(rows), "rows_by_language": summary["rows_by_language"], "intake_jsonl": rel(INTAKE)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
