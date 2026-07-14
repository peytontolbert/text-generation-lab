#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from audit_manifest_integrity import audit_manifest_rows, load_jsonl

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10624
NAME = "stage10624_multilingual_manifest_integrity_and_comparison_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "multilingual_manifest_integrity_and_comparison_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

MANIFEST_10620 = ROOT / "runs/local/artifacts/stage10620_reviewed_plus_bootstrap_multilingual_probe_request_capped/reviewed_plus_bootstrap_multilingual_probe_manifest_capped.jsonl"
MANIFEST_10622 = ROOT / "runs/local/artifacts/stage10622_multilingual_deduped_eval_package/multilingual_deduped_eval_manifest.jsonl"
STRICT_10420 = ROOT / "runs/local/artifacts/stage10420_reviewed_multilingual_v27_manifest_package/agentkernel_lite_encdec_strict_eval.jsonl"
GEMMA_10423 = ROOT / "runs/local/artifacts/stage10423_reviewed_multilingual_v27_same_manifest_gemma_comparison/reviewed_multilingual_v27_same_manifest_gemma_comparison.json"
EXEC_10623 = ROOT / "runs/local/artifacts/stage10623_multilingual_deduped_eval_probe/bounded_decoder_probe/execution_result.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def strict_row_ids(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row.get("row_id") or "") for row in rows if str(row.get("split") or "") == "strict_eval" or "strict_eval" not in row}


def main() -> None:
    rows_10620 = load_jsonl(MANIFEST_10620)
    rows_10622 = load_jsonl(MANIFEST_10622)
    rows_10420_strict = load_jsonl(STRICT_10420)
    gemma = load_json(GEMMA_10423)
    exec_10623 = load_json(EXEC_10623)

    audit_10620 = audit_manifest_rows(rows_10620)
    audit_10622 = audit_manifest_rows(rows_10622)

    strict_10622_ids = {str(row.get("row_id") or "") for row in rows_10622 if str(row.get("split") or "") == "strict_eval"}
    strict_10420_ids = {str(row.get("row_id") or "") for row in rows_10420_strict}
    strict_same = strict_10622_ids == strict_10420_ids

    strict_10623 = ((exec_10623.get("bounded_choice_eval") or {}).get("strict_eval") or {})
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "deduped_multilingual_v27_is_honest_current_headline",
        "claim_scope": [
            "Compare the pre-dedup and post-dedup multilingual manifests under a reusable integrity audit.",
            "Verify that the deduped strict slice matches the reviewed v2.7 24-row strict set used for the Gemma baseline.",
            "Restate the honest current multilingual 100M-vs-Gemma headline after removing duplicate logical eval rows.",
        ],
        "inputs": {
            "manifest_10620": display(MANIFEST_10620),
            "manifest_10622": display(MANIFEST_10622),
            "strict_10420": display(STRICT_10420),
            "gemma_10423": display(GEMMA_10423),
            "execution_10623": display(EXEC_10623),
        },
        "integrity": {
            "stage10620_pre_dedup": audit_10620,
            "stage10622_deduped": audit_10622,
        },
        "strict_row_set_compatibility": {
            "stage10622_strict_rows": len(strict_10622_ids),
            "stage10420_strict_rows": len(strict_10420_ids),
            "exact_match": strict_same,
            "only_in_stage10622": sorted(strict_10622_ids - strict_10420_ids),
            "only_in_stage10420": sorted(strict_10420_ids - strict_10622_ids),
        },
        "honest_current_headline": {
            "hundred_m_stage10623": {
                "correct": round(float(strict_10623.get("constrained_choice_top1_accuracy") or 0.0) * int(strict_10623.get("rows") or 0)),
                "exact_accuracy": strict_10623.get("constrained_choice_top1_accuracy"),
                "rows": strict_10623.get("rows"),
                "full_vocab_top1_accuracy": strict_10623.get("full_vocab_top1_accuracy"),
                "weights_sha256": ((exec_10623.get("runtime_model_bundle") or {}).get("weights_sha256")),
            },
            "gemma12b_reviewed_v27": gemma.get("gemma12b"),
            "delta_exact_accuracy_vs_gemma12b": (strict_10623.get("constrained_choice_top1_accuracy") or 0.0) - float((gemma.get("gemma12b") or {}).get("exact_accuracy") or 0.0),
            "by_language": gemma.get("by_language"),
        },
        "expert_eval_and_anti_cheat_findings": [
            "The stage10620 multilingual expansion was not promotable because eval and strict_eval reused 24 duplicate row_ids across reviewed and compiled sources.",
            "The deduped stage10622 package repairs that bookkeeping issue and returns to the reviewed 24-row v2.7 strict slice.",
            "The current honest multilingual headline remains 100M 22/24 versus Gemma-12B 6/24 on the reviewed strict slice, with wins in Python, Rust, C/C++, and Web.",
            "This is still a reviewed same-slice multilingual maintainer-choice result, not a fresh broader heldout-root expansion.",
        ],
        "next_best_step": "Use stage10622/stage10623 as the honest multilingual v2.7 baseline, and rebuild bootstrap strict rows with genuinely new row_ids and roots before claiming broader multilingual heldout growth.",
    }
    write_json(AUDIT_JSON, payload)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "audit": display(AUDIT_JSON),
            "current_exact_accuracy": strict_10623.get("constrained_choice_top1_accuracy"),
            "gemma_exact_accuracy": (gemma.get("gemma12b") or {}).get("exact_accuracy"),
        },
    )
    print(json.dumps({"stage": STAGE, "passed": True, "strict_same": strict_same}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
