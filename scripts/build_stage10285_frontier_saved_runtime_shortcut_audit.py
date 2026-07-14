#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10285
NAME = "stage10285_frontier_saved_runtime_shortcut_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "frontier_saved_runtime_shortcut_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
PAYLOAD = ROOT / "runs/local/artifacts/stage10280_frontier_saved_runtime_harness_payload/frontier_saved_runtime_harness_payload.json"
RUNTIME = ROOT / "runs/local/artifacts/stage10283_frontier_saved_runtime_harness_local_runtime/canonical_harness_local_runtime_summary.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def normalize_text(text: str) -> str:
    return " ".join(str(text).lower().split())


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_./-]+", normalize_text(text))


def lexical_overlap_score(prompt: str, value: str) -> float:
    p = set(tokenize(prompt))
    v = set(tokenize(value))
    if not p or not v:
        return 0.0
    return len(p & v) / len(v)


def row_contains_value(prompt: str, value: str) -> bool:
    return normalize_text(value) in normalize_text(prompt)


def evidence_only_prompt(prompt: str) -> str:
    text = str(prompt)
    marker = "\nOptions:\n"
    if marker in text:
        return text.split(marker, 1)[0]
    return text


def build_audit() -> dict[str, Any]:
    payload = load_json(PAYLOAD)
    runtime = load_json(RUNTIME)
    row_map: dict[str, dict[str, Any]] = {}
    for run in payload.get("runs") or []:
        if not isinstance(run, dict):
            continue
        task_pack = run.get("task_pack") if isinstance(run.get("task_pack"), dict) else {}
        language = str(task_pack.get("language_family") or "")
        for row in task_pack.get("rows") or []:
            if not isinstance(row, dict):
                continue
            enriched = dict(row)
            enriched["language_family"] = language
            row_map[str(row.get("row_id") or "")] = enriched

    joined_rows: list[dict[str, Any]] = []
    weak_100m: list[dict[str, Any]] = []
    weak_gemma: list[dict[str, Any]] = []
    baseline_correct = Counter()
    baseline_totals = Counter()
    perspective_contains_gold = Counter()
    perspective_rows = Counter()
    perspective_unique_prompt_match = Counter()
    semantic_confusions_100m: dict[str, Counter[str]] = defaultdict(Counter)
    semantic_confusions_gemma: dict[str, Counter[str]] = defaultdict(Counter)

    for result in runtime.get("results") or []:
        if not isinstance(result, dict):
            continue
        hundred_rows = {str(row.get("row_id") or ""): row for row in load_jsonl(ROOT / str((result.get("hundred_m_runtime") or {}).get("predictions_path") or ""))}
        gemma_rows = {str(row.get("row_id") or ""): row for row in load_jsonl(ROOT / str((result.get("gemma12b_runtime") or {}).get("rows_path") or ""))}
        runtime_dir = ROOT / str(result.get("runtime_dir") or "")
        payload_path = runtime_dir / "runtime_payload.json"
        live_payload = load_json(payload_path)
        task_pack = live_payload.get("task_pack") if isinstance(live_payload.get("task_pack"), dict) else {}
        for row in task_pack.get("rows") or []:
            if not isinstance(row, dict):
                continue
            row_id = str(row.get("row_id") or "")
            prompt = str(row.get("prompt") or row.get("prompt_text") or row.get("input_text") or "")
            evidence_prompt = evidence_only_prompt(prompt)
            expected = str(row.get("expected_label") or row.get("target_text") or "")
            perspective = str(row.get("perspective") or row.get("task_type") or "")
            options = [opt for opt in row.get("opaque_options") or [] if isinstance(opt, dict)]
            label_to_value = {str(opt.get("label") or ""): str(opt.get("value") or "") for opt in options}
            expected_value = label_to_value.get(expected, "")
            perspective_rows[perspective] += 1
            if expected_value and row_contains_value(evidence_prompt, expected_value):
                perspective_contains_gold[perspective] += 1
            containing = [str(opt.get("label") or "") for opt in options if row_contains_value(evidence_prompt, str(opt.get("value") or ""))]
            if len(containing) == 1 and containing[0] == expected:
                perspective_unique_prompt_match[perspective] += 1

            first_option = str(options[0].get("label") or "") if options else ""
            abstain_option = next((str(opt.get("label") or "") for opt in options if str(opt.get("value") or "") == "ABSTAIN_INSUFFICIENT_EVIDENCE"), "")
            lexical_choice = ""
            best_score = -1.0
            for opt in options:
                label = str(opt.get("label") or "")
                score = lexical_overlap_score(evidence_prompt, str(opt.get("value") or ""))
                if score > best_score:
                    best_score = score
                    lexical_choice = label
            unique_prompt_choice = containing[0] if len(containing) == 1 else ""
            heuristics = {
                "first_option": first_option,
                "abstain_if_present": abstain_option,
                "lexical_overlap": lexical_choice,
                "unique_prompt_match": unique_prompt_choice,
            }
            for name, pred in heuristics.items():
                if pred:
                    baseline_totals[name] += 1
                    if pred == expected:
                        baseline_correct[name] += 1

            hundred = hundred_rows.get(row_id, {})
            gemma = gemma_rows.get(row_id, {})
            hundred_pred = str(hundred.get("predicted") or hundred.get("predicted_label") or "")
            gemma_pred = str(gemma.get("predicted_label") or "")
            hundred_correct = bool(hundred.get("correct")) if hundred.get("correct") is not None else None
            gemma_correct = bool(gemma.get("correct")) if gemma.get("correct") is not None else None
            if hundred_correct is False:
                weak_100m.append({
                    "row_id": row_id,
                    "language_family": row.get("language_family"),
                    "perspective": perspective,
                    "expected_label": expected,
                    "expected_value": expected_value,
                    "predicted_label": hundred_pred,
                    "predicted_value": label_to_value.get(hundred_pred, ""),
                    "lexical_overlap_choice": lexical_choice,
                    "unique_prompt_match": unique_prompt_choice,
                })
                if expected_value and label_to_value.get(hundred_pred):
                    semantic_confusions_100m[perspective][f"{expected_value} -> {label_to_value.get(hundred_pred)}"] += 1
            if gemma_correct is False:
                weak_gemma.append({
                    "row_id": row_id,
                    "language_family": row.get("language_family"),
                    "perspective": perspective,
                    "expected_label": expected,
                    "expected_value": expected_value,
                    "predicted_label": gemma_pred,
                    "predicted_value": label_to_value.get(gemma_pred, ""),
                    "lexical_overlap_choice": lexical_choice,
                    "unique_prompt_match": unique_prompt_choice,
                })
                if expected_value and label_to_value.get(gemma_pred):
                    semantic_confusions_gemma[perspective][f"{expected_value} -> {label_to_value.get(gemma_pred)}"] += 1

            joined_rows.append({
                "row_id": row_id,
                "language_family": row.get("language_family"),
                "perspective": perspective,
                "expected_label": expected,
                "expected_value": expected_value,
                "hundred_m_predicted": hundred_pred,
                "hundred_m_correct": hundred_correct,
                "gemma_predicted": gemma_pred,
                "gemma_correct": gemma_correct,
                "heuristics": heuristics,
                "gold_value_in_prompt": expected_value and row_contains_value(evidence_prompt, expected_value),
                "option_values_mentioned": containing,
            })

    baseline_metrics = {
        name: {
            "correct": int(baseline_correct[name]),
            "rows_scored": int(baseline_totals[name]),
            "accuracy": (baseline_correct[name] / baseline_totals[name]) if baseline_totals[name] else None,
        }
        for name in sorted(baseline_totals)
    }
    direct_prompt_match = {
        perspective: {
            "rows": int(perspective_rows[perspective]),
            "gold_value_mentioned": int(perspective_contains_gold[perspective]),
            "gold_value_mentioned_rate": (perspective_contains_gold[perspective] / perspective_rows[perspective]) if perspective_rows[perspective] else None,
            "unique_gold_prompt_match": int(perspective_unique_prompt_match[perspective]),
            "unique_gold_prompt_match_rate": (perspective_unique_prompt_match[perspective] / perspective_rows[perspective]) if perspective_rows[perspective] else None,
        }
        for perspective in sorted(perspective_rows)
    }

    findings = []
    if baseline_metrics.get("unique_prompt_match", {}).get("accuracy", 0) and baseline_metrics["unique_prompt_match"]["accuracy"] > 0.5:
        findings.append("A simple unique prompt-match heuristic solves a substantial share of the packet, so direct visible-option mention remains a real shortcut risk.")
    if baseline_metrics.get("lexical_overlap", {}).get("accuracy", 0) and baseline_metrics["lexical_overlap"]["accuracy"] > 0.5:
        findings.append("A simple lexical-overlap heuristic reaches high accuracy, indicating the packet is still heavily driven by shallow prompt-option overlap.")
    if direct_prompt_match.get("symptom_localization", {}).get("unique_gold_prompt_match_rate", 0) and direct_prompt_match["symptom_localization"]["unique_gold_prompt_match_rate"] > 0.5:
        findings.append("Symptom localization rows frequently mention exactly one candidate value verbatim in the prompt, which is too close to extraction rather than maintainer reasoning.")
    if semantic_confusions_100m.get("evidence_citation"):
        findings.append("100M still confuses evidence families on some evidence_citation rows even on the winning frontier, so its remaining errors are not random.")
    if semantic_confusions_gemma.get("patch_impact"):
        findings.append("Gemma still defaults to visible candidate surfaces on some patch_impact rows, which suggests the packet rewards shallow visible-surface priors more than realistic repair reasoning.")

    return {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(joined_rows),
        "source_payload": display(PAYLOAD),
        "source_runtime_summary": display(RUNTIME),
        "metrics": {
            "rows": len(joined_rows),
            "weak_rows_100m": len(weak_100m),
            "weak_rows_gemma": len(weak_gemma),
            "baseline_metrics": baseline_metrics,
            "direct_prompt_match_by_perspective": direct_prompt_match,
        },
        "semantic_confusions_100m": {k: dict(v.most_common()) for k, v in sorted(semantic_confusions_100m.items())},
        "semantic_confusions_gemma": {k: dict(v.most_common()) for k, v in sorted(semantic_confusions_gemma.items())},
        "weak_rows_100m": weak_100m,
        "weak_rows_gemma": weak_gemma,
        "findings": findings,
        "recommended_next_steps": [
            "Lower the share of rows where one candidate value is mentioned verbatim in the prompt, especially for symptom_localization and minimal_fix_selection.",
            "Add rows where candidate_change_surface and verifier/test evidence compete without exact candidate value copy signals.",
            "Keep compact bounded wins labeled as diagnostic unless the same improvements survive more realistic maintainer-grade packets with concrete code and trace evidence.",
        ],
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    audit = build_audit()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(
        json.dumps({"stage": STAGE, "passed": audit["passed"], "artifact": display(AUDIT), "metrics": audit["metrics"]}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "artifact": display(AUDIT), "metrics": audit["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
