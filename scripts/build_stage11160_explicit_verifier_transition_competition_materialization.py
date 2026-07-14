#!/usr/bin/env python3
"""Materialize explicit verifier-transition competition rows from local tests.

The previous local verifier support rows only taught "which verifier is the
direct PASS_TO_PASS guardrail".  This stage projects the same kind of local
source/test evidence into explicit transition classification:

  focused verifier target -> PASS_TO_PASS | NOT_EXERCISED | FAIL_TO_PASS | INSUFFICIENT_EVIDENCE

Rows are review/support candidates only.  They are source-backed and pytest
anchored, but they are not promotion heldout rows.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "runs/local/artifacts/stage11160_explicit_verifier_transition_competition_materialization"
CURRENT_STRICT = (
    ROOT
    / "runs/local/artifacts/stage11146_singleton_strict_quarantine_successor/agentkernel_lite_encdec_strict_eval.jsonl"
)

PAIR_CANDIDATES = [
    ("scripts/materialize_trainer_setup.py", "tests/test_materialize_trainer_setup.py", "materialize"),
    ("scripts/learning_signal_contract_builder.py", "tests/test_learning_signal_contract_builder.py", "build_learning_signal_rows"),
    ("scripts/learning_signal_implementation_plan_builder.py", "tests/test_learning_signal_implementation_plan_builder.py", "build_plan_rows"),
    ("scripts/commit_inventory_dry_run_design_builder.py", "tests/test_commit_inventory_dry_run_gate_audit.py", "build_inventory_design_rows"),
    ("scripts/commit_learning_signal_contract_builder.py", "tests/test_commit_learning_signal_contract_builder.py", "build_learning_signal_rows"),
    ("scripts/model_output_capture_preflight_audit.py", "tests/test_model_output_capture_preflight_audit.py", "audit_rows"),
    ("scripts/model_output_capture_preflight_builder.py", "tests/test_model_output_capture_preflight_audit.py", "build_preflight_rows"),
    ("scripts/model_output_packet_telemetry_contract_builder.py", "tests/test_model_output_packet_telemetry_contract_builder.py", "build_contract_rows"),
    ("scripts/heldout_non_ce_decoder_eval_design_builder.py", "tests/test_heldout_non_ce_decoder_eval_design_builder.py", "build_card"),
    ("scripts/route_card_materializer.py", "tests/test_stage9137_synthetic_route_card_materializer_smoke_audit.py", "materialize_synthetic_route_cards"),
    ("scripts/metadata_only_path_inventory.py", "tests/test_stage9149_metadata_only_inventory_runner_dry_run.py", "inventory_paths"),
    ("scripts/domain_twin_adapter_validator.py", "tests/test_domain_twin_synthetic_adapter_validator_stage9048.py", "validate_source_record"),
    ("scripts/native_probe_preflight_gate.py", "tests/test_native_probe_preflight_gate.py", "audit_preflight_rows"),
    ("scripts/build_stage8894_registry_frontier_collision_guard.py", "tests/test_registry_frontier_collision_guard.py", "frontier_collision_audit"),
    ("scripts/build_stage8893_no_execution_telemetry_gate_matrix.py", "tests/test_no_execution_telemetry_gate_matrix.py", "build_matrix_audit"),
]

LABELS = list("ABCDEFGH")
TRANSITIONS = [
    "PASS_TO_PASS | focused verifier passed on current source snapshot",
    "NOT_EXERCISED | focused verifier is not tied to the shown source surface",
    "FAIL_TO_PASS | focused verifier is observed failing before a repair and passing after it",
    "INSUFFICIENT_EVIDENCE | visible evidence is not enough to determine the transition",
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def protected_roots() -> set[str]:
    return {str(row.get("source_root_id")) for row in read_jsonl(CURRENT_STRICT) if row.get("source_root_id")}


def compact(text: str, max_chars: int = 1100) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def snippet(path: Path, needle: str | None = None, max_chars: int = 1100) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    if needle and needle in text:
        idx = max(0, text.index(needle) - 350)
        return compact(text[idx : idx + max_chars], max_chars)
    return compact(text[:max_chars], max_chars)


def run_pytest(test_path: str) -> dict[str, Any]:
    proc = subprocess.run(
        ["pytest", "-q", test_path],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
    )
    return {
        "command": f"pytest -q {test_path}",
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout[-1200:],
        "stderr_tail": proc.stderr[-1200:],
    }


def shuffled_options(row_id: str) -> list[dict[str, str]]:
    keyed = []
    for i, value in enumerate(TRANSITIONS):
        digest = hashlib.sha256(f"{row_id}::{i}::{value}".encode()).hexdigest()
        keyed.append((digest, value))
    return [
        {"label": label, "value": value}
        for label, (_, value) in zip(LABELS, sorted(keyed))
    ]


def target_label(options: list[dict[str, str]], transition_prefix: str) -> str:
    return next(opt["label"] for opt in options if opt["value"].startswith(transition_prefix))


def imported_module_name(source: str) -> str:
    module = source.removesuffix(".py").replace("/", ".")
    return module


def make_prompt(
    *,
    source: str,
    direct_test: str,
    distractor_test: str,
    symbol_hint: str,
    focus: str,
    focus_evidence: str,
    source_snippet: str,
    direct_test_snippet: str,
    distractor_test_snippet: str,
    direct_result: dict[str, Any],
    distractor_result: dict[str, Any],
    options: list[dict[str, str]],
) -> str:
    return (
        "Language: python\n"
        "Perspective: verifier_outcome_semantic_transition\n"
        "Task: Choose the semantic transition for the focused verifier target. "
        "Use only visible source, test, and command evidence. Do not choose FAIL_TO_PASS unless a failing-before/passing-after repair transition is actually visible.\n"
        "Repository: agentkernel-seq2seq-text-lab\n"
        f"Visible source surface: {source}\n"
        f"Focused verifier target: {focus}\n"
        "Visible evidence:\n"
        f"E1 source snippet [{source}]: {source_snippet}\n"
        f"E2 direct test snippet [{direct_test}]: {direct_test_snippet}\n"
        f"E3 neighboring test snippet [{distractor_test}]: {distractor_test_snippet}\n"
        f"E4 direct verifier result: {direct_result['command']} -> returncode={direct_result['returncode']} passed={direct_result['passed']}\n"
        f"E5 neighboring verifier result: {distractor_result['command']} -> returncode={distractor_result['returncode']} passed={distractor_result['passed']}\n"
        f"E6 focus-specific evidence: {focus_evidence}\n"
        "Options:\n"
        + "\n".join(f"{opt['label']}. {opt['value']}" for opt in options)
        + "\nAnswer:\n"
    )


def make_row(
    *,
    source: str,
    direct_test: str,
    distractor_test: str,
    symbol_hint: str,
    variant: str,
    target_transition: str,
    focus: str,
    focus_evidence: str,
    direct_result: dict[str, Any],
    distractor_result: dict[str, Any],
) -> dict[str, Any]:
    root_id = f"stage11160::local_transition::{source}::{direct_test}"
    row_id = f"{root_id}::{variant}"
    options = shuffled_options(row_id)
    label = target_label(options, target_transition)
    prompt = make_prompt(
        source=source,
        direct_test=direct_test,
        distractor_test=distractor_test,
        symbol_hint=symbol_hint,
        focus=focus,
        focus_evidence=focus_evidence,
        source_snippet=snippet(ROOT / source, symbol_hint),
        direct_test_snippet=snippet(ROOT / direct_test, symbol_hint),
        distractor_test_snippet=snippet(ROOT / distractor_test),
        direct_result=direct_result,
        distractor_result=distractor_result,
        options=options,
    )
    return {
        "row_id": row_id,
        "source_root_id": root_id,
        "source_bundle_id": root_id,
        "repo_id": "agentkernel-seq2seq-text-lab",
        "repo_family": "agentkernel-seq2seq-text-lab",
        "language_family": "python",
        "task_type": "verifier_outcome_semantic_transition",
        "surface": "maintainer_bundle_compact_bounded_choice",
        "split": "train",
        "split_role": "review_queue_only",
        "train_support_only": True,
        "strict_eval_eligible": False,
        "selected_test_anchor": True,
        "verifier_anchor": True,
        "objective_family": "bounded_decoder_ce",
        "expected_enabled_loss": "decoder_ce",
        "disable_losses": [],
        "loss_mask": {"decoder_ce": True},
        "input_text": prompt,
        "prompt_text": prompt,
        "target_text": label,
        "decoder_text": label,
        "target_token_len": 1,
        "opaque_options": options,
        "semantic_target_value": target_transition,
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "explicit_transition_options": True,
            "focused_verifier_target": True,
            "source_snippet_visible": True,
            "direct_test_snippet_visible": True,
            "neighboring_test_snippet_visible": True,
            "pytest_results_visible": True,
            "review_queue_only": True,
        },
        "standalone_projection_source": {
            "projection_mode": "stage11160_explicit_verifier_transition_competition_materialization",
            "source_path": source,
            "direct_test_path": direct_test,
            "distractor_test_path": distractor_test,
            "variant": variant,
            "target_transition": target_transition,
            "direct_result": direct_result,
            "distractor_result": distractor_result,
        },
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    protected = protected_roots()
    rows: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    pytest_cache: dict[str, dict[str, Any]] = {}
    valid_pairs: list[tuple[str, str, str]] = []

    for source, test, symbol_hint in PAIR_CANDIDATES:
        root_id = f"stage11160::local_transition::{source}::{test}"
        reasons = []
        if root_id in protected:
            reasons.append("root_overlaps_clean_strict")
        if not (ROOT / source).exists():
            reasons.append("missing_source")
        if not (ROOT / test).exists():
            reasons.append("missing_test")
        if reasons:
            blockers.append({"source": source, "test": test, "blockers": reasons})
            continue
        result = run_pytest(test)
        pytest_cache[test] = result
        if not result["passed"]:
            blockers.append({"source": source, "test": test, "blockers": ["pytest_not_passing"], "pytest_result": result})
            continue
        valid_pairs.append((source, test, symbol_hint))

    for idx, (source, direct_test, symbol_hint) in enumerate(valid_pairs):
        distractor_source, distractor_test, _ = valid_pairs[(idx + 3) % len(valid_pairs)]
        if distractor_test not in pytest_cache:
            pytest_cache[distractor_test] = run_pytest(distractor_test)
        direct_result = pytest_cache[direct_test]
        distractor_result = pytest_cache[distractor_test]
        module_name = imported_module_name(source)

        rows.append(
            make_row(
                source=source,
                direct_test=direct_test,
                distractor_test=distractor_test,
                symbol_hint=symbol_hint,
                variant="direct_pass_to_pass",
                target_transition="PASS_TO_PASS",
                focus=f"V1 direct verifier {direct_test}",
                focus_evidence=f"The focused test imports or targets {module_name} and the command passes on the current snapshot.",
                direct_result=direct_result,
                distractor_result=distractor_result,
            )
        )
        rows.append(
            make_row(
                source=source,
                direct_test=direct_test,
                distractor_test=distractor_test,
                symbol_hint=symbol_hint,
                variant="neighbor_not_exercised",
                target_transition="NOT_EXERCISED",
                focus=f"V2 neighboring verifier {distractor_test}",
                focus_evidence=(
                    f"The focused neighboring test is paired with {distractor_source}, not {source}; "
                    "there is no visible evidence that it exercises the shown source surface."
                ),
                direct_result=direct_result,
                distractor_result=distractor_result,
            )
        )
        rows.append(
            make_row(
                source=source,
                direct_test=direct_test,
                distractor_test=distractor_test,
                symbol_hint=symbol_hint,
                variant="missing_verifier_insufficient",
                target_transition="INSUFFICIENT_EVIDENCE",
                focus="V3 hidden or unspecified verifier target",
                focus_evidence=(
                    "No concrete focused verifier path, test snippet, or before/after repair result is supplied for V3. "
                    "A forced singleton transition would be unsupported."
                ),
                direct_result=direct_result,
                distractor_result=distractor_result,
            )
        )

    label_counts = Counter(row["target_text"] for row in rows)
    semantic_counts = Counter(row["semantic_target_value"] for row in rows)
    summary = {
        "stage": 11160,
        "stage_name": "explicit_verifier_transition_competition_materialization",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "metrics": {
            "candidate_pairs": len(PAIR_CANDIDATES),
            "valid_pairs": len(valid_pairs),
            "materialized_rows": len(rows),
            "unique_roots": len({row["source_root_id"] for row in rows}),
            "blocked_pairs": len(blockers),
            "target_label_counts": dict(sorted(label_counts.items())),
            "semantic_target_counts": dict(sorted(semantic_counts.items())),
            "pytest_commands_run": len(pytest_cache),
        },
        "blockers": blockers,
        "decision": "review_queue_only_not_train_package",
        "claim_scope": (
            "Explicit local verifier-transition competition rows with PASS_TO_PASS, NOT_EXERCISED, "
            "FAIL_TO_PASS as a hard negative, and INSUFFICIENT_EVIDENCE options. These are review/support "
            "candidates, not strict heldout rows and not a model result."
        ),
        "next_best_step": (
            "Run an admission audit. Only rows with non-overlap, visible verifier evidence, deterministic "
            "option shuffle, and complete transition semantics should be merged into a diagnostic support package."
        ),
        "outputs": {
            "rows_jsonl": str((OUT_DIR / "explicit_verifier_transition_review_rows.jsonl").relative_to(ROOT)),
            "summary_json": str((OUT_DIR / "explicit_verifier_transition_competition_materialization.json").relative_to(ROOT)),
        },
    }
    write_jsonl(OUT_DIR / "explicit_verifier_transition_review_rows.jsonl", rows)
    (OUT_DIR / "explicit_verifier_transition_competition_materialization.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
