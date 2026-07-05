#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8811
NAME = "stage8811_split_deduped_closed_ce_candidate_selection_audit"
MANIFEST = ROOT / "runs/local/artifacts/stage8810_split_deduped_closed_ce_candidate_selection/split_deduped_closed_ce_candidate_selection.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SPLIT_DEDUPED_CLOSED_CE_CANDIDATE_SELECTION_AUDIT_STAGE8811.md"
AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    rows = read_jsonl(MANIFEST)
    selected = [row for row in rows if (row.get("selection_status") or {}).get("selected_by_split_dedup") is True]
    selected_hashes = [(row.get("clean_state") or {}).get("decoder_target_text_sha256") for row in selected]
    selected_refs = [(row.get("clean_state") or {}).get("decoder_target_ref") for row in selected]
    metrics = {
        **AUTHORITY_CLOSED,
        "rows": len(rows),
        "selected_candidate_rows": len(selected),
        "blocked_rows": len(rows) - len(selected),
        "route_counts": dict(sorted(Counter(row.get("route") for row in rows).items())),
        "selected_split_counts": dict(sorted(Counter(row.get("split") for row in selected).items())),
        "selected_argument_counts": dict(sorted(Counter((row.get("clean_state") or {}).get("bounded_argument_type") for row in selected).items())),
        "authority_rows": sum(int(any((row.get("authority") or {}).values())) for row in rows),
        "training_loss_rows": sum(int(any((row.get("loss_mask") or {}).values())) for row in rows),
        "decoder_ce_eligible_now_rows": sum(int((row.get("clean_state") or {}).get("decoder_ce_eligible_now") is True) for row in rows),
        "selected_hash_unique_rows": len(set(selected_hashes)),
        "selected_ref_unique_rows": len(set(selected_refs)),
        "selected_eval_rows": sum(int(row.get("split") == "eval") for row in selected),
        "selected_strict_rows": sum(int(row.get("split") in {"strict", "strict_eval"}) for row in selected),
        "target_text_in_manifest_flags": sum(int((row.get("anti_cheat") or {}).get("target_text_in_manifest") is True) for row in rows),
        "probe_ready": False,
        "probe_blockers": [
            "selected_candidates_are_train_only",
            "eval_and_strict_need_unique_target_materialization_or_holdout_design",
            "decoder_ce_loss_not_authorized",
            "explicit_execution_authorization_required",
        ],
    }
    failures = []
    expected = {
        "rows": 504,
        "selected_candidate_rows": 120,
        "blocked_rows": 384,
        "authority_rows": 0,
        "training_loss_rows": 0,
        "decoder_ce_eligible_now_rows": 0,
        "selected_hash_unique_rows": 120,
        "selected_ref_unique_rows": 120,
        "target_text_in_manifest_flags": 0,
    }
    for key, expected_value in expected.items():
        if metrics[key] != expected_value:
            failures.append(f"metric_mismatch:{key}:{metrics[key]}!={expected_value}")
    if metrics["selected_eval_rows"] != 0 or metrics["selected_strict_rows"] != 0:
        failures.append("unexpected_eval_or_strict_selected")
    metrics["failures"] = failures
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "artifacts": {
            "audit_card": str((OUT_DIR / "split_deduped_closed_ce_candidate_selection_audit_card.json").relative_to(ROOT)),
            "manifest": str(MANIFEST.relative_to(ROOT)),
            "audit_script": "scripts/audit_stage8811_split_deduped_closed_ce_candidate_selection.py",
        },
        "decision": "Split-deduped closed CE selection passed as train-only candidate support; it is not probe-ready because eval/strict targets are blocked." if not failures else "Split-deduped closed CE selection failed audit.",
        "next_best_step": "Attach split-deduped closed CE selection to graph, then recover eval/strict unique target materialization or a heldout evaluation design.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "split_deduped_closed_ce_candidate_selection_audit_card.json").write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8811 Split-Deduped Closed CE Candidate Selection Audit",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Selected candidate rows: `{metrics['selected_candidate_rows']}`",
        f"Selected split counts: `{metrics['selected_split_counts']}`",
        f"Probe ready: `{metrics['probe_ready']}`",
        "",
        "The selected set is train-only. That is safe as candidate support, but it is not a CE probe package because eval/strict rows require unique target materialization or a heldout design.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
