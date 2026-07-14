#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
OUT_DIR = ARTIFACTS / "stage11027_next_source_materialization_request"

SCALING_ATLAS = ARTIFACTS / "stage10417_multilingual_reviewed_scaling_atlas" / "multilingual_reviewed_scaling_atlas.json"
LONG_CONTEXT_ROOTS = ARTIFACTS / "stage10516_long_context_root_state_compiler" / "compiled_root_records.jsonl"
ACQ_ATLAS = ARTIFACTS / "stage11026_multilingual_fresh_source_acquisition_atlas" / "multilingual_fresh_source_acquisition_atlas.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def pick_root(rows: list[dict], language: str, repo_family: str, preferred_verifier: str = "PASS_TARGETED_TEST_SELECTION") -> dict | None:
    matches = [r for r in rows if r.get("language_family") == language and r.get("repo_family") == repo_family]
    if not matches:
        return None
    exact = [r for r in matches if r.get("verifier_id") == preferred_verifier]
    audited = [r for r in exact if str(r.get("root_id", "")).startswith("audited::")]
    if audited:
        return audited[0]
    if exact:
        return exact[0]
    audited = [r for r in matches if str(r.get("root_id", "")).startswith("audited::")]
    if audited:
        return audited[0]
    return matches[0]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    scaling = read_json(SCALING_ATLAS)
    long_context_roots = read_jsonl(LONG_CONTEXT_ROOTS)
    acquisition = read_json(ACQ_ATLAS)

    admitted = scaling.get("admitted_bundle_rows", [])
    bundle_lookup = {row["bundle_id"]: row for row in admitted}

    request_rows: list[dict] = []

    def add_reviewed(bundle_id: str, priority: int, objective: str, why: str) -> None:
        row = bundle_lookup[bundle_id]
        request_rows.append(
            {
                "priority": priority,
                "request_kind": "reviewed_bundle_materialization",
                "language_family": row["language_family"],
                "repo_id": row["repo_id"],
                "bundle_id": bundle_id,
                "selected_tests": row.get("selected_tests", []),
                "candidate_paths": row.get("candidate_paths", []),
                "visible_evidence_keys": row.get("visible_evidence_keys", []),
                "objective": objective,
                "why_now": why,
                "anti_cheat_requirements": [
                    "Preserve selected-test anchors as visible verifier evidence where available.",
                    "Do not expose target path strings before options.",
                    "Retain candidate-surface distractors so the row tests evidence-role choice rather than lexical matching.",
                    "Keep new roots disjoint from the frozen 23-row overlay claim path until explicitly admitted."
                ],
            }
        )

    def add_seed(language: str, repo_family: str, priority: int, objective: str, why: str) -> None:
        root = pick_root(long_context_roots, language, repo_family)
        if root is None:
            return
        request_rows.append(
            {
                "priority": priority,
                "request_kind": "long_context_seed_materialization",
                "language_family": language,
                "repo_id": root.get("repo_id"),
                "repo_family": repo_family,
                "root_id": root.get("root_id"),
                "snapshot_id": root.get("snapshot_id"),
                "verifier_id": root.get("verifier_id"),
                "source_family_id": root.get("source_family_id"),
                "objective": objective,
                "why_now": why,
                "anti_cheat_requirements": [
                    "Recover maintainer-visible evidence from the source root rather than synthetic template summaries.",
                    "Materialize selected-test or verifier anchors explicitly before scoring.",
                    "Reject the row if prompt-visible evidence cannot justify one answer or honest abstention.",
                    "Keep root-level split isolation and avoid same-family overlap with current strict overlay."
                ],
            }
        )

    add_reviewed(
        "stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_28t20_02_25_019acc0f_4bd7_77f2_b15f_3b0c_models_mirrormind_init_py_models_mirrormind_context_py_models_mirrormind_coordin_fd8013631e_aug_1500000_8b46e7f662::python",
        1,
        "materialize_python_verifier_and_evidence_successor_rows",
        "MirrorMind is the strongest reviewed Python packet beyond the current immediate root and directly touches the remaining verifier frontier.",
    )
    add_reviewed(
        "stage10119::localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_26t17_53_18_019d2b47_7d2d_7622_8e05_3513_agent_kernel_modeling_ssm_kernels_src_selective_scan_cpp_agent_kernel_modeling_w_5511e7fec6_aug_1500000_8b46e7f662::c_cpp",
        2,
        "materialize_c_cpp_counterfamily_and_verifier_ledgers",
        "This admitted C/C++ bundle already has selected tests and a rich candidate set, so it is the cleanest non-parametergolf immediate expansion root.",
    )
    add_reviewed(
        "stage10119::localsess_parametergolf_sessseed_codex_sessions_rollout_2026_03_28t16_56_21_019d3560_1014_7761_9ea7_5638_parameter_golf_records_track_10min_16mb_2026_03_26_statespace_causalmachine_cuda_a018ca0b43_aug_1500000_8b46e7f662::c_cpp",
        3,
        "expand_parametergolf_beyond_current_single_root",
        "Parametergolf is already productive, but it still only contributes one fresh C/C++ root to the current evidence bank.",
    )
    add_reviewed(
        "stage10176::localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_27t13_13_10_019bff96_2dc5_7162_88f8_83eb_src_code_assist_orchestrator_cognitive_perfection_py_src_code_assist_orchestrato_3a0f6d8311_aug_1500000_8b46e7f662::web_js_ts_html",
        4,
        "use_as_web_overlap_control_until_pure_web_selected_tests_exist",
        "This is the only reviewed web bundle here with a selected test anchor, so it should be kept as a stress/control lane while pure-web supply is built.",
    )

    add_seed(
        "python",
        "faiss",
        5,
        "materialize_python_seed_roots_with_pass_targeted_test_selection",
        "Faiss is a clean non-current Python seed family with multiple PASS_TARGETED_TEST_SELECTION roots.",
    )
    add_seed(
        "python",
        "diffusers",
        6,
        "materialize_python_seed_roots_with_test_and_evidence_ledgers",
        "Diffusers offers multiple Python roots and some broader verifier variants, useful for moving beyond repository_library.",
    )
    add_seed(
        "python",
        "django",
        7,
        "materialize_python_seed_roots_with_real_test_routing",
        "Django gives a distinct Python family with targeted-test signals and should reduce same-family overfitting.",
    )
    add_seed(
        "python",
        "openai-agents-python",
        8,
        "materialize_python_agentic_seed_roots",
        "OpenAI Agents Python is a strong candidate for maintainer-style action/evidence rows with different abstractions than current roots.",
    )
    add_seed(
        "c_cpp",
        "onnxruntime",
        9,
        "materialize_new_c_cpp_evidence_roots",
        "ONNX Runtime is the clearest fresh non-current C/C++ family from the long-context inventory.",
    )
    add_seed(
        "c_cpp",
        "cccl",
        10,
        "materialize_new_c_cpp_evidence_roots",
        "CCCL is the second strongest non-current C/C++ seed family and already appears in support rows.",
    )
    add_seed(
        "web_js_ts_html",
        "mem0",
        11,
        "acquire_pure_web_selected_test_family",
        "mem0 is the clearest non-current web seed family in the long-context inventory and should be mined for a pure-web selected-test root.",
    )

    request_rows.sort(key=lambda row: (row["priority"], row["language_family"], row.get("repo_id", "")))

    summary = {
        "stage": 11027,
        "stage_name": "next_source_materialization_request",
        "claim_scope": [
            "Convert the multilingual acquisition atlas into an executable next-source request with exact reviewed bundles and exact long-context seed roots.",
            "Name the immediate Python/C++/web roots that should be materialized before another broad evidence probe.",
            "Keep the request honest about overlap: code_assist web remains a control/stress lane, not a promotable pure-web headline root."
        ],
        "source_artifacts": {
            "reviewed_scaling_atlas": str(SCALING_ATLAS.relative_to(ROOT)),
            "long_context_root_records": str(LONG_CONTEXT_ROOTS.relative_to(ROOT)),
            "multilingual_fresh_source_acquisition_atlas": str(ACQ_ATLAS.relative_to(ROOT)),
        },
        "metrics": {
            "request_count": len(request_rows),
            "by_language": dict(sorted({lang: sum(1 for row in request_rows if row["language_family"] == lang) for lang in {row['language_family'] for row in request_rows}}.items())),
            "reviewed_bundle_requests": sum(1 for row in request_rows if row["request_kind"] == "reviewed_bundle_materialization"),
            "long_context_seed_requests": sum(1 for row in request_rows if row["request_kind"] == "long_context_seed_materialization"),
        },
        "findings": [
            "The next source work can now start from exact bundle IDs and exact long-context root IDs rather than repo-family guesses.",
            "MirrorMind is the best immediate Python expansion root because it is reviewed, selected-test anchored, and directly relevant to the remaining Python verifier miss.",
            "ONNX Runtime and CCCL are the clearest non-current C/C++ seed families, while mem0 is the clearest non-current web seed family.",
        ],
        "next_best_step": "Materialize the priority-1 through priority-4 reviewed roots first, then begin seed-family materialization for faiss/diffusers/django/openai-agents-python/onnxruntime/cccl/mem0.",
        "outputs": {
            "summary_json": str((OUT_DIR / "next_source_materialization_request.json").relative_to(ROOT)),
            "request_rows_jsonl": str((OUT_DIR / "request_rows.jsonl").relative_to(ROOT)),
        },
        "passed": True,
    }

    write_jsonl(OUT_DIR / "request_rows.jsonl", request_rows)
    (OUT_DIR / "next_source_materialization_request.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
