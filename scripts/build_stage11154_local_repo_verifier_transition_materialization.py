#!/usr/bin/env python3
"""Materialize local source-backed verifier-transition review candidates.

This creates review-only support candidates from real repository test/source
pairs.  The rows are not merged into train; they provide concrete local roots
that can be reviewed and later admitted if they pass anti-cheat and quality
checks.
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
OUT_DIR = ROOT / "runs/local/artifacts/stage11154_local_repo_verifier_transition_materialization"
CURRENT_STRICT = (
    ROOT
    / "runs/local/artifacts/stage11146_singleton_strict_quarantine_successor/agentkernel_lite_encdec_strict_eval.jsonl"
)

PAIR_CANDIDATES = [
    {
        "source": "scripts/prepare_strict_long_context_training_dataset.py",
        "test": "tests/test_prepare_strict_long_context_training_dataset.py",
        "symbol_hint": "prepare_strict_long_context_training_dataset",
    },
    {
        "source": "scripts/bounded_decoder_ce_package_gate_builder.py",
        "test": "tests/test_bounded_decoder_ce_package_gate_builder.py",
        "symbol_hint": "build_row",
    },
    {
        "source": "scripts/runtime_verifier_loop_contract.py",
        "test": "tests/test_runtime_verifier_loop_contract.py",
        "symbol_hint": "audit_runtime_verifier_loop_contract",
    },
    {
        "source": "scripts/parse_bounded_session_jsonl_metadata.py",
        "test": "tests/test_parse_bounded_session_jsonl_metadata.py",
        "symbol_hint": "parse",
    },
    {
        "source": "scripts/assign_strict_long_context_pack_splits.py",
        "test": "tests/test_assign_strict_long_context_pack_splits.py",
        "symbol_hint": "assign",
    },
    {
        "source": "scripts/materialize_strict_long_context_mixture_rows.py",
        "test": "tests/test_materialize_strict_long_context_mixture_rows.py",
        "symbol_hint": "materialize",
    },
]

LABELS = list("ABCDEFGH")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def protected_roots() -> set[str]:
    roots = set()
    for row in read_jsonl(CURRENT_STRICT):
        value = row.get("source_root_id")
        if value:
            roots.add(str(value))
    return roots


def snippet(path: Path, needle: str | None = None, max_chars: int = 850) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    if needle and needle in text:
        idx = max(0, text.index(needle) - 250)
        return text[idx : idx + max_chars].strip()
    return text[:max_chars].strip()


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


def shuffled_options(row_id: str, option_values: list[str]) -> list[dict[str, str]]:
    keyed = []
    for i, value in enumerate(option_values):
        digest = hashlib.sha256(f"{row_id}::{i}::{value}".encode()).hexdigest()
        keyed.append((digest, value))
    return [
        {"label": label, "value": value}
        for label, (_, value) in zip(LABELS, sorted(keyed))
    ]


def make_row(pair: dict[str, str], all_tests: list[str], pytest_result: dict[str, Any]) -> dict[str, Any]:
    source = pair["source"]
    test = pair["test"]
    root_id = f"stage11154::local_repo::{source}::{test}"
    row_id = f"{root_id}::verifier_outcome_semantic_transition::review_candidate"
    source_path = ROOT / source
    test_path = ROOT / test
    distractors = [t for t in all_tests if t != test][:3]
    option_values = [
        f"T1 | PASS_TO_PASS | direct verifier for {Path(test).name}",
        f"T2 | NOT_EXERCISED | neighboring verifier {Path(distractors[0]).name if distractors else 'none'}",
        f"T3 | NOT_EXERCISED | neighboring verifier {Path(distractors[1]).name if len(distractors) > 1 else 'none'}",
        "T4 | ABSTAIN_INSUFFICIENT_EVIDENCE | no direct verifier is identifiable",
    ]
    options = shuffled_options(row_id, option_values)
    target_value = option_values[0]
    target_label = next(opt["label"] for opt in options if opt["value"] == target_value)
    prompt = (
        "Language: python\n"
        "Perspective: verifier_outcome_semantic_transition\n"
        "Task: Choose which opaque verifier target is the direct PASS_TO_PASS guardrail for the visible source surface. "
        "Use the source snippet, test snippet, and pytest result; do not choose neighboring tests unless they exercise the shown source.\n"
        f"Repository: agentkernel-seq2seq-text-lab\n"
        f"Visible source candidate P1: {source}\n"
        f"Evidence:\n"
        f"E1 source snippet [{source}]: {snippet(source_path, pair.get('symbol_hint'))}\n"
        f"E2 direct test snippet [{test}]: {snippet(test_path, pair.get('symbol_hint'))}\n"
        f"E3 pytest verifier result: {pytest_result['command']} -> returncode={pytest_result['returncode']} passed={pytest_result['passed']}\n"
        "Verifier target ledger:\n"
        + "\n".join(opt["value"] for opt in options)
        + "\nOptions:\n"
        + "\n".join(f"{opt['label']}. {opt['value']}" for opt in options)
        + "\nAnswer:\n"
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
        "target_text": target_label,
        "decoder_text": target_label,
        "target_token_len": 1,
        "opaque_options": options,
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "explicit_verifier_target_ledger": True,
            "source_snippet_visible": True,
            "test_snippet_visible": True,
            "pytest_result_visible": True,
            "review_queue_only": True,
            "not_merged_into_train": True,
        },
        "standalone_projection_source": {
            "projection_mode": "stage11154_local_repo_verifier_transition_materialization",
            "source_path": source,
            "test_path": test,
            "target_value": target_value,
            "pytest_result": pytest_result,
        },
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    protected = protected_roots()
    all_tests = [pair["test"] for pair in PAIR_CANDIDATES]
    rows: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    pytest_results: dict[str, dict[str, Any]] = {}
    for pair in PAIR_CANDIDATES:
        source_path = ROOT / pair["source"]
        test_path = ROOT / pair["test"]
        root_id = f"stage11154::local_repo::{pair['source']}::{pair['test']}"
        reasons = []
        if root_id in protected:
            reasons.append("root_overlaps_clean_strict")
        if not source_path.exists():
            reasons.append("missing_source")
        if not test_path.exists():
            reasons.append("missing_test")
        if reasons:
            blockers.append({"pair": pair, "blockers": reasons})
            continue
        result = run_pytest(pair["test"])
        pytest_results[pair["test"]] = result
        if not result["passed"]:
            blockers.append({"pair": pair, "blockers": ["pytest_not_passing"], "pytest_result": result})
            continue
        rows.append(make_row(pair, all_tests, result))

    label_counts = Counter(row["target_text"] for row in rows)
    summary = {
        "stage": 11154,
        "stage_name": "local_repo_verifier_transition_materialization",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "metrics": {
            "candidate_pairs": len(PAIR_CANDIDATES),
            "materialized_rows": len(rows),
            "blocked_pairs": len(blockers),
            "unique_roots": len({row["source_root_id"] for row in rows}),
            "target_label_counts": dict(sorted(label_counts.items())),
            "pytest_passed": sum(1 for result in pytest_results.values() if result["passed"]),
        },
        "decision": "review_queue_only_not_train_package",
        "claim_scope": (
            "Local source-backed verifier-transition candidates with PASS_TO_PASS "
            "guardrail semantics. These are review/support candidates, not strict "
            "heldout rows and not a model result."
        ),
        "next_best_step": (
            "Audit these rows for whether PASS_TO_PASS guardrail supervision is "
            "acceptable support for the Python verifier-transition miss; only then "
            "merge admitted rows into a support package."
        ),
        "blockers": blockers,
        "outputs": {
            "rows_jsonl": str((OUT_DIR / "local_repo_verifier_transition_review_rows.jsonl").relative_to(ROOT)),
            "summary_json": str((OUT_DIR / "local_repo_verifier_transition_materialization.json").relative_to(ROOT)),
        },
    }
    with (OUT_DIR / "local_repo_verifier_transition_review_rows.jsonl").open("w") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    (OUT_DIR / "local_repo_verifier_transition_materialization.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
