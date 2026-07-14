#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10875
NAME = "stage10875_hybrid_evidence_fallback_audit"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "hybrid_evidence_fallback_audit.json"

AUDITS = {
    "stage10870": {
        "strict_eval": ARTIFACTS / "stage10870_residual_family_probe_plus_second_python_materialized/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json",
        "eval": ARTIFACTS / "stage10870_residual_family_probe_plus_second_python_materialized/bounded_decoder_probe/bounded_choice_eval_audit_eval.json",
    },
    "stage10873": {
        "strict_eval": ARTIFACTS / "stage10873_verifier_candidate_semantic_probe/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json",
        "eval": ARTIFACTS / "stage10873_verifier_candidate_semantic_probe/bounded_decoder_probe/bounded_choice_eval_audit_eval.json",
    },
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def task_type_from_row_id(row_id: str) -> str:
    for task in [
        "symptom_localization",
        "evidence_citation",
        "patch_impact",
        "verifier_outcome",
        "minimal_fix_selection",
        "abstention_insufficient_evidence",
    ]:
        if f"::{task}::" in row_id:
            return task
    return "unknown"


def language_from_row_id(row_id: str) -> str:
    for language in ["python", "rust", "c_cpp", "web_js_ts_html"]:
        if f"::{language}::" in row_id:
            return language
    return "unknown"


def hybrid_pred(row_card: dict[str, Any]) -> str:
    task_type = task_type_from_row_id(str(row_card["row_id"]))
    option_labels = {str(label) for label in row_card.get("option_labels") or []}
    decoder_text = str(row_card.get("full_vocab_top1_text") or "").strip()
    if task_type == "evidence_citation" and decoder_text in option_labels:
        return decoder_text
    return str(row_card["constrained_choice_top1_label"])


def summarize_row_cards(row_cards: list[dict[str, Any]]) -> dict[str, Any]:
    base_correct = 0
    hybrid_correct = 0
    changed_rows = []
    for row in row_cards:
        target = str(row["bounded_choice_target_label"])
        base_pred = str(row["constrained_choice_top1_label"])
        new_pred = hybrid_pred(row)
        base_ok = base_pred == target
        new_ok = new_pred == target
        if base_ok:
            base_correct += 1
        if new_ok:
            hybrid_correct += 1
        if new_pred != base_pred:
            changed_rows.append(
                {
                    "row_id": str(row["row_id"]),
                    "language_family": language_from_row_id(str(row["row_id"])),
                    "task_type": task_type_from_row_id(str(row["row_id"])),
                    "target": target,
                    "base_pred": base_pred,
                    "decoder_top_text": str(row.get("full_vocab_top1_text") or ""),
                    "hybrid_pred": new_pred,
                    "base_correct": base_ok,
                    "hybrid_correct": new_ok,
                }
            )
    return {
        "rows": len(row_cards),
        "base_correct": base_correct,
        "base_accuracy": (base_correct / len(row_cards)) if row_cards else None,
        "hybrid_correct": hybrid_correct,
        "hybrid_accuracy": (hybrid_correct / len(row_cards)) if row_cards else None,
        "delta": ((hybrid_correct - base_correct) / len(row_cards)) if row_cards else None,
        "changed_rows": changed_rows,
    }


def main() -> None:
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "claim_scope": [
            "Audit a lightweight evidence-only fallback policy using existing bounded-choice eval artifacts.",
            "If the decoder top token cleanly names a valid option label on evidence_citation rows, use it instead of the constrained encoder scorer; otherwise keep the constrained scorer.",
        ],
        "runtimes": {},
    }

    for runtime, split_map in AUDITS.items():
        runtime_payload = {}
        for split, path in split_map.items():
            audit = load_json(path)
            runtime_payload[split] = summarize_row_cards(list(audit["row_cards"]))
        payload["runtimes"][runtime] = runtime_payload

    findings = []
    for runtime, runtime_payload in payload["runtimes"].items():
        strict = runtime_payload["strict_eval"]
        findings.append(
            {
                "runtime": runtime,
                "strict_base_accuracy": strict["base_accuracy"],
                "strict_hybrid_accuracy": strict["hybrid_accuracy"],
                "strict_delta": strict["delta"],
                "strict_changed_rows": strict["changed_rows"],
            }
        )
    payload["findings"] = findings
    payload["next_best_step"] = (
        "If this hybrid fallback improves strict accuracy without introducing regressions, promote it into a standalone scored-interface audit and compare against Gemma under the same reported policy."
    )
    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
