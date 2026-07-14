#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10429
NAME = "stage10429_reviewed_v27_eval_hacking_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "reviewed_v27_eval_hacking_audit.json"
ROW_AUDIT_JSONL = OUT_DIR / "reviewed_v27_eval_hacking_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

PACKAGE_JSON = ROOT / "runs/local/artifacts/stage10420_reviewed_multilingual_v27_manifest_package/reviewed_multilingual_v27_manifest_package.json"
ROWS_JSONL = ROOT / "runs/local/artifacts/stage10420_reviewed_multilingual_v27_manifest_package/reviewed_multilingual_v27_bounded_rows.jsonl"
STRICT_ROWS_JSONL = ROOT / "runs/local/artifacts/stage10420_reviewed_multilingual_v27_manifest_package/agentkernel_lite_encdec_strict_eval.jsonl"
EXECUTION_RESULT_JSON = ROOT / "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/bounded_decoder_probe/execution_result.json"
GEMMA_JSON = ROOT / "runs/local/artifacts/stage10423_reviewed_multilingual_v27_same_manifest_gemma_comparison/reviewed_multilingual_v27_same_manifest_gemma_comparison.json"

EVIDENCE_LINE_RE = re.compile(r"^([A-Za-z0-9_]+)\s*(?:\[[^\]]+\])?:\s", re.MULTILINE)


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


def prompt_before_options(prompt: str) -> str:
    marker = "\nOptions:\n"
    idx = prompt.find(marker)
    return prompt if idx < 0 else prompt[:idx]


def basename(path: str) -> str:
    return path.rsplit("/", 1)[-1]


def evidence_keys(prompt: str) -> list[str]:
    return EVIDENCE_LINE_RE.findall(prompt_before_options(prompt))


def semantic_target(row: dict[str, Any]) -> str:
    projection = row.get("standalone_projection_source") or {}
    return str(projection.get("gold_value") or "")


def split_accuracy(rows: list[dict[str, Any]], key_fn) -> dict[str, Any]:
    grouped: dict[tuple[Any, ...], Counter[str]] = defaultdict(Counter)
    total = 0
    correct = 0
    for row in rows:
        target = semantic_target(row)
        if not target:
            continue
        grouped[key_fn(row)][target] += 1
    winners = {key: counter.most_common(1)[0][0] for key, counter in grouped.items() if counter}
    for row in rows:
        target = semantic_target(row)
        if not target:
            continue
        total += 1
        if winners.get(key_fn(row)) == target:
            correct += 1
    return {
        "rows": total,
        "correct": correct,
        "accuracy": (correct / total) if total else None,
        "signature_count": len(grouped),
    }


def leave_one_out_accuracy(rows: list[dict[str, Any]], key_fn) -> dict[str, Any]:
    grouped: dict[tuple[Any, ...], Counter[str]] = defaultdict(Counter)
    for row in rows:
        target = semantic_target(row)
        if target:
            grouped[key_fn(row)][target] += 1
    total = 0
    correct = 0
    abstained = 0
    for row in rows:
        target = semantic_target(row)
        if not target:
            continue
        total += 1
        signature = key_fn(row)
        counter = grouped[signature].copy()
        counter[target] -= 1
        if counter[target] <= 0:
            del counter[target]
        if not counter:
            abstained += 1
            continue
        predicted = counter.most_common(1)[0][0]
        if predicted == target:
            correct += 1
    scored = total - abstained
    return {
        "rows": total,
        "scored_rows": scored,
        "abstained_rows": abstained,
        "accuracy_on_scored_rows": (correct / scored) if scored else None,
        "coverage": (scored / total) if total else None,
        "effective_accuracy": (correct / total) if total else None,
    }


def overlap(a: set[str], b: set[str]) -> list[str]:
    return sorted(a & b)


def main() -> None:
    package = load_json(PACKAGE_JSON)
    rows = load_jsonl(ROWS_JSONL)
    strict_rows = load_jsonl(STRICT_ROWS_JSONL)
    execution = load_json(EXECUTION_RESULT_JSON)
    gemma = load_json(GEMMA_JSON)

    root_ids_by_split: dict[str, set[str]] = defaultdict(set)
    row_audits: list[dict[str, Any]] = []
    evidence_signature_counter: Counter[tuple[str, ...]] = Counter()
    target_label_counter: Counter[str] = Counter()

    prompt_verbatim_gold_hits = 0
    prompt_basename_gold_hits = 0
    evidence_signature_to_target: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)

    for row in rows:
        split = str(row.get("split") or "unknown")
        root_id = str(row.get("source_root_id") or "")
        if root_id:
            root_ids_by_split[split].add(root_id)

        prompt = str(row.get("prompt_text") or row.get("input_text") or "")
        prompt_body = prompt_before_options(prompt)
        gold_value = semantic_target(row)
        gold_basename = basename(gold_value)
        target_label = str(row.get("target_text") or "")
        target_label_counter[target_label] += 1

        keys = tuple(evidence_keys(prompt))
        evidence_signature_counter[keys] += 1
        evidence_signature_to_target[keys][gold_value] += 1

        verbatim_hit = bool(gold_value and gold_value in prompt_body)
        basename_hit = bool(gold_basename and gold_basename in prompt_body)
        prompt_verbatim_gold_hits += int(verbatim_hit)
        prompt_basename_gold_hits += int(basename_hit)

        row_audits.append(
            {
                "row_id": row.get("row_id"),
                "split": split,
                "language_family": row.get("language_family"),
                "task_type": row.get("task_type"),
                "repo_family": row.get("repo_family"),
                "source_bundle_id": row.get("source_bundle_id"),
                "selected_test_anchor": bool(row.get("selected_test_anchor")),
                "verifier_anchor": bool(row.get("verifier_anchor")),
                "abstention_heavy": bool(row.get("abstention_heavy")),
                "source_heldout_admissible": bool(row.get("source_heldout_admissible")),
                "target_label": target_label,
                "target_value": gold_value,
                "evidence_keys": list(keys),
                "evidence_key_signature": "|".join(keys),
                "prompt_contains_target_value_before_options": verbatim_hit,
                "prompt_contains_target_basename_before_options": basename_hit,
                "option_count": len(row.get("opaque_options") or []),
            }
        )

    metadata_baselines = {
        "task_type": split_accuracy(rows, lambda r: (r.get("task_type"),)),
        "language_and_task": split_accuracy(rows, lambda r: (r.get("language_family"), r.get("task_type"))),
        "repo_and_task": split_accuracy(rows, lambda r: (r.get("repo_family"), r.get("task_type"))),
        "anchor_profile_and_task": split_accuracy(
            rows,
            lambda r: (
                bool(r.get("selected_test_anchor")),
                bool(r.get("verifier_anchor")),
                bool(r.get("abstention_heavy")),
                r.get("task_type"),
            ),
        ),
        "evidence_key_signature": split_accuracy(rows, lambda r: tuple(evidence_keys(str(r.get("prompt_text") or r.get("input_text") or "")))),
    }

    strict_metadata_baselines = {
        "task_type": split_accuracy(strict_rows, lambda r: (r.get("task_type"),)),
        "language_and_task": split_accuracy(strict_rows, lambda r: (r.get("language_family"), r.get("task_type"))),
        "repo_and_task": split_accuracy(strict_rows, lambda r: (r.get("repo_family"), r.get("task_type"))),
        "anchor_profile_and_task": split_accuracy(
            strict_rows,
            lambda r: (
                bool(r.get("selected_test_anchor")),
                bool(r.get("verifier_anchor")),
                bool(r.get("abstention_heavy")),
                r.get("task_type"),
            ),
        ),
        "evidence_key_signature": split_accuracy(strict_rows, lambda r: tuple(evidence_keys(str(r.get("prompt_text") or r.get("input_text") or "")))),
    }

    leave_one_out = {
        "all_rows": {
            "task_type": leave_one_out_accuracy(rows, lambda r: (r.get("task_type"),)),
            "language_and_task": leave_one_out_accuracy(rows, lambda r: (r.get("language_family"), r.get("task_type"))),
            "repo_and_task": leave_one_out_accuracy(rows, lambda r: (r.get("repo_family"), r.get("task_type"))),
            "evidence_key_signature": leave_one_out_accuracy(rows, lambda r: tuple(evidence_keys(str(r.get("prompt_text") or r.get("input_text") or "")))),
        },
        "strict_rows": {
            "task_type": leave_one_out_accuracy(strict_rows, lambda r: (r.get("task_type"),)),
            "language_and_task": leave_one_out_accuracy(strict_rows, lambda r: (r.get("language_family"), r.get("task_type"))),
            "repo_and_task": leave_one_out_accuracy(strict_rows, lambda r: (r.get("repo_family"), r.get("task_type"))),
            "evidence_key_signature": leave_one_out_accuracy(strict_rows, lambda r: tuple(evidence_keys(str(r.get("prompt_text") or r.get("input_text") or "")))),
        },
    }

    root_overlap = {
        "train_vs_validation": overlap(root_ids_by_split["train"], root_ids_by_split["validation"]),
        "train_vs_strict_eval": overlap(root_ids_by_split["train"], root_ids_by_split["strict_eval"]),
        "validation_vs_strict_eval": overlap(root_ids_by_split["validation"], root_ids_by_split["strict_eval"]),
        "stress_vs_train": overlap(root_ids_by_split["stress_eval"], root_ids_by_split["train"]),
        "stress_vs_strict_eval": overlap(root_ids_by_split["stress_eval"], root_ids_by_split["strict_eval"]),
    }

    evidence_signature_rows = []
    for keys, counter in evidence_signature_to_target.items():
        total = sum(counter.values())
        most_common = counter.most_common(1)[0]
        evidence_signature_rows.append(
            {
                "evidence_keys": list(keys),
                "rows": total,
                "majority_target_value": most_common[0],
                "majority_count": most_common[1],
                "majority_accuracy": most_common[1] / total,
                "distinct_target_values": len(counter),
            }
        )
    evidence_signature_rows.sort(key=lambda item: (-item["majority_accuracy"], -item["rows"], item["evidence_keys"]))

    bounded_choice_eval = execution["bounded_choice_eval"]
    gemma_strict_accuracy = float(gemma["gemma12b"]["exact_accuracy"])
    frontier_result = {
        "target100m_eval_accuracy": bounded_choice_eval["eval"]["constrained_choice_top1_accuracy"],
        "target100m_strict_accuracy": bounded_choice_eval["strict_eval"]["constrained_choice_top1_accuracy"],
        "gemma_strict_accuracy": gemma_strict_accuracy,
        "strict_delta_vs_gemma": bounded_choice_eval["strict_eval"]["constrained_choice_top1_accuracy"] - gemma_strict_accuracy,
    }

    package_metrics = package.get("metrics") or {}
    prompt_value_leak_rate = prompt_verbatim_gold_hits / len(rows) if rows else None
    prompt_basename_leak_rate = prompt_basename_gold_hits / len(rows) if rows else None
    evidence_signature_baseline = metadata_baselines["evidence_key_signature"]["accuracy"]

    highest_risk_findings = []
    if evidence_signature_baseline is not None and evidence_signature_baseline >= 0.9:
        highest_risk_findings.append("Evidence-key signature alone predicts the semantic target with very high accuracy across the reviewed v2.7 rows.")
    if prompt_value_leak_rate is not None and prompt_value_leak_rate > 0:
        highest_risk_findings.append("Some rows expose the exact target path before the options block; these rows require manual review.")
    if any(root_overlap.values()):
        highest_risk_findings.append("Root overlap exists across train/eval splits, which would invalidate heldout claims.")
    if package_metrics.get("selected_test_anchor_counts", {}).get("present", 0) == 0:
        highest_risk_findings.append("No selected-test anchors are present, which would weaken verifier realism.")

    claim_boundary = [
        "The reviewed v2.7 package is materially stronger than the frozen 47-row v2.6 frontier because it is root-split and review-backed.",
        "It is still not source-heldout promotable; every row remains marked source_heldout_admissible=false.",
        "Any claim about beating Gemma on the reviewed v2.7 standalone surface should remain same-manifest and standalone-only until fresh heldout roots are added.",
        "Stress overlap rows must remain excluded from the promotable path and reported separately.",
    ]

    next_best_steps = [
        "Build fresh source-heldout reviewed roots, especially Python and Rust, rather than replaying the current reviewed-v2.7 misses.",
        "Prioritize pure-web verifier-anchored roots and non-abstention-heavy Rust roots to strengthen language-specific claims.",
        "Run future promotion probes against this root-split package while tracking verifier-anchor slices, abstention calibration, and metadata-baseline gaps.",
    ]

    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_boundary": claim_boundary,
        "source_artifacts": {
            "package": display(PACKAGE_JSON),
            "bounded_rows": display(ROWS_JSONL),
            "strict_rows": display(STRICT_ROWS_JSONL),
            "target100m_probe": display(EXECUTION_RESULT_JSON),
            "gemma_comparison": display(GEMMA_JSON),
        },
        "frontier_result": frontier_result,
        "package_metrics": package_metrics,
        "root_overlap": root_overlap,
        "label_distribution": {
            "target_label_counts": dict(sorted(target_label_counter.items())),
            "distinct_target_values": len({semantic_target(row) for row in rows if semantic_target(row)}),
        },
        "prompt_leakage": {
            "rows": len(rows),
            "prompt_contains_target_value_before_options": prompt_verbatim_gold_hits,
            "prompt_contains_target_value_before_options_rate": prompt_value_leak_rate,
            "prompt_contains_target_basename_before_options": prompt_basename_gold_hits,
            "prompt_contains_target_basename_before_options_rate": prompt_basename_leak_rate,
        },
        "metadata_majority_baselines": {
            "all_rows": metadata_baselines,
            "strict_rows": strict_metadata_baselines,
            "leave_one_out": leave_one_out,
        },
        "evidence_signature_summary": {
            "distinct_signatures": len(evidence_signature_counter),
            "top_signatures": evidence_signature_rows[:12],
        },
        "highest_risk_findings": highest_risk_findings,
        "next_best_steps": next_best_steps,
        "outputs": {
            "row_audit": display(ROW_AUDIT_JSONL),
            "audit_json": display(AUDIT_JSON),
        },
    }

    write_json(AUDIT_JSON, audit)
    write_jsonl(ROW_AUDIT_JSONL, row_audits)
    write_json(SUMMARY, audit)

    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
